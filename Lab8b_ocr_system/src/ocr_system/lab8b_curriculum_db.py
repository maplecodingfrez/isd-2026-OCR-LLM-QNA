#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab8b_curriculum_db.py — Lab 8B : จากข้อความที่สกัดได้ สู่ฐานข้อมูลที่ตอบคำถามได้
วิชา 06026240 การพัฒนาระบบอัจฉริยะ 

ต่อยอดจาก Lab 7B ซึ่งสกัดเล่มหลักสูตรออกมาเป็น Markdown ได้แล้ว
Lab 8B พาข้อมูลนั้นเดินต่ออีกสามก้าว

    Markdown  ->  JSON ที่ผ่านการตรวจ  ->  ฐานข้อมูล  ->  คำตอบ

ทำไมต้องผ่านฐานข้อมูล ไม่ถาม LLM ตรง ๆ กับข้อความเลย
    เพราะคำถามจริงของนักศึกษาคือคำถามเชิงคำนวณและเชิงความสัมพันธ์
    "ปี 3 เทอม 1 มีกี่หน่วยกิต"  "วิชาไหนต้องเรียน 06026240 มาก่อน"
    ซึ่ง LLM ที่อ่านข้อความยาว ๆ จะนับผิดเสมอ แต่ SQL นับถูกทุกครั้ง
    LLM เก่งเรื่อง "แปลภาษาคนเป็น SQL"  ไม่ใช่ "เป็นเครื่องคิดเลข"

คำสั่งหลัก
  python3 lab8b_curriculum_db.py check
  python3 lab8b_curriculum_db.py selftest
  python3 lab8b_curriculum_db.py demo    -o work/
  python3 lab8b_curriculum_db.py schema  -o work/schema/
  python3 lab8b_curriculum_db.py extract -i work/curriculum.md -o work/curriculum.json
  python3 lab8b_curriculum_db.py import-lab7b -i output/pred_vlm.json -o work/curriculum.json
  python3 lab8b_curriculum_db.py load    -i work/curriculum.json -d work/curriculum.db
  python3 lab8b_curriculum_db.py verify  -d work/curriculum.db
  python3 lab8b_curriculum_db.py ask     -d work/curriculum.db -q "ปี 2 เทอม 1 เรียนกี่หน่วยกิต"
  python3 lab8b_curriculum_db.py eval    -d work/curriculum.db -q work/gold_questions.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════════
#  ค่าคงที่
# ═══════════════════════════════════════════════════════════════════════

OLLAMA_URL = os.environ.get("LAB8_OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_TEXT = os.environ.get("LAB8_MODEL_TEXT", "qwen3:4b")

MAX_REPAIR_ROUNDS = 3      # จำนวนครั้งสูงสุดที่ยอมให้ LLM แก้ JSON ของตัวเอง
SQL_ROW_LIMIT = 200        # กันไม่ให้ query เผลอดึงทั้งตารางมาใส่ prompt

# ระเบียบหน่วยกิตต่อภาคเรียนของหลักสูตรปริญญาตรี (ใช้ในการตรวจ CHK7)
MIN_CREDITS_PER_SEM = 9
MAX_CREDITS_PER_SEM = 22


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 0 — ตรวจสภาพแวดล้อม
# ═══════════════════════════════════════════════════════════════════════

def check_environment() -> bool:
    print("=" * 68)
    print("  ตรวจสภาพแวดล้อม Lab 8B")
    print("=" * 68)
    ok = True

    required = [
        ("pydantic", "pydantic", "ตรวจความถูกต้องของ JSON และสร้างข้อความ error ให้ LLM แก้"),
        ("requests", "requests", "เรียก Ollama"),
    ]
    for mod, pipname, why in required:
        try:
            __import__(mod)
            print(f"  [ ok ] {pipname:<12} — {why}")
        except ImportError:
            print(f"  [FAIL] {pipname:<12} — {why}")
            print(f"         แก้ด้วย:  pip install {pipname}")
            ok = False

    # sqlite3 มากับ Python อยู่แล้ว แต่ต้องตรวจว่ารุ่นรองรับ foreign key
    v = sqlite3.sqlite_version_info
    if v >= (3, 6, 19):
        print(f"  [ ok ] sqlite3      — เวอร์ชัน {sqlite3.sqlite_version} รองรับ foreign key")
    else:
        print(f"  [FAIL] sqlite3      — เวอร์ชัน {sqlite3.sqlite_version} เก่าเกินไป")
        ok = False

    try:
        import requests
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        names = [m["name"] for m in r.json().get("models", [])]
        print(f"  [ ok ] Ollama ทำงานอยู่ที่ {OLLAMA_URL}")
        if any(n == MODEL_TEXT or n.startswith(MODEL_TEXT.split(":")[0]) for n in names):
            print(f"  [ ok ] พบโมเดล {MODEL_TEXT}")
        else:
            print(f"  [FAIL] ไม่พบโมเดล {MODEL_TEXT}")
            print(f"         แก้ด้วย:  ollama pull {MODEL_TEXT}")
            ok = False
    except Exception as e:
        print(f"  [FAIL] ต่อ Ollama ไม่ได้ ({type(e).__name__}) — เปิดด้วย  ollama serve")
        ok = False

    print("=" * 68)
    print("  พร้อมทำแล็บ" if ok else "  ยังไม่พร้อม — แก้ตามข้อความ [FAIL] ข้างบนก่อน")
    print("=" * 68)
    return ok


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 1 — ออกแบบ Schema ก่อน แล้วค่อยสกัด
# ═══════════════════════════════════════════════════════════════════════
#
#  ลำดับที่ถูกต้องคือ  ออกแบบ schema -> สกัด -> ตรวจ
#  ไม่ใช่  สกัด -> ดูว่าได้อะไรมา -> ค่อยคิด schema
#
#  ถ้าปล่อยให้ LLM คิดโครงสร้างเอง จะเกิดสองปัญหาที่แก้ทีหลังไม่ได้
#    1) แต่ละหน้าได้ชื่อฟิลด์ไม่ตรงกัน (หน้าหนึ่ง "หน่วยกิต" อีกหน้า "credit")
#       ทำให้รวมข้อมูลไม่ได้
#    2) ไม่มีเกณฑ์ตัดสินว่า "ผิด" คืออะไร จึงตรวจอัตโนมัติไม่ได้เลย
#
#  Schema คือสัญญาที่เขียนไว้ก่อน ทั้งฝั่งสกัดและฝั่งตรวจจึงพูดภาษาเดียวกัน
# ═══════════════════════════════════════════════════════════════════════

def build_models():
    """
    สร้าง Pydantic models

    ห่อไว้ในฟังก์ชันเพื่อให้ไฟล์นี้ยัง import ได้แม้ยังไม่ได้ติดตั้ง pydantic
    (คำสั่ง check จะได้บอกวิธีติดตั้งแทนที่จะพังตั้งแต่บรรทัด import)
    """
    from pydantic import BaseModel, Field, field_validator

    # รหัสวิชา 8 หลัก — รูปแบบมาตรฐานของ สจล.
    CODE_RE = re.compile(r"^\d{8}$")

    class Course(BaseModel):
        """รายวิชาหนึ่งวิชา ตามที่ปรากฏในหมวดคำอธิบายรายวิชา"""
        code: str
        name_th: str
        name_en: str | None = None
        credits: int = Field(ge=0, le=12)
        # สหกิจศึกษาในเล่มจริงใช้ 6(0-35-0) จึงห้ามจำกัดชั่วโมงไว้แค่ 30
        lecture_h: int | None = Field(default=None, ge=0, le=60)
        lab_h: int | None = Field(default=None, ge=0, le=60)
        self_h: int | None = Field(default=None, ge=0, le=60)
        description_th: str | None = None

        @field_validator("code")
        @classmethod
        def _code_format(cls, v: str) -> str:
            v = v.strip()
            if not CODE_RE.match(v):
                raise ValueError(f"รหัสวิชาต้องเป็นตัวเลข 8 หลัก แต่ได้ '{v}'")
            return v

    class PlanItem(BaseModel):
        """
        หนึ่งบรรทัดในแผนการศึกษา

        alt_group คือกลไกจัดการ "วิชาเลือกอย่างใดอย่างหนึ่ง"
        เล่มหลักสูตรเขียนว่า  06026259 หรือ 06026260
        เราแตกเป็นสองแถวที่มี alt_group เดียวกัน
        เวลานับหน่วยกิตจึงนับ alt_group ละครั้งเดียว ไม่นับซ้ำ

        นี่คือบทเรียนตรงจาก Lab 7B: กฎตรวจที่ไม่รู้จักกรณีนี้
        จะเตือนผิดทุกครั้งที่เจอวิชาเลือก จนนักศึกษาเลิกอ่านคำเตือน
        """
        year: int = Field(ge=1, le=8)
        semester: int = Field(ge=1, le=3)   # 3 = ภาคฤดูร้อน
        code: str
        credits: int = Field(ge=0, le=12)
        alt_group: str | None = None
        note: str | None = None

        @field_validator("code")
        @classmethod
        def _code_format(cls, v: str) -> str:
            v = v.strip()
            if not CODE_RE.match(v):
                raise ValueError(f"รหัสวิชาในแผนต้องเป็นตัวเลข 8 หลัก แต่ได้ '{v}'")
            return v

    class Prerequisite(BaseModel):
        """ความสัมพันธ์วิชาบังคับก่อน / วิชาเรียนควบ"""
        code: str
        requires: str
        kind: str = "pre"       # pre = บังคับก่อน, co = เรียนควบ

        @field_validator("kind")
        @classmethod
        def _kind_ok(cls, v: str) -> str:
            if v not in ("pre", "co"):
                raise ValueError("kind ต้องเป็น 'pre' หรือ 'co' เท่านั้น")
            return v

    class Program(BaseModel):
        """ข้อมูลหลักสูตรระดับบนสุด"""
        program_id: str
        name_th: str
        name_en: str | None = None
        degree: str | None = None
        total_credits: int = Field(ge=30, le=300)
        years: int = Field(ge=1, le=8)

    class Curriculum(BaseModel):
        """เอกสารทั้งเล่มหนึ่งฉบับ"""
        program: Program
        courses: list[Course] = []
        plan: list[PlanItem] = []
        prerequisites: list[Prerequisite] = []

    return Curriculum


# ── SQL DDL ────────────────────────────────────────────────────────────
# เขียนแยกจาก Pydantic โดยตั้งใจ เพราะสองอย่างนี้ทำหน้าที่ต่างกัน
#   Pydantic ตรวจ "รูปร่างของข้อมูลแต่ละชิ้น"  (ก่อนเข้าฐานข้อมูล)
#   SQL constraint ตรวจ "ความสัมพันธ์ระหว่างชิ้น" (ตอนเข้าฐานข้อมูล)

DDL = """
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
"""


# DDL ของ "หรือ" ในวิชาบังคับก่อน — แยกออกจาก DDL หลักโดยตั้งใจ (เหตุผลเดียวกับ PLAN_SLOT_DDL:
# DDL หลักถูกยัดเข้า prompt ของ NL2SQL ถ้าแก้ตาราง prerequisite prompt เปลี่ยนและคะแนน eval เดิมอาจเพี้ยน)
# ตาราง prerequisite เดิมไม่เปลี่ยน (ยังเก็บ "A หรือ B" เป็นสองแถว kind='pre'); ตารางนี้ระบุเพิ่มว่า
# แถวไหนเป็น "ทางเลือกกัน": แถวของวิชาเดียวกันที่ group_no เดียวกัน = ผ่านอย่างใดอย่างหนึ่งก็พอ
# (วิชาที่ไม่มีแถวในตารางนี้ = "และ" ตามปกติ) ใช้เฉพาะตอน `load-prerequisites`
PREREQ_ALT_DDL = """
CREATE TABLE IF NOT EXISTS prerequisite_alt (
    code     TEXT NOT NULL,
    requires TEXT NOT NULL,
    group_no INTEGER NOT NULL,
    PRIMARY KEY (code, requires)
);
"""


# DDL ของช่องแผนที่ plan_item เก็บไม่ตรงเล่ม — แยกออกจาก DDL ด้านบนโดยตั้งใจ
# เพราะ DDL ถูกยัดทั้งก้อนเข้า prompt ของ NL2SQL (ask/eval, num_ctx 4096) ถ้าเพิ่มตาราง
# ตรงนั้น prompt เปลี่ยน คะแนนข้อสอบเดิมอาจเพี้ยน; ใช้เฉพาะตอน `load-plan-slots`
PLAN_SLOT_DDL = """
-- ช่องในตารางแผนที่ plan_item เก็บได้ไม่ตรงเล่ม (เพิ่มแบบ additive — ไม่แตะ plan_item,
-- v_semester_credits หรือ verify เดิม เพื่อไม่ให้คำตอบ eval/คะแนน Lab 9 เดิมเปลี่ยน)
--   wildcard      แถวรหัส xxx (06026xxx, 9064xxxx, xxxxxxxx ...) ที่ plan_item ไม่เก็บ
--   choose_one    "A หรือ B" (สหกิจในประเทศ/ต่างประเทศ) นับหน่วยกิตครั้งเดียว
--   choose_group  "เลือก 1 กลุ่มวิชา" (IT ปี 2/2, 3/1) — นับหน่วยกิตของ 1 กลุ่มเท่านั้น
-- choose_one/choose_group: วิชาสมาชิกยังอยู่ใน plan_item ครบ แต่ v_semester_credits_full
-- ตัดออกแล้วนับ credits ของ slot แทน (credits = หน่วยกิตที่เล่มรวมให้เทอมนั้นจริง)
CREATE TABLE IF NOT EXISTS plan_slot (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL REFERENCES program(program_id),
    year       INTEGER NOT NULL CHECK (year BETWEEN 1 AND 8),
    semester   INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 3),
    kind       TEXT NOT NULL CHECK (kind IN ('wildcard','choose_one','choose_group')),
    code       TEXT,                 -- รหัส wildcard ตามเล่ม (เช่น 06026xxx); NULL ถ้าไม่ใช่ wildcard
    name_th    TEXT NOT NULL,
    credits    INTEGER NOT NULL CHECK (credits BETWEEN 0 AND 12),
    note       TEXT
);

CREATE TABLE IF NOT EXISTS plan_slot_member (
    slot_id    INTEGER NOT NULL REFERENCES plan_slot(id),
    group_no   INTEGER NOT NULL DEFAULT 1,   -- choose_group: กลุ่มที่เท่าไร; choose_one: 1
    group_name TEXT,
    code       TEXT NOT NULL,
    PRIMARY KEY (slot_id, group_no, code)
);

CREATE INDEX IF NOT EXISTS ix_slot_sem ON plan_slot(year, semester);

-- หน่วยกิตต่อภาคเรียน "ตามเล่ม": วิชาใน plan_item ที่ไม่ใช่สมาชิก slot (นับ alt_group ครั้งเดียว)
-- + credits ของทุก slot ถ้าไม่มีแถวใน plan_slot จะได้ค่าเท่า v_semester_credits
CREATE VIEW IF NOT EXISTS v_semester_credits_full AS
SELECT year, semester, SUM(credits) AS credits, COUNT(*) AS n_entries
FROM (
    SELECT p.year, p.semester, MIN(p.credits) AS credits
    FROM plan_item p
    WHERE NOT EXISTS (
        SELECT 1 FROM plan_slot s
        JOIN plan_slot_member m ON m.slot_id = s.id
        WHERE s.program_id = p.program_id AND s.year = p.year
          AND s.semester = p.semester AND m.code = p.code)
    GROUP BY p.year, p.semester, COALESCE(p.alt_group, 'x' || p.id)
    UNION ALL
    SELECT year, semester, credits FROM plan_slot
)
GROUP BY year, semester;
"""


def cmd_schema(args) -> None:
    """เขียน JSON Schema และ SQL DDL ออกเป็นไฟล์ เพื่อใช้อ้างอิงและส่งงาน"""
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    Curriculum = build_models()
    (out / "curriculum.schema.json").write_text(
        json.dumps(Curriculum.model_json_schema(), ensure_ascii=False, indent=2),
        encoding="utf-8")
    (out / "schema.sql").write_text(DDL, encoding="utf-8")
    print(f"  เขียน {out}/curriculum.schema.json")
    print(f"  เขียน {out}/schema.sql")


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 2 — สกัด JSON พร้อมวงจรซ่อม (repair loop)
# ═══════════════════════════════════════════════════════════════════════

def ollama_generate(prompt: str, fmt: Any | None = None,
                    timeout: int = 600, model: str | None = None,
                    num_ctx: int = 8192, num_predict: int = 4096) -> str:
    """เรียก Ollama บนเครื่องตัวเอง"""
    import requests
    payload: dict[str, Any] = {
        "model": model or MODEL_TEXT,
        # qwen3:4b บาง build ของ Ollama ยังไม่ปิด reasoning จาก field think
        # จึงใส่ /no_think ใน prompt ซ้ำเพื่อให้งาน SQL สั้นๆ คืนคำตอบใน content
        "messages": [{"role": "user", "content": prompt + "\n/no_think"}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_ctx": num_ctx,
                    "num_predict": num_predict},
    }
    if fmt:
        payload["format"] = fmt
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    return (r.json().get("message") or {}).get("content", "")


def parse_json_loose(s: str) -> dict:
    """ดึง JSON ออกจากคำตอบ แม้จะมี <think> หรือ fence ปนมา"""
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    s = re.sub(r"^```(?:json)?|```$", "", s.strip(), flags=re.M).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    if start < 0:
        return {}
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start:i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


EXTRACT_PROMPT = """คุณคือผู้ช่วยแปลงเอกสารหลักสูตรเป็นข้อมูลที่มีโครงสร้าง

แปลงข้อความเล่มหลักสูตรต่อไปนี้เป็น JSON ตาม schema นี้เท่านั้น

{
  "program":  {"program_id":"", "name_th":"", "name_en":"", "degree":"",
               "total_credits":0, "years":0},
  "courses":  [{"code":"12345678","name_th":"","name_en":"","credits":0,
                "lecture_h":0,"lab_h":0,"self_h":0,"description_th":""}],
  "plan":     [{"year":1,"semester":1,"code":"12345678","credits":0,
                "alt_group":null,"note":null}],
  "prerequisites": [{"code":"12345678","requires":"12345678","kind":"pre"}]
}

กติกา
1. รหัสวิชาต้องเป็นตัวเลข 8 หลักเสมอ
2. ถ้าเล่มเขียนว่า "รหัส A หรือ รหัส B" ให้แตกเป็นสองรายการในแผน
   โดยใส่ alt_group เป็นข้อความเดียวกัน เช่น "elective_y3s1_1"
3. ค่าที่หาไม่พบ ให้ใส่ null ห้ามเดาและห้ามคำนวณเอง
4. semester ใช้ 1, 2 หรือ 3 (3 หมายถึงภาคฤดูร้อน)
5. ตอบเป็น JSON ล้วน ไม่ต้องมีคำอธิบาย

ข้อความ:
"""

REPAIR_PROMPT = """JSON ที่คุณสร้างมาไม่ผ่านการตรวจสอบ นี่คือรายการข้อผิดพลาด

{errors}

แก้เฉพาะจุดที่ระบุไว้ ห้ามแก้ส่วนอื่น ห้ามลบรายการที่ถูกต้องอยู่แล้ว
ถ้าข้อผิดพลาดเกิดเพราะข้อมูลไม่มีในเอกสารจริง ให้ลบรายการนั้นออก แทนที่จะเดาค่า

ตอบกลับเป็น JSON ฉบับสมบูรณ์ที่แก้แล้ว ไม่ต้องมีคำอธิบาย

JSON เดิม:
{payload}
"""


def format_errors(exc) -> str:
    """
    แปลง ValidationError ของ Pydantic เป็นข้อความที่ LLM แก้ตามได้จริง

    จุดสำคัญ: ต้องบอก "ตำแหน่ง" ให้ชัด (plan -> 12 -> code)
    ถ้าบอกแค่ "รหัสวิชาผิด" โมเดลจะไม่รู้ว่าต้องแก้รายการไหน
    แล้วมักจะรื้อทั้งก้อนใหม่ ซึ่งทำให้ข้อมูลที่ถูกอยู่แล้วพังไปด้วย
    """
    lines = []
    for e in exc.errors()[:25]:      # จำกัดไว้ไม่ให้ prompt ยาวเกิน
        loc = " -> ".join(str(x) for x in e["loc"])
        lines.append(f"- ตำแหน่ง {loc}: {e['msg']}")
    if len(exc.errors()) > 25:
        lines.append(f"- (และอีก {len(exc.errors()) - 25} ข้อ)")
    return "\n".join(lines)


def extract_with_repair(text: str, max_rounds: int = MAX_REPAIR_ROUNDS,
                        verbose: bool = True) -> tuple[dict, dict]:
    """
    สกัด JSON แล้ววนซ่อมจนผ่าน หรือจนครบจำนวนรอบ

    ทำไมต้องจำกัดจำนวนรอบ
        ถ้าปล่อยให้วนไม่จำกัด จะเจอกรณีที่โมเดลแก้วนไปวนมาไม่จบ
        (แก้ข้อ A แล้วข้อ B พัง แก้ข้อ B แล้วข้อ A พังอีก)
        การจำกัดรอบแล้ว "ยอมแพ้อย่างมีเกียรติ" คือพฤติกรรมที่ถูกต้อง
        ระบบที่ดีต้องรู้ว่าเมื่อไรควรส่งงานให้คนตรวจ

    คืน (data, meta) โดย meta บอกว่าใช้กี่รอบและผ่านหรือไม่
    """
    from pydantic import ValidationError
    Curriculum = build_models()

    raw = ollama_generate(EXTRACT_PROMPT + text, fmt="json")
    data = parse_json_loose(raw)
    meta = {"rounds": 0, "valid": False, "errors": []}

    for attempt in range(max_rounds + 1):
        try:
            model = Curriculum.model_validate(data)
            meta.update({"rounds": attempt, "valid": True, "errors": []})
            if verbose:
                print(f"  ผ่านการตรวจในรอบที่ {attempt}")
            return model.model_dump(), meta
        except ValidationError as exc:
            errs = format_errors(exc)
            meta["errors"] = errs.splitlines()
            if verbose:
                print(f"  รอบที่ {attempt}: พบข้อผิดพลาด {len(exc.errors())} ข้อ")
            if attempt >= max_rounds:
                meta.update({"rounds": attempt, "valid": False})
                if verbose:
                    print(f"  ! ซ่อมครบ {max_rounds} รอบแล้วยังไม่ผ่าน "
                          f"— ทำเครื่องหมายให้คนตรวจ")
                return data, meta
            raw = ollama_generate(
                REPAIR_PROMPT.format(
                    errors=errs,
                    payload=json.dumps(data, ensure_ascii=False)),
                fmt="json")
            new = parse_json_loose(raw)
            if new:
                data = new

    return data, meta


def cmd_extract(args) -> None:
    text = Path(args.input).read_text(encoding="utf-8")
    if args.max_chars and len(text) > args.max_chars:
        print(f"  ! ข้อความยาว {len(text):,} ตัวอักษร ตัดเหลือ {args.max_chars:,}")
        text = text[:args.max_chars]
    t0 = time.time()
    data, meta = extract_with_repair(text, args.rounds)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    meta["seconds"] = round(time.time() - t0, 1)
    out.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  เขียน {out}  ({meta['seconds']}s · "
          f"{'ผ่าน' if meta['valid'] else 'ต้องให้คนตรวจ'})")


# ── นำ JSON จาก Lab 7B มาใช้ต่อโดยไม่เรียก LLM ซ้ำ ─────────────────────────

def _credit_parts(value: Any) -> tuple[int, int | None, int | None, int | None]:
    """แปล 3(2-2-5) ของ Lab 7B เป็นคอลัมน์ตัวเลขของ Lab 8B"""
    text = str(value or "").strip()
    m = re.search(r"(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*\)", text)
    if m:
        return tuple(map(int, m.groups()))  # type: ignore[return-value]
    m = re.search(r"\d+", text)
    if not m:
        raise ValueError(f"อ่านหน่วยกิตไม่ได้: {value!r}")
    return int(m.group()), None, None, None


def _lab7b_codes(value: Any) -> list[str]:
    """แตกรหัส `A หรือ B`; คืนรหัสตัวเลข 8 หลักทั้งหมดที่เจอ"""
    return re.findall(r"(?<!\d)\d{8}(?!\d)", str(value or ""))


def _ambiguous_code_merge(raw_code: str, codes: list[str]) -> bool:
    """True เมื่อ raw_code มีเลข 8 หลักมากกว่า 1 ตัว แต่ไม่มีตัวคั่น "หรือ"/"/" จริง —
    แปลว่าไม่ใช่ "A หรือ B" แต่เป็น cell rowspan ที่ OCR รวม 2 แถวเข้าด้วยกันเฉย ๆ
    (เช่น "06036146 96642033") ชื่อ/รายละเอียดในแถวนี้เป็นของ "แถวเดียว" ไม่ใช่ของ
    ทั้งสองรหัส ห้ามยัดชื่อเดียวกันให้ทุกรหัส ไม่งั้นรหัสที่ไม่เกี่ยวข้องจะได้ชื่อผิด
    แล้วอาจทับชื่อที่ถูกต้องซึ่งมาจากแถวอื่นแบบเงียบ ๆ (เจอจริงกับ BIT ปีที่ 3/2)"""
    return len(codes) > 1 and not re.search(r"หรือ|/", raw_code)


# label หมวด/กลุ่มวิชา (เช่น "วิชาเลือกกลุ่มวิศวกรรมข้อมูล 4", "กลุ่มวิชาที่กำหนดโดยคณะ*")
# ไม่ใช่ชื่อวิชาจริง เอกสารตระกูลนี้ใช้ "*" เป็นเครื่องหมายเชิงอรรถของ label เท่านั้น
# ไม่เคยเป็นส่วนของชื่อวิชาจริง (ดูหมายเหตุที่จุดเรียกใน sanity check ท้าย convert_lab7b)
_LABEL_LIKE_PREFIX = re.compile(r"^(กลุ่มวิชา|หมวดวิชา|วิชาเลือก)")


def _label_like_name(name: Any) -> bool:
    """True เมื่อชื่อวิชา "หน้าตาเป็น label หมวดวิชา" ไม่ใช่ชื่อวิชาจริง"""
    name = str(name or "").strip()
    return bool(name) and ("*" in name or bool(_LABEL_LIKE_PREFIX.match(name)))


def convert_lab7b(data: dict, *, program_id: str | None = None,
                  program_name: str | None = None,
                  total_credits: int | None = None,
                  years: int | None = None,
                  markdown: str | None = None) -> tuple[dict, dict]:
    """
    แปล schema ผลลัพธ์ Lab 7B เป็น Lab 8B ด้วยกฎคงที่ โดยไม่เรียก LLM

    รหัส wildcard เช่น 06026xxx ไม่มีตัวตนวิชาจริงในตาราง course จึงไม่เดารหัสให้
    แต่บันทึกลง conversion report ทุกรายการ
    """
    warnings: list[str] = []
    recovered_terms: list[dict] = []
    if markdown:
        # กู้ปี/เทอมของวิชารหัสจริงที่ได้ 0/0 จาก Markdown ของ OCR (กฎเชิงกำหนด; ดู md_plan_slots.recover_terms)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from md_plan_slots import recover_terms
        data = {**data, "courses": [dict(c) for c in (data.get("courses") or [])]}
        recovered_terms = recover_terms(markdown, data["courses"])
        for r in recovered_terms:
            warnings.append(f"{r['code']}: ปี/เทอม {r['from']} -> {r['to']} (กู้จากตำแหน่งใน Markdown ของ OCR)")
    course_by_code: dict[str, dict] = {}
    plan: list[dict] = []
    prerequisites: list[dict] = []
    seen_plan: set[tuple] = set()
    seen_pre: set[tuple] = set()
    skipped_wildcards = 0
    skipped_flexible = 0

    # แถว "A หรือ B" ที่ OCR/LLM ส่งมาเป็น "หลายแถวรหัสเดียวกันคนละชื่อ" (เช่น IT/AIT/DSBA/BIT
    # แผนสหกิจ: "06046443 หรือ 06046444" สองแถว ชื่อ "สหกิจศึกษา…" กับ "สหกิจศึกษาต่างประเทศ…")
    # เล่มเรียงชื่อตามลำดับรหัส -> แถวที่ k ของรหัสชุดเดียวกัน (ปี/เทอมเดียวกัน) เป็นชื่อของรหัสที่ k
    # เดิมทุกแถวยัดชื่อของตัวเองให้ "ทุกรหัส" first-write-wins จึงทำให้รหัสที่ 2 ได้ชื่อของแถวแรก
    # (ชื่อซ้ำ + warning "รหัสเดียวกันมาพร้อมชื่อไทยสองชื่อ") กติกาเชิงกำหนด ไม่เรียก LLM ไม่ใช้เฉลย:
    # ใช้ต่อเมื่อ "จำนวนแถว = จำนวนรหัส" พอดีเท่านั้น ไม่งั้นคงพฤติกรรมเดิม
    # (แถวเดียวที่เขียน "A หรือ B" ยังให้ชื่อเดียวกันทั้งสองรหัสเหมือนเดิม)
    # ผลกระทบจำกัดที่ชื่อ/name_en/description ใน course — ไม่แตะ plan/alt_group/หน่วยกิต
    or_rows: dict[tuple, tuple[int, list[int]]] = {}
    for idx, s in enumerate(data.get("courses") or []):
        rc = str(s.get("code") or "").strip()
        cs = _lab7b_codes(rc)
        if len(cs) > 1 and not _ambiguous_code_merge(rc, cs):
            key = (tuple(cs), str(s.get("year")), str(s.get("semester")))
            or_rows.setdefault(key, (len(cs), []))[1].append(idx)
    or_row_owner: dict[int, int] = {}
    for n_codes, idxs in or_rows.values():
        if len(idxs) == n_codes:
            for k, idx in enumerate(idxs):
                or_row_owner[idx] = k

    for index, src in enumerate(data.get("courses") or []):
        raw_code = str(src.get("code") or "").strip()
        codes = _lab7b_codes(raw_code)
        if not codes:
            skipped_wildcards += 1
            warnings.append(f"courses[{index}] ข้ามรหัสที่ไม่ใช่ตัวเลข 8 หลัก: {raw_code!r}")
            continue
        ambiguous_merge = _ambiguous_code_merge(raw_code, codes)
        if ambiguous_merge:
            warnings.append(
                f"courses[{index}] รหัส {raw_code!r} ไม่มีตัวคั่น 'หรือ'/'/' ดูเหมือน "
                f"cell รวมจาก OCR (rowspan) — ใช้ชื่อวิชาของแถวนี้กับ {codes[0]!r} เท่านั้น "
                f"ส่วน {codes[1:]!r} จะได้แค่รหัส+หน่วยกิต (ชื่อรอข้อมูลจากแถวอื่นมาเติม "
                "ถ้ามี ไม่งั้นชื่อวิชาจะยังเป็นรหัสตัวเอง ต้องตรวจด้วยตา)")
        try:
            credit, lecture, lab, self_h = _credit_parts(src.get("credits"))
        except ValueError as exc:
            warnings.append(f"courses[{index}] {exc}; ข้ามรายการ")
            continue
        if "หรือ" in str(src.get("credits") or ""):
            warnings.append(f"{raw_code}: หน่วยกิตมีหลายแบบ; ใช้แบบแรก")

        for i, code in enumerate(codes):
            # cell รวมจาก rowspan (ambiguous_merge): ชื่อ/คำอธิบายในแถวนี้เป็นของรหัส
            # แรกเท่านั้น รหัสที่เหลือให้ placeholder name_th=code ไว้ก่อน (เหมือน
            # "ชื่อยังหาย" ปกติ) เผื่อมีแถวอื่นที่มีชื่อจริงของรหัสนั้นมา merge ทับทีหลัง
            use_real_name = ((not ambiguous_merge or i == 0)
                             and (index not in or_row_owner or i == or_row_owner[index]))
            candidate = {
                "code": code,
                "name_th": (str(src.get("name_th") or code).strip()
                            if use_real_name else code),
                "name_en": ((str(src["name_en"]).replace("\n", " ").strip()
                             if src.get("name_en") else None) if use_real_name else None),
                "credits": credit,
                "lecture_h": lecture,
                "lab_h": lab,
                "self_h": self_h,
                "description_th": src.get("description_th") if use_real_name else None,
            }
            old = course_by_code.get(code)
            if old is None:
                course_by_code[code] = candidate
            else:
                # วิชาเดียวกันอาจโผล่หลายหน้า (เช่น แผน coop กับ non-coop มีตาราง
                # ปี 1 เทอม 1 เหมือนกัน) หน้าหนึ่งอาจอ่านชื่อไทยตก อีกหน้าอ่านครบ
                # --> เติมช่องที่ยังว่าง และให้ชื่อไทยที่ยังเป็นแค่ "รหัสวิชา"
                #     (fallback ตอนชื่อหาย) ถูกแทนด้วยชื่อจริงจากหน้าถัดไปได้
                new_name = str(candidate.get("name_th") or "").strip()
                old_name = str(old.get("name_th") or "").strip()
                # ตัวกันเชิงกำหนดแน่: "รหัสเดียวกัน แถวแรกได้ชื่อที่เป็น label หมวดวิชา
                # แถวหลังได้ชื่อวิชาจริง" — first-write-wins เดิมจะเก็บ label ไว้แล้วทิ้งชื่อจริง
                # เงียบ ๆ ทำให้วิชาจริงหายจากตาราง course ทั้งวิชา (ไม่ใช่แค่ชื่อเพี้ยน)
                # label ไม่มีทางเป็นชื่อวิชาจริงได้อยู่แล้ว จึงให้ชื่อที่ "ไม่เป็น label" ชนะเสมอ
                # โดยไม่สนลำดับที่เจอก่อน/หลัง (ทิศทางเดียว: ปล่อยชื่อจริง -> label ไม่ได้)
                # เจอจริงกับ DSBA แผนไม่สหกิจ มคอ.2 หน้าปีที่ 3/2: Typhoon-OCR เลื่อนคอลัมน์
                # รหัสของตาราง 2 คอลัมน์ย่อย (wildcard "06026xxx" คู่กับวิชาทางเลือกจริง)
                # ขึ้นไปหนึ่งแถว ทำให้ "06066100" ไปเกาะ label "วิชาเลือกกลุ่มการวิเคราะห์
                # เชิงสถิติ 4" ก่อน แล้วทับชื่อจริง "การบริหารโครงการเทคโนโลยีสารสนเทศ"
                demoted_label = bool(
                    new_name and old_name and new_name != old_name
                    and code not in (new_name, old_name)
                    and _label_like_name(old_name)
                    and not _label_like_name(new_name)
                    and re.search(r"[ก-๙]", new_name))
                if demoted_label:
                    # ล้างให้ว่างเพื่อให้ลูปเติมช่องว่างด้านล่างเขียนทับด้วยค่าของแถวใหม่
                    # (name_en/description_th ของแถวเดิมเป็นของ label ต้องทิ้งไปด้วย)
                    old["name_th"] = ""
                    old["name_en"] = None
                    old["description_th"] = None
                for key, value in candidate.items():
                    stale = old.get(key) in (None, "") or (
                        key == "name_th" and old.get(key) == code)
                    fresh = value not in (None, "") and not (
                        key == "name_th" and value == code)
                    # ชื่อไทยที่ OCR หลุดเหลือแต่อักษรโรมัน (เช่น "CALCULUS 1")
                    # ให้ถูกแทนด้วยชื่อที่มีอักษรไทยจริงจากอีกหน้า
                    if (key == "name_th" and fresh
                            and not re.search(r"[ก-๙]", str(old.get(key) or ""))
                            and re.search(r"[ก-๙]", str(value))):
                        stale = True
                    if stale and fresh:
                        old[key] = value
                # ตัวกันเชิงกำหนดแน่: "รหัสเดียวกัน แต่ชื่อไทยคนละชื่อ" แปลว่ามีแถวหนึ่ง
                # ได้รหัสผิด (ไม่ใช่แค่ชื่อขาด) ลูปข้างบนจะเก็บชื่อแรกไว้แล้ว "ทิ้งชื่อที่สอง
                # เงียบ ๆ" ซึ่งเป็นการสูญข้อมูลที่มองไม่เห็น — ต้องเตือน ไม่ auto-fix
                # เพราะไม่รู้ว่ารหัสที่ถูกของแถวที่สองคืออะไร
                # เจอจริงกับ IT แผนไม่สหกิจ มคอ.2 หน้า 31: Typhoon-OCR ยุบคอลัมน์รหัส
                # ของสองแถวเป็น <td rowspan="2">90642033</td> ทำให้รหัสจริงของแถวที่สอง
                # (90644042 "การสื่อสารและการนำเสนออย่างมืออาชีพ") หายไปจาก Markdown
                # ตั้งแต่ชั้น OCR แล้ว qwen3:4b จึงคืน 90642033 ซ้ำมาสองครั้ง
                if (new_name and old_name and new_name != old_name
                        and code not in (new_name, old_name)
                        and re.search(r"[ก-๙]", new_name)
                        and re.search(r"[ก-๙]", old_name)):
                    kept = (f"ชื่อแรกดูเหมือน label หมวดวิชา ระบบจึงเก็บ {new_name!r} แทน"
                            if demoted_label else "ระบบเก็บชื่อแรกไว้ ทิ้งชื่อหลัง")
                    warnings.append(
                        f"{code}: รหัสเดียวกันมาพร้อมชื่อไทยสองชื่อ {old_name!r} "
                        f"กับ {new_name!r} — น่าจะมีแถวหนึ่งได้รหัสผิด "
                        f"({kept}) ตรวจสอบ intermediate_vlm.md ต้นทาง")

        try:
            year = int(src.get("year"))
            semester = int(src.get("semester"))
        except (TypeError, ValueError):
            year = semester = 0
        if not (1 <= year <= 8 and 1 <= semester <= 3):
            skipped_flexible += 1
            warnings.append(f"{raw_code}: ไม่ใส่ในแผนเพราะปี/เทอม={year}/{semester}")
        else:
            # alt_group ใช้ได้เฉพาะ "A หรือ B" จริง (เลือกอย่างใดอย่างหนึ่ง นับหน่วยกิต
            # ครั้งเดียว) — cell รวมจาก rowspan (ambiguous_merge) เป็นวิชาคนละตัวที่ถูก
            # OCR ยำเข้าด้วยกันเฉย ๆ แต่ละรหัสยังต้องนับหน่วยกิตแยกกันเต็ม จึงห้ามใส่
            # alt_group ร่วมกัน (ไม่งั้น GROUP BY COALESCE(alt_group, ...) ใน CHK1/CHK7
            # จะรวมสองวิชานี้เป็นก้อนเดียว นับหน่วยกิตหายไปครึ่งหนึ่งแบบเงียบ ๆ)
            alt_group = (f"lab7b_alt_{index}"
                         if len(codes) > 1 and not ambiguous_merge else None)
            notes = [str(x).strip() for x in
                     (src.get("category"), src.get("type"), src.get("note")) if x]
            note = " | ".join(notes) or None
            for code in codes:
                key = (year, semester, code, alt_group)
                if key not in seen_plan:
                    plan.append({"year": year, "semester": semester,
                                 "code": code, "credits": credit,
                                 "alt_group": alt_group, "note": note})
                    seen_plan.add(key)

        # หมายเหตุ (2026-09-21, แก้ความเห็นเดิมของ 2026-09-14): โมเดลใน Lab 7B ไม่เคยกรอกฟิลด์ "prerequisite" เอง
        # (หน้าแผนไม่มีคอลัมน์นี้ และ qwen3:4b เคยเดาผิด — ดู COURSE_SCHEMA ส่วนที่ 3) แต่ Lab 7B เติมฟิลด์นี้
        # ทีหลังด้วยกฎเชิงกำหนดจากข้อความ OCR ของภาคผนวก "3.4 คำอธิบายรายวิชา" (`lab7b_curriculum.py --book-ocr` /
        # `--fill-prerequisites`, prereq_from_book.py; ไม่ใช้ LLM/เฉลย ไม่เดา): "ไม่มี" = ไม่มีวิชาบังคับก่อน,
        # "A"/"A, B"/"A หรือ B" = รหัสที่ต้องผ่านก่อน, ไม่มีฟิลด์ = ไม่ทราบ — บล็อกด้านล่างจึงใช้งานจริงแล้ว
        # (ส่วน `load-prerequisites` ยังรันต่อเพื่อบันทึก 'หรือ' ลง prerequisite_alt และรายงานสถานะ)
        pre_codes = _lab7b_codes(src.get("prerequisite"))
        for code in codes:
            for required in pre_codes:
                if required == code:
                    warnings.append(f"{code}: ข้าม prerequisite ที่อ้างถึงตัวเอง")
                    continue
                key = (code, required, "pre")
                if key not in seen_pre:
                    prerequisites.append({"code": code, "requires": required,
                                          "kind": "pre"})
                    seen_pre.add(key)

    # ตัวกันเชิงกำหนดแน่ (sanity check) — ดักชื่อวิชาที่ดูเหมือนหลุดมาผิดช่อง (เช่น label
    # หมวดวิชาที่ VLM ดึงมาเป็นชื่อวิชาแทนชื่อจริง หรือชื่อวิชาอื่นที่ถูกยัดผิดรหัสระหว่าง
    # merge) — ไม่ auto-fix เพราะไม่รู้ค่าที่ถูกต้อง แค่ชี้เป้าให้คนตรวจ
    name_to_codes: dict[str, list[str]] = {}
    for code, course in course_by_code.items():
        name_to_codes.setdefault(course["name_th"], []).append(code)
    for name, codes_with_name in name_to_codes.items():
        if len(codes_with_name) > 1:
            warnings.append(
                f"ชื่อวิชา {name!r} ซ้ำกันข้ามหลายรหัส {codes_with_name} — "
                "ตรวจสอบว่ามีรหัสไหนได้ชื่อผิดมาจากแถวอื่นหรือไม่")
    for code, course in course_by_code.items():
        name = course["name_th"] or ""
        # เดิมใช้ \b กั้นท้าย "กลุ่มวิชา"/"หมวดวิชา"/"วิชาเลือก" แต่ \b ไม่ตัดพรมแดนระหว่าง
        # อักษรไทย 2 ตัวที่ติดกัน (ไม่มีช่องว่างคั่นแบบคำอังกฤษ) เช่น "กลุ่มวิชาที่กำหนดโดยคณะ"
        # จึงไม่ match เลย (เจอจริงกับ BIT-coop "96643021": ชื่อกลายเป็น "กลุ่มวิชาที่กำหนดโดย
        # คณะ* ผู้ประกอบการสมัยใหม่" - "*" อยู่กลางสตริงไม่ใช่ท้ายสตริง ก็หลุด endswith("*") ไปด้วย)
        # แก้เป็นเช็ค "*" อยู่ตรงไหนก็ได้ในชื่อ (เอกสารตระกูลนี้ใช้ "*" เป็นเครื่องหมายเชิงอรรถของ
        # label หมวดวิชาเท่านั้น ไม่เคยเป็นส่วนของชื่อวิชาจริง) + ตัด \b ออกจาก prefix check
        if _label_like_name(name):
            warnings.append(
                f"{code}: ชื่อวิชา {name!r} ดูเหมือน label หมวดวิชา ไม่ใช่ชื่อวิชาจริง — "
                "ตรวจสอบ intermediate_vlm.md ต้นทาง")

    max_year = max((p["year"] for p in plan), default=4)
    effective_years = years or max_year
    if total_credits is None:
        groups: dict[tuple, int] = {}
        for i, item in enumerate(plan):
            group = item.get("alt_group") or f"row_{i}"
            groups[(item["year"], item["semester"], group)] = item["credits"]
        total_credits = sum(groups.values())
        warnings.append(f"ไม่ได้ระบุ --total-credits; คำนวณจากแผนที่แปลได้ = {total_credits}")
    if not 30 <= total_credits <= 300:
        raise ValueError(f"หน่วยกิตรวม {total_credits} อยู่นอกช่วง 30..300; "
                         "ระบุ --total-credits จากเล่มหลักสูตร")

    pid = str(program_id or data.get("program") or "curriculum").strip()
    result = {
        "program": {
            "program_id": pid,
            "name_th": str(program_name or data.get("program") or pid).strip(),
            "name_en": None,
            "degree": None,
            "total_credits": total_credits,
            "years": effective_years,
        },
        "courses": list(course_by_code.values()),
        "plan": plan,
        "prerequisites": prerequisites,
    }
    Curriculum = build_models()
    result = Curriculum.model_validate(result).model_dump()
    report = {
        "source_courses": len(data.get("courses") or []),
        "converted_courses": len(result["courses"]),
        "plan_items": len(result["plan"]),
        "prerequisites": len(result["prerequisites"]),
        "skipped_wildcards": skipped_wildcards,
        "skipped_flexible_plan_items": skipped_flexible,
        "terms_recovered_from_markdown": recovered_terms,
        "warnings": warnings,
    }
    return result, report


def cmd_import_lab7b(args) -> None:
    src = Path(args.input)
    data = json.loads(src.read_text(encoding="utf-8"))
    md_path = Path(args.markdown) if getattr(args, "markdown", None) else None
    markdown = md_path.read_text(encoding="utf-8") if md_path and md_path.exists() else None
    converted, report = convert_lab7b(
        data,
        program_id=args.program_id,
        program_name=args.program_name,
        total_credits=args.total_credits,
        years=args.years,
        markdown=markdown,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(converted, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path = out.with_suffix(".conversion.json")
    meta_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  แปล Lab 7B JSON -> Lab 8B JSON โดยไม่เรียก LLM")
    print(f"  เขียน {out}")
    print(f"  รายงาน {meta_path}")
    if report["terms_recovered_from_markdown"]:
        print(f"    กู้ปี/เทอมจาก Markdown {len(report['terms_recovered_from_markdown'])} วิชา")
    print(f"    course={report['converted_courses']}  plan={report['plan_items']}  "
          f"prerequisite={report['prerequisites']}")
    if report["warnings"]:
        print(f"    ต้องตรวจ {len(report['warnings'])} รายการ — ดูได้ใน {meta_path}")


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 3 — โหลดเข้าฐานข้อมูล
# ═══════════════════════════════════════════════════════════════════════

def open_db(path: str | Path, readonly: bool = False) -> sqlite3.Connection:
    """
    เปิดฐานข้อมูล

    readonly=True ใช้ตอนตอบคำถาม ซึ่งเป็นด่านความปลอดภัยชั้นที่หนึ่ง
    ต่อให้ LLM สร้าง SQL ที่เป็น DROP TABLE ขึ้นมา ฐานข้อมูลก็ปฏิเสธเอง
    เราไม่พึ่ง prompt ในการป้องกัน เพราะ prompt เป็นเพียงการขอร้อง
    """
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def cmd_load(args) -> None:
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    db = Path(args.database)
    if db.exists() and args.replace:
        db.unlink()
    db.parent.mkdir(parents=True, exist_ok=True)

    conn = open_db(db)
    conn.executescript(DDL)

    prog = data["program"]
    conn.execute(
        "INSERT OR REPLACE INTO program VALUES (?,?,?,?,?,?)",
        (prog["program_id"], prog["name_th"], prog.get("name_en"),
         prog.get("degree"), prog["total_credits"], prog["years"]))

    for c in data.get("courses", []):
        conn.execute("INSERT OR REPLACE INTO course VALUES (?,?,?,?,?,?,?,?)",
                     (c["code"], c["name_th"], c.get("name_en"), c["credits"],
                      c.get("lecture_h"), c.get("lab_h"), c.get("self_h"),
                      c.get("description_th")))

    conn.execute("DELETE FROM plan_item WHERE program_id = ?", (prog["program_id"],))
    for p in data.get("plan", []):
        conn.execute(
            "INSERT INTO plan_item (program_id, year, semester, code, credits,"
            " alt_group, note) VALUES (?,?,?,?,?,?,?)",
            (prog["program_id"], p["year"], p["semester"], p["code"],
             p["credits"], p.get("alt_group"), p.get("note")))

    for r in data.get("prerequisites", []):
        conn.execute("INSERT OR REPLACE INTO prerequisite VALUES (?,?,?)",
                     (r["code"], r["requires"], r.get("kind", "pre")))

    conn.commit()
    n = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
         for t in ("program", "course", "plan_item", "prerequisite")}
    conn.close()
    print(f"  โหลดเข้า {db} แล้ว")
    for t, c in n.items():
        print(f"    {t:<14} {c:>5} แถว")


def cmd_load_electives(args) -> None:
    """โหลดผลลัพธ์จาก extract_elective_catalog.py เข้า elective_group/elective_group_course

    ไม่แตะ course/plan_item เลย — ดู DDL ด้านบนว่าทำไม (ไม่ให้ eval คำถามเดิมที่นับ
    COUNT(*) FROM course เพี้ยน และไม่เดาว่านักศึกษาเลือกวิชาไหนจริง)
    """
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    db = Path(args.database)
    if not db.exists():
        raise SystemExit(f"ไม่พบ {db} — ต้อง `load` โปรแกรม/แผนหลักเข้าไปก่อน")

    conn = open_db(db)
    conn.executescript(DDL)  # เผื่อ DB เดิมสร้างก่อนมี 2 ตารางนี้ (CREATE TABLE IF NOT EXISTS)

    program_id = args.program_id or data.get("program")
    if not conn.execute("SELECT 1 FROM program WHERE program_id = ?",
                        (program_id,)).fetchone():
        raise SystemExit(f"ไม่พบ program_id={program_id!r} ใน {db} — โหลดผิดไฟล์/ผิด id หรือเปล่า")

    conn.execute(
        "DELETE FROM elective_group_course WHERE group_id IN "
        "(SELECT id FROM elective_group WHERE program_id = ? AND plan_slot = ?)",
        (program_id, data["plan_slot"]))
    conn.execute("DELETE FROM elective_group WHERE program_id = ? AND plan_slot = ?",
                (program_id, data["plan_slot"]))

    n_groups = n_courses = 0
    for g in data["groups"]:
        cur = conn.execute(
            "INSERT INTO elective_group (program_id, plan_slot, credits_required,"
            " group_no, name_th, name_en) VALUES (?,?,?,?,?,?)",
            (program_id, data["plan_slot"], data.get("credits_required"),
             g["group_no"], g["name_th"], g.get("name_en")))
        group_id = cur.lastrowid
        n_groups += 1
        for c in g["courses"]:
            credit, *_ = _credit_parts(c["credits"])
            conn.execute(
                "INSERT INTO elective_group_course (group_id, code, name_th,"
                " name_en, credits) VALUES (?,?,?,?,?)",
                (group_id, c["code"], c["name_th"], c.get("name_en"), credit))
            n_courses += 1

    conn.commit()
    conn.close()
    print(f"  โหลด elective_group {n_groups} กลุ่ม, elective_group_course {n_courses} วิชา เข้า {db}")


def cmd_load_prerequisites(args) -> None:
    """สกัดวิชาบังคับก่อนของทุกวิชาใน `course` จากข้อความ OCR ทั้งเล่ม (ภาคผนวกคำอธิบายรายวิชา) แล้วโหลดตาราง `prerequisite`

    กฎเชิงกำหนด ไม่เรียก LLM ไม่ใช้เฉลย (prereq_from_book.py) — "ไม่เดา": วิชาที่หาช่องวิชาบังคับก่อนไม่เจอ/อ่านไม่ออก
    จะไม่ถูกเติมแถวใดเลย และถูกบันทึกในรายงานว่า not_found/unreadable (ไม่ได้แปลว่าไม่มีวิชาบังคับก่อน)
    "A หรือ B" เก็บเป็นสองแถว kind='pre' แยกรหัส และระบุว่าเป็นทางเลือกกันในตาราง prerequisite_alt (PREREQ_ALT_DDL)
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from prereq_from_book import extract_prerequisites

    db = Path(args.database)
    if not db.exists():
        raise SystemExit(f"ไม่พบ {db} — ต้อง `load` แผนหลักเข้าไปก่อน")
    lines = Path(args.text).read_text(encoding="utf-8").replace("\r", "").split("\n")
    conn = open_db(db)
    codes = [r[0] for r in conn.execute("SELECT code FROM course ORDER BY code")
             if re.fullmatch(r"\d{8}", r[0])]
    res = extract_prerequisites(lines, codes, known_codes=codes)

    pairs = 0
    conn.executescript(PREREQ_ALT_DDL)  # DB เดิมที่สร้างก่อนมีตารางนี้
    conn.execute("DELETE FROM prerequisite_alt")
    or_groups = 0
    for code, r in res.items():
        if r["status"] != "found":
            continue
        for req in r["requires"]:
            conn.execute("INSERT OR REPLACE INTO prerequisite VALUES (?,?,'pre')", (code, req))
            pairs += 1
        if r["op"] == "or" and len(r["requires"]) >= 2:   # "A หรือ B": ทางเลือกกัน (group_no 1 ต่อวิชา)
            or_groups += 1
            for req in r["requires"]:
                conn.execute("INSERT OR REPLACE INTO prerequisite_alt VALUES (?,?,1)", (code, req))
    conn.commit()
    counts = {s: sum(1 for r in res.values() if r["status"] == s)
              for s in ("found", "none", "not_found", "unreadable")}
    print(f"  วิชารหัสจริง {len(codes)} วิชา: พบวิชาบังคับก่อน {counts['found']} · ไม่มี {counts['none']} · "
          f"หาไม่เจอ {counts['not_found']} · อ่านไม่ออก {counts['unreadable']}  -> เติม prerequisite {pairs} คู่"
          f" (เป็นทางเลือก 'หรือ' {or_groups} วิชา -> prerequisite_alt)")
    if counts["not_found"] or counts["unreadable"]:
        print("  (หาไม่เจอ/อ่านไม่ออก = ไม่ทราบ ไม่ใช่ 'ไม่มี' — ไม่มีแถวในตาราง prerequisite สำหรับวิชาเหล่านี้)")
    if args.output:
        report = {"source_text": str(args.text), "courses": len(codes), "counts": counts,
                  "pairs_inserted": pairs, "or_groups": or_groups, "per_course": res}
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  บันทึกรายงานที่ {args.output}")


def cmd_load_plan_slots_md(args) -> None:
    """สกัดช่อง wildcard / "หรือ" / "เลือก 1 กลุ่ม" จาก Markdown ของ OCR แล้วโหลดเข้า plan_slot

    ข้อมูลมาจากผล OCR อย่างเดียว (md_plan_slots.py — กฎเชิงกำหนด ไม่กรอกมือ ไม่เรียก LLM)
    ไม่แตะ course/plan_item/v_semester_credits/verify เดิม (ดู PLAN_SLOT_DDL)
    หน่วยกิตที่อธิบายไม่ได้เทียบแถว "รวม" ของเล่ม = วิชาที่ OCR ตกจริง ถูกรายงานลงไฟล์ report
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from md_plan_slots import derive_slots, md_codes_by_term

    md = Path(args.markdown).read_text(encoding="utf-8")
    slots, term_report = derive_slots(md)
    db = Path(args.database)
    if not db.exists():
        raise SystemExit(f"ไม่พบ {db} — ต้อง `load` แผนหลักเข้าไปก่อน")

    conn = open_db(db)
    conn.executescript(PLAN_SLOT_DDL)
    program_id = conn.execute("SELECT program_id FROM program LIMIT 1").fetchone()[0]
    conn.execute("DELETE FROM plan_slot_member WHERE slot_id IN "
                 "(SELECT id FROM plan_slot WHERE program_id = ?)", (program_id,))
    conn.execute("DELETE FROM plan_slot WHERE program_id = ?", (program_id,))

    n_members = 0
    for slot in slots:
        cur = conn.execute(
            "INSERT INTO plan_slot (program_id, year, semester, kind, code, name_th,"
            " credits, note) VALUES (?,?,?,?,?,?,?,?)",
            (program_id, slot["year"], slot["semester"], slot["kind"], slot.get("code"),
             slot["name_th"], slot["credits"], slot.get("note")))
        for g_no, group in enumerate(slot.get("groups") or [], 1):
            for code in group["codes"]:
                conn.execute(
                    "INSERT OR IGNORE INTO plan_slot_member (slot_id, group_no, group_name, code)"
                    " VALUES (?,?,?,?)", (cur.lastrowid, g_no, group.get("name"), code))
                n_members += 1
    conn.commit()

    declared = conn.execute("SELECT total_credits FROM program").fetchone()[0]
    full = sum(r[0] for r in conn.execute("SELECT credits FROM v_semester_credits_full"))
    base = sum(r[0] for r in conn.execute("SELECT credits FROM v_semester_credits"))
    in_db: dict[tuple[int, int], set[str]] = {}
    for y, sm, c in conn.execute("SELECT year, semester, code FROM plan_item"):
        in_db.setdefault((y, sm), set()).add(c)
    conn.close()
    # รหัสที่ OCR อ่านได้ใน Markdown แต่หายจาก plan_item = วิชาหายที่ขั้น Markdown -> JSON (LLM)
    lost_in_json = {f"{y}/{sm}": sorted(codes - in_db.get((y, sm), set()))
                    for (y, sm), codes in md_codes_by_term(md).items()
                    if codes - in_db.get((y, sm), set())}
    unexplained = [(r["year"], r["semester"], r["unexplained"]) for r in term_report
                   if r["unexplained"]]
    report = {"source": str(args.markdown), "slots": len(slots), "members": n_members,
              "plan_item_credits": base, "with_slots_credits": full,
              "declared_total_credits": declared, "terms": term_report,
              "md_codes_missing_in_plan_item": lost_in_json}
    Path(args.database).with_name("plan_slot_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  plan_slot {len(slots)} ช่อง, สมาชิก {n_members} · หน่วยกิตรวม plan_item {base}"
          f" -> รวมช่อง {full} · ประกาศ {declared} · ขาด {declared - full}"
          + (f" · เทอมที่หน่วยกิตอธิบายไม่ได้ (OCR ตก/สับสน): {unexplained}" if unexplained else "")
          + (f" · รหัสที่อยู่ใน Markdown แต่หายจาก plan_item: {lost_in_json}" if lost_in_json else ""))


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 4 — ตรวจความสอดคล้องของข้อมูลในฐานข้อมูล 7 ข้อ
# ═══════════════════════════════════════════════════════════════════════
#
#  Pydantic ตรวจได้แค่ "แต่ละชิ้นหน้าตาถูกไหม"
#  แต่ตรวจไม่ได้ว่า "ชิ้นทั้งหมดรวมกันแล้วสมเหตุสมผลไหม"
#  เช่น รหัสวิชา 8 หลักถูกรูปแบบ แต่เป็นวิชาที่ไม่มีอยู่ในเล่ม — Pydantic ผ่าน
#
#  บทเรียนสำคัญจาก Lab 7A/7B ที่นำมาใช้ตรงนี้
#      กฎที่เตือนผิดบ่อย แย่กว่าไม่มีกฎเลย
#      เพราะเมื่อคนเห็นคำเตือนผิดสามครั้ง เขาจะเลิกอ่านคำเตือนทั้งหมด
#      รวมถึงครั้งที่สี่ที่เป็นของจริง  (alarm fatigue)
#  กฎทั้ง 7 ข้อนี้จึงถูกออกแบบให้รู้จักข้อยกเว้นที่มีอยู่จริงในหลักสูตร
# ═══════════════════════════════════════════════════════════════════════

def _sem_credits(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """
    หน่วยกิตรวมต่อภาคเรียน โดยนับ alt_group ครั้งเดียว

    ถ้าไม่มี alt_group จะนับวิชาเลือก "A หรือ B" เป็นสองวิชา
    ทำให้หน่วยกิตเกินจริงทุกภาคที่มีวิชาเลือก
    """
    return conn.execute(
        "SELECT year, semester, credits, n_courses "
        "FROM v_semester_credits ORDER BY year, semester").fetchall()


def verify_db(conn: sqlite3.Connection) -> list[dict]:
    """รันการตรวจทั้ง 7 ข้อ คืนรายการผลลัพธ์"""
    results: list[dict] = []

    def add(cid, name, ok, detail=""):
        results.append({"id": cid, "name": name, "ok": ok, "detail": detail})

    prog = conn.execute("SELECT * FROM program LIMIT 1").fetchone()
    if prog is None:
        add("CHK0", "มีข้อมูลหลักสูตร", False, "ตาราง program ว่าง")
        return results

    # ── CHK1 หน่วยกิตรวมของแผน ต้องเท่ากับที่หลักสูตรประกาศ ────────
    rows = _sem_credits(conn)
    total = sum(r["credits"] for r in rows)
    declared = prog["total_credits"]
    # ยอมให้ต่างได้ ถ้าหลักสูตรมีหมวดวิชาเลือกเสรีที่ไม่ระบุในแผนรายเทอม
    free = conn.execute(
        "SELECT COUNT(*) FROM plan_item WHERE note LIKE '%เลือกเสรี%'").fetchone()[0]
    ok = (total == declared)
    add("CHK1", "หน่วยกิตรวมของแผน = หน่วยกิตที่หลักสูตรประกาศ", ok,
        f"แผนรวม {total} · ประกาศไว้ {declared}"
        + (f" · มีวิชาเลือกเสรี {free} รายการ" if free else ""))

    # ── CHK2 ทุกรหัสในแผน ต้องมีคำอธิบายรายวิชาในเล่ม ───────────────
    orphan = conn.execute("""
        SELECT DISTINCT p.code FROM plan_item p
        LEFT JOIN course c ON c.code = p.code
        WHERE c.code IS NULL
    """).fetchall()
    add("CHK2", "ทุกรหัสวิชาในแผน มีคำอธิบายรายวิชา", not orphan,
        "ไม่พบคำอธิบายของ: " + ", ".join(r["code"] for r in orphan[:8])
        + (f" (และอีก {len(orphan) - 8})" if len(orphan) > 8 else "")
        if orphan else "ครบทุกรหัส")

    # ── CHK3 รูปแบบรหัสวิชา ────────────────────────────────────────
    bad = conn.execute("""
        SELECT code FROM (
            SELECT code FROM course UNION SELECT code FROM plan_item
        ) WHERE code GLOB '*[^0-9]*' OR LENGTH(code) <> 8
    """).fetchall()
    add("CHK3", "รหัสวิชาเป็นตัวเลข 8 หลักทุกรายการ", not bad,
        "ผิดรูปแบบ: " + ", ".join(r["code"] for r in bad[:8]) if bad else "ถูกต้องทุกรายการ")

    # ── CHK4 หน่วยกิตในแผน ต้องตรงกับหน่วยกิตในคำอธิบายรายวิชา ──────
    mismatch = conn.execute("""
        SELECT p.code, p.credits AS plan_cr, c.credits AS course_cr
        FROM plan_item p JOIN course c ON c.code = p.code
        WHERE p.credits <> c.credits
    """).fetchall()
    add("CHK4", "หน่วยกิตในแผน ตรงกับคำอธิบายรายวิชา", not mismatch,
        "; ".join(f"{r['code']} แผน {r['plan_cr']} แต่คำอธิบาย {r['course_cr']}"
                  for r in mismatch[:5]) if mismatch else "ตรงกันทุกรายการ")

    # ── CHK5 วิชาบังคับก่อน ต้องอยู่ภาคเรียนที่มาก่อนจริง ────────────
    #    ใช้ (year*10 + semester) เป็นลำดับเวลาอย่างง่าย
    viol = conn.execute("""
        SELECT r.code, r.requires,
               a.year || '/' || a.semester AS at_course,
               b.year || '/' || b.semester AS at_prereq
        FROM prerequisite r
        JOIN plan_item a ON a.code = r.code
        JOIN plan_item b ON b.code = r.requires
        WHERE r.kind = 'pre'
          AND (b.year * 10 + b.semester) >= (a.year * 10 + a.semester)
    """).fetchall()
    # "A หรือ B" (prerequisite_alt): ผ่านอย่างใดอย่างหนึ่งก็พอ — ถ้ามีทางเลือกที่อยู่ก่อนจริงอย่างน้อยหนึ่งทาง
    # ไม่นับทางเลือกที่เหลือว่าผิดลำดับ (ตารางนี้อาจยังไม่มีใน DB เดิม -> ทำงานเหมือนเดิม)
    try:
        ok_alt = {r[0] for r in conn.execute("""
            SELECT DISTINCT r.code FROM prerequisite_alt r
            JOIN plan_item a ON a.code = r.code
            JOIN plan_item b ON b.code = r.requires
            WHERE (b.year * 10 + b.semester) < (a.year * 10 + a.semester)""")}
        alts = {(r[0], r[1]) for r in conn.execute("SELECT code, requires FROM prerequisite_alt")}
        viol = [r for r in viol if not ((r["code"], r["requires"]) in alts and r["code"] in ok_alt)]
    except sqlite3.OperationalError:
        pass
    add("CHK5", "วิชาบังคับก่อน อยู่ภาคเรียนก่อนวิชาที่อ้างถึง", not viol,
        "; ".join(f"{r['code']} ({r['at_course']}) ต้องเรียน {r['requires']} "
                  f"({r['at_prereq']}) มาก่อน" for r in viol[:5])
        if viol else "ลำดับถูกต้องทุกคู่")

    # ── CHK6 ห้ามมีวิชาซ้ำในภาคเรียนเดียวกัน ───────────────────────
    dup = conn.execute("""
        SELECT year, semester, code, COUNT(*) AS n
        FROM plan_item
        WHERE alt_group IS NULL          -- วิชาเลือกกลุ่มเดียวกันไม่นับเป็นซ้ำ
        GROUP BY year, semester, code
        HAVING n > 1
    """).fetchall()
    add("CHK6", "ไม่มีวิชาซ้ำในภาคเรียนเดียวกัน", not dup,
        "; ".join(f"{r['code']} ที่ปี {r['year']}/{r['semester']} ซ้ำ {r['n']} ครั้ง"
                  for r in dup[:5]) if dup else "ไม่มีรายการซ้ำ")

    # ── CHK7 ภาระหน่วยกิตต่อภาคเรียน อยู่ในเกณฑ์ ────────────────────
    #    ข้อยกเว้นสำคัญ: ภาคสหกิจศึกษา / ฝึกงาน มีวิชาเดียว 6 หน่วยกิต
    #    ถ้าไม่ยกเว้น กฎนี้จะเตือนผิดทุกหลักสูตรที่มีสหกิจ
    #    (บทเรียนตรงจากบั๊ก has_block_course ใน Lab 7B)
    #
    #    ข้อจำกัดที่ต้องรู้ตัว: ทุกข้อยกเว้นคือจุดบอด
    #    เกณฑ์ "มีวิชา >= 6 หน่วยกิต" แปลว่าถ้าสกัดหน่วยกิตผิดจาก 3 เป็น 6
    #    ภาคเรียนนั้นจะถูกยกเว้นทันที และ CHK7 จะเงียบทั้งที่ข้อมูลผิด
    #    นี่คือราคาที่ต้องจ่ายเพื่อลดการเตือนผิด — ไม่มีกฎใดได้ทั้งสองอย่าง
    #    สิ่งที่ทำได้คือรู้ว่าจุดบอดอยู่ตรงไหน แล้วให้ CHK4 ช่วยคุมอีกชั้น
    block_rows = conn.execute("""
        SELECT DISTINCT year, semester FROM plan_item
        WHERE credits >= 6
           OR note LIKE '%สหกิจ%' OR note LIKE '%ฝึกงาน%'
           OR code IN (SELECT code FROM course
                       WHERE name_th LIKE '%สหกิจ%' OR name_th LIKE '%ฝึกงาน%')
    """).fetchall()
    block = {(r["year"], r["semester"]) for r in block_rows}
    out_of_range = []
    for r in rows:
        key = (r["year"], r["semester"])
        if key in block:
            continue                       # ภาคบล็อก ไม่ใช้เกณฑ์ปกติ
        if r["semester"] == 3:
            continue                       # ภาคฤดูร้อน หน่วยกิตน้อยเป็นปกติ
        if not (MIN_CREDITS_PER_SEM <= r["credits"] <= MAX_CREDITS_PER_SEM):
            out_of_range.append(f"ปี {r['year']}/{r['semester']} = {r['credits']} หน่วยกิต")
    add("CHK7", f"หน่วยกิตต่อภาคเรียนอยู่ระหว่าง {MIN_CREDITS_PER_SEM}"
                f"–{MAX_CREDITS_PER_SEM}", not out_of_range,
        "; ".join(out_of_range[:5]) if out_of_range
        else f"ผ่านทุกภาค (ยกเว้นภาคบล็อก {len(block)} ภาค และภาคฤดูร้อน)")

    return results


def verify_full_db(conn: sqlite3.Connection) -> list[dict]:
    """ข้อตรวจคู่ขนาน CHK1F/CHK7F — เหมือน CHK1/CHK7 แต่นับหน่วยกิตของ "ช่องตามเล่ม" (plan_slot: wildcard,
    "A หรือ B", "เลือก 1 กลุ่ม") ผ่าน v_semester_credits_full ทำให้ผลรวมเทียบกับที่เล่มประกาศได้ตรงความจริงกว่า

    เพิ่มแบบ additive: **ไม่รวมใน 7 ข้อของ verify_db** และไม่แตะ verify.json เดิม (คะแนน Lab 9/NL2SQL จึงไม่เปลี่ยน);
    ไม่มีตาราง/ข้อมูล plan_slot ในฐานข้อมูล → คืนลิสต์ว่าง (ไม่ตรวจ ไม่ใช่ "ผ่าน")
    ข้อผิดที่เหลือมาจากข้อมูลที่ OCR ทำเสียจริง (เช่น หัวกลุ่มวิชาหาย -> วิชาในกลุ่มถูกนับเป็นวิชาปกติ) ไม่ได้ซ่อนไว้"""
    has = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plan_slot'").fetchone()
    if not has or conn.execute("SELECT COUNT(*) FROM plan_slot").fetchone()[0] == 0:
        return []
    prog = conn.execute("SELECT * FROM program LIMIT 1").fetchone()
    if prog is None:
        return []
    results: list[dict] = []
    rows = conn.execute("SELECT year, semester, credits FROM v_semester_credits_full ORDER BY year, semester").fetchall()
    total_full = sum(r["credits"] for r in rows)
    total_item = sum(r["credits"] for r in _sem_credits(conn))
    declared = prog["total_credits"]
    results.append({
        "id": "CHK1F", "name": "หน่วยกิตรวมตามเล่ม (นับช่อง wildcard/หรือ/เลือก 1 กลุ่ม) = ที่หลักสูตรประกาศ",
        "ok": total_full == declared,
        "detail": f"นับรวมช่อง {total_full} · plan_item อย่างเดียว {total_item} · ประกาศไว้ {declared}"})

    block = {(r["year"], r["semester"]) for r in conn.execute("""
        SELECT DISTINCT year, semester FROM plan_item
        WHERE credits >= 6
           OR note LIKE '%สหกิจ%' OR note LIKE '%ฝึกงาน%'
           OR code IN (SELECT code FROM course
                       WHERE name_th LIKE '%สหกิจ%' OR name_th LIKE '%ฝึกงาน%')""")}
    bad = [f"ปี {r['year']}/{r['semester']} = {r['credits']} หน่วยกิต" for r in rows
           if (r["year"], r["semester"]) not in block and r["semester"] != 3
           and not (MIN_CREDITS_PER_SEM <= r["credits"] <= MAX_CREDITS_PER_SEM)]
    results.append({
        "id": "CHK7F", "name": f"หน่วยกิตต่อภาคเรียน (นับช่องตามเล่ม) อยู่ระหว่าง {MIN_CREDITS_PER_SEM}–{MAX_CREDITS_PER_SEM}",
        "ok": not bad,
        "detail": "; ".join(bad[:5]) if bad else f"ผ่านทุกภาค (ยกเว้นภาคบล็อก {len(block)} ภาค และภาคฤดูร้อน)"})
    return results


def cmd_verify(args) -> None:
    conn = open_db(args.database, readonly=True)
    results = verify_db(conn)
    full = verify_full_db(conn)
    conn.close()

    print()
    print("  ผลการตรวจความสอดคล้องของข้อมูล")
    print("  " + "=" * 74)
    n_fail = 0
    for r in results:
        mark = "ผ่าน  " if r["ok"] else "ไม่ผ่าน"
        if not r["ok"]:
            n_fail += 1
        print(f"  [{mark}] {r['id']}  {r['name']}")
        if r["detail"]:
            print(f"           {r['detail']}")
    print("  " + "=" * 74)
    print(f"  ผ่าน {len(results) - n_fail} จาก {len(results)} ข้อ")
    if n_fail:
        print()
        print("  ข้อที่ไม่ผ่านอาจเกิดได้สองทาง และต้องแยกให้ออกก่อนแก้")
        print("    (ก) สกัดผิด        -> กลับไปแก้ prompt หรือแก้ JSON")
        print("    (ข) เล่มเขียนแบบนั้นจริง -> ต้องแก้กฎให้รู้จักข้อยกเว้นนี้")
    if full:
        print()
        print("  ตรวจคู่ขนาน — นับหน่วยกิตของช่องตามเล่ม (wildcard / หรือ / เลือก 1 กลุ่ม) (ไม่รวมใน 7 ข้อข้างบน)")
        for r in full:
            print(f"  [{'ผ่าน  ' if r['ok'] else 'ไม่ผ่าน'}] {r['id']}  {r['name']}")
            print(f"           {r['detail']}")
    if args.output:
        Path(args.output).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  บันทึกผลที่ {args.output}")
        if full:
            full_path = Path(args.output).with_name(Path(args.output).stem + "_full.json")
            full_path.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  บันทึกผลตรวจคู่ขนานที่ {full_path}")


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 5 — ถามเป็นภาษาคน ตอบด้วย SQL
# ═══════════════════════════════════════════════════════════════════════

# คำสั่งที่ห้ามปรากฏใน SQL ที่ LLM สร้าง
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|"
    r"pragma|vacuum|reindex|truncate)\b", re.I)


def guard_sql(sql: str) -> str:
    """
    ด่านความปลอดภัยชั้นที่สอง — ตรวจ SQL ก่อนรัน

    ชั้นที่หนึ่งคือการเปิดฐานข้อมูลแบบอ่านอย่างเดียว
    ทำไมต้องมีสองชั้น: ชั้นแรกกันการ "แก้ข้อมูล" ได้ก็จริง
    แต่กันการดึงข้อมูลจนล้น หรือ query ที่รันไม่จบไม่ได้
    ชั้นนี้จึงเสริมเรื่องนั้น และทำให้ข้อผิดพลาดอ่านง่ายขึ้นด้วย
    """
    s = sql.strip().rstrip(";").strip()
    if not s:
        raise ValueError("SQL ว่างเปล่า")
    if ";" in s:
        raise ValueError("ห้ามมีหลายคำสั่งใน query เดียว")
    if not re.match(r"^\s*(select|with)\b", s, re.I):
        raise ValueError("อนุญาตเฉพาะ SELECT หรือ WITH เท่านั้น")
    if FORBIDDEN_SQL.search(s):
        raise ValueError("พบคำสั่งที่ไม่อนุญาตใน SQL")
    if not re.search(r"\blimit\b", s, re.I):
        s += f" LIMIT {SQL_ROW_LIMIT}"
    return s


SQL_PROMPT = """คุณคือผู้ช่วยแปลงคำถามภาษาไทยเป็นคำสั่ง SQL ของ SQLite

โครงสร้างฐานข้อมูล
{ddl}

ตัวอย่าง
คำถาม: ปี 2 เทอม 1 เรียนกี่หน่วยกิต
SQL: SELECT credits FROM v_semester_credits WHERE year=2 AND semester=1

คำถาม: วิชาไหนบ้างที่ต้องเรียน 06026240 มาก่อน
SQL: SELECT code FROM prerequisite WHERE requires='06026240' AND kind='pre'

คำถาม: ต้องเรียนวิชาอะไรมาก่อนจึงจะลงเรียน 06026215 ได้
SQL: SELECT requires FROM prerequisite WHERE code='06026215' AND kind='pre'

คำถาม: วิชาที่ต้องผ่าน CALCULUS 1 (06026200) มาก่อน มีกี่วิชา
SQL: SELECT COUNT(*) FROM prerequisite WHERE requires='06026200' AND kind='pre'

คำถาม: มีวิชาใดบ้างในหลักสูตรที่เป็นวิชาเรียนควบ
SQL: SELECT code FROM prerequisite WHERE kind='co'

คำถาม: หลักสูตรนี้มีกี่หน่วยกิต
SQL: SELECT total_credits FROM program

คำถาม: ค่าเทอมของหลักสูตรนี้ภาคเรียนละเท่าไหร่
SQL: SELECT NULL WHERE 0

กติกา
- เขียน SQL คำสั่งเดียว ขึ้นต้นด้วย SELECT หรือ WITH เท่านั้น
- ห้ามใช้ INSERT UPDATE DELETE DROP หรือคำสั่งที่แก้ไขข้อมูล
- ถามว่าภาคเรียนไหนมีกี่หน่วยกิต ให้ใช้ v_semester_credits เสมอ
  ห้ามใช้ SUM(credits) จาก v_plan เพราะจะนับวิชาเลือกซ้ำ
- ถามว่าเรียนวิชาอะไรบ้าง ให้ใช้ v_plan เพราะมีชื่อวิชาอยู่แล้ว
- คำถามเรื่อง "วิชาบังคับก่อน / ต้องผ่านวิชาใดก่อน / วิชาไหนใช้ X เป็นบังคับก่อน /
  วิชาเรียนควบ" ให้ query ตาราง prerequisite เสมอ (join ผ่านคอลัมน์ code/requires)
  ห้ามใช้ LIKE กับ name_th หรือ name_en เพื่อเดาความสัมพันธ์วิชาบังคับก่อน
- ถ้าคำถามถามถึงสิ่งที่ "ไม่มีคอลัมน์หรือตารางรองรับในโครงสร้างข้างบนเลย"
  (เช่น ค่าเทอม/ค่าธรรมเนียม, ชื่ออาจารย์ผู้สอน, ห้องเรียน, ตำราเรียน, ตารางสอบ)
  ห้ามเดา SQL ที่ดูใกล้เคียง ให้ตอบว่า  SELECT NULL WHERE 0  เท่านั้น
- ตอบเป็น SQL ล้วน ไม่ต้องมีคำอธิบายและไม่ต้องมี markdown fence

คำถาม: {question}
SQL:"""

ANSWER_PROMPT = """ตอบคำถามต่อไปนี้เป็นภาษาไทย โดยใช้ผลลัพธ์จากฐานข้อมูลเท่านั้น

คำถาม: {question}

ผลลัพธ์จากฐานข้อมูล (รูปแบบ JSON):
{rows}

ตัวอย่างการตอบ (ค่าในคำตอบต้องตรงกับ JSON เป๊ะ ห้ามพิมพ์ผิด/แต่งเลขเอง)
- ผลลัพธ์ [{{"total_credits": 132}}]   ถามหน่วยกิต  -> "132 หน่วยกิต"
- ผลลัพธ์ [{{"years": 4}}]             ถามชั้นปี    -> "ปีที่ 4"
- ผลลัพธ์ [{{"lab_h": 2}}]             ถามชั่วโมง   -> "2 ชั่วโมง"
- ผลลัพธ์ [{{"COUNT(*)": 20}}]         ถามจำนวนวิชา -> "20 วิชา"
- ผลลัพธ์ [{{"COUNT(*)": 0}}]          ถามจำนวน     -> "ไม่มีเลย (0 รายการ)"
- ผลลัพธ์ [{{"code": "90641001"}}]     ถามรหัสวิชา  -> "90641001"
- ผลลัพธ์ [{{"name_th": "แคลคูลัส 1"}}] ถามชื่อวิชา  -> "แคลคูลัส 1"
- ผลลัพธ์ [{{"code":"A"}},{{"code":"B"}},{{"code":"C"}}]  -> "A, B, C"
- ผลลัพธ์ []                                          -> "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"

กติกา
- ใช้เฉพาะตัวเลขและข้อความที่ปรากฏในผลลัพธ์ ห้ามเพิ่มข้อมูลจากความรู้ของคุณเอง
- ผลลัพธ์ "แถวเดียว ค่าเดียว": ตอบเป็นวลีสั้น ๆ ที่เป็นธรรมชาติ ใส่หน่วย/บริบทให้เข้ากับคำถาม
  (ถามหน่วยกิต -> "... หน่วยกิต", ถามชั่วโมง -> "... ชั่วโมง", ถามจำนวนวิชา -> "... วิชา",
  ถามชั้นปี -> "ปีที่ ...") — ตัวเลข/ค่าต้องตรงกับ JSON เป๊ะ
- ผลลัพธ์ "หลายแถว/หลายค่า" (เช่น รายชื่อรหัสวิชา): คัดลอกค่าจาก JSON ตรง ๆ ทีละตัว
  คั่นด้วย ", " ห้ามเรียบเรียง/ย่อ/สลับหลัก/แต่งประโยคอ้อมค้อม
- "ผลลัพธ์ว่างเปล่า" คือ JSON ข้างบนเป็น [] (ไม่มีแถวเลย) เท่านั้น กรณีนี้ให้ตอบว่า
  "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"
- ถ้ามีอย่างน้อย 1 แถว ห้ามตอบว่า "ไม่พบ" หรือ "ไม่มีข้อมูล" ต้องตอบด้วยค่าจากแถวนั้น
  แม้ค่าที่ได้ (เช่น COUNT) จะเป็น 0 ก็ตอบว่า "0" (หรือ "ไม่มีเลย (0 รายการ)")
  ไม่ใช่ "ไม่พบข้อมูล"
- ตอบเป็น JSON รูปแบบ {{"answer": "คำตอบภาษาไทย"}} เท่านั้น
"""


def clean_sql_output(s: str) -> str:
    """ตัด <think> และ fence ออกจาก SQL ที่โมเดลตอบมา"""
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    s = re.sub(r"```(?:sql)?", "", s).strip()
    # งานนี้ใช้ query บรรทัดเดียว: เก็บเฉพาะบรรทัด SQL แรก
    # เพื่อไม่ให้ reasoning หรือคำอธิบายที่หลุดมาถูกส่งเข้า SQLite
    m = re.search(r"(?im)^\s*(select|with)\b[^\r\n]*", s)
    return m.group(0).strip() if m else s


def ask(conn: sqlite3.Connection, question: str,
        verbose: bool = True) -> dict:
    """
    ถามหนึ่งคำถาม — คืน dict ที่มี sql, rows, answer, error

    ขั้นตอน: สร้าง SQL -> ตรวจ -> รัน -> สรุปเป็นภาษาไทย
    ถ้ารันไม่ผ่าน จะให้โมเดลลองใหม่หนึ่งครั้งพร้อมข้อความ error
    แล้วถ้ายังไม่ผ่านอีก ให้ยอมแพ้ ไม่เดาคำตอบ
    """
    result: dict[str, Any] = {
        "question": question, "sql": None, "rows": [], "answer": None,
        "error": None, "sql_model_output": None, "answer_model_output": None,
    }
    ddl = DDL.strip()
    prompt = SQL_PROMPT.format(ddl=ddl, question=question)

    for attempt in range(2):
        try:
            raw_sql = ollama_generate(
                prompt + '\nตอบเป็น JSON รูปแบบ {"sql": "SELECT ..."} เท่านั้น',
                fmt={
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                    "additionalProperties": False,
                }, num_ctx=4096, num_predict=256)
            result["sql_model_output"] = raw_sql
            parsed_sql = parse_json_loose(raw_sql)
            sql = clean_sql_output(
                str(parsed_sql.get("sql", "")) if isinstance(parsed_sql, dict)
                else raw_sql)
            sql = guard_sql(sql)
            result["sql"] = sql
            rows = [dict(r) for r in conn.execute(sql).fetchall()]
            result["rows"] = rows
            result["error"] = None
            break
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"
            if verbose:
                print(f"    รอบที่ {attempt + 1} รันไม่ผ่าน: {e}")
            if attempt == 1:
                result["answer"] = "ไม่สามารถตอบคำถามนี้ได้ กรุณาตรวจสอบเอง"
                return result
            prompt = (SQL_PROMPT.format(ddl=ddl, question=question)
                      + f"\n\nSQL ที่ลองไปแล้วมีข้อผิดพลาด: {e}\nเขียนใหม่ให้ถูก\nSQL:")

    # ปฏิเสธที่จะเดา เมื่อไม่มีข้อมูล — จุดนี้สำคัญกว่าที่คิด
    if not result["rows"]:
        result["answer"] = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"
        return result

    raw_answer = ollama_generate(
        ANSWER_PROMPT.format(
            question=question,
            rows=json.dumps(result["rows"][:40], ensure_ascii=False)),
        fmt={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        }, num_ctx=4096, num_predict=256).strip()
    result["answer_model_output"] = raw_answer
    parsed_answer = parse_json_loose(raw_answer)
    result["answer"] = (
        str(parsed_answer.get("answer", "")).strip()
        if isinstance(parsed_answer, dict) else raw_answer)
    result["answer"] = re.sub(
        r"<think>.*?</think>", "", result["answer"], flags=re.S).strip()

    # ตัวกันเชิงกำหนดแน่สำหรับคำตอบหลายค่า — qwen3:4b มักคัดลอกรหัสวิชา/ตัวเลข
    # หลายตัวในสตริงเดียวผิด (เช่น "06066303" -> "0606630 03", สลับหลัก, เว้นวรรคเกิน)
    # ถ้าผลลัพธ์เป็นรายการค่าเดี่ยวสั้น ๆ หลายแถว และคำตอบของโมเดลยังมีไม่ครบทุกค่า
    # ให้ประกอบคำตอบเองจากค่าในแถวตรง ๆ (score_one เทียบที่แถว SQL อยู่แล้ว
    # ตัวนี้แค่ทำให้ "ข้อความคำตอบ" ตรงกับข้อมูลจริงด้วย)
    flat = [str(v).strip() for r in result["rows"] if len(r) == 1
            for v in r.values() if v is not None]
    if len(flat) == len(result["rows"]) >= 2 and all(len(v) <= 40 for v in flat):
        seen: list[str] = []
        for v in flat:
            if v and v not in seen:
                seen.append(v)
        if seen and not all(v in result["answer"] for v in seen):
            result["answer"] = ", ".join(seen)
    return result


def cmd_ask(args) -> None:
    conn = open_db(args.database, readonly=True)
    r = ask(conn, args.question)
    conn.close()
    print()
    print(f"  คำถาม : {r['question']}")
    print(f"  SQL   : {r['sql']}")
    print(f"  แถว   : {len(r['rows'])}")
    print(f"  คำตอบ : {r['answer']}")
    print(f"  Raw SQL   : {r['sql_model_output']}")
    print(f"  Raw answer: {r['answer_model_output']}")
    if r["error"]:
        print(f"  หมายเหตุ: {r['error']}")


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 6 — ประเมินด้วยชุดคำถามทอง
# ═══════════════════════════════════════════════════════════════════════
#
#  วิธีให้คะแนน: เทียบที่ "ผลลัพธ์ของ SQL" ไม่ใช่ "ข้อความคำตอบ"
#
#  ถ้าเทียบข้อความ จะเจอปัญหาว่า "19 หน่วยกิต" กับ "รวม 19 หน่วยกิต"
#  ควรได้คะแนนเท่ากัน แต่เทียบตรง ๆ จะนับเป็นผิด
#  การเทียบที่ค่าตัวเลข/ชุดรหัสวิชาจึงยุติธรรมและทำอัตโนมัติได้จริง
# ═══════════════════════════════════════════════════════════════════════

def _values_of(rows: list[dict]) -> set[str]:
    """ดึงค่าทั้งหมดในผลลัพธ์ออกมาเป็นชุดข้อความ เพื่อเทียบแบบไม่สนลำดับคอลัมน์"""
    out = set()
    for r in rows:
        for v in r.values():
            if v is not None:
                out.add(str(v).strip())
    return out


def score_one(expect: dict, got: dict) -> tuple[bool, str]:
    """
    ให้คะแนนหนึ่งข้อ ตามชนิดของคำถาม

    value  — ต้องมีค่านี้อยู่ในผลลัพธ์
    set    — ชุดคำตอบต้องตรงกันทั้งหมด (ใช้กับคำถาม "มีวิชาอะไรบ้าง")
    count  — จำนวนแถวต้องเท่ากับที่คาด
    none   — ต้องตอบว่าไม่พบ (ใช้ทดสอบว่าระบบยอมรับได้ว่าไม่รู้)
    """
    kind = expect.get("type", "value")
    rows = got.get("rows") or []
    vals = _values_of(rows)

    if kind == "none":
        ok = (len(rows) == 0)
        return ok, "ตอบว่าไม่พบตามที่ควร" if ok else f"ควรไม่พบ แต่ได้ {len(rows)} แถว"

    if kind == "count":
        ok = (len(rows) == int(expect["value"]))
        return ok, f"ได้ {len(rows)} แถว คาด {expect['value']}"

    if kind == "set":
        want = {str(x).strip() for x in expect["value"]}
        ok = want.issubset(vals)
        missing = want - vals
        return ok, "ครบ" if ok else f"ขาด {', '.join(sorted(missing)[:5])}"

    want = str(expect["value"]).strip()
    ok = want in vals
    return ok, "ตรง" if ok else f"ไม่พบค่า {want} (ได้ {sorted(vals)[:5]})"


def cmd_eval(args) -> None:
    conn = open_db(args.database, readonly=True)
    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    rows_out = []
    n_ok = n_sql_ok = 0

    print(f"  ประเมิน {len(questions)} คำถาม")
    print("  " + "-" * 74)
    for i, q in enumerate(questions, 1):
        t0 = time.time()
        got = ask(conn, q["question"], verbose=False)
        ok, why = score_one(q["expect"], got)
        sql_ok = got["error"] is None
        n_ok += ok
        n_sql_ok += sql_ok
        rows_out.append({**q, "sql": got["sql"], "n_rows": len(got["rows"]),
                         "error": got["error"],
                         "sql_model_output": got["sql_model_output"],
                         "answer_model_output": got["answer_model_output"],
                         "answer": got["answer"], "correct": ok, "why": why,
                         "seconds": round(time.time() - t0, 1)})
        print(f"  {i:>2}. [{'ถูก ' if ok else 'ผิด'}] {q['question'][:44]:<46} {why[:26]}")
    conn.close()

    print("  " + "-" * 74)
    n = len(questions)
    print(f"  SQL รันผ่าน   {n_sql_ok}/{n}  ({n_sql_ok / n:.0%})")
    print(f"  ตอบถูก        {n_ok}/{n}  ({n_ok / n:.0%})")
    print()
    print("  แยกสองตัวเลขนี้เสมอ เพราะมันบอกคนละเรื่อง")
    print("    SQL รันผ่านแต่ตอบผิด = โมเดลเข้าใจคำถามผิด (แก้ที่ prompt/ตัวอย่าง)")
    print("    SQL รันไม่ผ่าน       = โมเดลเขียน SQL ไม่เป็น (แก้ที่ schema/VIEW)")

    if args.output:
        Path(args.output).write_text(
            json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  บันทึกผลที่ {args.output}")


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 7 — ข้อมูลตัวอย่างสำหรับทดลอง
# ═══════════════════════════════════════════════════════════════════════

DEMO_JSON = {
    "program": {
        "program_id": "IT2565",
        # หมายเหตุ: นี่คือหลักสูตร "ฉบับย่อ" ที่ตัดเหลือ 2 ปีเพื่อใช้ฝึกปฏิบัติ
        # ตัวเลขทุกตัวสอดคล้องกันเอง กฎตรวจทั้ง 7 ข้อจึงต้องผ่านหมด
        # ถ้ากฎข้อใดเตือนกับข้อมูลชุดนี้ แปลว่ากฎข้อนั้นเขียนผิด ไม่ใช่ข้อมูลผิด
        "name_th": "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (ฉบับย่อสำหรับฝึกปฏิบัติ)",
        "name_en": "Bachelor of Science Program in Information Technology (abridged)",
        "degree": "วท.บ. (เทคโนโลยีสารสนเทศ)",
        "total_credits": 39,
        "years": 2,
    },
    "courses": [
        {"code": "06026101", "name_th": "คณิตศาสตร์สำหรับเทคโนโลยีสารสนเทศ",
         "name_en": "Mathematics for IT", "credits": 3,
         "lecture_h": 3, "lab_h": 0, "self_h": 6, "description_th": None},
        {"code": "06026102", "name_th": "การเขียนโปรแกรมคอมพิวเตอร์",
         "name_en": "Computer Programming", "credits": 3,
         "lecture_h": 2, "lab_h": 3, "self_h": 5, "description_th": None},
        {"code": "06026103", "name_th": "โครงสร้างข้อมูลและอัลกอริทึม",
         "name_en": "Data Structures and Algorithms", "credits": 3,
         "lecture_h": 2, "lab_h": 3, "self_h": 5, "description_th": None},
        {"code": "06026104", "name_th": "ระบบฐานข้อมูล",
         "name_en": "Database Systems", "credits": 3,
         "lecture_h": 2, "lab_h": 3, "self_h": 5, "description_th": None},
        {"code": "06026240", "name_th": "การพัฒนาระบบอัจฉริยะ",
         "name_en": "Intelligent System Development", "credits": 3,
         "lecture_h": 2, "lab_h": 3, "self_h": 5, "description_th": None},
        {"code": "06026241", "name_th": "คอมพิวเตอร์วิทัศน์",
         "name_en": "Computer Vision", "credits": 3,
         "lecture_h": 2, "lab_h": 3, "self_h": 5, "description_th": None},
        {"code": "06026259", "name_th": "การประมวลผลภาษาธรรมชาติ",
         "name_en": "Natural Language Processing", "credits": 3,
         "lecture_h": 3, "lab_h": 0, "self_h": 6, "description_th": None},
        {"code": "06026260", "name_th": "การเรียนรู้เชิงลึก",
         "name_en": "Deep Learning", "credits": 3,
         "lecture_h": 3, "lab_h": 0, "self_h": 6, "description_th": None},
        {"code": "06026390", "name_th": "สหกิจศึกษาทางเทคโนโลยีสารสนเทศ",
         "name_en": "Cooperative Education in IT", "credits": 6,
         "lecture_h": 0, "lab_h": 0, "self_h": 0, "description_th": None},
        {"code": "90130001", "name_th": "ภาษาอังกฤษเพื่อการสื่อสาร",
         "name_en": "English for Communication", "credits": 3,
         "lecture_h": 3, "lab_h": 0, "self_h": 6, "description_th": None},
        {"code": "90130002", "name_th": "ภาษาอังกฤษเชิงวิชาการ",
         "name_en": "Academic English", "credits": 3,
         "lecture_h": 3, "lab_h": 0, "self_h": 6, "description_th": None},
        {"code": "90230001", "name_th": "มนุษย์กับสังคม",
         "name_en": "Human and Society", "credits": 3,
         "lecture_h": 3, "lab_h": 0, "self_h": 6, "description_th": None},
        {"code": "90330001", "name_th": "กีฬาและนันทนาการ",
         "name_en": "Sports and Recreation", "credits": 3,
         "lecture_h": 1, "lab_h": 4, "self_h": 4, "description_th": None},
    ],
    "plan": [
        {"year": 1, "semester": 1, "code": "06026101", "credits": 3,
         "alt_group": None, "note": None},
        {"year": 1, "semester": 1, "code": "06026102", "credits": 3,
         "alt_group": None, "note": None},
        {"year": 1, "semester": 1, "code": "90130001", "credits": 3,
         "alt_group": None, "note": None},
        {"year": 1, "semester": 1, "code": "90230001", "credits": 3,
         "alt_group": None, "note": None},
        {"year": 1, "semester": 2, "code": "06026103", "credits": 3,
         "alt_group": None, "note": None},
        {"year": 1, "semester": 2, "code": "06026104", "credits": 3,
         "alt_group": None, "note": None},
        {"year": 1, "semester": 2, "code": "90130002", "credits": 3,
         "alt_group": None, "note": None},
        {"year": 1, "semester": 2, "code": "90330001", "credits": 3,
         "alt_group": None, "note": None},
        {"year": 2, "semester": 1, "code": "06026240", "credits": 3,
         "alt_group": None, "note": None},
        {"year": 2, "semester": 1, "code": "06026241", "credits": 3,
         "alt_group": None, "note": None},
        # วิชาเลือกอย่างใดอย่างหนึ่ง — สองแถว alt_group เดียวกัน
        {"year": 2, "semester": 1, "code": "06026259", "credits": 3,
         "alt_group": "elect_y2s1", "note": "เลือกอย่างใดอย่างหนึ่ง"},
        {"year": 2, "semester": 1, "code": "06026260", "credits": 3,
         "alt_group": "elect_y2s1", "note": "เลือกอย่างใดอย่างหนึ่ง"},
        # ภาคสหกิจศึกษา — วิชาเดียว 6 หน่วยกิต (ทดสอบข้อยกเว้นของ CHK7)
        {"year": 2, "semester": 2, "code": "06026390", "credits": 6,
         "alt_group": None, "note": "ภาคสหกิจศึกษา"},
    ],
    "prerequisites": [
        {"code": "06026103", "requires": "06026102", "kind": "pre"},
        {"code": "06026240", "requires": "06026103", "kind": "pre"},
        {"code": "06026259", "requires": "06026103", "kind": "pre"},
        # เรียนควบ (co) ไม่ถูกตรวจด้วย CHK5 เพราะอยู่ภาคเดียวกันได้ตามระเบียบ
        {"code": "06026241", "requires": "06026240", "kind": "co"},
        {"code": "06026390", "requires": "06026240", "kind": "pre"},
    ],
}

DEMO_QUESTIONS = [
    # คำถามถูกออกแบบให้ "ตรวจอัตโนมัติได้" คือคำตอบเป็นค่าเดียวหรือชุดรหัสวิชา
    # หลีกเลี่ยงคำถามที่ตอบได้หลายรูปแบบ เช่น "อธิบายหลักสูตรนี้"
    # เพราะจะให้คะแนนอัตโนมัติไม่ได้ และไม่บอกอะไรเกี่ยวกับคุณภาพ SQL
    {"question": "หลักสูตรนี้มีทั้งหมดกี่หน่วยกิต",
     "expect": {"type": "value", "value": 39}},
    {"question": "หลักสูตรนี้ใช้เวลาเรียนกี่ปี",
     "expect": {"type": "value", "value": 2}},
    {"question": "ปี 1 เทอม 1 เรียนกี่หน่วยกิต",
     "expect": {"type": "value", "value": 12}},
    {"question": "ปี 1 เทอม 1 เรียนวิชาอะไรบ้าง",
     "expect": {"type": "set",
                "value": ["06026101", "06026102", "90130001", "90230001"]}},
    {"question": "ปี 2 เทอม 1 เรียนกี่หน่วยกิต",
     "expect": {"type": "value", "value": 9}},
    {"question": "วิชาการพัฒนาระบบอัจฉริยะมีรหัสอะไร",
     "expect": {"type": "value", "value": "06026240"}},
    {"question": "วิชา 06026240 มีกี่หน่วยกิต",
     "expect": {"type": "value", "value": 3}},
    {"question": "วิชา 06026104 ชื่อภาษาอังกฤษว่าอะไร",
     "expect": {"type": "value", "value": "Database Systems"}},
    {"question": "ต้องเรียนวิชาอะไรมาก่อนจึงจะลงเรียน 06026240 ได้",
     "expect": {"type": "value", "value": "06026103"}},
    {"question": "วิชาไหนใช้ 06026240 เป็นวิชาบังคับก่อน",
     "expect": {"type": "value", "value": "06026390"}},
    {"question": "วิชาคอมพิวเตอร์วิทัศน์อยู่ชั้นปีที่เท่าไร",
     "expect": {"type": "value", "value": 2}},
    {"question": "วิชาสหกิจศึกษามีกี่หน่วยกิต",
     "expect": {"type": "value", "value": 6}},
    {"question": "วิชา 90330001 มีชั่วโมงปฏิบัติการกี่ชั่วโมง",
     "expect": {"type": "value", "value": 4}},
    {"question": "ปี 2 เทอม 1 มีวิชาเลือกอย่างใดอย่างหนึ่งคือวิชาอะไรบ้าง",
     "expect": {"type": "set", "value": ["06026259", "06026260"]}},
    # สองข้อสุดท้ายทดสอบสิ่งที่สำคัญที่สุด คือระบบต้องยอมรับได้ว่า "ไม่รู้"
    # ระบบที่ตอบทุกคำถามได้เสมอ คือระบบที่แต่งคำตอบเมื่อไม่มีข้อมูล
    {"question": "วิชา 06026999 ชื่ออะไร",
     "expect": {"type": "none", "value": None}},
    {"question": "ปี 7 เทอม 1 เรียนวิชาอะไรบ้าง",
     "expect": {"type": "none", "value": None}},
]


def markdown_from_demo(d: dict) -> str:
    """สร้าง Markdown เลียนแบบผลลัพธ์ของ Lab 7B เพื่อใช้ทดสอบคำสั่ง extract"""
    L = [f"# {d['program']['name_th']}", "",
         f"{d['program']['name_en']}", "",
         f"ชื่อปริญญา: {d['program']['degree']}",
         f"จำนวนหน่วยกิตรวมตลอดหลักสูตร: {d['program']['total_credits']} หน่วยกิต",
         f"ระยะเวลาการศึกษา: {d['program']['years']} ปี", "",
         "## คำอธิบายรายวิชา", "",
         "| รหัสวิชา | ชื่อวิชา | หน่วยกิต | ท-ป-อ |",
         "|---|---|---|---|"]
    for c in d["courses"]:
        L.append(f"| {c['code']} | {c['name_th']} ({c['name_en']}) | "
                 f"{c['credits']} | {c['lecture_h']}-{c['lab_h']}-{c['self_h']} |")
    L += ["", "## แผนการศึกษา", ""]
    names = {c["code"]: c["name_th"] for c in d["courses"]}
    seen = set()
    for p in d["plan"]:
        key = (p["year"], p["semester"])
        if key not in seen:
            seen.add(key)
            L += ["", f"### ปีที่ {p['year']} ภาคการศึกษาที่ {p['semester']}", "",
                  "| รหัสวิชา | ชื่อวิชา | หน่วยกิต |", "|---|---|---|"]
        L.append(f"| {p['code']} | {names.get(p['code'], '')} | {p['credits']} |"
                 + (f"  <!-- {p['note']} -->" if p.get("note") else ""))
    L += ["", "## เงื่อนไขรายวิชา", ""]
    for r in d["prerequisites"]:
        word = "วิชาบังคับก่อน" if r["kind"] == "pre" else "วิชาเรียนควบ"
        L.append(f"- {r['code']} : {word} {r['requires']}")
    return "\n".join(L)


def cmd_demo(args) -> None:
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "curriculum.md").write_text(markdown_from_demo(DEMO_JSON), encoding="utf-8")
    (out / "curriculum_demo.json").write_text(
        json.dumps(DEMO_JSON, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "gold_questions.json").write_text(
        json.dumps(DEMO_QUESTIONS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  เขียน {out}/curriculum.md          (ใช้ทดสอบคำสั่ง extract)")
    print(f"  เขียน {out}/curriculum_demo.json   (JSON ที่ถูกต้อง ใช้ข้าม extract ได้)")
    print(f"  เขียน {out}/gold_questions.json    ({len(DEMO_QUESTIONS)} คำถาม)")
    print()
    print("  ทดลองทั้งสายโดยไม่ต้องรอ LLM สกัด:")
    print(f"    python3 lab8b_curriculum_db.py load "
          f"-i {out}/curriculum_demo.json -d {out}/curriculum.db --replace")
    print(f"    python3 lab8b_curriculum_db.py verify -d {out}/curriculum.db")


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 8 — selftest
# ═══════════════════════════════════════════════════════════════════════

def cmd_selftest(args=None) -> bool:
    print("=" * 68)
    print("  selftest — ตรวจ schema, กฎตรวจ, และด่านความปลอดภัย SQL")
    print("=" * 68)
    passed = failed = 0

    def ck(name, got, want):
        nonlocal passed, failed
        if got == want:
            print(f"  [ ok ] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}: ได้ {got!r} ต้องการ {want!r}")
            failed += 1

    # ── 1. Pydantic schema ──────────────────────────────────────────
    try:
        from pydantic import ValidationError
        Curriculum = build_models()
        ok_obj = Curriculum.model_validate(DEMO_JSON)
        ck("ข้อมูลตัวอย่างผ่าน schema", ok_obj.program.total_credits, 39)

        bad = json.loads(json.dumps(DEMO_JSON))
        bad["courses"][0]["code"] = "0602610"          # 7 หลัก
        try:
            Curriculum.model_validate(bad)
            ck("จับรหัสวิชาผิดรูปแบบ", False, True)
        except ValidationError as e:
            ck("จับรหัสวิชาผิดรูปแบบ", "8 หลัก" in format_errors(e), True)

        bad2 = json.loads(json.dumps(DEMO_JSON))
        bad2["plan"][0]["semester"] = 5                # เทอมต้อง 1-3
        try:
            Curriculum.model_validate(bad2)
            ck("จับเทอมนอกช่วง", False, True)
        except ValidationError as e:
            ck("จับเทอมนอกช่วง", "plan -> 0 -> semester" in format_errors(e), True)

        # JSON จาก Lab 7B ต้องแปลได้โดยไม่เรียก LLM
        lab7b_sample = {
            "program": "TEST",
            "courses": [
                {"code": "06026240", "name_th": "วิชาหนึ่ง",
                 "credits": "3(2-2-5)", "year": 1, "semester": 1,
                 "prerequisite": "ไม่มี"},
                {"code": "06026241", "name_th": "วิชาสอง",
                 "credits": "3(3-0-6)", "year": 2, "semester": 1,
                 "prerequisite": "06026240"},
                {"code": "06026xxx", "name_th": "ช่องวิชาเลือก",
                 "credits": "3(3-0-6)", "year": 2, "semester": 1,
                 "prerequisite": "ไม่มี"},
            ],
        }
        converted, report = convert_lab7b(
            lab7b_sample, total_credits=30, years=4)
        ck("import Lab 7B แยกหน่วยกิตและชั่วโมง",
           (converted["courses"][0]["credits"],
            converted["courses"][0]["lecture_h"],
            converted["courses"][0]["lab_h"],
            converted["courses"][0]["self_h"]), (3, 2, 2, 5))
        ck("import Lab 7B แยก prerequisite",
           converted["prerequisites"],
           [{"code": "06026241", "requires": "06026240", "kind": "pre"}])
        ck("import Lab 7B ไม่เดารหัส wildcard",
           report["skipped_wildcards"], 1)
    except ImportError:
        print("  [skip] ไม่มี pydantic จึงข้ามการทดสอบ schema")

    # ── 2. ด่านความปลอดภัย SQL ──────────────────────────────────────
    ck("เติม LIMIT ให้อัตโนมัติ",
       "LIMIT" in guard_sql("SELECT * FROM course"), True)
    ck("ไม่เติม LIMIT ซ้ำ",
       guard_sql("SELECT 1 LIMIT 5").count("LIMIT"), 1)
    for bad_sql, why in [("DROP TABLE course", "DROP"),
                         ("SELECT 1; DELETE FROM course", "หลายคำสั่ง"),
                         ("UPDATE course SET credits=0", "UPDATE"),
                         ("PRAGMA table_info(course)", "PRAGMA")]:
        try:
            guard_sql(bad_sql)
            ck(f"ปฏิเสธ {why}", False, True)
        except ValueError:
            ck(f"ปฏิเสธ {why}", True, True)
    ck("ยอมรับ WITH", guard_sql("WITH x AS (SELECT 1) SELECT * FROM x")[:4], "WITH")

    # ── 3. clean_sql_output ─────────────────────────────────────────
    ck("ตัด think ออกจาก SQL",
       clean_sql_output("<think>คิด</think>```sql\nSELECT 1\n```"), "SELECT 1")

    # ── 4. กฎตรวจ 7 ข้อ บนข้อมูลที่ถูกต้อง — ต้องไม่เตือนผิดเลย ────
    db = Path(tempfile.gettempdir()) / "_lab8b_selftest.db"
    if db.exists():
        db.unlink()
    conn = open_db(db)
    conn.executescript(DDL)
    _load_dict(conn, DEMO_JSON)
    res = verify_db(conn)
    fails = [r["id"] for r in res if not r["ok"]]
    ck("ข้อมูลถูกต้องไม่ทำให้กฎเตือนผิด (false alarm = 0)", fails, [])

    # หน่วยกิตรวมต้องนับ alt_group ครั้งเดียว
    rows = {(r["year"], r["semester"]): r["credits"] for r in _sem_credits(conn)}
    ck("นับวิชาเลือกอย่างใดอย่างหนึ่งครั้งเดียว", rows[(2, 1)], 9)
    ck("ภาคสหกิจนับได้ 6 หน่วยกิต", rows[(2, 2)], 6)

    # ── 5. กฎต้องจับความผิดจริงได้ด้วย ──────────────────────────────
    conn.execute("UPDATE plan_item SET credits = 5 WHERE code = '06026240'")
    res2 = {r["id"]: r["ok"] for r in verify_db(conn)}
    ck("CHK4 จับหน่วยกิตไม่ตรงกัน", res2["CHK4"], False)
    conn.execute("UPDATE plan_item SET credits = 3 WHERE code = '06026240'")

    conn.execute("INSERT INTO plan_item (program_id, year, semester, code,"
                 " credits) VALUES ('IT2565', 1, 1, '06026777', 3)")
    res3 = {r["id"]: r["ok"] for r in verify_db(conn)}
    ck("CHK2 จับรหัสที่ไม่มีคำอธิบาย", res3["CHK2"], False)
    conn.execute("DELETE FROM plan_item WHERE code = '06026777'")

    # สลับลำดับให้วิชาบังคับก่อนอยู่หลัง
    conn.execute("UPDATE plan_item SET year = 1, semester = 1 "
                 "WHERE code = '06026260'")
    conn.execute("INSERT INTO prerequisite VALUES ('06026260','06026240','pre')")
    res4 = {r["id"]: r["ok"] for r in verify_db(conn)}
    ck("CHK5 จับลำดับวิชาบังคับก่อนผิด", res4["CHK5"], False)

    conn.execute("DELETE FROM prerequisite WHERE code='06026260'")
    conn.execute("UPDATE plan_item SET year=2, semester=1 WHERE code='06026260'")

    # CHK1 — หน่วยกิตรวมไม่ตรงกับที่ประกาศ
    conn.execute("UPDATE program SET total_credits = 120")
    ck("CHK1 จับหน่วยกิตรวมไม่ตรง",
       {r["id"]: r["ok"] for r in verify_db(conn)}["CHK1"], False)
    conn.execute("UPDATE program SET total_credits = 39")

    # CHK6 — วิชาซ้ำในภาคเรียนเดียวกัน
    conn.execute("INSERT INTO plan_item (program_id, year, semester, code,"
                 " credits) VALUES ('IT2565', 1, 1, '06026101', 3)")
    ck("CHK6 จับวิชาซ้ำในภาคเดียวกัน",
       {r["id"]: r["ok"] for r in verify_db(conn)}["CHK6"], False)
    conn.execute("DELETE FROM plan_item WHERE id = (SELECT MAX(id) FROM plan_item)")

    # CHK7 — ภาระหน่วยกิตเกินเกณฑ์
    # ต้องเพิ่ม "จำนวนวิชา" ไม่ใช่เพิ่มหน่วยกิตของวิชาเดิมให้สูง
    # เพราะวิชา 6 หน่วยกิตขึ้นไปจะถูกมองว่าเป็นภาคบล็อกแล้วได้รับยกเว้น
    # (ดูข้อจำกัดที่บันทึกไว้ในฟังก์ชัน verify_db)
    for c in ("06026240", "06026241", "06026259", "06026260"):
        conn.execute("INSERT INTO plan_item (program_id, year, semester, code,"
                     " credits) VALUES ('IT2565', 1, 1, ?, 3)", (c,))
    ck("CHK7 จับหน่วยกิตต่อภาคเกินเกณฑ์",
       {r["id"]: r["ok"] for r in verify_db(conn)}["CHK7"], False)
    conn.execute("DELETE FROM plan_item WHERE year=1 AND semester=1 AND code IN"
                 " ('06026240','06026241','06026259','06026260')")

    # ยืนยันอีกครั้งว่ากลับสู่สภาพสะอาดแล้วไม่มีการเตือนผิด
    ck("คืนค่าแล้วไม่มีคำเตือนค้าง",
       [r["id"] for r in verify_db(conn) if not r["ok"]], [])

    conn.close()
    db.unlink(missing_ok=True)

    print("=" * 68)
    print(f"  ผ่าน {passed} · ไม่ผ่าน {failed}")
    print("=" * 68)
    return failed == 0


def _load_dict(conn: sqlite3.Connection, data: dict) -> None:
    """โหลด dict เข้าฐานข้อมูลที่เปิดอยู่แล้ว (ใช้ร่วมกับ selftest)"""
    p = data["program"]
    conn.execute("INSERT OR REPLACE INTO program VALUES (?,?,?,?,?,?)",
                 (p["program_id"], p["name_th"], p.get("name_en"),
                  p.get("degree"), p["total_credits"], p["years"]))
    for c in data.get("courses", []):
        conn.execute("INSERT OR REPLACE INTO course VALUES (?,?,?,?,?,?,?,?)",
                     (c["code"], c["name_th"], c.get("name_en"), c["credits"],
                      c.get("lecture_h"), c.get("lab_h"), c.get("self_h"),
                      c.get("description_th")))
    for it in data.get("plan", []):
        conn.execute("INSERT INTO plan_item (program_id, year, semester, code,"
                     " credits, alt_group, note) VALUES (?,?,?,?,?,?,?)",
                     (p["program_id"], it["year"], it["semester"], it["code"],
                      it["credits"], it.get("alt_group"), it.get("note")))
    for r in data.get("prerequisites", []):
        conn.execute("INSERT OR REPLACE INTO prerequisite VALUES (?,?,?)",
                     (r["code"], r["requires"], r.get("kind", "pre")))
    conn.commit()


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Lab 8B — จากข้อความที่สกัดได้ สู่ฐานข้อมูลที่ตอบคำถามได้",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="ตรวจสภาพแวดล้อม")
    sub.add_parser("selftest", help="ทดสอบ schema กฎตรวจ และด่าน SQL")

    p = sub.add_parser("demo", help="สร้างข้อมูลตัวอย่างสำหรับทดลอง")
    p.add_argument("-o", "--output", required=True)

    p = sub.add_parser("schema", help="เขียน JSON Schema และ SQL DDL")
    p.add_argument("-o", "--output", required=True)

    p = sub.add_parser("extract", help="Markdown -> JSON พร้อมวงจรซ่อม")
    p.add_argument("-i", "--input", required=True, help="ไฟล์ Markdown จาก Lab 7B")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--rounds", type=int, default=MAX_REPAIR_ROUNDS)
    p.add_argument("--max-chars", type=int, default=40000)

    p = sub.add_parser("import-lab7b",
                       help="Lab 7B JSON -> Lab 8B JSON โดยไม่เรียก LLM ซ้ำ")
    p.add_argument("-i", "--input", required=True,
                   help="pred_vlm.json, pred_text.json หรือ pred_baseline.json จาก Lab 7B")
    p.add_argument("-o", "--output", required=True, help="JSON schema ของ Lab 8B")
    p.add_argument("--program-id", default=None, help="ทับ program id จาก Lab 7B")
    p.add_argument("--program-name", default=None, help="ชื่อหลักสูตรภาษาไทย")
    p.add_argument("--total-credits", type=int, default=None,
                   help="หน่วยกิตรวมตามที่หลักสูตรประกาศ; ไม่ระบุจะคำนวณจากแผน")
    p.add_argument("--years", type=int, default=None,
                   help="จำนวนปีของหลักสูตร; ไม่ระบุจะใช้ปีสูงสุดในแผน")
    p.add_argument("--markdown", default=None,
                   help="intermediate_vlm.md จาก Lab 7B — ใช้กู้ปี/เทอมของวิชารหัสจริงที่ได้ 0/0 (ไม่บังคับ)")

    p = sub.add_parser("load", help="JSON -> SQLite")
    p.add_argument("-i", "--input", required=True)
    p.add_argument("-d", "--database", required=True)
    p.add_argument("--replace", action="store_true", help="ลบฐานข้อมูลเดิมก่อน")

    p = sub.add_parser("load-electives",
                       help="โหลดผล extract_elective_catalog.py เข้าตารางอ้างอิง"
                            " elective_group/elective_group_course (ไม่แตะ course/plan_item)")
    p.add_argument("-i", "--input", required=True, help="JSON จาก extract_elective_catalog.py")
    p.add_argument("-d", "--database", required=True)
    p.add_argument("--program-id", default=None, help="ทับ program id จากไฟล์ input")

    p = sub.add_parser("load-plan-slots-md",
                       help="สกัดช่อง wildcard/หรือ/เลือก 1 กลุ่ม จาก Markdown ของ OCR เข้า plan_slot"
                            " (ไม่แตะ plan_item/verify เดิม; ไม่กรอกมือ)")
    p.add_argument("-m", "--markdown", required=True, help="intermediate_vlm.md จาก Lab 7B")
    p.add_argument("-d", "--database", required=True)

    p = sub.add_parser("load-prerequisites",
                       help="สกัดวิชาบังคับก่อนจากข้อความ OCR ทั้งเล่ม (ภาคผนวกคำอธิบายรายวิชา) เข้าตาราง prerequisite"
                            " (กฎเชิงกำหนด ไม่เดา: หาไม่เจอ = ไม่เติมแถว)")
    p.add_argument("-t", "--text", required=True, help="outputs/<หลักสูตร>/<หลักสูตร>_curriculum_ocr.txt (OCR ทั้งเล่มจาก Lab 4-6)")
    p.add_argument("-d", "--database", required=True)
    p.add_argument("-o", "--output", help="เขียนรายงานรายวิชา (found/none/not_found/unreadable) เป็น JSON")

    p = sub.add_parser("verify", help="ตรวจความสอดคล้อง 7 ข้อ")
    p.add_argument("-d", "--database", required=True)
    p.add_argument("-o", "--output", default="")

    p = sub.add_parser("ask", help="ถามหนึ่งคำถาม")
    p.add_argument("-d", "--database", required=True)
    p.add_argument("-q", "--question", required=True)

    p = sub.add_parser("eval", help="ประเมินด้วยชุดคำถามทอง")
    p.add_argument("-d", "--database", required=True)
    p.add_argument("-q", "--questions", required=True)
    p.add_argument("-o", "--output", default="")

    args = ap.parse_args()
    if args.cmd == "check":
        sys.exit(0 if check_environment() else 1)
    if args.cmd == "selftest":
        sys.exit(0 if cmd_selftest(args) else 1)
    {"demo": cmd_demo, "schema": cmd_schema, "extract": cmd_extract,
     "import-lab7b": cmd_import_lab7b,
     "load": cmd_load, "load-electives": cmd_load_electives,
     "load-plan-slots-md": cmd_load_plan_slots_md,
     "load-prerequisites": cmd_load_prerequisites,
     "verify": cmd_verify, "ask": cmd_ask,
     "eval": cmd_eval}[args.cmd](args)


if __name__ == "__main__":
    main()
