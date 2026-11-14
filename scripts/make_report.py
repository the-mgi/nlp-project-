"""Render results/summary.json into LaTeX macros and tables for the paper.

    python scripts/make_report.py results/summary.json paper/generated
"""
import json
import sys
from pathlib import Path

CLASS_ORDER = ["n_plus_one", "race_condition", "authorization_regression",
               "unsafe_migration", "resource_leak", "silent_error_swallowing"]
CLASS_SHORT = {"n_plus_one": "N+1 query", "race_condition": "Race / concurrency",
               "authorization_regression": "Authorisation", "unsafe_migration": "Unsafe migration",
               "resource_leak": "Resource leak", "silent_error_swallowing": "Error swallowing"}
NICE = {"qwen2.5-coder-1.5b": "Qwen2.5-Coder-1.5B", "qwen2.5-coder-3b": "Qwen2.5-Coder-3B",
        "qwen3-1.7b": "Qwen3-1.7B", "qwen3-4b": "Qwen3-4B", "llama-3.2-3b": "Llama-3.2-3B",
        "gemma-3-4b": "Gemma-3-4B", "qwen3-1.7b-think": "Qwen3-1.7B-think"}
COND = {"ctx_retrieved_2000": "+ retrieved, 2k chars", "ctx_retrieved_6000": "+ retrieved, 6k chars",
        "ctx_file_6000": "+ file, 6k chars", "think": "thinking"}


def pct(x, d=1):
    return "--" if x is None or x != x else f"{100 * x:.{d}f}"


def ci(c):
    return f"[{pct(c[0], 0)}, {pct(c[1], 0)}]"


def main():
    S = json.load(open(sys.argv[1]))
    extra = Path(sys.argv[1]).parent / "extra_macros.json"
    if extra.exists():
        S["extra_macros"] = json.load(open(extra))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    D = S["dataset"]
    models = S["models"]
    mac = {}
    mac["NPairs"] = str(D.get("pairs", 0))
    mac["NInstances"] = str(D.get("instances", 0))
    mac["NRepos"] = str(D.get("repos", 0))
    cand = sum(D["candidates_tested"].values())
    caught = sum(D["caught_by_tests"].values())
    mac["NCandidates"] = str(cand)
    mac["NCaught"] = str(caught)
    mac["TestCatchRate"] = f"{pct(caught / cand if cand else float('nan'))}\\%"
    mac["NProcessed"] = str(D["instances_processed"])
    mac["NJudges"] = str(len([m for m in models if not m.endswith("-think")]))
    for k, v in S.get("extra_macros", {}).items():
        mac[k] = v
    with open(out / "numbers.tex", "w") as fo:
        for k, v in mac.items():
            fo.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")

    # ---- dataset table ----------------------------------------------------
    rows = []
    for c in CLASS_ORDER:
        t = D["candidates_tested"].get(c, 0)
        k = D["caught_by_tests"].get(c, 0)
        a = D["admitted"].get(c, 0)
        rows.append(f"{CLASS_SHORT[c]} & {t} & {k} & {pct(k / t) if t else '--'} & {a} \\\\")
    tot = f"\\midrule\nTotal & {cand} & {caught} & {pct(caught / cand) if cand else '--'} & {sum(D['admitted'].values())} \\\\"
    (out / "tab_dataset.tex").write_text(
        "\\begin{table}[t]\n\\caption{Defect injection and execution-based admission. "
        "\\emph{Tested}: candidates run against the PR's tests; \\emph{caught}: candidates that broke "
        "at least one gold-passing test; \\emph{admitted}: pairs in \\RJB{}.}\n\\label{tab:dataset}\n"
        "\\centering\\footnotesize\n\\begin{tabular}{@{}lrrrr@{}}\n\\toprule\n"
        "Class & Tested & Caught & Caught (\\%) & Admitted \\\\\n\\midrule\n" + "\n".join(rows) + "\n" + tot +
        "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")

    # ---- main table -----------------------------------------------------------
    rows = []
    for m in models:
        bm = S["by_model"].get(m, {})
        c, r = bm.get("cjb_control"), bm.get("diff_only")
        if not r and not c:
            continue
        g = S.get("regime_gap", {}).get(m)
        rows.append(" & ".join([
            NICE.get(m, m),
            f"{pct(c['acc'])} {ci(c['ci'])}" if c else "--",
            f"{pct(r['acc'])} {ci(r['ci'])}" if r else "--",
            f"{'+' if g and g['gap'] >= 0 else ''}{pct(g['gap'])}" if g else "--",
            f"{pct(c['acc_calibrated'])}" if c else "--",
            f"{pct(r['acc_calibrated'])} {ci(r['acc_calibrated_ci'])}" if r else "--",
            f"{c['n']}/{r['n']}" if (c and r) else (f"{c['n']}/--" if c else f"--/{r['n']}"),
        ]) + " \\\\")
    (out / "tab_main.tex").write_text(
        "\\begin{table*}[t]\n\\caption{Pairwise accuracy (\\%) with 95\\% bootstrap CIs on the "
        "\\CJB{} control subset (single-file) and on \\RJB{} (repository-level, diff-only); a pair's "
        "accuracy is the mean of its two presentation orders. $\\Delta$ = control $-$ \\RJB{}. "
        "\\emph{Calibrated} = accuracy after balanced position calibration (the probability given to "
        "the gold patch is averaged over both orders before deciding). Random = 50\\%; the execution "
        "oracle scores 0\\% on \\RJB{} by construction.}\n"
        "\\label{tab:main}\n\\centering\\footnotesize\n\\begin{tabular}{@{}lllrrlr@{}}\n\\toprule\n"
        " & \\multicolumn{2}{c}{Accuracy} & & \\multicolumn{2}{c}{Calibrated accuracy} & \\\\\n"
        "\\cmidrule(lr){2-3}\\cmidrule(lr){5-6}\n"
        "Judge & \\CJB{} control & \\RJB{} & $\\Delta$ & \\CJB{} & \\RJB{} & $n$ (pairs) \\\\\n\\midrule\n"
        + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table*}\n")

    # ---- robustness table (O5) -------------------------------------------------
    rows = []
    for m in models:
        bm = S["by_model"].get(m, {})
        c, r = bm.get("cjb_control"), bm.get("diff_only")
        if not r and not c:
            continue
        f = lambda d, k: pct(d[k]) if d else "--"
        rows.append(" & ".join([NICE.get(m, m), f(c, "position_gap"), f(r, "position_gap"),
                                f(c, "flip_rate"), f(r, "flip_rate"), f(c, "p_choose_A"), f(r, "p_choose_A"),
                                f(c, "self_consistency"), f(r, "self_consistency")]) + " \\\\")
    (out / "tab_robust.tex").write_text(
        "\\begin{table*}[t]\n\\caption{Robustness (O5), control (C) vs.\\ \\RJB{} (R), in \\%. "
        "\\emph{Pos.\\ gap}: accuracy with the gold patch shown first minus shown second. \\emph{Flip}: "
        "share of pairs whose verdict selects the same slot in both orders. $P(A)$: mean probability of "
        "choosing the first slot. \\emph{SC}: expected agreement of two independent $T{=}1$ samples of "
        "the verdict.}\n\\label{tab:robust}\n\\centering\\footnotesize\n"
        "\\begin{tabular}{@{}lrrrrrrrr@{}}\n\\toprule\n"
        " & \\multicolumn{2}{c}{Pos.\\ gap} & \\multicolumn{2}{c}{Flip} & \\multicolumn{2}{c}{$P(A)$} & "
        "\\multicolumn{2}{c}{SC} \\\\\n\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-9}\n"
        "Judge & C & R & C & R & C & R & C & R \\\\\n\\midrule\n" + "\n".join(rows) +
        "\n\\bottomrule\n\\end{tabular}\n\\end{table*}\n")

    # ---- per-class table ---------------------------------------------------
    allj = S["by_class"].get("all_judges", {})
    cls_present = [c for c in CLASS_ORDER if c in allj]
    head = " & ".join(["Judge"] + [CLASS_SHORT[c] for c in cls_present])
    rows = []
    for m in models:
        bc = S["by_class"].get(m, {})
        if not bc:
            continue
        rows.append(" & ".join([NICE.get(m, m)] + [pct(bc[c]["acc"]) if c in bc else "--" for c in cls_present]) + " \\\\")
    rows.append("\\midrule")
    rows.append(" & ".join(["All judges"] + [f"{pct(allj[c]['acc'])} {ci(allj[c]['ci'])}" for c in cls_present]) + " \\\\")
    rows.append(" & ".join(["Pairs ($n$)"] + [str(S['dataset']['by_class_judged'].get(c, 0)) if 'by_class_judged' in S['dataset'] else '' for c in cls_present]) + " \\\\")
    st = S.get("static", {})
    if st:
        for rs, lab in (("relevant", "Static (relevant)"), ("all", "Static (all rules)")):
            bc = st[rs]["by_class"]
            rows.append(" & ".join([lab] + [pct(bc[c]["acc"]) if c in bc else "--" for c in cls_present]) + " \\\\")
    colspec = "l" + "r" * len(cls_present)
    (out / "tab_classes.tex").write_text(
        "\\begin{table*}[t]\n\\caption{Accuracy (\\%) by defect class on \\RJB{} (diff-only). "
        "The pooled row averages pairs over all judges and reports a bootstrap CI.}\n"
        "\\label{tab:classes}\n\\centering\\footnotesize\n\\begin{tabular}{@{}" + colspec + "@{}}\n\\toprule\n"
        + head + " \\\\\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table*}\n")

    # ---- scaling table --------------------------------------------------------
    sc = S.get("scaling", {}).get("pooled", {})
    if "coef" in sc:
        names = {"const": "Intercept", "log2_lines": "$\\log_2$ changed lines", "files": "Files touched",
                 "hunks": "Hunks"}
        rows = [f"{names[k]} & {v['b']:+.3f} & [{v['ci'][0]:+.3f}, {v['ci'][1]:+.3f}] & {v['p']:.3f} \\\\"
                for k, v in sc["coef"].items()]
        (out / "tab_scaling.tex").write_text(
            "\\begin{table}[t]\n\\caption{Logistic regression of per-presentation correctness on diff "
            f"size (pooled over judges; {sc['n_obs']} presentations of {sc['n_pairs']} judge--pair "
            "combinations; SEs clustered by pair).}\n\\label{tab:scaling}\n\\centering\\footnotesize\n"
            "\\begin{tabular}{@{}lrrr@{}}\n\\toprule\nPredictor & $\\beta$ & 95\\% CI & $p$ \\\\\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")

    # ---- context / conditions table ------------------------------------------
    rows = []
    for m, conds in S.get("context_gain", {}).items():
        for cond, d in conds.items():
            if "::" in cond:
                continue
            base = S["by_model"][m].get("diff_only", {})
            other = S["by_model"][m].get(cond, {})
            rows.append(f"{NICE.get(m, m)} & {COND.get(cond, cond)} & {pct(other.get('acc'))} & "
                        f"{'+' if d['diff'] >= 0 else ''}{pct(d['diff'])} {ci(d['ci'])} & {d['n']} \\\\")
    if rows:
        (out / "tab_context.tex").write_text(
            "\\begin{table}[t]\n\\caption{Mitigation (O6) and thinking: accuracy (\\%) of each condition "
            "and paired difference to the diff-only prompt on the same pairs.}\n\\label{tab:context}\n"
            "\\centering\\footnotesize\n\\begin{tabular}{@{}llrrr@{}}\n\\toprule\n"
            "Judge & Condition & Acc. & $\\Delta$ vs diff-only & $n$ \\\\\n\\midrule\n" + "\n".join(rows) +
            "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")

    # ---- baselines table -------------------------------------------------------
    rows = ["Random & 50.0 & -- \\\\", "Execution oracle (PR tests) & 0.0 & by construction \\\\"]
    if st:
        for rs, lab in (("relevant", "Static analysis, relevant rules"), ("all", "Static analysis, all rules")):
            rows.append(f"{lab} & {pct(st[rs]['acc'])} & {ci(st[rs]['ci'])}; flags variant {pct(st[rs]['flag_variant_rate'])}\\%, gold {pct(st[rs]['flag_gold_rate'])}\\% \\\\")
    for m, p in S.get("pointwise", {}).items():
        rows.append(f"Point-wise, {NICE.get(m, m)} & {pct(p['acc'])} & {ci(p['ci'])}; greedy ties {pct(p.get('greedy_tie_rate'))}\\% \\\\")
    (out / "tab_baselines.tex").write_text(
        "\\begin{table}[t]\n\\caption{Non-LLM baselines and point-wise judging on \\RJB{} (accuracy, \\%).}\n"
        "\\label{tab:baselines}\n\\centering\\footnotesize\n\\begin{tabular}{@{}lrl@{}}\n\\toprule\n"
        "Method & Acc. & Notes \\\\\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    print("wrote", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main()
