// คำใบ้ "ลองระบุปีหรือเทอมให้ชัดขึ้น" ใช้เฉพาะคำถามที่พูดถึงปี/เทอมของแผนจริง — "ค่าเทอม" (tuition) ไม่ใช่
const test = require("node:test");
const assert = require("node:assert");
const app = require("../../lab10_fastapi/curriculum_app/static/app.js");

test("year/semester questions get the year-term hint", () => {
  for (const q of ["ปี 5 เทอม 1 เรียนอะไร", "เทอมนี้เรียนอะไร", "ภาคเรียนที่ 2 ปี 3 มีวิชาอะไร", "ชั้นปีไหนเรียนแคลคูลัส", "which year and semester is calculus", "year 1 term 2"]) {
    assert.strictEqual(app.isYearTermQuestion(q), true, q);
  }
});

test("tuition and other out-of-scope questions do not", () => {
  for (const q of ["ค่าเทอมเท่าไหร่", "ค่าเทอมปีละเท่าไร", "ค่าเทอมต่อเทอมกี่บาท", "อาจารย์ที่ปรึกษาชื่ออะไร", "DROP TABLE course", "tuition fee per term", ""]) {
    assert.strictEqual(app.isYearTermQuestion(q), false, q);
  }
  assert.strictEqual(app.isYearTermQuestion(undefined), false);
});
