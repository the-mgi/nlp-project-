"""Static-analysis baseline: can Ruff / Bandit tell the gold patch from the variant?

For every pair we materialise the parent-commit versions of the touched files,
apply the gold diff and the variant diff in two scratch git repositories, and
run Ruff and Bandit on the touched Python files.  A tool *flags* a patch when it
reports a finding (rule id + offending source line) that is absent from the
other patch.  Two rule sets are reported:

* ``relevant`` - rules that target the six defect classes, fixed in advance:
  Ruff BLE001 (blind except), S110/S112 (try-except-pass/continue), SIM105,
  SIM115 (open without context manager), E722 (bare except), and Bandit
  B110/B112;
* ``all``      - any Ruff rule (``--select ALL``) or any Bandit test.

Pairwise decision: choose the patch that is not flagged; if both or neither
are flagged the baseline abstains, which counts as 0.5 (a coin flip).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from .diffutils import file_path, split_files

RELEVANT_RUFF = {"BLE001", "S110", "S112", "SIM105", "SIM115", "E722"}
RELEVANT_BANDIT = {"B110", "B112"}
BIN = os.path.dirname(__import__("sys").executable)


def _materialise(files: dict[str, str], diff: str, root: str) -> list[str] | None:
    for p, txt in files.items():
        fp = Path(root) / p
        fp.parent.mkdir(parents=True, exist_ok=True)
        if txt:
            fp.write_text(txt)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    pf = Path(root) / ".patch.diff"
    pf.write_text(diff)
    r = subprocess.run(["git", "apply", "--whitespace=nowarn", str(pf)], cwd=root,
                       capture_output=True, text=True)
    pf.unlink()
    if r.returncode != 0:
        return None
    return [p for p in (file_path(f) for f in split_files(diff))
            if p.endswith(".py") and (Path(root) / p).exists()]


def _line(root: str, path: str, ln: int) -> str:
    try:
        return (Path(root) / path).read_text().splitlines()[ln - 1].strip()
    except (IndexError, OSError):
        return ""


def _findings(root: str, pyfiles: list[str]) -> Counter:
    out = Counter()
    if not pyfiles:
        return out
    r = subprocess.run([f"{BIN}/ruff", "check", "--isolated", "--select", "ALL",
                        "--output-format", "json", "--exit-zero", *pyfiles],
                       cwd=root, capture_output=True, text=True)
    try:
        for f in json.loads(r.stdout or "[]"):
            p = os.path.relpath(f["filename"], root)
            out[("ruff", f["code"], _line(root, p, f["location"]["row"]))] += 1
    except json.JSONDecodeError:
        pass
    r = subprocess.run([f"{BIN}/bandit", "-q", "-f", "json", *pyfiles], cwd=root,
                       capture_output=True, text=True)
    try:
        for f in json.loads(r.stdout or "{}").get("results", []):
            p = os.path.relpath(os.path.join(root, f["filename"]), root)
            out[("bandit", f["test_id"], _line(root, p, f["line_number"]))] += 1
    except json.JSONDecodeError:
        pass
    return out


def _flags(mine: Counter, other: Counter, relevant: bool) -> bool:
    for (tool, code, line), n in mine.items():
        if n > other.get((tool, code, line), 0):
            if not relevant or (tool == "ruff" and code in RELEVANT_RUFF) or \
                    (tool == "bandit" and code in RELEVANT_BANDIT):
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default="data/build/instances.jsonl")
    ap.add_argument("--out", default="results/raw/static_baseline.jsonl")
    args = ap.parse_args()
    rows = []
    for line in open(args.build):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("status") != "ok":
            continue
        files = (r.get("context") or {}).get("files", {})
        for v in r["variants"]:
            item = f"{r['instance_id']}::{v['defect_class']}"
            with tempfile.TemporaryDirectory() as g, tempfile.TemporaryDirectory() as b:
                pg = _materialise(files, r["gold_diff"], g)
                pb = _materialise(files, v["variant_diff"], b)
                if pg is None or pb is None:
                    rows.append({"item_id": item, "available": False})
                    continue
                fg, fb = _findings(g, pg), _findings(b, pb)
                rec = {"item_id": item, "available": True}
                for rs in ("relevant", "all"):
                    flag_gold, flag_var = _flags(fg, fb, rs == "relevant"), _flags(fb, fg, rs == "relevant")
                    rec[f"{rs}_flags_variant"] = flag_var
                    rec[f"{rs}_flags_gold"] = flag_gold
                    rec[f"{rs}_pairwise"] = 1.0 if (flag_var and not flag_gold) else \
                        0.0 if (flag_gold and not flag_var) else 0.5
                rows.append(rec)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fo:
        for rec in rows:
            fo.write(json.dumps(rec) + "\n")
    avail = [x for x in rows if x["available"]]
    print(f"static baseline: {len(avail)}/{len(rows)} pairs analysable")


if __name__ == "__main__":
    main()
