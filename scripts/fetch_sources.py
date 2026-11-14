"""Download the task sources (SWE-bench-Live full split, SWE-rebench) and the
CodeJudgeBench control data from Hugging Face into ``$WORK/data``.

    python scripts/fetch_sources.py /opt/work
"""
import os
import sys
import urllib.request

import pandas as pd

WORK = sys.argv[1] if len(sys.argv) > 1 else "/opt/work"
HF = "https://huggingface.co/datasets"
# revisions used in the paper (pinned for reproducibility)
REV = {"SWE-bench-Live/SWE-bench-Live": "babb27e45e072219195db7a744bbf0d3c1a36e56",
       "nebius/SWE-rebench": "89cdfbab4ab1bd8f5a658bb212d1b63624f4f881",
       "mattymchen/codejudgebench": "dd766c8a8e8d0088619362e21932d8e478a4c722"}


def get(url: str, dest: str):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        urllib.request.urlretrieve(url, dest)
    return dest


def main():
    d = f"{WORK}/data"
    live = [get(f"{HF}/SWE-bench-Live/SWE-bench-Live/resolve/{REV['SWE-bench-Live/SWE-bench-Live']}/data/full-0000{i}-of-00002.parquet",
                f"{d}/swelive/full-0000{i}-of-00002.parquet") for i in range(2)]
    pd.concat([pd.read_parquet(f) for f in live]).to_pickle(f"{d}/swelive/full.pkl")
    filt = get(f"{HF}/nebius/SWE-rebench/resolve/{REV['nebius/SWE-rebench']}/data/filtered-00000-of-00001.parquet",
               f"{d}/rebench/filtered.parquet")
    pd.read_parquet(filt).to_pickle(f"{d}/rebench/rebench_filtered.pkl")
    test = [get(f"{HF}/nebius/SWE-rebench/resolve/{REV['nebius/SWE-rebench']}/data/test-0000{i}-of-00002.parquet",
                f"{d}/rebench/test-0000{i}-of-00002.parquet") for i in range(2)]
    pd.concat([pd.read_parquet(f) for f in test]).to_pickle(f"{d}/rebench/rebench_test.pkl")
    # CodeJudgeBench control data: every generator split that exists for all three tasks
    import json
    api = f"https://huggingface.co/api/datasets/mattymchen/codejudgebench/tree/{REV['mattymchen/codejudgebench']}"
    splits = {}
    for task in ("codegen", "coderepair", "testgen"):
        with urllib.request.urlopen(f"{api}/{task}") as fh:
            names = [e["path"].split("/")[-1] for e in json.load(fh) if e["path"].endswith(".parquet")]
        splits[task] = {n.split("-00000-of-")[0]: n for n in names}
    common = set.intersection(*(set(v) for v in splits.values()))
    for task in splits:
        for gen in sorted(common):
            get(f"{HF}/mattymchen/codejudgebench/resolve/{REV['mattymchen/codejudgebench']}/{task}/{splits[task][gen]}",
                f"{d}/cjb/{task}/{gen}.parquet")
    print("sources ready in", d)


if __name__ == "__main__":
    main()
