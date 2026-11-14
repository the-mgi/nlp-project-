#!/usr/bin/env bash
# Helper used to spread the expensive stages over several identical machines.
#   scripts/shard_worker.sh setup
#   scripts/shard_worker.sh build <start> <stop> <shard> <num_shards> <minutes> <name>
#   scripts/shard_worker.sh judge <judge-name> <max-minutes>
#   scripts/shard_worker.sh judge-cond <judge> <name> <condition> <mode> <think_tokens> <max_minutes> <limit>
set -eu
WORK=${WORK:-/opt/work}
PY=$WORK/venv/bin/python
cmd=$1; shift
case "$cmd" in
  setup)
    mkdir -p "$WORK"
    python3 -m venv "$WORK/venv"
    CMAKE_ARGS='-DGGML_NATIVE=ON' "$WORK/venv/bin/pip" install -q llama-cpp-python==0.3.36 \
      numpy pandas pyarrow scipy statsmodels matplotlib unidiff jinja2 ruff bandit
    "$PY" scripts/fetch_sources.py "$WORK"
    if ! docker info >/dev/null 2>&1; then
      (nohup dockerd > "$WORK/dockerd.log" 2>&1 &)
      for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
    fi
    docker info >/dev/null && echo "SETUP OK"
    ;;
  build)
    start=$1; stop=$2; shard=$3; n=$4; minutes=$5; name=$6
    "$PY" -m repojudgebench.build_dataset --swelive "$WORK/data/swelive" --rebench "$WORK/data/rebench" \
      --out "data/build_shards/$name" --workers 3 --start "$start" --stop "$stop" \
      --shard "$shard" --num-shards "$n" --deadline-min "$minutes"
    echo "BUILD DONE"
    ;;
  judge)
    name=$1; minutes=$2
    mkdir -p "$WORK/models"
    f=$("$PY" -m repojudgebench.models "$name" file)
    [ -f "$WORK/models/$f" ] || curl -sSL --retry 4 -o "$WORK/models/$f" "$("$PY" -m repojudgebench.models "$name")"
    for cond in cjb_control diff_only; do
      "$PY" -m repojudgebench.judge --model "$WORK/models/$f" --name "$name" \
        --items "data/items/$cond.jsonl" --condition "$cond" \
        --out "results/raw/${name}__${cond}.jsonl" --max-minutes "$minutes"
    done
    echo "JUDGE DONE"
    ;;
  judge-cond)
    # judge-cond <judge> <name-in-results> <condition> <mode> <think_tokens> <max_minutes> <limit>
    judge=$1; name=$2; cond=$3; mode=$4; think=$5; minutes=$6; limit=$7
    items="data/items/$cond.jsonl"
    [ "$cond" = "pointwise" ] && items="data/items/diff_only.jsonl"
    case "$cond" in think_*) items="data/items/${cond#think_}.jsonl";; esac
    mkdir -p "$WORK/models"
    f=$("$PY" -m repojudgebench.models "$judge" file)
    [ -f "$WORK/models/$f" ] || curl -sSL --retry 4 -o "$WORK/models/$f" "$("$PY" -m repojudgebench.models "$judge")"
    "$PY" -m repojudgebench.judge --model "$WORK/models/$f" --name "$name" --items "$items" \
      --condition "${cond#think_}" --mode "$mode" --think-tokens "$think" \
      --out "results/raw/${name}__${cond}.jsonl" --max-minutes "$minutes" --limit "$limit"
    echo "JUDGE-COND DONE $name $cond"
    ;;
esac
