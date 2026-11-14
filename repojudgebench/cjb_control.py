"""CodeJudgeBench control subset (single-file, test-decidable regime).

Samples pairs from ``mattymchen/codejudgebench`` (Apache-2.0) so that the same
local judges can be compared under the same prompt in the single-file regime.
To keep CPU inference tractable we use the responses of a single generator model,
chosen automatically as the one with the shortest responses (smallest median
question + responses length over the three tasks), and keep pairs whose question
+ both responses fit in ``--max-chars`` characters.  The query
and answers are filled exactly as in the dataset card's quick-start
(``question_content``, ``pos_response``, ``neg_response``).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

TASKS = ("codegen", "coderepair", "testgen")


def shortest_generator(data_dir: str) -> str:
    """Generator split (present for all tasks) with the smallest median length of
    question + both responses."""
    gens = None
    for task in TASKS:
        g = {p.stem for p in (Path(data_dir) / task).glob("*.parquet")}
        gens = g if gens is None else gens & g
    best = {}
    for gen in sorted(gens):
        lens = []
        for task in TASKS:
            df = pd.read_parquet(Path(data_dir) / task / f"{gen}.parquet")
            lens += list(df.question_content.str.len() + df.pos_response.str.len() + df.neg_response.str.len())
        best[gen] = float(pd.Series(lens).median())
    return min(best, key=best.get)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/opt/work/data/cjb")
    ap.add_argument("--generator", default=None,
                    help="generator split to use (default: the one with the shortest responses)")
    ap.add_argument("--per-task", type=int, default=15)
    ap.add_argument("--max-chars", type=int, default=6000)
    ap.add_argument("--out", default="data/items/cjb_control.jsonl")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    gen = args.generator or shortest_generator(args.data)
    rows = []
    for task in TASKS:
        df = pd.read_parquet(Path(args.data) / task / f"{gen}.parquet")
        n_chars = df.question_content.str.len() + df.pos_response.str.len() + df.neg_response.str.len()
        df = df[n_chars <= args.max_chars]
        df = df.sample(n=min(args.per_task, len(df)), random_state=args.seed)
        for i, r in df.iterrows():
            rows.append({"item_id": f"cjb::{task}::{r.question_id}::{i}",
                         "task": task, "query": r.question_content,
                         "pos": r.pos_response, "neg": r.neg_response,
                         "difficulty": r.difficulty})
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fo:
        for r in rows:
            fo.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} control pairs to {args.out}")


if __name__ == "__main__":
    main()
