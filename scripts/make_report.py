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
    st_ = S.get("static", {})
    if st_:
        mac["StaticRelAcc"] = f"{pct(st_['relevant']['acc'])}\\%"
        mac["StaticRelFlagVar"] = f"{pct(st_['relevant']['flag_variant_rate'])}\\%"
        mac["StaticAllAcc"] = f"{pct(st_['all']['acc'])}\\%"
        mac["NStatic"] = str(st_["n"])
    if S.get("length_heuristic"):
        mac["LengthHeurAcc"] = f"{pct(S['length_heuristic']['acc'])}\\%"
    lb = S.get("length_bias", {}).get("all_judges", {})
    if "prefers_longer" in lb:
        mac["PrefersLonger"] = f"{pct(lb['prefers_longer']['rate'])}\\%"
    rc = S.get("length_relation_counts", {})
    if rc:
        tot = sum(rc.values())
        mac["VarLongerShare"] = f"{pct(rc.get('variant_longer', 0) / tot)}\\%"
    mac["NPairsJudged"] = str(D.get("pairs_judged", ""))
    stt = D.get("status", {})
    mac["NStatusNoSite"] = str(stt.get("no_mutation_site", 0))
    mac["NStatusNotGreen"] = str(stt.get("gold_tests_not_green", 0))
    mac["NStatusCaught"] = str(stt.get("all_caught_by_tests", 0))
    mac["NStatusError"] = str(stt.get("error", 0) + stt.get("timeout", 0) + stt.get("crash", 0))
    mac["NFromLive"] = str(D.get("by_source", {}).get("SWE-bench-Live", 0))
    mac["NFromRebench"] = str(D.get("by_source", {}).get("SWE-rebench", 0))
    mac["DateMin"] = str(D.get("created_at_min", ""))[:10]
    mac["DateMax"] = str(D.get("created_at_max", ""))[:10]
    mac["NOriginContext"] = str(D.get("by_origin", {}).get("context", 0))
    mac["NOriginAdded"] = str(D.get("by_origin", {}).get("added", 0))
    mac["NLeakPairs"] = str(D.get("pairs", 0) - D.get("pairs_no_leak", 0))
    mac["NTooLong"] = str(D.get("pairs_no_leak", 0) - D.get("pairs_judged", 0))
    mac["NJudgedMedianTokens"] = f"{int(D['judged_prompt_tokens']['median']):,}".replace(",", "{,}") \
        if "judged_prompt_tokens" in D else ""
    for key, cls in (("CatchAuth", "authorization_regression"), ("CatchSES", "silent_error_swallowing"),
                     ("CatchRace", "race_condition"), ("CatchRL", "resource_leak")):
        t = D["candidates_tested"].get(cls, 0)
        k = D["caught_by_tests"].get(cls, 0)
        mac[key] = f"{pct(k / t) if t else '--'}\\%, {k}/{t}"
    mac["NGoldMedianLines"] = str(int(D["gold_changed_lines"]["50%"])) if "gold_changed_lines" in D else ""
    mac["NGoldMedianFiles"] = str(int(D["gold_files"]["50%"])) if "gold_files" in D else ""
    mac["NGoldMedianHunks"] = str(int(D["gold_hunks"]["50%"])) if "gold_hunks" in D else ""
    KEY = {"qwen2.5-coder-1.5b": "CoderS", "qwen2.5-coder-3b": "CoderM", "qwen3-1.7b": "QwenS",
           "qwen3-4b": "QwenM", "llama-3.2-3b": "Llama", "gemma-3-4b": "Gemma", "qwen3-1.7b-think": "Think"}
    rj, cj, rc_, cc_ = [], [], [], []
    for m, key in KEY.items():
        bm = S["by_model"].get(m, {})
        for cond, tag in (("diff_only", "R"), ("cjb_control", "C")):
            d = bm.get(cond)
            if not d:
                continue
            mac[f"Acc{tag}{key}"] = f"{pct(d['acc'])}\\%"
            mac[f"Cal{tag}{key}"] = f"{pct(d['acc_calibrated'])}\\%"
            mac[f"CalCI{tag}{key}"] = ci(d["acc_calibrated_ci"])
            mac[f"Flip{tag}{key}"] = f"{pct(d['flip_rate'])}\\%"
            mac[f"N{tag}{key}"] = str(d["n"])
            if m != "qwen3-1.7b-think":
                (rj if tag == "R" else cj).append(d["acc"])
                (rc_ if tag == "R" else cc_).append(d["acc_calibrated"])
    rng = lambda xs: f"{pct(min(xs))}--{pct(max(xs))}\\%" if xs else "--"
    mac["AccRangeR"], mac["AccRangeC"] = rng(rj), rng(cj)
    mac["CalRangeR"], mac["CalRangeC"] = rng(rc_), rng(cc_)
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
            dc = d.get("calibrated", {})
            sgn = lambda x: "+" if x >= 0 else ""
            rows.append(f"{NICE.get(m, m)} & {COND.get(cond, cond)} & {pct(other.get('acc'))} & "
                        f"{sgn(d['diff'])}{pct(d['diff'])} {ci(d['ci'])} & "
                        + (f"{sgn(dc['diff'])}{pct(dc['diff'])} {ci(dc['ci'])}" if dc else "--")
                        + f" & {d['n']} \\\\")
    if rows:
        (out / "tab_context.tex").write_text(
            "\\begin{table}[t]\n\\caption{Mitigation (O6) and thinking: accuracy (\\%) of each condition "
            "and paired difference to the diff-only prompt on the same pairs (raw and after balanced position calibration).}\n\\label{tab:context}\n"
            "\\centering\\footnotesize\n\\setlength{\\tabcolsep}{3pt}\n\\begin{tabular}{@{}llrrrr@{}}\n\\toprule\n"
            "Judge & Condition & Acc. & $\\Delta$ & $\\Delta$ calib. & $n$ \\\\\n\\midrule\n" + "\n".join(rows) +
            "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")

    # ---- length-bias table ----------------------------------------------------
    LB = S.get("length_bias", {})
    if LB:
        rows = []
        for m in models + ["all_judges"]:
            d = LB.get(m)
            if not d:
                continue
            g = lambda k: (f"{pct(d[k]['acc_calibrated'])} ({d[k]['n']})" if k in d else "--")
            pl = d.get("prefers_longer")
            rows.append(" & ".join([NICE.get(m, "All judges" if m == "all_judges" else m),
                                    g("variant_longer"), g("same_length"), g("variant_shorter"),
                                    f"{pct(pl['rate'])} {ci(pl['ci'])}" if pl else "--"]) + " \\\\")
        rc = S.get("length_relation_counts", {})
        (out / "tab_length.tex").write_text(
            "\\begin{table}[t]\n\\caption{Length bias on \\RJB{}: position-calibrated accuracy (\\%) by "
            "whether the defective variant's diff has more, the same or fewer changed lines than the gold patch "
            f"(judged pairs: {rc.get('variant_longer', 0)} / {rc.get('same_length', 0)} / {rc.get('variant_shorter', 0)}); "
            "$n$ in parentheses. Last column: share of pairs of unequal length in which the judge prefers the longer patch.}\n"
            "\\label{tab:length}\n\\centering\\footnotesize\n\\begin{tabular}{@{}lrrrl@{}}\n\\toprule\n"
            "Judge & Var.\\ longer & Same & Var.\\ shorter & Prefers longer \\\\\n\\midrule\n" + "\n".join(rows) +
            "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")

    # ---- baselines table -------------------------------------------------------
    rows = ["Random & 50.0 & -- \\\\", "Execution oracle (PR tests) & 0.0 & by construction \\\\"]
    lh = S.get("length_heuristic")
    if lh:
        rows.append(f"Shorter-patch heuristic & {pct(lh['acc'])} & {ci(lh['ci'])}; artefact check \\\\")
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
