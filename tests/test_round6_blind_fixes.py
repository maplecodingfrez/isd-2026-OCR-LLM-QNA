"""รอบ 6: ข้อผิดจากชุด blind 140 ข้อ (2026-10-10) — คำถามเขียนโดย subagent ที่ไม่เห็นโค้ด/DB เฉลยจาก SQLite ตรง ๆ
กลุ่มสาเหตุ: (1) ชื่อวิชาอังกฤษไม่ครบแต่ชี้วิชาเดียว (2) ชื่อหลักสูตรตามด้วยแผน "DSBA สหกิจ" (3) เทียบสองแผนที่ถูกตัดคำว่า ไม่สหกิจ ทิ้ง
(4) เทียบหน่วยกิตสองปี (5) เทอมสหกิจรวมกี่หน่วยกิต (6) กี่หมู่/กลุ่มของ GE ที่ DB ไม่มีโครงสร้าง (7) จบได้ไหมจากหน่วยกิตที่มี (8) วิชาแกนทั้งหมด"""

import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import course_names
import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
NOT_FOUND = m._NOT_FOUND[0]


def _ask(rel, question, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("must be answered by a rule, not the model"))
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        return m.ask(conn, question, verbose=False)


def _courses(rel):
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        return [{"code": r[0], "name_th": r[1], "name_en": r[2]} for r in conn.execute("SELECT code, name_th, name_en FROM course")]


# ---- (1) ชื่ออังกฤษพิมพ์ไม่ครบ: นโยบายโปรเจกต์ = ไม่เดาวิชาให้ ("ผิดวิชา = 0") แต่ต้องเสนอวิชาใกล้เคียงพร้อมค่าที่ถาม (เดิมถามวิชาบังคับก่อน/ปีเทอมแล้วได้ "ไม่พบ" เฉย ๆ) ----
@pytest.mark.parametrize("rel, question, code", [
    ("BIT/no_coop", "วิชา Systems Analysis and Design มี prerequisite อะไรบ้างครับ", "06036121"),
    ("IT/coop", "วิชา Web Programming ต้องเรียนอะไรมาก่อน", "06066302"),
])
def test_partial_english_name_prerequisite_gets_near_course_not_a_guess(rel, question, code, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert answer.startswith(NOT_FOUND) and code in answer and "วิชาบังคับก่อน: ไม่มี" in answer and "ถ้าหมายถึงวิชาใด" in answer


def test_partial_english_name_term_question_in_english(monkeypatch):
    answer = _ask("BIT/coop", "Which semester is Database taken in BIT co-op plan?", monkeypatch)["answer"]
    assert answer.startswith(NOT_FOUND) and "06036112" in answer and "ปี 2 เทอม 2" in answer


def test_colloquial_data_structures_prerequisite_is_answered(monkeypatch):
    """"Data Structures" เป็นชื่อภาษาพูดที่ทางลัดอื่นรับอยู่แล้ว (COLLOQUIAL_RULES) — ถามวิชาบังคับก่อนต้องตอบตรง ๆ ไม่ใช่ "ไม่พบ" """
    answer = _ask("AIT", "ก่อนเรียน Data Structures ต้องผ่านวิชาอะไรมาก่อนบ้าง", monkeypatch)["answer"]
    assert "06066301" in answer and "วิชาบังคับก่อน: ไม่มี" in answer and "ไม่พบ" not in answer


# ---- (2) "<หลักสูตร> สหกิจ" = ชื่อแผน ไม่ใช่วิชาสหกิจศึกษา ----
@pytest.mark.parametrize("rel, question, expect", [
    ("DSBA/coop", "ปี 4 เทอม 2 DSBA สหกิจเรียนอะไรบ้าง", "06026259"),
    ("BIT/coop", "ปี 4 เทอม 1 ของ BIT สหกิจ เรียนอะไรบ้าง", "06036115"),
    ("IT/coop", "ปี 3 เทอม 2 IT สหกิจมีวิชาอะไรบ้าง", "06016481"),
    ("DSBA/coop", "สหกิจศึกษาในแผน DSBA สหกิจ อยู่เทอมไหนของปีอะไร", "ปี 4 เทอม 2"),
])
def test_program_plus_coop_is_plan_name(rel, question, expect, monkeypatch):
    assert expect in _ask(rel, question, monkeypatch)["answer"]


def test_web_application_development_in_coop_plan(monkeypatch):
    answer = _ask("BIT/coop", "วิชา Web Application Development เรียนปีไหน ของ BIT สหกิจ", monkeypatch)["answer"]
    assert "06036114" in answer and "ปี 3 เทอม 1" in answer and "สหกิจศึกษาอยู่" not in answer


def test_statistics_in_it_coop_is_not_the_coop_course(monkeypatch):
    answer = _ask("IT/coop", "วิชา Statistics ของ IT สหกิจ อยู่เทอมไหน", monkeypatch)["answer"]
    assert "06066001" in answer and "ปี 1 เทอม 2" in answer and "06016481" not in answer


# ---- (3) เทียบแผนสหกิจกับไม่สหกิจ ----
@pytest.mark.parametrize("rel, question", [
    ("BIT/no_coop", "BIT สหกิจกับไม่สหกิจ ต่างกันที่วิชาไหนบ้าง และหน่วยกิตรวมต่างกันเท่าไหร่"),
    ("BIT/coop", "BIT สหกิจกับ BIT ไม่สหกิจ ต่างกันตรงไหน เทอมไหนที่แผนไม่เหมือนกัน"),
    ("DSBA/no_coop", "DSBA สหกิจกับไม่สหกิจ ต่างกันที่วิชาไหนบ้าง แล้วทำไมหน่วยกิตรวมไม่เท่ากัน"),
])
def test_plan_diff_with_program_token(rel, question, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert "ไม่พบ" not in answer and "เฉพาะแผนสหกิจ 2 วิชา" in answer and "หน่วยกิตรวม" in answer


def test_plan_diff_it_year_scope(monkeypatch):
    answer = _ask("IT/no_coop", "IT สหกิจกับไม่สหกิจ หน่วยกิตรวมและวิชาในปี 4 ต่างกันยังไง", monkeypatch)["answer"]
    assert "ไม่พบ" not in answer and "ปี 4" in answer


# ---- (4) เทียบหน่วยกิตสองปี (ยอดตามเล่ม v_semester_credits_full) ----
@pytest.mark.parametrize("rel, question, expect", [
    ("BIT/coop", "เทียบหน่วยกิตปี 1 กับปี 2 ของ BIT สหกิจหน่อย", ["36", "เท่ากัน"]),
    ("IT/no_coop", "ปี 1 กับปี 2 ของ IT ไม่สหกิจ ปีไหนเรียนหนักกว่าในแง่หน่วยกิต", ["36", "เท่ากัน"]),
    ("AIT", "เปรียบเทียบหน่วยกิตรวมของปี 1 กับปี 3 ใน AIT หน่อย อันไหนเยอะกว่า", ["34", "31", "ปี 1 มากกว่าปี 3"]),
    ("DSBA/no_coop", "เปรียบเทียบปี 3 กับปี 4 ของ DSBA ไม่สหกิจ ปีไหนลงหน่วยกิตเยอะกว่า", ["36", "18", "ปี 3 มากกว่าปี 4"]),
])
def test_two_year_comparison(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert all(e in answer for e in expect), answer


# ---- (5) เทอมสหกิจ ----
@pytest.mark.parametrize("rel, question, expect", [
    ("DSBA/coop", "เทอมที่ไปสหกิจนับเป็นกี่หน่วยกิต รวมของเทอมนั้นเท่าไหร่", "ปี 4 เทอม 2) รวม 6 หน่วยกิต"),
    ("IT/coop", "เทอมสหกิจ รวมกี่หน่วยกิตในแผน IT สหกิจ", "ปี 3 เทอม 2) รวม 6 หน่วยกิต"),
])
def test_coop_term_total_credits(rel, question, expect, monkeypatch):
    assert expect in _ask(rel, question, monkeypatch)["answer"]


# ---- (6) กี่หมู่/กลุ่ม ----
def test_ge_group_count_without_structure_is_not_found(monkeypatch):
    assert _ask("BIT/no_coop", "วิชาศึกษาทั่วไปที่ต้องเรียนมีกี่หมู่ แต่ละหมู่กี่หน่วยกิต", monkeypatch)["answer"].startswith("ไม่มีข้อมูลโครงสร้างหน่วยกิต")


def test_ge_group_count_with_structure(monkeypatch):
    answer = _ask("DSBA/no_coop", "วิชาศึกษาทั่วไปที่ต้องเรียนมีกี่หมู่ แต่ละหมู่กี่หน่วยกิต", monkeypatch)["answer"]
    assert "4 กลุ่ม" in answer and "30 หน่วยกิต" in answer and all(n in answer for n in ("6", "9"))


# ---- (7) จบได้ไหม จากหน่วยกิตที่มี ----
@pytest.mark.parametrize("rel, question, expect", [
    ("BIT/no_coop", "ผมเก็บหน่วยกิตได้ 125 ครบทุกหมวดยกเว้นวิชาเลือกเสรีขาดอยู่ 3 หน่วย จะจบได้ไหม", ["126", "ยังจบไม่ได้", "ขาดอีก 1 หน่วยกิต"]),
    ("AIT", "เรียนผ่านมาแล้ว 100 หน่วยกิต แต่ยังไม่ผ่านวิชาศึกษาทั่วไปบางตัว จะจบ AIT ได้ไหม ต้องเช็กอะไรบ้าง", ["120", "ยังจบไม่ได้", "ขาดอีก 20 หน่วยกิต"]),
])
def test_graduation_check_from_credits(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert all(e in answer for e in expect), answer


def test_graduation_without_number_unchanged(monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT NULL WHERE 0"}')
    with closing(m.open_db(RUNS / "IT/no_coop" / "lab8b_output/curriculum.db", readonly=True)) as conn:
        assert "ยังจบไม่ได้" not in m.ask(conn, "ผมเรียนครบหน่วยกิตแล้วแต่ยังไม่ผ่านวิชาโครงงาน จบ IT ไม่สหกิจได้ไหม", verbose=False)["answer"]


# ---- (8) วิชาแกนทั้งหมด ----
def test_core_group_total(monkeypatch):
    answer = _ask("DSBA/coop", "วิชาแกนทั้งหมดของ DSBA สหกิจรวมกี่หน่วยกิต", monkeypatch)["answer"]
    assert "45 หน่วยกิต" in answer
