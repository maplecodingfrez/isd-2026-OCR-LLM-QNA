
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS program (
    program_id    TEXT PRIMARY KEY,
    name_th       TEXT NOT NULL,
    name_en       TEXT,
    degree        TEXT,
    total_credits INTEGER NOT NULL CHECK (total_credits BETWEEN 30 AND 300),
    years         INTEGER NOT NULL CHECK (years BETWEEN 1 AND 8)
);

CREATE TABLE IF NOT EXISTS course (
    code           TEXT PRIMARY KEY,
    name_th        TEXT NOT NULL,
    name_en        TEXT,
    credits        INTEGER NOT NULL CHECK (credits BETWEEN 0 AND 12),
    lecture_h      INTEGER,
    lab_h          INTEGER,
    self_h         INTEGER,
    description_th TEXT
);

CREATE TABLE IF NOT EXISTS plan_item (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL REFERENCES program(program_id),
    year       INTEGER NOT NULL CHECK (year BETWEEN 1 AND 8),
    semester   INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 3),
    code       TEXT NOT NULL,
    credits    INTEGER NOT NULL CHECK (credits BETWEEN 0 AND 12),
    alt_group  TEXT,
    note       TEXT
);

CREATE TABLE IF NOT EXISTS prerequisite (
    code     TEXT NOT NULL,
    requires TEXT NOT NULL,
    kind     TEXT NOT NULL CHECK (kind IN ('pre','co')),
    PRIMARY KEY (code, requires, kind)
);

CREATE INDEX IF NOT EXISTS ix_plan_sem ON plan_item(year, semester);
CREATE INDEX IF NOT EXISTS ix_plan_code ON plan_item(code);

-- ตารางอ้างอิงแยก (ไม่ใช่ plan_item/course) สำหรับ "เมนูวิชาเลือก" ที่ตารางแผนเขียนเป็นรหัส
-- wildcard (เช่น 06036xxx) ไม่ใช่รหัสจริง — เอกสารต้นฉบับเองก็ไม่ได้ระบุว่านักศึกษาจะเลือกวิชาไหน
-- (เป็นทางเลือกเปิดจริง ไม่ใช่ OCR อ่านไม่ออก) จึง "ไม่" ผูกเข้า plan_item โดยตรง — ยังต้องคง
-- CHK1/CHK7 รายงานหน่วยกิตที่ขาดของช่อง wildcard เหมือนเดิม ตารางนี้แค่เก็บว่า "มีตัวเลือกอะไรบ้าง"
-- ให้ตอบคำถามแยกได้ (ไม่แตะ course เดิม เพื่อไม่ให้ COUNT(*) FROM course ของ eval คำถามเดิมเพี้ยน)
CREATE TABLE IF NOT EXISTS elective_group (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id        TEXT NOT NULL REFERENCES program(program_id),
    plan_slot         TEXT NOT NULL,   -- ช่อง wildcard ในตารางแผนที่กลุ่มนี้แทนอยู่
    credits_required  INTEGER,         -- หน่วยกิตที่ต้องเลือกรวมจากกลุ่มนี้ (ไม่ใช่ต่อวิชา)
    group_no          INTEGER NOT NULL,
    name_th           TEXT NOT NULL,
    name_en           TEXT
);

CREATE TABLE IF NOT EXISTS elective_group_course (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id   INTEGER NOT NULL REFERENCES elective_group(id),
    code       TEXT NOT NULL,
    name_th    TEXT NOT NULL,
    name_en    TEXT,
    credits    INTEGER NOT NULL CHECK (credits BETWEEN 0 AND 12)
);

CREATE VIEW IF NOT EXISTS v_elective_group AS
SELECT eg.program_id, eg.plan_slot, eg.credits_required,
       eg.group_no, eg.name_th AS group_name_th, eg.name_en AS group_name_en,
       egc.code, egc.name_th AS course_name_th, egc.name_en AS course_name_en, egc.credits
FROM elective_group eg
JOIN elective_group_course egc ON egc.group_id = eg.id;

-- VIEW ทำให้การถามคำถามง่ายขึ้นมาก
-- แทนที่ LLM จะต้อง JOIN เองทุกครั้ง เราเตรียมตารางแบนไว้ให้
-- นี่คือเหตุผลที่ VIEW มีอยู่ในโลก: ซ่อนความซับซ้อนของการ normalize
CREATE VIEW IF NOT EXISTS v_plan AS
SELECT p.id, p.year, p.semester, p.code, c.name_th, c.name_en,
       p.credits, p.alt_group, p.note
FROM plan_item p
LEFT JOIN course c ON c.code = p.code;

-- VIEW ที่สองนี้สำคัญกว่าที่เห็น
--
-- ถ้าให้ LLM เขียน SUM(credits) FROM v_plan เอง มันจะได้คำตอบผิด
-- เพราะวิชาเลือก "A หรือ B" มีสองแถว แต่ต้องนับหน่วยกิตครั้งเดียว
-- ปี 2 เทอม 1 จะได้ 12 แทนที่จะเป็น 9
--
-- ทางแก้ที่ผิดคือ ไปเขียนใน prompt ว่า "อย่าลืมหักวิชาเลือกออก"
-- เพราะ prompt เป็นการขอร้อง โมเดลจะลืมเป็นบางครั้ง แล้วเราจะจับไม่ได้
--
-- ทางแก้ที่ถูกคือ ย้ายตรรกะนี้มาไว้ใน VIEW
-- แล้ว LLM แค่ SELECT ธรรมดา ไม่มีโอกาสทำผิดเลย
-- หลักการ: อะไรที่ต้อง "ถูกเสมอ" ให้เขียนเป็นโค้ด ไม่ใช่เขียนเป็นคำสั่งให้ AI
CREATE VIEW IF NOT EXISTS v_semester_credits AS
SELECT year, semester, SUM(credits) AS credits, COUNT(*) AS n_courses
FROM (
    SELECT year, semester,
           COALESCE(alt_group, 'x' || id) AS grp,
           MIN(credits) AS credits
    FROM plan_item
    GROUP BY year, semester, COALESCE(alt_group, 'x' || id)
)
GROUP BY year, semester;
