"""ชั้นแสดงผลคำตอบ: "รหัส (ชื่อไทย)" จากเส้นทางโมเดล → เติมชื่ออังกฤษของเล่มต่อท้ายเมื่อชื่อตรงกับ name_th ของรหัสนั้นเป๊ะ ๆ
(เดิม format_course_answer เติมเฉพาะผลที่มีทั้ง code และ name_th ในแถว; คำตอบโมเดลของ "ต้องผ่านวิชาอะไรมาก่อน" มีแค่คอลัมน์ requires จึงไม่ถูกเติม)
ไม่แตะ ask()/กฎ; เติมเฉพาะข้อมูลที่ตรงกับฐานข้อมูลอยู่แล้ว"""

from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m
from course_display import format_course_answer

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
DB = RUNS / "DSBA/coop/lab8b_output/curriculum.db"
TH = "แนวคิดระบบฐานข้อมูล"
EN = "DATABASE SYSTEM CONCEPTS"


def _fmt(answer, rows=None, error=None):
    result = {"answer": answer, "rows": rows if rows is not None else [{"requires": "06066300"}], "error": error}
    with closing(m.open_db(DB, readonly=True)) as conn:
        format_course_answer(conn, result)
    return result["answer"]


def test_model_route_parenthesized_thai_name_gets_english():
    assert _fmt(f"06066300 ({TH})") == f"06066300 ({TH} / {EN})"


def test_several_codes_in_one_answer():
    out = _fmt(f"06066300 ({TH}), 06026200 (แคลคูลัส 1)")
    assert f"06066300 ({TH} / {EN})" in out and "06026200 (แคลคูลัส 1 / CALCULUS 1)" in out


@pytest.mark.parametrize("answer", [
    f"06066300 ({TH} / {EN})",                  # มีอังกฤษแล้ว = ไม่ซ้ำ (เส้นทางกฎ)
    "06066300 (ชื่ออื่นที่ไม่ตรงเล่ม)",         # ชื่อไม่ตรง = ไม่แตะ
    f"99999999 ({TH})",                          # ไม่มีรหัสในแผน = ไม่แตะ
    "ปี 2 เทอม 1 รวม 18 หน่วยกิต",              # ไม่มีรูปแบบรหัส(ชื่อ) = ไม่แตะ
    "ไม่พบข้อมูลนี้ในเล่มหลักสูตร",
])
def test_everything_else_is_untouched(answer):
    assert _fmt(answer) == answer


def test_error_result_and_empty_answer_are_untouched():
    assert _fmt(f"06066300 ({TH})", error="boom") == f"06066300 ({TH})"
    assert _fmt("") == ""


def test_existing_row_based_formatting_still_works_and_is_not_doubled():
    rows = [{"code": "06026200", "name_th": "แคลคูลัส 1", "credits": 3}]
    out = _fmt("06026200 แคลคูลัส 1 3 หน่วยกิต", rows=rows)
    assert out.count("CALCULUS 1") == 1 and "06026200 แคลคูลัส 1 / CALCULUS 1" in out


def test_rule_route_answer_is_unchanged_end_to_end(monkeypatch):
    """คำตอบจากกฎวิชาบังคับก่อนมีอังกฤษครบแล้ว ผ่านชั้นแสดงผลต้องเหมือนเดิมทุกตัวอักษร"""
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("rule route must not call the model"))
    with closing(m.open_db(DB, readonly=True)) as conn:
        result = m.ask(conn, "วิชา 06026212 ต้องผ่านวิชาใดก่อน", verbose=False)
        before = result["answer"]
        format_course_answer(conn, result)
    assert result["answer"] == before
