// Builds slides/RepoJudgeBench_presentation.pptx: bright palette, Times New Roman,
// native (editable) charts and tables; every number is read from results/summary.json.
//   NODE_PATH=<dir with pptxgenjs> SKILL_DIR=<pptx skill dir> node slides/source/build_presentation.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(path.join(process.env.SKILL_DIR, "scripts/apply_theme.js"));

const ROOT = path.resolve(__dirname, "../..");
const S = JSON.parse(fs.readFileSync(path.join(ROOT, "results/summary.json")));
const BINS = JSON.parse(fs.readFileSync(path.join(ROOT, "results/pptx_bins.json")));
const OUT = path.join(ROOT, "slides/RepoJudgeBench_presentation.pptx");

const FONT = "Times New Roman";
const THEME = {
  name: "RepoJudgeBench Bright",
  headFontFace: FONT,
  bodyFontFace: FONT,
  colors: {
    dk1: "1A237E", lt1: "FFFFFF", dk2: "6200EA", lt2: "E3F2FD",
    accent1: "2962FF", accent2: "E91E63", accent3: "FF6D00", accent4: "00C853",
    accent5: "AA00FF", accent6: "00B8D4", hlink: "2962FF", folHlink: "AA00FF",
  },
};
const H = THEME.colors;
// light tints of the bright colours, for cards (hex, used as card fills)
const TINT = { blue: "E3F2FD", pink: "FCE4EC", orange: "FFF3E0", green: "E8F5E9", purple: "F3E5F5", cyan: "E0F7FA", yellow: "FFF8E1" };
const GRID = "BBDEFB";

const pct = (x, d = 1) => (100 * x).toFixed(d) + "%";
const ci = (c) => `[${Math.round(100 * c[0])}, ${Math.round(100 * c[1])}]`;
const D = S.dataset;
const M = S.models;
const BASE = M.filter((m) => !m.endsWith("think"));
const NICE = {
  "qwen2.5-coder-1.5b": "Qwen2.5-Coder-1.5B", "qwen2.5-coder-3b": "Qwen2.5-Coder-3B",
  "qwen3-1.7b": "Qwen3-1.7B", "qwen3-4b": "Qwen3-4B", "llama-3.2-3b": "Llama-3.2-3B",
  "gemma-3-4b": "Gemma-3-4B", "qwen3-1.7b-think": "Qwen3-1.7B (thinking)",
};
const cand = Object.values(D.candidates_tested).reduce((a, b) => a + b, 0);
const caught = Object.values(D.caught_by_tests).reduce((a, b) => a + b, 0);
const rjRaw = BASE.map((m) => S.by_model[m].diff_only.acc);
const cjRaw = BASE.map((m) => S.by_model[m].cjb_control.acc);
const rjCal = BASE.map((m) => S.by_model[m].diff_only.acc_calibrated);
const smallCal = ["qwen2.5-coder-1.5b", "qwen2.5-coder-3b", "qwen3-1.7b"].map((m) => S.by_model[m].diff_only.acc_calibrated);
const flips = M.flatMap((m) => [S.by_model[m].cjb_control.flip_rate, S.by_model[m].diff_only.flip_rate]);
const lrc = S.length_relation_counts;
const varLongerShare = lrc.variant_longer / (lrc.variant_longer + lrc.same_length + lrc.variant_shorter);

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = "Muhammad Usama; Ali Raza";
pres.title = "RepoJudgeBench";
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
const C = pres.SchemeColor;

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
  title: "HERO",
  background: { color: C.accent1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.9, w: 8.8, h: 1.1, fontSize: 48, bold: true,
        color: C.background1, align: "left", valign: "bottom", fontFace: FONT }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.1, w: 8.8, h: 3.1, fontSize: 18,
        color: C.background1, align: "left", valign: "top", fontFace: FONT }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.45, y: 0.25, w: 9.1, h: 0.7, fontSize: 28, bold: true,
        color: C.accent1, align: "left", valign: "middle", fontFace: FONT }, text: "" } },
  ],
  slideNumber: { x: 9.25, y: 5.22, w: 0.5, h: 0.3, fontSize: 11, color: C.accent5, fontFace: FONT },
});
pres.defineSlideMaster({
  title: "BOLD",
  background: { color: C.accent5 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.45, y: 0.25, w: 9.1, h: 0.7, fontSize: 28, bold: true,
        color: C.background1, align: "left", valign: "middle", fontFace: FONT }, text: "" } },
  ],
  slideNumber: { x: 9.25, y: 5.22, w: 0.5, h: 0.3, fontSize: 11, color: C.background1, fontFace: FONT },
});

// ------------------------------------------------------------------ helpers
const T = (o) => Object.assign({ fontFace: FONT, isTextBox: true }, o);
function bullets(slide, items, opts) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 7 } })),
    T(Object.assign({ fontSize: 16, color: C.text1, valign: "top" }, opts)));
}
function card(slide, x, y, w, h, fill, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill },
    rectRadius: 0.08, objectName: name });
}
function stat(slide, x, y, w, h, big, label, color, fill, name, bigSize = 30) {
  card(slide, x, y, w, h, fill, name + " card");
  slide.addText(big, T({ x: x + 0.15, y: y + 0.08, w: w - 0.3, h: 0.62, fontSize: bigSize, bold: true, color, margin: 0,
    valign: "middle", objectName: name + " value" }));
  slide.addText(label, T({ x: x + 0.15, y: y + 0.7, w: w - 0.3, h: h - 0.78, fontSize: 13, color: C.text1, margin: 0,
    valign: "top", objectName: name + " label" }));
}
function circle(slide, x, y, n, color, d = 0.44) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color } });
  slide.addText(String(n), T({ x, y, w: d, h: d, fontSize: 15, bold: true, color: C.background1, align: "center",
    valign: "middle", margin: 0 }));
}
function table(slide, rows, opts, headFill = C.accent1) {
  slide.addTable(rows.map((r, i) => r.map((t) => ({ text: String(t), options: {
    bold: i === 0, color: i === 0 ? C.background1 : C.text1, fontFace: FONT,
    fill: { color: i === 0 ? headFill : (i % 2 ? TINT.blue : "FFFFFF") } } }))),
  Object.assign({ fontSize: 12, rowH: 0.34, border: { type: "solid", pt: 0.5, color: GRID }, valign: "middle" }, opts));
}
const CH = { catAxisLabelFontFace: FONT, valAxisLabelFontFace: FONT, legendFontFace: FONT, dataLabelFontFace: FONT,
  titleFontFace: FONT, catAxisLabelColor: H.dk1, valAxisLabelColor: H.dk2, titleColor: H.dk1, dataLabelColor: H.dk1,
  valGridLine: { color: GRID, size: 0.5 }, catGridLine: { style: "none" }, catAxisLabelFontSize: 11, valAxisLabelFontSize: 10,
  titleFontSize: 14, dataLabelFontSize: 10 };
const chartOpts = (o) => Object.assign({}, CH, o);

// ================================================================== 1 title
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "HERO", sectionTitle: "Introduction" });
s.addText("RepoJudgeBench", { placeholder: "title" });
s.addText([
  { text: "Does LLM-as-a-Judge reliability survive the move from self-contained functions to repository-level, test-passing code changes?", options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 10 } },
  { text: "Muhammad Usama  |  25I-8007  |  i258007@isb.nu.edu.pk", options: { bold: true, color: "FFEB3B", fontSize: 16, breakLine: true } },
  { text: "Ali Raza  |  25I-8043  |  i258043@isb.nu.edu.pk", options: { bold: true, color: "FFEB3B", fontSize: 16, breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "Natural Language Processing, Semester Research Project  |  FAST-NUCES Islamabad", options: { fontSize: 14 } },
], { placeholder: "body" });
s.addNotes("Base paper: Jiang et al., CodeJudgeBench: Benchmarking LLM-as-a-Judge for Coding Tasks, arXiv:2507.10535.");

// ================================================================== 2 problem
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Problem definition", { placeholder: "title" });
bullets(s, [
  "LLMs now judge code: ranking agent patches, filtering training data, reward models, pull-request review bots",
  "The usual oracle, the test suite, is weak at repository level",
  "Existing judge benchmarks (CodeJudgeBench) contain only single-file programs decided by hidden tests",
  "Question: can a judge tell a correct patch from a test-passing but defective one in a real repository?",
], { x: 0.45, y: 1.1, w: 5.4, h: 4.1 });
stat(s, 6.1, 1.1, 3.45, 1.25, "32.67%", "of accepted SWE-Agent+GPT-4 patches leaked the solution", C.accent2, TINT.pink, "leak");
stat(s, 6.1, 2.5, 3.45, 1.25, "31.08%", "passed only because the tests were too weak", C.accent3, TINT.orange, "weak");
stat(s, 6.1, 3.9, 3.45, 1.25, "12.47% → 3.97%", "resolution rate after removing suspicious fixes", C.accent1, TINT.blue, "drop", 26);
s.addNotes("All three numbers: Aleithan et al., SWE-Bench+, arXiv:2410.06992.");

// ================================================================== 3 motivation
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Research motivation", { placeholder: "title" });
const mot = [
  ["Tests miss review-level defects", "N+1 queries, races, authorisation and migration regressions, leaked resources, swallowed errors", C.accent2],
  ["Judges are load-bearing infrastructure", "their mistakes flow into leaderboards, training data and reward signals", C.accent3],
  ["Known failure modes are untested at scale", "order and generator sensitivity were measured only on short, single-file code", C.accent4],
  ["Contamination", "we use only pull requests created on or after 1 January 2025", C.accent5],
];
mot.forEach(([h, t, col], i) => {
  const y = 1.12 + i * 1.0;
  circle(s, 0.5, y + 0.06, i + 1, col);
  s.addText(h, T({ x: 1.15, y, w: 8.4, h: 0.42, fontSize: 19, bold: true, color: col, margin: 0 }));
  s.addText(t, T({ x: 1.15, y: y + 0.42, w: 8.4, h: 0.42, fontSize: 15, color: C.text1, margin: 0 }));
});

// ================================================================== 4 base paper
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Base paper: CodeJudgeBench (Jiang et al., 2025)", { placeholder: "title" });
stat(s, 0.45, 1.1, 2.1, 1.3, "5,352", "response pairs", C.accent1, TINT.blue, "cjb pairs");
stat(s, 2.75, 1.1, 2.1, 1.3, "1,055", "LiveCodeBench-v6 problems (May 2023 – Apr 2025)", C.accent3, TINT.orange, "cjb problems");
stat(s, 5.05, 1.1, 2.1, 1.3, "26", "LLM judges evaluated", C.accent4, TINT.green, "cjb judges");
stat(s, 7.35, 1.1, 2.2, 1.3, "up to 14%", "accuracy change when the two answers are swapped", C.accent2, TINT.pink, "cjb swap", 26);
bullets(s, [
  "Tasks: code generation, code repair, unit-test generation; labels come from executing hidden tests",
  "Findings: thinking models judge best; pairwise beats point-wise scoring; judges are sensitive to answer order",
  "Gap we address: every instance is single-file and test-decidable — nothing about repository-level diffs that pass CI",
], { x: 0.45, y: 2.65, w: 9.1, h: 2.5, fontSize: 16 });

// ================================================================== 5 pipeline
pres.addSection({ title: "Method" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Proposed solution: the RepoJudgeBench pipeline", { placeholder: "title" });
const steps = [
  ["Select", "real PRs created ≥ 2025-01-01 from SWE-bench-Live and SWE-rebench, each with a Docker image", C.accent1, TINT.blue],
  ["Apply", "gold patch inside the task's container, re-rendered with git diff", C.accent6, TINT.cyan],
  ["Inject", "one AST mutation per defect class in the code the PR touches", C.accent5, TINT.purple],
  ["Admit", "keep a variant only if every test that passes with the gold patch still passes", C.accent2, TINT.pink],
  ["Retrieve", "neutral context from the parent commit: definitions and call sites", C.accent3, TINT.orange],
  ["Judge", "CodeJudgeBench pairwise prompt, both orders, bootstrap 95% CIs", C.accent4, TINT.green],
];
steps.forEach(([h, t, col, tint], i) => {
  const x = 0.45 + (i % 3) * 3.07, y = 1.1 + Math.floor(i / 3) * 2.08;
  card(s, x, y, 2.9, 1.9, tint, "step " + (i + 1));
  circle(s, x + 0.15, y + 0.15, i + 1, col);
  s.addText(h, T({ x: x + 0.72, y: y + 0.15, w: 2.0, h: 0.44, fontSize: 19, bold: true, color: col, margin: 0, valign: "middle" }));
  s.addText(t, T({ x: x + 0.15, y: y + 0.72, w: 2.6, h: 1.1, fontSize: 14, color: C.text1, margin: 0, valign: "top" }));
});
s.addNotes("Step 4 is the key property: 'passes CI but is wrong' is guaranteed by construction, so the execution oracle scores 0%.");

// ================================================================== 6 taxonomy
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Defect taxonomy and injection operators", { placeholder: "title" });
const adm = D.admitted;
table(s, [
  ["Defect class", "Injection operator(s)", "Pairs"],
  ["N+1 query", "drop select_related / prefetch_related / eager-loading options", adm.n_plus_one || 0],
  ["Race / concurrency", "unwrap a with <lock>: block; drop select_for_update / @atomic", adm.race_condition || 0],
  ["Authorisation", "delete an if <auth-check>: raise/return guard or access decorator", adm.authorization_regression || 0],
  ["Unsafe migration", "make an added column NOT NULL without a default", adm.unsafe_migration || 0],
  ["Resource leak", "with open(...) as f: → f = open(...); delete x.close()", adm.resource_leak || 0],
  ["Error swallowing", "re-raise → pass; except E → except Exception; delete a validation raise", adm.silent_error_swallowing || 0],
], { x: 0.45, y: 1.1, w: 9.1, colW: [2.0, 6.2, 0.9], rowH: 0.48, fontSize: 13 }, C.accent5);
s.addText("Operators edit the Python AST of the post-patch file, only inside the region the PR touches; unchanged ASTs are rejected.",
  T({ x: 0.45, y: 4.65, w: 9.1, h: 0.5, fontSize: 14, italic: true, color: C.accent5, margin: 0 }));

// ================================================================== 7 contributions
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Technical contributions", { placeholder: "title" });
const contrib = [
  ["New evaluation axis", "judges on repository-level, CI-passing diffs instead of single functions", C.accent1, TINT.blue],
  ["CI-passing injection harness", `${cand} candidates tested in Docker; only test-passing variants admitted`, C.accent2, TINT.pink],
  ["Defect taxonomy", "six review-grounded defect classes with executable AST operators", C.accent3, TINT.orange],
  ["Reliability analysis", "position bias, self-consistency, length bias, diff-size scaling", C.accent4, TINT.green],
  ["Mitigation", "retrieved repository context with a budget ablation, and a thinking mode", C.accent5, TINT.purple],
  ["Released artefacts", "dataset, harness, prompts and every raw verdict log", C.accent6, TINT.cyan],
];
contrib.forEach(([h, t, col, tint], i) => {
  const x = 0.45 + (i % 3) * 3.07, y = 1.1 + Math.floor(i / 3) * 2.08;
  card(s, x, y, 2.9, 1.9, tint, "contribution " + (i + 1));
  s.addText(h, T({ x: x + 0.15, y: y + 0.12, w: 2.6, h: 0.62, fontSize: 17, bold: true, color: col, margin: 0, valign: "middle" }));
  s.addText(t, T({ x: x + 0.15, y: y + 0.8, w: 2.6, h: 1.0, fontSize: 14, color: C.text1, margin: 0, valign: "top" }));
});

// ================================================================== 8 funnel
pres.addSection({ title: "Dataset" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Dataset" });
s.addText("Building the benchmark: from 1,216 PRs to 203 pairs", { placeholder: "title" });
const funnel = [["PRs created ≥ 2025-01-01", 1216], ["Passed the quick screen", 473], ["Processed in Docker", D.instances_processed],
  ["PRs with an admitted variant", D.instances], ["Benchmark pairs", D.pairs], ["Pairs judged", D.pairs_judged]];
s.addChart(pres.charts.BAR, [{ name: "Count", labels: funnel.map((f) => f[0]).reverse(), values: funnel.map((f) => f[1]).reverse() }],
  chartOpts({ x: 0.45, y: 1.05, w: 5.6, h: 4.2, barDir: "bar", chartColors: [H.accent1], showValue: true, dataLabelPosition: "outEnd",
    valAxisMinVal: 0, valAxisMaxVal: 1400, showLegend: false, showTitle: true, title: "Number of PRs / pairs at each stage" }));
const st = D.status;
table(s, [["Why processed PRs dropped out", "PRs"],
  ["No usable mutation site", st.no_mutation_site], ["Gold patch's tests not green", st.gold_tests_not_green],
  ["Every candidate caught by tests", st.all_caught_by_tests], ["Infrastructure failure (e.g. disk)", st.error],
  ["Admitted (in the benchmark)", st.ok]], { x: 6.3, y: 1.15, w: 3.25, colW: [2.5, 0.75], rowH: 0.42, fontSize: 12 }, C.accent3);
s.addText(`${D.pairs - D.pairs_no_leak} pairs removed for solution leakage, ${D.pairs_no_leak - D.pairs_judged} too long for the judges.`,
  T({ x: 6.3, y: 3.85, w: 3.25, h: 1.2, fontSize: 13, italic: true, color: C.accent3, margin: 0, valign: "top" }));

// ================================================================== 9 dataset stats
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Dataset" });
s.addText("RepoJudgeBench in numbers", { placeholder: "title" });
stat(s, 0.45, 1.05, 2.0, 1.25, String(D.pairs), `pairs from ${D.instances} real PRs`, C.accent1, TINT.blue, "pairs");
stat(s, 2.6, 1.05, 2.0, 1.25, String(D.repos), "Python repositories", C.accent4, TINT.green, "repos");
stat(s, 0.45, 2.45, 2.0, 1.25, String(D.gold_changed_lines["50%"]), "median changed lines per gold patch", C.accent5, TINT.purple, "lines");
stat(s, 2.6, 2.45, 2.0, 1.25, `${D.gold_files["50%"]} / ${D.gold_hunks["50%"]}`, "median files / hunks", C.accent6, TINT.cyan, "files");
stat(s, 0.45, 3.85, 4.15, 1.3, pct(caught / cand), `of ${cand} injected defects were caught by the PRs' own tests`, C.accent2, TINT.pink, "caught");
const cls4 = [["Authorisation", "authorization_regression"], ["Error swallowing", "silent_error_swallowing"],
  ["Race / concurrency", "race_condition"], ["Resource leak", "resource_leak"]];
s.addChart(pres.charts.BAR, [{ name: "Caught by tests (%)", labels: cls4.map((c) => c[0]),
  values: cls4.map((c) => +(100 * (D.caught_by_tests[c[1]] || 0) / D.candidates_tested[c[1]]).toFixed(1)) }],
  chartOpts({ x: 4.85, y: 1.05, w: 4.7, h: 4.2, barDir: "col", chartColors: [H.accent2, H.accent3, H.accent4, H.accent1],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 100,
    showLegend: false, showTitle: true, title: "Injected defects caught by the PR's tests (%)" }));
s.addNotes(`Created ${String(D.created_at_min).slice(0, 10)} to ${String(D.created_at_max).slice(0, 10)}. ${D.by_source["SWE-bench-Live"]} pairs from SWE-bench-Live, ${D.by_source["SWE-rebench"]} from SWE-rebench.`);

// ================================================================== 10 protocol
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Dataset" });
s.addText("Judging protocol and judges", { placeholder: "title" });
bullets(s, [
  "CodeJudgeBench pairwise prompt; verdict [[A>B]] or [[B>A]]",
  "Issue text as the user prompt, the two unified diffs as the answers",
  "Forced verdict prefix: logits of A vs B give the verdict and p(A)",
  "Every pair is judged in both orders (gold as A, gold as B)",
  "Accuracy = mean of both orders; 95% bootstrap CIs over PRs",
  "Control: 45 CodeJudgeBench pairs (15 per task)",
], { x: 0.45, y: 1.1, w: 4.6, h: 4.1, fontSize: 15 });
table(s, [["Judge", "Size", "Type"],
  ["Qwen2.5-Coder-1.5B", "1.5B", "code"], ["Qwen2.5-Coder-3B", "3B", "code"], ["Qwen3-1.7B", "1.7B", "hybrid"],
  ["Qwen3-1.7B (thinking)", "1.7B", "thinking"], ["Qwen3-4B", "4B", "hybrid"], ["Llama-3.2-3B", "3B", "general"],
  ["Gemma-3-4B", "4B", "general"]], { x: 5.3, y: 1.1, w: 4.25, colW: [2.35, 0.8, 1.1], rowH: 0.4, fontSize: 13 }, C.accent4);
s.addText("All open-weight, run locally with llama.cpp on CPU (no GPU, no API).",
  T({ x: 5.3, y: 4.45, w: 4.25, h: 0.6, fontSize: 13, italic: true, color: C.accent4, margin: 0 }));

// ================================================================== 11 result: raw accuracy chart
pres.addSection({ title: "Results" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 1: raw accuracy is at chance in both regimes", { placeholder: "title" });
const ml = M.map((m) => NICE[m]);
s.addChart(pres.charts.BAR, [
  { name: "CodeJudgeBench control (single-file)", labels: ml, values: M.map((m) => +(100 * S.by_model[m].cjb_control.acc).toFixed(1)) },
  { name: "RepoJudgeBench (repository-level)", labels: ml, values: M.map((m) => +(100 * S.by_model[m].diff_only.acc).toFixed(1)) },
], chartOpts({ x: 0.45, y: 1.0, w: 6.6, h: 4.3, barDir: "col", barGrouping: "clustered", chartColors: [H.accent1, H.accent2],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", dataLabelFontSize: 9, catAxisLabelFontSize: 9,
  valAxisMinVal: 0, valAxisMaxVal: 80, showLegend: true, legendPos: "t", legendFontSize: 11, showTitle: true,
  title: "Pairwise accuracy (%)" }));
stat(s, 7.3, 1.05, 2.25, 1.2, "50%", "random baseline", C.accent5, TINT.purple, "random", 28);
stat(s, 7.3, 2.4, 2.25, 1.35, `${pct(Math.min(...rjRaw))}–${pct(Math.max(...rjRaw))}`, "range on RepoJudgeBench", C.accent2, TINT.pink, "rj range", 22);
stat(s, 7.3, 3.9, 2.25, 1.35, `${pct(Math.min(...cjRaw))}–${pct(Math.max(...cjRaw))}`, "range on the control set", C.accent1, TINT.blue, "cj range", 22);

// ================================================================== 12 result: main table
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Accuracy per judge with 95% confidence intervals", { placeholder: "title" });
const mainRows = [["Judge", "Control acc.", "RepoJudgeBench acc.", "Control calib.", "RepoJudgeBench calib.", "n (C / R)"]];
M.forEach((m) => {
  const c = S.by_model[m].cjb_control, r = S.by_model[m].diff_only;
  mainRows.push([NICE[m], `${pct(c.acc)} ${ci(c.ci)}`, `${pct(r.acc)} ${ci(r.ci)}`, pct(c.acc_calibrated),
    `${pct(r.acc_calibrated)} ${ci(r.acc_calibrated_ci)}`, `${c.n} / ${r.n}`]);
});
table(s, mainRows, { x: 0.45, y: 1.05, w: 9.1, colW: [2.15, 1.5, 1.65, 1.15, 1.75, 0.9], rowH: 0.42, fontSize: 12 }, C.accent1);
s.addText("Calibrated = balanced position calibration: the probability given to the gold patch is averaged over both orders before deciding.",
  T({ x: 0.45, y: 4.65, w: 9.1, h: 0.55, fontSize: 13, italic: true, color: C.accent5, margin: 0 }));

// ================================================================== 13 result: position bias
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 2: verdicts follow the position, not the patch", { placeholder: "title" });
s.addChart(pres.charts.BAR, [
  { name: "Control", labels: ml, values: M.map((m) => +(100 * S.by_model[m].cjb_control.p_choose_A).toFixed(1)) },
  { name: "RepoJudgeBench", labels: ml, values: M.map((m) => +(100 * S.by_model[m].diff_only.p_choose_A).toFixed(1)) },
], chartOpts({ x: 0.45, y: 1.0, w: 6.2, h: 4.3, barDir: "col", barGrouping: "clustered", chartColors: [H.accent6, H.accent3],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0", dataLabelFontSize: 9, catAxisLabelFontSize: 9,
  valAxisMinVal: 0, valAxisMaxVal: 100, showLegend: true, legendPos: "t", legendFontSize: 11, showTitle: true,
  title: "Probability of choosing the first slot, P(A) (%)" }));
stat(s, 6.9, 1.05, 2.65, 1.3, `${pct(Math.min(...flips), 0)}–${pct(Math.max(...flips), 0)}`, "flip rate: same slot chosen in both orders", C.accent3, TINT.orange, "flip", 26);
stat(s, 6.9, 2.5, 2.65, 1.3, "100%", "Qwen2.5-Coder-1.5B picks A on every RepoJudgeBench prompt", C.accent2, TINT.pink, "coder", 26);
stat(s, 6.9, 3.95, 2.65, 1.3, "≤ 4%", "P(A) for the 4B judges: they almost always pick B", C.accent6, TINT.cyan, "4b", 26);

// ================================================================== 14 result: calibrated + length
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 3: calibrated, small judges pick the defect", { placeholder: "title" });
const calM = M.slice().reverse();
s.addChart(pres.charts.BAR, [{ name: "Calibrated accuracy (%)", labels: calM.map((m) => NICE[m]),
  values: calM.map((m) => +(100 * S.by_model[m].diff_only.acc_calibrated).toFixed(1)) }],
  chartOpts({ x: 0.45, y: 1.0, w: 5.6, h: 4.3, barDir: "bar", chartColors: [H.accent4], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 100, showLegend: false, showTitle: true,
    title: "Calibrated accuracy on RepoJudgeBench (%), 50 = chance" }));
stat(s, 6.3, 1.05, 3.25, 1.3, `${pct(Math.min(...smallCal))}–${pct(Math.max(...smallCal))}`, "three smallest judges: significantly below chance", C.accent2, TINT.pink, "small", 24);
stat(s, 6.3, 2.5, 3.25, 1.3, pct(S.by_model["qwen3-4b"].diff_only.acc_calibrated), `Qwen3-4B ${ci(S.by_model["qwen3-4b"].diff_only.acc_calibrated_ci)}: the only judge clearly above chance`, C.accent4, TINT.green, "q4b", 26);
stat(s, 6.3, 3.95, 3.25, 1.3, pct(S.by_model["gemma-3-4b"].diff_only.acc_calibrated), `Gemma-3-4B ${ci(S.by_model["gemma-3-4b"].diff_only.acc_calibrated_ci)}: borderline`, C.accent1, TINT.blue, "gemma", 26);

// ================================================================== 15 result: length bias
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 4: length bias", { placeholder: "title" });
const lb = S.length_bias.all_judges;
s.addChart(pres.charts.BAR, [{ name: "Calibrated accuracy (%)", labels: ["Variant longer", "Same length", "Variant shorter"],
  values: [lb.variant_longer, lb.same_length, lb.variant_shorter].map((x) => +(100 * x.acc_calibrated).toFixed(1)) }],
  chartOpts({ x: 0.45, y: 1.0, w: 4.9, h: 4.3, barDir: "col", chartColors: [H.accent2, H.accent5, H.accent4], showValue: true,
    dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 100, showLegend: false, showTitle: true,
    title: "All judges: calibrated accuracy by diff length (%)" }));
stat(s, 5.6, 1.05, 3.95, 1.2, pct(varLongerShare), "of judged pairs: the defective variant's diff is longer", C.accent3, TINT.orange, "longer", 26);
stat(s, 5.6, 2.4, 3.95, 1.2, "77–87%", "small judges prefer the longer patch (unequal pairs); 4B judges only 41%", C.accent2, TINT.pink, "prefers", 26);
stat(s, 5.6, 3.75, 3.95, 1.45, pct(S.length_heuristic.acc), `"pick the shorter patch" rule ${ci(S.length_heuristic.ci)}: a benchmark artefact we report openly`, C.accent5, TINT.purple, "heuristic", 26);

// ================================================================== 16 result: diff size
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 5: no measurable effect of diff size (O3)", { placeholder: "title" });
const bl = BINS.labels.map((l, i) => `${l} (n=${BINS.n[i]})`);
s.addChart(pres.charts.LINE, [
  { name: "Mean of judges, raw", labels: bl, values: BINS.raw.map((v) => +(100 * v).toFixed(1)) },
  { name: "Mean of judges, calibrated", labels: bl, values: BINS.cal.map((v) => +(100 * v).toFixed(1)) },
], chartOpts({ x: 0.45, y: 1.0, w: 5.2, h: 4.3, chartColors: [H.accent1, H.accent3], lineSize: 3, lineDataSymbolSize: 8,
  catAxisLabelFontSize: 10, valAxisMinVal: 0, valAxisMaxVal: 100, showLegend: true, legendPos: "b", legendFontSize: 11,
  showTitle: true, title: "Accuracy (%) by changed lines in the gold patch" }));
const co = S.scaling.pooled.coef;
const fmt = (v) => `${v.b >= 0 ? "+" : ""}${v.b.toFixed(3)}`;
table(s, [["Predictor", "β", "95% CI", "p"],
  ["log2(lines)", fmt(co.log2_lines), `[${co.log2_lines.ci[0].toFixed(3)}, ${co.log2_lines.ci[1].toFixed(3)}]`, co.log2_lines.p.toFixed(3)],
  ["Files", fmt(co.files), `[${co.files.ci[0].toFixed(3)}, ${co.files.ci[1].toFixed(3)}]`, co.files.p.toFixed(3)],
  ["Hunks", fmt(co.hunks), `[${co.hunks.ci[0].toFixed(3)}, ${co.hunks.ci[1].toFixed(3)}]`, co.hunks.p.toFixed(3)]],
  { x: 5.9, y: 1.1, w: 3.65, colW: [1.0, 0.75, 1.25, 0.65], rowH: 0.42, fontSize: 11 }, C.accent3);
s.addText(`Pooled logistic regression, ${S.scaling.pooled.n_obs} judgements. No coefficient differs from zero; accuracy is indistinguishable from chance from ${S.scaling.pooled.chance_from_lines} changed lines upward.`,
  T({ x: 5.9, y: 3.0, w: 3.65, h: 2.2, fontSize: 14, color: C.text1, margin: 0, valign: "top" }));

// ================================================================== 17 result: classes
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 6: defect-class error profile (O4)", { placeholder: "title" });
const allc = S.by_class.all_judges, stc = S.static.relevant.by_class;
const crows = [["Defect class", "Judged pairs", "Judges, calibrated acc.", "Static analysis acc."]];
[["Authorisation", "authorization_regression"], ["Resource leak", "resource_leak"], ["Error swallowing", "silent_error_swallowing"],
 ["Race / concurrency", "race_condition"], ["N+1 query", "n_plus_one"]].forEach(([n, k]) => {
  crows.push([n, D.by_class_judged[k] || 0, `${pct(allc[k].acc_calibrated)} ${ci(allc[k].acc_calibrated_ci)}`, stc[k] ? pct(stc[k].acc) : "–"]);
});
table(s, crows, { x: 0.45, y: 1.1, w: 9.1, colW: [2.5, 1.6, 2.8, 2.2], rowH: 0.52, fontSize: 15 }, C.accent2);
s.addText("Removing an authorisation guard is the defect judges miss most. Unsafe migrations: no candidate found; N+1 and race classes are too small to conclude.",
  T({ x: 0.45, y: 4.35, w: 9.1, h: 0.85, fontSize: 15, color: C.accent2, margin: 0, valign: "top" }));

// ================================================================== 18 result: mitigation
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 7: repository context and thinking (O6)", { placeholder: "title" });
const COND = { ctx_retrieved_2000: "+ retrieved context, 2k chars", ctx_retrieved_6000: "+ retrieved context, 6k chars",
  ctx_file_6000: "+ file context, 6k chars", think: "thinking mode (512 tokens)" };
const mrows = [["Judge", "Condition", "Δ raw", "Δ calibrated", "n"]];
for (const [m, conds] of Object.entries(S.context_gain)) {
  for (const [cname, d] of Object.entries(conds)) {
    if (cname.includes("::")) continue;
    const sg = (x) => (x >= 0 ? "+" : "") + (100 * x).toFixed(1);
    mrows.push([NICE[m], COND[cname] || cname, `${sg(d.diff)} ${ci(d.ci)}`, `${sg(d.calibrated.diff)} ${ci(d.calibrated.ci)}`, d.n]);
  }
}
table(s, mrows, { x: 0.45, y: 1.1, w: 9.1, colW: [2.1, 2.9, 1.5, 1.9, 0.7], rowH: 0.5, fontSize: 14 }, C.accent4);
s.addText("Context and thinking reduce the preference for the defective patch (significant only for Qwen3-1.7B), but no small judge rises above chance.",
  T({ x: 0.45, y: 4.35, w: 9.1, h: 0.85, fontSize: 15, color: C.accent4, margin: 0, valign: "top" }));

// ================================================================== 19 result: baselines
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 8: baselines", { placeholder: "title" });
const bestRaw = Math.max(...rjRaw), bestCal = Math.max(...rjCal);
const base = [["Execution oracle (PR tests)", 0], ["Random", 0.5], ["Best judge, raw", bestRaw], ["Best judge, calibrated", bestCal],
  ["Static analysis, 8 targeted rules", S.static.relevant.acc], ["Static analysis, all rules", S.static.all.acc], ["Shorter-patch heuristic", S.length_heuristic.acc]];
s.addChart(pres.charts.BAR, [{ name: "Accuracy (%)", labels: base.map((b) => b[0]).reverse(), values: base.map((b) => +(100 * b[1]).toFixed(1)).reverse() }],
  chartOpts({ x: 0.45, y: 1.0, w: 5.9, h: 4.3, barDir: "bar", chartColors: [H.accent5], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 100, showLegend: false, showTitle: true, title: "Accuracy on RepoJudgeBench (%)" }));
const pw = S.pointwise["qwen2.5-coder-1.5b"];
stat(s, 6.6, 1.05, 2.95, 1.3, pct(S.static.relevant.acc), `static analysis flags the variant in ${pct(S.static.relevant.flag_variant_rate)} of pairs, never the gold`, C.accent5, TINT.purple, "static", 26);
stat(s, 6.6, 2.5, 2.95, 1.3, "0%", "execution oracle: both patches pass the same tests by construction", C.accent2, TINT.pink, "oracle", 26);
stat(s, 6.6, 3.95, 2.95, 1.3, pct(pw.greedy_tie_rate), `point-wise 1–5 ratings tie (Qwen2.5-Coder-1.5B, acc. ${pct(pw.acc)})`, C.accent3, TINT.orange, "pointwise", 26);

// ================================================================== 20 findings
pres.addSection({ title: "Conclusion" });
s = pres.addSlide({ masterName: "BOLD", sectionTitle: "Conclusion" });
s.addText("Key findings", { placeholder: "title" });
const finds = [
  `The PRs' own tests catch only ${pct(caught / cand)} of the review-relevant defects we injected`,
  `Raw accuracy of all judges is at chance (${pct(Math.min(...rjRaw))}–${pct(Math.max(...rjRaw))}); verdicts follow the presentation slot`,
  `After calibration the smallest judges prefer the defective, longer patch (${pct(Math.min(...smallCal))}–${pct(Math.max(...smallCal))})`,
  `Only the 4B judges keep a weak correct signal (up to ${pct(bestCal)}); diff size has no measurable effect`,
  `Targeted static analysis (${pct(S.static.relevant.acc)}) beats every judge's raw accuracy`,
  "Our benchmark has a length artefact: the next version must length-match the variants",
];
const fcol = [C.accent6, C.accent3, C.accent2, C.accent4, C.accent1, "FFC400"];
finds.forEach((t, i) => {
  const y = 1.1 + i * 0.7;
  circle(s, 0.5, y, i + 1, fcol[i]);
  s.addText(t, T({ x: 1.12, y: y - 0.04, w: 8.45, h: 0.52, fontSize: 16, color: C.background1, margin: 0, valign: "middle" }));
});

// ================================================================== 21 limitations
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Conclusion" });
s.addText("Limitations and future work", { placeholder: "title" });
const lim = [
  ["Scale", `${D.pairs} pairs from ${D.repos} repositories (proposal: ≥300 pairs); each PR needs a multi-GB image and a test run`, C.accent1, TINT.blue],
  ["Judges", "only small open models (1.5–4B) on CPU; no GPU or API for frontier judges", C.accent2, TINT.pink],
  ["Test oracle", "the PR's test files instead of full suites; no per-instance witness tests", C.accent3, TINT.orange],
  ["Validation", "no human annotation yet; annotation sheet and Cohen's kappa script released", C.accent4, TINT.green],
  ["Next version", "length-matched variants, Django/SQLAlchemy repos for N+1 and migrations, GPU judges", C.accent5, TINT.purple],
];
lim.forEach(([h, t, col, tint], i) => {
  const y = 1.08 + i * 0.83;
  card(s, 0.45, y, 2.0, 0.66, tint, h + " label");
  s.addText(h, T({ x: 0.45, y, w: 2.0, h: 0.66, fontSize: 16, bold: true, color: col, align: "center", valign: "middle", margin: 0 }));
  s.addText(t, T({ x: 2.7, y, w: 6.85, h: 0.66, fontSize: 15, color: C.text1, valign: "middle", margin: 0 }));
});

// ================================================================== 22 demo + thanks
s = pres.addSlide({ masterName: "HERO", sectionTitle: "Conclusion" });
s.addText("Demo and questions", { placeholder: "title" });
s.addText([
  { text: "Live demo:", options: { bold: true, color: "FFEB3B", breakLine: true } },
  { text: "python scripts/demo.py --model models/qwen2.5-coder-1.5b-instruct-q8_0.gguf", options: { breakLine: true, fontSize: 16 } },
  { text: "shows one pair, the injected defect, the tests both patches pass, and the judge's verdict in both orders", options: { breakLine: true, fontSize: 15 } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "Reproduce everything: bash scripts/finalize.sh", options: { breakLine: true, fontSize: 16 } },
  { text: "Code, data and verdict logs: github.com/the-mgi/nlp-project-", options: { breakLine: true, fontSize: 16 } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "Thank you!  Questions?", options: { bold: true, fontSize: 26, color: "FFC400" } },
], { placeholder: "body" });

pres.writeFile({ fileName: OUT }).then(async () => {
  await applyTheme(OUT, THEME);
  // bullet glyphs in the master text styles default to Arial: use Times New Roman throughout
  const JSZip = require("jszip");
  const zip = await JSZip.loadAsync(fs.readFileSync(OUT));
  for (const name of Object.keys(zip.files)) {
    if (/^ppt\/(slideMasters|slideLayouts)\/.*\.xml$/.test(name)) {
      const xml = await zip.file(name).async("string");
      zip.file(name, xml.split('buFont typeface="Arial"').join('buFont typeface="Times New Roman"'));
    }
  }
  fs.writeFileSync(OUT, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
  console.log("wrote", OUT);
});
