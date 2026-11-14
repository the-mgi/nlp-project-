#!/usr/bin/env bash
# Final analysis -> tables/figures -> paper and slides PDFs.
set -eu
PY=${PY:-python}
BUILDS="data/build/instances.jsonl data/build_shards/shard1/instances.jsonl data/build_shards/shard2/instances.jsonl data/build_shards/shard3/instances.jsonl"
$PY scripts/normalise_ids.py results/raw/*__*.jsonl
$PY -m repojudgebench.analysis --raw results/raw --meta data/items/meta.jsonl --build $BUILDS --out results \
    --models qwen2.5-coder-1.5b qwen2.5-coder-3b qwen3-1.7b qwen3-4b llama-3.2-3b gemma-3-4b qwen3-1.7b-think
$PY scripts/make_report.py results/summary.json paper/generated
(cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex >/dev/null && latexmk -c >/dev/null)
(cd slides && latexmk -pdf -interaction=nonstopmode -halt-on-error slides.tex >/dev/null && latexmk -c >/dev/null)
echo "paper: paper/main.pdf  slides: slides/slides.pdf"
