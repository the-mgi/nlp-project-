"""Stage 6: analysis of judge verdicts (objectives O2-O6) and dataset statistics.

All accuracies are computed per *pair*: a pair's score is the mean of its two
presentation orders (gold shown as A, gold shown as B), which is the protocol
of CodeJudgeBench.  95% confidence intervals are percentile bootstrap intervals
over pairs (B = 2000 resamples, fixed seed).

Outputs ``results/summary.json``, LaTeX tables in ``results/tables`` and figures
in ``results/figures``.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

B = 2000
RNG_SEED = 12345
CLASS_ORDER = ["n_plus_one", "race_condition", "authorization_regression",
               "unsafe_migration", "resource_leak", "silent_error_swallowing"]
CLASS_SHORT = {"n_plus_one": "N+1 query", "race_condition": "Race / concurrency",
               "authorization_regression": "Authorisation", "unsafe_migration": "Unsafe migration",
               "resource_leak": "Resource leak", "silent_error_swallowing": "Error swallowing"}


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.open():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_verdicts(raw_dir: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(raw_dir.glob("*__*.jsonl")):
        rows += load_jsonl(f)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if "skipped" in df:
        df = df[df["skipped"].isna()]
    return df


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------

def boot_ci(values: np.ndarray, stat=np.mean, b: int = B, seed: int = RNG_SEED) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return (math.nan, math.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(b, len(values)))
    stats = stat(values[idx], axis=1) if stat is np.mean else np.array([stat(values[i]) for i in idx])
    return (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


def cluster_boot_ci(values: np.ndarray, clusters: np.ndarray, b: int = B,
                    seed: int = RNG_SEED) -> tuple[float, float]:
    """Percentile bootstrap that resamples *clusters* (tasks) with replacement, so
    that several pairs built from the same pull request are not treated as
    independent."""
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return (math.nan, math.nan)
    codes, uniq = pd.factorize(pd.Series(clusters))
    k = len(uniq)
    sums = np.bincount(codes, weights=values, minlength=k)
    cnts = np.bincount(codes, minlength=k).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, k, size=(b, k))
    stats = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


def _boot_means(values: np.ndarray, clusters: np.ndarray, seed_offset: int = 0) -> np.ndarray:
    """Bootstrap distribution (B draws) of the mean, resampling clusters."""
    codes, uniq = pd.factorize(pd.Series(clusters))
    k = len(uniq)
    sums = np.bincount(codes, weights=np.asarray(values, float), minlength=k)
    cnts = np.bincount(codes, minlength=k).astype(float)
    idx = np.random.default_rng(RNG_SEED + seed_offset).integers(0, k, size=(B, k))
    return sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)


def _ci(values, pt: pd.DataFrame | None = None):
    if pt is not None and "cluster" in pt:
        return cluster_boot_ci(values, pt["cluster"].to_numpy())
    return boot_ci(values)


def pair_table(v: pd.DataFrame) -> pd.DataFrame:
    """One row per (model, condition, item) with both orders."""
    pw = v[v["mode"] == "pairwise"]
    piv = pw.pivot_table(index=["model", "condition", "item_id"], columns="order",
                         values=["correct", "p_a"], aggfunc="first")
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    piv = piv.dropna(subset=["correct_AB", "correct_BA"]).reset_index()
    piv["acc"] = (piv["correct_AB"] + piv["correct_BA"]) / 2
    piv["both_correct"] = (piv["correct_AB"] * piv["correct_BA"]).astype(int)
    # same *position* chosen in both orders -> verdict driven by position, not content
    piv["position_flip"] = (piv["correct_AB"] != piv["correct_BA"]).astype(int)
    # p(gold) in each order
    piv["pgold_AB"] = piv["p_a_AB"]
    piv["pgold_BA"] = 1 - piv["p_a_BA"]
    # expected agreement of two independent samples at T=1 for the verdict token
    piv["self_consistency"] = 0.5 * ((piv["p_a_AB"] ** 2 + (1 - piv["p_a_AB"]) ** 2)
                                     + (piv["p_a_BA"] ** 2 + (1 - piv["p_a_BA"]) ** 2))
    piv["p_first"] = 0.5 * (piv["p_a_AB"] + piv["p_a_BA"])  # mean prob. of choosing slot A
    # balanced position calibration (Wang et al.): average the probability given to the
    # gold patch over both orders, which cancels a constant preference for one slot
    pg = 0.5 * (piv["pgold_AB"] + piv["pgold_BA"])
    piv["acc_calibrated"] = np.where(pg > 0.5, 1.0, np.where(pg < 0.5, 0.0, 0.5))
    piv["pgold_mean"] = pg
    # cluster = source task (pairs from one pull request share the gold patch)
    piv["cluster"] = piv["item_id"].map(lambda x: x if x.startswith("cjb::") else x.split("::")[0])
    return piv


def summarise(pt: pd.DataFrame) -> dict:
    acc = pt["acc"].to_numpy()
    lo, hi = _ci(acc, pt)
    ab, ba = pt["correct_AB"].to_numpy(), pt["correct_BA"].to_numpy()
    gap = ab - ba
    glo, ghi = _ci(gap, pt)
    sc = pt["self_consistency"].to_numpy()
    cal = pt["acc_calibrated"].to_numpy()
    return {"n": int(len(pt)), "acc": float(acc.mean()), "ci": [lo, hi],
            "acc_calibrated": float(cal.mean()), "acc_calibrated_ci": list(_ci(cal, pt)),
            "acc_gold_first": float(ab.mean()), "acc_gold_second": float(ba.mean()),
            "position_gap": float(gap.mean()), "position_gap_ci": [glo, ghi],
            "flip_rate": float(pt["position_flip"].mean()),
            "both_correct": float(pt["both_correct"].mean()),
            "p_choose_A": float(pt["p_first"].mean()),
            "self_consistency": float(sc.mean()),
            "self_consistency_ci": list(_ci(sc, pt)),
            "n_clusters": int(pt["cluster"].nunique()) if "cluster" in pt else int(len(pt))}


def paired_diff(a: pd.Series, b: pd.Series) -> dict:
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    d = (j["a"] - j["b"]).to_numpy()
    lo, hi = cluster_boot_ci(d, np.array([str(i).split("::")[0] for i in j.index]))
    return {"n": int(len(d)), "diff": float(d.mean()) if len(d) else math.nan, "ci": [lo, hi]}


def logistic_scaling(pt: pd.DataFrame, meta: pd.DataFrame) -> dict:
    """O3: P(correct) ~ log2(changed lines) + files + hunks, per presentation (both orders)."""
    import statsmodels.api as sm

    d = pt.merge(meta[["item_id", "gold_changed_lines", "gold_files", "gold_hunks"]], on="item_id")
    long = pd.concat([d.assign(correct=d["correct_AB"]), d.assign(correct=d["correct_BA"])])
    X = pd.DataFrame({"log2_lines": np.log2(long["gold_changed_lines"].clip(lower=1)),
                      "files": long["gold_files"], "hunks": long["gold_hunks"]})
    X = sm.add_constant(X)
    y = long["correct"].astype(int)
    out = {"n_obs": int(len(y)), "n_pairs": int(len(d))}
    if y.nunique() < 2 or len(y) < 20:
        out["error"] = "degenerate"
        return out
    try:
        groups = pd.factorize(long["item_id"])[0]
        m = sm.Logit(y, X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": groups})
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
        return out
    ci = m.conf_int()
    out["coef"] = {k: {"b": float(m.params[k]), "ci": [float(ci.loc[k, 0]), float(ci.loc[k, 1])],
                       "p": float(m.pvalues[k])} for k in m.params.index}
    # predicted accuracy along diff size, files/hunks at their medians
    grid = np.array([4, 8, 16, 32, 64, 128, 256, 512])
    med_f, med_h = float(np.median(long["gold_files"])), float(np.median(long["gold_hunks"]))
    Xg = sm.add_constant(pd.DataFrame({"log2_lines": np.log2(grid), "files": med_f, "hunks": med_h}),
                         has_constant="add")
    pred = m.get_prediction(Xg)
    sf = pred.summary_frame(alpha=0.05)
    out["curve"] = [{"lines": int(g), "p": float(r["predicted"]), "lo": float(r["ci_lower"]),
                     "hi": float(r["ci_upper"])} for g, (_, r) in zip(grid, sf.iterrows())]
    chance = [c["lines"] for c in out["curve"] if c["lo"] <= 0.5]
    out["chance_from_lines"] = chance[0] if chance else None
    out["pseudo_r2"] = float(m.prsquared)
    return out


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "font.family": "serif", "axes.spines.top": False,
                         "axes.spines.right": False})
    return plt


def fig_regimes(summary: dict, models: list[str], path: Path):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    x = np.arange(len(models))
    w = 0.38
    for k, (cond, lab, col) in enumerate([("cjb_control", "CodeJudgeBench (single-file)", "#4C72B0"),
                                          ("diff_only", "RepoJudgeBench (repository-level)", "#DD8452")]):
        vals = [summary["by_model"].get(m, {}).get(cond, {}) for m in models]
        acc = [s.get("acc", np.nan) for s in vals]
        err = [[s["acc"] - s["ci"][0] if s else 0 for s in vals], [s["ci"][1] - s["acc"] if s else 0 for s in vals]]
        ax.bar(x + (k - 0.5) * w, acc, w, yerr=err, capsize=2, label=lab, color=col, error_kw={"lw": 0.7})
    ax.axhline(0.5, ls="--", lw=0.8, color="grey")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=25, ha="right")
    ax.set_ylabel("Pairwise accuracy")
    ax.set_ylim(0.3, 1.0)
    ax.legend(frameon=False, fontsize=6.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_scaling(pt_all: pd.DataFrame, meta: pd.DataFrame, models: list[str], path: Path):
    plt = _plt()
    d = pt_all.merge(meta[["item_id", "gold_changed_lines", "gold_files"]], on="item_id")
    edges = [0, 10, 25, 50, 100, 10**9]
    labels = ["1-10", "11-25", "26-50", "51-100", ">100"]
    d["bin"] = pd.cut(d["gold_changed_lines"], edges, labels=labels, right=True)
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    for m in models:
        s = d[d["model"] == m].groupby("bin", observed=False)["acc"].mean()
        ax.plot(range(len(labels)), s.reindex(labels).to_numpy(), marker="o", ms=3, lw=1, label=m)
    pooled = d.groupby("bin", observed=False)["acc"]
    mean = pooled.mean().reindex(labels).to_numpy()
    ax.plot(range(len(labels)), mean, color="black", lw=2, label="mean of judges")
    ax.axhline(0.5, ls="--", lw=0.8, color="grey")
    counts = d[d["model"] == models[0]].groupby("bin", observed=False).size().reindex(labels)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([f"{l}\n(n={int(c) if not pd.isna(c) else 0})" for l, c in zip(labels, counts)], fontsize=6.5)
    ax.set_xlabel("Changed lines in the gold patch")
    ax.set_ylabel("Pairwise accuracy")
    ax.legend(frameon=False, fontsize=5.5, ncol=2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_classes(summary: dict, models: list[str], path: Path):
    plt = _plt()
    classes = [c for c in CLASS_ORDER if any(c in summary["by_class"].get(m, {}) for m in models)]
    M = np.full((len(models), len(classes)), np.nan)
    N = np.zeros(len(classes), dtype=int)
    for i, m in enumerate(models):
        for j, c in enumerate(classes):
            s = summary["by_class"].get(m, {}).get(c)
            if s:
                M[i, j] = s["acc"]
                N[j] = s["n"]
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    im = ax.imshow(M, cmap="RdYlGn", vmin=0.2, vmax=0.8, aspect="auto")
    for i in range(len(models)):
        for j in range(len(classes)):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=6)
    ax.set_xticks(range(len(classes)))
    ax.set_xticklabels([f"{CLASS_SHORT[c]}\n(n={N[j]})" for j, c in enumerate(classes)], fontsize=6, rotation=20)
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models, fontsize=6.5)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="results/raw")
    ap.add_argument("--meta", default="data/items/meta.jsonl")
    ap.add_argument("--build", nargs="+", default=["data/build/instances.jsonl"])
    ap.add_argument("--out", default="results")
    ap.add_argument("--models", nargs="*", default=None, help="judge order for tables/figures")
    args = ap.parse_args()
    out = Path(args.out)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    (out / "tables").mkdir(parents=True, exist_ok=True)

    meta = pd.DataFrame(load_jsonl(Path(args.meta)))
    v = load_verdicts(Path(args.raw))
    summary: dict = {"dataset": dataset_stats([Path(b) for b in args.build], meta)}
    pt = pair_table(v) if not v.empty else pd.DataFrame()
    models = args.models or sorted(pt["model"].unique()) if not pt.empty else []
    models = [m for m in models if m in set(pt["model"])] if not pt.empty else []

    summary["by_model"] = defaultdict(dict)
    summary["by_class"] = defaultdict(dict)
    summary["scaling"] = {}
    for (m, c), g in pt.groupby(["model", "condition"]):
        summary["by_model"][m][c] = summarise(g)
    main_pt = pt[pt["condition"] == "diff_only"].merge(meta, on="item_id", how="left") if not pt.empty else pt
    for m, g in main_pt.groupby("model") if not main_pt.empty else []:
        for cls, gc in g.groupby("defect_class"):
            s = summarise(gc)
            summary["by_class"][m][cls] = s
        for origin, go in g.groupby("site_origin"):
            summary["by_model"][m][f"diff_only[origin={origin}]"] = summarise(go)
        summary["scaling"][m] = logistic_scaling(g[pt.columns], meta)
    if not main_pt.empty:
        summary["scaling"]["pooled"] = logistic_scaling(main_pt[pt.columns], meta)
        # pooled per-class accuracy (mean over judges)
        summary["by_class"]["all_judges"] = {
            cls: summarise(gc) for cls, gc in main_pt.groupby("defect_class")}
    # length bias: does the (position-calibrated) preference follow the longer diff?
    summary["length_bias"] = {}
    if not main_pt.empty:
        lb = main_pt.copy()
        dl = lb["variant_changed_lines"] - lb["gold_changed_lines"]
        lb["len_rel"] = np.where(dl > 0, "variant_longer", np.where(dl < 0, "variant_shorter", "same_length"))
        lb["prefers_longer"] = np.where(dl > 0, 1 - lb["acc_calibrated"],
                                        np.where(dl < 0, lb["acc_calibrated"], np.nan))
        for m, g in list(lb.groupby("model")) + [("all_judges", lb)]:
            out_m = {}
            for rel, gr in g.groupby("len_rel"):
                out_m[rel] = {"n": int(len(gr)), "acc": float(gr["acc"].mean()),
                              "acc_calibrated": float(gr["acc_calibrated"].mean()),
                              "acc_calibrated_ci": list(_ci(gr["acc_calibrated"].to_numpy(), gr))}
            pl = g["prefers_longer"].dropna()
            if len(pl):
                gg = g.loc[pl.index]
                out_m["prefers_longer"] = {"n": int(len(pl)), "rate": float(pl.mean()),
                                           "ci": list(_ci(pl.to_numpy(), gg))}
            summary["length_bias"][m] = out_m
        summary["length_relation_counts"] = meta[meta.get("judged", True) == True].assign(
            rel=np.sign(meta["variant_changed_lines"] - meta["gold_changed_lines"])
        )["rel"].value_counts().rename(index={1: "variant_longer", -1: "variant_shorter", 0: "same_length"}).to_dict() \
            if "judged" in meta else {}
    # regime gap (O2) and context gain (O6) as paired / unpaired differences
    summary["regime_gap"] = {}
    summary["context_gain"] = defaultdict(dict)
    for m in models:
        bm = summary["by_model"][m]
        if "cjb_control" in bm and "diff_only" in bm:
            ga = pt[(pt.model == m) & (pt.condition == "cjb_control")]
            gb = pt[(pt.model == m) & (pt.condition == "diff_only")]
            a, b = ga["acc"].to_numpy(), gb["acc"].to_numpy()
            diffs = _boot_means(a, ga["cluster"].to_numpy(), 1) - _boot_means(b, gb["cluster"].to_numpy(), 2)
            summary["regime_gap"][m] = {"cjb": float(a.mean()), "repo": float(b.mean()),
                                        "gap": float(a.mean() - b.mean()),
                                        "ci": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]}
        base = pt[(pt.model == m) & (pt.condition == "diff_only")].set_index("item_id")["acc"]
        for cond in sorted(set(pt[pt.model == m]["condition"])):
            if cond.startswith("ctx_") or cond.startswith("think"):
                other = pt[(pt.model == m) & (pt.condition == cond)].set_index("item_id")["acc"]
                summary["context_gain"][m][cond] = paired_diff(other, base)
                # per class
                mm = meta.set_index("item_id")["defect_class"]
                per = {}
                for cls in CLASS_ORDER:
                    ids = mm[mm == cls].index
                    if len(set(ids) & set(other.index)):
                        per[cls] = paired_diff(other[other.index.isin(ids)], base[base.index.isin(ids)])
                summary["context_gain"][m][cond + "::by_class"] = per
    # pointwise (secondary condition)
    summary["pointwise"] = {}
    if not v.empty and (v["mode"] == "pointwise").any():
        pw = v[v["mode"] == "pointwise"].pivot_table(index=["model", "item_id"], columns="order",
                                                     values="expected", aggfunc="first").dropna().reset_index()
        for m, g in pw.groupby("model"):
            sc = np.where(g["pos"] > g["neg"], 1.0, np.where(g["pos"] < g["neg"], 0.0, 0.5))
            # discrete greedy ratings for the tie analysis
            summary["pointwise"][m] = {"n": int(len(g)), "acc": float(sc.mean()), "ci": list(boot_ci(sc)),
                                       "mean_pos": float(g["pos"].mean()), "mean_neg": float(g["neg"].mean())}
        vv = v[v["mode"] == "pointwise"].copy()
        vv["greedy"] = vv["p_rating"].map(lambda p: int(np.argmax(p)) + 1)
        gp = vv.pivot_table(index=["model", "item_id"], columns="order", values="greedy",
                            aggfunc="first").dropna().reset_index()
        for m, g in gp.groupby("model"):
            sc = np.where(g["pos"] > g["neg"], 1.0, np.where(g["pos"] < g["neg"], 0.0, 0.5))
            summary["pointwise"][m]["greedy_acc"] = float(sc.mean())
            summary["pointwise"][m]["greedy_tie_rate"] = float((g["pos"] == g["neg"]).mean())
    # trivial length heuristic: pick the patch with fewer changed lines (ties = coin flip)
    if "judged" in meta and len(meta):
        jm = meta[meta["judged"] == True].copy()
        dl = jm["variant_changed_lines"] - jm["gold_changed_lines"]
        x = np.where(dl > 0, 1.0, np.where(dl < 0, 0.0, 0.5))
        summary["length_heuristic"] = {"n": int(len(jm)), "acc": float(x.mean()),
                                       "ci": list(cluster_boot_ci(x, jm["instance_id"].to_numpy()))}
    # static analysis baseline
    st = pd.DataFrame(load_jsonl(Path(args.raw) / "static_baseline.jsonl"))
    if not st.empty:
        sa = st[st["available"]]
        summary["static"] = {"n": int(len(sa)), "n_total": int(len(st))}
        for rs in ("relevant", "all"):
            x = sa[f"{rs}_pairwise"].to_numpy(dtype=float)
            summary["static"][rs] = {"acc": float(x.mean()), "ci": list(boot_ci(x)),
                                     "flag_variant_rate": float(sa[f"{rs}_flags_variant"].mean()),
                                     "flag_gold_rate": float(sa[f"{rs}_flags_gold"].mean())}
            sam = sa.merge(meta[["item_id", "defect_class"]], on="item_id")
            summary["static"][rs]["by_class"] = {
                c: {"n": int(len(g)), "acc": float(g[f"{rs}_pairwise"].mean()),
                    "flag_variant_rate": float(g[f"{rs}_flags_variant"].mean())}
                for c, g in sam.groupby("defect_class")}
    # figures
    if models:
        fig_regimes(summary, models, out / "figures" / "regimes.pdf")
        if not main_pt.empty:
            fig_scaling(pt[pt.condition == "diff_only"], meta, models, out / "figures" / "scaling.pdf")
            fig_classes(summary, models, out / "figures" / "classes.pdf")
    summary["models"] = models
    with open(out / "summary.json", "w") as fo:
        json.dump(summary, fo, indent=1, default=float)
    print(json.dumps({m: {c: (round(s["acc"], 3), s["n"]) for c, s in summary["by_model"][m].items()}
                      for m in models}, indent=1))


def dataset_stats(builds: list[Path], meta: pd.DataFrame) -> dict:
    from .make_items import dedupe
    recs = dedupe([r for b in builds for r in load_jsonl(b)])
    st = Counter(r.get("status") for r in recs)
    cand = Counter()
    caught = Counter()
    admitted = Counter()
    for r in recs:
        for v in r.get("variants", []):
            cand[v["defect_class"]] += 1
            admitted[v["defect_class"]] += 1
        for v in r.get("rejected", []):
            cand[v["defect_class"]] += 1
            caught[v["defect_class"]] += 1
    out = {"instances_processed": len(recs), "status": dict(st),
           "candidates_tested": dict(cand), "caught_by_tests": dict(caught), "admitted": dict(admitted)}
    if not meta.empty:
        out["pairs"] = int(len(meta))
        out["pairs_no_leak"] = int((~meta["solution_leak"]).sum())
        out["repos"] = int(meta["repo"].nunique())
        out["instances"] = int(meta["instance_id"].nunique())
        out["by_source"] = meta.groupby("source")["item_id"].count().to_dict()
        out["by_class"] = meta["defect_class"].value_counts().to_dict()
        if "judged" in meta:
            out["pairs_judged"] = int(meta["judged"].sum())
            out["by_class_judged"] = meta[meta["judged"]]["defect_class"].value_counts().to_dict()
            if "prompt_tokens" in meta:
                pt_ = meta[meta["judged"]]["prompt_tokens"]
                out["judged_prompt_tokens"] = {"median": float(pt_.median()), "max": float(pt_.max()),
                                               "min": float(pt_.min())}
        out["by_operator"] = meta.groupby(["defect_class", "operator"]).size().rename("n").reset_index().to_dict("records")
        out["by_origin"] = meta["site_origin"].value_counts().to_dict()
        for k in ("gold_changed_lines", "gold_files", "gold_hunks"):
            q = meta[k].describe(percentiles=[0.25, 0.5, 0.75]).to_dict()
            out[k] = {kk: float(vv) for kk, vv in q.items()}
        out["created_at_min"] = str(meta["created_at"].min())
        out["created_at_max"] = str(meta["created_at"].max())
    return out


if __name__ == "__main__":
    main()
