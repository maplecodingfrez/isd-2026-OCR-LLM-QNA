// ปุ่ม "คัดลอกคำตอบ" ต้องได้ข้อความล้วน: คำตอบ + หน้าอ้างอิง (ไม่มี JSON/SQL/ชื่อฟิลด์) — อาจารย์ให้ copy คำตอบทีละข้อลงไฟล์ text
const test = require("node:test");
const assert = require("node:assert");

const app = require("../../lab10_fastapi/curriculum_app/static/app.js");

test("answer + citation text, blank line between", () => {
  const out = app.buildCopyText({ answer: "ปี 1 เรียนรวม 39 หน่วยกิต", citation_text: "อ้างอิงเล่มหลักสูตร:\n• หน้า 33 (PDF 38)" });
  assert.strictEqual(out, "ปี 1 เรียนรวม 39 หน่วยกิต\n\nอ้างอิงเล่มหลักสูตร:\n• หน้า 33 (PDF 38)");
});

test("no citation: answer only, no trailing blank lines", () => {
  assert.strictEqual(app.buildCopyText({ answer: "หน่วยกิตรวมตลอดหลักสูตร 132 หน่วยกิต", citation_text: "" }), "หน่วยกิตรวมตลอดหลักสูตร 132 หน่วยกิต");
  assert.strictEqual(app.buildCopyText({ answer: " 3 หน่วยกิต \n", citation_text: "   " }), "3 หน่วยกิต");
});

test("works on the copy payload built by buildCopyPayload", () => {
  const payload = app.buildCopyPayload("ปี 1 รวมกี่หน่วยกิต", "dsba_coop", { answer: "ปี 1 เรียนรวม 39 หน่วยกิต", citation_text: "อ้างอิงเล่มหลักสูตร:\n• หน้า 1 (PDF 5)" }, 1.234);
  const out = app.buildCopyText(payload);
  assert.ok(out.startsWith("ปี 1 เรียนรวม 39 หน่วยกิต"));
  assert.ok(out.endsWith("• หน้า 1 (PDF 5)"));
  for (const bad of ["{", "}", '"answer"', "elapsed_seconds", "dsba_coop", "ปี 1 รวมกี่หน่วยกิต"]) assert.ok(!out.includes(bad), bad);
});

test("empty answer falls back to the page's own no-answer text, never undefined", () => {
  const out = app.buildCopyText({});
  assert.ok(typeof out === "string" && out.length > 0 && !out.includes("undefined"));
});
