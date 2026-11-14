#!/usr/bin/env bash
# Incremental judging on the coordinator machine while the dataset is still being built:
# rebuild the item files from the current build output, then judge new pairs (resume-safe).
set -u
M=${MODELS_DIR:-/opt/work/models}
BUILD=${BUILD:-data/build/instances.jsonl}
for round in $(seq 1 ${ROUNDS:-100}); do
  python -m repojudgebench.make_items --build $BUILD --out data/items \
      --tokenizer-gguf "$M/qwen2.5-coder-1.5b-instruct-q8_0.gguf" 2>/dev/null | tail -1
  for spec in "qwen2.5-coder-1.5b qwen2.5-coder-1.5b-instruct-q8_0.gguf" "qwen3-1.7b Qwen3-1.7B-Q8_0.gguf"; do
    set -- $spec
    python -m repojudgebench.judge --model "$M/$2" --name "$1" --items data/items/diff_only.jsonl \
        --condition diff_only --out "results/raw/$1__diff_only.jsonl" 2>/dev/null
  done
  [ -f "${STOP_FILE:-/tmp/stop_local_judges}" ] && break
  sleep 60
done
