// วัน Challenge: ข้อที่เล่มไม่มีคำตอบ ระบบตอบ "ไม่พบข้อมูลนี้ในเล่มหลักสูตร" ผู้ใช้ต้อง copy คำตอบนี้ลงไฟล์ text ได้เหมือนข้ออื่น
// (เดิมหน้าเว็บซ่อนแถวปุ่ม copy ทั้งแถวเมื่อ "ไม่พบ") — ปุ่มข้อความต้องมีเสมอ ส่วนปุ่ม JSON ซ่อนเมื่อไม่มีคำตอบจริง
const test = require("node:test");
const assert = require("node:assert");
const app = require("../../lab10_fastapi/curriculum_app/static/app.js");

const NOT_FOUND = { answer: "ไม่พบข้อมูลนี้ในเล่มหลักสูตร", rows: [], citation_text: "" };

test("text copy button is available for not-found answers, JSON button is not", () => {
  assert.deepStrictEqual(app.copyButtonsVisible(NOT_FOUND), { text: true, json: false });
  assert.deepStrictEqual(app.copyButtonsVisible({ answer: "ไม่พบข้อมูลนี้ในเล่มหลักสูตร: แผนนี้มีปี 1–4 เท่านั้น (ไม่มีปี 5)", rows: [] }), { text: true, json: false });
});

test("normal and ask-back answers keep both buttons", () => {
  assert.deepStrictEqual(app.copyButtonsVisible({ answer: "ปี 1 เรียนรวม 39 หน่วยกิต", rows: [{ year: 1, credits: 39 }] }), { text: true, json: true });
  assert.deepStrictEqual(app.copyButtonsVisible({ answer: "คำถามยังไม่ชัดเจน: ต้องการทราบหน่วยกิตของอะไร", rows: [] }), { text: true, json: true });
});

test("a rule answer with no rows that is a real answer keeps both buttons", () => {
  assert.deepStrictEqual(app.copyButtonsVisible({ answer: "แผนนี้มีแผนเดียว", rows: [] }), { text: true, json: true });
});

test("copied text of a not-found answer is the answer itself", () => {
  const payload = app.buildCopyPayload("ค่าเทอมเท่าไหร่", "dsba_coop", NOT_FOUND, 0.5);
  assert.strictEqual(app.buildCopyText(payload), "ไม่พบข้อมูลนี้ในเล่มหลักสูตร");
});

test("empty/undefined response shows no JSON button but still the text button", () => {
  assert.deepStrictEqual(app.copyButtonsVisible(undefined), { text: true, json: false });
});
