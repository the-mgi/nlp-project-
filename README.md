# RepoJudgeBench

**Does LLM-as-a-Judge reliability survive the move from self-contained functions to
repository-level, test-passing code changes?**

NLP semester research project, FAST-NUCES Islamabad.

**Contributors**
- Muhammad Usama — 25I-8007 — i258007@isb.nu.edu.pk
- Ali Raza — 25I-8043 — i258043@isb.nu.edu.pk
Base paper: Jiang et al., *CodeJudgeBench: Benchmarking LLM-as-a-Judge for Coding Tasks*,
arXiv:2507.10535.

The final paper is in [`paper/main.pdf`](paper/main.pdf) (LaTeX sources in `paper/`), and
the presentation slides are in [`slides/`](slides/).

---

## Main results

| | |
|---|---|
| Benchmark | 203 execution-verified (gold, defective) pairs from 133 real PRs (created 2025-01-01 to 2025-09-02) in 90 Python repositories; 155 judged |
| Tests vs. injected defects | the PRs' own tests catch only 40.5% of candidate defects (resource leaks: 15.4%) |
| Raw pairwise accuracy | 50.0–55.6% on the CodeJudgeBench control, 42.4–51.1% on RepoJudgeBench (6 judges, 1.5–4B) |
| Position bias | flip rates 71–100%; verdicts follow the presentation slot |
| After position calibration | three smallest judges significantly *below* chance on RepoJudgeBench (24.3–31.6%); Qwen3-4B 66.7%, Gemma-3-4B 59.1% |
| Length bias | small judges prefer the longer (usually defective) patch in 77–87% of unequal pairs |
| Diff size | no measurable effect (all logistic coefficients' CIs include 0) |
| Mitigation | retrieved context / thinking: +16 to +22 calibrated points for Qwen3-1.7B, still not above chance |
| Baselines | targeted static analysis 68.4%; shorter-patch heuristic 80.0% (a length artefact of the current benchmark) |

All numbers are generated from `results/summary.json` (see `paper/generated/`).

## What this repository contains

| Path | Content |
|---|---|
| `repojudgebench/mutate.py` | AST-based defect-injection operators for the six defect classes (N+1 query, race condition, authorisation regression, unsafe migration, resource leak, silent error swallowing) |
| `repojudgebench/build_dataset.py` | Execution-verified benchmark construction: applies real post-2025 pull requests inside their published Docker images, injects defects, and **admits a variant only if every test that passes with the gold patch still passes** |
| `repojudgebench/make_items.py` | Builds judge items (diff-only, retrieved-context and file-context conditions), solution-leakage filter, token-length filter |
| `repojudgebench/cjb_control.py` | CodeJudgeBench control subset (single-file regime) |
| `repojudgebench/judge.py` | Local LLM judges (llama.cpp): pairwise forced-verdict scoring, point-wise scoring, bounded thinking mode |
| `repojudgebench/static_baseline.py` | Ruff / Bandit static-analysis baseline |
| `repojudgebench/analysis.py` | Bootstrap CIs, position bias, self-consistency, logistic scaling model, per-class breakdown, context gain, figures |
| `scripts/` | Source download (pinned revisions), distributed worker script, report/table generation, annotation sheet + Cohen's kappa |
| `data/build/`, `data/build_shards/` (shards 1-3) | Raw construction logs: every processed task, every tested candidate, admitted and rejected variants, retrieved context |
| `data/items/` | The benchmark as judge items (`meta.jsonl` holds per-pair metadata) |
| `results/raw/` | Raw verdict logs for every judge, condition and presentation order |
| `results/summary.json`, `results/tables/`, `results/figures/` | Aggregated results used in the paper |
| `tests/` | Unit tests for the mutation operators |

## Pipeline

```
SWE-bench-Live / SWE-rebench tasks created >= 2025-01-01
  -> apply gold patch in the task's Docker image, re-render with `git diff`
  -> AST mutation in the region touched by the gold patch (one operator per class)
  -> run the PR's tests: admit iff every gold-passing test still passes
  -> neutral context from the parent commit (definitions + call sites)
  -> pairwise judging in both orders (CodeJudgeBench prompt), analysis
```

## Reproducing

Requirements: Linux, Python >= 3.10, Docker (for dataset construction), ~40 GB disk.
No GPU is needed; all judges run on CPU through `llama-cpp-python`.

```bash
python -m venv venv && . venv/bin/activate
CMAKE_ARGS='-DGGML_NATIVE=ON' pip install -r requirements.txt

# 1. sources (SWE-bench-Live, SWE-rebench, CodeJudgeBench) at pinned revisions
python scripts/fetch_sources.py /opt/work

# 2. build the benchmark (Docker daemon must be running)
python -m repojudgebench.build_dataset --swelive /opt/work/data/swelive \
    --rebench /opt/work/data/rebench --out data/build --workers 3

# 3. judge items + control subset
python -m repojudgebench.make_items --build data/build/instances.jsonl data/build_shards/*/instances.jsonl \
    --out data/items --tokenizer-gguf /opt/work/models/qwen2.5-coder-1.5b-instruct-q8_0.gguf
python -m repojudgebench.cjb_control --data /opt/work/data/cjb

# 4. judges (GGUF files listed in repojudgebench/models.py)
python -m repojudgebench.judge --model /opt/work/models/qwen2.5-coder-1.5b-instruct-q8_0.gguf \
    --name qwen2.5-coder-1.5b --items data/items/diff_only.jsonl --condition diff_only \
    --out results/raw/qwen2.5-coder-1.5b__diff_only.jsonl
#    (see scripts/shard_worker.sh for every condition that was run)

# 5. baselines, analysis, paper tables
python -m repojudgebench.static_baseline --build data/build/instances.jsonl data/build_shards/*/instances.jsonl
bash scripts/finalize.sh      # analysis -> tables/figures -> paper/main.pdf and slides/slides.pdf
```

Unit tests: `python -m pytest tests`.

## Human validation

`python scripts/make_annotation_sheet.py sheet --n 50` writes a stratified sheet of 50 pairs
(patch order randomised) for two annotators; `python scripts/make_annotation_sheet.py kappa a.csv b.csv`
computes Cohen's kappa. This validation was planned in the proposal but was not carried out
for the submitted results (see the paper's "Deviations from the proposal").

## Licences of the sources

SWE-bench-Live: MIT. SWE-rebench: CC-BY-4.0 (per-repository licences are listed in its
`license_name` field and kept in `data/items/meta.jsonl`). CodeJudgeBench: Apache-2.0.
The benchmark stores only diffs, issue texts and short code snippets of the source repositories.
