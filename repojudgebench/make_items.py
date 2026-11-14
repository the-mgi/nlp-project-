"""Turn the verified build output into judge items, one JSONL file per prompt condition.

Each item holds a query, the gold patch (``pos``) and the defective variant
(``neg``), and metadata used in the analysis.  Conditions:

* ``diff_only``        - issue + two diffs (primary baseline, CodeJudgeBench protocol)
* ``ctx_retrieved_<B>`` - + retrieved definitions / call sites, at most B characters
* ``ctx_file_<B>``      - + parent-commit versions of the touched files, at most B characters

Also applies the SWE-Bench+ style solution-leakage filter: an instance is
flagged when a non-trivial line added by the gold patch appears verbatim in the
issue text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .diffutils import diff_stats, split_files, file_path
from .prompts import patch_answer, repo_query

CONTEXT_BUDGETS = (2000, 6000)


def load_build(path: str) -> list[dict]:
    recs = []
    for line in open(path):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        recs.append(r)
    return recs


def dedupe(recs: list[dict]) -> list[dict]:
    """One record per task: a task can be logged twice when a build was resumed
    after an interruption; keep its last successful record (else its last record)."""
    best: dict[str, dict] = {}
    for r in recs:
        iid = r.get("instance_id")
        if iid is None:
            continue
        if iid not in best or r.get("status") == "ok" or best[iid].get("status") != "ok":
            best[iid] = r
    return list(best.values())


def leaked(gold_diff: str, issue: str) -> bool:
    issue_n = re.sub(r"\s+", " ", issue or "")
    for line in gold_diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            s = line[1:].strip()
            if len(s) >= 30 and not s.startswith("#") and re.sub(r"\s+", " ", s) in issue_n:
                return True
    return False


def retrieved_context(ctx: dict, budget: int) -> str:
    parts, used = [], 0
    snippets = sorted(ctx.get("snippets", []), key=lambda s: 0 if s["kind"] == "definition" else 1)
    for s in snippets:
        block = f"# {s['path']} (from line {s['start']}; {s['kind']} of `{s['symbol']}`)\n{s['text'].rstrip()}\n"
        if used + len(block) > budget:
            remaining = budget - used
            if remaining > 300:
                parts.append(block[:remaining] + "\n# [... truncated ...]\n")
                used = budget
            break
        parts.append(block)
        used += len(block)
    return "```python\n" + "\n".join(parts) + "```" if parts else ""


def file_context(ctx: dict, budget: int) -> str:
    parts, used = [], 0
    for p, txt in ctx.get("files", {}).items():
        if not txt:
            continue
        block = f"# ===== {p} =====\n{txt.rstrip()}\n"
        if used + len(block) > budget:
            remaining = budget - used
            if remaining > 300:
                parts.append(block[:remaining] + "\n# [... truncated ...]\n")
            break
        parts.append(block)
        used += len(block)
    return "```python\n" + "\n".join(parts) + "```" if parts else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", nargs="+", default=["data/build/instances.jsonl"])
    ap.add_argument("--out", default="data/items")
    ap.add_argument("--tokenizer-gguf", default=None,
                    help="GGUF whose tokenizer is used to measure prompt length")
    ap.add_argument("--max-tokens", type=int, default=6000,
                    help="pairs whose diff-only prompt is longer are kept in the dataset "
                         "but not judged (CPU budget)")
    args = ap.parse_args()
    count_tokens = None
    if args.tokenizer_gguf:
        from llama_cpp import Llama
        from .prompts import CJB_PAIRWISE
        tok = Llama(model_path=args.tokenizer_gguf, vocab_only=True, verbose=False)

        def count_tokens(q, a, b):
            return len(tok.tokenize(CJB_PAIRWISE.format(query=q, answer_a=a, answer_b=b).encode(),
                                    add_bos=False, special=False))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    recs = dedupe([r for b in args.build for r in load_build(b)])
    items, meta_rows, n_leak = [], [], 0
    for r in recs:
        if r.get("status") != "ok":
            continue
        is_leak = leaked(r["gold_diff"], r.get("problem_statement", ""))
        n_leak += int(is_leak)
        for v in r["variants"]:
            gs, vs = r["gold_stats"], v["variant_stats"]
            meta = {
                "item_id": f"{r['instance_id']}::{v['defect_class']}::{v['operator']}",
                "instance_id": r["instance_id"], "repo": r["repo"], "source": r["source"],
                "created_at": r["created_at"], "defect_class": v["defect_class"],
                "operator": v["operator"], "site_origin": v["site_origin"],
                "description": v["description"], "file": v["file"],
                "gold_changed_lines": gs["changed_lines"], "gold_files": gs["files"],
                "gold_hunks": gs["hunks"], "variant_changed_lines": vs["changed_lines"],
                "variant_files": vs["files"], "variant_hunks": vs["hunks"],
                "n_tests_passed": v.get("n_tests_passed"), "solution_leak": is_leak,
                "license_name": r.get("license_name"),
            }
            if count_tokens is not None:
                meta["prompt_tokens"] = count_tokens(
                    repo_query(r["repo"], r.get("problem_statement", "")),
                    patch_answer(r["gold_diff"]), patch_answer(v["variant_diff"]))
                meta["judged"] = (meta["prompt_tokens"] <= args.max_tokens) and not is_leak
            else:
                meta["judged"] = not is_leak
            meta_rows.append(meta)
            items.append((meta, r, v))
    # deterministic pseudo-random order (stable when new pairs are added), so that
    # any prefix of an item file is an unbiased sample for time-limited judges
    items.sort(key=lambda t: hashlib.md5(t[0]["item_id"].encode()).hexdigest())
    meta_rows.sort(key=lambda m: hashlib.md5(m["item_id"].encode()).hexdigest())
    with (out / "meta.jsonl").open("w") as fo:
        for m in meta_rows:
            fo.write(json.dumps(m) + "\n")
    conds = {"diff_only": None}
    for b in CONTEXT_BUDGETS:
        conds[f"ctx_retrieved_{b}"] = ("retrieved", b)
        conds[f"ctx_file_{b}"] = ("file", b)
    for cname, spec in conds.items():
        with (out / f"{cname}.jsonl").open("w") as fo:
            for meta, r, v in items:
                if not meta["judged"]:
                    continue
                context = None
                if spec:
                    kind, b = spec
                    ctx = r.get("context") or {}
                    context = retrieved_context(ctx, b) if kind == "retrieved" else file_context(ctx, b)
                q = repo_query(r["repo"], r.get("problem_statement", ""), context or None)
                fo.write(json.dumps({"item_id": meta["item_id"], "query": q,
                                     "pos": patch_answer(r["gold_diff"]),
                                     "neg": patch_answer(v["variant_diff"]),
                                     "defect_class": meta["defect_class"]}) + "\n")
    print(f"pairs={len(items)} judged={sum(m['judged'] for m in meta_rows)} leak_instances={n_leak} "
          f"classes={Counter(m['defect_class'] for m in meta_rows)} "
          f"repos={len({m['repo'] for m in meta_rows})}")


if __name__ == "__main__":
    main()
