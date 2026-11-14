#!/usr/bin/env bash
# Collect outputs that a worker machine pushed to its own branch:
#   scripts/collect_shards.sh <branch> <path-prefix> [<path-prefix> ...]
# e.g. scripts/collect_shards.sh worker-branch data/build_shards/shard0 results/raw/qwen3-4b__
# Copies only the matching files (no history is merged).
set -eu
br=$1; shift
git fetch -q origin "$br"
for prefix in "$@"; do
  git ls-tree -r --name-only "origin/$br" | grep -F "$prefix" | while read -r f; do
    mkdir -p "$(dirname "$f")"
    git show "origin/$br:$f" > "$f"
    echo "  $f ($(wc -l < "$f") lines)"
  done
done
echo "collected from $br"
