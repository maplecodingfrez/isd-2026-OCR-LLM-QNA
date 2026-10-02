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
                and re.search(r"หน่วยกิต|หนัก|เบา|เรียน", question) and not _CODE8.search(question)
                and not re.search(r"วิชา(?:ไหน|อะไร|ใด)", question))          # "วิชาไหน…มากที่สุด" ถามวิชา ไม่ใช่เทอม/ปี


def _extreme_credits_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ปี/เทอมที่หน่วยกิตมาก/น้อยที่สุด จาก v_semester_credits_full (นับตามเล่ม — ช่อง "เลือก 1 กลุ่ม" ไม่นับซ้ำ); เท่ากันบอกครบทุกเทอม"""
    if not _is_extreme_credits_question(question):
        return None
    y, _s = _term_numbers(question)
    per_year = bool(re.search(r"ปีไหน|ปีใด|ชั้นปีไหน", question)) and not re.search(r"เทอมไหน|ภาคไหน|ภาคการศึกษาไหน|ภาคเรียนไหน|เทอมใด", question)
    want_max = bool(_EXTREME_MAX.search(question))
    first_n = re.search(r"(?:ใน|ช่วง)?\s*(\d|สอง|สาม|สี่)\s*ปีแรก", question)             # "ในสองปีแรก" = ปี 1..N (เดิมถูกเมิน → ตอบค่าสุดของทั้งหลักสูตร)
    where = f" WHERE year = {y}" if y else (f" WHERE year <= {({'สอง': 2, 'สาม': 3, 'สี่': 4}.get(first_n.group(1)) or int(first_n.group(1)))}" if first_n else "")
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
    if not _CATALOG_ATTR_RE.search(question) or _RELATIONAL_NOT.search(question):
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
        qkey = _name_key(question)
        match = max((r for r in by_code.values() if len(r["name_th"] or "") >= 6 and r["name_th"] in question
                     and _name_is_whole(qkey, _name_key(r["name_th"]))),            # ชื่อเต็มเท่านั้น ("…ขั้นสูง" ที่ไม่มีใน DB ไม่ตกไปเป็นชื่อสั้นข้างใน)
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
            if codes and re.search(r"ตั้งแต่ต้น|ทั้งสาย|ย้อนไป|ทุกวิชาที่ต้อง|ตลอดสาย|ลูกโซ่|ทั้งหมดที่ต้อง", question):      # ลูกโซ่ทุกชั้น (เดิมตอบแค่ชั้นเดียวแล้วดูเหมือนครบ)
                seen, frontier = list(codes), list(codes)
                while frontier:
                    frontier = list(dict.fromkeys(r for c in frontier for r in requires_of(c) if r not in seen and r != x))
                    seen += frontier
                return (f"{names.get(x, x)} ต้องเรียนมาก่อนตั้งแต่ต้น (ทุกชั้น): " + ", ".join(label(c) for c in seen),
                        [{"code": c, "name_th": names.get(c), "year": (terms.get(c) or (None, None))[0],
                          "semester": (terms.get(c) or (None, None))[1]} for c in seen], sql)
            own = f" ({_TERM_LABEL.format(y=terms[x][0], s=terms[x][1])})" if x in terms and re.search(r"ปีไหน|เทอมไหน|ภาคไหน|ปีอะไร|เทอมอะไร", question) else ""
            text = (f"{names.get(x, x)}{own} ต้องเรียนมาก่อน: " + ", ".join(label(c) for c in codes)) if codes \
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
    loose_ok = not strict and _is_credit_structure_question(question, loose=True)
    # ผู้ถามเรียกชื่อกลุ่มสั้น ๆ ไม่มีคำว่า กลุ่ม/หมวด ("วิชาเลือกปัญญาประดิษฐ์เฉพาะทางต้องเรียนกี่หน่วยกิต") — ต้องมีชื่อกลุ่มในตารางจริง (ยืนยันข้างล่าง)
    named_ok = (not strict and not loose_ok and bool(_STRUCT_CREDIT_ASK.search(question)) and not _CODE8.search(question)
                and not any(_term_numbers(question)) and not _named_courses(conn, question, strict=False))
    if not strict and not loose_ok and not named_ok:
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
    hits = [(len(core(n)), n) for n in nodes if len(core(n)) >= (3 if strict else (8 if named_ok else 6)) and core(n) in q]   # คำว่า "กลุ่ม" เฉย ๆ ต้องมีชื่อกลุ่มยาว ≥ 6
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
    citations = _citations_module()
    marks = list(_STRUCT_PAGE_RE.finditer(text))
    pages = {int(mk.group(1)): text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)] for i, mk in enumerate(marks)}
    printed = citations.consistent_printed({pg: citations.printed_page(body) for pg, body in pages.items()})
    data = [(r["code"], r["name_th"], r["description_th"], r["description_en"], r["pdf_page"], printed.get(r["pdf_page"])) for r in rows]
    try:                                                   # ทุกอย่างพร้อมแล้ว: สลับตารางใน transaction เดียว — พังกลางทาง = ตารางเดิมยังอยู่
        conn.execute("SAVEPOINT table_swap")
        conn.execute("DROP TABLE IF EXISTS course_description")
        conn.execute(COURSE_DESCRIPTION_DDL.replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE", 1).strip())
        conn.executemany("INSERT OR REPLACE INTO course_description VALUES (?,?,?,?,?,?)", data)
        conn.execute("RELEASE table_swap")
        conn.commit()
    except Exception:
        conn.execute("ROLLBACK TO table_swap")
        conn.execute("RELEASE table_swap")
        raise
    return {"loaded": len(rows)}


_HOURS_LINE = re.compile(r"^(\d{8})\)?[ \t]*\|?[ \t]*\S.*?[ \t](\d{1,2})[ \t]*\((\d{1,2})-(\d{1,2})-(\d{1,3})\)[ \t]*$", re.M)


def reconcile_course_hours(conn: sqlite3.Connection, text: str) -> dict[str, Any]:
    """ชั่วโมง บรรยาย-ปฏิบัติ-ศึกษาเอง ของแต่ละวิชามาจาก VLM อ่านภาพตารางแผน (อ่านผิดได้: IT/no_coop 06016425 อ่าน 3-0-6 ทั้งที่เล่มพิมพ์ 3(2-2-5))
    แต่เล่มพิมพ์ "รหัส ชื่อ n(a-b-c)" ซ้ำหลายที่ในข้อความ OCR → ถ้าเล่มตรงกันเอง (≥2 ที่ และชนะเสียงอื่นขาด) และหน่วยกิต n ตรงกับ DB
    จึงแก้ชั่วโมงใน DB ตามเล่ม; ไม่ครบเงื่อนไข = ไม่แตะ. คืน {"checked": จำนวนวิชาที่เทียบ, "fixed": [(รหัส, ค่าเดิม, ค่าใหม่)]}"""
    votes: dict[str, dict[tuple[int, int, int, int], int]] = {}
    for mt in _HOURS_LINE.finditer(text):
        key = tuple(int(g) for g in mt.groups()[1:])
        bucket = votes.setdefault(mt.group(1), {})
        bucket[key] = bucket.get(key, 0) + 1
    fixed, checked = [], 0
    for code, credits, lec, lab, own in conn.execute("SELECT code, credits, lecture_h, lab_h, self_h FROM course").fetchall():
        ranked = sorted(votes.get(code, {}).items(), key=lambda kv: -kv[1])
        if not ranked or ranked[0][1] < 2 or (len(ranked) > 1 and ranked[1][1] == ranked[0][1]):
            continue
        (n, a, b, c), _ = ranked[0]
        if n != credits:
            continue
        checked += 1
        if (lec, lab, own) != (a, b, c):
            conn.execute("UPDATE course SET lecture_h = ?, lab_h = ?, self_h = ? WHERE code = ?", (a, b, c, code))
            fixed.append((code, (lec, lab, own), (a, b, c)))
    conn.commit()
    return {"checked": checked, "fixed": fixed}


def cmd_load_course_descriptions(args) -> None:
    db = Path(args.database)
    if not db.exists():
        raise SystemExit(f"ไม่พบ {db} — ต้อง `load` แผนหลักเข้าไปก่อน")
    conn = open_db(db)
    text = Path(args.text).read_text(encoding="utf-8").replace("\r", "")
    stats = load_course_descriptions(conn, text)
    hours = reconcile_course_hours(conn, text)               # ข้อความชุดเดียวกัน: เทียบชั่วโมงในตารางแผนกับ n(a-b-c) ที่เล่มพิมพ์
    conn.close()
    print(f"  course_description: โหลดคำอธิบาย {stats['loaded']} วิชา (ยกข้อความจากภาคผนวกของเล่ม)")
    print(f"  ชั่วโมงต่อสัปดาห์: เทียบกับเล่ม {hours['checked']} วิชา แก้ตามเล่ม {len(hours['fixed'])} วิชา"
          + "".join(f" [{c}: {o}→{n}]" for c, o, n in hours["fixed"]))


_DESC_ASK = re.compile(r"เกี่ยวกับ(?:เรื่อง)?อะไร|สอน(?:เรื่อง|เกี่ยวกับ)?อะไร|(?<!ต้อง)เรียน(?:เรื่อง|เกี่ยวกับ)?อะไร|มีเนื้อหาอะไร|คำอธิบายรายวิชา|คําอธิบายรายวิชา|เนื้อหา(?:ของ)?วิชา|เนื้อหารายวิชา|รายละเอียดวิชา|description", re.I)
_DESC_MAX_TH, _DESC_MAX_EN = 1100, 420
_DESC_NOT = re.compile(r"ก่อน|ต้อง(?:เรียน|ผ่าน)|ต่อจาก|เรียนต่อ|หลังจาก")                 # คำถามวิชาบังคับก่อน/วิชาตัวต่อ ไม่ใช่ถามเนื้อหา


def _course_description_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ถามคำอธิบาย/เนื้อหาของวิชา (ระบุรหัส 8 หลัก หรือชื่อวิชา) → ยกข้อความไทย (+อังกฤษ) จากภาคผนวกของเล่มพร้อมเลขหน้า;
    วิชารู้จักแต่เล่มไม่มีคำอธิบาย = บอกตรง ๆ (ไม่ให้โมเดลเดา); ไม่ได้อ้างวิชา/DB ไม่มีตาราง = None (ทางเดิม)"""
    if not _DESC_ASK.search(question) or _DESC_NOT.search(question) or _RELATIONAL_NOT.search(question):
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
        named = _named_courses(conn, question)             # ชื่อไทยหรืออังกฤษ ต้องเป็นชื่อเต็ม; สองวิชา/ชื่อกำกวม = None (ไม่ตอบแค่วิชาเดียว)
        if not named or len(named) > 2:
            return None
        codes = list(named)
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
    # ใช้อ้างหน้าของ "ข้อมูลระดับหลักสูตร" (หน่วยกิตรวม/ระยะเวลา) — ไม่มีคำถามเชิงบรรยายผูกกับสองหัวข้อนี้
    ("หน่วยกิตตลอดหลักสูตร", r"^จานวนหนวยกต(?:ท)?เรยนตลอดหลกสตร$", None),
    ("ระยะเวลาการศึกษา", r"^ระยะเวลา?การศกษาของหลกสตร$", r"^รปแบบของหลกสตร$"),
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
    citations = _citations_module()
    marks = list(_STRUCT_PAGE_RE.finditer(text))
    pages = {int(mk.group(1)): text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)] for i, mk in enumerate(marks)}
    printed = citations.consistent_printed({pg: citations.printed_page(body) for pg, body in pages.items()})
    data = [(r["topic"], r["heading"], r["body"], r["pdf_page"], printed.get(r["pdf_page"])) for r in rows]
    try:                                                   # ทุกอย่างพร้อมแล้ว: สลับตารางใน transaction เดียว — พังกลางทาง = ตารางเดิมยังอยู่
        conn.execute("SAVEPOINT table_swap")
        conn.execute("DROP TABLE IF EXISTS book_section")
        conn.execute(BOOK_SECTION_DDL.replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE", 1).strip())
        conn.executemany("INSERT OR REPLACE INTO book_section VALUES (?,?,?,?,?)", data)
        conn.execute("RELEASE table_swap")
        conn.commit()
    except Exception:
        conn.execute("ROLLBACK TO table_swap")
        conn.execute("RELEASE table_swap")
        raise
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
    ("ชื่อปริญญา", r"ชื่อ(?:ย่อ)?ปริญญา|ได้(?:รับ)?ปริญญา|ปริญญาอะไร|ปริญญา(?:ที่)?ได้(?:รับ)?|ได้(?:รับ)?วุฒิ|วุฒิอะไร"),
    ("อาชีพ", r"(?<!มือ)อาชีพ|ทำงานอะไรได้|จบ.{0,12}ทำงาน|ทำงาน(?:ตำแหน่ง|เป็นอะไร|สายไหน|ด้านไหน|อะไร).{0,6}ได้"),
    ("สถานที่จัดการเรียนการสอน", r"สถานที่จัดการเรียน(?:การ)?สอน"),
    ("ปรัชญา", r"ปรัชญา"),
    ("วัตถุประสงค์", r"วัตถุประสงค์(?:ของ)?หลักสูตร|หลักสูตร(?:นี้)?(?:มี)?วัตถุประสงค์"),
    ("คุณสมบัติผู้เข้าศึกษา", r"คุณสมบัติ(?:ของ)?(?:ผู้)?(?:ที่)?(?:จะ)?(?:สมัคร|เข้า|ศึกษา|เรียน)|ใคร(?:บ้าง)?(?:สามารถ)?(?:สมัคร|เข้า)เรียน|ใคร(?:บ้าง)?(?:สามารถ)?เรียน.{0,14}ได้"
                              r"|เกณฑ์(?:การ)?รับ(?:เข้า)?|สมัคร(?:เรียน)?ต้อง(?:มี|จบ)|ต้องจบ(?:อะไร|สาย).{0,6}มา"),
    ("เกณฑ์สำเร็จการศึกษา", r"(?:เกณฑ์|เงื่อนไข)(?:ในการ|การ|ใน)?(?:สำเร็จการศึกษา|จบการศึกษา|จบ)|สำเร็จการศึกษา.{0,12}(?:เกณฑ์|เงื่อนไข)|จบการศึกษา.{0,12}(?:เกณฑ์|เงื่อนไข)"),
)


_SECTION_NOT = re.compile(r"(?<!สาขา)วิชา|หน่วยกิต|รหัส|ปี\s*\d|ชั้นปี|เทอม|ภาคการศึกษา|ภาคเรียน|ชั่วโมง|สหกิจ|ฝึกงาน|พาร์ทไทม์|ฝึกประสบการณ์")


def _clean_book_body(body: str) -> str:
    """ตัดขยะ OCR ท้ายข้อความหัวข้อที่แสดงให้ผู้ใช้: ถ้ามีเส้นประยาว (----) ตัดตั้งแต่ตรงนั้นแล้วถอยไปจบที่ ")" ล่าสุด
    (IT: "…(ภาคผนวก ก ) เนดทหคุพ ๒6 ------- ------ง6งธง…" → "…(ภาคผนวก ก )"); ไม่มีเส้นประ = ไม่แตะ"""
    mt = re.search(r"-{4,}", body or "")
    if not mt:
        return body
    head = body[:mt.start()].rstrip()
    cut = head.rfind(")")
    return (head[:cut + 1] if cut >= 0 else head).strip()


# ---- ระดับ 3 ของอาจารย์ (สไลด์ ch1 หน้า 7): "ตรวจว่าแผนเรียนนี้ครบเงื่อนไขจบหรือไม่" — หน่วยกิตรวมตามแผน (นับช่องตามเล่ม) เทียบที่หลักสูตรกำหนด + เกณฑ์ตามข้อบังคับ ----
_PLAN_CHECK_Q = re.compile(r"แผน(?:การ)?(?:เรียน|ศึกษา).{0,40}(?:ครบ|ตรง|พอ|เพียงพอ).{0,24}(?:เงื่อนไข|หน่วยกิต|จบ|เกณฑ์)|"
                           r"(?:ตรวจ|เช็ก|เช็ค|ตรวจสอบ).{0,10}แผน(?:การ)?(?:เรียน|ศึกษา)|เรียนตามแผน(?:การ)?(?:เรียน|ศึกษา)?.{0,12}จบได้(?:ไหม|หรือไม่|มั้ย)|"
                           r"ตามแผน.{0,60}?(?:ตรงกับ|ครบ).{0,20}?(?:หลักสูตรกำหนด|เงื่อนไข|ที่กำหนด)|"
                           r"แผน.{0,30}?หน่วยกิตรวม.{0,12}?(?:ถึง|พอ|ครบ|ตรง).{0,24}?(?:เกณฑ์|เงื่อนไข|จบ|หลักสูตรกำหนด)")


def _plan_check_text(plan_total: int, declared: int, criteria: str) -> str:
    if plan_total == declared:
        head = f"แผนการเรียนตามเล่มรวม {plan_total} หน่วยกิต ตรงกับที่หลักสูตรกำหนด {declared} หน่วยกิต → ครบด้านหน่วยกิต"
    else:
        diff = declared - plan_total
        head = f"แผนการเรียนตามเล่มรวม {plan_total} หน่วยกิต ไม่ตรงกับที่หลักสูตรกำหนด {declared} หน่วยกิต ({'ขาด' if diff > 0 else 'เกิน'} {abs(diff)} หน่วยกิต)"
    return f"{head}; เกณฑ์การสำเร็จการศึกษา: {criteria} (ระบบตรวจเฉพาะหน่วยกิตรวมตามแผน; เงื่อนไขอื่น เช่น เกรดเฉลี่ย ต้องตรวจตามข้อบังคับ)"


def _plan_check_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """"ตรวจว่าแผนเรียนนี้ครบเงื่อนไขจบหรือไม่" (ทั้งแผน ไม่ระบุปี/เทอม/วิชา/หลักสูตรอื่น) → หน่วยกิตรวมตามแผนเทียบที่หลักสูตรกำหนด + ข้อความเกณฑ์จบจากเล่ม
    หน่วยกิตรวมนับด้วย v_semester_credits_full (ช่องเลือกตามเล่ม); ไม่มีข้อมูลครบ/ระบุปี-เทอม-วิชา-รหัส-หลักสูตรอื่น = None"""
    if not _PLAN_CHECK_Q.search(question) or _CODE8.search(question) or _PROGRAM_TOKEN.search(question):
        return None
    if re.search(r"ปี\s*\d|เทอม|ภาค(?:การศึกษา)?\s*\d|วิชา", re.sub(r"ทุก(?:เทอม|ภาค(?:การศึกษา)?|ปี)", "", question)) or _named_courses(conn, question, strict=False):
        return None
    try:
        plan_total = conn.execute("SELECT SUM(credits) FROM main.v_semester_credits_full").fetchone()[0]
        declared = conn.execute("SELECT total_credits FROM program LIMIT 1").fetchone()
        secs = {r["topic"]: dict(r) for r in conn.execute(
            "SELECT topic, body, pdf_page, printed_page FROM book_section WHERE topic IN ('หน่วยกิตตลอดหลักสูตร', 'เกณฑ์สำเร็จการศึกษา')")}
    except sqlite3.OperationalError:
        return None
    if plan_total is None or not declared or declared[0] is None or "เกณฑ์สำเร็จการศึกษา" not in secs:
        return None
    criteria = _clean_book_body(secs["เกณฑ์สำเร็จการศึกษา"]["body"])
    rows = [{"topic": "เกณฑ์สำเร็จการศึกษา", "body": criteria, "pdf_page": secs["เกณฑ์สำเร็จการศึกษา"]["pdf_page"],
             "printed_page": secs["เกณฑ์สำเร็จการศึกษา"]["printed_page"]}]
    if "หน่วยกิตตลอดหลักสูตร" in secs:
        s = secs["หน่วยกิตตลอดหลักสูตร"]
        rows.insert(0, {"topic": "หน่วยกิตตลอดหลักสูตร", "plan_total": int(plan_total), "declared": declared[0],
                        "pdf_page": s["pdf_page"], "printed_page": s["printed_page"]})
    return (_plan_check_text(int(plan_total), int(declared[0]), criteria), rows,
            "SELECT (SELECT SUM(credits) FROM main.v_semester_credits_full) AS plan_total, (SELECT total_credits FROM program) AS declared")


# ---- "X มีวิชาบังคับก่อนไหม/หรือเปล่า" (วิชาเดียว) ----
_HAS_PREREQ_YN = re.compile(r"(?<!ไม่)มี\s*(?:วิชา)?(?:บังคับก่อน|prerequisite)(?:อะไร)?\s*(?:ไหม|หรือไม่|หรือเปล่า|มั้ย|รึเปล่า)|ต้องมีวิชาบังคับก่อน(?:ไหม|หรือไม่|หรือเปล่า|มั้ย)")
_HAS_PREREQ_TAIL = re.compile(r"มีวิชาบังคับก่อน|prerequisite|มี|วิชา|บังคับก่อน|อะไร|ไหม|หรือไม่|หรือเปล่า|รึเปล่า|มั้ย|หรือ|เปล่า|ต้อง|ครับ|ค่ะ|คะ|นะ|ของ|การ")


def _remove_hinted_name(question: str, raw: str) -> str:
    """ตัดชื่อวิชาที่ hint จับได้ออกจากคำถามเพื่อดู "ส่วนที่เหลือ": ชื่อไทย = ตัดข้อความตรง ๆ; ชื่ออังกฤษ (ผู้ถามอาจพิมพ์ย่อ/ตัดท้าย) = ตัดคำอังกฤษทั้งหมด"""
    if raw.isascii():
        return re.sub(r"[A-Za-z0-9][-A-Za-z0-9&']*", " ", question)
    return re.sub(re.escape(raw), "", question, flags=re.I)


def _has_prereq_yesno_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """"วิชา X มีวิชาบังคับก่อนหรือเปล่า" → มี (ลิสต์) / ไม่มี (ยืนยันจากเล่ม); วิชาเดียวเท่านั้น; มีทางเลือก "หรือ"/ไม่ทราบสถานะ/ส่วนอื่นค้าง = None"""
    if not _HAS_PREREQ_YN.search(question) or _CODE8.search(question):
        return None
    _citations_module()
    import course_names
    try:
        courses = [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in conn.execute("SELECT code, name_th, name_en FROM course")]
        req, alt = _requires_map(conn)
    except sqlite3.OperationalError:
        return None
    hints = course_names.course_hints(question, courses)
    if len({c for _, c in hints}) != 1 or len({_name_key(r) for r, _ in hints}) != 1:
        return None
    raw, code = hints[0]
    if _strip_punct(_HAS_PREREQ_TAIL.sub("", _remove_hinted_name(question, raw))):
        return None
    names = {c["code"]: c["name_th"] for c in courses}
    name = f"{names.get(code, code)} ({code})"
    sql = f"SELECT requires FROM prerequisite WHERE code = '{code}' AND kind = 'pre'"
    if code in alt:
        return None
    if req.get(code):
        listed = ", ".join(f"{r} {names.get(r, '')}".strip() for r in sorted(req[code]))
        return f"{name} มีวิชาบังคับก่อน: {listed}", [{"code": r, "name_th": names.get(r)} for r in sorted(req[code])], sql
    if (_prereq_statuses(conn) or {}).get(code) == "none":
        return f"{name} ไม่มีวิชาบังคับก่อน", [{"code": code, "name_th": names.get(code), "requires": None}], sql
    return None


# ---- "A กับ B วิชาไหนเรียนก่อน" — เทียบเทอมแรกที่พบในแผน (+ บอกถ้าเป็นวิชาบังคับก่อนของกัน) ----
_WHICH_FIRST_Q = re.compile(r"อันไหน(?:ต้อง)?เรียนก่อน|ต้องเรียนก่อนกัน|วิชาไหนเรียนก่อน|วิชาไหนก่อน|อันไหนเรียนก่อน|ตัวไหนเรียนก่อน|เรียนวิชาไหนก่อน|วิชาใดเรียนก่อน|เรียนอะไรก่อน")
_WHICH_FIRST_TAIL = re.compile(r"อันไหน(?:ต้อง)?เรียนก่อน|ต้องเรียนก่อนกัน|กัน|วิชาไหนเรียนก่อน|วิชาไหนก่อน|อันไหนเรียนก่อน|ตัวไหนเรียนก่อน|เรียนวิชาไหนก่อน|วิชาใดเรียนก่อน|เรียนอะไรก่อน|ระหว่าง|กับ|และ|วิชา|ไหน|เรียน|ก่อน|ครับ|ค่ะ|คะ|นะ")


def _which_first_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """สองวิชา "วิชาไหนเรียนก่อน" → เทียบปี/เทอมแรกที่พบในแผน; ไม่รู้เทอมของวิชาใด/ส่วนอื่นค้าง = None"""
    if not _WHICH_FIRST_Q.search(question) or _CODE8.search(question):
        return None
    _citations_module()
    import course_names
    try:
        courses = [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in conn.execute("SELECT code, name_th, name_en FROM course")]
        req, _alt = _requires_map(conn)
    except sqlite3.OperationalError:
        return None
    hints = course_names.course_hints(question, courses)
    if len({c for _, c in hints}) != 2 or len({_name_key(r) for r, _ in hints}) != 2:
        return None
    rest = question
    for raw, _ in sorted(hints, key=lambda h: -len(h[0])):
        rest = _remove_hinted_name(rest, raw)
    if _strip_punct(_WHICH_FIRST_TAIL.sub("", rest)):
        return None
    terms = _first_terms(conn)
    (_, a), (_, b) = hints[0], hints[1]
    if a not in terms or b not in terms:
        return None
    names = {c["code"]: c["name_th"] for c in courses}
    lab = lambda c: f"{names.get(c, c)} ({c}) {_TERM_LABEL.format(y=terms[c][0], s=terms[c][1])}"
    if terms[a] == terms[b]:
        text = f"{lab(a)} และ {lab(b)} อยู่เทอมเดียวกัน"
    else:
        first, second = (a, b) if terms[a] < terms[b] else (b, a)
        text = f"{lab(first)} เรียนก่อน {lab(second)}"
    if a in req.get(b, set()):
        text += f" ({names.get(a, a)} เป็นวิชาบังคับก่อนของ {names.get(b, b)})"
    elif b in req.get(a, set()):
        text += f" ({names.get(b, b)} เป็นวิชาบังคับก่อนของ {names.get(a, a)})"
    return text, [{"code": c, "name_th": names.get(c), "year": terms[c][0], "semester": terms[c][1]} for c in (a, b)], \
        f"SELECT code, year, semester FROM plan_item WHERE code IN ('{a}', '{b}') ORDER BY year, semester"


# ---- "รหัสของ <ชื่อสั้น>" ที่เป็นต้นชื่อของหลายวิชา (สหกิจศึกษา / สหกิจศึกษาต่างประเทศ) → ลิสต์ทุกวิชาในตระกูลชื่อนั้น ----
_CODE_FAMILY_ASK = re.compile(r"รหัสวิชา(?:อะไร|ไหน|ใด)|รหัสอะไร|ขอรหัส|รหัสของ|รหัสคือ")


def _code_family_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ผู้ถามเรียกชื่อสั้น ("สหกิจศึกษา") ซึ่งเป็น "ต้นชื่อ" ของ 2-4 วิชา (สหกิจศึกษา…, สหกิจศึกษาต่างประเทศ…) → ลิสต์รหัสของทุกวิชาในตระกูลนั้น;
    ต้องยาว >= 8 ตัวอักษร, ไม่ตรงชื่อเต็มของวิชาใด, ไม่มีรหัส/ปี/เทอม/หน่วยกิต; ไม่ใช่ตระกูล = None"""
    if not _CODE_FAMILY_ASK.search(question) or _CODE8.search(question) or any(_term_numbers(question)) or re.search(r"หน่วยกิต|ชั่วโมง|ก่อน", question):
        return None
    try:
        names = {r[0]: r[1] for r in conn.execute("SELECT code, name_th FROM course") if r[1]}
    except sqlite3.OperationalError:
        return None
    q = re.sub(r"\s+", "", question)
    groups: dict[str, list[str]] = {}
    for code, nm in names.items():
        n = re.sub(r"\s+", "", nm)
        best = ""
        for i in range(8, len(n) + 1):
            if n[:i] in q:
                best = n[:i]
            else:
                break
        if best and best != n:                                      # ต้นชื่อที่ผู้ถามพิมพ์ แต่ชื่อเต็มของวิชานี้ยาวกว่า
            groups.setdefault(best, []).append(code)
    if not groups:
        return None
    top = max(groups, key=len)
    fam = groups[top]
    if not 2 <= len(fam) <= 4 or any(re.sub(r"\s+", "", names[c]) in q for c in names):     # ชื่อเต็มของวิชาใดอยู่ในคำถามด้วย = ไม่ใช่เคสนี้
        return None
    rows = [{"code": c, "name_th": names[c]} for c in sorted(fam)]
    return (f"วิชาที่ชื่อขึ้นต้นด้วย \"{top}\" มี {len(fam)} วิชา: " + "; ".join(f"{c} {names[c]}" for c in sorted(fam)), rows,
            "SELECT code, name_th FROM course WHERE name_th LIKE '" + top + "%'")


# ---- สถานการณ์หลายวิชา: "ถ้าตก A แต่ผ่าน B แล้ว ลง C ได้ไหม" (รองรับวิชาบังคับก่อนแบบ "หรือ") ----
def _prereq_scenario_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """สามวิชาขึ้นไปในคำถามใช่/ไม่ใช่: วิชาสุดท้ายที่นำหน้าด้วย ลง/เรียน = วิชาที่จะลง; วิชาอื่นต้องมีคำว่า ตก/ไม่ผ่าน (ไม่ผ่าน) หรือ ผ่าน (ผ่านแล้ว) นำหน้าชัดเจน
    วิชาบังคับก่อนแบบ "A หรือ B" ผ่านอย่างใดอย่างหนึ่งก็ลงได้; ตัดสินไม่ได้/คำกำกวม = None"""
    if not _YESNO.search(question):
        return None
    _citations_module()
    import course_names
    try:
        courses = [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in conn.execute("SELECT code, name_th, name_en FROM course")]
        req, alt = _requires_map(conn)
    except sqlite3.OperationalError:
        return None
    known = {c["code"] for c in courses}
    found: list[tuple[int, int, str]] = []
    for raw, code in course_names.course_hints(question, courses):
        mt = re.search(re.escape(raw), question, re.I)
        if mt:
            found.append((mt.start(), mt.end(), code))
    for mt in _CODE8.finditer(question):
        if mt.group() in known:
            found.append((mt.start(), mt.end(), mt.group()))
    found = sorted(set(found))
    codes = list(dict.fromkeys(c for _, _, c in found))
    if len(codes) < 3:
        return None
    t_start, _t_end, target = found[-1]
    if not re.search(r"ลง|เรียน", question[max(0, t_start - 14):t_start]) or target not in req:
        return None
    passed, failed = set(), set()
    last = None                                                      # ขั้วของวิชาก่อนหน้า ("ตก A กับ B" = ตกทั้งคู่)
    for st, _en, code in found[:-1]:
        if code == target:
            return None
        ctx = question[max(0, st - 16):st]
        if re.search(r"ตก|ไม่ผ่าน", ctx):
            last = "fail"
        elif "ผ่าน" in ctx:
            last = "pass"
        elif not (last and re.search(r"(?:กับ|และ|,|แล้ว)\s*$", ctx)):
            return None
        (failed if last == "fail" else passed).add(code)
    names = {c["code"]: c["name_th"] for c in courses}

    def nm(c: str) -> str:
        return f"{names.get(c, c)} ({c})"
    need = req[target]
    sql = f"SELECT requires FROM prerequisite WHERE code = '{target}' AND kind = 'pre'"
    rows = [{"code": c, "name_th": names.get(c)} for c in sorted(need)]
    if target in alt:
        got = need & passed
        if got:
            return (f"ได้ — {nm(target)} มีวิชาบังคับก่อนแบบ \"หรือ\" ({' หรือ '.join(nm(c) for c in sorted(need))}) "
                    f"และผ่าน {', '.join(nm(c) for c in sorted(got))} แล้ว (ผ่านอย่างใดอย่างหนึ่งก็พอ)"), rows, sql
        if need & failed:
            return (f"ยังไม่ได้ — {nm(target)} ต้องผ่านอย่างใดอย่างหนึ่งใน {' หรือ '.join(nm(c) for c in sorted(need))} แต่ยังไม่ผ่านวิชาที่ระบุ"), rows, sql
        return None
    missing = need - passed
    if not missing:
        return f"ได้ — ผ่านวิชาบังคับก่อนของ {nm(target)} ครบแล้ว ({', '.join(nm(c) for c in sorted(need))})", rows, sql
    if missing & failed:
        return f"ไม่ได้ — {nm(target)} ต้องผ่าน {', '.join(nm(c) for c in sorted(missing))} ก่อน แต่ยังไม่ผ่าน", rows, sql
    return None


# ---- "วิชาที่ชื่อขึ้นต้นด้วย 'การออกแบบ' มีอะไรบ้าง" ----
_NAME_PREFIX_Q = re.compile(r"ขึ้นต้น(?:ด้วย|ว่า)(?:คำว่า)?\s*['\"“‘]?(?P<p>[^'\"”’\s][^'\"”’]*?)['\"”’]?(?=\s+(?:ใน|มี|ทั้งหมด|กี่)|\s*$|\s*\?)")


def _name_prefix_list_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """รายวิชา (หรือจำนวน) ที่ชื่อไทยขึ้นต้นด้วยคำที่ระบุ (ตัวพิมพ์/ช่องว่างไม่สำคัญ); คำสั้นกว่า 3 ตัวอักษร/มีรหัส/ปี-เทอม/ไม่พบวิชาใดเลย = None"""
    mt = _NAME_PREFIX_Q.search(question)
    if not mt or _CODE8.search(question) or any(_term_numbers(question)):
        return None
    prefix = _name_key(mt.group("p"))
    if len(prefix) < 3:
        return None
    try:
        rows = [(r[0], r[1]) for r in conn.execute("SELECT code, name_th FROM course ORDER BY code") if _name_key(r[1]).startswith(prefix)]
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None
    sql = f"SELECT code, name_th FROM course WHERE name_th LIKE '{mt.group('p').strip()}%'"
    out = [{"code": c, "name_th": n} for c, n in rows]
    if re.search(r"กี่วิชา|กี่รายวิชา|จำนวน", question) and not re.search(r"อะไรบ้าง|วิชาไหน|รายชื่อ", question):
        return f"มี {len(rows)} วิชาที่ชื่อขึ้นต้นด้วย \"{mt.group('p').strip()}\"", out, sql
    return f"วิชาที่ชื่อขึ้นต้นด้วย \"{mt.group('p').strip()}\" มี {len(rows)} วิชา: " + "; ".join(f"{c} {n}" for c, n in rows), out, sql


# ---- ผ่านวิชา A (และ B) แล้วลงอะไรได้ / สอบตก A แล้วลงอะไรต่อไม่ได้-กระทบวิชาไหน ----
_UNLOCK_PASS_Q = re.compile(r"(?<!ไม่)ผ่าน.{0,90}?แล้ว.{0,14}?(?:ลง|เรียน)(?:ทะเบียน)?(?:วิชา)?(?:อะไร|ไหน|ใด)(?:บ้าง)?(?:ได้|เพิ่ม|ต่อ|ที่ต้องใช้)")
_UNLOCK_FAIL_Q = re.compile(r"(?:สอบตก|ไม่ผ่าน|ตก).{0,90}?(?:กระทบ|ลง(?:ต่อ)?ไม่ได้|เรียนต่อไม่ได้|ลงทะเบียนต่อไม่ได้)")


def _requires_map(conn: sqlite3.Connection) -> tuple[dict[str, set[str]], set[str]]:
    """{วิชา: {วิชาบังคับก่อน}} จาก prerequisite (kind='pre') + วิชาที่มีทางเลือก "หรือ" (prerequisite_alt) แยกเป็น set ที่สอง"""
    req: dict[str, set[str]] = {}
    for c, r in conn.execute("SELECT code, requires FROM prerequisite WHERE kind = 'pre'"):
        req.setdefault(c, set()).add(r)
    try:
        alt = {r[0] for r in conn.execute("SELECT code FROM prerequisite_alt")}
    except sqlite3.OperationalError:
        alt = set()
    return req, alt


def _unlock_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """(ก) "ผ่าน A [กับ B] แล้วลงวิชาอะไรได้/ที่ต้องใช้วิชานี้" (หลายวิชา หรือมี "ที่ต้องใช้") → วิชาที่ลงได้ทันที (วิชาบังคับก่อนครบ) + ที่ต้องผ่านเพิ่ม/มีทางเลือก "หรือ"
    (ข) "สอบตก A แล้วลงต่อไม่ได้/กระทบวิชาไหน" → วิชาตัวต่อที่ลงไม่ได้ + ที่ตามมาเป็นลูกโซ่
    วิชาเดียวแบบ "ผ่าน A แล้วเรียนอะไรต่อได้" ยังไปทางเดิม; ถามใช่/ไม่ใช่ ("ได้ไหม") = None"""
    if _YESNO.search(question):
        return None
    pass_mode, fail_mode = bool(_UNLOCK_PASS_Q.search(question)), bool(_UNLOCK_FAIL_Q.search(question))
    if pass_mode == fail_mode:
        return None
    _citations_module()
    import course_names
    try:
        courses = [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in conn.execute("SELECT code, name_th, name_en FROM course")]
        req, alt = _requires_map(conn)
    except sqlite3.OperationalError:
        return None
    hints = course_names.course_hints(question, courses)
    known = {c["code"] for c in courses}
    given = list(dict.fromkeys([c for _, c in hints] + [c for c in _CODE8.findall(question) if c in known]))
    if not given or (pass_mode and len(given) < 2 and "ที่ต้องใช้" not in question):
        return None
    names = {c["code"]: c["name_th"] for c in courses}

    def nm(c: str) -> str:
        return f"{names.get(c, c)} ({c})"
    base = set(given)
    in_sql = "SELECT code, requires FROM prerequisite WHERE requires IN (" + ", ".join(f"'{c}'" for c in given) + ")"
    if pass_mode:
        deps = sorted(c for c, rs in req.items() if rs & base and c not in base)
        now = [c for c in deps if req[c] <= base and c not in alt]
        later = [c for c in deps if c not in now]
        parts = [f"ผ่าน {', '.join(nm(c) for c in given)} แล้ว ลงได้ทันที: " + ("; ".join(nm(c) for c in now) if now else "ยังไม่มีวิชาที่ลงได้ทันที")]
        if later:
            parts.append("ต้องผ่านวิชาอื่นเพิ่มหรือมีทางเลือก \"หรือ\" จึงจะลงได้: " + "; ".join(
                nm(c) + (" (มีทางเลือก \"หรือ\")" if c in alt else f" (ต้องผ่านเพิ่ม: {', '.join(nm(r) for r in sorted(req[c] - base))})") for c in later))
        rows = [{"code": c, "name_th": names.get(c), "effect": "ลงได้ทันที"} for c in now] + [{"code": c, "name_th": names.get(c), "effect": "ต้องผ่านเพิ่ม"} for c in later]
        return "; ".join(parts), rows, in_sql
    direct = sorted(c for c, rs in req.items() if rs & base and c not in base)
    seen, frontier = set(direct), list(direct)
    while frontier:
        frontier = [c for c, rs in req.items() if rs & set(frontier) and c not in seen and c not in base]
        seen |= set(frontier)
    indirect = sorted(seen - set(direct))
    head = (f"ถ้าสอบตก {', '.join(nm(c) for c in given)} วิชาที่ได้รับผลกระทบ (ลงไม่ได้จนกว่าจะผ่านก่อน): "
            + ("; ".join(nm(c) for c in direct) if direct else "ไม่มีวิชาที่ต้องใช้วิชานี้เป็นวิชาบังคับก่อน"))
    if indirect:
        head += "; และวิชาที่ตามมาเป็นลูกโซ่: " + "; ".join(nm(c) for c in indirect)
    rows = [{"code": c, "name_th": names.get(c), "effect": "ลงไม่ได้"} for c in direct] + [{"code": c, "name_th": names.get(c), "effect": "ตามมาเป็นลูกโซ่"} for c in indirect]
    return head, rows, in_sql


# ---- "วิชาไหน (ใน BIT) ที่มีวิชาบังคับก่อน / มีกี่วิชาที่มีวิชาบังคับก่อน" ----
_HAS_PREREQ_Q = re.compile(r"(?:วิชา(?:ไหน|อะไร)|มีวิชา(?:ไหน|อะไร)|มีกี่วิชา|กี่วิชา|วิชาที่).{0,30}?(?<!ไม่)(?:ที่)?(?:ต้อง)?มี\s*(?:วิชาบังคับก่อน|วิชาที่ต้องเรียนก่อน|prerequisite)", re.I)


def _courses_with_prereq_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """รายชื่อ (หรือจำนวน) วิชาที่มีวิชาบังคับก่อน ทั้งแผน; มีรหัส/ชื่อวิชา/ปี-เทอม/"กี่คู่"/"ไม่มี" = None"""
    if not _HAS_PREREQ_Q.search(question) or _CODE8.search(question) or _PAIR_WORD.search(question) or re.search(r"ไม่มี|ปี\s*\d|เทอม|ภาค", question):
        return None
    if _named_courses(conn, question, strict=False):
        return None
    try:
        codes = {r[0] for r in conn.execute("SELECT code FROM prerequisite WHERE kind = 'pre'")}
        try:
            codes |= {r[0] for r in conn.execute("SELECT code FROM prerequisite_alt")}
        except sqlite3.OperationalError:
            pass
        names = {r[0]: r[1] for r in conn.execute("SELECT code, name_th FROM course")}
    except sqlite3.OperationalError:
        return None
    codes = sorted(codes)
    if not codes:
        return None
    statuses = _prereq_statuses(conn) or {}
    unknown = [c for c, st in statuses.items() if st in ("not_found", "unreadable")]
    note = f" (อีก {len(unknown)} วิชาอ่านวิชาบังคับก่อนจากเล่มไม่ได้ จึงยังไม่ทราบ)" if unknown else ""
    rows = [{"code": c, "name_th": names.get(c)} for c in codes]
    sql = "SELECT DISTINCT code FROM prerequisite WHERE kind = 'pre'"
    if re.search(r"กี่วิชา", question) and not re.search(r"วิชา(?:ไหน|อะไร)", question):
        return f"มี {len(codes)} วิชาที่มีวิชาบังคับก่อน{note}", rows, sql
    return f"มี {len(codes)} วิชาที่มีวิชาบังคับก่อน: " + "; ".join(f"{c} {names.get(c, '')}".strip() for c in codes) + note, rows, sql


# ---- ระดับ 3-4: เทียบ "แผนสหกิจ กับ ไม่สหกิจ" ของหลักสูตรเดียวกัน (แผนหนึ่งเล่ม = คนละฐานข้อมูล runs/<หลักสูตร>/{coop,no_coop}) ----
_COOP_WORD = re.compile(r"(?<!ไม่)(?<!ไม่มี)(?<!ไม่ทำ)(?<!ไม่เข้า)สหกิจ")
_NOCOOP_WORD = re.compile(r"ไม่(?:มี|ทำ|เป็น|ใช่|เข้า|ได้ทำ)?(?:แผน)?สหกิจ|แผนปกติ|แผนทั่วไป")
_PLAN_DIFF_ASK = re.compile(r"ต่างกัน|ต่างจาก|แตกต่าง|เปรียบเทียบ|เทียบกับ|เทียบ|เหมือนกัน|ไม่มีใน|มีเฉพาะ|เพิ่มจาก|มีเพิ่ม|ที่มีใน|คนละ")
_PLAN_DIFF_NOT = re.compile(r"หน่วยกิตเท่า")


def _sibling_plan_db(conn: sqlite3.Connection) -> tuple[str, Path | None] | None:
    """(ชื่อแผนของ DB นี้ "coop"/"no_coop", path ของ DB แผนคู่ — None ถ้าไม่มี) จากโครงโฟลเดอร์ runs/<หลักสูตร>/<แผน>/lab8b_output/curriculum.db;
    หาโครงนี้ไม่เจอ (DB ทดสอบ/ในหน่วยความจำ) = None"""
    try:
        file = next((r[2] for r in conn.execute("PRAGMA database_list") if r[1] == "main"), "")
    except sqlite3.Error:
        return None
    if not file:
        return None
    p = Path(file)
    if len(p.parents) < 3 or p.parent.name != "lab8b_output" or p.parents[1].name not in ("coop", "no_coop"):
        return None
    mine = p.parents[1].name
    sib = p.parents[2] / ("no_coop" if mine == "coop" else "coop") / "lab8b_output" / p.name
    return mine, (sib if sib.exists() else None)


def _other_plan_diff_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """เปรียบเทียบแผนสหกิจกับไม่สหกิจของหลักสูตรเดียวกัน (พูดถึงทั้งสองแผน + ถามความต่าง) สามขอบเขต:
    ทั้งแผน (วิชาเฉพาะแต่ละแผน + หน่วยกิตรวม) · เทอมเดียว ("ปี 4 เทอม 2 ต่างกันยังไง": วิชา/ช่องเลือกของเทอมนั้นในสองแผน) · วิชาเดียว (รหัสหรือชื่อ: เรียนเทอมเดียวกันไหม)
    หลักสูตรที่มีแผนเดียว (AIT) = บอกว่ามีแผนเดียว; ระบุปีโดยไม่มีเทอม / ปนหลายขอบเขต / ไม่รู้แผนคู่ = None"""
    if not (_COOP_WORD.search(question) and _NOCOOP_WORD.search(question)) or not _PLAN_DIFF_ASK.search(question) or _PLAN_DIFF_NOT.search(question):
        return None
    y, sm = _term_numbers(question)
    codes = list(dict.fromkeys(_CODE8.findall(question)))
    named = _named_courses(conn, question, strict=False)
    if named:
        codes = list(dict.fromkeys(codes + list(named)))
    if sm and not y:
        return None
    if codes and (y or sm or len(codes) != 1):
        return None
    where = _sibling_plan_db(conn)
    if where is None:
        try:                                                         # DB ที่ไม่มีโครงโฟลเดอร์แผนคู่: หลักสูตรเดียวแผนเดียวเท่านั้นที่ตอบได้ (AIT)
            pid = conn.execute("SELECT program_id FROM program LIMIT 1").fetchone()[0] or ""
        except (sqlite3.Error, TypeError):
            return None
        return ("หลักสูตรนี้มีแผนการเรียนแผนเดียว ไม่แยกแผนสหกิจ/ไม่สหกิจ", [], "SELECT program_id FROM program") if pid.upper() == "AIT" else None
    mine, sib_path = where
    if sib_path is None:
        return None
    other = open_db(sib_path, readonly=True)
    try:
        plans = {"สหกิจ": conn if mine == "coop" else other, "ไม่สหกิจ": conn if mine == "no_coop" else other}
        names: dict[str, str] = {}
        for c in plans.values():
            names.update({r[0]: r[1] for r in c.execute("SELECT code, name_th FROM course")})

        def page_of(code: str, plan: str) -> dict:
            """หน้าอ้างอิงของวิชาจากฐานข้อมูลของแผนที่วิชานี้อยู่ (ตารางแผน > คำอธิบาย > หน้าที่พบวิชา); ไม่พบ = ไม่ใส่ (ไม่เดา)"""
            try:
                got = plans[plan].execute("SELECT pdf_page, printed_page FROM course_page WHERE code = ? ORDER BY CASE kind WHEN 'plan' THEN 0 "
                                          "WHEN 'description' THEN 1 WHEN 'primary' THEN 2 ELSE 3 END, pdf_page LIMIT 1", (code,)).fetchone()
            except sqlite3.OperationalError:
                got = None
            return {"pdf_page": got[0], "printed_page": got[1]} if got else {}

        def fmt(cs) -> str:
            return "; ".join(f"{c} {names.get(c, '')}".strip() for c in cs) if cs else "ไม่มี"

        if codes:                                                    # ---- วิชาเดียว: เทอมในสองแผน ----
            code = codes[0]
            where_txt, rows = {}, []
            for plan, c in plans.items():
                places = [tuple(r) for r in c.execute("SELECT DISTINCT year, semester FROM plan_item WHERE code = ? ORDER BY year, semester", (code,))]
                where_txt[plan] = places
                rows += [{"code": code, "name_th": names.get(code), "plan": plan, "year": a, "semester": b, **page_of(code, plan)} for a, b in places[:1]]
            if not any(where_txt.values()):
                return None
            show = lambda pl: (" และ ".join(f"ปี {a} เทอม {b}" for a, b in where_txt[pl]) if where_txt[pl] else "ไม่มีในแผนนี้")
            same = where_txt["สหกิจ"] == where_txt["ไม่สหกิจ"]
            verdict = "เรียนเทอมเดียวกัน" if same else ("มีเฉพาะในแผนเดียว" if not (where_txt["สหกิจ"] and where_txt["ไม่สหกิจ"]) else "เรียนคนละเทอมกัน")
            return (f"{code} {names.get(code, '')}: แผนสหกิจ {show('สหกิจ')}; แผนไม่สหกิจ {show('ไม่สหกิจ')} → {verdict}", rows,
                    f"SELECT year, semester FROM plan_item WHERE code = '{code}'")
        if y and not sm:                                             # ---- ทั้งปี: หน่วยกิตและวิชาเฉพาะแต่ละแผน ----
            tot, cnt, sets, rows = {}, {}, {}, []
            for plan, c in plans.items():
                got = c.execute("SELECT SUM(credits), SUM(n_entries) FROM main.v_semester_credits_full WHERE year = ?", (y,)).fetchone()
                tot[plan], cnt[plan] = got[0], got[1]
                sets[plan] = {r[0] for r in c.execute("SELECT DISTINCT code FROM plan_item WHERE year = ?", (y,)) if re.fullmatch(r"\d{8}", r[0] or "")}
            if tot["สหกิจ"] is None or tot["ไม่สหกิจ"] is None:
                return None
            only = {pl: sorted(sets[pl] - sets["ไม่สหกิจ" if pl == "สหกิจ" else "สหกิจ"]) for pl in sets}
            text = (f"ปี {y}: แผนสหกิจรวม {tot['สหกิจ']} หน่วยกิต ({cnt['สหกิจ']} วิชา) เทียบกับแผนไม่สหกิจรวม {tot['ไม่สหกิจ']} หน่วยกิต ({cnt['ไม่สหกิจ']} วิชา) | "
                    f"เฉพาะแผนสหกิจ: {fmt(only['สหกิจ'])} | เฉพาะแผนไม่สหกิจ: {fmt(only['ไม่สหกิจ'])}")
            for pl in ("สหกิจ", "ไม่สหกิจ"):
                rows += [{"code": c, "name_th": names.get(c), "plan": pl, **page_of(c, pl)} for c in only[pl]]
            rows.insert(0, {"year": y, "credits_coop": tot["สหกิจ"], "credits_no_coop": tot["ไม่สหกิจ"]})
            return text, rows, f"SELECT SUM(credits) FROM main.v_semester_credits_full WHERE year = {y}"
        if y and sm:                                                 # ---- เทอมเดียว ----
            data, rows = {}, []
            for plan, c in plans.items():
                items = [tuple(r) for r in c.execute("SELECT code, note FROM plan_item WHERE year = ? AND semester = ? ORDER BY id", (y, sm))]
                slots = [r[0] for r in c.execute("SELECT name_th FROM plan_slot WHERE year = ? AND semester = ? ORDER BY id", (y, sm))]
                data[plan] = (items, slots)
            only = {pl: sorted({c for c, _ in data[pl][0]} - {c for c, _ in data["ไม่สหกิจ" if pl == "สหกิจ" else "สหกิจ"][0]}) for pl in data}

            def listing(pl: str) -> str:
                items, slots = data[pl]
                bits = [f"{c} {names.get(c, '')}".strip() + (f" [{mk.group(1)}]" if (mk := re.search(r"\|\s*(บังคับ|เลือกเสรี|เลือก)\s*$", n or "")) else "") for c, n in items]
                bits += [f"ช่อง: {sl}" for sl in slots]
                return "; ".join(bits) if bits else "ไม่มีวิชาในเทอมนี้"
            cr = {pl: (c.execute("SELECT credits FROM main.v_semester_credits_full WHERE year = ? AND semester = ?", (y, sm)).fetchone() or [None])[0]
                  for pl, c in plans.items()}
            text = (f"ปี {y} เทอม {sm} — แผนสหกิจ (รวม {cr['สหกิจ']} หน่วยกิต): {listing('สหกิจ')} | แผนไม่สหกิจ (รวม {cr['ไม่สหกิจ']} หน่วยกิต): {listing('ไม่สหกิจ')} | "
                    f"เฉพาะแผนสหกิจ: {fmt(only['สหกิจ'])} | เฉพาะแผนไม่สหกิจ: {fmt(only['ไม่สหกิจ'])}")
            for pl in ("สหกิจ", "ไม่สหกิจ"):
                rows += [{"code": c, "name_th": names.get(c), "plan": pl, "only_here": c in only[pl], **page_of(c, pl)} for c, _ in data[pl][0]]
            if not any(data[pl][0] or data[pl][1] for pl in data):
                return None
            return text, rows, f"SELECT code, note FROM plan_item WHERE year = {y} AND semester = {sm}"
        # ---- ทั้งแผน ----
        sets = {pl: {r[0] for r in c.execute("SELECT DISTINCT code FROM plan_item") if re.fullmatch(r"\d{8}", r[0] or "")} for pl, c in plans.items()}
        totals = {pl: c.execute("SELECT SUM(credits) FROM main.v_semester_credits_full").fetchone()[0] for pl, c in plans.items()}
        only_coop, only_no = sorted(sets["สหกิจ"] - sets["ไม่สหกิจ"]), sorted(sets["ไม่สหกิจ"] - sets["สหกิจ"])
        text = (f"เฉพาะแผนสหกิจ {len(only_coop)} วิชา: {fmt(only_coop)} | เฉพาะแผนไม่สหกิจ {len(only_no)} วิชา: {fmt(only_no)} | "
                f"หน่วยกิตรวม (นับช่องตามเล่ม): แผนสหกิจ {totals['สหกิจ']}, แผนไม่สหกิจ {totals['ไม่สหกิจ']} "
                "(เทียบรหัสวิชาในแผน ไม่รวมช่องวิชาเลือกที่นักศึกษาเลือกเอง)")
        rows = [{"code": c, "name_th": names.get(c), "only_in": "สหกิจ", **page_of(c, "สหกิจ")} for c in only_coop] + \
               [{"code": c, "name_th": names.get(c), "only_in": "ไม่สหกิจ", **page_of(c, "ไม่สหกิจ")} for c in only_no]
        return text, rows, "SELECT DISTINCT code FROM plan_item"
    except sqlite3.OperationalError:
        return None
    finally:
        other.close()


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
    if _SECTION_NOT.search(q) or _named_courses(conn, q, strict=False):     # ชื่อวิชา (แผน/แคตตาล็อก/GE) ที่มีคำหัวข้อติดอยู่ เช่น "…มืออาชีพ", "ปรัชญาเศรษฐกิจพอเพียง"
        return None
    parts, rows = [], []
    for t in topics:
        label = _SECTION_LABEL[t]
        if t not in have:
            parts.append(f"ไม่พบหัวข้อ{label}ในเล่มหลักสูตร")
            continue
        d = have[t]
        body = _clean_book_body(d["body"])
        parts.append(f"{label}: {body}")
        rows.append({"topic": t, "heading": d["heading"], "body": body, "pdf_page": d["pdf_page"], "printed_page": d["printed_page"]})
    sql = "SELECT topic, heading, body, pdf_page FROM book_section WHERE topic IN (" + ", ".join(f"'{t}'" for t in topics) + ")"
    return "\n".join(parts), rows, sql


# ---- 11. "ขอรหัสวิชา <ชื่อวิชา>" — รหัสจากชื่อ (ไทย/อังกฤษ) ตรง ๆ โมเดลเคยสุ่มเขียน SQL ผิดตาราง (prerequisite) แล้วตอบ "ไม่พบ" ----
_CODE_ASK_RE = re.compile(r"รหัส|course\s*code|code\s+(?:of|for)\b", re.I)
_CODE_NOT_RE = re.compile(r"ปี\s*\d|ชั้นปี|เทอม|ภาคการศึกษา|ก่อน|หน่วยกิต|ชั่วโมง|ต่างกัน|เปรียบเทียบ")


# คำถามเชิงความสัมพันธ์ (ต่อจาก/เป็นพื้นฐาน/เทอมเดียวกับ/แทน/ถ้า…) ถึงมีชื่อวิชาก็ไม่ได้ถามค่าของวิชานั้น → ทางลัดเรื่อง "วิชาเดียว" ต้องปฏิเสธ
_RELATIONAL_NOT = re.compile(
    r"ต่อจาก|ตัวต่อ|เป็นพื้นฐาน|พื้นฐานของ|เดียวกับ|คู่กับ|ร่วมกับ|เทียบกับ|เทียบเท่า|ต่างจาก|ต่างกัน|เหมือนกับ|แล้ว.{0,14}ต่อ|ต่อไป|ถัดไป|ก่อนหน้า|"
    r"แทน|ทดแทน|หลังจาก|วิชาที่|ที่ใช้|ถ้า|หาก|(?:เทอม|ภาค|ปี)ที่(?:เรียน|ลง)")
# ตัวอักษรที่อยู่ติดหน้า/หลังชื่อวิชาได้ โดยยังเป็น "ชื่อเต็ม" (คำนำ/คำถาม/เครื่องหมาย) — ตัวอักษรไทยอื่นที่ติดอยู่ = ชื่ออาจยาวกว่านี้ (เช่น "…ขั้นสูง", "การเตรียมความพร้อม…")
_NAME_PREFIX_OK = re.compile(r"(?:^|วิชา|รายวิชา|รหัสวิชา|รหัส|ของ|ขอ|ทราบ|คือ|ที่|ใน|เรื่อง|ว่า|ชื่อ|ถาม|เกี่ยวกับ|เรียน|ลง|บอก|ช่วย|หา|ดู|อยากรู้|อยาก|หน่อย|นะ|ครับ|ค่ะ|"
                             r"code|of|for|is|the|about|course|name|[,.:;()\-–\"'?!/])$")
_NAME_SUFFIX_OK = re.compile(r"^(?:$|กี่|มี|รหัส|เรียน|คือ|ใช้|อยู่|เป็น|ชื่อ|สอน|เกี่ยวกับ|ต้อง|ได้|ไหม|หรือไม่|อะไร|ปี|เทอม|ภาค|ชั่วโมง|หน่วยกิต|ครับ|ค่ะ|นะ|หน่อย|จะ|"
                             r"แล็บ|แลป|บรรยาย|ปฏิบัติ|ศึกษา|สัปดาห์|ใคร|ที่|ใน|ของ|จบ|code|[,.:;()\-–\"'?!/])")


def _name_key(text: str | None) -> str:
    """ชื่อวิชาสำหรับเทียบ: ตัดช่องว่าง/ตัวพิมพ์, นิคหิต+า → ำ (พิมพ์ได้สองแบบ), ซ→ช (OCR สับสน "เซิง"/"เชิง")"""
    return re.sub(r"\s+", "", (text or "").replace("ํา", "ำ")).lower().replace("ซ", "ช")


def _name_is_whole(qn: str, key: str) -> bool:
    """ชื่อวิชา key ปรากฏใน qn (ตัดช่องว่างแล้ว) ในฐาน "ชื่อเต็ม": ก่อน/หลังเป็นต้นประโยค คำนำ/คำถามที่รู้จัก หรือเครื่องหมาย (อย่างน้อยหนึ่งตำแหน่ง)
    ตัวอักษรไทย/อังกฤษ/ตัวเลขอื่นที่ติดอยู่ (ชื่อยาวกว่าที่ไม่มีใน DB), "และ/กับ" ต่อท้าย (สองวิชา) = ไม่ใช่ชื่อเต็ม"""
    for mt in re.finditer(re.escape(key), qn):
        tail = qn[mt.end():]
        if re.match(r"[,/&\-–]\d", tail):                    # "X 1, 2" / "X 1-2" = หลายวิชาในลำดับเดียวกัน ไม่ใช่ชื่อเดียว
            continue
        if _NAME_PREFIX_OK.search(qn[: mt.start()]) and _NAME_SUFFIX_OK.match(tail):
            return True
    return False


def _named_courses(conn: sqlite3.Connection, question: str, catalog: bool = True, strict: bool = True,
                   relational_ok: bool = False) -> dict[str, str] | None:
    """{รหัส: ชื่อไทย} ของวิชาที่ระบุในคำถามด้วยชื่อ (ไทยหรืออังกฤษ ทั้งวิชาในแผนและแคตตาล็อกรวม GE เมื่อ catalog=True);
    strict=True (ค่าตั้งต้น): ต้องเป็นชื่อเต็ม (_name_is_whole) และไม่ใช่คำถามเชิงความสัมพันธ์ — ชื่อที่ไม่มีใน DB ที่มีชื่อวิชาอื่นอยู่ข้างใน = None;
    strict=False: แค่ "มีชื่อวิชาอยู่ในคำถามไหม" (ใช้ตัดสินว่าไม่ใช่คำถามระดับหลักสูตร/หัวข้อ); ชื่อยาวสุดชนะ; ชื่อเดียวกันหลายรหัส = คืนทุกรหัส; กำกวม = None"""
    if strict and not relational_ok and _RELATIONAL_NOT.search(question):
        return None
    try:
        pairs = [(r[0], r[1] or "", r[2] or "") for r in conn.execute("SELECT code, name_th, name_en FROM course")]
        if catalog:
            pairs += [(r[0], r[1] or "", r[2] or "") for r in conn.execute("SELECT code, course_name_th, course_name_en FROM main.v_elective_group")]
    except sqlite3.OperationalError:
        return None
    qn = _name_key(question)
    hits: dict[str, dict[str, str]] = {}                       # ชื่อที่ normalise แล้ว → {รหัส: ชื่อไทย}
    for code, th, en in pairs:
        for name in (th, en):
            key = _name_key(name)
            if len(key) >= 5 and key in qn and (not strict or _name_is_whole(qn, key)):
                hits.setdefault(key, {}).setdefault(code, th or en)
    maximal = [k for k in hits if not any(k != o and k in o for o in hits)]
    if not maximal or len({frozenset(hits[k]) for k in maximal}) != 1:
        return None
    return {c: n for k in maximal for c, n in hits[k].items()}


def _code_lookup_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ถามรหัสของวิชาที่ระบุด้วยชื่อ (ไทยหรืออังกฤษ ทั้งวิชาในแผนและวิชาแคตตาล็อก) → ตอบรหัสจาก DB ตรง ๆ;
    ระบุวิชาไม่ได้/กำกวมหลายวิชา/มีรหัสวิชาหรือปีเทอมในคำถาม = None (ทางเดิม)"""
    if not _CODE_ASK_RE.search(question) or _CODE_NOT_RE.search(question) or _CODE8.search(question) or _RELATIONAL_NOT.search(question):
        return None
    codes = _named_courses(conn, question)
    if not codes:
        return None
    found = [{"code": c, "name_th": n} for c, n in sorted(codes.items())]
    ids = ", ".join(f"'{r['code']}'" for r in found)
    return "; ".join(f"{r['code']} ({r['name_th']})" for r in found), found, f"SELECT code, name_th FROM course WHERE code IN ({ids})"


# ---- 12. ชั่วโมงบรรยาย/ปฏิบัติ/ศึกษาเองของวิชาเดียว และวิชาที่ชั่วโมงมาก/น้อยที่สุดในปีที่ระบุ ----
# ทดสอบ 5 รอบ: โมเดลไม่แกว่ง แต่ตอบผิดซ้ำทุกรอบ ("แล็บกี่ชั่วโมง" ตอบ lecture_h; "บรรยายนานที่สุด" ตอบผลบวกสามคอลัมน์)
_HOUR_ATTRS = (("lecture_h", "บรรยาย", r"บรรยาย|ทฤษฎี"), ("lab_h", "ปฏิบัติ", r"ปฏิบัติ|แล็บ|แลป|lab\b"),
               ("self_h", "ศึกษาด้วยตนเอง", r"ศึกษาด้วยตนเอง|ศึกษาเอง|นอกชั้นเรียน"))
_HOURS_NOT_RE = re.compile(r"ปี\s*\d|ชั้นปี|เทอม|ภาคการศึกษา|มากกว่า|น้อยกว่า|ไม่น้อยกว่า|ไม่เกิน|เกิน|อย่างน้อย|ตั้งแต่|อะไรบ้าง|วิชาไหน|วิชาอะไร|"
                           r"ทั้งหมด|รวม|ทุกวิชา|กี่วิชา|จำนวนวิชา|หน่วยกิต")


def _hours_attrs(question: str) -> list[tuple[str, str]]:
    return [(col, label) for col, label, rx in _HOUR_ATTRS if re.search(rx, question, re.I)]


def _course_hours_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ชั่วโมงบรรยาย/ปฏิบัติ/ศึกษาด้วยตนเองต่อสัปดาห์ของ "วิชาเดียว" (ระบุด้วยรหัสหรือชื่อ) จากแถว course ตรง ๆ;
    ถามหลายวิชา/ถามเป็นรายการ/มีเงื่อนไขเทียบตัวเลข/ปีเทอม/ไม่ระบุวิชา/ชั่วโมงในเล่มเป็นค่าว่าง = None (ทางเดิม)"""
    if "ชั่วโมง" not in question or _HOURS_NOT_RE.search(question) or _RELATIONAL_NOT.search(question):
        return None
    attrs = _hours_attrs(question)
    if not attrs:
        return None
    codes = list(dict.fromkeys(_CODE8.findall(question)))
    if len(codes) > 1:
        return None
    if codes:
        named = {codes[0]: ""}
    else:
        named = _named_courses(conn, question)                 # รวมแคตตาล็อก/GE: ชื่อวิชานอกแผนที่ยาวกว่าต้องไม่ตกไปเป็นวิชาในแผนที่สั้นกว่า
        if not named or len(named) != 1:
            return None
    code = next(iter(named))
    cols = ", ".join(c for c, _ in attrs)
    try:
        row = conn.execute(f"SELECT code, name_th, {cols} FROM course WHERE code = ?", (code,)).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None or any(row[c] is None for c, _ in attrs):
        return None
    out = dict(row)
    text = " ".join(f"ชั่วโมง{label} {row[c]} ชั่วโมงต่อสัปดาห์" for c, label in attrs)
    return f"{row['code']} {row['name_th']}: {text}", [out], f"SELECT code, name_th, {cols} FROM course WHERE code = '{code}'"


_HOURS_MAX = re.compile(r"นานที่สุด|นานสุด|มากที่สุด|มากสุด|สูงสุด|เยอะที่สุด")
_HOURS_MIN = re.compile(r"น้อยที่สุด|น้อยสุด|ต่ำสุด|สั้นที่สุด|สั้นสุด")


def _extreme_hours_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """วิชาที่ชั่วโมงบรรยาย/ปฏิบัติ/ศึกษาเองมาก/น้อยที่สุดในแผน (ทั้งแผนหรือเฉพาะปีที่ระบุ เช่น "ปี 1 กับปี 2", "ปี 1 ถึงปี 3") —
    ค่าสูงสุด/ต่ำสุดของ "คอลัมน์เดียว" ไม่ใช่ผลบวก; เสมอกันบอกทุกวิชา; ระบุเทอม/รหัส/ชื่อวิชา/ไม่ใช่เรื่องชั่วโมง = None"""
    want_max, want_min = bool(_HOURS_MAX.search(question)), bool(_HOURS_MIN.search(question))
    attrs = _hours_attrs(question)
    if want_max == want_min or len(attrs) != 1 or _CODE8.search(question) or re.search(r"เทอม|ภาคการศึกษา|ภาคเรียน|หน่วยกิต|ปีไหน|ปีใด", question):
        return None
    if "ชั่วโมง" not in question and not re.search(r"นาน|เยอะ", question):
        return None
    nonzero = bool(re.search(r"ไม่(?:เป็น|ใช่)\s*(?:ศูนย์|0)|ไม่นับ\s*(?:ศูนย์|0)|มากกว่า\s*0", question))      # "น้อยที่สุดที่ไม่ใช่ศูนย์" = ค่าต่ำสุดในบรรดาค่าที่ > 0
    if _named_courses(conn, question, strict=False) or re.search(r"ยกเว้น|รองลงมา|อันดับ", question):
        return None
    col, label = attrs[0]
    if _YEAR_WORDS.search(question):                          # "ปีสุดท้าย/ปีหนึ่ง" ต้องรู้ว่าปีไหน — ไม่เดา ไม่ใช่ทั้งแผน
        return None
    years = _question_years(question)
    where = f" AND p.year IN ({', '.join(str(y) for y in sorted(years))})" if years else ""
    sql = (f"SELECT DISTINCT c.code, c.name_th, c.{col} FROM course c JOIN plan_item p ON p.code = c.code "
           f"WHERE c.{col} IS NOT NULL{' AND c.' + col + ' > 0' if nonzero else ''}{where}")
    try:
        rows = [dict(r) for r in conn.execute(sql).fetchall()]
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None
    best = (max if want_max else min)(r[col] for r in rows)
    top = sorted((r for r in rows if r[col] == best), key=lambda r: r["code"])
    scope = f"ปี {', '.join(str(y) for y in sorted(years))}" if years else "ทั้งแผน"
    names = " และ ".join(f"{r['code']} {r['name_th']}" for r in top)
    return (f"วิชาที่ชั่วโมง{label}{'มาก' if want_max else 'น้อย'}ที่สุดใน{scope}คือ {names} ({best} ชั่วโมงต่อสัปดาห์)", top,
            sql + f" ORDER BY c.{col} {'DESC' if want_max else 'ASC'}")


# ---- 13. ข้อมูลระดับหลักสูตร (เรียนกี่ปี/หน่วยกิตรวม) และหน่วยกิต/ปี/เทอมของวิชาเดียว ----
# held-out ใหม่ 270 ข้อ: "เรียนทั้งหมดกี่ปี" โมเดลตอบ COUNT(DISTINCT year) FROM program ผิดทุก DB; หน่วยกิต/ปี/เทอมของวิชาเดียวบางครั้งถามตารางผิด
_FACT_NOT_RE = re.compile(r"ปี\s*\d|ชั้นปี|ปีที่|เทอม|ภาค|หมวด|กลุ่ม|เลือก|เสรี|ศึกษาทั่วไป|วิชา|อะไรบ้าง|ชั่วโมง|ก่อน|รหัส|[A-Za-z]{4,}")


# ขอบเขตย่อย/ค่าสูงสุด/เงื่อนไขพิเศษ ที่ไม่ใช่ "ยอดของทั้งหลักสูตร" — ปีแรก/ปีสุดท้าย/ซัมเมอร์/แกน/สะสม/ระยะเวลาสูงสุด/สหกิจ
_FACT_SUBSCOPE_RE = re.compile(r"ปีแรก|ปีสุดท้าย|ปีหนึ่ง|ปีสอง|ปีสาม|ปีสี่|ซัมเมอร์|ฤดูร้อน|แกน|สะสม|สูงสุด|นานสุด|นานที่สุด|ไม่เกิน|ขั้นต่ำ|อย่างน้อย|เฉลี่ย|"
                              r"ต่อเทอม|ต่อภาค|ออกสหกิจ|ไปสหกิจ|ก่อนสหกิจ|ลงสหกิจ|ฝึกสหกิจ|ฝึกงาน|ได้ออก|ถึงจะออก|ก่อนออก")


def _program_fact_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ "หลักสูตรนี้เรียนกี่ปี" / "ต้องเรียนกี่หน่วยกิตถึงจะจบ" → ค่าจากตาราง program (หน่วยกิตรวมตลอดหลักสูตร, จำนวนปี);
    มีปี/เทอม/หมวด/กลุ่ม/วิชาเลือก/ชื่อวิชา/รหัสวิชาในคำถาม = None (ไปทางทางลัดอื่นหรือโมเดล)"""
    # ชื่อหลักสูตร (DSBA/AIT/BIT/IT) ไม่นับเป็น "คำอังกฤษ 4 ตัวขึ้นไป" ของ _FACT_NOT_RE — ชื่อของหลักสูตรอื่นถูกดักไปแล้วโดย _other_program_answer
    if _FACT_NOT_RE.search(_PROGRAM_TOKEN.sub("", question)) or _FACT_SUBSCOPE_RE.search(re.sub(r"สะสม(?:ให้)?ครบ", "", question))             or _CODE8.search(question) or _RELATIONAL_NOT.search(question):
        return None
    years = bool(re.search(r"กี่ปี", question) and re.search(r"เรียน|ใช้เวลา|ระยะเวลา|หลักสูตร|จบ|ศึกษา", question))
    credits = bool("หน่วยกิต" in question and re.search(r"หลักสูตร|ถึงจะจบ|จึงจะจบ|เพื่อจบ|แผน(?:สหกิจ|ไม่สหกิจ|การเรียน|การศึกษา)|กี่หน่วยกิตรวม|รวมกี่หน่วยกิต", question))
    if years == credits:                                                   # ไม่ใช่ทั้งสองอย่าง/ถามสองอย่างพร้อมกัน → ทางเดิม
        return None
    try:
        progs = [dict(r) for r in conn.execute("SELECT total_credits, years FROM program").fetchall()]
    except sqlite3.OperationalError:
        return None
    if len(progs) != 1 or _named_courses(conn, question, strict=False):
        return None
    col, label = ("years", "ปี") if years else ("total_credits", "หน่วยกิต")
    if progs[0][col] is None:
        return None
    row: dict[str, Any] = {col: progs[0][col]}
    try:                                                     # หน้าที่เล่มพิมพ์ข้อมูลนี้ (book_section) — ไม่มีตาราง/หัวข้อ = ไม่อ้างหน้า
        page = conn.execute("SELECT pdf_page, printed_page FROM book_section WHERE topic = ?",
                            ("ระยะเวลาการศึกษา" if years else "หน่วยกิตตลอดหลักสูตร",)).fetchone()
    except sqlite3.OperationalError:
        page = None
    if page:
        row.update(pdf_page=page[0], printed_page=page[1])
    return (f"{'หลักสูตรนี้ใช้เวลาเรียนตามแผน' if years else 'หน่วยกิตรวมตลอดหลักสูตร'} {progs[0][col]} {label}", [row],
            f"SELECT {col} FROM program")


_ATTR_YEAR = re.compile(r"ปีไหน|ชั้นปีไหน|ปีใด|ชั้นปีใด|ปีที่เท่าไร|ปีที่เท่าไหร่|ปีอะไร")
_ATTR_SEM = re.compile(r"เทอมไหน|ภาคไหน|ภาคเรียนไหน|ภาคการศึกษาไหน|เทอมใด|ภาคเรียนที่เท่าไร|เทอมที่เท่าไร|เทอมอะไร")
_ATTR_NOT = re.compile(r"ปี\s*\d|ชั้นปีที่\s*\d|เทอม\s*\d|ภาค\S*\s*\d|รวม|ทั้งหมด|กี่วิชา|หมวด|ชั่วโมง|ก่อน|รหัส|ชื่อ|อะไรบ้าง|วิชาไหนบ้าง|วิชา(?:อะไร|ใด)")


def _course_attr_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """หน่วยกิต / ปี / เทอมที่เรียน ของ "วิชาเดียว" (ระบุด้วยรหัสหรือชื่อ) จากตาราง course และ plan_item ตรง ๆ;
    วิชาอยู่ในแผนหลายที่ = บอกทุกที่; ปี/เทอมของวิชานอกแผน, ถามหลายวิชา/เป็นรายการ/มีเลขปีเทอมในคำถาม = None (ทางเดิม)"""
    want_credits = "หน่วยกิต" in question
    want_year, want_sem = bool(_ATTR_YEAR.search(question)), bool(_ATTR_SEM.search(question))
    if not (want_credits or want_year or want_sem) or _ATTR_NOT.search(question) or _RELATIONAL_NOT.search(question):
        return None
    codes = list(dict.fromkeys(_CODE8.findall(question)))
    if len(codes) > 1:
        return None
    if codes:
        code = codes[0]
    else:
        named = _named_courses(conn, question)                 # รวมแคตตาล็อก/GE (ดู _course_hours_answer)
        if not named or len(named) != 1:
            return None
        code = next(iter(named))
    try:
        course = conn.execute("SELECT code, name_th, credits FROM course WHERE code = ?", (code,)).fetchone()
        places = [tuple(r) for r in conn.execute("SELECT DISTINCT year, semester FROM plan_item WHERE code = ? ORDER BY year, semester", (code,))]
    except sqlite3.OperationalError:
        return None
    if course is None or ((want_year or want_sem) and not places) or (want_credits and course["credits"] is None):
        return None
    bits, rows = [], []
    if want_credits:
        bits.append(f"{course['credits']} หน่วยกิต")
    if want_year or want_sem:
        bits.append(" และ ".join(f"ปี {y} เทอม {s}" for y, s in places))
        for y, s in places:
            rows.append({"code": course["code"], "name_th": course["name_th"], "year": y, "semester": s,
                         **({"credits": course["credits"]} if want_credits else {})})
    else:
        rows.append({"code": course["code"], "name_th": course["name_th"], "credits": course["credits"]})
    return (f"{course['code']} {course['name_th']}: " + " — ".join(bits), rows,
            f"SELECT c.code, c.name_th, c.credits, p.year, p.semester FROM course c LEFT JOIN plan_item p ON p.code = c.code WHERE c.code = '{code}'")


# ---- 14. กลุ่มวิชาเลือกถามด้วยชื่อกลุ่ม (รายชื่อวิชา / จำนวนวิชา / หน่วยกิตที่ต้องเลือก) ----
# ชุดสำนวนใหม่: "กลุ่มวิชาเลือกการตลาดเชิงดิจิทัล มีวิชาอะไรบ้าง" โมเดลหยิบวิชา "การตลาดเชิงดิจิทัล" แทนกลุ่ม, "…มีกี่วิชา" ตอบ 0 (ชื่อกลุ่มไม่ตรงตัว)
_GROUP_LIST = re.compile(r"อะไรบ้าง|วิชาอะไร|มีวิชา(?:อะไร|ไหน)|วิชาไหนบ้าง|รายชื่อ|ได้แก่|รหัสวิชา|ให้เลือก")
_GROUP_COUNT = re.compile(r"กี่วิชา|กี่รายวิชา|จำนวนวิชา|กี่ตัว")
_GROUP_CREDITS = re.compile(r"กี่หน่วยกิต")
_GROUP_NOT = re.compile(r"ปี\s*\d|ชั้นปี|ปีไหน|เทอม|ภาคการศึกษา|ภาคเรียน|ก่อน|ชั่วโมง|อยู่ใน|เป็นวิชา|หรือเปล่า|หรือไม่|ต่อจาก|เดียวกับ")


def _elective_group_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ถามกลุ่มวิชาเลือกที่ระบุด้วยชื่อกลุ่ม (ไม่รวมกลุ่ม GE) → รายชื่อวิชาในกลุ่ม / จำนวนวิชา / หน่วยกิตที่ต้องเลือก (credits_required) จาก DB ตรง ๆ;
    ถามหลายอย่างพร้อมกัน/มีปีเทอม/รหัสวิชา/ไม่เจอชื่อกลุ่ม/ชื่อวิชายาวกว่าชื่อกลุ่ม (ถามเรื่องวิชานั้น) = None (ทางเดิม)"""
    if _GROUP_NOT.search(question) or _CODE8.search(question) or not re.search(r"กลุ่ม|วิชาเลือก", question):
        return None
    intents = [name for name, rx in (("list", _GROUP_LIST), ("count", _GROUP_COUNT), ("credits", _GROUP_CREDITS)) if rx.search(question)]
    if len(intents) != 1:
        return None
    try:
        groups = [dict(r) for r in conn.execute(
            "SELECT DISTINCT group_no, group_name_th, credits_required FROM main.v_elective_group "
            "WHERE plan_slot NOT LIKE 'หมวดวิชาศึกษาทั่วไป%' AND group_name_th IS NOT NULL")]
    except sqlite3.OperationalError:
        return None
    norm = lambda s: re.sub(r"\s+", "", s or "").lower()
    qn = norm(question)
    hits = []
    key_of = lambda g: re.sub(r"^กลุ่ม", "", norm(g["group_name_th"]))
    for g in groups:
        key = key_of(g)
        core = re.sub(r"กลุ่ม|วิชาเลือก|วิชา|เลือก", "", key)             # ชื่อกลุ่มกว้าง ๆ เช่น "กลุ่มวิชาเลือก" ไม่ใช่ชื่อกลุ่มที่เจาะจง
        if len(key) >= 8 and len(core) >= 4 and key in qn:
            hits.append((len(key), g))
    if not hits:
        return None
    best = max(n for n, _ in hits)
    top = [g for n, g in hits if n == best]
    if len({(g["group_no"], g["group_name_th"]) for g in top}) != 1:
        return None
    g = top[0]
    named = _named_courses(conn, question, strict=False)       # มีวิชาชื่อยาวเท่ากันหรือยาวกว่า/เท่ากับชื่อกลุ่ม (วิชาเดี่ยวที่ชื่อเหมือนกลุ่ม) = ถามเรื่องวิชานั้น
    explicit = re.search(r"กลุ่ม(?:วิชาเลือก|วิชา)?" + re.escape(key_of(g)), qn)             # "กลุ่ม(วิชา)<ชื่อกลุ่ม>" ติดกัน = ถามกลุ่มแน่นอน
    if named and max(len(norm(n)) for n in named.values()) >= best and not explicit:
        return None
    if not re.search(r"กลุ่ม", question) and "วิชาเลือก" not in key_of(g):
        return None
    try:
        members = [dict(r) for r in conn.execute(
            "SELECT DISTINCT code, course_name_th AS name_th, credits FROM main.v_elective_group WHERE group_no = ? AND group_name_th = ? ORDER BY code",
            (g["group_no"], g["group_name_th"]))]
    except sqlite3.OperationalError:
        return None
    sql = f"SELECT DISTINCT code, course_name_th, credits FROM main.v_elective_group WHERE group_name_th = '{g['group_name_th']}' ORDER BY code"
    if intents[0] == "list":
        return f"{g['group_name_th']} มี {len(members)} วิชา: " + ", ".join(f"{r['code']} {r['name_th']}" for r in members), members, sql
    if intents[0] == "count":
        return f"{g['group_name_th']} มี {len(members)} วิชา", [{"group": g["group_name_th"], "n_courses": len(members)}], sql
    if g["credits_required"] is None:
        return None
    return (f"{g['group_name_th']} ต้องเลือกรวม {g['credits_required']} หน่วยกิต", [{"group": g["group_name_th"], "credits_required": g["credits_required"]}], sql)


_SEM_HALF = ((r"(?:ภาคการศึกษา|ภาคเรียน|ภาค|เทอม)ต้น", "ภาคการศึกษาที่ 1 "), (r"(?:ภาคการศึกษา|ภาคเรียน|ภาค|เทอม)ปลาย", "ภาคการศึกษาที่ 2 "))


def _strip_own_program_token(conn: sqlite3.Connection, question: str) -> str:
    """ตัดชื่อหลักสูตรของแผนที่เลือกอยู่ (DSBA/AIT/BIT/IT ตัวพิมพ์ใหญ่) ออกจากข้อความที่ส่งให้ทางลัด/โมเดล — เป็นคำของ "ผู้ถาม" ไม่ใช่ส่วนของชื่อวิชา
    ("สหกิจศึกษา BIT เรียนกี่หน่วยกิต" เดิมชื่อวิชามี BIT ต่อท้ายจึงไม่เข้าทางลัดแล้วโมเดลตอบ 18); ชื่อหลักสูตรอื่นไม่ตัด (ให้ _other_program_answer ดัก)"""
    try:
        row = conn.execute("SELECT program_id FROM program LIMIT 1").fetchone()
    except sqlite3.Error:
        return question
    mine = (re.match(r"[A-Za-z]+", (row[0] or "")) or [None])[0] if row else None
    if not mine or mine.upper() not in ("DSBA", "AIT", "BIT", "IT"):
        return question
    out = re.sub(rf"(?:ของ|ใน)?\s*(?<![A-Za-z]){re.escape(mine.upper())}(?![A-Za-z])", " ", question)
    return re.sub(r" {2,}", " ", out).strip() if out != question else question


def _drop_redundant_codes(conn: sqlite3.Connection, question: str) -> str:
    """"แนวคิดระบบฐานข้อมูล (06066300)" -> "แนวคิดระบบฐานข้อมูล": ตัดรหัสที่ซ้ำชื่อวิชาซึ่งเขียนติดอยู่ข้างหน้า (ชื่อไทย/อังกฤษของวิชานั้นเอง) เพื่อให้ทางลัดแบบชื่อทำงานได้;
    รหัสที่ไม่มีชื่อวิชานั้นนำหน้า = ไม่แตะ ("รหัสวิชา 06026201 ชื่ออะไร" ยังใช้รหัส)"""
    if not _CODE8.search(question):
        return question
    try:
        info = {r[0]: (r[1] or "", r[2] or "") for r in conn.execute("SELECT code, name_th, name_en FROM course")}
    except sqlite3.OperationalError:
        return question

    def sub(mt: re.Match) -> str:
        code = mt.group(1)
        th, en = info.get(code, ("", ""))
        before = question[:mt.start()]
        ok = (th and len(_name_key(th)) >= 4 and _name_key(before).endswith(_name_key(th))) or              (en and len(en) >= 4 and re.sub(r"\s+", "", before.upper()).endswith(re.sub(r"\s+", "", en.upper())))
        return " " if ok else mt.group(0)
    out = re.sub(r"\(?\s*(?<!\d)(\d{8})(?!\d)\s*\)?", sub, question)
    return re.sub(r" {2,}", " ", out).strip() if out != question else question


# ---- ชื่อแผน (สหกิจ / ไม่สหกิจ) ที่ระบุในคำถาม: ตัดเมื่อตรงกับแผนของ DB นี้, ส่งไปตอบจากแผนคู่เมื่อถามถึงอีกแผน ----
_COOP_PLAN_PHRASE = re.compile(r"\(?\s*(?<!ไม่)(?<!ตาม)(?:แผน|แบบ|หลักสูตร)(?:ที่)?(?:เข้า|มี|ทำ)?สหกิจ(?:ศึกษา)?\s*\)?")
_NOCOOP_PLAN_PHRASE = re.compile(r"\(?\s*(?<!ตาม)(?:(?:แผน|แบบ|หลักสูตร)(?:ที่)?)?ไม่(?:เข้า|มี|ทำ|เป็น|ใช่)?(?:แผน)?สหกิจ(?:ศึกษา)?\s*\)?|\(?\s*แผน(?:ปกติ|ทั่วไป)\s*\)?")


def _own_plan(conn: sqlite3.Connection) -> str | None:
    where = _sibling_plan_db(conn)
    return where[0] if where else None


def _requested_plan(question: str) -> str | None:
    """"coop"/"no_coop" เมื่อคำถามพูดถึงแผนเดียวชัดเจน (แผนสหกิจ / แผนไม่สหกิจ) — พูดถึงสองแผน/ไม่พูดถึง = None; ชื่อวิชา "สหกิจศึกษา" เฉย ๆ ไม่นับ"""
    no = bool(_NOCOOP_PLAN_PHRASE.search(question))
    co = bool(_COOP_PLAN_PHRASE.search(_NOCOOP_PLAN_PHRASE.sub(" ", question)))
    return None if no == co else ("coop" if co else "no_coop")


def _strip_own_plan_phrase(conn: sqlite3.Connection, question: str) -> str:
    own = _own_plan(conn)
    if own is None or _requested_plan(question) != own:
        return question
    out = (_COOP_PLAN_PHRASE if own == "coop" else _NOCOOP_PLAN_PHRASE).sub(" ", question)
    return re.sub(r" {2,}", " ", out).strip()


def _prepare_question(conn: sqlite3.Connection, question: str) -> str:
    """ข้อความที่ทางลัด/โมเดลเห็น: ตัดชื่อหลักสูตรและชื่อแผน (สหกิจ/ไม่สหกิจ) ของแผนตัวเอง, ตัดรหัสที่ซ้ำชื่อวิชา, แปลงภาคต้น/ปลาย
    (result["question"] ยังเป็นข้อความเดิมของผู้ใช้)"""
    q = _strip_own_plan_phrase(conn, _strip_own_program_token(conn, question))
    return _normalise_semester_words(_drop_redundant_codes(conn, q))


def _normalise_semester_words(question: str) -> str:
    """"ภาคต้น/เทอมต้น" = ภาคการศึกษาที่ 1, "ภาคปลาย/เทอมปลาย" = ภาคการศึกษาที่ 2 (โมเดลเคยตีเป็น semester 3 = ภาคฤดูร้อน แล้วตอบ "ไม่พบ")"""
    out = question
    for rx, repl in _SEM_HALF:
        out = re.sub(rx, repl, out)
    return re.sub(r" {2,}", " ", out).strip() if out != question else question


# ---- 15. ผลชุดคำถามหลอก (subagent): ปฏิเสธวิชาที่ไม่มีจริง, ผลรวมรายปี, ภาคฤดูร้อน, เทอมเดียวกับ X, เลือกหรือบังคับ, สองวิชา ----
_NOT_FOUND_TEXT = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"
_NOT_FOUND = (_NOT_FOUND_TEXT, [], "SELECT NULL WHERE 0")
_UNKNOWN_ATTR_Q = re.compile(r"หน่วยกิต|รหัส|ชั่วโมง|ปีไหน|เทอมไหน|ภาคไหน|ชื่อ(?:ภาษา)?อังกฤษ|เรียนเกี่ยวกับอะไร|สอนอะไร|สอนเกี่ยวกับ|ต้องผ่านอะไร|บังคับก่อน|เรียนอะไรมาก่อน")
# ตัวขยายที่ทำให้ชื่อวิชากลายเป็น "วิชาอื่น" (ชื่อยาวกว่าที่ไม่มีใน DB) — ติดหน้า/หลังชื่อวิชาที่รู้จัก
_NAME_MODIFIERS = ("ขั้นสูง", "ขั้นกลาง", "ขั้นต้น", "ปฏิบัติการ", "ภาคปฏิบัติ", "ภาคทฤษฎี", "ประยุกต์", "เชิง", "พิเศษ", "ต่างประเทศ", "เฉพาะทาง",
                   "เพิ่มเติม", "ระดับสูง", "ระดับกลาง")


def _unknown_course_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ถามค่าของ "วิชาที่ไม่มีในเล่ม" แต่มีชื่อวิชาจริงที่สั้นกว่าอยู่ข้างใน → ตอบ "ไม่พบ" ตรง ๆ (โมเดลเคยหยิบวิชาสั้นมาตอบ):
    (ก) ชื่อวิชาที่รู้จักมีตัวขยายติดอยู่ (ขั้นสูง/ปฏิบัติการ/เชิง…/ต่างประเทศ) และไม่มีชื่อเต็มอื่นในคำถาม
    (ข) ชื่อลงท้ายด้วยเลขลำดับ ("ภาษาอังกฤษพื้นฐาน 3") แต่ DB มีลำดับอื่น (1, 2) ไม่มีลำดับที่ถาม
    ใช้เฉพาะคำถามค่าของวิชา (หน่วยกิต/รหัส/ชั่วโมง/ปี/เทอม/เนื้อหา/วิชาบังคับก่อน); คำถามเชิงความสัมพันธ์/หลายวิชา = None"""
    if not _UNKNOWN_ATTR_Q.search(question) or _RELATIONAL_NOT.search(question) or re.search(r"และ|กับ|,|&", question) and re.search(r"\d\s*(?:และ|กับ|,|&)\s*\d", question):
        return None
    if _named_courses(conn, question):                          # มีชื่อเต็มของวิชาที่รู้จัก → ไม่ใช่กรณีนี้
        return None
    try:
        pairs = [(r[0], r[1] or "", r[2] or "") for r in conn.execute("SELECT code, name_th, name_en FROM course")]
        pairs += [(r[0], r[1] or "", r[2] or "") for r in conn.execute("SELECT code, course_name_th, course_name_en FROM main.v_elective_group")]
    except sqlite3.OperationalError:
        return None
    qn = _name_key(question)
    known = {_name_key(n) for _c, th, en in pairs for n in (th, en) if n}
    for key in known:
        if len(key) < 5 or key not in qn:
            continue
        for mt in re.finditer(re.escape(key), qn):
            pre, suf = qn[: mt.start()], qn[mt.end():]
            if any(suf.startswith(_name_key(w)) for w in _NAME_MODIFIERS) or any(pre.endswith(_name_key(w)) for w in _NAME_MODIFIERS):
                return _NOT_FOUND
    for key in known:                                           # (ข) ลำดับที่ไม่มี: ชื่อ "stem + เลข" ที่ stem มีจริงกับลำดับอื่น
        mt0 = re.fullmatch(r"(.{5,}?)(\d+)", key)
        if not mt0:
            continue
        stem = mt0.group(1)
        for mt in re.finditer(re.escape(stem) + r"(\d+)", qn):
            if (stem + mt.group(1)) not in known and _NAME_PREFIX_OK.search(qn[: mt.start()]):
                return _NOT_FOUND
    return None


_YEAR_TOTAL_NOT = re.compile(r"เทอม|ภาค|วิชา|เฉลี่ย|ต่อ|มาก|น้อย|กี่วิชา|ที่ได้|ก่อน")


def _year_credits_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """หน่วยกิตรวมของ "ปีเดียว" ("ปี 1 เรียนรวมกี่หน่วยกิต", "ปีแรก…", "ปีสุดท้าย…") = ผลรวมยอดรายเทอมตามเล่ม (v_semester_credits_full);
    มีเทอม/ภาค/วิชา/หลายปี/ชื่อวิชา/รหัส = None"""
    if "หน่วยกิต" not in question or _YEAR_TOTAL_NOT.search(question) or _CODE8.search(question) or _RELATIONAL_NOT.search(question):
        return None
    if not re.search(r"รวม|ทั้งหมด|เรียนกี่|ต้องเรียน|กี่หน่วยกิต|เท่าไร|เท่าไหร่", question):
        return None
    digits = re.findall(r"ปี(?:ที่)?\s*(\d)", question)
    first, last = "ปีแรก" in question, "ปีสุดท้าย" in question
    if len(digits) + first + last != 1 or re.search(r"ปี(?:ที่)?\s*\d\s*(?:และ|กับ|,|-|–|ถึง)", question) or _named_courses(conn, question, strict=False):
        return None
    try:
        rows = [dict(r) for r in conn.execute("SELECT year, SUM(credits) AS credits FROM main.v_semester_credits_full GROUP BY year ORDER BY year")]
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None
    year = int(digits[0]) if digits else (1 if first else max(r["year"] for r in rows))
    row = next((r for r in rows if r["year"] == year), None)
    if row is None or row["credits"] is None:
        return None
    return f"ปี {year} เรียนรวม {row['credits']} หน่วยกิต", [{"year": year, "credits": row["credits"]}], \
        f"SELECT year, SUM(credits) AS credits FROM main.v_semester_credits_full WHERE year = {year} GROUP BY year"


def _summer_term_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """ถามภาคฤดูร้อน/ซัมเมอร์ ทั้งที่แผนไม่มีภาคที่ 3 เลย → "ไม่พบ" (โมเดลเคยตอบหน่วยกิตของเทอมอื่น); แผนมีภาค ≥ 3 = None (ทางเดิม)"""
    if not re.search(r"ฤดูร้อน|ซัมเมอร์|summer", question, re.I) or not re.search(r"หน่วยกิต|วิชา|ลงทะเบียน|เรียน", question) or _RELATIONAL_NOT.search(question):
        return None
    try:
        sems = [r[0] for r in conn.execute("SELECT DISTINCT semester FROM plan_item")]
    except sqlite3.OperationalError:
        return None
    if not sems or any(s is None or s >= 3 for s in sems):
        return None
    return _NOT_FOUND


def _same_term_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """"เทอมเดียวกับ X มีวิชาอะไรอีกบ้าง" → วิชาอื่นในเทอมเดียวกับ X (X ต้องอยู่ในแผนที่เดียว); หน่วยกิต/ชั่วโมง/สองวิชา = None"""
    if "เดียวกับ" not in question or not re.search(r"อะไรอีก|อีกบ้าง|วิชาอะไร|วิชาไหน|อะไรบ้าง|มีวิชา", question) or re.search(r"หน่วยกิต|ชั่วโมง|ปีไหน|ต่อจาก", question):
        return None
    named = _named_courses(conn, re.sub(r"(?:เทอม|ภาคเรียน|ภาคการศึกษา|ภาค|ปี)?เดียวกับ", " ", question), catalog=False, relational_ok=True)
    if not named or len(named) != 1:
        return None
    code = next(iter(named))
    try:
        places = [tuple(r) for r in conn.execute("SELECT DISTINCT year, semester FROM plan_item WHERE code = ?", (code,))]
        if len(places) != 1:
            return None
        y, sm = places[0]
        rows = [dict(r) for r in conn.execute(
            "SELECT DISTINCT p.code, c.name_th, p.credits FROM plan_item p LEFT JOIN course c ON c.code = p.code "
            "WHERE p.year = ? AND p.semester = ? AND p.code != ? ORDER BY p.code", (y, sm, code))]
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None
    return (f"เทอมเดียวกับ {code} {named[code]} (ปี {y} เทอม {sm}) มีอีก {len(rows)} วิชา: " + ", ".join(f"{r['code']} {r['name_th']}" for r in rows), rows,
            f"SELECT DISTINCT code FROM plan_item WHERE year = {y} AND semester = {sm} AND code != '{code}' ORDER BY code")


_KIND_Q = re.compile(r"เลือกหรือ(?:เป็น)?(?:วิชา)?บังคับ|บังคับหรือ(?:เป็น)?(?:วิชา)?เลือก|เป็นวิชา(?:บังคับ|เลือก)(?:หรือไม่|ไหม|หรือเปล่า)")


def _course_kind_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """"X เป็นวิชาเลือกหรือบังคับ" → จากหมายเหตุช่องในแผน (plan_item.note: "… | บังคับ/เลือก") ของวิชาในแผน; หลายค่าขัดกัน/ไม่มีหมายเหตุ/ถามหลายอย่าง = None"""
    if not _KIND_Q.search(question) or re.search(r"หน่วยกิต|ชั่วโมง|รหัส|ปีไหน|เทอมไหน|กลุ่ม", question):
        return None
    named = _named_courses(conn, question, catalog=False)
    if not named or len(named) != 1:
        return None
    code = next(iter(named))
    try:
        notes = [r[0] for r in conn.execute("SELECT note FROM plan_item WHERE code = ?", (code,))]
    except sqlite3.OperationalError:
        return None
    kinds = {mt.group(1) for n in notes for mt in [re.search(r"\|\s*(บังคับ|เลือกเสรี|เลือก)\s*$", n or "")] if mt}
    if len(kinds) != 1 or len(notes) != len([n for n in notes if n]):
        return None
    kind = next(iter(kinds))
    return (f"{code} {named[code]} เป็นวิชา{kind}", [{"code": code, "name_th": named[code], "kind": kind}],
            f"SELECT code, note FROM plan_item WHERE code = '{code}'")


_MULTI_NOT = re.compile(r"ต่างกัน|เปรียบเทียบ|เหมือนกัน|เกี่ยวกับอะไร|สอนอะไร|ก่อน|หลัง|ต่อจาก|ชั่วโมง|ชื่อ")
_MULTI_TAIL = re.compile(r"รวม|กัน|กี่|หน่วยกิต|รหัส|วิชา|เรียน|ปีไหน|เทอมไหน|ภาคไหน|คือ|อะไร|ของ|ขอ|ครับ|ค่ะ|นะ|หน่อย|มี|ทั้งหมด|เท่าไร|เท่าไหร่|เป็น|ใช้|อยู่|ได้|ที่")


def _expand_name_range(conn: sqlite3.Connection, question: str) -> str:
    """"โครงงานกลุ่ม 1 ถึง 3" -> "โครงงานกลุ่ม 1 และ 2 และ 3" เมื่อ "ชื่อ + เลขแรก" และ "ชื่อ + เลขสุดท้าย" เป็นวิชาจริง (ช่วงไม่เกิน 5 วิชา); ไม่ใช่ = เดิม"""
    mt = re.search(r"([^\d]{4,}?)\s*(\d+)\s*(?:ถึง|-|–)\s*(\d+)(?!\d)", question)
    if not mt:
        return question
    stem, a, b = mt.group(1).strip(), int(mt.group(2)), int(mt.group(3))
    if not (a < b <= a + 4) or any(_named_courses(conn, f"{stem} {n}", catalog=False) is None for n in (a, b)):
        return question
    return question[:mt.start()] + f"{stem} " + " และ ".join(str(n) for n in range(a, b + 1)) + question[mt.end():]


def _multi_course_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """สองถึงสี่วิชาในคำถามเดียว ("X 1 และ 2", "X กับ Y") ถามค่าเดียวกัน: หน่วยกิต (+ผลรวมเมื่อ "รวม") / รหัส / ปีเทอม — ตอบทุกวิชา;
    ทุกส่วนต้องระบุวิชาได้ชัดเจน (ชื่อเต็ม/ลำดับต่อจากชื่อก่อนหน้า) ไม่เช่นนั้น = None; เปรียบเทียบ/เนื้อหา/ชั่วโมง = None"""
    if _MULTI_NOT.search(question) or _RELATIONAL_NOT.search(question) or _CODE8.search(question):
        return None
    question = _expand_name_range(conn, question)               # "X 1 ถึง 3" -> "X 1 และ 2 และ 3"
    wants = [k for k, rx in (("credits", r"หน่วยกิต"), ("code", r"รหัส"), ("place", r"ปีไหน|เทอมไหน|ภาคไหน")) if re.search(rx, question)]
    if len(wants) != 1:
        return None
    segs = [x.strip() for x in re.split(r"และ|กับ|,|&", question)]
    if len(segs) < 2:
        return None
    found: list[tuple[str, str]] = []
    prev_stem = None
    for seg in segs:
        nm = re.match(r"(\d+)(?!\d)", seg)
        if nm and prev_stem:
            named = _named_courses(conn, prev_stem + nm.group(1), catalog=False)
        else:
            named = _named_courses(conn, seg, catalog=False)
        if named and len(named) == 1:
            code, name = next(iter(named.items()))
            found.append((code, name))
            prev_stem = re.sub(r"\s*\d+\s*$", "", name) + " " if re.search(r"\d\s*$", name) else None
        elif _MULTI_TAIL.sub("", _strip_punct(seg)):    # ส่วนที่ไม่ใช่ชื่อวิชาและมีคำอื่นนอกจากคำถาม = ไม่แน่ใจ
            return None
    if not (2 <= len({c for c, _ in found}) <= 4):
        return None
    found = list(dict.fromkeys(found))
    codes = [c for c, _ in found]
    ids = ", ".join(f"'{c}'" for c in codes)
    if wants[0] == "code":
        return "; ".join(f"{n} = {c}" for c, n in found), [{"code": c, "name_th": n} for c, n in found], f"SELECT code, name_th FROM course WHERE code IN ({ids})"
    try:
        if wants[0] == "credits":
            cr = {r[0]: r[1] for r in conn.execute(f"SELECT code, credits FROM course WHERE code IN ({ids})")}
            if len(cr) != len(codes) or any(v is None for v in cr.values()):
                return None
            text = "; ".join(f"{c} {n}: {cr[c]} หน่วยกิต" for c, n in found)
            rows = [{"code": c, "name_th": n, "credits": cr[c]} for c, n in found]
            if re.search(r"รวม|ทั้งหมด", question):
                text += f" — รวม {sum(cr.values())} หน่วยกิต"
                rows.append({"total_credits": sum(cr.values())})
            return text, rows, f"SELECT code, credits FROM course WHERE code IN ({ids})"
        parts, rows = [], []
        for c, n in found:
            places = [tuple(r) for r in conn.execute("SELECT DISTINCT year, semester FROM plan_item WHERE code = ? ORDER BY year, semester", (c,))]
            if not places:
                return None
            parts.append(f"{c} {n}: " + " และ ".join(f"ปี {y} เทอม {s}" for y, s in places))
            rows += [{"code": c, "name_th": n, "year": y, "semester": s} for y, s in places]
        return "; ".join(parts), rows, f"SELECT code, year, semester FROM plan_item WHERE code IN ({ids})"
    except sqlite3.OperationalError:
        return None


def _strip_punct(text: str) -> str:
    """ลบช่องว่าง ตัวเลข และเครื่องหมายวรรคตอน — ไม่ใช้คลาสตัวอักษร non-word เพราะลบสระ/วรรณยุกต์ไทยทิ้งด้วย"""
    return re.sub(r"[\s\d.,;:!?()\[\]{}\"'\-–—/&|]+", "", text)


_TERM_TOTAL_NOT = re.compile(r"อะไรบ้าง|รหัส|ชื่อ|ชั่วโมง|ก่อน|มาก|น้อย|เฉลี่ย|วิชาไหน|วิชาอะไร|ที่ได้|ที่มี\s*\d|และ|กับ|เท่ากับ|ต่อ|เลือก")


# คำที่ประกอบเป็นคำถามยอดรายเทอมได้ — มีคำอื่นเหลือ (ชื่อวิชา ฯลฯ) = ปฏิเสธ
_TERM_TOTAL_WORDS = re.compile(r"ในแผนการศึกษา|แผนการศึกษา|ชั้นปีที่|ปีการศึกษา|ภาคการศึกษาที่|ภาคเรียนที่|ภาคการศึกษา|ภาคเรียน|ปีที่|เทอมที่|เทอม|ภาค|ปี|ที่|ของ|มี|ต้อง|ลงทะเบียน|"
                               r"เรียน|รวม|ทั้งหมด|กี่|รายวิชา|วิชา|หน่วยกิต|จำนวน|เท่าไร|เท่าไหร่|เป็น|ใน|ครับ|ค่ะ|นะ|หน่อย|คือ|ขอ|ทราบ|บอก|ได้|กัน|จะ|ต้องการ|อยาก")


def _term_total_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """"ปี Y เทอม S ต้องลงทะเบียนกี่วิชา" / "…รวมกี่หน่วยกิต" (ปี/เทอมเดียว) → ยอดรายเทอมตามเล่ม (v_semester_credits_full: ช่อง "เลือก 1 กลุ่ม" นับครั้งเดียว,
    ช่องเลือกเสรีนับ) — นิยามเดียวกับที่ทางโมเดลใช้ แต่ตายตัว (โมเดลเคยแกว่ง 1 ใน ~160 ครั้ง); ถามรายการ/สองอย่างพร้อมกัน/หลายเทอม/ชื่อวิชา/เทอมที่ไม่มีในแผน = None"""
    both_q = bool(re.search(r"กี่วิชา|กี่รายวิชา|จำนวนวิชา|จำนวนรายวิชา", question)) and "หน่วยกิต" in question
    chk = re.sub(r"(?:และ|แล้ว)\s*(?=รวม|กี่หน่วยกิต|หน่วยกิต)", "", question) if both_q else question      # "กี่วิชา แล้วรวมกี่หน่วยกิต" = ถามสองค่า ไม่ใช่คำถามเชิงเปรียบเทียบ
    if _TERM_TOTAL_NOT.search(chk) or _CODE8.search(question) or _RELATIONAL_NOT.search(question):
        return None
    if _TERM_TOTAL_WORDS.sub("", _strip_punct(chk)):    # เหลือคำไทยที่ไม่ใช่คำของคำถามยอดรายเทอม (เช่น ชื่อวิชา) = ไม่ใช่คำถามนี้
        return None
    years, sems = _TERM_YEAR_NUM.findall(question), _TERM_SEM_NUM.findall(question)
    if len(years) != 1 or len(sems) != 1:
        return None
    count_q = bool(re.search(r"กี่วิชา|กี่รายวิชา|จำนวนวิชา|จำนวนรายวิชา", question))
    credit_q = "หน่วยกิต" in question
    if re.search(r"อะไรบ้าง|วิชาอะไร|เรียนอะไร|ลงอะไร|มีอะไร|ลงวิชา|รหัสวิชา|ต้องเรียนอะไร|วิชาไหน", question):     # ขอ "รายวิชา" ด้วย = คำถามควบ: ไม่ตอบแค่ยอด (เดิมทิ้งส่วนรายวิชาเงียบ ๆ) ปล่อยให้ทางโมเดล+สรุปเทอม (_term_summary_hint_text) ตอบทั้งสองส่วน
        return None
    if (not count_q and not credit_q) or _named_courses(conn, question, strict=False):
        return None
    y, sm = int(years[0]), int(sems[0])
    try:
        row = conn.execute("SELECT credits, n_entries FROM main.v_semester_credits_full WHERE year = ? AND semester = ?", (y, sm)).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None or row[0] is None or row[1] is None:
        return None
    where = f"WHERE year = {y} AND semester = {sm}"
    if count_q and credit_q:                                  # ถามจำนวนวิชาและหน่วยกิตรวมพร้อมกัน (เดิมโมเดลตอบ "1 วิชา")
        return (f"ปี {y} เทอม {sm} มี {row[1]} วิชา รวม {row[0]} หน่วยกิต", [{"n_courses": row[1], "credits": row[0]}],
                f"SELECT n_entries AS n_courses, credits FROM main.v_semester_credits_full {where}")
    if count_q:
        return (f"ปี {y} เทอม {sm} ต้องลงทะเบียน {row[1]} วิชา", [{"n_courses": row[1]}],
                f"SELECT n_entries AS n_courses FROM main.v_semester_credits_full {where}")
    return (f"ปี {y} เทอม {sm} รวม {row[0]} หน่วยกิต", [{"credits": row[0]}], f"SELECT credits FROM main.v_semester_credits_full {where}")


_YEAR_CITE_MAX = 4                                          # 4 เทอมของ 2 ปี = หน้าตารางแผนได้ถึง 4 หน้า (เพดานปกติ 3 หน้าตัดทิ้งหนึ่งหน้า)


_YEAR_WORDS = re.compile(r"ปีแรก|ปีสุดท้าย|ปีหนึ่ง|ปีสอง|ปีสาม|ปีสี่|ปีที่หนึ่ง|ปีที่สอง|ปีที่สาม|ปีที่สี่")


def _question_years(question: str) -> set[int]:
    """ปีที่ระบุในคำถาม: "ปี 1", "ปี 1 กับปี 2", "ปี 1 และ 3", "ปี 1, 2 และ 4", "ชั้นปีที่ 1–2", "ปี 1 ถึงปี 3" (ไม่มีปี = ว่าง)"""
    years: set[int] = set()
    for grp in re.findall(r"ปี(?:ที่)?\s*(\d(?:\s*(?:และ|กับ|,|&)\s*(?:ปี(?:ที่)?\s*)?\d)*)", question):
        years |= {int(d) for d in re.findall(r"\d", grp)}
    for a, b in re.findall(r"ปี(?:ที่)?\s*(\d)\s*(?:ถึง|-|–|ไปจนถึง)\s*(?:ปี(?:ที่)?\s*)?(\d)", question):
        years |= set(range(int(a), int(b) + 1))
    return years


def _prereq_pair_pages(conn: sqlite3.Connection) -> list[dict]:
    """หน้าคำอธิบายรายวิชา (kind='description') ของวิชาที่มีแถวใน prerequisite — ไม่มีหน้าเดียวที่ระบุทั้งคำตอบ จึงอ้างหน้าที่
    มาของคู่เหล่านั้น (ไม่จำกัดจำนวนหน้า เพื่อให้ไม่มีวิชาตกหล่น เรียงตามหน้า); ไม่มีหน้า/ไม่มีตาราง = [] (ไม่เดา)"""
    try:
        got = conn.execute("SELECT cp.pdf_page, cp.printed_page, cp.code FROM course_page cp "
                           "WHERE cp.kind = 'description' AND cp.code IN (SELECT code FROM prerequisite) "
                           "ORDER BY cp.pdf_page, cp.code").fetchall()
    except sqlite3.OperationalError:
        return []
    by_page: dict[tuple, list[str]] = {}
    for pdf, printed, code in got:
        by_page.setdefault((pdf, printed), []).append(code)
    return [{"pdf_page": p, "printed_page": pr, "courses": codes}
            for (p, pr), codes in by_page.items()]


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
        citations.add_course_names(conn, result["citations"])
        result["citation_text"] = citations.format_citation(result["citations"])
        return
    lookup = citations.load_lookup(conn)
    if lookup is not None:
        result["citations"] = citations.citations_for(result["rows"], result["sql"], lookup)
        if not result["citations"] and result["rows"]:       # นับ/รวมตามปี ("ปี 1 กับปี 2 มีกี่วิชา"): ไม่มีรหัสวิชาในผล → อ้างหน้าตารางแผนของปีที่ถาม
            years = _question_years(str(result.get("question") or ""))
            pages = sorted({p for (y, _s), ps in lookup[1].items() if y in years for p in ps})
            result["citations"] = [{"pdf_page": p, "printed_page": pr, "courses": []} for p, pr in pages[:_YEAR_CITE_MAX]]
        if not result["citations"] and result["rows"] and re.search(r"\bFROM\s+prerequisite\b", result["sql"] or "", re.I):
            result["citations"] = _prereq_pair_pages(conn)   # นับคู่วิชาบังคับก่อนทั้งเล่ม: อ้างหน้าคำอธิบายรายวิชาที่พิมพ์บรรทัดวิชาบังคับก่อน
        citations.add_course_names(conn, result["citations"])
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


# ---- นับคู่วิชาบังคับก่อน "ทั้งหมด" — โมเดลเคยตีความ "ต่อเนื่อง/เงื่อนไข" เป็นวิชาเรียนควบ (kind='co') แล้วตอบ 0 ----
_PAIR_WORD = re.compile(r"กี่คู่|กี่ความสัมพันธ์|กี่เงื่อนไข|จำนวนคู่|คู่วิชา")
_PAIR_PREREQ = re.compile(r"บังคับก่อน|ต้อง(?:เรียน|ผ่าน)(?:วิชา)?(?:อื่น)?(?:ใด)?ก่อน|เงื่อนไข(?:ต้อง)?เรียนก่อน|prerequisite", re.I)
# ขอบเขตอื่น/คำถามอื่น: เรียนควบ ต่อเนื่อง ขอรายชื่อ ไม่มี ถามจำนวนวิชา (ไม่ใช่คู่) เปรียบเทียบ ค่าสูงสุด ฯลฯ → ปฏิเสธ
_PAIR_NOT = re.compile(r"ควบ|ต่อเนื่อง|ต่อยอด|หรือ|ไม่มี|ไม่ผ่าน|ไม่ได้|บ้าง|รายชื่อ|รายการ|ลิสต์|คู่ไหน|วิชาไหน|วิชาอะไร|อะไร|"
                       r"มากที่สุด|น้อยที่สุด|มากสุด|น้อยสุด|ที่สุด|ต่างกัน|เท่ากับ|เทียบ|กับ|และ|แต่ละ|เฉลี่ย|กี่วิชา|กี่ตัว|กี่รายวิชา|"
                       r"ปี|เทอม|ภาค|สหกิจ|ฤดูร้อน|เลือก|GE|ทั่วไป")


def _prereq_pair_count_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """"มีวิชาบังคับก่อนทั้งหมดกี่คู่" (ทั้งเล่ม ไม่ระบุปี/เทอม/วิชา) = COUNT(*) ของ prerequisite kind='pre' — ตามที่ตาราง prerequisite เก็บ
    (แถวละคู่ รหัสวิชา+รหัสวิชาบังคับก่อน; "A หรือ B" นับเป็นสองแถว); ต้องมีทั้งคำว่า "คู่/ความสัมพันธ์" และวิชาบังคับก่อน
    มีรหัส/ชื่อวิชา(ไม่ใช้ _RELATIONAL_NOT เพราะมันจับ "วิชาอื่น…ก่อน" ซึ่งเป็นสำนวนปกติของคำถามนี้)/ปี/เทอม/เรียนควบ/ต่อเนื่อง/ขอรายชื่อ/ไม่มี/ถามจำนวนวิชา = None (ไม่เดา)"""
    if not (_PAIR_WORD.search(question) and _PAIR_PREREQ.search(question)):
        return None
    rest = _PAIR_PREREQ.sub("", question).replace("คู่วิชากับ", "")
    if _CODE8.search(question) or _PAIR_NOT.search(rest) or _named_courses(conn, question, strict=False):
        return None
    try:
        n = conn.execute("SELECT COUNT(*) FROM prerequisite WHERE kind = 'pre'").fetchone()[0]
    except sqlite3.OperationalError:
        return None
    return f"{n} คู่วิชากับวิชาบังคับก่อนทั้งหมด", [{"pairs": n}], "SELECT COUNT(*) AS pairs FROM prerequisite WHERE kind = 'pre'"


# ---- "ต่อเนื่อง" กำกวม (วิชาบังคับก่อน หรือ วิชาเรียนควบ?) และวิชาเรียนควบ — ไม่เดา ----
# ตาราง prerequisite ไม่มีแถว kind='co' เลยทั้ง 7 แผน (ตัวสกัดใส่แต่ 'pre') → "0 วิชาเรียนควบ" แปลว่าไม่ได้สกัด ไม่ใช่เล่มไม่มี จึงห้ามตอบ 0
_CONT_Q = re.compile(r"(?<!ไม่)ต่อเนื่อง")
_CONT_PAIR = re.compile(r"คู่|ความสัมพันธ์|เงื่อนไข")
_COREQ_Q = re.compile(r"(?:เรียน|ลงทะเบียน(?:เรียน)?|วิชา)\s*ควบ(?!คุม)|ควบคู่|ควบกับ|ควบกัน")
_AMBIGUOUS_TEXT = ("คำถามนี้ตีความได้สองแบบ: วิชาบังคับก่อน (ต้องผ่านวิชาหนึ่งก่อนจึงเรียนอีกวิชาได้) หรือวิชาเรียนควบ "
                   "(ต้องลงทะเบียนเรียนพร้อมกัน) — กรุณาระบุให้ชัดว่าหมายถึงแบบไหน")


def _prereq_ambiguity_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """(ก) "วิชาที่ต้องเรียนต่อเนื่องกันกี่คู่" (ไม่มีคำว่าบังคับก่อน) = ถามกลับว่าหมายถึงวิชาบังคับก่อนหรือวิชาเรียนควบ (ไม่ใส่ตัวเลขในคำตอบ)
    (ข) คำถามวิชาเรียนควบ = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร" (ไม่ตอบ 0); มีรหัสวิชา/ชื่อวิชา/ปี-เทอม (เช่นวิชา "คณิตศาสตร์ไม่ต่อเนื่อง") = None"""
    if _CODE8.search(question) or _named_courses(conn, question, strict=False) or _term_numbers(question) != (None, None):
        return None
    if re.search(r"ปี(?:ที่)?\s*\d", question):
        return None
    if _COREQ_Q.search(question):
        return _NOT_FOUND
    if _CONT_Q.search(question) and _CONT_PAIR.search(question) and "วิชา" in question and not _PAIR_PREREQ.search(question):
        return _AMBIGUOUS_TEXT, [], "SELECT NULL WHERE 0"
    return None


# ---- เปรียบเทียบสองวิชา ("X กับ Y ต่างกันอย่างไร [และแต่ละวิชามีรหัสอะไร]") — ยกคำอธิบายรายวิชาของทั้งสอง ไม่สรุปความต่างเอง ----
_COMPARE_WORD = re.compile(r"ต่างกัน|แตกต่าง|เปรียบเทียบ|เหมือนกัน|ต่างจาก")
_COMPARE_TAIL = re.compile(r"ต่างกัน|แตกต่างกัน|แตกต่าง|เปรียบเทียบกัน|เปรียบเทียบ|เหมือนกัน|ต่างจาก|อย่างไร|ยังไง|หรือไม่|ไหม|และ|กับ|แต่ละ|ทั้งสอง|สอง|"
                           r"วิชา|มี|รหัส|อะไร|คือ|ของ|ขอ|ช่วย|หน่อย|ครับ|ค่ะ|คะ|นะ|หรือ")


# ส่วนที่ถามเพิ่มในคำถามเปรียบเทียบที่รู้จัก (ตอบรวมไม่ได้ จึงบอกว่าไม่ได้ตอบ) — คำอื่นที่ค้าง = ไม่แน่ใจ → ปฏิเสธทั้งข้อ
_COMPARE_EXTRAS = (("จำนวนหน่วยกิต", r"หน่วยกิต"), ("วิชาบังคับก่อน", r"ก่อน|ต้องผ่าน|ต้องเรียน"),
                   ("ปี/เทอมที่เรียน", r"ปีไหน|เทอมไหน|ภาคไหน|ในปี"), ("ชั่วโมงเรียน", r"ชั่วโมง"))
_COMPARE_EXTRA_WORDS = re.compile(r"หน่วยกิต|กี่|ก่อน|ต้องผ่าน|ต้องเรียน|ปีไหน|เทอมไหน|ภาคไหน|ในปี|ชั่วโมง|เรียน|ปี|เทอม|ภาค")


def _compare_courses_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """คำถามเปรียบเทียบ "สองวิชาพอดี" (ชื่อเต็มทั้งคู่) → ยกคำอธิบายรายวิชาของทั้งสองตามเล่ม + บอกตรง ๆ ว่าเล่มไม่ได้ระบุข้อแตกต่างไว้
    ส่วนที่ถามเพิ่ม (รหัส/ชื่อวิชา) ตอบให้ในข้อความ; คำที่เหลือนอกเหนือจากนั้น (ก่อน/หน่วยกิต/ปี/ชื่อไม่ครบ/ตัวขยาย) = None ไม่ตอบครึ่งเดียวแบบเงียบ"""
    if not _COMPARE_WORD.search(question) or _CODE8.search(question):
        return None
    _citations_module()
    import course_names
    try:
        courses = [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in conn.execute("SELECT code, name_th, name_en FROM course")]
        described = {r["code"]: dict(r) for r in conn.execute(
            "SELECT code, name_th, description_th, description_en, pdf_page, printed_page FROM course_description")}
    except sqlite3.OperationalError:
        return None
    qn = _name_key(question)
    hints = course_names.course_hints(question, courses)       # ชื่อเต็มตรงตัว; ตัวขยายที่ติดชื่อ ("…ขั้นสูง") จะค้างในส่วนที่เหลือด้านล่าง → ปฏิเสธ
    if len({c for _, c in hints}) != 2 or len({_name_key(r) for r, _ in hints}) != 2:
        return None
    rest = qn
    for raw, _ in sorted(hints, key=lambda h: -len(h[0])):
        rest = rest.replace(_name_key(raw), "")
    left = _COMPARE_TAIL.sub("", rest)
    omitted = [label for label, rx in _COMPARE_EXTRAS if re.search(rx, left)]          # ส่วนที่ถามเพิ่มซึ่งตอบรวมในข้อเดียวไม่ได้ → บอกตรง ๆ
    if _strip_punct(_COMPARE_EXTRA_WORDS.sub("", left)):
        return None
    codes = [c for _, c in hints]
    names = {c["code"]: c["name_th"] for c in courses}
    parts, rows = [], []
    for code in codes:
        d = described.get(code)
        th = ((d or {}).get("description_th") or "").strip() or ((d or {}).get("description_en") or "").strip()
        if not d or not th:
            parts.append(f"ไม่พบคำอธิบายรายวิชา {code} {names.get(code, '')} ในเล่มหลักสูตร".strip())
            continue
        th = re.sub(r"^[A-Z][A-Z\- ]*(?=\s+[ก-๙])\s*", "", th)               # ชื่ออังกฤษที่ขึ้นบรรทัดใหม่ติดหน้าคำอธิบาย ("CONCEPTS ลักษณะ…")
        th = re.sub(r"\s*วท\.บ\.?\s*\(.*$", "", th, flags=re.S).strip() or th   # ท้ายกระดาษ ("วท.บ (…) … สจล. 323 มคอ. 2") ที่ OCR ต่อท้ายคำอธิบายหน้าสุดท้าย
        parts.append(f"{code} {names.get(code, '')}: " + th[:_DESC_MAX_TH] + ("…" if len(th) > _DESC_MAX_TH else ""))
        rows.append({"code": code, "name_th": names.get(code), "description_th": d["description_th"], "description_en": d["description_en"],
                     "pdf_page": d["pdf_page"], "printed_page": d["printed_page"]})
    if not rows:
        return None
    text = "; ".join(parts) + " — เล่มหลักสูตรไม่ได้ระบุข้อแตกต่างระหว่างสองวิชานี้ไว้โดยตรง เปรียบเทียบได้จากคำอธิบายรายวิชาข้างต้น"
    extra_parts: list[str] = []
    try:
        if "จำนวนหน่วยกิต" in omitted:
            cr = {r[0]: r[1] for r in conn.execute("SELECT code, credits FROM course WHERE code IN (?, ?)", codes)}
            if all(cr.get(c) is not None for c in codes):
                extra_parts.append("หน่วยกิต: " + "; ".join(f"{c} {names.get(c, '')} {cr[c]} หน่วยกิต" for c in codes))
                omitted.remove("จำนวนหน่วยกิต")
        if "วิชาบังคับก่อน" in omitted:
            statuses = _prereq_statuses(conn) or {}
            segs = []
            for c in codes:
                req = [r[0] for r in conn.execute("SELECT requires FROM prerequisite WHERE code = ? AND kind = 'pre' ORDER BY requires", (c,))]
                req += [r[0] for r in conn.execute("SELECT requires FROM prerequisite_alt WHERE code = ? ORDER BY requires", (c,))]
                req = list(dict.fromkeys(req))
                if req:
                    segs.append(f"{names.get(c, c)} ต้องเรียนมาก่อน: " + ", ".join(f"{r} {names.get(r, '')}".strip() for r in req))
                elif statuses.get(c) in ("not_found", "unreadable"):
                    segs.append(f"{names.get(c, c)} ยังไม่ทราบวิชาบังคับก่อน (อ่านจากเล่มไม่ได้)")
                else:
                    segs.append(f"{names.get(c, c)} ไม่มีวิชาบังคับก่อน")
            extra_parts.append("วิชาบังคับก่อน: " + "; ".join(segs))
            omitted.remove("วิชาบังคับก่อน")
        if "ปี/เทอมที่เรียน" in omitted:
            segs = []
            for c in codes:
                places = [tuple(r) for r in conn.execute("SELECT DISTINCT year, semester FROM plan_item WHERE code = ? ORDER BY year, semester", (c,))]
                if not places:
                    segs = []
                    break
                segs.append(f"{names.get(c, c)}: " + " และ ".join(f"ปี {y} เทอม {s}" for y, s in places))
            if segs:
                extra_parts.append("ปี/เทอมที่เรียน: " + "; ".join(segs))
                omitted.remove("ปี/เทอมที่เรียน")
    except sqlite3.OperationalError:
        pass
    if extra_parts:
        text += " — " + " — ".join(extra_parts)
    if omitted:
        text += f" — ส่วนที่ยังไม่ได้ตอบ: {', '.join(omitted)} (ตอบรวมกับการเปรียบเทียบในคำถามเดียวไม่ได้ กรุณาถามแยกเป็นอีกคำถาม)"
    return text, rows, "SELECT code, name_th, description_th, description_en, pdf_page FROM course_description WHERE code IN (" + ", ".join(f"'{c}'" for c in codes) + ")"


# ---- ระดับ 3 (วางแผน/กฎ) ที่เล่มไม่มี: เพดานการลงทะเบียน / แผนจบเร็ว → ไม่ตอบ ----
# เจอจริง: "ถ้าอยากจบใน 3 ปีต้องลงเทอมละกี่หน่วยกิต" ตอบ 18 (SUM ของเทอมเดียว), "ปี 3 เทอม 1 ลงทะเบียนได้สูงสุดกี่หน่วยกิต" ตอบ 3 (MAX หน่วยกิตของวิชาเดียว)
_PLANNING_NOT = re.compile(r"จบ(?:ใน|ภายใน)?\s*\d+(?:\.\d+)?\s*ปี|จบเร็ว|จบก่อนกำหนด|ลง(?:ทะเบียน)?(?:เรียน)?(?:ได้)?(?:สูงสุด|ไม่เกิน|มากสุด|เกิน)|เพดานหน่วยกิต")


def _planning_unsupported_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    return _NOT_FOUND if _PLANNING_NOT.search(question) else None


# ---- ถามถึงหลักสูตรอื่นนอกแผนที่เลือก: เดิมตอบด้วยข้อมูลของแผนที่เลือกเงียบ ๆ ("IT ต้องเรียนกี่หน่วยกิต" ตอบ 132 ของ DSBA) ----
_PROGRAM_TOKEN = re.compile(r"(?<![A-Za-z])(DSBA|AIT|BIT|IT)(?![A-Za-z])")           # ตัวพิมพ์ใหญ่เท่านั้น ("it"/"bit" เป็นคำอังกฤษทั่วไป)


def _other_program_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """คำถามที่พูดถึงหลักสูตรอื่น (DSBA/AIT/BIT/IT ที่ไม่ใช่แผนของ DB นี้) หรือเทียบข้ามหลักสูตร = ไม่ตอบด้วยข้อมูลแผนนี้ แต่บอกให้เลือกหลักสูตรก่อน
    ตัดชื่อวิชาออกจากคำถามก่อนหา (กันชื่อวิชาที่มีคำพวกนี้อยู่ข้างใน)"""
    try:
        pid = conn.execute("SELECT program_id FROM program LIMIT 1").fetchone()
        names = [r[0] for r in conn.execute("SELECT name_th FROM course UNION SELECT name_en FROM course") if r[0] and len(r[0]) >= 5]
    except sqlite3.OperationalError:
        return None
    mine = (re.match(r"[A-Za-z]+", pid[0] or "") or [None])[0] if pid else None
    if mine is None or mine.upper() not in ("DSBA", "AIT", "BIT", "IT"):          # ไม่รู้ว่า DB นี้คือแผนไหน = ไม่ตัดสิน
        return None
    text = question
    for n in sorted(names, key=len, reverse=True):
        text = text.replace(n, " ")
    other = [t for t in dict.fromkeys(_PROGRAM_TOKEN.findall(text)) if t != mine.upper()]
    if not other:
        return None
    return (f"คำถามนี้พูดถึงหลักสูตรอื่น ({', '.join(other)}) ที่ไม่ใช่หลักสูตรที่เลือกอยู่ ({mine}) — ตอบข้ามหลักสูตรในคำถามเดียวไม่ได้ "
            "กรุณาเลือกหลักสูตรที่ต้องการในช่องเลือกหลักสูตรแล้วถามใหม่"), [], "SELECT NULL WHERE 0"


# ---- ใช่/ไม่ใช่เรื่องวิชาบังคับก่อน: "สอบตก X จะเรียน Y ได้ไหม" / "เรียน Y ก่อน X ได้ไหม" — ตอบ "ไม่ได้" ได้เมื่อ X เป็นวิชาบังคับก่อนของ Y แน่ ๆ เท่านั้น ----
_YESNO = re.compile(r"ได้ไหม|ได้หรือไม่|ได้หรือเปล่า|ได้มั้ย|ได้รึเปล่า")
_FAIL_WORD = re.compile(r"สอบตก|ยังไม่ผ่าน|ไม่ผ่าน|ตก")


def _prereq_yesno_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """สองวิชาพอดีในคำถามใช่/ไม่ใช่: (ก) "สอบตก/ไม่ผ่าน X … เรียน Y ได้ไหม" (ข) "เรียน Y ก่อน X ได้ไหม" — ถ้า X ∈ วิชาบังคับก่อนของ Y (kind='pre' และ Y ไม่มีทางเลือก
    "หรือ" ใน prerequisite_alt) → "ไม่ได้ — Y มี X เป็นวิชาบังคับก่อน"; กรณีอื่น (ลำดับถูกต้อง/ไม่มีความสัมพันธ์/กำกวม) = None ไม่ตอบ "ไม่ได้" มั่ว"""
    if not _YESNO.search(question) or _CODE8.search(question):
        return None
    _citations_module()
    import course_names
    try:
        courses = [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in conn.execute("SELECT code, name_th, name_en FROM course")]
    except sqlite3.OperationalError:
        return None
    hints = course_names.course_hints(question, courses)
    if len({c for _, c in hints}) != 2:
        return None
    (raw1, c1), (raw2, c2) = hints[0], hints[1]
    f1, f2 = re.search(re.escape(raw1), question, re.I), re.search(re.escape(raw2), question, re.I)
    if not f1 or not f2:
        return None
    p1, p2 = f1.start(), f2.start()
    if p1 >= p2:
        return None
    between = question[p1 + len(raw1): p2]
    if "ก่อน" in between and re.search(r"เรียน", question[:p1]):          # (ข) เรียน c1 ก่อน c2 → ถามว่า c1 เรียนก่อน c2 ได้ไหม: ต้องมี c2 เป็นวิชาบังคับก่อนของ c1
        target, cand = c1, c2
    elif _FAIL_WORD.search(question[:p1]) and re.search(r"เรียน|ลง", between + question[p2:]):   # (ก) ตก c1 แล้วเรียน/ลง(ทะเบียน) c2
        target, cand = c2, c1
    else:
        return None
    try:
        needs = conn.execute("SELECT 1 FROM prerequisite WHERE code = ? AND requires = ? AND kind = 'pre'", (target, cand)).fetchone()
        alt = conn.execute("SELECT 1 FROM prerequisite_alt WHERE code = ?", (target,)).fetchone()
    except sqlite3.OperationalError:
        return None
    names = {c["code"]: c["name_th"] for c in courses}
    if not needs and "ก่อน" in between and not alt:                       # (ข) ลำดับที่ถูกต้อง: c1 เป็นวิชาบังคับก่อนของ c2 → "ได้" (ต้องเรียน c1 ก่อนอยู่แล้ว)
        try:
            ok = conn.execute("SELECT 1 FROM prerequisite WHERE code = ? AND requires = ? AND kind = 'pre'", (c2, c1)).fetchone()
        except sqlite3.OperationalError:
            return None
        if ok:
            return (f"ได้ — {names.get(c1, c1)} ({c1}) เป็นวิชาบังคับก่อนของ {names.get(c2, c2)} ({c2}) จึงต้องเรียน {names.get(c1, c1)} ก่อนอยู่แล้ว",
                    [{"code": c2, "name_th": names.get(c2), "requires": c1, "requires_name_th": names.get(c1)}],
                    f"SELECT code, requires FROM prerequisite WHERE code = '{c2}' AND requires = '{c1}' AND kind = 'pre'")
    if not needs or alt:
        return None
    text = (f"ไม่ได้ — {names.get(target, target)} ({target}) มี {names.get(cand, cand)} ({cand}) เป็นวิชาบังคับก่อน "
            f"(ต้องผ่าน {names.get(cand, cand)} ก่อนจึงจะเรียน {names.get(target, target)} ได้)")
    return text, [{"code": target, "name_th": names.get(target), "requires": cand, "requires_name_th": names.get(cand)}], \
        f"SELECT code, requires FROM prerequisite WHERE code = '{target}' AND requires = '{cand}' AND kind = 'pre'"


# ---- ตัวอย่างระดับ 2 จากสไลด์ ch1 หน้า 7: "วิชาบังคับชั้นปี 2 ภาคต้นมีอะไรบ้าง" / "วิชาเลือก…" — จากหมายเหตุช่องในแผน (plan_item.note "… | บังคับ/เลือก/เลือกเสรี") ----
# เดิมไปทางโมเดล: คำถามนี้ error ("ambiguous column name") และ "วิชาเลือก" ตอบ "ไม่พบ"
_KIND_LIST_Q = re.compile(r"วิชา(?:เฉพาะ)?(เลือกเสรี|เลือก|บังคับ)(?!ก่อน)")
_KIND_LIST_ASK = re.compile(r"อะไรบ้าง|มีอะไร|วิชาอะไร|วิชาไหน|รายชื่อ|รายวิชา|ได้แก่")
_KIND_COUNT_ASK = re.compile(r"กี่วิชา|กี่รายวิชา|มีกี่")
_KIND_LIST_NOT = re.compile(r"ก่อน|ไหม|หรือ|มาก|น้อย|ที่สุด|สูงสุด|ต่ำสุด|หน่วยกิต|ชั่วโมง|เฉลี่ย|รวม|เปรียบเทียบ|ต่างกัน|ถ้า")
_KIND_CATEGORY = re.compile(r"หมวด(?:วิชา)?(เฉพาะ|ศึกษาทั่วไป|เลือกเสรี)")      # กรองหมวดเฉพาะเมื่อพูดว่า "หมวด…" (หมวดในหมายเหตุของแผนบางเล่มอ่านผิด เช่น BIT วิชาเฉพาะบางตัวเป็น "ศึกษาทั่วไป" จึงไม่ถือ "วิชาเฉพาะ" เป็นตัวกรอง)


def _term_kind_list_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """รายวิชา (หรือจำนวนวิชา) บังคับ/เลือก/เลือกเสรี ของ "ปี Y [เทอม S]" ตามหมายเหตุช่องในแผน (plan_item.note); กรองหมวด (เฉพาะ/ศึกษาทั่วไป/เลือกเสรี)
    ได้เมื่อคำถามระบุ; รองรับ "ปีแรก/ปีสุดท้าย/เทอมแรก"; วิชาเลือกรวมช่องที่นักศึกษาเลือกเอง (plan_slot)
    ไม่ระบุปี / มีรหัส / ชื่อวิชา / เทียบ / บังคับก่อน / วิชาในเทอมมีหมายเหตุไม่ครบ = None (ไม่เดา); เทอมที่ไม่มีวิชาประเภทนั้น = บอกตรง ๆ ว่าไม่มี"""
    mt = _KIND_LIST_Q.search(question)
    count_q = bool(_KIND_COUNT_ASK.search(question))
    if not mt or not (count_q or _KIND_LIST_ASK.search(question)) or _KIND_LIST_NOT.search(question) or _CODE8.search(question):
        return None
    try:
        last_year = conn.execute("SELECT MAX(year) FROM plan_item").fetchone()[0]
    except sqlite3.OperationalError:
        return None
    q = question.replace("ปีสุดท้าย", f"ปี {last_year}" if last_year else "ปีสุดท้าย").replace("ปีแรก", "ปี 1")
    q = re.sub(r"(?:เทอม|ภาค(?:การศึกษา)?)แรก", "เทอม 1", q)
    y, s = _term_numbers(q)
    if not y or _named_courses(conn, question, strict=False):
        return None
    kind = mt.group(1)
    cm = _KIND_CATEGORY.search(question)
    category = cm.group(1) if cm else None
    where = "year = ?" + (" AND semester = ?" if s else "")
    args = (y, s) if s else (y,)
    try:
        items = [dict(r) for r in conn.execute(
            f"SELECT p.year, p.semester, p.code, c.name_th, c.name_en, p.credits, p.note FROM plan_item p LEFT JOIN course c ON c.code = p.code "
            f"WHERE p.{where.replace(' AND semester', ' AND p.semester')} ORDER BY p.year, p.semester, p.id", args)]
        slots = [dict(r) for r in conn.execute(f"SELECT year, semester, name_th, credits FROM plan_slot WHERE {where} ORDER BY year, semester, id", args)]             if kind != "บังคับ" and not category else []
    except sqlite3.OperationalError:
        return None
    kinds = [(mk.group(1) if (mk := re.search(r"\|\s*(บังคับ|เลือกเสรี|เลือก)\s*$", it["note"] or "")) else None) for it in items]
    if not items or any(k is None for k in kinds):                           # หมายเหตุไม่ครบ = ไม่ตัดสิน
        return None
    picked = [dict(it, kind=k) for it, k in zip(items, kinds) if k == kind and (not category or category in (it["note"] or ""))]
    label = _TERM_LABEL.format(y=y, s=s) if s else f"ปี {y}"
    cat_text = f"หมวด{category}" if category else ""
    sql = (f"SELECT code, credits, note FROM plan_item WHERE year = {y}" + (f" AND semester = {s}" if s else "") + f" AND note LIKE '%| {kind}'"
           + (f" AND note LIKE '%{category}%'" if category else ""))
    rows = [{"year": it["year"], "semester": it["semester"], "code": it["code"], "name_th": it["name_th"], "credits": it["credits"], "kind": kind}
            for it in picked] + [{"slot": sl["name_th"], "credits": sl["credits"]} for sl in slots]
    if not picked and not slots:
        if kind == "บังคับ":                                          # ทุกวิชาในเทอมถูกอ่านเป็น "เลือก" = น่าจะอ่านประเภทผิด (ctype แม่น 79-98%) → ไม่ยืนยันว่า "ไม่มี" ปล่อยทางอื่น
            return None
        return f"{label} ไม่มีวิชา{kind}{cat_text}ที่ระบุในแผนตามหมายเหตุของเล่ม", [], sql
    if count_q:
        text = f"{label} มีวิชา{kind}{cat_text} {len(picked)} วิชา" + (f" (และมีช่องที่นักศึกษาเลือกเองอีก {len(slots)} ช่อง)" if slots else "")
        return text, rows, sql
    parts = [f"{it['code']} {it['name_th'] or ''} ({it['credits']} หน่วยกิต)".replace("  ", " ") + (f" [{_TERM_LABEL.format(y=it['year'], s=it['semester'])}]" if not s else "")
             for it in picked]
    text = f"{label} วิชา{kind}{cat_text} {len(picked)} วิชา: " + "; ".join(parts) if picked else f"{label} ไม่มีวิชา{kind}ที่ระบุรหัสในแผน"
    if slots:
        text += "; ช่องที่นักศึกษาเลือกเอง: " + ", ".join(f"{sl['name_th']} ({sl['credits']} หน่วยกิต)" for sl in slots)
    return text, rows, sql


# ---- ตัวอย่างระดับ 2 ของอาจารย์: "วิชา X ต้องผ่านวิชาใดก่อน? ถ้ายังไม่ผ่านจะลงทะเบียนได้ไหม" — เดิมตอบแค่ลิสต์วิชา ไม่ตอบส่วน "ลงทะเบียนได้ไหม" ----
_REG_YESNO = re.compile(r"(?:ถ้า|หาก)?\s*ยัง?ไม่ผ่าน.{0,24}?(?:ลงทะเบียน|เรียน).{0,12}?(?:ได้ไหม|ได้หรือไม่|ได้มั้ย|ได้รึเปล่า|ได้หรือเปล่า)")
_REG_TAIL = re.compile(r"ต้องผ่านวิชา(?:ใด|อะไร)ก่อน|ต้องผ่านอะไรก่อน|วิชาบังคับก่อน(?:คืออะไร|คือ|มีอะไร)?|ถ้า|หาก|ยัง|ไม่ผ่าน|จะ|ลงทะเบียน|เรียน|ได้ไหม|ได้หรือไม่|ได้มั้ย|"
                       r"ได้รึเปล่า|ได้หรือเปล่า|วิชา|ต้อง|ใด|อะไร|ก่อน|บังคับ|ผ่าน|และ|แล้ว|ครับ|ค่ะ|คะ|นะ|มี|ของ|การ")


def _prereq_register_answer(conn: sqlite3.Connection, question: str) -> tuple[str, list[dict], str] | None:
    """วิชาเดียว + ถามวิชาบังคับก่อน + "ถ้ายังไม่ผ่านจะลงทะเบียนได้ไหม" → ลิสต์วิชาบังคับก่อน + "ลงทะเบียนไม่ได้ (ต้องผ่านก่อน)";
    วิชาที่ไม่มีวิชาบังคับก่อน (ยืนยันจากเล่ม) → ลงทะเบียนได้; มีทางเลือก "หรือ"/ไม่ทราบสถานะ/ส่วนอื่นค้าง = None"""
    if not _REG_YESNO.search(question) or not _PAIR_PREREQ.search(question) or _CODE8.search(question):
        return None
    _citations_module()
    import course_names
    try:
        courses = [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in conn.execute("SELECT code, name_th, name_en FROM course")]
    except sqlite3.OperationalError:
        return None
    hints = course_names.course_hints(question, courses)
    if len({c for _, c in hints}) != 1 or len({_name_key(r) for r, _ in hints}) != 1:
        return None
    raw, code = hints[0]
    if _strip_punct(_REG_TAIL.sub("", _name_key(_remove_hinted_name(question, raw)).replace(_name_key(raw), ""))):
        return None
    names = {c["code"]: c["name_th"] for c in courses}
    try:
        req = [r[0] for r in conn.execute("SELECT requires FROM prerequisite WHERE code = ? AND kind = 'pre' ORDER BY requires", (code,))]
        alt = conn.execute("SELECT 1 FROM prerequisite_alt WHERE code = ?", (code,)).fetchone()
    except sqlite3.OperationalError:
        return None
    if alt:
        return None
    sql = f"SELECT requires FROM prerequisite WHERE code = '{code}' AND kind = 'pre'"
    name = names.get(code, code)
    if req:
        listed = ", ".join(f"{r} {names.get(r, '')}".strip() for r in req)
        return (f"{name} ต้องเรียนมาก่อน: {listed} — ถ้ายังไม่ผ่านวิชาบังคับก่อนดังกล่าว จะลงทะเบียนเรียน {name} ไม่ได้ (ต้องผ่านก่อน)",
                [{"code": r, "name_th": names.get(r)} for r in req], sql)
    if (_prereq_statuses(conn) or {}).get(code) == "none":
        return (f"{name} ไม่มีวิชาบังคับก่อน จึงลงทะเบียนได้โดยไม่ต้องผ่านวิชาอื่นก่อน", [{"code": code, "name_th": name, "requires": None}], sql)
    return None


# ทางลัดเชิงกำหนดตามลำดับความสำคัญ — ตัวแรกที่ตอบได้ชนะ (ไม่ผ่านโมเดล); ทุกตัวต้องปฏิเสธ (None) เมื่อไม่แน่ใจ ดีกว่าตอบผิด
_SHORTCUTS = (
    _other_program_answer, _planning_unsupported_answer,
    _open_slot_answer, _term_choices_answer, _term_kind_list_answer, _prereq_register_answer, _prereq_scenario_answer, _has_prereq_yesno_answer, _which_first_answer, _unlock_answer, _courses_with_prereq_answer, _name_prefix_list_answer, _plan_check_answer, _other_plan_diff_answer, _ge_category_answer, _extreme_credits_answer, _no_prereq_answer, _prereq_pair_count_answer, _prereq_ambiguity_answer, _compare_courses_answer,
    _prereq_yesno_answer,
    _hours_filter_answer, _prereq_term_answer, _term_total_answer, _course_description_answer, _book_section_answer, _elective_group_answer,
    _code_lookup_answer, _code_family_answer, _course_hours_answer, _extreme_hours_answer, _program_fact_answer, _course_attr_answer,
    _multi_course_answer, _same_term_answer, _course_kind_answer, _year_credits_answer, _summer_term_answer, _unknown_course_answer,
    _catalog_course_answer, _credit_structure_answer,
)


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
    asked_plan, own_plan = _requested_plan(question), _own_plan(conn)
    if asked_plan and own_plan and asked_plan != own_plan:                # ถามถึงอีกแผน (เช่น เลือกแผนไม่สหกิจแต่ถาม "แผนสหกิจ…") → ตอบจากฐานข้อมูลของแผนนั้น
        sib = (_sibling_plan_db(conn) or (None, None))[1]
        if sib is not None:
            other = open_db(sib, readonly=True)
            try:
                routed = ask(other, question, verbose=verbose)
            finally:
                other.close()
            routed["answer"] = f"(ตอบตามแผน{'สหกิจ' if asked_plan == 'coop' else 'ไม่สหกิจ'}) " + str(routed.get("answer") or "")
            return routed
    question = _prepare_question(conn, question)            # ตัดชื่อหลักสูตร/ชื่อแผนของตัวเอง + รหัสที่ซ้ำชื่อ + ภาคต้น/ภาคปลาย → ภาคการศึกษาที่ 1/2 (result["question"] ยังเป็นข้อความเดิมของผู้ใช้)
    scope_elective_view(conn, question)                   # v_elective_group ไม่รวม GE เว้นแต่คำถามพูดถึง GE (ดูเหตุผลที่ฟังก์ชัน)
    # ช่องเลือกเองที่เล่มไม่ระบุรายชื่อ (ระบุชื่อช่อง) หรือสรุปช่องเลือกทั้งเทอม — ตอบตามเล่ม/แคตตาล็อก ไม่ต้องเรียกโมเดล
    open_slot = None
    for shortcut in _SHORTCUTS:
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
                result["answer"] = _NOT_FOUND_TEXT                   # SQL สร้าง/รันไม่สำเร็จหลังลองซ้ำ = ตอบแบบเดียวกับ "ไม่พบ" (judge/ผู้ใช้เห็นข้อความเดียว; error ยังเก็บไว้ในฟิลด์ error สำหรับตรวจ)
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
