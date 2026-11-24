#!/usr/bin/env bash
# Runs ON THE MASTER. Drives the whole experiment over the private network:
#   1. build:   each worker builds one shard of the benchmark in Docker
#   2. collect: shards -> master; master builds the judge items and the static baseline
#   3. judge:   items -> workers; each worker runs its assigned judges / conditions
#   4. collect: verdict logs -> master; analysis, tables, figures, paper and slides PDFs
# Usage: bash infra/scripts/orchestrate.sh   (env: BUILD_MIN, JUDGE_MIN)
set -euo pipefail
REPO=$HOME/nlp-project-
WORK=/opt/work
PY=$WORK/venv/bin/python
BUILD_MIN=${BUILD_MIN:-150}   # stop scheduling new build tasks after this many minutes
JUDGE_MIN=${JUDGE_MIN:-600}   # time budget per judge/condition (minutes)
mapfile -t W < "$HOME/workers.txt"
N=${#W[@]}
cd "$REPO"
log() { echo "[$(date +%H:%M:%S)] $*"; }
on() { ssh -o BatchMode=yes "${W[$1]}" "cd ~/nlp-project- && $2"; }

wait_for() {  # wait_for <marker text> <remote log file>
  for i in $(seq 0 $((N - 1))); do
    until on "$i" "grep -q '$1' $2 2>/dev/null"; do sleep 60; done
    log "worker $i: $1"
  done
}

# ---- 0. all nodes bootstrapped -------------------------------------------------
for i in $(seq 0 $((N - 1))); do
  until ssh -o BatchMode=yes -o ConnectTimeout=5 "${W[$i]}" "test -f /var/lib/rjb-bootstrap-done"; do
    log "waiting for worker $i bootstrap"
    sleep 30
  done
done
log "all $N workers ready"

# ---- 1. distributed benchmark construction --------------------------------------
for i in $(seq 0 $((N - 1))); do
  on "$i" "nohup bash scripts/shard_worker.sh build 0 100000 $i $N $BUILD_MIN shard$i > /tmp/build.log 2>&1 < /dev/null &"
done
log "build started on $N workers (deadline $BUILD_MIN min)"
wait_for "BUILD DONE" /tmp/build.log

# ---- 2. collect shards, build items, static baseline ------------------------------
for i in $(seq 0 $((N - 1))); do
  mkdir -p "data/build_shards/shard$i"
  rsync -az "${W[$i]}:nlp-project-/data/build_shards/shard$i/" "data/build_shards/shard$i/"
done
BUILDS=$(ls data/build_shards/shard*/instances.jsonl)
$PY -m repojudgebench.make_items --build $BUILDS --out data/items \
  --tokenizer-gguf "$WORK/models/qwen2.5-coder-1.5b-instruct-q8_0.gguf"
$PY -m repojudgebench.cjb_control --data "$WORK/data/cjb" --out data/items/cjb_control.jsonl
$PY -m repojudgebench.static_baseline --build $BUILDS --out results/raw/static_baseline.jsonl
for i in $(seq 0 $((N - 1))); do
  rsync -az data/items/ "${W[$i]}:nlp-project-/data/items/"
done
log "items distributed: $(wc -l < data/items/diff_only.jsonl) judged pairs"

# ---- 3. distributed judging (one job list per worker) ------------------------------
J="bash scripts/shard_worker.sh judge-cond"
B=$JUDGE_MIN
JOBS=(
  "$J qwen2.5-coder-1.5b qwen2.5-coder-1.5b cjb_control pairwise 0 $B 0; $J qwen2.5-coder-1.5b qwen2.5-coder-1.5b diff_only pairwise 0 $B 0; $J qwen2.5-coder-1.5b qwen2.5-coder-1.5b ctx_retrieved_2000 pairwise 0 $B 0; $J qwen2.5-coder-1.5b qwen2.5-coder-1.5b ctx_retrieved_6000 pairwise 0 $B 0; $J qwen2.5-coder-1.5b qwen2.5-coder-1.5b ctx_file_6000 pairwise 0 $B 0; $J qwen2.5-coder-1.5b qwen2.5-coder-1.5b pointwise pointwise 0 $B 0"
  "$J qwen2.5-coder-3b qwen2.5-coder-3b cjb_control pairwise 0 $B 0; $J qwen2.5-coder-3b qwen2.5-coder-3b diff_only pairwise 0 $B 0"
  "$J qwen3-1.7b qwen3-1.7b cjb_control pairwise 0 $B 0; $J qwen3-1.7b qwen3-1.7b diff_only pairwise 0 $B 0; $J qwen3-1.7b qwen3-1.7b ctx_retrieved_6000 pairwise 0 $B 0; $J qwen3-1.7b qwen3-1.7b-think think_cjb_control pairwise 512 $B 0; $J qwen3-1.7b qwen3-1.7b-think think_diff_only pairwise 512 $B 0"
  "$J qwen3-4b qwen3-4b cjb_control pairwise 0 $B 0; $J qwen3-4b qwen3-4b diff_only pairwise 0 $B 0"
  "$J llama-3.2-3b llama-3.2-3b cjb_control pairwise 0 $B 0; $J llama-3.2-3b llama-3.2-3b diff_only pairwise 0 $B 0; $J gemma-3-4b gemma-3-4b cjb_control pairwise 0 $B 0; $J gemma-3-4b gemma-3-4b diff_only pairwise 0 $B 0"
)
for i in $(seq 0 $((N - 1))); do
  job=${JOBS[$((i % ${#JOBS[@]}))]}
  on "$i" "nohup bash -c '$job; echo ALL JUDGING DONE' > /tmp/judge.log 2>&1 < /dev/null &"
done
log "judging started"
wait_for "ALL JUDGING DONE" /tmp/judge.log

# ---- 4. collect verdicts, analyse, build paper + slides -------------------------------
for i in $(seq 0 $((N - 1))); do
  rsync -az --include='*__*.jsonl' --exclude='*' "${W[$i]}:nlp-project-/results/raw/" results/raw/
done
$PY scripts/normalise_ids.py results/raw/*__*.jsonl
$PY -m repojudgebench.analysis --raw results/raw --meta data/items/meta.jsonl --build $BUILDS --out results \
  --models qwen2.5-coder-1.5b qwen2.5-coder-3b qwen3-1.7b qwen3-4b llama-3.2-3b gemma-3-4b qwen3-1.7b-think
$PY scripts/make_report.py results/summary.json paper/generated
(cd paper && latexmk -pdf -interaction=nonstopmode main.tex > /dev/null || true)
(cd slides && latexmk -pdf -interaction=nonstopmode slides.tex > /dev/null || true)
tar czf "$HOME/rjb-results.tgz" results data/items data/build_shards paper/main.pdf slides/slides.pdf
log "EXPERIMENT DONE -> $HOME/rjb-results.tgz"
