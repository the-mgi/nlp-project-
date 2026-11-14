// Builds slides/RepoJudgeBench_slides.pptx (editable; native charts and tables).
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const { applyTheme } = require(process.env.SKILL_DIR + "/scripts/apply_theme.js");

const S = JSON.parse(fs.readFileSync("../../results/summary.json"));
const BINS = JSON.parse(fs.readFileSync("../../results/pptx_bins.json"));
const OUT = "../RepoJudgeBench_slides.pptx";

const THEME = {
  name: "RepoJudgeBench",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1D2B3A", lt1: "FFFFFF", dk2: "34495E", lt2: "EEF2F5",
    accent1: "2A9D8F", accent2: "E9A23B", accent3: "C8553D", accent4: "5C6B7A",
    accent5: "8AB17D", accent6: "264653", hlink: "2A9D8F", folHlink: "5C6B7A",
  },
};
const HEX = THEME.colors;
const pct = (x, d = 1) => (100 * x).toFixed(d) + "%";
const M = S.models;
const NICE = {
  "qwen2.5-coder-1.5b": "Qwen2.5-Coder-1.5B", "qwen2.5-coder-3b": "Qwen2.5-Coder-3B",
  "qwen3-1.7b": "Qwen3-1.7B", "qwen3-4b": "Qwen3-4B", "llama-3.2-3b": "Llama-3.2-3B",
  "gemma-3-4b": "Gemma-3-4B", "qwen3-1.7b-think": "Qwen3-1.7B (thinking)",
};
const D = S.dataset;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = "Muhammad Usama";
pres.title = "RepoJudgeBench";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "DARK_TITLE",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.35, w: 8.8, h: 1.0,
        fontSize: 44, bold: true, color: C.background1, align: "left", valign: "bottom" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.45, w: 8.8, h: 1.2,
        fontSize: 18, color: C.background2, align: "left", valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.7,
        fontSize: 28, bold: true, color: C.text1, align: "left", valign: "middle" }, text: "" } },
  ],
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.accent4 },
});
pres.defineSlideMaster({
  title: "DARK_CONTENT",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.7,
        fontSize: 28, bold: true, color: C.background1, align: "left", valign: "middle" }, text: "" } },
  ],
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.background2 },
});

// ---------------------------------------------------------------- helpers
function bullets(slide, items, opts) {
  const runs = items.map((t, i) => ({
    text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 8 },
  }));
  slide.addText(runs, Object.assign({ isTextBox: true, fontSize: 15, color: C.text1, valign: "top" }, opts));
}
function stat(slide, x, y, w, big, label, color, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 1.25, fill: { color: C.background2 },
    line: { color: C.background2 }, rectRadius: 0.08, objectName: name + " card" });
  slide.addText(big, { x: x + 0.15, y: y + 0.08, w: w - 0.3, h: 0.65, fontSize: 30, bold: true,
    color: color, fontFace: THEME.headFontFace, isTextBox: true, margin: 0, objectName: name + " value" });
  slide.addText(label, { x: x + 0.15, y: y + 0.72, w: w - 0.3, h: 0.48, fontSize: 11, color: C.text2,
    isTextBox: true, margin: 0, valign: "top", objectName: name + " label" });
}
function numberCircle(slide, x, y, n, color) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color }, line: { color } });
  slide.addText(String(n), { x, y, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: C.background1,
    align: "center", valign: "middle", isTextBox: true, margin: 0 });
}
const chartText = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  legendFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt" };

// ---------------------------------------------------------------- 1 title
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "DARK_TITLE", sectionTitle: "Introduction" });
s.addText("RepoJudgeBench", { placeholder: "title" });
s.addText([
  { text: "Does LLM-as-a-Judge reliability survive the move from self-contained functions to repository-level, test-passing code changes?", options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "Muhammad Usama  ·  25I-8007  ·  Natural Language Processing, Semester Research Project", options: { fontSize: 13, color: C.accent2 } },
], { placeholder: "body" });
s.addNotes("Title. Base paper: Jiang et al., CodeJudgeBench (arXiv:2507.10535).");

// ---------------------------------------------------------------- 2 problem
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Problem definition", { placeholder: "title" });
bullets(s, [
  "LLMs judge code: ranking agent patches, filtering training data, reward models, PR review bots",
  "The usual oracle, the test suite, is weak at repository level",
  "CodeJudgeBench (base paper): 5,352 pairs, but every instance is single-file and test-decidable",
  "Question: can judges tell a correct patch from a test-passing but defective one in a real repository?",
], { x: 0.5, y: 1.15, w: 5.3, h: 3.9 });
stat(s, 6.2, 1.15, 3.3, "32.67%", "of accepted SWE-Agent+GPT-4 patches leaked the solution (SWE-Bench+)", C.accent3, "leak");
stat(s, 6.2, 2.55, 3.3, "31.08%", "passed only because the tests were too weak (SWE-Bench+)", C.accent2, "weak");
stat(s, 6.2, 3.95, 3.3, "12.47% → 3.97%", "resolution rate after filtering suspicious fixes", C.accent1, "drop");
s.addNotes("Numbers from Aleithan et al., SWE-Bench+, arXiv:2410.06992.");

// ---------------------------------------------------------------- 3 motivation
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Research motivation", { placeholder: "title" });
const mot = [
  ["Tests miss review-level defects", "N+1 queries, races, authorisation and migration regressions, resource leaks, swallowed errors"],
  ["Judges are load-bearing infrastructure", "their errors propagate into rankings, training data and reward signals"],
  ["Known failure modes are untested at scale", "order and generator sensitivity were measured on short, single-file code only"],
  ["Contamination", "only pull requests created after 1 January 2025"],
];
mot.forEach(([h, t], i) => {
  const y = 1.2 + i * 0.95;
  numberCircle(s, 0.6, y + 0.05, i + 1, C.accent1);
  s.addText(h, { x: 1.2, y, w: 8.2, h: 0.4, fontSize: 17, bold: true, color: C.text1, isTextBox: true, margin: 0 });
  s.addText(t, { x: 1.2, y: y + 0.4, w: 8.2, h: 0.4, fontSize: 14, color: C.text2, isTextBox: true, margin: 0 });
});

// ---------------------------------------------------------------- 4 solution
pres.addSection({ title: "Method" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Proposed solution: the RepoJudgeBench pipeline", { placeholder: "title" });
const steps = [
  ["Select", "real PRs created ≥ 2025-01-01 (SWE-bench-Live, SWE-rebench), each with a Docker image"],
  ["Apply", "gold patch inside the container, re-rendered with git diff"],
  ["Inject", "one AST mutation per defect class in the code the PR touches"],
  ["Admit", "keep a variant only if every gold-passing test still passes"],
  ["Retrieve", "neutral context from the parent commit: definitions and call sites"],
  ["Judge", "CodeJudgeBench pairwise prompt, both orders, bootstrap CIs"],
];
steps.forEach(([h, t], i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.5 + col * 3.05, y = 1.2 + row * 2.0;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.8, h: 1.75, fill: { color: i === 3 ? C.accent1 : C.background2 },
    line: { color: i === 3 ? C.accent1 : C.background2 }, rectRadius: 0.08, objectName: "step " + (i + 1) });
  s.addText((i + 1) + "  " + h, { x: x + 0.15, y: y + 0.12, w: 2.5, h: 0.45, fontSize: 18, bold: true,
    color: i === 3 ? C.background1 : C.text1, isTextBox: true, margin: 0 });
  s.addText(t, { x: x + 0.15, y: y + 0.6, w: 2.5, h: 1.05, fontSize: 13, color: i === 3 ? C.background1 : C.text2,
    isTextBox: true, margin: 0, valign: "top" });
});
s.addNotes("Step 4 is the key property: 'passes CI but is wrong' is guaranteed by construction.");

// ---------------------------------------------------------------- 5 contributions
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Technical contributions", { placeholder: "title" });
const contrib = [
  ["New evaluation axis", "judges on repository-level, CI-passing diffs instead of single functions"],
  ["CI-passing injection harness", `${Object.values(D.candidates_tested).reduce((a, b) => a + b, 0)} candidates tested in Docker; only test-passing ones admitted`],
  ["Defect taxonomy", "six review-grounded classes with executable AST operators"],
  ["Reliability analysis", "position bias, self-consistency, length bias, diff-size scaling"],
  ["Mitigation", "retrieved repository context with a budget ablation; thinking mode"],
  ["Released artefacts", "dataset, harness, prompts and every raw verdict log"],
];
contrib.forEach(([h, t], i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.5 + col * 3.05, y = 1.2 + row * 2.0;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.8, h: 1.75, fill: { color: C.background2 },
    line: { color: C.background2 }, rectRadius: 0.08, objectName: "contribution " + (i + 1) });
  numberCircle(s, x + 0.15, y + 0.15, i + 1, C.accent2);
  s.addText(h, { x: x + 0.7, y: y + 0.15, w: 2.0, h: 0.45, fontSize: 15, bold: true, color: C.text1, isTextBox: true, margin: 0, valign: "middle" });
  s.addText(t, { x: x + 0.15, y: y + 0.72, w: 2.5, h: 0.95, fontSize: 13, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
});

// ---------------------------------------------------------------- 6 dataset
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("RepoJudgeBench in numbers", { placeholder: "title" });
const cand = Object.values(D.candidates_tested).reduce((a, b) => a + b, 0);
const caught = Object.values(D.caught_by_tests).reduce((a, b) => a + b, 0);
stat(s, 0.5, 1.15, 2.6, String(D.pairs), `verified pairs from ${D.instances} PRs (2025)`, C.accent1, "pairs");
stat(s, 0.5, 2.55, 2.6, String(D.repos), "Python repositories", C.accent1, "repos");
stat(s, 0.5, 3.95, 2.6, pct(caught / cand), "of injected defects caught by the PRs' own tests", C.accent3, "caught");
const cls = [["Authorisation", "authorization_regression"], ["Error swallowing", "silent_error_swallowing"],
  ["Race / concurrency", "race_condition"], ["Resource leak", "resource_leak"]];
s.addChart(pres.charts.BAR, [{ name: "Caught by tests (%)", labels: cls.map(c => c[0]),
  values: cls.map(c => +(100 * (D.caught_by_tests[c[1]] || 0) / D.candidates_tested[c[1]]).toFixed(1)) }], Object.assign({
  x: 3.5, y: 1.15, w: 6.0, h: 4.0, barDir: "bar", chartColors: [HEX.accent3],
  showTitle: true, title: "Share of candidates caught by the PR's tests (%)", titleFontSize: 13, titleColor: HEX.dk1,
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.dk1,
  valAxisMinVal: 0, valAxisMaxVal: 100, valAxisLabelColor: HEX.accent4, catAxisLabelColor: HEX.dk1,
  catAxisLabelFontSize: 12, valAxisLabelFontSize: 10, valGridLine: { color: "DDE3E8", size: 0.5 },
  catGridLine: { style: "none" }, showLegend: false,
}, chartText));
s.addNotes(`Median gold patch: ${D.gold_changed_lines["50%"]} changed lines, ${D.gold_files["50%"]} files, ${D.gold_hunks["50%"]} hunks. ${D.pairs_judged} pairs judged (no leakage, prompt ≤ 6k tokens).`);

// ---------------------------------------------------------------- 7 protocol
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Judging protocol", { placeholder: "title" });
bullets(s, [
  "CodeJudgeBench pairwise prompt, verdict [[A>B]] or [[B>A]]",
  "Issue text as the user prompt, two unified diffs as the answers",
  "Forced verdict prefix: logits of A vs B give the verdict and p(A)",
  "Every pair judged in both orders; 95% bootstrap CIs over PRs",
  "Control: 45 CodeJudgeBench pairs (generation, repair, test generation)",
], { x: 0.5, y: 1.15, w: 4.6, h: 3.9, fontSize: 14 });
const jrows = [["Judge", "Size", "Type"],
  ["Qwen2.5-Coder-1.5B", "1.5B", "code"], ["Qwen2.5-Coder-3B", "3B", "code"],
  ["Qwen3-1.7B", "1.7B", "hybrid"], ["Qwen3-1.7B (thinking)", "1.7B", "thinking"],
  ["Qwen3-4B", "4B", "hybrid"], ["Llama-3.2-3B", "3B", "general"], ["Gemma-3-4B", "4B", "general"]];
s.addTable(jrows.map((r, i) => r.map(t => ({ text: t, options: { bold: i === 0, color: i === 0 ? C.background1 : C.text1,
  fill: { color: i === 0 ? C.accent6 : (i % 2 ? C.background2 : C.background1) } } }))),
  { x: 5.4, y: 1.2, w: 4.1, colW: [2.2, 0.8, 1.1], fontSize: 12, rowH: 0.4, border: { type: "none" } });
s.addText("All open-weight, run locally with llama.cpp on CPU (no GPU, no API).", { x: 5.4, y: 4.55, w: 4.1, h: 0.5,
  fontSize: 11, italic: true, color: C.accent4, isTextBox: true, margin: 0 });

// ---------------------------------------------------------------- 8 result 1
pres.addSection({ title: "Results" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 1: raw accuracy is at chance in both regimes", { placeholder: "title" });
const mlabels = M.map(m => NICE[m]);
s.addChart(pres.charts.BAR, [
  { name: "CodeJudgeBench (single-file)", labels: mlabels, values: M.map(m => +(100 * S.by_model[m].cjb_control.acc).toFixed(1)) },
  { name: "RepoJudgeBench (repository-level)", labels: mlabels, values: M.map(m => +(100 * S.by_model[m].diff_only.acc).toFixed(1)) },
], Object.assign({
  x: 0.5, y: 1.1, w: 6.4, h: 4.1, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent6, HEX.accent2],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9, dataLabelColor: HEX.dk1, dataLabelFormatCode: "0.0",
  valAxisMinVal: 0, valAxisMaxVal: 80, valAxisLabelColor: HEX.accent4, catAxisLabelColor: HEX.dk1,
  catAxisLabelFontSize: 9, valAxisLabelFontSize: 10, valGridLine: { color: "DDE3E8", size: 0.5 }, catGridLine: { style: "none" },
  showLegend: true, legendPos: "t", legendFontSize: 11, showTitle: true, title: "Pairwise accuracy (%)", titleFontSize: 13, titleColor: HEX.dk1,
}, chartText));
const rj = M.filter(m => !m.endsWith("think")).map(m => S.by_model[m].diff_only.acc);
const cj = M.filter(m => !m.endsWith("think")).map(m => S.by_model[m].cjb_control.acc);
s.addText([
  { text: "Random baseline: 50%", options: { bold: true, breakLine: true } },
  { text: `Control: ${pct(Math.min(...cj))}–${pct(Math.max(...cj))}`, options: { breakLine: true } },
  { text: `RepoJudgeBench: ${pct(Math.min(...rj))}–${pct(Math.max(...rj))}`, options: { breakLine: true } },
  { text: " ", options: { breakLine: true } },
  { text: "Execution oracle (the PR's tests): 0% by construction.", options: {} },
], { x: 7.1, y: 1.4, w: 2.4, h: 3.6, fontSize: 14, color: C.text1, isTextBox: true, valign: "top", margin: 0 });

// ---------------------------------------------------------------- 9 result 2
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 2: position bias and length bias", { placeholder: "title" });
const lb = S.length_bias;
stat(s, 0.5, 1.15, 3.0, "71–100%", "flip rate: the verdict follows the slot, not the patch", C.accent3, "flip");
stat(s, 0.5, 2.55, 3.0, pct(S.length_relation_counts.variant_longer / (S.length_relation_counts.variant_longer + S.length_relation_counts.same_length + S.length_relation_counts.variant_shorter)),
  "of judged pairs: the defective variant's diff is longer", C.accent2, "longer");
stat(s, 0.5, 3.95, 3.0, pct(S.length_heuristic.acc), "a trivial 'pick the shorter patch' rule (benchmark artefact)", C.accent4, "heuristic");
const calM = M.slice().reverse();
s.addChart(pres.charts.BAR, [{ name: "Calibrated accuracy on RepoJudgeBench (%)", labels: calM.map(m => NICE[m]),
  values: calM.map(m => +(100 * S.by_model[m].diff_only.acc_calibrated).toFixed(1)) }], Object.assign({
  x: 3.8, y: 1.1, w: 5.7, h: 4.1, barDir: "bar", chartColors: [HEX.accent1],
  showTitle: true, title: "After balanced position calibration (%), 50 = chance", titleFontSize: 13, titleColor: HEX.dk1,
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: HEX.dk1, dataLabelFormatCode: "0.0",
  valAxisMinVal: 0, valAxisMaxVal: 100, valAxisLabelColor: HEX.accent4, catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 10,
  valAxisLabelFontSize: 10, valGridLine: { color: "DDE3E8", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false,
}, chartText));
s.addNotes("Small judges prefer the longer patch in 77-87% of unequal-length pairs; the 4B judges in about 41%. Qwen3-4B 66.7% [54, 79] and Gemma-3-4B 59.1% [49, 68] after calibration.");

// ---------------------------------------------------------------- 10 result 3
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 3: diff size and defect class", { placeholder: "title" });
s.addChart(pres.charts.LINE, [
  { name: "Mean of judges (raw)", labels: BINS.labels.map((l, i) => `${l} (n=${BINS.n[i]})`), values: BINS.raw.map(v => +(100 * v).toFixed(1)) },
  { name: "Mean of judges (calibrated)", labels: BINS.labels.map((l, i) => `${l} (n=${BINS.n[i]})`), values: BINS.cal.map(v => +(100 * v).toFixed(1)) },
], Object.assign({
  x: 0.5, y: 1.1, w: 5.0, h: 4.1, chartColors: [HEX.accent6, HEX.accent2], lineSize: 2, lineDataSymbolSize: 6,
  showTitle: true, title: "Accuracy (%) by changed lines in the gold patch", titleFontSize: 12, titleColor: HEX.dk1,
  valAxisMinVal: 0, valAxisMaxVal: 100, valAxisLabelColor: HEX.accent4, catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 9,
  valAxisLabelFontSize: 10, valGridLine: { color: "DDE3E8", size: 0.5 }, catGridLine: { style: "none" },
  showLegend: true, legendPos: "b", legendFontSize: 10,
}, chartText));
const allc = S.by_class.all_judges;
const crow = [["Defect class (judged pairs)", "Calibrated acc."]];
[["Authorisation", "authorization_regression"], ["Resource leak", "resource_leak"], ["Error swallowing", "silent_error_swallowing"],
 ["Race / concurrency", "race_condition"]].forEach(([n, k]) => {
  crow.push([`${n} (${D.by_class_judged[k] || 0})`, `${pct(allc[k].acc_calibrated)} [${Math.round(100 * allc[k].acc_calibrated_ci[0])}, ${Math.round(100 * allc[k].acc_calibrated_ci[1])}]`]);
});
s.addTable(crow.map((r, i) => r.map(t => ({ text: t, options: { bold: i === 0, color: i === 0 ? C.background1 : C.text1,
  fill: { color: i === 0 ? C.accent6 : (i % 2 ? C.background2 : C.background1) } } }))),
  { x: 5.8, y: 1.2, w: 3.7, colW: [2.15, 1.55], fontSize: 12, rowH: 0.42, border: { type: "none" } });
const sc = S.scaling.pooled;
s.addText(`No measurable effect of diff size, files or hunks (all 95% CIs include 0). Authorisation guards are missed most often.`,
  { x: 5.8, y: 3.55, w: 3.7, h: 1.4, fontSize: 13, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
s.addNotes(`Pooled logistic regression on ${sc.n_obs} presentations; log2(lines) beta=${sc.coef.log2_lines.b.toFixed(3)}, p=${sc.coef.log2_lines.p.toFixed(3)}.`);

// ---------------------------------------------------------------- 11 result 4
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Result 4: baselines and mitigation", { placeholder: "title" });
const bestRaw = Math.max(...rj), bestCal = Math.max(...M.filter(m => !m.endsWith("think")).map(m => S.by_model[m].diff_only.acc_calibrated));
const base = [["Execution oracle (PR tests)", 0], ["Random", 0.5], ["Best judge, raw", bestRaw], ["Best judge, calibrated", bestCal],
  ["Static analysis (8 targeted rules)", S.static.relevant.acc], ["Shorter-patch heuristic", S.length_heuristic.acc]];
s.addChart(pres.charts.BAR, [{ name: "Accuracy on RepoJudgeBench (%)", labels: base.map(b => b[0]), values: base.map(b => +(100 * b[1]).toFixed(1)) }],
  Object.assign({ x: 0.5, y: 1.1, w: 5.6, h: 4.1, barDir: "bar", chartColors: [HEX.accent6],
    showTitle: true, title: "Accuracy on RepoJudgeBench (%)", titleFontSize: 13, titleColor: HEX.dk1,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: HEX.dk1, dataLabelFormatCode: "0.0",
    valAxisMinVal: 0, valAxisMaxVal: 100, valAxisLabelColor: HEX.accent4, catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 10,
    valAxisLabelFontSize: 10, valGridLine: { color: "DDE3E8", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false }, chartText));
const cg = S.context_gain["qwen3-1.7b"];
s.addText("Mitigation (Qwen3-1.7B, calibrated)", { x: 6.4, y: 1.2, w: 3.1, h: 0.4, fontSize: 15, bold: true, color: C.text1, isTextBox: true, margin: 0 });
stat(s, 6.4, 1.7, 3.1, "+" + (100 * cg.ctx_retrieved_6000.calibrated.diff).toFixed(1) + " pts", "with retrieved repository context (6k characters)", C.accent1, "ctx");
stat(s, 6.4, 3.1, 3.1, "+" + (100 * cg.think.calibrated.diff).toFixed(1) + " pts", "with thinking mode (512 tokens)", C.accent1, "think");
s.addText("Both still leave the judge at or below chance.", { x: 6.4, y: 4.5, w: 3.1, h: 0.5, fontSize: 12, italic: true,
  color: C.accent4, isTextBox: true, margin: 0 });

// ---------------------------------------------------------------- 12 findings
pres.addSection({ title: "Conclusion" });
s = pres.addSlide({ masterName: "DARK_CONTENT", sectionTitle: "Conclusion" });
s.addText("Key findings", { placeholder: "title" });
const smallCal = ["qwen2.5-coder-1.5b", "qwen2.5-coder-3b", "qwen3-1.7b"].map(m => S.by_model[m].diff_only.acc_calibrated);
const finds = [
  `The PRs' own tests catch only ${pct(caught / cand)} of review-relevant injected defects`,
  "Small open judges are at chance; their verdicts follow the presentation slot",
  `After calibration the smallest judges prefer the defective, longer patch (${pct(Math.min(...smallCal))}–${pct(Math.max(...smallCal))})`,
  `Only the 4B judges keep a weak correct signal (up to ${pct(bestCal)})`,
  `Targeted static analysis (${pct(S.static.relevant.acc)}) beats every judge's raw accuracy`,
  "Our benchmark has a length artefact: future versions must length-match variants",
];
finds.forEach((t, i) => {
  const y = 1.15 + i * 0.68;
  numberCircle(s, 0.6, y, i + 1, C.accent2);
  s.addText(t, { x: 1.2, y: y - 0.02, w: 8.3, h: 0.46, fontSize: 15, color: C.background1, isTextBox: true, margin: 0, valign: "middle" });
});

// ---------------------------------------------------------------- 13 limitations
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Conclusion" });
s.addText("Limitations and deviations from the proposal", { placeholder: "title" });
const lim = [
  ["Scale", `${D.pairs} pairs from ${D.repos} repositories (proposal: ≥300 pairs) — every task needs a multi-GB image and a test run`],
  ["Judges", "only small open models (1.5–4B) on CPU; no closed models (no API access)"],
  ["Test oracle", "PR test files instead of full suites; no per-instance witness tests"],
  ["Validation", "no human annotation yet — sheet and Cohen's kappa script released"],
  ["Classes", "N+1 and unsafe-migration sites are rare in issue-resolution PRs"],
];
lim.forEach(([h, t], i) => {
  const y = 1.15 + i * 0.8;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 1.8, h: 0.6, fill: { color: C.background2 }, line: { color: C.background2 }, rectRadius: 0.06 });
  s.addText(h, { x: 0.5, y, w: 1.8, h: 0.6, fontSize: 14, bold: true, color: C.text1, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  s.addText(t, { x: 2.55, y, w: 6.95, h: 0.6, fontSize: 14, color: C.text2, valign: "middle", isTextBox: true, margin: 0 });
});

// ---------------------------------------------------------------- 14 demo
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Conclusion" });
s.addText("Demonstration and reproducibility", { placeholder: "title" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 1.2, w: 9.0, h: 1.0, fill: { color: C.text1 }, line: { color: C.text1 }, rectRadius: 0.06 });
s.addText("python scripts/demo.py --model models/qwen2.5-coder-1.5b-instruct-q8_0.gguf", { x: 0.7, y: 1.2, w: 8.6, h: 1.0,
  fontSize: 12, fontFace: "Courier New", color: C.background1, valign: "middle", isTextBox: true, margin: 0 });
bullets(s, [
  "Prints one pair: the issue, the injected defect and the lines where the variant differs",
  "Shows how many tests both patches pass",
  "Runs a local judge in both orders and prints the verdict probabilities",
  "bash scripts/finalize.sh rebuilds every table, figure and PDF from the raw verdict logs",
], { x: 0.5, y: 2.5, w: 9.0, h: 2.2, fontSize: 14 });
s.addText("Code, data and logs: github.com/the-mgi/nlp-project-", { x: 0.5, y: 4.75, w: 9.0, h: 0.4, fontSize: 12,
  color: C.accent1, isTextBox: true, margin: 0 });

pres.writeFile({ fileName: OUT }).then(async () => {
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
});
