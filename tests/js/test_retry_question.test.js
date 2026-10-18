// คำตอบ "คุณหมายถึง ... หรือไม่" มีปุ่ม "ใช่ ถามใหม่": แทนชื่อที่พิมพ์ผิดในคำถามเดิมด้วยรหัสวิชาที่ระบบแนะนำ
const test = require("node:test");
const assert = require("node:assert");

const app = require("../../lab10_fastapi/curriculum_app/static/app.js");

const near = (typed, code) => ({ answer: "ไม่พบข้อมูลนี้ในเล่มหลักสูตร: ...", rows: [{ code: code, name_th: "x", near_match: true, typed: typed }] });

test("replaces the typed name with the suggested code", () => {
  assert.strictEqual(app.retryQuestion("วิชาแคลคุลัส 2 กี่หน่วยกิต", near("แคลคุลัส 2", "06026201")), "วิชา 06026201 กี่หน่วยกิต");
  assert.strictEqual(app.retryQuestion("ถ้าไม่ผ่านวิชาโครงสร้างข้อมูล จะกระทบอะไร", near("โครงสร้างข้อมูล", "06066301")), "ถ้าไม่ผ่านวิชา 06066301 จะกระทบอะไร");
  assert.strictEqual(app.retryQuestion("Calcuus 1 กี่หน่วยกิต", near("Calcuus 1", "06026200")), "06026200 กี่หน่วยกิต");
});

test("spacing between name and number may differ from the typed text", () => {
  assert.strictEqual(app.retryQuestion("วิชาแคลคุลัส2 กี่หน่วยกิต", near("แคลคุลัส 2", "06026201")), "วิชา 06026201 กี่หน่วยกิต");
});

test("no button when the answer is not a near match or the name is not in the question", () => {
  assert.strictEqual(app.retryQuestion("ปี 1 เรียนอะไร", { answer: "...", rows: [{ code: "06026200" }] }), "");
  assert.strictEqual(app.retryQuestion("ถามอย่างอื่น", near("แคลคุลัส 2", "06026201")), "");
  assert.strictEqual(app.retryQuestion("x", null), "");
});
