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
import csv
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════════
#  ค่าคงที่
# ═══════════════════════════════════════════════════════════════════════

OLLAMA_URL = os.environ.get("LAB8_OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_TEXT = os.environ.get("LAB8_MODEL_TEXT", "qwen3:4b")
# ให้ Ollama ค้างโมเดลไว้ในหน่วยความจำ (ค่าเริ่มต้นของ Ollama คือ 5 นาทีแล้วปล่อย → คำถามถัดไปช้าตอนโหลดใหม่)
KEEP_ALIVE = os.environ.get("LAB8_KEEP_ALIVE", "30m")

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

# สถานะการอ่านวิชาบังคับก่อนของแต่ละวิชา (ผลของ load-prerequisites): ตาราง prerequisite มีแถวเฉพาะวิชาที่ "พบ" — วิชาที่ไม่มีแถว
# อาจเป็น none (เล่มเขียนว่าไม่มี) หรือ not_found/unreadable (อ่านจากเล่มไม่ได้ = ไม่ทราบ) ซึ่งแยกกันไม่ได้ถ้าไม่เก็บสถานะ
# แยกจาก DDL ของ prompt (โมเดลไม่เห็นตารางนี้ → prompt ของทุกคำถามไม่เปลี่ยน) ใช้เฉพาะทางลัดเชิงกำหนด
PREREQ_STATUS_DDL = """
CREATE TABLE IF NOT EXISTS prerequisite_status (
    code   TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('found', 'none', 'not_found', 'unreadable'))
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
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0.0, "num_ctx": num_ctx,
                    "num_predict": num_predict},
    }
    if fmt:
        payload["format"] = fmt
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    return (r.json().get("message") or {}).get("content", "")


def warm_up(timeout: int = 180) -> bool:
    """โหลดโมเดลเข้าหน่วยความจำล่วงหน้า (คำถามแรกจะได้ไม่ช้า) — ไม่ throw เมื่อ Ollama ยังไม่พร้อม"""
    import requests
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate",
                          json={"model": MODEL_TEXT, "keep_alive": KEEP_ALIVE}, timeout=timeout)
        return bool(r.ok)
    except Exception:
        return False


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

REPO_ROOT = Path(__file__).resolve().parents[3]      # ocr_system/ (src/ocr_system/ -> Lab7B_Lab8B_ocr_system/ -> repo)


def repo_relative(path: str | Path) -> str:
    """path ที่เขียนลงรายงาน: ถ้าอยู่ใน repo ใช้แบบ relative (a/b/c) — ไฟล์ที่ commit ไว้จึงไม่เปลี่ยนตามเครื่องที่รัน
    และไม่มี path ในเครื่องหลุดไป; อยู่นอก repo คงค่าเดิม"""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


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
    or_pairs: list[dict] = []
    if markdown:
        # คู่ "A หรือ B" ที่ qwen จับชื่อไขว้/ซ้ำ -> ชื่อตามลำดับที่ Markdown เขียนไว้ (or_course_names.py)
        # ทำตรงนี้ทุกครั้งที่ import (เดิมเป็นสคริปต์แยก apply_or_course_names.py จึงถูกทับเมื่อรัน Lab 8B ใหม่)
        from or_course_names import apply_to_courses, or_pair_names
        or_pairs = apply_to_courses(list(course_by_code.values()), or_pair_names(markdown))
        for f in or_pairs:
            warnings.append(f"{f['code']}: {f['field']} {f['from']!r} -> {f['to']!r} (คู่ 'A หรือ B' ตามลำดับใน Markdown)")
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
        "or_pair_names": or_pairs,
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
    conn.executescript(PREREQ_STATUS_DDL)
    conn.execute("DELETE FROM prerequisite_status")
    conn.executemany("INSERT INTO prerequisite_status (code, status) VALUES (?, ?)",
                     [(code, r["status"]) for code, r in res.items()])
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
        report = {"source_text": repo_relative(args.text), "courses": len(codes), "counts": counts,
                  "pairs_inserted": pairs, "or_groups": or_groups, "per_course": res}
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  บันทึกรายงานที่ {args.output}")


# ตารางอ้างอิงหน้า — แยกจาก DDL หลักโดยตั้งใจ (DDL หลักอยู่ใน prompt ของ NL2SQL; เพิ่มตารางตรงนั้น
# prompt เปลี่ยนและคำตอบข้ออื่นอาจเปลี่ยน) ใช้เฉพาะตอน `load-course-pages` และตอนแนบอ้างอิงใน ask()
COURSE_PAGE_DDL = """
CREATE TABLE IF NOT EXISTS course_page (
    code         TEXT NOT NULL,
    pdf_page     INTEGER NOT NULL,
    printed_page TEXT,
    kind         TEXT NOT NULL CHECK (kind IN ('primary', 'description', 'other', 'plan')),
    PRIMARY KEY (code, pdf_page, kind)
);
-- หน้าตารางแผนของแต่ละเทอม เก็บเทอมไว้ตรง ๆ (ไม่ย้อนหาเทอมจากรหัสวิชา — วิชาที่อยู่ในแผนหลายเทอมจะอ้างหน้าผิดเทอม)
CREATE TABLE IF NOT EXISTS term_page (
    year         INTEGER NOT NULL,
    semester     INTEGER NOT NULL,
    pdf_page     INTEGER NOT NULL,
    printed_page TEXT,
    PRIMARY KEY (year, semester, pdf_page)
);
"""


def _citations_module():
    """citations.py (ไฟล์ข้าง ๆ) — เพิ่มโฟลเดอร์นี้ใน sys.path ครั้งเดียว ไม่เพิ่มซ้ำทุกคำถาม"""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import citations
    return citations


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    """ตัดแถวของวิชาเดียวกันที่ต่างกันแค่การสะกด (ำ เทียบ ํา จาก OCR — แถวหนึ่งมาจาก course อีกแถวมาจากแคตตาล็อกวิชาเลือก)
    ซ้ำ = มี code เท่ากันและทุกคอลัมน์อื่นเท่ากันหลังรวม ํา+า เป็น ำ; ปีหรือเทอมต่างกัน = ไม่ซ้ำ (ไม่แตะ); เก็บแบบสะกดมาตรฐาน"""
    def norm(v):
        return v.replace("ํา", "ำ") if isinstance(v, str) else v

    out: list[dict] = []
    seen: dict[tuple, int] = {}
    for r in rows:
        if "code" not in r:
            out.append(r)
            continue
        key = tuple(sorted((k, norm(v)) for k, v in r.items()))
        if key not in seen:
            seen[key] = len(out)
            out.append(r)
        elif "ํา" in "".join(str(v) for v in out[seen[key]].values()):
            out[seen[key]] = r                    # แถวแรกสะกดแยกอักขระ แถวนี้สะกดมาตรฐาน → ใช้แถวนี้
    return out


_ELECTIVE_Q = re.compile(r"วิชาเลือก(?!เสรี)|elective", re.I)       # วิชาเลือกเสรี ไม่ใช่แคตตาล็อกเฉพาะทาง
_TOPIC_Q = re.compile(r"วิชา.*(?:เกี่ยวกับ|เกี่ยวข้องกับ|ด้าน|เรื่อง)|(?:เกี่ยวกับ|เกี่ยวข้องกับ|ด้าน|เรื่อง).*วิชา"
                      # รูป "มีวิชาภาษาจีนไหม" (ถามว่ามีหัวข้อนี้ไหม) — ไม่รวม "มีวิชาบังคับ/เลือก/ก่อน…ไหม" และคำถามที่มีคำขึ้นต้นเป็นคำถามอื่น
                      r"|มี(?:รายวิชา|วิชา)(?!บังคับ|เลือก|ก่อน|ใด|อะไร|ไหน)\S{2,30}(?:ไหม|หรือไม่)")


_TERM_COUNT_Q = re.compile(r"กี่หน่วยกิต|กี่วิชา|กี่ตัว|หน่วยกิตรวม|รวมกี่")
_TERM_LIST_Q = re.compile(r"อะไรบ้าง|วิชาอะไร|ชื่อวิชา|รายชื่อ")
_TERM_YEAR_Q = re.compile(r"(?:ปี|ชั้นปี)(?:ที่)?\s*\d")
_TERM_SEM_Q = re.compile(r"(?:เทอม|ภาค(?:เรียน|การศึกษา)?)(?:ที่)?\s*\d")
TERM_TOTAL_COLS = ("total_credits", "n_courses")


def _term_summary_hint_text(question: str) -> str:
    """คำถามควบ "ปี/เทอมนี้ กี่หน่วยกิต/กี่วิชา + มีวิชาอะไรบ้าง": มีคำว่า "กี่…" โมเดลเลยเลือก v_semester_credits
    (มีแค่ credits, n_courses ไม่มีชื่อวิชา) ส่วน "…อะไรบ้าง" ไปใช้ v_plan (ได้ชื่อวิชาแต่ไม่มียอดรวม) — ได้ครึ่งเดียวทั้งสองทาง
    คำใบ้: SQL เดียว JOIN สองส่วน (ยอดรวมนับตามเล่มจาก v_semester_credits) — เปิดเฉพาะเมื่อมีทั้งคำถามยอด + รายวิชา + ระบุปี/เทอม"""
    if not (_TERM_COUNT_Q.search(question) and _TERM_LIST_Q.search(question)
            and _TERM_YEAR_Q.search(question) and _TERM_SEM_Q.search(question)):
        return ""
    return (
        "สรุปรายเทอมพร้อมรายวิชา: คำถามนี้ต้องการทั้งยอดรวมและชื่อวิชาของภาคเรียน — ใช้ SQL เดียว JOIN v_plan "
        "(ชื่อวิชา) กับ v_semester_credits (ยอดรวม จำนวนวิชา) ห้ามเลือกอย่างใดอย่างหนึ่ง:\n"
        "SELECT p.code, p.name_th, p.credits, s.credits AS total_credits, s.n_courses FROM v_plan p "
        "JOIN v_semester_credits s ON s.year = p.year AND s.semester = p.semester "
        "WHERE p.year = <ปี> AND p.semester = <เทอม> ORDER BY p.id\n\n"
    )


_TERM_YEAR_NUM = re.compile(r"(?:ปี|ชั้นปี)(?:ที่)?\s*(\d)")
_TERM_SEM_NUM = re.compile(r"(?:เทอม|ภาค(?:เรียน|การศึกษา)?)(?:ที่)?\s*(\d)")
_TERM_SUMMARY_SQL = (
    "SELECT p.code, p.name_th, p.credits, s.credits AS total_credits, s.n_courses FROM v_plan p "
    "JOIN v_semester_credits s ON s.year = p.year AND s.semester = p.semester "
    "WHERE p.year = {y} AND p.semester = {s} ORDER BY p.id")


def _term_summary_fallback(conn: sqlite3.Connection, question: str, sql: str | None,
                           rows: list[dict]) -> tuple[str | None, list[dict]]:
    """ตัวสำรองของ _term_summary_hint_text: คำถามควบ (ยอดรวม + รายวิชา ของปี/เทอมที่ระบุ) แต่ SQL ของโมเดลได้แถวที่ไม่มี
    ชื่อวิชา (เช่น ใช้ v_semester_credits อย่างเดียว) → รันแม่แบบ JOIN เองด้วยปี/เทอมที่อ่านจากข้อความคำถาม (กฎเชิงกำหนด)
    SQL ที่ได้ชื่อวิชาอยู่แล้ว หรือคำถามที่ไม่ใช่แบบควบ ไม่ถูกแตะ; รันไม่ได้/ไม่มีแถว = คงของเดิม"""
    if not rows or not _term_summary_hint_text(question):
        return sql, rows
    if any(k in rows[0] for k in ("name_th", "course_name_th", "name_en")):
        return sql, rows
    y, s = _TERM_YEAR_NUM.search(question), _TERM_SEM_NUM.search(question)
    if not (y and s):
        return sql, rows
    template = _TERM_SUMMARY_SQL.format(y=int(y.group(1)), s=int(s.group(1)))
    try:
        fixed = _dedupe_rows([dict(r) for r in conn.execute(template).fetchall()])
    except sqlite3.Error:
        return sql, rows
    return (template, fixed) if fixed else (sql, rows)


_OPEN_SLOT_LIST_Q = re.compile(r"อะไรบ้าง|วิชาอะไร|อะไรได้|อะไรให้เลือก|รายชื่อ|วิชาไหน|เลือกอะไร")
_OPEN_SLOT_COUNT_Q = re.compile(r"กี่หน่วยกิต|กี่วิชา")
_OPEN_SLOT_GE_PHRASES = ("ภาษาและการสื่อสาร", "ศึกษาทั่วไป")
# "GE" ต้องเป็นคำเดี่ยว (ไม่ใช่ส่วนของ INTELLIGENCE/MANAGEMENT/LANGUAGE) หรือ "general education"
_GE_WORD = re.compile(r"(?<![A-Za-z])GE(?![A-Za-z])|general\s+education", re.I)
_GE_Q = re.compile(r"ศึกษาทั่วไป|ภาษาและการสื่อสาร|" + _GE_WORD.pattern, re.I)
_UNIVERSITY = "สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง"


_GE_PLAN_SLOT_PREFIX = "หมวดวิชาศึกษาทั่วไป"
_GE_EXAMPLES_SINGLE, _GE_EXAMPLES_PER_GROUP = 8, 2


def _ge_pool(conn: sqlite3.Connection, code: str | None, credits: int,
             brief: bool = False) -> tuple[str, list[dict], str] | None:
    """คลังตัวเลือกของช่อง GE จากแคตตาล็อก (v_elective_group ที่ plan_slot ขึ้นต้น "หมวดวิชาศึกษาทั่วไป") — คืน (ข้อความ, แถว, SQL)
    หรือ None (DB ไม่มีแคตตาล็อก เช่น BIT / ไม่เหลือตัวเลือก → ใช้ข้อความระดับ 1)
    ช่อง 90644xxx = กลุ่มทักษะภาษาและการสื่อสาร (4); ช่อง 9064xxxx = กลุ่ม 2,3,4 (ไม่รวมกลุ่ม 1 อัตลักษณ์ซึ่งเอกสารจัดเป็นบล็อกบังคับ,
    ไม่รวมกลุ่ม 5 เทียบโอน); หน่วยกิตต้องเท่ากับของช่อง; ไม่รวมวิชาที่เป็นวิชาบังคับในแผนของหลักสูตรนี้ (plan_item) — แต่แจ้งไว้
    ท้ายคำตอบ (วิชาบังคับบางตัว เช่น 90644007/008 ของ DSBA/IT เป็นรหัสฉบับ 2564 ที่ไม่อยู่ในแคตตาล็อก 2566 จะได้ไม่ตกหล่น)
    ใช้ main.v_elective_group เสมอ (view ชั่วคราวของ scope_elective_view ซ่อน GE)"""
    if credits is None:
        return None
    groups = (4,) if (code or "").startswith("90644") else (2, 3, 4)
    marks = ", ".join(str(g) for g in groups)
    try:
        credits = int(credits)
    except (TypeError, ValueError):
        return None
    # main.-qualified (รันซ้ำได้แม้ TEMP VIEW ซ่อน GE) และ NOT EXISTS (NOT IN ล้มเหลวทั้งชุดถ้า plan_item.code มี NULL; และ citations.py
    # ข้ามหน้าตารางแผนเมื่อเจอ NOT IN ใน SQL)
    sql = ("SELECT v.code, v.course_name_th AS name_th, v.credits, v.group_no, v.group_name_th FROM main.v_elective_group v "
           f"WHERE v.plan_slot LIKE '{_GE_PLAN_SLOT_PREFIX}%' AND v.group_no IN ({marks}) AND v.credits = {credits} "
           "AND NOT EXISTS (SELECT 1 FROM plan_item p WHERE p.code = v.code) ORDER BY v.group_no, v.code")
    try:
        found = [dict(r) for r in conn.execute(sql).fetchall()]
        edition = conn.execute("SELECT plan_slot FROM main.v_elective_group WHERE plan_slot LIKE ? LIMIT 1",
                               (_GE_PLAN_SLOT_PREFIX + "%",)).fetchone()
        required = conn.execute(
            "SELECT DISTINCT c.code, c.name_th FROM plan_item p JOIN course c ON c.code = p.code "
            f"WHERE c.code LIKE '9064%' AND substr(c.code, 5, 1) IN ({', '.join(repr(str(g)) for g in groups)}) "   # substr = ข้อความ ต้องเทียบกับ '4' ไม่ใช่ 4
            "ORDER BY c.code").fetchall()
    except (sqlite3.Error, TypeError, ValueError):
        return None
    if not found or not edition:
        return None
    by_group: dict[str, list[dict]] = {}
    for r in found:
        by_group.setdefault(r["group_name_th"], []).append(r)
    if len(groups) == 1:
        shown = found[:3 if brief else _GE_EXAMPLES_SINGLE]
        detail = ""
    else:
        shown = [r for rs in by_group.values() for r in rs[:1 if brief else _GE_EXAMPLES_PER_GROUP]]
        detail = " (" + ", ".join(f"{g} {len(rs)} วิชา" for g, rs in by_group.items()) + ")"
    examples = ", ".join(f"{r['code']} {r['name_th']}" for r in shown) + (" …" if len(shown) < len(found) else "")
    text = (f"เลือก {credits} หน่วยกิตตาม{edition[0]} — มี {len(found)} วิชาให้เลือก{detail} เช่น {examples}")
    if required and not brief:
        text += ("; วิชาบังคับในแผนของหลักสูตรนี้ที่อยู่ในกลุ่มเดียวกัน (ไม่นับเป็นตัวเลือก): "
                 + ", ".join(f"{c} {n}" for c, n in required[:8]))
    rows = [{"code": r["code"], "name_th": r["name_th"], "credits": r["credits"], "group_no": r["group_no"]} for r in found]
    return text, rows, sql


def _open_slot_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ช่อง "เลือกเอง" ที่เล่มไม่ระบุรายชื่อวิชา — คืน (คำตอบ, แถว, SQL) หรือ None (ใช้ทางเดิม)
    - หมวดศึกษาทั่วไป / ด้านภาษาและการสื่อสาร (plan_slot wildcard เช่น 90644xxx): ถ้า DB มีแคตตาล็อก GE (ฉบับ 2566) → คลังตัวเลือก
      ตามกลุ่ม+หน่วยกิตของช่อง (_ge_pool); ไม่มี (เช่น BIT) → ข้อความตามเล่ม "เลือกตามรายวิชาที่ สจล. เปิดสอน (ภาคผนวก ง)" —
      ไม่ลิสต์วิชารหัสขึ้นต้นเดียวกันจาก course เพราะรวมวิชาบังคับ/กลุ่มอื่นเข้ามา (เคยตอบผิดแบบนั้น)
    - วิชาเลือกเสรี: เลือกจากรายวิชาที่เปิดสอนในสถาบัน ไม่มีรายชื่อกำหนด
    เปิดเฉพาะคำถามแบบ "…เลือก…มีวิชาอะไรบ้าง" ที่ระบุชื่อช่อง (ไม่ใช่ถามหน่วยกิต/จำนวน); ช่องที่มีแคตตาล็อกจริง
    (เช่น 06026xxx กลุ่มวิทยาการข้อมูล) ไม่เกี่ยว ปล่อยให้ทางเดิม; ระบุปี/เทอมในคำถาม = กรองเฉพาะเทอมนั้น"""
    if "เลือก" not in question or not _OPEN_SLOT_LIST_Q.search(question) or _OPEN_SLOT_COUNT_Q.search(question):
        return None
    try:
        slots = conn.execute("SELECT id, year, semester, code, name_th, credits FROM plan_slot "
                             "WHERE kind = 'wildcard' ORDER BY year, semester, id").fetchall()
    except sqlite3.OperationalError:
        return None
    y, s = _TERM_YEAR_NUM.search(question), _TERM_SEM_NUM.search(question)

    def collect(use_term_filter: bool) -> list[tuple]:
        found, seen = [], set()
        for sid, year, sem, code, name, credits in slots:
            name = name or ""
            is_free = "เลือกเสรี" in name and "เลือกเสรี" in question
            is_ge = (any(p in name and p in question for p in _OPEN_SLOT_GE_PHRASES)
                     or (_GE_WORD.search(question) is not None and "ศึกษาทั่วไป" in name))      # "GE"/"general education" = หมวดศึกษาทั่วไป
            if not (is_free or is_ge):
                continue
            if use_term_filter and ((y and int(y.group(1)) != year) or (s and int(s.group(1)) != sem)):
                continue
            if (year, sem, name) in seen:
                continue
            seen.add((year, sem, name))
            found.append((sid, year, sem, code, name, credits, is_free))
        return found

    picked = collect(True)
    wrong_term = ""
    if not picked and (y or s):                           # ชื่อช่องมีจริงแต่อยู่คนละเทอม → ตอบช่องนั้นพร้อมบอกเทอมจริง (ไม่หลุดไปสรุปช่องอื่น)
        picked = collect(False)
        if picked:
            asked = " ".join(x for x in (f"ปี {y.group(1)}" if y else "", f"เทอม {s.group(1)}" if s else "") if x)
            where_is = ", ".join(sorted({f"ปี {p[1]} เทอม {p[2]}" for p in picked}))
            wrong_term = f"ไม่มีช่องนี้ใน{asked} — ช่องนี้อยู่ที่ {where_is}: "
    if not picked:
        return None
    picked = [p for p in picked if p[4] in question] or picked      # ระบุชื่อช่องเต็ม (เช่น "วิชาเลือกเสรี 2") = เฉพาะช่องนั้น
    parts, pool_rows, pool_sql, plain = [], [], None, False
    for _sid, year, sem, code, name, credits, is_free in picked:
        where = f"(ปี {year} เทอม {sem})"
        if is_free:
            plain = True
            parts.append(f"{name} {where}: เลือกเรียนจากรายวิชาที่เปิดสอนในสถาบันได้ {credits} หน่วยกิต "
                         "ไม่มีรายชื่อวิชากำหนดในเล่ม")
            continue
        pool = _ge_pool(conn, code, credits)
        if pool:                                          # มีแคตตาล็อก GE ใน DB → ตอบรายชื่อจริง (ระบุฉบับ ไม่อ้างว่าตรงกับภาคผนวกในเล่ม)
            parts.append(f"{name} {where}: {pool[0]}")
            pool_rows += [r for r in pool[1] if r not in pool_rows]
            pool_sql = pool_sql or pool[2]
        else:                                             # ไม่มีแคตตาล็อก (เช่น BIT) → ข้อความระดับ 1 ตามถ้อยคำเล่ม
            plain = True
            appendix = " (ภาคผนวก ง ของเล่มหลักสูตร)" if (code or "").startswith("9064") else ""
            parts.append(f"{name} {where}: ไม่ได้กำหนดรายวิชาตายตัวในแผน — ให้เลือก {credits} หน่วยกิต"
                         f"จากรายวิชาที่{_UNIVERSITY}เปิดสอน{appendix}")
    terms = {(p[1], p[2]) for p in picked}
    if pool_rows and not plain:
        # SQL เดียวที่รันซ้ำได้; เทอมเดียว → ใส่ year/semester ในคอมเมนต์เพื่อให้ citations.py อ้างหน้าตารางแผนของเทอมนั้น
        tag = f" /* year = {next(iter(terms))[0]} AND semester = {next(iter(terms))[1]} */" if len(terms) == 1 else ""
        return wrong_term + "; ".join(parts), pool_rows, pool_sql + tag
    if len(terms) == 1:                                   # เทอมเดียว → SQL ระบุ year/semester เพื่ออ้างอิงหน้าตารางแผนของเทอมนั้น
        year, sem = next(iter(terms))
        names = " OR ".join("name_th = '" + p[4].replace("'", "''") + "'" for p in picked)
        sql = (f"SELECT year, semester, name_th AS slot, code AS code_pattern, credits FROM plan_slot "
               f"WHERE year = {year} AND semester = {sem} AND ({names}) ORDER BY id")
    else:
        ids = ", ".join(str(p[0]) for p in picked)
        sql = (f"SELECT year, semester, name_th AS slot, code AS code_pattern, credits FROM plan_slot "
               f"WHERE id IN ({ids}) ORDER BY year, semester, id")
    rows = [dict(r) for r in conn.execute(sql).fetchall()]
    # ผสมคลัง GE กับช่องอื่น: คืน SQL ตัวแรกตัวเดียว (รันซ้ำได้) แล้วบอกในคอมเมนต์ว่าแถวช่องอื่นมาจาก plan_slot
    return wrong_term + "; ".join(parts), pool_rows + rows, sql if not pool_rows else f"{pool_sql} /* ช่องอื่นจาก plan_slot */"


# "เลือก" ต้องเป็นสิ่งที่ถาม ("เลือกอะไรได้", "วิชาเลือกมีอะไร", "วิชาอะไรให้เลือก") — ไม่ใช่แค่มีคำว่าเลือกอยู่ในประโยค
_TERM_CHOICES_ASK = re.compile(r"เลือก(?:เรียน)?(?:วิชา)?(?:อะไร|ได้)|วิชาเลือก(?:มี)?(?:วิชา)?อะไร|(?:อะไร|วิชาอะไร|วิชาไหน)ให้เลือก|ให้เลือก")
# ประโยคที่ขอบเขตกว้างกว่า/ปฏิเสธ ("ไม่รวมวิชาเลือก", "รวมวิชาเลือกด้วย", "ถ้าเลือกแผนสหกิจ") — ปล่อยให้ทางโมเดล
_TERM_CHOICES_BAIL = re.compile(r"ไม่รวม|นอกจาก|ยกเว้น|บังคับ|รวม.*ด้วย|แผน|สหกิจ")


def _is_term_choices_question(question: str) -> bool:
    """คำถามแบบ "ปี N เทอม M เลือกอะไรได้บ้าง/มีวิชาอะไรให้เลือก" — ระบุทั้งปีและเทอม ถามตัวเลือกจริง ไม่ปฏิเสธ/ขยายขอบเขต
    ไม่ใช่ถามหน่วยกิต/จำนวน"""
    return bool(_TERM_YEAR_NUM.search(question) and _TERM_SEM_NUM.search(question) and _TERM_CHOICES_ASK.search(question)
                and not _TERM_CHOICES_BAIL.search(question) and not _OPEN_SLOT_COUNT_Q.search(question))


def _term_choices_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """สรุปทุกช่อง "ให้เลือก" ของเทอมที่ถาม (plan_slot) ตามชนิด: หมวดศึกษาทั่วไป/ภาษาฯ → คลังตัวเลือกจากแคตตาล็อก GE (ย่อ),
    วิชาเลือกเสรี → ประโยคตามเล่ม, ช่อง wildcard ของหลักสูตร → ชื่อกลุ่มพร้อมจำนวนวิชาจากแคตตาล็อกวิชาเลือก,
    A หรือ B / เลือก 1 กลุ่ม → สมาชิกจาก plan_slot_member; เทอมที่ไม่มีช่องเลือก/ไม่ใช่คำถามแบบนี้ = None (ทางเดิม)
    SQL ที่คืนระบุ year/semester เพื่ออ้างอิงหน้าตารางแผนของเทอมนั้น"""
    if not _is_term_choices_question(question):
        return None
    try:                                                  # ถามกลุ่มวิชาเลือกของหลักสูตรโดยระบุชื่อ → ให้ทางโมเดลลิสต์ชื่อวิชา (สรุปจำนวนกลุ่มไม่พอ)
        own_groups = [r[0] for r in conn.execute(
            "SELECT DISTINCT group_name_th FROM main.v_elective_group "
            f"WHERE plan_slot NOT LIKE '{_GE_PLAN_SLOT_PREFIX}%' AND group_name_th IS NOT NULL")]
    except sqlite3.Error:
        own_groups = []
    if any(g and g in question for g in own_groups):
        return None
    year, sem = int(_TERM_YEAR_NUM.search(question).group(1)), int(_TERM_SEM_NUM.search(question).group(1))
    sql = ("SELECT year, semester, kind, name_th AS slot, code AS code_pattern, credits FROM plan_slot "
           f"WHERE year = {year} AND semester = {sem} ORDER BY id")
    try:
        slots = [dict(r) for r in conn.execute(sql).fetchall()]
    except sqlite3.OperationalError:
        return None
    if not slots:
        return None
    parts = []
    for slot in slots:
        name, code, credits, kind = slot["slot"] or "", slot["code_pattern"], slot["credits"], slot["kind"]
        head = f"{name} ({credits} หน่วยกิต)"
        if kind in ("choose_one", "choose_group"):
            members = conn.execute(
                "SELECT m.group_no, m.group_name, m.code, c.name_th FROM plan_slot_member m "
                "JOIN plan_slot p ON p.id = m.slot_id LEFT JOIN course c ON c.code = m.code "
                "WHERE p.year = ? AND p.semester = ? AND p.name_th = ? ORDER BY m.group_no, m.code",
                (year, sem, name)).fetchall()
            by_group: dict[str, list[str]] = {}
            for g_no, g_name, m_code, m_name in members:
                by_group.setdefault(g_name or f"กลุ่ม {g_no}", []).append(f"{m_code} {m_name or ''}".strip())
            parts.append(head + (": " + " | ".join(f"{g}: {', '.join(v)}" for g, v in by_group.items()) if by_group else ""))
        elif "เลือกเสรี" in name:
            parts.append(f"{head}: เลือกเรียนจากรายวิชาที่เปิดสอนในสถาบัน ไม่มีรายชื่อวิชากำหนดในเล่ม")
        elif any(p in name for p in _OPEN_SLOT_GE_PHRASES):
            pool = _ge_pool(conn, code, credits, brief=True)
            parts.append(f"{head}: {pool[0]}" if pool else
                         f"{head}: ไม่ได้กำหนดรายวิชาตายตัวในแผน — เลือกจากรายวิชาที่{_UNIVERSITY}เปิดสอน")
        else:
            prefix = (code or "").rstrip("xX")
            groups = conn.execute(
                "SELECT group_name_th, COUNT(*) FROM main.v_elective_group "
                f"WHERE plan_slot NOT LIKE '{_GE_PLAN_SLOT_PREFIX}%' AND code LIKE ? GROUP BY group_no, group_name_th ORDER BY group_no",
                (prefix + "%",)).fetchall() if prefix.isdigit() and len(prefix) >= 5 else []
            parts.append(head + (": เลือกจากกลุ่มวิชาเลือกของหลักสูตร " + ", ".join(f"{g} {n} วิชา" for g, n in groups)
                                 if groups else ": เลือกตามกลุ่มวิชาเลือกที่หลักสูตรกำหนด"))
    return f"ปี {year} เทอม {sem} มีช่องให้เลือก {len(slots)} ช่อง — " + "; ".join(parts), slots, sql


_GE_CATEGORY_LIST_Q = re.compile(r"อะไรบ้าง|วิชาอะไร|มีวิชา|รายวิชา|รายชื่อ")


def _is_ge_category_question(question: str) -> bool:
    """คำถามภาพรวมหมวด "หมวดวิชาศึกษาทั่วไปมีวิชาอะไรบ้าง" — พูดถึงศึกษาทั่วไป ถามรายการ ไม่มีคำว่าเลือก (ถามตัวเลือกไปทางช่อง/รายเทอม)
    ไม่ระบุปี/เทอม และไม่ถามจำนวน/หน่วยกิต"""
    return bool("ศึกษาทั่วไป" in question and _GE_CATEGORY_LIST_Q.search(question) and "เลือก" not in question
                and not _TERM_YEAR_NUM.search(question) and not _TERM_SEM_NUM.search(question)
                and not _OPEN_SLOT_COUNT_Q.search(question))


def _ge_category_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ภาพรวมหมวดวิชาศึกษาทั่วไปของหลักสูตรนี้จากแผน: วิชา GE ที่เป็นวิชาบังคับในแผน (plan_item) + ช่องที่นักศึกษาเลือกเอง (plan_slot)
    พร้อมบอกว่าจะดูรายชื่อวิชาเลือกต่อได้อย่างไร — ไม่มีทั้งสองอย่าง = None (ทางเดิม)"""
    if not _is_ge_category_question(question):
        return None
    sql = ("SELECT DISTINCT c.code, c.name_th, c.credits FROM plan_item p JOIN course c ON c.code = p.code "
           "WHERE c.code LIKE '9064%' OR c.code LIKE '9664%' ORDER BY c.code")
    try:
        required = [dict(r) for r in conn.execute(sql).fetchall()]
        slots = conn.execute("SELECT year, semester, name_th, credits FROM plan_slot WHERE kind = 'wildcard' ORDER BY year, semester, id").fetchall()
    except sqlite3.Error:
        return None
    slots = [r for r in slots if any(p in (r[2] or "") for p in _OPEN_SLOT_GE_PHRASES)]
    if not required and not slots:
        return None
    parts = []
    if required:
        parts.append("วิชาบังคับในแผนของหลักสูตรนี้: " + ", ".join(f"{r['code']} {r['name_th']} ({r['credits']} หน่วยกิต)" for r in required))
    if slots:
        parts.append("ช่องที่นักศึกษาเลือกเอง: " + ", ".join(f"{r[2]} (ปี {r[0]} เทอม {r[1]}, {r[3]} หน่วยกิต)" for r in slots)
                     + " — ถามรายชื่อวิชาที่เลือกได้ต่อเป็นรายช่อง เช่น \"" + slots[0][2] + "มีวิชาอะไรให้เลือกบ้าง\"")
    return "หมวดวิชาศึกษาทั่วไปในแผนของหลักสูตรนี้ — " + "; ".join(parts), required, sql


# ===================== ทางลัดเชิงกำหนดสำหรับคำถามที่โมเดลเล็ก (qwen3:4b) พลาด =====================
# ที่มา: probe 62 คำถาม (DSBA/IT) พบคำตอบ "มั่นใจแต่ผิด" และ "ปฏิเสธทั้งที่มีข้อมูล" — ทุกทางลัดอิงข้อมูลใน DB ล้วน ๆ ไม่ผูกกับถ้อยคำของคำถามตัวอย่าง;
# เปิดเฉพาะรูปคำถามที่ชัดเจน (ไม่ชัด = None → ทางโมเดลเดิม) และมีเทสต์ว่าไม่มีคำถามในชุดเฉลย Lab 9 เข้าเงื่อนไข

_CODE8 = re.compile(r"(?<!\d)\d{8}(?!\d)")
_LIST_WORD = re.compile(r"อะไรบ้าง|วิชาไหน|วิชาอะไร|รายชื่อ|มีวิชา|ได้แก่")
_COUNT_WORD = re.compile(r"กี่วิชา|กี่ตัว|จำนวน|กี่รายวิชา")
_TERM_LABEL = "ปี {y} เทอม {s}"


def _term_numbers(question: str) -> tuple[int | None, int | None]:
    y, s = _TERM_YEAR_NUM.search(question), _TERM_SEM_NUM.search(question)
    return (int(y.group(1)) if y else None), (int(s.group(1)) if s else None)


def _first_terms(conn: sqlite3.Connection) -> dict[str, tuple[int, int]]:
    """ปี/เทอมแรกที่วิชาปรากฏในแผน (plan_item)"""
    out: dict[str, tuple[int, int]] = {}
    for code, year, sem in conn.execute("SELECT code, year, semester FROM plan_item ORDER BY year, semester, id"):
        out.setdefault(code, (year, sem))
    return out


# ---- 1. วิชาที่ไม่มีวิชาบังคับก่อน (นับ/ลิสต์) — โมเดลเคยตอบ "0" และลิสต์ปนวิชาที่มี prereq ----
_NO_PREREQ_RE = re.compile(r"ไม่(?:มี|ต้องมี).{0,8}(?:วิชาบังคับก่อน|บังคับก่อน|วิชาก่อนหน้า|prerequisite)", re.I)


def _is_no_prereq_question(question: str) -> bool:
    rest = _NO_PREREQ_RE.sub("", question)                # "ไม่มีวิชาบังคับก่อน" มีคำว่า "มีวิชา" อยู่ข้างใน — ไม่ใช่คำขอรายการ
    return bool(_NO_PREREQ_RE.search(question) and not _CODE8.search(question)
                and (_LIST_WORD.search(rest) or _COUNT_WORD.search(rest)))


def _prereq_statuses(conn: sqlite3.Connection) -> dict[str, str] | None:
    """สถานะการอ่านวิชาบังคับก่อนของแต่ละวิชา (prerequisite_status) — None = DB เก่าไม่มีตาราง/ว่าง (ใช้พฤติกรรมเดิม)"""
    try:
        got = dict(conn.execute("SELECT code, status FROM prerequisite_status").fetchall())
    except sqlite3.OperationalError:
        return None
    return got or None


def _no_prereq_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """วิชาในแผน (ระบุปี/เทอมในคำถามได้) ที่ "ยืนยันว่าไม่มีวิชาบังคับก่อน" = ไม่มีแถว prerequisite และไม่อยู่ใน prerequisite_alt และ
    (ถ้า DB มีสถานะ) สถานะ none — วิชาที่ not_found/unreadable (อ่านจากเล่มไม่ได้) ไม่นับ แต่บอกจำนวน/รายชื่อแยกว่า "ไม่ทราบ" """
    if not _is_no_prereq_question(question):
        return None
    y, s = _term_numbers(question)
    cond = " AND ".join(c for c in (f"year = {y}" if y else "", f"semester = {s}" if s else "") if c)
    plan = "SELECT code FROM plan_item" + (f" WHERE {cond}" if cond else "")
    statuses = _prereq_statuses(conn)
    sure = " AND EXISTS (SELECT 1 FROM prerequisite_status st WHERE st.code = c.code AND st.status = 'none')" if statuses else ""
    base = (f"SELECT c.code, c.name_th, c.credits FROM course c WHERE c.code IN ({plan}) "
            "AND NOT EXISTS (SELECT 1 FROM prerequisite p WHERE p.code = c.code AND p.kind = 'pre') {alt}" + sure + " ORDER BY c.code")
    sql = base.format(alt="AND NOT EXISTS (SELECT 1 FROM prerequisite_alt a WHERE a.code = c.code)")
    try:
        rows = [dict(r) for r in conn.execute(sql).fetchall()]
    except sqlite3.OperationalError:                      # DB เก่าไม่มี prerequisite_alt
        sql = base.format(alt="")
        rows = [dict(r) for r in conn.execute(sql).fetchall()]
    unknown = []
    if statuses:
        in_scope = [r[0] for r in conn.execute(f"SELECT DISTINCT p.code FROM plan_item p WHERE p.code IN ({plan}) ORDER BY p.code")]
        names = {r[0]: r[1] for r in conn.execute("SELECT code, name_th FROM course")}
        unknown = [(c, names.get(c, "")) for c in in_scope if statuses.get(c) in ("not_found", "unreadable")]
    where = f"ใน{_TERM_LABEL.format(y=y, s=s)}" if (y and s) else (f"ในปี {y}" if y else "ในแผนการศึกษา")
    head = f"มี {len(rows)} วิชา{where}ที่ระบุว่าไม่มีวิชาบังคับก่อน" if statuses else f"มี {len(rows)} วิชา{where}ที่ไม่มีวิชาบังคับก่อน"
    note = f" (อีก {len(unknown)} วิชาอ่านวิชาบังคับก่อนจากเล่มไม่ได้ จึงยังไม่ทราบ)" if unknown else ""
    rest = _NO_PREREQ_RE.sub("", question)
    if not rows or (_COUNT_WORD.search(rest) and not _LIST_WORD.search(rest)):
        return head + note, rows, sql
    text = head + ": " + ", ".join(f"{r['code']} {r['name_th']}" for r in rows)
    if unknown:
        text += f"; ไม่ทราบ: " + ", ".join(f"{c} {n}".strip() for c, n in unknown)
    return text, rows, sql


# ---- 2. กรองตามชั่วโมง (บรรยาย/ปฏิบัติ/ศึกษาด้วยตนเอง) — โมเดลเคยละเงื่อนไข ได้ 36 วิชาแทน 5 ----
_HOURS_COLS = (("ศึกษาด้วยตนเอง", "self_h", "ศึกษาด้วยตนเอง"), ("นอกชั้นเรียน", "self_h", "ศึกษาด้วยตนเอง"),
               ("บรรยาย", "lecture_h", "บรรยาย"), ("ปฏิบัติ", "lab_h", "ปฏิบัติ"))
_HOURS_OPS = ((r"ไม่น้อยกว่า|อย่างน้อย|ตั้งแต่", ">=", "ไม่น้อยกว่า"), (r"ไม่เกิน|อย่างมาก|ไม่มากกว่า", "<=", "ไม่เกิน"),
              (r"มากกว่า|เกิน|สูงกว่า", ">", "มากกว่า"), (r"น้อยกว่า|ต่ำกว่า", "<", "น้อยกว่า"), (r"เท่ากับ|เท่ากัน", "=", "เท่ากับ"))


def _hours_filter_spec(question: str) -> tuple[str, str, int, str, str] | None:
    """(คอลัมน์, ตัวดำเนินการ, ค่า, ชื่อชั่วโมง, คำบอกเงื่อนไข) จากคำถามแบบ "วิชาที่ชั่วโมงปฏิบัติมากกว่า 2 ชั่วโมง" / "ไม่มีชั่วโมงปฏิบัติ";
    คำถามเจาะวิชาเดียว (มีรหัส/ไม่มีตัวดำเนินการ+ตัวเลข) หรือไม่ได้ถามรายการ = None"""
    if "ชั่วโมง" not in question or _CODE8.search(question) or not _LIST_WORD.search(question):
        return None
    col = next(((c, label) for w, c, label in _HOURS_COLS if w in question), None)
    if col is None:
        return None
    if re.search(r"ไม่มี(?:ชั่วโมง)?(?:บรรยาย|ปฏิบัติ|ศึกษาด้วยตนเอง|นอกชั้นเรียน)", question):
        return col[0], "=", 0, col[1], "เท่ากับ"
    n = re.search(r"(\d+)\s*ชั่วโมง", question)
    if not n:
        return None
    op = next(((o, label) for p, o, label in _HOURS_OPS if re.search(p, question)), None)
    if op is None and re.search(r"มี\s*\d+\s*ชั่วโมง", question):
        op = ("=", "เท่ากับ")
    return (col[0], op[0], int(n.group(1)), col[1], op[1]) if op else None


def _hours_filter_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    spec = _hours_filter_spec(question)
    if spec is None:
        return None
    col, op, value, label, op_label = spec                # col/op มาจากตารางคงที่ด้านบน (ไม่ใช่ข้อความผู้ใช้) value เป็น int
    sql = (f"SELECT c.code, c.name_th, c.credits, c.lecture_h, c.lab_h, c.self_h FROM course c "
           f"WHERE c.code IN (SELECT code FROM plan_item) AND c.{col} IS NOT NULL AND c.{col} {op} {value} ORDER BY c.code")
    rows = [dict(r) for r in conn.execute(sql).fetchall()]
    head = f"วิชาในแผนที่ชั่วโมง{label}{op_label} {value} ชั่วโมง มี {len(rows)} วิชา"
    if not rows:
        return head, rows, sql
    return (head + ": " + ", ".join(f"{r['code']} {r['name_th']} (บรรยาย {r['lecture_h']}-ปฏิบัติ {r['lab_h']}-ศึกษาด้วยตนเอง {r['self_h']})"
                                    for r in rows), rows, sql)


# ---- 3. เทอม/ปีที่หน่วยกิตมากสุด-น้อยสุด — โมเดลเคยตอบแค่ตัวเลข ไม่บอกว่าเทอมไหน ----
_EXTREME_MAX = re.compile(r"มากที่สุด|มากสุด|สูงสุด|หนักที่สุด")
_EXTREME_MIN = re.compile(r"น้อยที่สุด|น้อยสุด|ต่ำสุด|เบาที่สุด")


def _is_extreme_credits_question(question: str) -> bool:
    return bool((_EXTREME_MAX.search(question) or _EXTREME_MIN.search(question))
                and re.search(r"เทอม|ภาคการศึกษา|ภาคเรียน|ภาค|ปีไหน|ปีใด", question) and re.search(r"ไหน|ใด", question)
                and re.search(r"หน่วยกิต|หนัก|เบา|เรียน", question) and not _CODE8.search(question))


def _extreme_credits_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ปี/เทอมที่หน่วยกิตมาก/น้อยที่สุด จาก v_semester_credits_full (นับตามเล่ม — ช่อง "เลือก 1 กลุ่ม" ไม่นับซ้ำ); เท่ากันบอกครบทุกเทอม"""
    if not _is_extreme_credits_question(question):
        return None
    y, _s = _term_numbers(question)
    per_year = bool(re.search(r"ปีไหน|ปีใด|ชั้นปีไหน", question)) and not re.search(r"เทอมไหน|ภาคไหน|ภาคการศึกษาไหน|ภาคเรียนไหน|เทอมใด", question)
    want_max = bool(_EXTREME_MAX.search(question))
    where = f" WHERE year = {y}" if y else ""
    if per_year:
        sql = f"SELECT year, SUM(credits) AS credits FROM main.v_semester_credits_full{where} GROUP BY year"
    else:
        sql = f"SELECT year, semester, credits FROM main.v_semester_credits_full{where}"
    try:
        rows = [dict(r) for r in conn.execute(sql).fetchall() if r["credits"] is not None]
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None
    best = (max if want_max else min)(r["credits"] for r in rows)
    top = [r for r in rows if r["credits"] == best]
    names = " และ ".join((f"ปี {r['year']}" if per_year else _TERM_LABEL.format(y=r["year"], s=r["semester"])) for r in top)
    kind = "ปี" if per_year else "เทอม"
    return (f"{kind}ที่เรียน{'มาก' if want_max else 'น้อย'}ที่สุดคือ {names} ({best} หน่วยกิต)", top,
            sql + f" ORDER BY credits {'DESC' if want_max else 'ASC'}")


# ---- 4. รหัสภายในจากขั้นตอน Lab 7B (alt_group = "lab7b_alt_61") ต้องไม่หลุดเข้าแถว/คำตอบ ----
def _hide_internal_columns(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if len(r) > 1 and isinstance(r.get("alt_group"), str) and r["alt_group"].startswith("lab7b_alt_"):
            r = {k: v for k, v in r.items() if k != "alt_group"}      # แถวที่มีแต่คอลัมน์นี้คงเดิม (ตัดแล้วจะว่างเปล่า)
        out.append(r)
    return out


# ---- 5. ค้นวิชาในแคตตาล็อก (วิชาเลือกของหลักสูตร + GE) จากรหัสหรือชื่อ — ไม่อยู่ในตาราง course โมเดลเลยตอบ "ไม่พบ" ----
_CATALOG_ATTR_RE = re.compile(r"ชื่อ|หน่วยกิต|ภาษาอังกฤษ|รหัส|คือวิชา|กลุ่ม|หมวด|ชั่วโมง")


def _catalog_course_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ถามชื่อ/หน่วยกิต/ชื่ออังกฤษ/กลุ่มของวิชาที่อยู่ในแคตตาล็อกแต่ไม่อยู่ใน course (วิชาเลือก, GE) — อ้างด้วยรหัส 8 หลัก หรือชื่อวิชาเต็ม
    (ชื่อยาวกว่าชื่อวิชาในแผนที่อยู่ในคำถาม: "ระบบฐานข้อมูลขั้นสูง" ชนะ "ระบบฐานข้อมูล"); วิชาในแผน/รหัสที่ไม่มีจริง/ไม่ได้ถามคุณสมบัติ = None"""
    if not _CATALOG_ATTR_RE.search(question):
        return None
    try:
        own = {r[0]: r[1] or "" for r in conn.execute("SELECT code, name_th FROM course")}
        cat = [dict(r) for r in conn.execute(
            "SELECT code, course_name_th AS name_th, course_name_en AS name_en, credits, plan_slot, group_name_th "
            "FROM main.v_elective_group ORDER BY (plan_slot LIKE 'หมวดวิชาศึกษาทั่วไป%'), group_no, code").fetchall()]
    except sqlite3.OperationalError:
        return None
    by_code: dict[str, dict] = {}
    for r in cat:
        by_code.setdefault(r["code"], r)                  # วิชาเลือกของหลักสูตรมาก่อน GE (ตาม ORDER BY)
    codes = list(dict.fromkeys(_CODE8.findall(question)))
    if codes:
        if any(c in own for c in codes) or not all(c in by_code for c in codes):
            return None
        found = [by_code[c] for c in codes[:5]]
    else:
        plan_len = max((len(n) for n in own.values() if len(n) >= 4 and n in question), default=0)
        match = max((r for r in by_code.values() if len(r["name_th"] or "") >= 6 and r["name_th"] in question),
                    key=lambda r: len(r["name_th"]), default=None)
        if match is None or len(match["name_th"]) <= plan_len:
            return None
        found = [match]
    wants_en = bool(re.search(r"ภาษาอังกฤษ|ชื่ออังกฤษ", question))
    wants_credit = "หน่วยกิต" in question
    wants_group = bool(re.search(r"กลุ่ม|หมวด", question))
    parts = []
    for r in found:
        bits = [f"{r['code']} {r['name_th']}"]
        if wants_credit or not (wants_en or wants_group):
            bits.append(f"{r['credits']} หน่วยกิต")
        if wants_en:
            bits.append(f"ชื่ออังกฤษ {r['name_en'] or '-'}")
        if wants_group or not (wants_en or wants_credit):
            bits.append(f"อยู่ในกลุ่ม {r['group_name_th']} ({r['plan_slot']})")
        parts.append(" — ".join(bits))
    ids = ", ".join(f"'{r['code']}'" for r in found)
    return "; ".join(parts), found, ("SELECT code, course_name_th AS name_th, course_name_en AS name_en, credits, plan_slot, group_name_th "
                                     f"FROM main.v_elective_group WHERE code IN ({ids})")


# ---- 6. วิชาบังคับก่อน + ปี/เทอมในคำถามเดียว — โมเดลเคย error "ไม่สามารถตอบคำถามนี้ได้" ----
_TERM_ASK_RE = re.compile(r"ปีไหน|เทอมไหน|ภาคไหน|ภาคการศึกษาไหน|ภาคเรียนไหน|ปีอะไร|เทอมอะไร|ปีใด|เทอมใด")
_PREREQ_WORD_RE = re.compile(r"บังคับก่อน|ก่อนหน้า|ต้องเรียน.{0,14}ก่อน|ต้องผ่าน|เรียนต่อ|ต่อยอด|prerequisite|เรียนมาก่อน", re.I)


def _is_prereq_term_question(question: str) -> bool:
    if not _PREREQ_WORD_RE.search(question):
        return False
    if _TERM_ASK_RE.search(question):
        return True
    y, s = _term_numbers(question)                         # "ปี N เทอม M มีวิชาอะไรบ้าง และวิชาไหนมีวิชาบังคับก่อน"
    return bool(y and s and _LIST_WORD.search(question) and re.search(r"(?:และ|แล้ว|พร้อม).{0,20}(?:บังคับก่อน|prerequisite)", question, re.I))


def _prereq_term_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    if not _is_prereq_term_question(question):
        return None
    import course_names
    _citations_module()
    courses = [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in conn.execute("SELECT code, name_th, name_en FROM course")]
    names = {c["code"]: c["name_th"] for c in courses}
    terms = _first_terms(conn)
    statuses = _prereq_statuses(conn) or {}

    def none_text(code: str) -> str:                       # สถานะ not_found/unreadable = อ่านจากเล่มไม่ได้ ไม่ใช่ "ไม่มี"
        return "ยังไม่ทราบวิชาบังคับก่อน (อ่านจากเล่มไม่ได้)" if statuses.get(code) in ("not_found", "unreadable") else "ไม่มีวิชาบังคับก่อน"

    direction = course_names.prereq_direction(question, course_names.course_hints(question, courses))

    def label(code: str) -> str:
        t = terms.get(code)
        return f"{code} {names.get(code, '')} ({_TERM_LABEL.format(y=t[0], s=t[1])})" if t else f"{code} {names.get(code, '')}".strip()

    def requires_of(code: str) -> list[str]:
        got = [r[0] for r in conn.execute("SELECT requires FROM prerequisite WHERE code = ? AND kind = 'pre' ORDER BY requires", (code,))]
        try:
            got += [r[0] for r in conn.execute("SELECT requires FROM prerequisite_alt WHERE code = ? ORDER BY requires", (code,))]
        except sqlite3.OperationalError:
            pass
        return list(dict.fromkeys(got))

    if direction:
        kind, x = direction
        if kind == "after":                                # วิชาที่ต้องเรียน x ก่อน (requires = x)
            codes = [r[0] for r in conn.execute("SELECT code FROM prerequisite WHERE requires = ? AND kind = 'pre' ORDER BY code", (x,))]
            sql = f"SELECT code FROM prerequisite WHERE requires = '{x}' AND kind = 'pre'"
            text = (f"{names.get(x, x)} เป็นวิชาบังคับก่อนของ: " + ", ".join(label(c) for c in codes)) if codes \
                else (f"ไม่พบวิชาที่ต้องเรียน {names.get(x, x)} ก่อน" + (" (บางวิชาอ่านวิชาบังคับก่อนจากเล่มไม่ได้ จึงอาจไม่ครบ)"
                                                                 if any(v in ("not_found", "unreadable") for v in statuses.values()) else ""))
        else:                                              # วิชาที่ x ต้องเรียนมาก่อน
            codes = requires_of(x)
            sql = f"SELECT requires FROM prerequisite WHERE code = '{x}' AND kind = 'pre'"
            text = (f"{names.get(x, x)} ต้องเรียนมาก่อน: " + ", ".join(label(c) for c in codes)) if codes \
                else f"{names.get(x, x)} {none_text(x)}"
        return text, [{"code": c, "name_th": names.get(c), "year": (terms.get(c) or (None, None))[0],
                       "semester": (terms.get(c) or (None, None))[1]} for c in codes], sql
    y, s = _term_numbers(question)                         # รูป "ปี N เทอม M … และวิชาไหนมีวิชาบังคับก่อน"
    if not (y and s):
        return None
    sql = f"SELECT code FROM plan_item WHERE year = {y} AND semester = {s} ORDER BY id"
    in_term = list(dict.fromkeys(r[0] for r in conn.execute(sql)))
    if not in_term:
        return None
    lines, rows = [], []
    for code in in_term:
        req = requires_of(code)
        lines.append(f"{code} {names.get(code, '')}: " + (f"ต้องเรียน {', '.join(label(c) for c in req)} มาก่อน" if req else none_text(code)))
        rows.append({"code": code, "name_th": names.get(code), "requires": ", ".join(req) or None})
    return f"{_TERM_LABEL.format(y=y, s=s)} — " + "; ".join(lines), rows, sql


# ===================== โครงสร้างหน่วยกิตต่อหมวด (ก./ข./ค. → 1) → -) จากหัวข้อ 3.1.3 ของเล่ม =====================
# โมเดลเคยตอบ "หมวดวิชาเฉพาะกี่หน่วยกิต" เป็น "6, 24" (เล่มบอก 96) — ตารางนี้ไม่อยู่ใน DDL ของ prompt (CREDIT_STRUCTURE_DDL แยก)
CREDIT_STRUCTURE_DDL = """
CREATE TABLE IF NOT EXISTS credit_structure (
    id           INTEGER PRIMARY KEY,
    parent_id    INTEGER,
    level        INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
    name_th      TEXT NOT NULL,
    credits      INTEGER NOT NULL,
    pdf_page     INTEGER,
    printed_page TEXT
);
"""

_STRUCT_PAGE_RE = re.compile(r"^--- Page (\d+) ---\s*$", re.M)
_STRUCT_CRED = r"(?P<n>\d{1,3})\s*\S{0,4}?น่วยกิ"                    # ทน OCR "หหน่วยกิต" "ใหน่วยกิต" "ห+ขหน่วยกิต"
_STRUCT_TOP = re.compile(rf"^[ก-ฮ]\.\s*(?P<t>หมวดวิชา\S*(?:\s+\S+)*?)\s*{_STRUCT_CRED}")
_STRUCT_TOP_OPEN = re.compile(r"^[ก-ฮ]\.\s*(?P<t>หมวดวิชา\S*)")           # หัวข้อที่ตัวเลขอยู่บรรทัดถัดไป (ประโยคยาว)
_STRUCT_L2 = re.compile(rf"^\d\)\s*(?P<t>\S.*?)\s*{_STRUCT_CRED}")
_STRUCT_L3 = re.compile(rf"^[-•]\s*(?P<t>\S.*?)\s*{_STRUCT_CRED}")
_STRUCT_BARE = re.compile(rf"^(?P<t>กลุ่ม\S.*?)\s+{_STRUCT_CRED}")        # บางเล่ม (AIT) ไม่ใส่หมายเลข/ขีด
_STRUCT_TOTAL = re.compile(r"จ\S{0,3}านวนหน่วยกิตรวมตลอดหลักสูตร\s*(?P<n>\d{1,3})")
_STRUCT_NOTE = re.compile(r"จํานวนรวม|จำนวนรวม|ใดก็ได้|ไม่น้อยกว่า|ไม่เกิน|อย่างน้อย")
_STRUCT_HEAD = re.compile(r"^3\.\d+(?:\.\d+)*\s")


def _struct_clean(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip(" .:")


def parse_credit_structure(text: str) -> tuple[int | None, list[dict]]:
    """(หน่วยกิตรวม, โหนด) จากข้อความ OCR ทั้งเล่ม (มี marker "--- Page N ---", 40 หน้าแรก) — กฎเชิงกำหนด ไม่เดา
    โหนด = {idx, level 1-3, name_th, credits, pdf_page, parent (ชื่อ), parent_idx}; เจอหัวข้อซ้ำ (เล่มพิมพ์รายละเอียดซ้ำ) เก็บครั้งแรก
    แต่ย้ายตัวชี้ "หมวด/กลุ่มปัจจุบัน" ไปที่โหนดเดิม เพื่อให้รายการลูกที่ตามมาได้พ่อถูกตัว; กลุ่มที่ไม่มีหมายเลขรับเฉพาะในบล็อก 3.1.2"""
    total, nodes, index = None, [], {}
    cur1: dict | None = None
    cur2: dict | None = None
    in_block = False
    marks = list(_STRUCT_PAGE_RE.finditer(text))
    for i, mk in enumerate(marks):
        pg = int(mk.group(1))
        if pg > 40:
            break
        lines = [re.sub(r"\s+", " ", ln.strip()) for ln in text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)].split("\n")]
        lines = [ln for ln in lines if ln]
        for j, line in enumerate(lines):
            if total is None and (t := _STRUCT_TOTAL.search(line)):
                total = int(t.group("n"))
            if re.match(r"^3\.1\.2\s*โครงสร้างหลักสูตร", line):
                in_block = True
                continue
            if _STRUCT_HEAD.match(line):
                in_block = False
            level, title, credits = None, None, None
            if (m1 := _STRUCT_TOP.match(line)):
                level, title, credits = 1, _struct_clean(m1.group("t")), int(m1.group("n"))
            elif (m1 := _STRUCT_TOP_OPEN.match(line)):                # "ค. หมวดวิชาเลือกเสรี นักศึกษาสามารถเลือก… / … ไม่น้อยกว่า 6 หน่วยกิต"
                ahead = " ".join(lines[j: j + 3])
                m2 = re.search(r"ไม่น้อยกว่า\s*(\d{1,3})\s*\S{0,4}?น่วยกิ", ahead) or re.search(rf"{_STRUCT_CRED}", ahead)
                if m2:
                    level, title, credits = 1, _struct_clean(m1.group("t")), int(m2.group(1) if m2.re.groups == 1 else m2.group("n"))
            elif cur1 is not None and (m1 := _STRUCT_L2.match(line)):
                level, title, credits = 2, _struct_clean(m1.group("t")), int(m1.group("n"))
            elif cur1 is not None and (m1 := _STRUCT_L3.match(line)):
                level, title, credits = 3, _struct_clean(m1.group("t")), int(m1.group("n"))
            elif in_block and cur1 is not None and (m1 := _STRUCT_BARE.match(line)):
                level, title, credits = 2, _struct_clean(m1.group("t")), int(m1.group("n"))
            if level is None or not title or not re.search(r"[ก-๙]", title) or (level > 1 and (len(title) < 3 or _STRUCT_NOTE.search(title))):
                continue
            parent = None if level == 1 else (cur1 if level == 2 else (cur2 or cur1))
            key = (level, title, parent["idx"] if parent else None)
            node = index.get(key)
            if node is None:
                node = {"idx": len(nodes), "level": level, "name_th": title, "credits": credits, "pdf_page": pg,
                        "parent": parent["name_th"] if parent else None, "parent_idx": parent["idx"] if parent else None}
                nodes.append(node)
                index[key] = node
            if level == 1:
                cur1, cur2 = node, None
            elif level == 2:
                cur2 = node
    return total, nodes


def load_credit_structure(conn: sqlite3.Connection, text: str) -> dict[str, Any]:
    """โหลดโครงสร้างเข้า credit_structure เมื่อ "ผลรวมหมวดระดับบน = หน่วยกิตรวม" (เลขคณิตของเล่มเอง) — ไม่ตรง = ไม่โหลด (อ่านพลาด/แผนสองแบบ
    ปนกัน) ปล่อยให้ตอบว่าไม่มีข้อมูล ดีกว่าตอบตัวเลขผิด; รันซ้ำได้ (สร้างตารางใหม่ทุกครั้ง)"""
    total_text, nodes = parse_credit_structure(text)
    conn.executescript("DROP TABLE IF EXISTS credit_structure;" + CREDIT_STRUCTURE_DDL)
    try:
        total_db = conn.execute("SELECT total_credits FROM program LIMIT 1").fetchone()
        total = total_db[0] if total_db and total_db[0] else total_text
    except sqlite3.OperationalError:
        total = total_text
    tops = [n for n in nodes if n["level"] == 1]
    if not tops:
        return {"loaded": 0, "reason": "ไม่พบหัวข้อหมวดวิชา"}
    if total is None or sum(n["credits"] for n in tops) != total:
        return {"loaded": 0, "reason": f"ผลรวมหมวดระดับบน {sum(n['credits'] for n in tops)} ไม่ตรงหน่วยกิตรวม {total}"}
    citations = _citations_module()
    pages = {int(mk.group(1)): text[mk.end(): (marks[i + 1].start() if i + 1 < len(marks) else len(text))]
             for marks in [list(_STRUCT_PAGE_RE.finditer(text))] for i, mk in enumerate(marks)}
    printed = citations.consistent_printed({pg: citations.printed_page(body) for pg, body in pages.items()})
    # ชั้นที่สอง: ผลรวมกลุ่มย่อย (ระดับ 2) ของแต่ละหมวดต้องเท่ากับหมวด — ยอมให้เกินได้เฉพาะเท่ากับหน่วยกิตของกลุ่ม "…ทางเลือก"
    # (IT นับกลุ่มการศึกษาทางเลือกเป็นทางเลือกแทนสหกิจ: 99 = 93 + 6); ผ่านชั้นแรกโดยบังเอิญได้ (BIT: 30+96=126 แต่กลุ่มย่อยรวม 90 → "96" น่าจะเป็น 90)
    for top in tops:
        kids = [n for n in nodes if n["parent_idx"] == top["idx"] and n["level"] == 2]
        if not kids:
            continue
        diff = sum(k["credits"] for k in kids) - top["credits"]
        if diff != 0 and not any(diff == k["credits"] and "ทางเลือก" in k["name_th"] for k in kids):
            return {"loaded": 0, "reason": f"ผลรวมกลุ่มย่อยของ {top['name_th']} {sum(k['credits'] for k in kids)} ไม่ตรงหมวด {top['credits']}"}
    ids: dict[int, int] = {}
    for n in nodes:
        cur = conn.execute("INSERT INTO credit_structure (parent_id, level, name_th, credits, pdf_page, printed_page) VALUES (?,?,?,?,?,?)",
                           (ids.get(n["parent_idx"]), n["level"], n["name_th"], n["credits"], n["pdf_page"], printed.get(n["pdf_page"])))
        ids[n["idx"]] = cur.lastrowid
    conn.commit()
    return {"loaded": len(nodes), "reason": None, "total": total}


def cmd_load_credit_structure(args) -> None:
    db = Path(args.database)
    if not db.exists():
        raise SystemExit(f"ไม่พบ {db} — ต้อง `load` แผนหลักเข้าไปก่อน")
    text = Path(args.text).read_text(encoding="utf-8").replace("\r", "")
    conn = open_db(db)
    stats = load_credit_structure(conn, text)
    conn.close()
    if stats["loaded"]:
        print(f"  credit_structure: โหลด {stats['loaded']} โหนด (ผลรวมหมวดระดับบน = {stats['total']} หน่วยกิตตรงกับเล่ม)")
    else:
        print(f"  credit_structure: ไม่โหลด — {stats['reason']} (คำถามโครงสร้างหน่วยกิตจะตอบว่าไม่มีข้อมูล ไม่ใช่เดา)")


# ---- ทางลัดตอบ ----
# ศัพท์โครงสร้างจริงเท่านั้น — "กลุ่ม"/"หมวด" เฉย ๆ ชนชื่อวิชา (ชุดเฉลย: "โครงงานกลุ่ม 3", "เทคโนโลยีกลุ่มเมฆ"); กรณีนั้นรับเฉพาะเมื่อชื่อกลุ่มในตารางโครงสร้างปรากฏในคำถาม
_STRUCT_CUE = re.compile(r"หมวดวิชา|กลุ่มวิชา|เลือกเสรี|ศึกษาทั่วไป|โครงสร้างหลักสูตร|กี่หมวด")
_STRUCT_CUE_LOOSE = re.compile(r"กลุ่ม|หมวด")
_STRUCT_CREDIT_ASK = re.compile(r"กี่หน่วยกิต|หน่วยกิตเท่า|หน่วยกิตกี่")
_STRUCT_COMPOSE_ASK = re.compile(r"ประกอบด้วย|แบ่งเป็น|กี่หมวด|กี่กลุ่ม|โครงสร้างหลักสูตร|หมวดอะไรบ้าง|กลุ่มอะไรบ้าง|มีอะไรบ้าง")
_STRUCT_OVERVIEW = re.compile(r"โครงสร้างหลักสูตร|กี่หมวด|หมวดอะไรบ้าง")
_STRUCT_GENERIC = re.compile(r"หมวดวิชาศึกษาทั่วไป|หมวดวิชาเฉพาะ|เลือกเสรี|โครงสร้างหลักสูตร|กลุ่มวิชาแกน|กี่หมวด")


def _is_credit_structure_question(question: str, loose: bool = False) -> bool:
    """ถามหน่วยกิต/องค์ประกอบของหมวด-กลุ่มวิชาตามโครงสร้างหลักสูตร (ไม่ใช่วิชาเดี่ยว/ปี-เทอม/หน่วยกิตรวมทั้งหลักสูตร);
    loose=True ยอมรับคำว่า "กลุ่ม/หมวด" เฉย ๆ (ผู้เรียกต้องยืนยันด้วยชื่อกลุ่มในตารางเอง)"""
    return bool((_STRUCT_CUE.search(question) or (loose and _STRUCT_CUE_LOOSE.search(question)))
                and (_STRUCT_CREDIT_ASK.search(question) or _STRUCT_COMPOSE_ASK.search(question))
                and not _CODE8.search(question) and not any(_term_numbers(question)))


def _credit_structure_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    strict = _is_credit_structure_question(question)
    if not strict and not _is_credit_structure_question(question, loose=True):
        return None
    sql = "SELECT name_th, level, credits, parent, pdf_page FROM credit_structure"
    try:
        nodes = [dict(r) for r in conn.execute(
            "SELECT s.id, s.parent_id, s.level, s.name_th, s.credits, s.pdf_page, s.printed_page, p.name_th AS parent "
            "FROM credit_structure s LEFT JOIN credit_structure p ON p.id = s.parent_id ORDER BY s.id").fetchall()]
    except sqlite3.OperationalError:
        return None                                       # DB ที่ไม่มีตาราง → ทางเดิม
    if not nodes:                                         # โหลดแล้วแต่ตรวจเลขคณิตไม่ผ่าน → ไม่เดา
        return ("ไม่มีข้อมูลโครงสร้างหน่วยกิตตามหมวดของหลักสูตรนี้ในระบบ (อ่านจากเล่มได้ไม่น่าเชื่อถือ)", [], sql) \
            if _STRUCT_GENERIC.search(question) else None
    q = re.sub(r"\s+", "", question)
    core = lambda n: re.sub(r"^(?:หมวดวิชา|หมวด|กลุ่มวิชา|กลุ่ม|วิชา)", "", re.sub(r"\s+", "", n["name_th"]))
    hits = [(len(core(n)), n) for n in nodes if len(core(n)) >= (3 if strict else 6) and core(n) in q]   # คำว่า "กลุ่ม" เฉย ๆ ต้องมีชื่อกลุ่มยาว ≥ 6
    top = [n for n in nodes if n["level"] == 1]
    total = sum(n["credits"] for n in top)

    def row(n: dict) -> dict:
        return {"name_th": n["name_th"], "level": n["level"], "credits": n["credits"], "parent": n["parent"],
                "pdf_page": n["pdf_page"], "printed_page": n["printed_page"]}

    if not hits:
        if not strict or not _STRUCT_OVERVIEW.search(question):
            return None
        return (f"โครงสร้างหลักสูตรแบ่งเป็น {len(top)} หมวด (รวม {total} หน่วยกิต): " + ", ".join(f"{n['name_th']} {n['credits']}" for n in top),
                [row(n) for n in top], sql)
    best = max(h[0] for h in hits)
    chosen = [n for ln, n in hits if ln == best]
    parts, rows = [], []
    for n in chosen:
        kids = [k for k in nodes if k["parent_id"] == n["id"]]
        text = f"{n['name_th']}: {n['credits']} หน่วยกิต" + (f" (อยู่ใน{n['parent']})" if n["parent"] else "")
        if kids:
            text += " — ประกอบด้วย " + ", ".join(f"{k['name_th']} {k['credits']}" for k in kids)
            extra = sum(k["credits"] for k in kids) - n["credits"]
            alt = next((k for k in kids if extra > 0 and k["credits"] == extra and "ทางเลือก" in k["name_th"]), None)
            if n["level"] == 1 and alt:                       # ผลรวมกลุ่มย่อยเกินหมวดเท่ากับกลุ่ม "…ทางเลือก" พอดี = ไม่นับรวม (ข้อสรุปจากเลขคณิตของเล่ม)
                text += f" (หมายเหตุ: {alt['name_th']} {alt['credits']} ไม่นับรวมใน {n['credits']})"
        parts.append(text)
        rows += [row(n)] + [row(k) for k in kids]
    return "; ".join(parts), rows, sql


# ===================== คำอธิบายรายวิชาจากภาคผนวกของเล่ม =====================
# เล่มพิมพ์คำอธิบายทุกวิชา (บรรทัดหัว "รหัส ชื่อ n(a-b-c)" / ชื่ออังกฤษ / วิชาบังคับก่อน / PREREQUISITE / เนื้อหาไทย / เนื้อหาอังกฤษ)
# แต่ DB ไม่เคยเก็บ (course.description_th ว่างทุกวิชา) → "วิชา X เรียนเกี่ยวกับอะไร" ตอบเป็นรายการวิชา/ปฏิเสธ
# ตารางแยกจาก DDL ของ prompt (โมเดลไม่เห็น) ตอบด้วยทางลัดเชิงกำหนด ยกข้อความจากเล่ม ไม่สรุปเอง
COURSE_DESCRIPTION_DDL = """
CREATE TABLE IF NOT EXISTS course_description (
    code           TEXT PRIMARY KEY,
    name_th        TEXT,
    description_th TEXT,
    description_en TEXT,
    pdf_page       INTEGER,
    printed_page   TEXT
);
"""

_DESC_HEADER = re.compile(r"^(?P<code>\d{8})\s+(?P<name>\S.*?)\s+(?P<cr>\d{1,2})\s*\(\d{1,2}-\d{1,2}-\d{1,3}\)\s*$")
_DESC_PREREQ = re.compile(r"^(?:วิชาบังคับก่อน|PREREQUISITE|CO-?REQUISITE|วิชาเรียนควบ)", re.I)


def _latin_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(1 for c in letters if c.isascii()) / len(letters) if letters else 0.0


def parse_course_descriptions(text: str) -> list[dict]:
    """คำอธิบายรายวิชาจากข้อความ OCR ทั้งเล่ม (marker "--- Page N ---") — เลือกเฉพาะก้อนที่มีหัวข้อ "วิชาบังคับก่อน/PREREQUISITE"
    (รหัสเดียวกันปรากฏหลายที่ เช่น รายการวิชาศึกษาทั่วไป/โครงสร้าง ซึ่งไม่มีเนื้อหา) ถ้ามีหลายก้อนเลือกก้อนที่เนื้อหายาวที่สุด
    ไทย = บรรทัดหลัง PREREQUISITE ที่ไม่ใช่ภาษาอังกฤษ, อังกฤษ = บรรทัดที่เป็นตัวอักษรละติน > 70% (และบรรทัดต่อเนื่อง); ไม่มีเนื้อหาเลย = ไม่คืน"""
    blocks: dict[str, list[dict]] = {}
    cur = None
    marks = list(_STRUCT_PAGE_RE.finditer(text))
    for i, mk in enumerate(marks):
        pg = int(mk.group(1))
        body = text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        for raw in body.split("\n"):
            line = re.sub(r"\s+", " ", raw.strip())
            if not line:
                continue
            h = _DESC_HEADER.match(line)
            if h:
                cur = {"code": h.group("code"), "name_th": h.group("name"), "pdf_page": pg, "lines": []}
                blocks.setdefault(cur["code"], []).append(cur)
            elif cur is not None:
                cur["lines"].append(line)
    out = []
    for code, bl in blocks.items():
        best = None
        for d in bl:
            th: list[str] = []
            en: list[str] = []
            seen = False
            for line in d["lines"]:
                if _DESC_PREREQ.match(line):
                    seen = True
                    continue
                if not seen:
                    continue
                if (_latin_ratio(line) > 0.7 and len(line) > 12) or (en and _latin_ratio(line) > 0.5):
                    en.append(line)
                elif not en:                                   # ไทยมาก่อนอังกฤษเสมอ — บรรทัดหลังจากเริ่มอังกฤษไม่ใช่ไทย (ส่วนหัว/ท้ายหน้า)
                    th.append(line)
            cand = {"code": code, "name_th": d["name_th"], "description_th": " ".join(th), "description_en": " ".join(en),
                    "pdf_page": d["pdf_page"], "_seen": seen}
            size = len(cand["description_th"]) + len(cand["description_en"])
            if seen and size > 0 and (best is None or size > best[0]):
                best = (size, cand)
        if best:
            best[1].pop("_seen")
            out.append(best[1])
    return out


def load_course_descriptions(conn: sqlite3.Connection, text: str) -> dict[str, Any]:
    """โหลดตาราง course_description (สร้างใหม่ทุกครั้ง รันซ้ำได้) พร้อมเลขหน้าที่พิมพ์ (consistent_printed)"""
    rows = parse_course_descriptions(text)
    conn.executescript("DROP TABLE IF EXISTS course_description;" + COURSE_DESCRIPTION_DDL)
    citations = _citations_module()
    marks = list(_STRUCT_PAGE_RE.finditer(text))
    pages = {int(mk.group(1)): text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)] for i, mk in enumerate(marks)}
    printed = citations.consistent_printed({pg: citations.printed_page(body) for pg, body in pages.items()})
    conn.executemany("INSERT OR REPLACE INTO course_description VALUES (?,?,?,?,?,?)",
                     [(r["code"], r["name_th"], r["description_th"], r["description_en"], r["pdf_page"], printed.get(r["pdf_page"])) for r in rows])
    conn.commit()
    return {"loaded": len(rows)}


def cmd_load_course_descriptions(args) -> None:
    db = Path(args.database)
    if not db.exists():
        raise SystemExit(f"ไม่พบ {db} — ต้อง `load` แผนหลักเข้าไปก่อน")
    conn = open_db(db)
    stats = load_course_descriptions(conn, Path(args.text).read_text(encoding="utf-8").replace("\r", ""))
    conn.close()
    print(f"  course_description: โหลดคำอธิบาย {stats['loaded']} วิชา (ยกข้อความจากภาคผนวกของเล่ม)")


_DESC_ASK = re.compile(r"เกี่ยวกับอะไร|สอนอะไร|เรียนอะไร|เรียนเรื่องอะไร|คำอธิบายรายวิชา|คําอธิบายรายวิชา|เนื้อหา(?:ของ)?วิชา|เนื้อหารายวิชา|รายละเอียดวิชา|description", re.I)
_DESC_MAX_TH, _DESC_MAX_EN = 1100, 420


def _course_description_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ถามคำอธิบาย/เนื้อหาของวิชา (ระบุรหัส 8 หลัก หรือชื่อวิชา) → ยกข้อความไทย (+อังกฤษ) จากภาคผนวกของเล่มพร้อมเลขหน้า;
    วิชารู้จักแต่เล่มไม่มีคำอธิบาย = บอกตรง ๆ (ไม่ให้โมเดลเดา); ไม่ได้อ้างวิชา/DB ไม่มีตาราง = None (ทางเดิม)"""
    if not _DESC_ASK.search(question):
        return None
    try:
        known = {r[0]: (r[1] or "") for r in conn.execute("SELECT code, name_th FROM course")}
        described = {r["code"]: dict(r) for r in conn.execute(
            "SELECT code, name_th, description_th, description_en, pdf_page, printed_page FROM course_description").fetchall()}
        for r in conn.execute("SELECT code, course_name_th FROM main.v_elective_group"):
            known.setdefault(r[0], r[1] or "")
    except sqlite3.OperationalError:
        return None
    for code, d in described.items():
        known.setdefault(code, d["name_th"] or "")
    codes = [c for c in dict.fromkeys(_CODE8.findall(question)) if c in known][:3]
    if not codes:
        qn = re.sub(r"\s+", "", question)
        best = max(((len(re.sub(r"\s+", "", n)), c) for c, n in known.items() if len(re.sub(r"\s+", "", n)) >= 4 and re.sub(r"\s+", "", n) in qn),
                   default=None)
        if best is None:
            return None
        codes = [c for ln, c in ((len(re.sub(r"\s+", "", n)), c) for c, n in known.items() if re.sub(r"\s+", "", n) and re.sub(r"\s+", "", n) in qn)
                 if ln == best[0]][:2]
    if not codes:
        return None
    parts, rows = [], []
    for code in codes:
        d = described.get(code)
        name = known.get(code) or (d or {}).get("name_th") or ""
        if not d or not ((d["description_th"] or "").strip() or (d["description_en"] or "").strip()):
            parts.append(f"ไม่พบคำอธิบายรายวิชา {code} {name} ในเล่มหลักสูตร".strip())
            continue
        th, en = (d["description_th"] or "").strip(), (d["description_en"] or "").strip()
        text = f"{code} {name}: " + (th[:_DESC_MAX_TH] + ("…" if len(th) > _DESC_MAX_TH else "") if th else en[:_DESC_MAX_TH])
        if th and en:
            text += f" (English: {en[:_DESC_MAX_EN]}{'…' if len(en) > _DESC_MAX_EN else ''})"
        parts.append(text)
        rows.append({"code": code, "name_th": name, "description_th": th, "description_en": en,
                     "pdf_page": d["pdf_page"], "printed_page": d["printed_page"]})
    sql = "SELECT code, name_th, description_th, description_en, pdf_page FROM course_description WHERE code IN (" + ", ".join(f"'{c}'" for c in codes) + ")"
    return "; ".join(parts), rows, sql


# ===================== หัวข้อเล่ม มคอ.2 (ชื่อหลักสูตร/ปริญญา/อาชีพ/ปรัชญา/วัตถุประสงค์/คุณสมบัติ/เกณฑ์จบ) =====================
# แม่แบบ มคอ.2 มีหัวข้อมาตรฐานเดียวกันทุกเล่ม (ตรวจกับ 4 เล่มแล้ว) แต่ข้อความไม่อยู่ใน DB → คำถามเชิงบรรยายตอบไม่ได้
# สกัดแบบยกข้อความ (ไม่สรุปเอง): จับบรรทัดหัวข้อ → เก็บเนื้อหาจนถึงหัวข้อถัดไป (ตัดเศษหน้ากระดาษ/ขยะ OCR) พร้อมเลขหน้า
# ตารางแยกจาก DDL ของ prompt; ไม่พบหัวข้อ = บอกตรง ๆ ไม่ให้โมเดลเดา
BOOK_SECTION_DDL = """
CREATE TABLE IF NOT EXISTS book_section (
    topic        TEXT PRIMARY KEY,
    heading      TEXT,
    body         TEXT,
    pdf_page     INTEGER,
    printed_page TEXT
);
"""

_SECTION_MAX_CHARS = 1200
_THAI_MARKS_RE = re.compile("[ัิ-ฺ็-๎]")      # สระบน/ล่าง วรรณยุกต์ ทัณฑฆาต นิคหิต — OCR ทำหล่นบ่อย จึงตัดทิ้งก่อนเทียบหัวข้อ
# (หัวข้อ, regex เข้ม, regex หลวม) เทียบกับข้อความหัวข้อที่ตัดวรรณยุกต์/ช่องว่างแล้ว และ ซ→ช (OCR สับสน "ซือ"/"ชื่อ")
_SECTION_TOPICS = (
    ("ชื่อหลักสูตร", r"^ชอหลกสตร$", None),
    ("ชื่อปริญญา", r"^ชอปรญญา(?:และสาขาวชา)?$", None),
    ("อาชีพ", r"^อาชพทสามารถประกอบ", None),
    ("สถานที่จัดการเรียนการสอน", r"^สถานทจดการเรยนการสอน$", None),
    ("ปรัชญา", r"^ปรชญา$", r"^ปรชญาความสาคญ"),
    ("วัตถุประสงค์", r"^วตถประสงค(?:ของหลกสตร)?$", None),
    ("คุณสมบัติผู้เข้าศึกษา", r"^คณสมบตของผเขาศกษา$", None),
    ("เกณฑ์สำเร็จการศึกษา", r"^เกณฑ(?:การ)?สาเรจการศกษา(?:ตามหลกสตร)?$", None),
)
_SECTION_LABEL = {
    "ชื่อหลักสูตร": "ชื่อหลักสูตร", "ชื่อปริญญา": "ชื่อปริญญาและสาขาวิชา", "อาชีพ": "อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา",
    "สถานที่จัดการเรียนการสอน": "สถานที่จัดการเรียนการสอน", "ปรัชญา": "ปรัชญาของหลักสูตร", "วัตถุประสงค์": "วัตถุประสงค์ของหลักสูตร",
    "คุณสมบัติผู้เข้าศึกษา": "คุณสมบัติของผู้เข้าศึกษา", "เกณฑ์สำเร็จการศึกษา": "เกณฑ์การสำเร็จการศึกษา"}
_SECTION_HEAD = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})[\.,]?\s+(\S.*)$")
_SECTION_NOT_HEAD = re.compile(r"^(?:หน่วยกิต|สัปดาห์|ปี|ภาคการศึกษา|เดือน|ชั่วโมง|คน|วิชา|ครั้ง|ข้อ)(?:\s|$)")
_SECTION_JUNK_PREFIX = re.compile(r"^(?:\[[^\]\s]{0,3}\]?\s*\|?\s*|[Mm]1?\s+|Vv\]?\s*|LU\s+|[|\]]\s*)")
_SECTION_JUNK_LABEL = re.compile(r"^[A-Za-z]{2,8}\s+(?=\(ภาษา)")
_SECTION_FOOTER = re.compile(r"^วท\.บ\.?\s*\(|สจล\.?$|^มคอ\.?\s*\d?$")


def _section_key(text: str) -> str:
    return re.sub("ช+", "ช", _THAI_MARKS_RE.sub("", text).replace(" ", "").replace("ซ", "ช"))     # "ชซือ" (ตัวอักษรเกิน) → "ชอ"


def _section_lines(text: str) -> list[tuple[int, str]]:
    """(เลขหน้า PDF, บรรทัด) ทั้งเล่มต่อกันเป็นสายเดียว (ข้ามหน้าได้) — ตัดบรรทัดสารบัญไม่ได้ที่นี่ (ทำตอนจับหัวข้อ)"""
    marks = list(_STRUCT_PAGE_RE.finditer(text))
    raw: list[tuple[int, str]] = []
    for i, mk in enumerate(marks):
        pg = int(mk.group(1))
        for line in text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)].split("\n"):
            line = re.sub(r"\s+", " ", line.strip())
            if line:
                raw.append((pg, line))
    seen: dict[str, int] = {}
    for _, line in raw:
        seen[line] = seen.get(line, 0) + 1
    out = []
    for pg, line in raw:
        if seen[line] >= 5 and len(line) > 8:                        # หัวท้ายกระดาษที่ซ้ำทุกหน้า
            continue
        if re.fullmatch(r"\d{1,3}", line) or _SECTION_FOOTER.search(line):
            continue
        out.append((pg, line))
    return out


def _section_clean(line: str) -> str:
    line = _SECTION_JUNK_PREFIX.sub("", line).strip()
    line = _SECTION_JUNK_LABEL.sub("", line)
    chars = [c for c in line if not c.isspace()]
    if len(chars) < 3 or sum(1 for c in chars if c.isalnum() or "฀" <= c <= "๿") / len(chars) < 0.6:
        return ""
    return line


def _section_heading(line: str) -> tuple[str, int, str] | None:
    """บรรทัดหัวข้อมีเลขข้อ ("2.2 คุณสมบัติ…", "11, สถานการณ์…") → (เลขข้อ, ความลึก, ข้อความ); บรรทัดสารบัญ (ลงท้ายเลขหน้า) ไม่นับ"""
    mt = _SECTION_HEAD.match(_SECTION_JUNK_PREFIX.sub("", line))
    if not mt or re.search(r"\s\d{1,3}$", line) or _SECTION_NOT_HEAD.match(mt.group(2)) or len(mt.group(2)) > 120:
        return None
    return mt.group(1), mt.group(1).count(".") + 1, mt.group(2)


def parse_book_sections(text: str) -> list[dict]:
    """หัวข้อมาตรฐาน มคอ.2 → [{topic, heading, body, pdf_page}] ยกข้อความตามเล่ม (เนื้อหาถึงหัวข้อถัดไป ไม่เกิน _SECTION_MAX_CHARS ตัดที่ขอบบรรทัด)
    ใช้ "หัวข้อเข้ม" ที่พบก่อนเสมอ (เช่น 1.1 ปรัชญา) แล้วจึงลดเป็นหัวข้อรวม (ปรัชญา ความสำคัญ และวัตถุประสงค์…); ไม่พบ/ไม่มีเนื้อหา = ไม่คืนหัวข้อนั้น"""
    lines = _section_lines(text)
    heads = [(i, h) for i, (_, ln) in enumerate(lines) if (h := _section_heading(ln))]
    out = []
    for topic, strict, loose in _SECTION_TOPICS:
        found = None
        for rx in (strict, loose):
            if rx is None:
                continue
            for i, (num, depth, title) in heads:
                if re.search(rx, _section_key(title)):
                    found = (i, num, depth, title)
                    break
            if found:
                break
        if not found:
            continue
        i, num, depth, title = found
        body: list[str] = []
        size = 0
        for pg, ln in lines[i + 1:]:
            h = _section_heading(ln)
            if h and not h[0].startswith(num + "."):                 # หัวข้อถัดไปที่ไม่ใช่หัวข้อย่อยของหัวข้อนี้
                break
            if re.match(r"^หมวดที่?\s*\d", ln):
                break
            clean = _section_clean(ln)
            if not clean:
                continue
            if body and size + len(clean) + 1 > _SECTION_MAX_CHARS:
                break
            body.append(clean)
            size += len(clean) + 1
        text_body = " ".join(body)[:_SECTION_MAX_CHARS]
        if len(text_body) >= 10:
            out.append({"topic": topic, "heading": f"{num} {title}", "body": text_body, "pdf_page": lines[i][0]})
    return out


def load_book_sections(conn: sqlite3.Connection, text: str) -> dict[str, Any]:
    """โหลดตาราง book_section (สร้างใหม่ทุกครั้ง รันซ้ำได้) พร้อมเลขหน้าที่พิมพ์ (consistent_printed)"""
    rows = parse_book_sections(text)
    conn.executescript("DROP TABLE IF EXISTS book_section;" + BOOK_SECTION_DDL)
    citations = _citations_module()
    marks = list(_STRUCT_PAGE_RE.finditer(text))
    pages = {int(mk.group(1)): text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)] for i, mk in enumerate(marks)}
    printed = citations.consistent_printed({pg: citations.printed_page(body) for pg, body in pages.items()})
    conn.executemany("INSERT OR REPLACE INTO book_section VALUES (?,?,?,?,?)",
                     [(r["topic"], r["heading"], r["body"], r["pdf_page"], printed.get(r["pdf_page"])) for r in rows])
    conn.commit()
    return {"loaded": len(rows)}


def cmd_load_book_sections(args) -> None:
    db = Path(args.database)
    if not db.exists():
        raise SystemExit(f"ไม่พบ {db} — ต้อง `load` แผนหลักเข้าไปก่อน")
    conn = open_db(db)
    stats = load_book_sections(conn, Path(args.text).read_text(encoding="utf-8").replace("\r", ""))
    conn.close()
    print(f"  book_section: โหลดหัวข้อ มคอ.2 {stats['loaded']}/{len(_SECTION_TOPICS)} หัวข้อ (ยกข้อความจากเล่ม)")


_SECTION_Q = (
    ("ชื่อหลักสูตร", r"หลักสูตร(?:นี้)?ชื่อ(?:ว่า)?อะไร|ชื่อ(?:เต็ม)?(?:ภาษา(?:ไทย|อังกฤษ))?(?:ของ)?หลักสูตร"),
    ("ชื่อปริญญา", r"ชื่อ(?:ย่อ)?ปริญญา|ได้(?:รับ)?ปริญญา|ปริญญาอะไร|ได้(?:รับ)?วุฒิ|วุฒิอะไร"),
    ("อาชีพ", r"(?<!มือ)อาชีพ|ทำงานอะไรได้"),
    ("สถานที่จัดการเรียนการสอน", r"สถานที่จัดการเรียน(?:การ)?สอน"),
    ("ปรัชญา", r"ปรัชญา"),
    ("วัตถุประสงค์", r"วัตถุประสงค์(?:ของ)?หลักสูตร|หลักสูตร(?:นี้)?(?:มี)?วัตถุประสงค์"),
    ("คุณสมบัติผู้เข้าศึกษา", r"คุณสมบัติ(?:ของ)?ผู้(?:เข้า)?(?:ศึกษา|เรียน|สมัคร)|ใคร(?:บ้าง)?(?:สามารถ)?(?:สมัคร|เข้า)เรียน|ใคร(?:บ้าง)?(?:สามารถ)?เรียน.{0,14}ได้"),
    ("เกณฑ์สำเร็จการศึกษา", r"(?:เกณฑ์|เงื่อนไข)(?:การ)?(?:สำเร็จการศึกษา|จบการศึกษา|จบ)"),
)


def _book_section_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ถามหัวข้อมาตรฐาน มคอ.2 (ชื่อหลักสูตร/ปริญญา/อาชีพ/ปรัชญา/วัตถุประสงค์/คุณสมบัติผู้เข้าศึกษา/เกณฑ์จบ/สถานที่) → ยกข้อความตามเล่มพร้อมหน้า;
    หัวข้อที่อ่านไม่ได้จากเล่ม = บอกตรง ๆ; ไม่มีตาราง/ไม่เข้าหัวข้อ/อ้างรหัสวิชา = None (ทางเดิม)"""
    q = question.replace("ํา", "ำ")                    # "สํา" (นิคหิต+า) → "สำ"
    if _CODE8.search(q):
        return None
    topics = [t for t, rx in _SECTION_Q if re.search(rx, q)][:3]
    if not topics:
        return None
    try:
        have = {r["topic"]: dict(r) for r in conn.execute("SELECT topic, heading, body, pdf_page, printed_page FROM book_section")}
    except sqlite3.OperationalError:
        return None
    if not have:
        return None
    qn = re.sub(r"\s+", "", q)
    for (name,) in conn.execute("SELECT name_th FROM course WHERE length(name_th) >= 5"):    # ชื่อวิชาที่มีคำหัวข้อติดอยู่ (เช่น "…มืออาชีพ") = คำถามเรื่องวิชา
        if re.sub(r"\s+", "", name) in qn:
            return None
    parts, rows = [], []
    for t in topics:
        label = _SECTION_LABEL[t]
        if t not in have:
            parts.append(f"ไม่พบหัวข้อ{label}ในเล่มหลักสูตร")
            continue
        d = have[t]
        parts.append(f"{label}: {d['body']}")
        rows.append({"topic": t, "heading": d["heading"], "body": d["body"], "pdf_page": d["pdf_page"], "printed_page": d["printed_page"]})
    sql = "SELECT topic, heading, body, pdf_page FROM book_section WHERE topic IN (" + ", ".join(f"'{t}'" for t in topics) + ")"
    return "\n".join(parts), rows, sql


def _attach_citations(conn: sqlite3.Connection, result: dict[str, Any]) -> None:
    """อ้างอิงหน้าในเล่ม (citations.py) — แนบด้วยโค้ด ไม่ให้ LLM เขียนเลขหน้า; ไม่รวมใน answer
    (ใส่ตัวเลขหน้าในข้อความคำตอบจะทำให้การตรวจคำตอบเจอเลขที่ไม่ใช่คำตอบ)"""
    citations = _citations_module()
    page_rows = [r for r in result["rows"] if isinstance(r, dict) and r.get("pdf_page")]
    if page_rows:                                          # คำตอบจากโครงสร้างหน่วยกิต: อ้างหน้าที่พบหัวข้อ (ไม่เกิน MAX_CITED หน้า)
        seen: list[tuple] = []
        for r in page_rows:
            key = (r["pdf_page"], r.get("printed_page"))
            if key not in seen:
                seen.append(key)
        result["citations"] = [{"pdf_page": p, "printed_page": pr, "courses": []} for p, pr in seen[:citations.MAX_CITED]]
        result["citation_text"] = citations.format_citation(result["citations"])
        return
    lookup = citations.load_lookup(conn)
    if lookup is not None:
        result["citations"] = citations.citations_for(result["rows"], result["sql"], lookup)
        result["citation_text"] = citations.format_citation(result["citations"])


def _self_chosen_slot_note(conn: sqlite3.Connection, question: str) -> str:
    """ช่องที่นักศึกษาเลือกเองของปี/เทอมที่ถามในคำถามควบ (plan_slot: wildcard / A หรือ B / เลือก 1 กลุ่ม) เช่น
    "ช่องที่นักศึกษาเลือกเอง: วิชาเลือกด้านภาษาและการสื่อสาร 3 หน่วยกิต" — v_plan ไม่มีช่อง wildcard แต่ n_courses นับรวม
    ผู้ใช้เลยเห็น "6 วิชา" ลิสต์ 5 ชื่อ; ไม่ใช่คำถามควบ/ไม่ระบุปีเทอม/ไม่มีตาราง/ไม่มีช่อง = "" """
    if not _term_summary_hint_text(question):
        return ""
    y, s = _TERM_YEAR_NUM.search(question), _TERM_SEM_NUM.search(question)
    if not (y and s):
        return ""
    try:
        slots = conn.execute("SELECT name_th, credits FROM plan_slot WHERE year = ? AND semester = ? ORDER BY id",
                             (int(y.group(1)), int(s.group(1)))).fetchall()
    except sqlite3.OperationalError:
        return ""
    return "; ".join(f"ช่องที่นักศึกษาเลือกเอง: {n} {c} หน่วยกิต" for n, c in slots)


def _has_view(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone() is not None


def _elective_hint_text(conn: sqlite3.Connection, question: str) -> str:
    """คำใบ้เมื่อถามเรื่องวิชาเลือก: ชี้ให้ใช้ view v_elective_group (โมเดลเคยแต่งชื่อ v_elective_group_course เอง)
    เปิดเฉพาะเมื่อคำถามพูดถึงวิชาเลือก และแคตตาล็อกของหลักสูตรนี้มีข้อมูล — นอกนั้นคืน "" (prompt เหมือนเดิมทุกตัวอักษร)"""
    if not _ELECTIVE_Q.search(question):
        return ""
    try:
        if not conn.execute("SELECT 1 FROM elective_group LIMIT 1").fetchone():
            return ""
    except sqlite3.OperationalError:
        return ""
    if _GE_Q.search(question):
        # ถามถึงหมวดวิชาศึกษาทั่วไป (scope_elective_view ไม่ซ่อนแคตตาล็อก GE ในคำถามนี้) — ตัวอย่างต้องชี้ที่ GE ไม่ใช่วิชาเลือกของหลักสูตร
        return (
            "แคตตาล็อกหมวดวิชาศึกษาทั่วไป (GE) อยู่ใน view v_elective_group ที่ plan_slot ขึ้นต้น 'หมวดวิชาศึกษาทั่วไป' เท่านั้น "
            "(ห้ามแต่งชื่อ view/ตารางอื่น) คอลัมน์: plan_slot, group_no, group_name_th, code, course_name_th, course_name_en, credits; "
            "group_no 1=อัตลักษณ์สถาบัน 2=บุคคลและวิชาชีพ 3=การจัดการและผู้นำ 4=ภาษาและการสื่อสาร (ตัวอย่างใช้กลุ่ม 4 เปลี่ยนเลขตามที่ถาม)\n"
            "- รายวิชาของกลุ่ม: SELECT code, course_name_th, credits FROM v_elective_group "
            "WHERE plan_slot LIKE 'หมวดวิชาศึกษาทั่วไป%' AND group_no = 4 ORDER BY code\n"
            "- นับจำนวนวิชา: SELECT COUNT(*) FROM v_elective_group "
            "WHERE plan_slot LIKE 'หมวดวิชาศึกษาทั่วไป%' AND group_no = 4\n\n"
        )
    return (                                                  # วิชาเลือกของหลักสูตร: scope_elective_view ซ่อนแคตตาล็อก GE ให้แล้ว ไม่ต้องกรองเอง
        "วิชาเลือกของหลักสูตรนี้ (จากแคตตาล็อก) อยู่ใน view v_elective_group เท่านั้น "
        "(ห้ามแต่งชื่อ view/ตารางอื่น) คอลัมน์: plan_slot, credits_required, group_no, group_name_th, group_name_en, "
        "code, course_name_th, course_name_en, credits\n"
        "- รายวิชาเลือกทั้งหมด/ของกลุ่ม: SELECT group_no, group_name_th, code, course_name_th, credits "
        "FROM v_elective_group [WHERE group_no = ?] ORDER BY group_no, code\n"
        "- ต้องเลือกกี่หน่วยกิต/กี่กลุ่ม: SELECT DISTINCT plan_slot, credits_required FROM v_elective_group\n\n"
    )



def scope_elective_view(conn: sqlite3.Connection, question: str) -> bool:
    """ตัวกันแบบกำหนดตายตัวของ _elective_hint_text: ให้ v_elective_group "ในคำถามนี้" ไม่มีแคตตาล็อกหมวดวิชาศึกษาทั่วไป (GE 303 วิชา)
    เว้นแต่คำถามพูดถึง GE เอง — กรองที่ต้นทางด้วย TEMP VIEW (เทคนิคเดียวกับ use_slot_aware_credit_view; temp ถูกค้นก่อน main
    และเขียนได้แม้ mode=ro) เพราะกรองหลังได้แถวแล้วไม่ทัน: SQL ที่โมเดลเขียนไม่กรองจะโดน LIMIT 200 ตัดก่อน (เจอจริงกับ DSBA: ได้ 23 จาก 43 วิชา)
    ทุกครั้งที่เรียกจะลบ view ชั่วคราวเดิมก่อน เพื่อให้คำถามถัดไปบน connection เดียวกันไม่ติดสถานะของคำถามก่อนหน้า
    คืน True ถ้าตัด GE ออก"""
    try:
        conn.execute("DROP VIEW IF EXISTS temp.v_elective_group")
        if _GE_Q.search(question) or not _ELECTIVE_Q.search(question) or not _has_view(conn, "v_elective_group"):
            return False
        conn.execute("CREATE TEMP VIEW v_elective_group AS SELECT * FROM main.v_elective_group "
                     "WHERE plan_slot NOT LIKE 'หมวดวิชาศึกษาทั่วไป%'")
        return True
    except sqlite3.Error:
        return False


def _topic_hint_text(conn: sqlite3.Connection, question: str) -> str:
    """คำใบ้เมื่อถามหาวิชาตามหัวข้อ ("วิชาเกี่ยวกับ X"): ค้นด้วย LIKE ในชื่อวิชาไทย+อังกฤษ (และแคตตาล็อกวิชาเลือกถ้ามี)
    ตัวอย่างใช้ตัวแทน <คำค้น> ไม่ใช่หัวข้อจริง — เปิดเฉพาะคำถามรูปแบบนี้ นอกนั้นคืน "" """
    if not _TOPIC_Q.search(question):
        return ""
    text = (
        "ค้นวิชาตามหัวข้อ: ใช้ LIKE '%<คำค้น>%' กับทั้ง name_th และ name_en (ใส่คำค้นทั้งภาษาไทยและอังกฤษที่ความหมายเดียวกัน) "
        "อย่าใช้ = และอย่าเดาจากรหัสวิชา\n"
        "  SELECT DISTINCT code, name_th, credits FROM course WHERE name_th LIKE '%<คำค้นไทย>%' OR name_en LIKE '%<คำค้นอังกฤษ>%'\n"
    )
    if _has_view(conn, "v_elective_group"):
        text += (
            "  ถ้าถามถึงวิชาเลือกด้วย ให้ UNION กับ v_elective_group:\n"
            "  SELECT code, course_name_th, credits FROM v_elective_group "
            "WHERE course_name_th LIKE '%<คำค้นไทย>%' OR course_name_en LIKE '%<คำค้นอังกฤษ>%'\n"
        )
    return text + "\n"


def _course_name_hint_text(conn: sqlite3.Connection, question: str) -> str:
    """บรรทัด "ชื่อวิชา = รหัส" + ทิศทางวิชาบังคับก่อน สำหรับ prompt (course_names.py) — ไม่มีตาราง/ไม่เจออะไร = "" """
    _citations_module()                          # ให้โฟลเดอร์นี้อยู่ใน sys.path (ครั้งเดียว)
    import course_names
    try:
        rows = conn.execute("SELECT code, name_th, name_en FROM course").fetchall()
    except sqlite3.OperationalError:
        return ""
    courses = [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in rows]
    hints = course_names.course_hints(question, courses)
    # ทิศทาง code/requires ของวิชาบังคับก่อน (ไม่ชัด = "" — prompt เหมือนเดิม)
    return (course_names.hint_block(hints)
            + course_names.direction_block(course_names.prereq_direction(question, hints)))


def _with_course_names(conn: sqlite3.Connection, answer: str | None, rows: list[dict]) -> str | None:
    """เติมชื่อวิชาหลังรหัสในคำตอบ (course_names.with_course_names) — ไม่มีคำตอบ/ไม่มีตาราง course = คืนเดิม"""
    if not answer:
        return answer
    _citations_module()
    import course_names
    try:
        names = {r[0]: r[1] for r in conn.execute("SELECT code, name_th FROM course") if r[1]}
    except sqlite3.OperationalError:
        return answer
    return course_names.with_course_names(answer, rows, names)


def load_course_pages(conn: sqlite3.Connection, ocr_pages: list[dict],
                      image_names: list[str], md_text: str) -> dict[str, int]:
    """เติมตาราง course_page (ลบของเดิมก่อน รันซ้ำได้): หน้าที่มีรหัสวิชา (primary/other) จาก OCR ทั้งเล่ม
    + หน้าตารางแผนของเทอมที่วิชานั้นอยู่ (plan) จากภาพหน้าของ Lab 7B — ไม่ใช้ LLM/เฉลย
    เลขหน้าที่พิมพ์ผ่าน consistent_printed (ตัดเลขที่ Tesseract อ่านผิด เช่น IT PDF 42 = "27")"""
    citations = _citations_module()
    # สร้างใหม่ทุกครั้ง (ข้อมูลเดิมถูกแทนที่ทั้งหมดอยู่แล้ว) — DB เก่ามี CHECK ของ kind ชุดเดิม
    conn.executescript("DROP TABLE IF EXISTS course_page; DROP TABLE IF EXISTS term_page;" + COURSE_PAGE_DDL)
    courses = [dict(r) for r in conn.execute("SELECT code, name_th, name_en FROM course")]
    printed = citations.consistent_printed(
        {int(p["page"]): citations.printed_page(p.get("text") or "") for p in ocr_pages})
    rows = citations.course_pages(ocr_pages, courses)
    for r in rows:
        r["printed_page"] = printed.get(r["pdf_page"])
    book_text = {int(p["page"]): p.get("text") or "" for p in ocr_pages}
    for t in citations.plan_pages(image_names, md_text, printed, book_text):
        conn.execute("INSERT OR IGNORE INTO term_page VALUES (?, ?, ?, ?)",
                     (t["year"], t["semester"], t["pdf_page"], t["printed_page"]))
        for (code,) in conn.execute("SELECT DISTINCT code FROM plan_item WHERE year = ? AND semester = ?",
                                    (t["year"], t["semester"])).fetchall():
            rows.append({"code": code, "pdf_page": t["pdf_page"], "printed_page": t["printed_page"],
                         "kind": "plan"})
    conn.executemany("INSERT OR IGNORE INTO course_page VALUES (:code, :pdf_page, :printed_page, :kind)", rows)
    conn.commit()
    counts = {"primary": 0, "description": 0, "other": 0, "plan": 0}
    for kind, n in conn.execute("SELECT kind, COUNT(*) FROM course_page GROUP BY kind"):
        counts[kind] = n
    return counts


def cmd_load_course_pages(args) -> None:
    missing = [str(p) for p in (Path(args.ocr_json), Path(args.data_input), Path(args.markdown)) if not p.exists()]
    if missing:
        print(f"  ข้าม load-course-pages (ไม่พบ {', '.join(missing)}) — คำตอบรอบนี้จะไม่มีอ้างอิงหน้า")
        return
    ocr_pages = json.loads(Path(args.ocr_json).read_text(encoding="utf-8"))["pages"]
    image_names = [p.name for p in Path(args.data_input).iterdir() if p.is_file()]
    md_text = Path(args.markdown).read_text(encoding="utf-8")
    conn = open_db(args.database)
    counts = load_course_pages(conn, ocr_pages, image_names, md_text)
    conn.close()
    print(f"  course_page: primary {counts['primary']} · description {counts['description']} · "
          f"other {counts['other']} · plan {counts['plan']}")


def cmd_load_plan_slots_md(args) -> None:
    """สกัดช่อง wildcard / "หรือ" / "เลือก 1 กลุ่ม" จาก Markdown ของ OCR แล้วโหลดเข้า plan_slot

    ข้อมูลมาจากผล OCR อย่างเดียว (md_plan_slots.py — กฎเชิงกำหนด ไม่กรอกมือ ไม่เรียก LLM)
    ไม่แตะ course/plan_item/v_semester_credits/verify เดิม (ดู PLAN_SLOT_DDL)
    หน่วยกิตที่อธิบายไม่ได้เทียบแถว "รวม" ของเล่ม = วิชาที่ OCR ตกจริง ถูกรายงานลงไฟล์ report
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from md_plan_slots import derive_slots, md_codes_by_term

    md = Path(args.markdown).read_text(encoding="utf-8")
    db = Path(args.database)
    if not db.exists():
        raise SystemExit(f"ไม่พบ {db} — ต้อง `load` แผนหลักเข้าไปก่อน")

    conn = open_db(db)
    # ชื่อวิชาต่อเทอมใน DB — ให้ derive_slots หาสมาชิกของกลุ่มวิชาที่ OCR ทำรหัสหาย (ชื่อต้องอยู่ในเซลล์หัวกลุ่ม)
    names_by_term: dict[tuple[int, int], dict[str, str]] = {}
    for y, sm, code, name in conn.execute(
            "SELECT p.year, p.semester, p.code, c.name_th FROM plan_item p JOIN course c ON c.code = p.code"):
        names_by_term.setdefault((y, sm), {})[code] = name
    slots, term_report = derive_slots(md, names_by_term)
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
    base = sum(r[0] for r in conn.execute("SELECT credits FROM main.v_semester_credits"))
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
    report = {"source": repo_relative(args.markdown), "slots": len(slots), "members": n_members,
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
        "FROM main.v_semester_credits ORDER BY year, semester").fetchall()


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
        "detail": f"นับรวมช่อง {total_full} · plan_item อย่างเดียว {total_item} · ประกาศไว้ {declared}",
        # แยกสาเหตุ (ก)/(ข) แบบกำหนดได้ (ใบงาน Lab 8B: verify.json ต้องแยกกรณี "สกัดผิด" กับ "เล่มเขียนแบบนั้นจริง")
        #   (ข) = ส่วนต่างที่มาจากช่องตามเล่มซึ่ง plan_item ไม่นับ (wildcard) หรือนับเกิน (สมาชิกกลุ่ม "เลือก 1") — เป็นข้อจำกัดของ plan_item
        #   (ก) = ส่วนต่างที่ยังเหลือหลังนับช่องแล้ว — บวก = ขาด (OCR/สกัดทำวิชาหาย) · ลบ = เกิน (เช่น หัวกลุ่มหายทำให้นับซ้ำ)
        "cause": {"gap_vs_declared": declared - total_item,
                  "b_book_as_written": total_full - total_item,
                  "a_extraction": declared - total_full}})

    block = {(r["year"], r["semester"]) for r in conn.execute("""
        SELECT DISTINCT year, semester FROM plan_item
        WHERE credits >= 6
           OR note LIKE '%สหกิจ%' OR note LIKE '%ฝึกงาน%'
           OR code IN (SELECT code FROM course
                       WHERE name_th LIKE '%สหกิจ%' OR name_th LIKE '%ฝึกงาน%')""")}
    def _bad_terms(term_rows):
        return [f"ปี {r['year']}/{r['semester']} = {r['credits']} หน่วยกิต" for r in term_rows
                if (r["year"], r["semester"]) not in block and r["semester"] != 3
                and not (MIN_CREDITS_PER_SEM <= r["credits"] <= MAX_CREDITS_PER_SEM)]

    bad = _bad_terms(rows)
    bad_item = _bad_terms(_sem_credits(conn))
    bad_keys = {b.split(" = ")[0] for b in bad}
    results.append({
        "cause": {"b_book_as_written": [b for b in bad_item if b.split(" = ")[0] not in bad_keys],   # ตกตอนนับ plan_item แต่ผ่านเมื่อนับช่อง = เหตุคือช่องตามเล่ม
                  "a_extraction": bad},                                                              # ยังตกหลังนับช่อง = ข้อมูลที่สกัดได้ผิดจริง
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


_SQL_STRING = re.compile(r"'(?:[^']|'')*'")
_SQL_KEYWORDS = {"where", "on", "join", "left", "right", "inner", "outer", "cross", "natural",
                 "group", "order", "limit", "having", "union", "except", "intersect", "using", "as"}
_SQL_SOURCE = re.compile(r"\b(?:from|join)\s+([A-Za-z_]\w*)(?:\s+(?:as\s+)?([A-Za-z_]\w*))?", re.I)
_SQL_SUBQUERY_ALIAS = re.compile(r"\)\s*(?:as\s+)?([A-Za-z_]\w*)", re.I)
_SQL_QUALIFIER = re.compile(r"\b([A-Za-z_]\w*)\.(?=[A-Za-z_\"])")


def repair_undefined_aliases(sql: str) -> str:
    """ตัด "X." ออกเมื่อ X ไม่ใช่ตาราง/view/alias ที่ประกาศใน FROM/JOIN (รวม alias ของ subquery) ของ SQL นี้เลย
    (ชื่อ CTE ถูกนับผ่าน "FROM <ชื่อ CTE>" อยู่แล้ว)

    พบจริง (ทั้ง 7 run): DDL ที่ส่งให้ qwen นิยาม `v_plan AS SELECT p.code ... FROM plan_item p`
    qwen จึงเขียน `SELECT p.code FROM v_plan WHERE p.year = 1` -> "no such column: p.code"
    (รอบ retry ที่ส่ง error กลับไปก็ยังเขียนแบบเดิม) SQL ที่มี alias ที่ไม่ได้ประกาศรันไม่ได้แน่นอน
    ฟังก์ชันนี้จึงแตะเฉพาะ query ที่จะพังอยู่แล้ว — query ที่ถูกต้องไม่เปลี่ยน
    ไม่แตะข้อความในเครื่องหมาย '...' และตัวเลขทศนิยม"""
    code = _SQL_STRING.sub(" ", sql)                   # หาชื่อที่ประกาศจากส่วนที่ไม่ใช่ string
    defined: set[str] = set()
    for table, alias in _SQL_SOURCE.findall(code):
        defined.add(table.lower())
        if alias and alias.lower() not in _SQL_KEYWORDS:
            defined.add(alias.lower())
    defined.update(n.lower() for n in _SQL_SUBQUERY_ALIAS.findall(code)
                   if n.lower() not in _SQL_KEYWORDS)

    def fix(segment: str) -> str:
        return _SQL_QUALIFIER.sub(
            lambda m: m.group(0) if m.group(1).lower() in defined else "", segment)

    out, pos = [], 0
    for m in _SQL_STRING.finditer(sql):                 # แก้เฉพาะช่วงนอก string literal
        out.append(fix(sql[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(fix(sql[pos:]))
    return "".join(out)


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
- ถามว่าภาคเรียนไหนหรือชั้นปีไหนมีกี่หน่วยกิต ให้ใช้ v_semester_credits เสมอ
  (รวมทั้งชั้นปีใช้ SUM(credits) จาก v_semester_credits ตาม year)
  ห้ามใช้ SUM(credits) จาก v_plan เพราะจะนับวิชาเลือกซ้ำ
- ถามว่าเรียนวิชาอะไรบ้าง ให้ใช้ v_plan เพราะมีชื่อวิชาอยู่แล้ว
- คำถามเรื่อง "วิชาบังคับก่อน / ต้องผ่านวิชาใดก่อน / วิชาไหนใช้ X เป็นบังคับก่อน /
  วิชาเรียนควบ" ให้ query ตาราง prerequisite เสมอ (join ผ่านคอลัมน์ code/requires)
  ห้ามใช้ LIKE กับ name_th หรือ name_en เพื่อเดาความสัมพันธ์วิชาบังคับก่อน
- ทิศของตาราง prerequisite: แถว (code, requires) แปลว่า "code ต้องผ่าน requires ก่อน"
  ถามว่า X ต้องผ่านอะไรก่อน -> กรอง code = X แล้วเลือกคอลัมน์ requires
  ถามว่าเรียน X แล้วเรียนอะไรต่อได้ / X ปลดล็อกวิชาอะไร / วิชาไหนต้องใช้ X ก่อน
  -> กรอง requires = X แล้วเลือกคอลัมน์ code
  (ทั้งสองทิศใช้ kind='pre' ยกเว้นถามวิชาเรียนควบ ใช้ kind='co')
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


def use_slot_aware_credit_view(conn: sqlite3.Connection) -> bool:
    """ให้ v_semester_credits ในการเชื่อมต่อนี้ "นับตามเล่ม" (รู้จัก plan_slot) โดยไม่แก้ไฟล์ DB และไม่แก้ prompt

    ราก: v_semester_credits ที่เก็บใน DB รวมทุกแถวของ plan_item จึงนับสมาชิกของช่อง "เลือก 1 กลุ่มวิชา" ครบทุกวิชา
    (IT ปี 2/2 ได้ 30 ทั้งที่เล่มรวม 18) ส่วน v_semester_credits_full (ที่ CHK1F/CHK7F ใช้ตรวจ 7/7 run) ถูกต้อง
    จึงสร้าง TEMP VIEW ชื่อเดิมชี้ไป _full — temp schema ถูกค้นก่อน main และเขียนได้แม้เปิด DB แบบ mode=ro;
    เทอมที่ไม่มี slot ได้ค่าเท่าเดิมทุกประการ; DB ที่ไม่มีตาราง slot ไม่ถูกแตะ (คืน False)
    หมายเหตุ n_courses = จำนวน "รายการในตารางแผนตามเล่ม" — ช่อง "เลือก 1 กลุ่มวิชา" และวิชาเลือก wildcard นับเป็น 1 รายการ
    (ไม่ใช่จำนวนวิชาที่นักศึกษาต้องลงจริงของกลุ่มนั้น); verify_db/CHK เรียก main.v_semester_credits เพื่อไม่ถูกบัง
    """
    try:
        has_full = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'view' AND name = 'v_semester_credits_full'").fetchone()
        if not has_full:
            return False
        conn.execute(
            "CREATE TEMP VIEW IF NOT EXISTS v_semester_credits AS "
            "SELECT year, semester, credits, n_entries AS n_courses FROM main.v_semester_credits_full")
        return True
    except sqlite3.Error:
        return False


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
        "citations": [], "citation_text": "", "slot_aware_credits": False,
    }
    # หน่วยกิตรายเทอมนับตามเล่ม (ดูเหตุผลที่ฟังก์ชัน); False = สร้างไม่ได้ → กลับไปใช้ view เดิมใน DB (เห็นได้จากผลลัพธ์)
    result["slot_aware_credits"] = use_slot_aware_credit_view(conn)
    scope_elective_view(conn, question)                   # v_elective_group ไม่รวม GE เว้นแต่คำถามพูดถึง GE (ดูเหตุผลที่ฟังก์ชัน)
    # ช่องเลือกเองที่เล่มไม่ระบุรายชื่อ (ระบุชื่อช่อง) หรือสรุปช่องเลือกทั้งเทอม — ตอบตามเล่ม/แคตตาล็อก ไม่ต้องเรียกโมเดล
    open_slot = None
    for shortcut in (_open_slot_answer, _term_choices_answer, _ge_category_answer, _extreme_credits_answer, _no_prereq_answer,
                     _hours_filter_answer, _prereq_term_answer, _course_description_answer, _book_section_answer, _catalog_course_answer, _credit_structure_answer):
        try:
            open_slot = shortcut(conn, question)
        except Exception:                                 # ทางลัดพัง (ข้อมูล DB ไม่ครบ ฯลฯ) = ห้ามให้หลุดเป็น HTTP 500 → ใช้ทางเดิม (โมเดล)
            open_slot = None
        if open_slot:
            break
    if open_slot:
        result["answer"], result["rows"], result["sql"] = open_slot
        _attach_citations(conn, result)
        return result
    ddl = DDL.strip()
    # ชื่อวิชาในคำถาม -> รหัส จากตาราง course (course_names.py) — qwen ไม่รู้ว่าชื่อไหนคือรหัสอะไร จึงเคยแต่งรหัสเอง;
    # แทรกไว้หน้าบรรทัดคำถาม และเฉพาะเมื่อเจอชื่อวิชา (ไม่เจอ = prompt เหมือนเดิมทุกตัวอักษร)
    base_prompt = SQL_PROMPT.format(ddl=ddl, question=question)
    hints = (_course_name_hint_text(conn, question) + _elective_hint_text(conn, question)
             + _topic_hint_text(conn, question) + _term_summary_hint_text(question))
    if hints:
        tail = f"คำถาม: {question}\nSQL:"
        base_prompt = base_prompt[: -len(tail)] + hints + tail
    prompt = base_prompt

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
            # alias ที่ไม่ได้ประกาศ (qwen ลอก "p.code" จากนิยาม v_plan ใน DDL) -> ตัดออกก่อนรัน
            sql = guard_sql(repair_undefined_aliases(sql))
            result["sql"] = sql
            rows = _hide_internal_columns(_dedupe_rows([dict(r) for r in conn.execute(sql).fetchall()]))
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
            prompt = (base_prompt
                      + f"\n\nSQL ที่ลองไปแล้วมีข้อผิดพลาด: {e}\nเขียนใหม่ให้ถูก\nSQL:")

    result["sql"], result["rows"] = _term_summary_fallback(conn, question, result["sql"], result["rows"])

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
    # ผลลัพธ์ค่าเดียว (COUNT/MIN/MAX/ชื่อ) ที่ข้อความคำตอบไม่มีค่านั้น — เช่น qwen ลอกเลข 3 จากคำถาม
    # "กี่วิชาที่ 3 หน่วยกิต" ทั้งที่ SQL ได้ 32 → ใช้ค่าจากฐานข้อมูลเป็นคำตอบ (ตัวเลขต้องตรงทั้งตัว: 2 ≠ 12)
    elif len(flat) == len(result["rows"]) == 1 and len(flat[0]) <= 40:
        value = flat[0]
        pattern = rf"(?<!\d){re.escape(value)}(?!\d)" if re.fullmatch(r"-?\d+(\.\d+)?", value) else re.escape(value)
        if not re.search(pattern, result["answer"] or ""):
            result["answer"] = value
    # รายการหลายแถว หลายคอลัมน์ (เช่น วิชาเลือก: กลุ่ม+รหัส+ชื่อ+หน่วยกิต): num_predict=256 ตัดคำตอบกลางสตริงจนได้ข้อความว่าง
    # และ qwen สะกดไทยเพี้ยน → ถ้าคำตอบขาดค่าข้อความของแถวใด (หรือว่าง) ประกอบจากแถวจริงตรง ๆ; คำตอบที่ครบอยู่แล้วไม่แตะ
    elif 2 <= len(result["rows"]) <= 80 and all(len(r) >= 2 for r in result["rows"]):
        rows_ = result["rows"]
        # คอลัมน์ยอดรวมของภาคเรียน (ค่าเดียวกันทุกแถว) รายงานครั้งเดียวท้ายคำตอบ ไม่ซ้ำทุกแถว
        totals = {c: rows_[0][c] for c in TERM_TOTAL_COLS
                  if all(c in r and r[c] == rows_[0][c] for r in rows_) and rows_[0][c] is not None}
        shown = [{k: v for k, v in r.items() if k not in totals} for r in rows_]
        texts = [str(v).strip() for r in shown for v in r.values()
                 if isinstance(v, str) and v.strip() and not v.strip().isdigit()]
        ans = result["answer"] or ""
        has_totals = all(re.search(rf"(?<!\d){re.escape(str(v))}(?!\d)", ans) for v in totals.values())
        if not ans.strip() or not all(t in ans for t in texts) or not has_totals:
            body = "; ".join(" ".join(str(v).strip() for v in r.values() if v is not None) for r in shown)
            parts = []
            if "total_credits" in totals:
                parts.append(f"รวม {totals['total_credits']} หน่วยกิต")
            if "n_courses" in totals:
                parts.append(f"{totals['n_courses']} วิชา")
            result["answer"] = body + (f" ({', '.join(parts)})" if parts else "")
    slot_note = _self_chosen_slot_note(conn, question)
    if slot_note and slot_note not in (result["answer"] or ""):
        result["answer"] = f"{result['answer']}; {slot_note}" if result["answer"] else slot_note
    # รหัสวิชาในคำตอบ -> เติมชื่อจากตาราง course ("06026200" -> "06026200 (แคลคูลัส 1)") เฉพาะรหัสที่มาจากผล SQL
    result["answer"] = _with_course_names(conn, result["answer"], result["rows"])
    _attach_citations(conn, result)
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
    if r["citation_text"]:
        print(f"  อ้างอิง : {r['citation_text']}")
    print(f"  Raw SQL   : {r['sql_model_output']}")
    print(f"  Raw answer: {r['answer_model_output']}")
    if r["error"]:
        print(f"  หมายเหตุ: {r['error']}")


# ───────────────────────────────────────────────────────────────────────
#  รันหลายคำถามจากไฟล์ (ask-batch) — เตรียมวัน Challenge
#  อาจารย์ส่งชุดคำถามมา เราส่งคำตอบกลับเป็นไฟล์ JSON; ข้อไหนพังต้องไม่ทำให้ทั้งชุดหยุด
# ───────────────────────────────────────────────────────────────────────

FALLBACK_ANSWER = "ตอบไม่ได้: ระบบประมวลผลคำถามนี้ไม่สำเร็จ"


def load_questions(path: str | Path) -> list[dict]:
    """อ่านคำถามจาก .json (list ของข้อความ/อ็อบเจ็กต์ หรือ dict ที่มีคีย์ questions), .csv (หัวคอลัมน์ question)
    หรือ .txt (หนึ่งบรรทัดหนึ่งคำถาม; บรรทัดว่างและบรรทัดขึ้นต้นด้วย # ถูกข้าม) → [dict ที่มี id และ question]"""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    suffix = p.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
        items = (data.get("questions") or data.get("items") or []) if isinstance(data, dict) else data
    elif suffix == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        names = [(n or "").strip().lower() for n in (reader.fieldnames or [])]
        if "question" not in names:
            raise ValueError("ไฟล์ CSV ต้องมีคอลัมน์ question")
        items = [{(k or "").strip().lower(): v for k, v in row.items()} for row in reader]
    else:
        items = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    out: list[dict] = []
    for i, item in enumerate(items, 1):
        if isinstance(item, str):
            d: dict = {"question": item}
        elif isinstance(item, dict):
            d = dict(item)
        else:
            raise ValueError(f"ข้อที่ {i} ไม่ใช่ข้อความหรืออ็อบเจ็กต์")
        d["question"] = str(d.get("question") or "").strip()
        if not d["question"]:
            raise ValueError(f"ข้อที่ {i} ไม่มีข้อความคำถาม")
        d["id"] = str(d.get("id") or f"q{i}")
        out.append(d)
    if not out:
        raise ValueError("ไม่พบคำถามในไฟล์")
    return out


def ask_batch(conn, questions: list[dict], ask_fn=None, clock=time.perf_counter,
              with_rows: bool = False, on_result=None) -> list[dict]:
    """ถามทีละข้อตามลำดับ — ข้อที่ exception (เช่น Ollama ล่ม) บันทึกเป็นคำตอบสำรองแล้วไปต่อ ไม่หยุดทั้งชุด
    และไม่ปล่อยให้คำตอบว่าง (คำตอบว่างทำให้ judge ให้ 0)"""
    ask_fn = ask_fn or ask
    results: list[dict] = []
    for i, q in enumerate(questions, 1):
        t0 = clock()
        try:
            r = ask_fn(conn, q["question"], verbose=False)
            error = r.get("error")
        except Exception as e:                                  # noqa: BLE001 — ตั้งใจจับทุกชนิด
            r, error = {}, f"{type(e).__name__}: {e}"
        seconds = round(clock() - t0, 2)
        item = {
            "id": q["id"], "question": q["question"],
            "answer": str(r.get("answer") or "").strip() or FALLBACK_ANSWER,
            "citation_text": r.get("citation_text") or "", "citations": r.get("citations") or [],
            "sql": r.get("sql"), "n_rows": len(r.get("rows") or []),
            "seconds": seconds, "error": error,
        }
        for key in ("level", "category"):
            if key in q:
                item[key] = q[key]
        if with_rows:
            item["rows"] = r.get("rows") or []
        results.append(item)
        if on_result:
            on_result(i, len(questions), item)
    return results


def summarize_batch(results: list[dict]) -> dict:
    secs = [r["seconds"] for r in results]
    n = len(results)
    ok = sum(1 for r in results if not r["error"])
    return {"n": n, "ok": ok, "failed": n - ok, "over_5s": sum(1 for s in secs if s > 5),
            "avg_seconds": round(sum(secs) / n, 2) if n else 0, "max_seconds": max(secs) if secs else 0}


def cmd_ask_batch(args) -> None:
    questions = load_questions(args.questions)
    conn = open_db(args.database, readonly=True)
    warmed = None if args.no_warmup else warm_up()
    if warmed is False:
        print("  คำเตือน: โหลดโมเดลล่วงหน้าไม่สำเร็จ (Ollama ยังไม่เปิดหรือไม่มีโมเดล) — ข้อแรกอาจช้าหรือล้ม")

    def show(i: int, n: int, r: dict) -> None:
        mark = "ok " if not r["error"] else "ERR"
        print(f"  [{i}/{n}] {mark} {r['seconds']:>5.1f}s  {r['question'][:60]}")

    started = time.perf_counter()
    results = ask_batch(conn, questions, with_rows=args.with_rows, on_result=show)
    conn.close()
    summary = summarize_batch(results)
    payload = {"meta": {"database": str(args.database), "program": args.program or None, "model": MODEL_TEXT,
                        "warmed_up": warmed, "created": datetime.now().isoformat(timespec="seconds"),
                        "total_seconds": round(time.perf_counter() - started, 1), **summary},
               "results": results}
    out = Path(args.output) if args.output else Path(args.questions).with_name(Path(args.questions).stem + "_answers.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  ตอบได้ {summary['ok']}/{summary['n']} ข้อ · เกิน 5 วินาที {summary['over_5s']} ข้อ · "
          f"เฉลี่ย {summary['avg_seconds']} วินาที")
    print(f"  เขียนคำตอบไว้ที่ {out}")


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


_SCORE_CODE_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")


def score_one(expect: dict, got: dict, question: str = "") -> tuple[bool, str]:
    """
    ให้คะแนนหนึ่งข้อ ตามชนิดของคำถาม

    value     — ต้องมีค่านี้อยู่ในผลลัพธ์
    set       — ชุดคำตอบต้องตรงกันทั้งหมด (ใช้กับคำถาม "มีวิชาอะไรบ้าง")
    set_exact — ชุดรหัสวิชา 8 หลักในผลลัพธ์ต้องเท่ากับที่คาดพอดี (ไม่ขาด ไม่เกิน) — ไม่นับรหัสที่อยู่ในคำถาม
                และรหัสใน expect["ignore"] (วิชาที่ถูกถามเอง ซึ่ง SQL มักคืนมาคู่กับคำตอบ)
    count     — จำนวนแถวต้องเท่ากับที่คาด
    none      — ต้องตอบว่าไม่พบ (ใช้ทดสอบว่าระบบยอมรับได้ว่าไม่รู้)
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

    if kind == "set_exact":
        want = {str(x).strip() for x in expect["value"]}
        skip = set(_SCORE_CODE_RE.findall(question)) | {str(x) for x in expect.get("ignore") or []}
        have = {c for v in vals for c in _SCORE_CODE_RE.findall(v)} - skip
        ok = bool(want) and have == want
        if ok:
            return True, "ครบพอดี"
        return False, f"ขาด {', '.join(sorted(want - have)[:5]) or '-'} เกิน {', '.join(sorted(have - want)[:5]) or '-'}"

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
        ok, why = score_one(q["expect"], got, question=q["question"])
        sql_ok = got["error"] is None
        n_ok += ok
        n_sql_ok += sql_ok
        rows_out.append({**q, "sql": got["sql"], "n_rows": len(got["rows"]),
                         "error": got["error"],
                         "sql_model_output": got["sql_model_output"],
                         "answer_model_output": got["answer_model_output"],
                         "answer": got["answer"], "citations": got["citations"],
                         "citation_text": got["citation_text"], "correct": ok, "why": why,
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

    p = sub.add_parser("load-course-pages",
                       help="หน้าในเล่มที่มีรหัสวิชา (OCR ทั้งเล่ม) + หน้าตารางแผนของแต่ละเทอม (ภาพหน้า Lab 7B)"
                            " เข้าตาราง course_page สำหรับอ้างอิงหน้าในคำตอบ")
    p.add_argument("-d", "--database", required=True)
    p.add_argument("--ocr-json", required=True, help="outputs/<หลักสูตร>/<หลักสูตร>_curriculum_ocr.json")
    p.add_argument("--data-input", required=True, help="runs/<PROG>/<plan>/data_input")
    p.add_argument("-m", "--markdown", required=True, help="intermediate_vlm.md จาก Lab 7B")

    p = sub.add_parser("load-prerequisites",
                       help="สกัดวิชาบังคับก่อนจากข้อความ OCR ทั้งเล่ม (ภาคผนวกคำอธิบายรายวิชา) เข้าตาราง prerequisite"
                            " (กฎเชิงกำหนด ไม่เดา: หาไม่เจอ = ไม่เติมแถว)")
    p.add_argument("-t", "--text", required=True, help="outputs/<หลักสูตร>/<หลักสูตร>_curriculum_ocr.txt (OCR ทั้งเล่มจาก Lab 4-6)")
    p.add_argument("-d", "--database", required=True)
    p.add_argument("-o", "--output", help="เขียนรายงานรายวิชา (found/none/not_found/unreadable) เป็น JSON")

    p = sub.add_parser("load-credit-structure",
                       help="สกัดโครงสร้างหน่วยกิตต่อหมวด (ก./ข./ค. → กลุ่มย่อย) จากข้อความ OCR ทั้งเล่ม เข้าตาราง credit_structure"
                            " (ตรวจเลขคณิต: ผลรวมหมวดระดับบน = หน่วยกิตรวม ไม่ตรง = ไม่โหลด)")
    p.add_argument("-t", "--text", required=True, help="outputs/<หลักสูตร>/<หลักสูตร>_curriculum_ocr.txt")
    p.add_argument("-d", "--database", required=True)

    p = sub.add_parser("load-course-descriptions",
                       help="สกัดคำอธิบายรายวิชา (ไทย/อังกฤษ) จากภาคผนวกในข้อความ OCR ทั้งเล่ม เข้าตาราง course_description")
    p.add_argument("-t", "--text", required=True, help="outputs/<หลักสูตร>/<หลักสูตร>_curriculum_ocr.txt")
    p.add_argument("-d", "--database", required=True)

    p = sub.add_parser("load-book-sections",
                       help="สกัดหัวข้อมาตรฐาน มคอ.2 (ชื่อหลักสูตร/ปริญญา/อาชีพ/ปรัชญา/วัตถุประสงค์/คุณสมบัติ/เกณฑ์จบ) จากข้อความ OCR ทั้งเล่ม เข้าตาราง book_section")
    p.add_argument("-t", "--text", required=True, help="outputs/<หลักสูตร>/<หลักสูตร>_curriculum_ocr.txt")
    p.add_argument("-d", "--database", required=True)

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

    p = sub.add_parser("ask-batch", help="ถามหลายคำถามจากไฟล์ (json/csv/txt) แล้วเขียนคำตอบเป็นไฟล์ JSON")
    p.add_argument("-d", "--database", required=True)
    p.add_argument("-q", "--questions", required=True)
    p.add_argument("-o", "--output", default="", help="ไม่ระบุ = <ชื่อไฟล์คำถาม>_answers.json ข้าง ๆ ไฟล์คำถาม")
    p.add_argument("--program", default="", help="ชื่อหลักสูตร (บันทึกใน meta)")
    p.add_argument("--with-rows", action="store_true", help="แนบแถวผลลัพธ์จากฐานข้อมูลด้วย")
    p.add_argument("--no-warmup", action="store_true", help="ไม่โหลดโมเดลล่วงหน้า")

    args = ap.parse_args()
    if args.cmd == "check":
        sys.exit(0 if check_environment() else 1)
    if args.cmd == "selftest":
        sys.exit(0 if cmd_selftest(args) else 1)
    {"demo": cmd_demo, "schema": cmd_schema, "extract": cmd_extract,
     "import-lab7b": cmd_import_lab7b,
     "load": cmd_load, "load-electives": cmd_load_electives,
     "load-plan-slots-md": cmd_load_plan_slots_md,
     "load-course-pages": cmd_load_course_pages,
     "load-prerequisites": cmd_load_prerequisites,
     "load-credit-structure": cmd_load_credit_structure,
     "load-course-descriptions": cmd_load_course_descriptions,
     "load-book-sections": cmd_load_book_sections,
     "verify": cmd_verify, "ask": cmd_ask,
     "ask-batch": cmd_ask_batch, "eval": cmd_eval}[args.cmd](args)


if __name__ == "__main__":
    main()
