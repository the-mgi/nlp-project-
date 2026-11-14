"""Stage 1-4 of the pipeline: select post-cutoff PRs, inject defects, verify by execution.

For every selected task instance (a real merged pull request from SWE-bench-Live
or SWE-rebench, created after the cutoff date) we

1. start the instance's published Docker image (repository checked out at the
   PR's parent commit with a working test environment),
2. apply the gold patch and regenerate it with ``git diff`` (so that gold and
   defective variants are rendered by exactly the same tool),
3. run the AST mutation operators on every non-test Python file touched by the
   gold patch and keep at most one candidate per defect class,
4. apply the PR's test patch and run the PR-relevant test files on the gold
   patch and on every candidate.  A candidate is *admitted* only if every test
   that passes with the gold patch also passes with the candidate
   ("passes CI but is wrong"); candidates that break a test are logged as
   *caught by tests*,
5. collect neutral repository context from the parent commit (definitions of
   called symbols and call sites of modified functions) for the
   context-augmented judging condition (O6).

Usage::

    python -m repojudgebench.build_dataset --out data/build --workers 3 --max-instances 400
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import random
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import traceback
from pathlib import Path

import pandas as pd

from .diffutils import added_lines, diff_stats, file_path, is_test_path, split_files
from .mutate import find_mutations

CUTOFF = "2025-01-01"
MAX_GOLD_CHANGED_LINES = 400
TEST_TIMEOUT = 420
MIRROR = "mirror.gcr.io"
MIN_FREE_BYTES = 8 * 1024**3
PRIORITY = {"n_plus_one": 0, "unsafe_migration": 0, "race_condition": 1,
            "authorization_regression": 1, "resource_leak": 2,
            "silent_error_swallowing": 3}

_PRESCREEN = {
    "n_plus_one": [r"select_related|prefetch_related|selectinload|joinedload|subqueryload"],
    "unsafe_migration": [r"^\+\+\+ b/.*(migrations|alembic|versions)/.*\.py",
                         r"AddField|op\.add_column"],
    "race_condition": [r"^[+ ]\s*(async\s+)?with\s+[^:\n]*(lock|Lock|mutex|emaphore|atomic)",
                       r"select_for_update", r"^[+ ]\s*@\w*\.?atomic"],
    "authorization_regression": [
        r"^[+ ]\s*(if|elif)\b.*(perm|authori|authent|superuser|is_staff|is_admin|owner|"
        r"access|allowed|forbid|credential|login|privilege|csrf|api_key|auth)",
        r"^[+ ]\s*@\w*(login_required|permission|auth)"],
    "resource_leak": [r"^[+ ]\s*(async\s+)?with\s+.*\b(open|urlopen|ZipFile|TarFile|"
                      r"NamedTemporaryFile|TemporaryFile|socket|connect|Popen|Session|Client|"
                      r"ClientSession|fdopen|ThreadPoolExecutor|ProcessPoolExecutor|Pool)\s*\(",
                      r"^[+ ]\s*[\w\.\[\]]+\.close\(\)\s*$"],
    "silent_error_swallowing": [r"^[+ ]\s*except\b", r"^[+ ]\s*raise\b"],
}


# ---------------------------------------------------------------------------
# instance pool
# ---------------------------------------------------------------------------

def load_pool(swelive_dir: str, rebench_dir: str) -> pd.DataFrame:
    frames = []
    live = pd.read_pickle(os.path.join(swelive_dir, "full.pkl"))
    live = live.assign(source="SWE-bench-Live", license_name=None)
    frames.append(live)
    for name in ("rebench_filtered", "rebench_test"):
        p = os.path.join(rebench_dir, f"{name}.pkl")
        if os.path.exists(p):
            rb = pd.read_pickle(p)
            rb = rb.assign(source="SWE-rebench",
                           test_cmds=rb["install_config"].map(lambda c: [c["test_cmd"]]))
            frames.append(rb)
    cols = ["instance_id", "repo", "base_commit", "patch", "test_patch",
            "problem_statement", "created_at", "FAIL_TO_PASS", "PASS_TO_PASS",
            "test_cmds", "docker_image", "source", "license_name"]
    df = pd.concat([f[cols] for f in frames], ignore_index=True)
    df["created_at"] = df["created_at"].astype(str)
    df = df[df["created_at"] >= CUTOFF]
    df = df[df["docker_image"].notna()]
    df["key"] = df["instance_id"].str.lower()
    df = df.drop_duplicates("key", keep="first")  # SWE-bench-Live listed first
    return df.reset_index(drop=True)


def prescreen(row) -> tuple[set[str], int]:
    """Cheap diff-level screen for candidate mutation sites; returns the classes
    that *might* apply and the gold diff size."""
    src = [f for f in split_files(row["patch"])
           if file_path(f).endswith(".py") and not is_test_path(file_path(f))]
    txt = "\n".join(src)
    classes = {c for c, ps in _PRESCREEN.items() if any(re.search(p, txt, re.M) for p in ps)}
    return classes, diff_stats(row["patch"])["changed_lines"]


# ---------------------------------------------------------------------------
# docker helpers
# ---------------------------------------------------------------------------

def sh(cmd: list[str] | str, timeout: int = 600, check: bool = True, input: str | None = None):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True,
                       timeout=timeout, input=input, errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed ({r.returncode}): {cmd}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


class Container:
    def __init__(self, image: str):
        self.image = image
        self.cid = sh(["docker", "run", "-d", "--entrypoint", "", image, "sleep", "infinity"]).stdout.strip()

    def exec(self, script: str, timeout: int = 600, check: bool = True):
        # SWE-rebench images keep the environment in a conda env called "testbed"
        pre = ("for a in /opt/miniconda3/bin/activate /opt/conda/bin/activate; do "
               "if [ -f $a ]; then source $a testbed >/dev/null 2>&1; break; fi; done; ")
        return sh(["docker", "exec", self.cid, "bash", "-lc", pre + script], timeout=timeout, check=check)

    def put(self, path: str, content: str):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".tmp") as fh:
            fh.write(content)
            tmp = fh.name
        try:
            self.exec(f"mkdir -p {shlex.quote(os.path.dirname(path) or '.')}")
            sh(["docker", "cp", tmp, f"{self.cid}:{path}"])
        finally:
            os.unlink(tmp)

    def get(self, path: str) -> str:
        return self.exec(f"cat {shlex.quote(path)}").stdout

    def close(self):
        sh(["docker", "rm", "-f", self.cid], check=False)


def staged_diff(c: Container, paths: list[str] | None = None) -> str:
    spec = " ".join(shlex.quote(p) for p in paths) if paths else ""
    out = c.exec(f"cd /testbed && git add -A {spec} >/dev/null 2>&1; "
                 f"git -c core.quotepath=off diff --cached --no-color --no-ext-diff HEAD -- {spec}; "
                 f"git reset -q").stdout
    return out


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

_RESULT_RE = re.compile(r"^(PASSED|FAILED|ERROR|XFAIL|XPASS|SKIPPED)\s+(\S+)", re.M)


def pick_test_cmd(cmds: list[str]) -> str:
    """Pick the pytest invocation among the instance's test commands.  ``uv run``
    must not try to re-sync the environment (the containers have no network
    access to package indexes), so ``--no-sync`` is added."""
    cmd = next((c for c in cmds if "pytest" in c),
               next((c for c in cmds if c.startswith("hatch run")), "python -m pytest -rA"))
    cmd = cmd.split("&&")[-1].strip() if "&&" in cmd else cmd
    if cmd.startswith("uv run ") and "--no-sync" not in cmd:
        cmd = "uv run --no-sync " + cmd[len("uv run "):]
    return cmd


def build_test_cmd(test_cmd: str, test_files: list[str]) -> str:
    toks = shlex.split(test_cmd)
    try:
        i = next(k for k, t in enumerate(toks) if t.endswith("pytest") or t == "pytest")
    except StopIteration:
        i = len(toks) - 1
    head, rest = toks[: i + 1], toks[i + 1:]
    if toks and toks[0] == "hatch":
        head, rest = toks, []
    elif not any(t.endswith("pytest") for t in head):
        head, rest = ["python", "-m", "pytest"], []
    keep, skip = [], False
    for k, t in enumerate(rest):
        if skip:
            skip = False
            continue
        if t in ("--pyargs",):
            skip = True
            continue
        if t.startswith("--cov"):
            if t in ("--cov", "--cov-report") and k + 1 < len(rest) and not rest[k + 1].startswith("-"):
                skip = True
            continue
        if t.startswith("-"):
            keep.append(t)
            if t in ("-m", "-k", "-p", "-c", "-o", "-W", "-n", "--rootdir", "--tb", "--ignore",
                     "--deselect", "--durations", "--maxfail", "--timeout", "--log-level",
                     "--import-mode", "--dist", "--reruns") and k + 1 < len(rest):
                keep.append(rest[k + 1])
                skip = True
            continue
        # positional (test path or package) -> replaced by our file list
    if "-rA" not in keep:
        keep.append("-rA")
    keep += ["-p", "no:cacheprovider", "--color=no"]
    return " ".join(shlex.quote(t) for t in head + keep + test_files)


def run_tests(c: Container, cmd: str) -> tuple[dict[str, str], str]:
    r = c.exec(f"cd /testbed && timeout {TEST_TIMEOUT} {cmd}", timeout=TEST_TIMEOUT + 60, check=False)
    out = r.stdout + "\n" + r.stderr
    res = {}
    for status, name in _RESULT_RE.findall(out):
        res[name] = status
    return res, out[-3000:]


# ---------------------------------------------------------------------------
# context retrieval (from the parent commit -> neutral w.r.t. both candidates)
# ---------------------------------------------------------------------------

_DEF_RE = re.compile(r"^[+\- ]\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", re.M)
_CALL_RE = re.compile(r"([A-Za-z_]\w*)\s*\(")
import builtins as _b
_BUILTINS = set(dir(_b))
_SKIP_NAMES = _BUILTINS | {"self", "cls", "super", "print", "len", "str", "int", "dict",
                           "list", "set", "tuple", "isinstance", "getattr", "setattr",
                           "hasattr", "range", "enumerate", "zip", "open", "sorted", "format",
                           "append", "get", "join", "items", "keys", "values", "update"}


def collect_context(c: Container, gold_diff: str, variant_diffs: list[str],
                    max_snippets: int = 40) -> dict:
    files = [file_path(f) for f in split_files(gold_diff)]
    ctx = {"files": {}, "snippets": []}
    for p in files:
        r = c.exec(f"cd /testbed && git show HEAD:{shlex.quote(p)} 2>/dev/null | head -c 60000", check=False)
        ctx["files"][p] = r.stdout
    all_diffs = gold_diff + "\n".join(variant_diffs)
    modified_funcs = set()
    # enclosing function names from hunk headers and def lines
    for m in re.finditer(r"^@@[^@]*@@\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", all_diffs, re.M):
        modified_funcs.add(m.group(1))
    modified_funcs |= set(_DEF_RE.findall(all_diffs))
    called = set()
    for line in all_diffs.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            called |= set(_CALL_RE.findall(line))
    called = {n for n in called if n not in _SKIP_NAMES and len(n) > 2} - modified_funcs
    seen = set()

    def grab(path: str, line: int, kind: str, sym: str, radius: int = 12):
        key = (path, line // (radius * 2))
        if key in seen or path in files and kind == "caller" and False:
            return
        seen.add(key)
        r = c.exec(f"cd /testbed && git show HEAD:{shlex.quote(path)} 2>/dev/null | "
                   f"sed -n '{max(1, line - 2)},{line + radius * 2}p'", check=False)
        if r.stdout.strip():
            ctx["snippets"].append({"kind": kind, "symbol": sym, "path": path,
                                    "start": max(1, line - 2), "text": r.stdout})

    for sym in sorted(called)[:25]:
        r = c.exec(f"cd /testbed && git grep -n -E '^\\s*(async\\s+)?(def|class)\\s+{sym}\\b' "
                   f"HEAD -- '*.py' 2>/dev/null | grep -v -E '/(tests?|testing)/|test_' | head -2",
                   check=False)
        for ln in r.stdout.splitlines():
            parts = ln.split(":", 3)
            if len(parts) >= 3 and parts[2].isdigit():
                grab(parts[1], int(parts[2]), "definition", sym)
    for sym in sorted(modified_funcs)[:15]:
        r = c.exec(f"cd /testbed && git grep -n -E '[.( ]{sym}\\(' HEAD -- '*.py' 2>/dev/null | "
                   f"grep -v -E '/(tests?|testing)/|test_' | grep -v -E 'def {sym}\\(' | head -3",
                   check=False)
        for ln in r.stdout.splitlines():
            parts = ln.split(":", 3)
            if len(parts) >= 3 and parts[2].isdigit():
                grab(parts[1], int(parts[2]), "caller", sym, radius=8)
        if len(ctx["snippets"]) >= max_snippets:
            break
    return ctx


# ---------------------------------------------------------------------------
# per-instance processing
# ---------------------------------------------------------------------------

def select_candidates(muts_by_file: list[tuple[str, object]], seed: str, k: int = 3):
    rng = random.Random(int(hashlib.md5(seed.encode()).hexdigest(), 16))
    by_class: dict[str, list] = {}
    for path, m in muts_by_file:
        by_class.setdefault(m.defect_class, []).append((path, m))
    chosen = []
    for cls in sorted(by_class, key=lambda c: (PRIORITY[c], c)):
        cands = by_class[cls]
        rng.shuffle(cands)
        cands.sort(key=lambda pm: 0 if pm[1].site_origin == "added" else 1)
        chosen.append(cands[:2])  # one primary + one fallback per class
    return chosen[:k]


def process_instance(row: dict, out_dir: Path, log) -> dict:
    iid = row["instance_id"]
    rec = {"instance_id": iid, "repo": row["repo"], "source": row["source"],
           "created_at": row["created_at"], "status": None, "variants": [], "rejected": []}
    t0 = time.time()
    img = row["docker_image"]
    pulled = False
    c = None
    try:
        # images are large: wait until there is room for one more on disk
        for _ in range(120):
            if shutil.disk_usage("/").free > MIN_FREE_BYTES:
                break
            time.sleep(10)
        # Docker Hub rate-limits anonymous pulls; Google's public Docker Hub
        # mirror serves the same images without that limit.
        r = sh(["docker", "pull", "-q", f"{MIRROR}/{img}"], timeout=900, check=False)
        if r.returncode == 0:
            img = f"{MIRROR}/{img}"
        else:
            sh(["docker", "pull", "-q", img], timeout=900)
        pulled = True
        c = Container(img)
        c.put("/tmp/gold.diff", row["patch"])
        r = c.exec("cd /testbed && git apply --whitespace=nowarn /tmp/gold.diff || patch -p1 --forward < /tmp/gold.diff",
                   check=False)
        if r.returncode != 0:
            rec["status"] = "gold_apply_failed"
            return rec
        src_files = [file_path(f) for f in split_files(row["patch"])]
        src_files = [p for p in src_files if not is_test_path(p)]
        gold_diff = staged_diff(c, src_files)
        if not gold_diff.strip():
            rec["status"] = "empty_gold_diff"
            return rec
        # mutation candidates
        muts = []
        post = {}
        for fd in split_files(gold_diff):
            p = file_path(fd)
            if not p.endswith(".py"):
                continue
            try:
                post[p] = c.get(f"/testbed/{p}")
            except RuntimeError:
                continue
            for m in find_mutations(post[p], added_lines(fd), p):
                muts.append((p, m))
        if not muts:
            rec["status"] = "no_mutation_site"
            return rec
        groups = select_candidates(muts, iid)
        # render variant diffs (before the test patch is applied)
        cand = []
        for group in groups:
            for p, m in group:
                c.put(f"/testbed/{p}", m.new_source)
                vd = staged_diff(c, src_files)
                c.put(f"/testbed/{p}", post[p])
                if vd.strip() and vd != gold_diff:
                    cand.append((p, m, vd))
        # tests
        c.put("/tmp/test.diff", row["test_patch"] or "")
        if (row["test_patch"] or "").strip():
            c.exec("cd /testbed && git apply --whitespace=nowarn /tmp/test.diff || patch -p1 --forward < /tmp/test.diff",
                   check=False)
        tfiles = {file_path(f) for f in split_files(row["test_patch"] or "")}
        tfiles |= {t.split("::")[0] for t in list(row["FAIL_TO_PASS"])}
        tfiles = sorted(p for p in tfiles if p.endswith(".py"))
        exist = c.exec("cd /testbed && for f in " + " ".join(shlex.quote(p) for p in tfiles) +
                       "; do [ -f \"$f\" ] && echo \"$f\"; done", check=False).stdout.split()
        if not exist:
            rec["status"] = "no_test_files"
            return rec
        cmd = build_test_cmd(pick_test_cmd(list(row["test_cmds"])), exist)
        rec["test_cmd"] = cmd
        gold_res, gold_log = run_tests(c, cmd)
        f2p = [t for t in list(row["FAIL_TO_PASS"])]
        gold_pass = {t for t, s in gold_res.items() if s in ("PASSED", "XFAIL")}
        f2p_ok = [t for t in f2p if t in gold_res]
        if not gold_pass or (f2p_ok and not all(gold_res.get(t) == "PASSED" for t in f2p_ok)) \
                or (f2p and not f2p_ok and len(gold_pass) == 0):
            rec["status"] = "gold_tests_not_green"
            rec["gold_log"] = gold_log
            return rec
        rec["n_gold_pass"] = len(gold_pass)
        admitted_classes = set()
        context_needed = []
        for p, m, vd in cand:
            if m.defect_class in admitted_classes:
                continue
            c.put(f"/testbed/{p}", m.new_source)
            vres, vlog = run_tests(c, cmd)
            c.put(f"/testbed/{p}", post[p])
            broken = sorted(t for t in gold_pass if vres.get(t) not in ("PASSED", "XFAIL"))
            info = {"file": p, **m.to_dict(), "variant_diff": vd,
                    "variant_stats": diff_stats(vd)}
            if broken:
                info["caught_by_tests"] = broken[:20]
                rec["rejected"].append(info)
            else:
                info["n_tests_passed"] = len(gold_pass)
                rec["variants"].append(info)
                admitted_classes.add(m.defect_class)
                context_needed.append(vd)
        rec["gold_diff"] = gold_diff
        rec["gold_stats"] = diff_stats(gold_diff)
        rec["problem_statement"] = row["problem_statement"]
        rec["base_commit"] = row["base_commit"]
        rec["license_name"] = row.get("license_name")
        if rec["variants"]:
            # back to the parent commit state is not needed: context is read from HEAD (= parent)
            rec["context"] = collect_context(c, gold_diff, context_needed)
        rec["status"] = "ok" if rec["variants"] else "all_caught_by_tests"
        return rec
    except subprocess.TimeoutExpired:
        rec["status"] = "timeout"
        return rec
    except Exception as e:  # noqa: BLE001 - recorded, pipeline continues
        rec["status"] = "error"
        rec["error"] = f"{type(e).__name__}: {e}"[:2000]
        return rec
    finally:
        rec["seconds"] = round(time.time() - t0, 1)
        if c is not None:
            c.close()
        if pulled:
            sh(["docker", "rmi", "-f", img], check=False, timeout=300)
        log(f"{iid}: {rec['status']} variants={len(rec['variants'])} "
            f"rejected={len(rec['rejected'])} {rec['seconds']}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--swelive", default="/opt/work/data/swelive")
    ap.add_argument("--rebench", default="/opt/work/data/rebench")
    ap.add_argument("--out", default="data/build")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--max-instances", type=int, default=400)
    ap.add_argument("--deadline-min", type=float, default=90.0,
                    help="stop scheduling new instances after this many minutes")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    done_path = out / "instances.jsonl"
    done = set()
    if done_path.exists():
        for line in done_path.open():
            try:
                done.add(json.loads(line)["instance_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    pool = load_pool(args.swelive, args.rebench)
    rows = []
    for _, r in pool.iterrows():
        classes, size = prescreen(r)
        if not classes or size > MAX_GOLD_CHANGED_LINES or r["instance_id"] in done:
            continue
        rows.append((min(PRIORITY[c] for c in classes), r["instance_id"], r.to_dict()))
    rng = random.Random(0)
    rng.shuffle(rows)
    rows.sort(key=lambda x: x[0])
    rows = rows[: args.max_instances]
    print(f"pool={len(pool)} screened={len(rows)}", flush=True)
    lock = threading.Lock()
    logf = (out / "build.log").open("a")

    def log(msg):
        with lock:
            logf.write(time.strftime("%H:%M:%S ") + msg + "\n")
            logf.flush()

    t_start = time.time()
    with cf.ThreadPoolExecutor(args.workers) as ex, done_path.open("a") as fo:
        futs = {}
        it = iter(rows)

        def submit_next():
            if (time.time() - t_start) / 60 > args.deadline_min:
                return False
            try:
                _, _, row = next(it)
            except StopIteration:
                return False
            futs[ex.submit(process_instance, row, out, log)] = row["instance_id"]
            return True

        for _ in range(args.workers * 2):
            submit_next()
        while futs:
            fin, _ = cf.wait(list(futs), return_when=cf.FIRST_COMPLETED)
            for f in fin:
                futs.pop(f)
                try:
                    rec = f.result()
                except Exception:  # noqa: BLE001
                    rec = {"instance_id": "?", "status": "crash", "error": traceback.format_exc()}
                with lock:
                    fo.write(json.dumps(rec, default=str) + "\n")
                    fo.flush()
                submit_next()


if __name__ == "__main__":
    main()
