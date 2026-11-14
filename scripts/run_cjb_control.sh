#!/usr/bin/env bash
# Judge the CodeJudgeBench control subset with every local judge (both orders).
set -u
M=${MODELS_DIR:-/opt/work/models}
run(){ python -m repojudgebench.judge --model "$M/$2" --name "$1" --items data/items/cjb_control.jsonl \
        --condition cjb_control --out "results/raw/$1__cjb_control.jsonl"; }
run qwen2.5-coder-1.5b qwen2.5-coder-1.5b-instruct-q8_0.gguf
run qwen3-1.7b         Qwen3-1.7B-Q8_0.gguf
run qwen2.5-coder-3b   qwen2.5-coder-3b-instruct-q4_0.gguf
