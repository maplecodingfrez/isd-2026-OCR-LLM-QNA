// ข้อความ "ไม่พบข้อมูลนี้ในเล่มหลักสูตร" ต้องแสดงตามภาษาที่เลือก (EN เคยยังเป็นไทยกลางหน้าจอ EN)
// แสดงผลเท่านั้น: ข้อมูลที่ใช้คัดลอก/JSON ยังเป็นข้อความจากเซิร์ฟเวอร์เหมือนเดิม
const test = require("node:test");
const assert = require("node:assert");
const i18n = require("../../lab10_fastapi/curriculum_app/static/i18n.js");
const app = require("../../lab10_fastapi/curriculum_app/static/app.js");

const NOT_FOUND = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร";

test("English mode shows the not-found sentence in English", () => {
  i18n.setLang("en");
  try {
    const shown = app.displayAnswerData({ question: "q", answer: NOT_FOUND, rows: [] });
    assert.strictEqual(shown.answer, "Not found in the curriculum book");
  } finally { i18n.setLang("th"); }
});

test("Thai mode keeps the original sentence", () => {
  i18n.setLang("th");
  const data = { question: "q", answer: NOT_FOUND, rows: [] };
  assert.strictEqual(app.displayAnswerData(data).answer, NOT_FOUND);
});

test("only the exact not-found sentence is translated; real answers and reasons are untouched", () => {
  i18n.setLang("en");
  try {
    for (const answer of ["06026200 แคลคูลัส 1 — 3 หน่วยกิต", NOT_FOUND + ": นี่ไม่ใช่คำถามเกี่ยวกับหลักสูตร"]) {
      assert.strictEqual(app.displayAnswerData({ answer: answer, rows: [] }).answer, answer);
    }
    assert.strictEqual(app.displayAnswerData(undefined), undefined);
  } finally { i18n.setLang("th"); }
});

test("original data is never mutated (copy buttons keep the server text)", () => {
  i18n.setLang("en");
  try {
    const data = { answer: NOT_FOUND, rows: [] };
    app.displayAnswerData(data);
    assert.strictEqual(data.answer, NOT_FOUND);
    assert.strictEqual(app.buildCopyText(data), NOT_FOUND);
  } finally { i18n.setLang("th"); }
});
