// Regression guard for the answer renderers in lab10_fastapi/curriculum_app/static/app.js.
// The page parses the backend's answer *text*; if the backend wording drifts, a structured card silently
// falls back to plain paragraphs. Run:  node --test tests/js
//   LIVE_API=http://127.0.0.1:8000 node --test tests/js   (also checks the live backend wording)
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const app = require("../../lab10_fastapi/curriculum_app/static/app.js");
const FIX = path.join(__dirname, "fixtures");

function blocksOf(data) {
  return app.groupCreditBlocks(app.groupCourseBlocks(app.groupGeBlocks(app.groupPlanBlocks(app.answerBlocks(data)))));
}
const types = (blocks) => blocks.map((b) => b.type);
const fixture = (name) => JSON.parse(fs.readFileSync(path.join(FIX, name + ".json"), "utf8"));

async function load(name) {
  if (process.env.LIVE_API) {
    const f = fixture(name);
    const res = await fetch(process.env.LIVE_API + "/api/ask", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: f.question, program: f.program || "dsba_coop" }),
    });
    return res.json();
  }
  return fixture(name);
}

test("GE electives -> one ge block per term with examples and required-in-plan rows", async () => {
  const b = blocksOf(await load("ge"));
  assert.deepStrictEqual(types(b), ["ge", "ge"]);
  for (const block of b) {
    assert.ok(block.total > 100, "total courses parsed");
    assert.strictEqual(block.groups.length, 3);
    assert.ok(block.groups.every((g) => g.n), "each group has a count");
    assert.ok(block.examples.length >= 5 && block.examples.every((e) => e.kind === "course" && e.credits));
    assert.ok(block.mandatory.length >= 3 && block.mandatory.every((c) => /^\d{8}$/.test(c.code)));
  }
});

test("search list -> course rows tagged in plan / elective, no leftover plain list", async () => {
  const b = blocksOf(await load("search"));
  assert.deepStrictEqual(types(b), ["paragraph", "courses"]);
  const tags = new Set(b[1].entries.map((e) => e.tag));
  assert.ok(b[1].entries.length >= 8 && tags.size >= 2, "both tags present");
});

test("hours list -> course rows (hours parenthetical dropped, hours kept as l-p-s)", async () => {
  const b = blocksOf(await load("hours"));
  assert.deepStrictEqual(types(b), ["paragraph", "courses"]);
  assert.ok(b[1].entries.every((e) => Array.isArray(e.hours)));
});

test("term comparison -> plans block with two plans, slots and notes", async () => {
  const b = blocksOf(await load("compare"));
  assert.deepStrictEqual(types(b), ["plans"]);
  assert.strictEqual(b[0].plans.length, 2);
  assert.strictEqual(b[0].term, "ปี 4 เทอม 1");
  for (const p of b[0].plans) {
    assert.ok(p.entries.some((e) => e.kind === "course" && e.tag), "required course keeps its tag");
    assert.ok(p.entries.some((e) => e.kind === "slot"), "elective slots kept");
  }
  assert.strictEqual(b[0].notes.length, 2);
});

test("free-elective answer -> slot rows with sub line and credits", async () => {
  const b = blocksOf(await load("free"));
  assert.deepStrictEqual(types(b), ["courses"]);
  assert.ok(b[0].entries.length >= 2 && b[0].entries.every((e) => e.kind === "slot" && e.credits && e.sub));
});

test("parseCourseLine keeps working for the older shapes", () => {
  const c = app.parseCourseLine("06026200 แคลคูลัส 1 / CALCULUS 1 — 3 (3-0-6) หน่วยกิต");
  assert.strictEqual(c.code, "06026200");
  assert.deepStrictEqual(c.hours, ["3", "0", "6"]);
  assert.strictEqual(c.tag, null);
  assert.strictEqual(app.parseCourseLine("ประโยคทั่วไปที่ไม่ใช่วิชา"), null);
});

test("book-section answers are routed by answer_type, not by text parsing", () => {
  const f = fixture("career");
  assert.strictEqual(f.answer_type, "ocr");
  assert.ok(f.rows[0].body && /\d\)/.test(f.rows[0].body), "numbered items present in the OCR body");
});

test("BIT open GE slots (no fixed course list) -> slot rows, not plain paragraphs", async () => {
  const b = blocksOf(await load("bit_ge"));
  assert.deepStrictEqual(types(b), ["courses"]);
  assert.ok(b[0].entries.length === 2 && b[0].entries.every((e) => e.kind === "slot" && e.credits === "3" && e.sub));
});

test("search rows without credits keep their (in the book) tag", async () => {
  const b = blocksOf(await load("bit_search"));
  assert.deepStrictEqual(types(b), ["paragraph", "courses"]);
  assert.ok(b[1].entries.some((e) => e.credits === null && e.tag), "credit-less row parsed with a tag");
  assert.ok(b[1].entries.every((e) => e.kind === "course"));
});

test("no-coop plan comparison -> lead + course rows instead of 4 plain paragraphs", async () => {
  const b = blocksOf(await load("nocoop_compare"));
  assert.ok(b.some((x) => x.type === "courses" && x.entries.length >= 2), "only-in-coop courses become rows");
  assert.ok(b.filter((x) => x.type === "paragraph").length <= 3);
});

test("'free elective sits in year/term' answer -> slot rows with the term as sub line", async () => {
  const b = blocksOf(await load("free_when"));
  assert.deepStrictEqual(types(b), ["courses"]);
  assert.ok(b[0].entries.length === 2 && b[0].entries.every((e) => e.kind === "slot" && /^ปี \d+ เทอม \d+$/.test(e.sub)));
});

test("model-written summaries of course rows are rebuilt from data.rows (no raw '3 2 name EN 3;' dump)", async () => {
  for (const name of ["hybrid_rows", "hybrid_data"]) {
    const f = await load(name);
    const entries = app.modelRowEntries(f);
    assert.ok(entries && entries.length >= 2, name + ": rows turned into course entries");
    assert.ok(entries.every((e) => e.kind === "course" && e.name), name + ": every row has a name");
  }
  // rule / database answers are already formatted: never replaced
  assert.strictEqual(app.modelRowEntries({ answer_type: "database", rows: [{ name_th: "ก" }, { name_th: "ข" }] }), null);
  assert.strictEqual(app.modelRowEntries({ answer_type: "hybrid", rows: [{ name_th: "ก" }] }), null);
});

test("withdraw sample codes come from the plan's own withdraw examples (courses that actually have follow-ups)", () => {
  const topics = [
    { key: "prereq", examples: [{ q: { th: "วิชาที่ต้องผ่าน 06066300 ก่อนมีอะไรบ้าง" } }] },
    { key: "withdraw", examples: [
      { q: { th: "ถ้าถอนวิชา 06066300 จะกระทบกับอะไร" } },
      { q: { th: "ถ้าถอนวิชา 06026200 จะกระทบกับอะไร" } },
      { q: { th: "วิชา 06066300 มีวิชาต่อไหม" } },       // duplicate code
    ] },
  ];
  assert.deepStrictEqual(app.withdrawSampleCodes(topics), ["06066300", "06026200"]);
  assert.deepStrictEqual(app.withdrawSampleCodes([]), []);
  assert.deepStrictEqual(app.withdrawSampleCodes(null), []);
  assert.deepStrictEqual(app.withdrawSampleCodes([{ key: "withdraw", examples: [{ q: { th: "ไม่มีรหัส" } }] }]), []);
});
