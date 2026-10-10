"""คำใบ้ตามสาเหตุ — ราก: ตอบ "ไม่พบ" เหมือนกันหมด ผู้ใช้ไม่รู้ว่าผิดตรงไหน: (a) ปี/เทอมที่แผนไม่มี (ปี 5, เทอม 4) (b) ชื่อวิชาอังกฤษสะกดผิดนิดเดียว
(c) พูดถึง "วิชานี้" โดยไม่ระบุวิชา. ทุกข้อต้องไม่เรียกโมเดล และข้อความบอกสาเหตุ + ทางแก้; คำถามที่ถูกต้องห้ามถูกดัก"""

from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
NOT_FOUND = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"


def conn_for(rel="DSBA/coop"):
    return closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True))


@pytest.mark.parametrize("q,needle", [
    ("ปี 5 เทอม 1 เรียนอะไรบ้าง", "ปี 1–4"),
    ("ปี 6 รวมกี่หน่วยกิต", "ปี 1–4"),
    ("ปี 1 เทอม 4 เรียนอะไร", "เทอม 1–2"),
    ("ภาคเรียนที่ 3 เรียนอะไรบ้าง", "เทอม 1–2"),
    ("ปี 0 เทอม 1 มีกี่วิชา", "ปี 1–4"),
])
def test_term_outside_plan_says_which_part_is_wrong(q, needle, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("no model"))
    with conn_for() as conn:
        result = m.ask(conn, q, verbose=False)
    assert result["answer"].startswith(NOT_FOUND) and needle in result["answer"], result["answer"]
    assert result["rows"] == []


@pytest.mark.parametrize("q", [
    "ปี 4 เทอม 2 เรียนอะไรบ้าง", "ปี 1 เทอม 1 รวมกี่หน่วยกิต", "หลักสูตรปรับปรุง ปี 2564 กี่หน่วยกิต", "ภาคเรียนที่ 2 ปี 3 มีวิชาอะไรบ้าง",
    "ปี 2 เรียนกี่หน่วยกิต",
])
def test_valid_term_is_not_intercepted(q):
    with conn_for() as conn:
        assert m._out_of_plan_term_answer(conn, m._prepare_question(conn, q)) is None


@pytest.mark.parametrize("q", ["วิชานี้ต้องเรียนก่อนไหม", "วิชานั้นกี่หน่วยกิต", "วิชานี้เรียนปีไหน", "วิชานี้ต้องผ่านอะไรมาก่อน"])
def test_pronoun_without_course_asks_which(q, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("no model"))
    with conn_for() as conn:
        result = m.ask(conn, q, verbose=False)
    assert result["answer"].startswith("คำถามยังไม่ชัดเจน") and "วิชาไหน" in result["answer"], result["answer"]


@pytest.mark.parametrize("q", ["วิชา Calculus 1 กี่หน่วยกิต", "วิชานี้คือ แคลคูลัส 1 ต้องเรียนก่อนไหม", "Calculus 1 วิชานี้กี่หน่วยกิต"])
def test_pronoun_with_course_not_intercepted(q):
    with conn_for() as conn:
        assert m._unnamed_course_reference_answer(conn, m._prepare_question(conn, q)) is None


@pytest.mark.parametrize("q,code,name", [
    ("Calcuus 1 กี่หน่วยกิต", "06026200", "CALCULUS 1"),
    ("Discrete Mathmatics กี่หน่วยกิต", "06066000", "DISCRETE MATHEMATICS"),
    ("Data Visualisation เรียนปีไหน", "06026209", "DATA VISUALIZATION"),
])
def test_english_typo_suggests_did_you_mean(q, code, name, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("no model"))
    with conn_for() as conn:
        result = m.ask(conn, q, verbose=False)
    assert result["answer"].startswith(NOT_FOUND) and "หมายถึง" in result["answer"], result["answer"]
    assert code in result["answer"] and name in result["answer"]


@pytest.mark.parametrize("q", ["Zzzzzz Qqqq 1 กี่หน่วยกิต", "Calculus 1 กี่หน่วยกิต", "CALCULUS 1", "ค่าเทอมเท่าไหร่", "Calculus 9 กี่หน่วยกิต",
                               "PROBABILITY AND STATISTICS lecture สัปดาห์ละกี่ชั่วโมง", "DIGITAL TECHNOLOGY FOR BUSINESS lecture สัปดาห์ละกี่ชั่วโมง"])
def test_typo_rule_stays_quiet_otherwise(q):
    with conn_for() as conn:
        assert m._typo_course_answer(conn, m._prepare_question(conn, q)) is None
