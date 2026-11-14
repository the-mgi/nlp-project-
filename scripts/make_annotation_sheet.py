"""Create the human-validation sheet (proposal Stage 4) and compute Cohen's kappa.

    python scripts/make_annotation_sheet.py sheet --n 50     # writes data/annotation/sheet.csv
    python scripts/make_annotation_sheet.py kappa a.csv b.csv

Each row shows the issue, the gold diff and the variant diff (in random,
recorded order).  Annotators fill two columns with yes/no:
``variant_is_defective`` (the variant is genuinely worse to merge) and
``variant_is_plausible`` (a reviewer could believe the variant is a sincere fix).
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path


def sheet(n: int = 50, seed: int = 7):
    meta = [json.loads(l) for l in open("data/items/meta.jsonl")]
    items = {json.loads(l)["item_id"]: json.loads(l) for l in open("data/items/diff_only.jsonl")}
    meta = [m for m in meta if m["item_id"] in items]
    rng = random.Random(seed)
    by_cls: dict[str, list] = {}
    for m in meta:
        by_cls.setdefault(m["defect_class"], []).append(m)
    chosen = []
    while len(chosen) < min(n, len(meta)):
        for cls in sorted(by_cls):
            if by_cls[cls] and len(chosen) < n:
                chosen.append(by_cls[cls].pop(rng.randrange(len(by_cls[cls]))))
    out = Path("data/annotation")
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "sheet.csv", "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["item_id", "defect_class", "query", "patch_1", "patch_2", "variant_is_patch",
                    "variant_is_defective", "variant_is_plausible", "notes"])
        for m in chosen:
            it = items[m["item_id"]]
            swap = rng.random() < 0.5
            p1, p2 = (it["neg"], it["pos"]) if swap else (it["pos"], it["neg"])
            w.writerow([m["item_id"], m["defect_class"], it["query"], p1, p2, 1 if swap else 2, "", "", ""])
    print(f"wrote {len(chosen)} rows to {out / 'sheet.csv'}")


def kappa(a_path: str, b_path: str, col: str = "variant_is_defective"):
    def load(p):
        return {r["item_id"]: r[col].strip().lower() for r in csv.DictReader(open(p))}
    a, b = load(a_path), load(b_path)
    ids = [i for i in a if i in b and a[i] and b[i]]
    labels = sorted({a[i] for i in ids} | {b[i] for i in ids})
    po = sum(a[i] == b[i] for i in ids) / len(ids)
    pe = sum((sum(a[i] == l for i in ids) / len(ids)) * (sum(b[i] == l for i in ids) / len(ids))
             for l in labels)
    k = (po - pe) / (1 - pe) if pe < 1 else 1.0
    print(f"{col}: n={len(ids)} observed agreement={po:.3f} Cohen's kappa={k:.3f}")


if __name__ == "__main__":
    if sys.argv[1] == "sheet":
        sheet(int(sys.argv[3]) if len(sys.argv) > 3 else 50)
    else:
        kappa(sys.argv[2], sys.argv[3])
