"""Live demonstration for the viva.

    python scripts/demo.py --model /opt/work/models/qwen2.5-coder-1.5b-instruct-q8_0.gguf [--item ITEM_ID]

1. shows one RepoJudgeBench pair: the issue, the injected defect and the exact
   lines in which the defective variant differs from the real (gold) patch,
2. shows that both patches passed the same tests,
3. asks a local judge to compare them in both presentation orders and prints
   the verdict probabilities.
"""
import argparse
import difflib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repojudgebench.judge import LocalJudge  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--item", default=None)
    ap.add_argument("--items", default="data/items/diff_only.jsonl")
    ap.add_argument("--meta", default="data/items/meta.jsonl")
    args = ap.parse_args()
    items = {json.loads(l)["item_id"]: json.loads(l) for l in open(args.items)}
    meta = {json.loads(l)["item_id"]: json.loads(l) for l in open(args.meta)}
    iid = args.item or min(items, key=lambda k: len(items[k]["pos"]) + len(items[k]["neg"]))
    it, m = items[iid], meta[iid]
    print(f"== {iid}\nrepo: {m['repo']}   created: {m['created_at']}   source: {m['source']}")
    print(f"defect class: {m['defect_class']}   operator: {m['operator']}   site: {m['site_origin']}")
    print(f"injected defect: {m['description']}")
    print(f"gold patch: {m['gold_changed_lines']} changed lines, {m['gold_files']} file(s), "
          f"{m['gold_hunks']} hunk(s); tests passing for BOTH patches: {m['n_tests_passed']}\n")
    print("-- where the defective variant differs from the gold patch --")
    for line in difflib.unified_diff(it["pos"].splitlines(), it["neg"].splitlines(),
                                     "gold.diff", "variant.diff", n=2, lineterm=""):
        print(line)
    judge = LocalJudge(args.model, n_ctx=8192)
    for order, a, b in (("gold shown as A", it["pos"], it["neg"]), ("gold shown as B", it["neg"], it["pos"])):
        r = judge.pairwise(it["query"], a, b)
        verdict = "A" if r["p_a"] > 0.5 else "B"
        correct = (verdict == "A") == order.endswith("A")
        print(f"\n[{order}] P(A better) = {r['p_a']:.3f} -> verdict [[{verdict}>...]] "
              f"({'correct' if correct else 'WRONG'}), prompt = {r['n_tokens']} tokens")


if __name__ == "__main__":
    main()
