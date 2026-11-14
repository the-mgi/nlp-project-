"""Normalise control-set item ids in verdict logs to ``cjb::<task>::<question_id>::<row>``.

Early verdict logs used ids with an extra generator component
(``cjb::<task>::<generator>::<question_id>::<row>``); this rewrites them in place.

    python scripts/normalise_ids.py results/raw/*.jsonl
"""
import json
import sys


def norm(item_id: str) -> str:
    parts = item_id.split("::")
    if parts[0] == "cjb" and len(parts) == 5:
        return "::".join(parts[:2] + parts[3:])
    return item_id


for path in sys.argv[1:]:
    rows = []
    for line in open(path):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "item_id" in r:
            r["item_id"] = norm(r["item_id"])
        rows.append(r)
    with open(path, "w") as fo:
        for r in rows:
            fo.write(json.dumps(r) + "\n")
