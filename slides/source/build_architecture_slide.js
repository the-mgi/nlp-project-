// One editable slide: AWS architecture of the distributed RepoJudgeBench experiment.
//   NODE_PATH=<dir with pptxgenjs> SKILL_DIR=<pptx skill dir> node slides/source/build_architecture_slide.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(path.join(process.env.SKILL_DIR, "scripts/apply_theme.js"));

const OUT = path.resolve(__dirname, "../RepoJudgeBench_architecture_slide.pptx");
const FONT = "Times New Roman";
const THEME = {
  name: "RepoJudgeBench Bright", headFontFace: FONT, bodyFontFace: FONT,
  colors: { dk1: "1A237E", lt1: "FFFFFF", dk2: "6200EA", lt2: "E3F2FD", accent1: "2962FF", accent2: "E91E63",
    accent3: "FF6D00", accent4: "00C853", accent5: "AA00FF", accent6: "00B8D4", hlink: "2962FF", folHlink: "AA00FF" },
};
const TINT = { blue: "E3F2FD", pink: "FCE4EC", orange: "FFF3E0", green: "E8F5E9", purple: "F3E5F5", cyan: "E0F7FA", yellow: "FFFDE7" };

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = "Muhammad Usama; Ali Raza";
pres.title = "RepoJudgeBench distributed architecture";
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "CONTENT", background: { color: C.background1 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.3, y: 0.12, w: 9.4, h: 0.55, fontSize: 24, bold: true,
    color: C.accent1, align: "left", valign: "middle", fontFace: FONT }, text: "" } }],
});
const T = (o) => Object.assign({ fontFace: FONT, isTextBox: true, margin: 0 }, o);
const box = (s, x, y, w, h, fill, line, name, dash) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h,
  fill: { color: fill }, line: { color: line, width: 1.5, dashType: dash || "solid" }, rectRadius: 0.06, objectName: name });
const arrow = (s, x, y, w, h, color, name, opts = {}) => s.addShape(pres.shapes.LINE, Object.assign({ x, y, w, h,
  line: { color, width: 2.25, endArrowType: "triangle", beginArrowType: opts.both ? "triangle" : undefined }, objectName: name },
  opts.flipV ? { flipV: true } : {}));

const s = pres.addSlide({ masterName: "CONTENT" });
s.addText("Distributed architecture on AWS: 1 master + 5 workers", { placeholder: "title" });

// ---- external actors -----------------------------------------------------------
box(s, 0.3, 0.78, 2.55, 0.66, TINT.yellow, "FFC400", "operator");
s.addText([{ text: "Operator laptop", options: { bold: true, color: C.accent3, breakLine: true } },
  { text: "terraform apply / destroy, run_experiment.sh", options: { fontSize: 10 } }],
  T({ x: 0.4, y: 0.8, w: 2.35, h: 0.62, fontSize: 12, color: C.text1, valign: "middle" }));
box(s, 3.6, 0.78, 3.3, 0.66, TINT.cyan, C.accent6, "internet");
s.addText([{ text: "Internet services", options: { bold: true, color: C.accent6, breakLine: true } },
  { text: "Hugging Face (models, datasets) · Docker mirror (task images) · PyPI · GitHub", options: { fontSize: 10 } }],
  T({ x: 3.7, y: 0.8, w: 3.1, h: 0.62, fontSize: 12, color: C.text1, valign: "middle" }));

// ---- VPC ------------------------------------------------------------------------
box(s, 0.3, 1.72, 6.6, 3.78, "FFFFFF", C.accent5, "vpc", "dash");
s.addText("AWS VPC 10.42.0.0/16 (single AZ)", T({ x: 3.0, y: 1.76, w: 3.5, h: 0.26, fontSize: 11, bold: true, color: C.accent5 }));

// public subnet
box(s, 0.45, 2.05, 6.3, 1.2, TINT.blue, C.accent1, "public subnet");
s.addText("Public subnet 10.42.1.0/24", T({ x: 0.55, y: 2.08, w: 2.5, h: 0.24, fontSize: 10, bold: true, color: C.accent1 }));
box(s, 0.6, 2.34, 3.35, 0.85, "FFFFFF", C.accent1, "master");
s.addText([{ text: "MASTER  m7i.xlarge", options: { bold: true, color: C.accent1, breakLine: true } },
  { text: "orchestrate.sh · make_items · static baseline (Ruff/Bandit) · analysis · LaTeX", options: { fontSize: 10 } }],
  T({ x: 0.7, y: 2.36, w: 3.2, h: 0.8, fontSize: 12, color: C.text1, valign: "middle" }));
box(s, 4.85, 2.4, 1.75, 0.72, "FFFFFF", C.accent6, "nat");
s.addText([{ text: "NAT gateway", options: { bold: true, color: C.accent6, breakLine: true } },
  { text: "worker egress only", options: { fontSize: 10 } }], T({ x: 4.92, y: 2.42, w: 1.62, h: 0.68, fontSize: 12, color: C.text1, align: "center", valign: "middle" }));

// private subnet
box(s, 0.45, 3.5, 6.3, 1.88, TINT.pink, C.accent2, "private subnet");
s.addText("Private subnet 10.42.2.0/24 (no public IPs)", T({ x: 2.5, y: 3.53, w: 3.4, h: 0.24, fontSize: 10, bold: true, color: C.accent2 }));
const workers = [["W0", "Coder-1.5B", "+ context, point-wise", C.accent1], ["W1", "Coder-3B", "", C.accent3],
  ["W2", "Qwen3-1.7B", "+ thinking, context", C.accent4], ["W3", "Qwen3-4B", "", C.accent5], ["W4", "Llama-3B", "+ Gemma-4B", C.accent2]];
workers.forEach(([id, m, extra, col], i) => {
  const x = 0.58 + i * 1.235;
  box(s, x, 3.82, 1.14, 1.48, "FFFFFF", col, "worker " + id);
  s.addText([{ text: `${id} c7i.4xlarge`, options: { bold: true, color: col, fontSize: 10, breakLine: true } },
    { text: `build shard ${i}/5`, options: { fontSize: 10, breakLine: true } },
    { text: m, options: { bold: true, fontSize: 10, breakLine: true } },
    { text: extra || " ", options: { fontSize: 9 } }],
    T({ x: x + 0.05, y: 3.86, w: 1.04, h: 1.4, fontSize: 10, color: C.text1, align: "center", valign: "middle" }));
});

// ---- communication arrows ----------------------------------------------------------
arrow(s, 2.6, 1.44, 0, 0.9, C.accent3, "ssh operator to master");                       // operator -> master
s.addText("SSH :22 (your IP only)", T({ x: 0.75, y: 1.47, w: 1.7, h: 0.22, fontSize: 9, italic: true, color: C.accent3 }));
arrow(s, 2.25, 3.19, 0, 0.63, C.accent5, "master workers ssh", { both: true });             // master <-> workers
s.addText("SSH + rsync over private IPs: jobs, items ↓  shards, verdicts ↑", T({ x: 2.33, y: 3.22, w: 3.5, h: 0.24, fontSize: 9, italic: true, color: C.accent5 }));
arrow(s, 5.72, 3.12, 0, 0.7, C.accent6, "workers to nat", { flipV: true });                // workers -> NAT (up)
arrow(s, 5.72, 1.44, 0, 0.96, C.accent6, "nat to internet", { flipV: true });              // NAT -> internet (up)
s.addText("HTTPS egress", T({ x: 5.8, y: 1.78, w: 1.0, h: 0.22, fontSize: 9, italic: true, color: C.accent6 }));

// ---- right panel: tools + phases ------------------------------------------------------
box(s, 7.1, 0.78, 2.6, 2.05, TINT.green, C.accent4, "tools");
s.addText([
  { text: "Tools on every node", options: { bold: true, color: C.accent4, fontSize: 12, breakLine: true } },
  { text: "Ubuntu 24.04 · Docker · Python venv", options: { breakLine: true } },
  { text: "llama.cpp (llama-cpp-python, AMX)", options: { breakLine: true } },
  { text: "GGUF judges from Hugging Face", options: { breakLine: true } },
  { text: "Master adds: TeX Live, statsmodels, Ruff, Bandit", options: { breakLine: true } },
  { text: "Provisioned by Terraform + cloud-init", options: {} },
], T({ x: 7.2, y: 0.82, w: 2.42, h: 1.98, fontSize: 10, color: C.text1, valign: "top" }));
box(s, 7.1, 2.98, 2.6, 2.52, TINT.orange, C.accent3, "phases");
s.addText([
  { text: "Execution phases", options: { bold: true, color: C.accent3, fontSize: 12, breakLine: true } },
  { text: "1  Build: each worker builds 1/5 of the PRs in Docker, injects defects, runs tests", options: { breakLine: true } },
  { text: "2  Merge: master collects shards, builds judge items + static baseline, pushes items", options: { breakLine: true } },
  { text: "3  Judge: each worker runs its judge models (both orders)", options: { breakLine: true } },
  { text: "4  Collect: verdicts → master → analysis, paper, slides, results.tgz", options: {} },
], T({ x: 7.2, y: 3.02, w: 2.42, h: 2.44, fontSize: 10, color: C.text1, valign: "top", paraSpaceAfter: 3 }));

s.addNotes("Terraform creates the VPC, subnets, NAT gateway, security groups and six EC2 instances; cloud-init installs the tools. " +
  "The operator only reaches the master. The master drives the workers over SSH/rsync on private IPs; workers reach the internet only through the NAT gateway. " +
  "Code: infra/terraform, infra/scripts/orchestrate.sh, infra/run_experiment.sh.");

pres.writeFile({ fileName: OUT }).then(async () => {
  await applyTheme(OUT, THEME);
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
