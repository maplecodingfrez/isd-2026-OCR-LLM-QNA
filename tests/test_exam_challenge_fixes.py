"""ข้อผิดจาก probe แนว Challenge ch1 (2026-10-18): คำถามที่ตกไปทางโมเดลแล้วตอบผิดหรือตอบไม่พบ ทั้งที่ DB มีข้อมูลครบ
(1) ปี X เทอม Y มีวิชาไหนต้องผ่านวิชาก่อน (2) รายการวิชาทั้งปี — โมเดลทิ้งแถวและไม่นับช่องวิชาเลือก
(3) ผ่านแล้ว N หน่วยกิต ขาดอีกกี่ (4) AIT มีแผนสหกิจไหม — AIT มีแผนเดียว
(6) ฉบับเก่า/ฉบับปรับปรุง/2 ปริญญา — ระบบมีเล่มฉบับเดียว (เดิมตอบ "ไม่มีเลย (0 รายการ)" จาก SQL ไร้ความหมาย)
และทางลัดที่พังต้องมี log (เดิมกลืน exception เงียบแล้วตกไปโมเดล)"""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
NOT_FOUND = m._NOT_FOUND[0]
PLANS = ["AIT", "BIT/coop", "BIT/no_coop", "DSBA/coop", "DSBA/no_coop", "IT/coop", "IT/no_coop"]


def _ask(rel, question, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("must be answered by a rule, not the model"))
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        return m.ask(conn, question, verbose=False)


def _db(rel):
    return closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True))


def _with_prereq(conn, y, s):
    """Plan courses of one term that need another course first (ground truth straight from SQLite)."""
    codes = {r[0] for r in conn.execute("SELECT code FROM prerequisite WHERE kind = 'pre'")}
    try:
        codes |= {r[0] for r in conn.execute("SELECT code FROM prerequisite_alt")}
    except sqlite3.OperationalError:
        pass
    in_term = [r[0] for r in conn.execute("SELECT code FROM plan_item WHERE year = ? AND semester = ? ORDER BY id", (y, s))]
    return [c for c in dict.fromkeys(in_term) if c in codes]


def _terms(rel):
    with _db(rel) as conn:
        return [tuple(r) for r in conn.execute("SELECT DISTINCT year, semester FROM plan_item ORDER BY year, semester")]


# ---- (1) ปี X เทอม Y มีวิชาไหนต้องผ่านวิชาก่อน: เดิมโมเดลกรอง alt_group IS NOT NULL ได้ 0 แถว = "ไม่พบ" ----
def test_term_courses_with_prerequisite(monkeypatch):
    answer = _ask("DSBA/no_coop", "ปี 3 เทอม 1 มีวิชาไหนที่มีวิชาบังคับก่อนบ้าง", monkeypatch)["answer"]
    assert "06026212" in answer and "06066300" in answer and NOT_FOUND not in answer
    assert "06026211" not in answer                                      # ไม่มีวิชาบังคับก่อน ห้ามอยู่ในรายชื่อ


def test_term_credits_and_prerequisite_compound(monkeypatch):
    """เดิมตอบ "06066300 (รวม 9 หน่วยกิต)" ผิดทั้งสองส่วน (ที่ถูก: 18 หน่วยกิต, การสร้างคลังข้อมูลต้องผ่าน 06066300)"""
    answer = _ask("DSBA/no_coop", "ปี 3 เทอม 1 ถ้าลงวิชาครบตามแผนจะได้กี่หน่วยกิต และมีวิชาไหนที่ต้องผ่านวิชาก่อนบ้าง", monkeypatch)["answer"]
    assert "18 หน่วยกิต" in answer and "06026212" in answer and "06066300" in answer


@pytest.mark.parametrize("rel", PLANS)
def test_term_courses_with_prerequisite_every_term(rel, monkeypatch):
    for y, s in _terms(rel):
        with _db(rel) as conn:
            expect = _with_prereq(conn, y, s)
        answer = _ask(rel, f"ปี {y} เทอม {s} มีวิชาไหนที่ต้องผ่านวิชาก่อนบ้าง", monkeypatch)["answer"]
        assert NOT_FOUND not in answer, (y, s, answer)
        assert all(c in answer for c in expect), (y, s, expect, answer)
        if not expect:
            assert "ไม่มีวิชาที่" in answer, (y, s, answer)


# ---- (2) รายการวิชาทั้งปี: เดิมโมเดลเรียบเรียงเหลือวิชาเดียว (ปี 4 มี 1 วิชา + 5 ช่องวิชาเลือก = 18 หน่วยกิต) ----
@pytest.mark.parametrize("question", ["สรุปวิชาทั้งหมดที่ต้องเรียนในปี 4", "ปี 4 เรียนวิชาอะไรบ้าง"])
def test_year_list_is_rendered_from_rows(question, monkeypatch):
    answer = _ask("DSBA/no_coop", question, monkeypatch)["answer"]
    for part in ("06026215", "ปี 4 เทอม 1", "ปี 4 เทอม 2", "วิชาเลือกเสรี 1", "วิชาเลือกเสรี 2", "วิชาเลือกหมวดวิชาศึกษาทั่วไป", "18 หน่วยกิต"):
        assert part in answer, (part, answer)


@pytest.mark.parametrize("rel", PLANS)
def test_year_list_has_every_plan_course(rel, monkeypatch):
    with _db(rel) as conn:
        years = [r[0] for r in conn.execute("SELECT DISTINCT year FROM plan_item ORDER BY year")]
    for y in years:
        with _db(rel) as conn:
            codes = {r[0] for r in conn.execute("SELECT code FROM plan_item WHERE year = ?", (y,))}
            total = conn.execute("SELECT SUM(credits) FROM main.v_semester_credits_full WHERE year = ?", (y,)).fetchone()[0]
        answer = _ask(rel, f"ปี {y} มีวิชาอะไรบ้าง", monkeypatch)["answer"]
        assert all(c in answer for c in codes), (y, codes, answer)
        assert f"รวมทั้งปี {total} หน่วยกิต" in answer, (y, total, answer)


def test_term_list_unchanged(monkeypatch):
    """รายการเทอมเดียวยังเป็นของทางลัดเดิม (_term_list_answer)"""
    answer = _ask("DSBA/no_coop", "ปี 4 เทอม 1 มีวิชาอะไรบ้าง", monkeypatch)["answer"]
    assert answer.startswith("ปี 4 เทอม 1: ") and "รวมทั้งปี" not in answer


# ---- (3) ผ่านแล้ว N หน่วยกิต ขาดอีกกี่: เดิมตอบ "หน่วยกิตรวมตลอดหลักสูตร 132 หน่วยกิต" ไม่ได้ลบให้ ----
@pytest.mark.parametrize("rel, question, expect", [
    ("DSBA/no_coop", "ผมเรียนผ่านแล้ว 100 หน่วยกิต ยังขาดอีกกี่หน่วยกิตถึงจะจบ", ["ขาดอีก 32 หน่วยกิต", "132"]),
    ("AIT", "เก็บได้ 90 หน่วยกิตแล้ว เหลืออีกกี่หน่วยกิต", ["ขาดอีก 30 หน่วยกิต", "120"]),
    ("IT/coop", "เรียนมาแล้ว 129 หน่วยกิต ต้องเรียนอีกกี่หน่วยกิต", ["ครบ"]),
])
def test_credits_remaining(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert all(e in answer for e in expect), answer


def test_program_total_unchanged(monkeypatch):
    assert _ask("DSBA/no_coop", "หลักสูตรนี้ต้องเรียนกี่หน่วยกิต", monkeypatch)["answer"] == "หน่วยกิตรวมตลอดหลักสูตร 132 หน่วยกิต"


# ---- (4) AIT มีแผนสหกิจไหม: เดิมตอบไม่พบ ทั้งที่ AIT มีแผนเดียวและมีสหกิจศึกษาอยู่ในแผน ----
@pytest.mark.parametrize("question", ["AIT มีแผนสหกิจไหม", "หลักสูตรนี้มีแผนสหกิจหรือเปล่า", "มีแผนไม่สหกิจไหม"])
def test_ait_single_plan(question, monkeypatch):
    answer = _ask("AIT", question, monkeypatch)["answer"]
    assert "แผนเดียว" in answer and "06046443" in answer and "ปี 4 เทอม 2" in answer


# ---- (6) ฉบับเก่า/ฉบับปรับปรุง/2 ปริญญา: ระบบมีเล่มฉบับเดียวต่อหลักสูตร ตอบตรง ๆ แทนผลจาก SQL ที่ไม่มีความหมาย ----
@pytest.mark.parametrize("rel, question", [
    ("DSBA/no_coop", "หลักสูตรนี้มีแบบ 2 ปริญญาไหม"),
    ("DSBA/no_coop", "หลักสูตรฉบับปรับปรุงต่างจากฉบับเดิมอย่างไร"),
    ("DSBA/no_coop", "วิชาที่มีในหลักสูตรเก่า ไม่มีในหลักสูตรใหม่"),
    ("AIT", "มีหลักสูตรสองปริญญาไหม"),
    ("IT/coop", "หลักสูตรเวอร์ชันเก่ากับเวอร์ชันใหม่ต่างกันยังไง"),
])
def test_single_edition_answer(rel, question, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert answer.startswith(NOT_FOUND) and "ฉบับเดียว" in answer and "0 รายการ" not in answer, answer


# ---- ทางลัดที่พัง: ยังตอบต่อได้ (ตัวถัดไป/โมเดล) แต่ต้องเห็นใน log ว่าตัวไหนพัง ----
def test_shortcut_failure_is_logged(monkeypatch, caplog):
    def _broken_shortcut(conn, question):
        raise ValueError("canary")
    monkeypatch.setattr(m, "_SHORTCUTS", (_broken_shortcut,) + m._SHORTCUTS)
    with caplog.at_level(logging.WARNING, logger=m.__name__):
        answer = _ask("DSBA/no_coop", "หลักสูตรนี้ต้องเรียนกี่หน่วยกิต", monkeypatch)["answer"]
    assert answer == "หน่วยกิตรวมตลอดหลักสูตร 132 หน่วยกิต"
    assert any("_broken_shortcut" in r.getMessage() for r in caplog.records), [r.getMessage() for r in caplog.records]


# ---- ถ้อยคำใหม่ของ fixes 1-4 (ทดสอบ 2026-10-18: ทางลัดจับได้ 0/9 แล้วโมเดลตอบไม่พบหรือผิดเกือบหมด) ----
@pytest.mark.parametrize("rel, question, expect", [
    ("DSBA/no_coop", "เทอม 1 ปี 3 วิชาไหนต้องมีพื้นฐานจากวิชาอื่นก่อน", ["06026212", "06066300"]),
    ("DSBA/no_coop", "ปี3 เทอม1 มีวิชาที่ต้องเรียนวิชาอื่นมาก่อนไหม", ["06026212", "06066300"]),
    ("DSBA/no_coop", "ปีสี่เรียนอะไรบ้าง", ["รวมทั้งปี 18 หน่วยกิต", "06026215"]),
    ("DSBA/no_coop", "ชั้นปีที่ 4 ต้องลงวิชาอะไร", ["รวมทั้งปี 18 หน่วยกิต", "06026215"]),
    ("DSBA/no_coop", "ปี 4 ทั้งปีมีวิชาอะไรบ้าง", ["รวมทั้งปี 18 หน่วยกิต", "06026215"]),
    ("DSBA/no_coop", "เรียนไปแล้ว 100 หน่วยกิต เหลืออีกเท่าไหร่", ["ขาดอีก 32 หน่วยกิต"]),
    ("DSBA/no_coop", "ได้มา 100 หน่วยกิตแล้ว ต้องเก็บเพิ่มอีกเท่าไร", ["ขาดอีก 32 หน่วยกิต"]),
    ("AIT", "AIT แยกแผนสหกิจกับไม่สหกิจไหม", ["แผนเดียว", "06046443"]),
    ("AIT", "AIT มีให้เลือกไปสหกิจหรือเปล่า", ["แผนเดียว", "06046443"]),
])
def test_paraphrases_reach_shortcuts(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert all(e in answer for e in expect), answer


@pytest.mark.parametrize("question, expect", [
    ("ปีสี่เรียนอะไรบ้าง", "ปี 4เรียนอะไรบ้าง"),
    ("ปีสองเทอมหนึ่งมีวิชาอะไร", "ปี 2เทอม 1มีวิชาอะไร"),
    ("ปีสามารถลงวิชาเลือกได้กี่ตัว", "ปีสามารถลงวิชาเลือกได้กี่ตัว"),           # "สามารถ" ไม่ใช่เลข
    ("ภาคห้ามลงเกินกี่หน่วยกิต", "ภาคห้ามลงเกินกี่หน่วยกิต"),                   # "ห้าม" ไม่ใช่เลข
])
def test_spoken_term_numbers(question, expect):
    with _db("DSBA/no_coop") as conn:
        assert m._normalise_number_words(conn, question) == expect


# ---- probe ชุดที่ 3: ตกวิชาแล้วเรียนใหม่เทอมไหน (เดิมโมเดลตอบรหัสวิชาบังคับก่อนแบบมั่นใจผิดคำถาม) ----
@pytest.mark.parametrize("rel, question, expect", [
    ("DSBA/no_coop", "ถ้าตกวิชาการสร้างคลังข้อมูล ต้องรอเรียนใหม่เทอมไหน", ["06026212", "ปี 3 เทอม 1", "เทอม 1 ของปีการศึกษาถัดไป"]),
    ("DSBA/no_coop", "สอบตกแคลคูลัส 1 ต้องลงใหม่เมื่อไหร่", ["ปี 1 เทอม 1", "เทอม 1 ของปีการศึกษาถัดไป", "06026201"]),
    ("IT/coop", "ติด F ระบบเครือข่ายเบื้องต้น ต้องเรียนซ้ำเทอมไหน", ["06016413", "ปี 2 เทอม 1", "06016419", "06016423"]),
])
def test_retake_term(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert all(e in answer for e in expect) and "06066300" not in answer, answer


# ---- X กับ Y เรียนเทอมเดียวกันไหม (เดิมตกไปโมเดลแล้วได้ "ไม่พบ") ----
@pytest.mark.parametrize("rel, question, expect", [
    ("DSBA/no_coop", "แคลคูลัส 1 กับ แคลคูลัส 2 เรียนเทอมเดียวกันไหม", ["ไม่ใช่", "ปี 1 เทอม 1", "ปี 1 เทอม 2"]),
    ("DSBA/no_coop", "การเรียนรู้ของเครื่องเชิงประยุกต์กับการสร้างคลังข้อมูลอยู่ภาคเรียนเดียวกันหรือเปล่า", ["ใช่", "ปี 3 เทอม 1"]),
])
def test_two_courses_same_term(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert all(e in answer for e in expect), answer


# ---- "ต้องลงอะไร" / "เรียนอะไร" (ไม่มีคำว่า "วิชา") ในคำถามรายการรายเทอมและรายปี ----
@pytest.mark.parametrize("rel, question, expect", [
    ("BIT/no_coop", "BIT ไม่สหกิจ ปี 4 เทอม 2 ต้องลงอะไร", ["วิชาเลือกเสรี 1", "วิชาเลือกเสรี 2", "รวม 12 หน่วยกิต"]),
    ("DSBA/no_coop", "ปี 1 เทอม 2 ต้องลงอะไรบ้าง", ["06026201", "90644008"]),
    ("IT/coop", "ปี 1 เทอม 2 เรียนอะไร", ["06016408", "90644008"]),
    ("DSBA/no_coop", "ปี 4 ต้องลงอะไร", ["รวมทั้งปี 18 หน่วยกิต", "06026215"]),
])
def test_list_without_word_course(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert all(e in answer for e in expect), answer


# ---- กลุ่ม 2: คำถามผสม "ตก X จะกระทบวิชาไหน และต้องเลื่อนไปเรียนเทอมไหน" (เดิมตอบแค่ครึ่งแรก) ----
def test_fail_impact_with_retake_term(monkeypatch):
    answer = _ask("DSBA/no_coop", "ถ้าสอบตกแคลคูลัส 1 ตอนปี 1 เทอม 1 จะกระทบวิชาไหนบ้าง และต้องเลื่อนไปเรียนเทอมไหน", monkeypatch)["answer"]
    assert "06026201" in answer and "เทอม 1 ของปีการศึกษาถัดไป" in answer, answer


def test_fail_impact_without_term_ask_unchanged(monkeypatch):
    answer = _ask("DSBA/no_coop", "ตกแคลคูลัส 1 จะกระทบวิชาไหนบ้าง", monkeypatch)["answer"]
    assert "06026201" in answer and "ปีการศึกษาถัดไป" not in answer, answer


# ---- "ทั้งทางตรงและทางอ้อม" = วิชาบังคับก่อนทุกชั้น (เดิมตกไปโมเดลแล้วตอบไม่พบ) ----
@pytest.mark.parametrize("rel, question, expect", [
    ("DSBA/no_coop", "แคลคูลัส 2 ต้องผ่านวิชาอะไรมาก่อนบ้าง ทั้งทางตรงและทางอ้อม", ["06026200", "โดยตรง"]),
    ("DSBA/no_coop", "การเรียนรู้ของเครื่องเชิงประยุกต์ต้องผ่านวิชาอะไรมาก่อนบ้าง ทั้งทางตรงและทางอ้อม", ["ไม่มีวิชาบังคับก่อน"]),
    ("IT/coop", "06016421 ต้องผ่านวิชาอะไรมาก่อนบ้าง ทั้งทางตรงและทางอ้อม", ["06016413"]),
])
def test_direct_and_indirect_prerequisites(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert all(e in answer for e in expect) and not answer.startswith(NOT_FOUND), answer


# ---- ไม่ไปสหกิจต้องเรียนอะไรแทน = เทอมสหกิจของแผนสหกิจ เทียบกับเทอมเดียวกันของแผนไม่สหกิจ ----
@pytest.mark.parametrize("rel, question, expect", [
    ("DSBA/no_coop", "ถ้าไม่ไปสหกิจ ต้องเรียนวิชาอะไรแทน", ["ปี 4 เทอม 2", "06026259", "วิชาเลือกเสรี 1", "วิชาเลือกหมวดวิชาศึกษาทั่วไป"]),
    ("IT/no_coop", "ไม่ทำสหกิจต้องลงอะไรแทน", ["ปี 3 เทอม 2", "06016481", "06066100", "วิชาเลือกทางเทคโนโลยีสารสนเทศ 1"]),
    ("BIT/coop", "ถ้าไม่เลือกสหกิจ ต้องเรียนอะไรแทน", ["ปี 4 เทอม 2", "06036147", "วิชาเลือกเสรี 2"]),
])
def test_no_coop_instead(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert all(e in answer for e in expect), answer


# ---- กลุ่ม 3: SQL ของโมเดลล้มสองรอบ = ตอบ 200 "ไม่พบ ... ลองถามใหม่" แทน HTTP 422 (กติกาสอบนับ HTTP error เป็น 0, preflight เจอ 1 ใน 6 ครั้ง) ----
def _api_ask_with(monkeypatch, error):
    from fastapi import HTTPException
    from curriculum_app import main as api
    from curriculum_app.schemas import AskRequest, AskResponse

    def fake_ask(conn, question, verbose=False):
        return {"question": question, "sql": "SELECT broken FROM nowhere", "rows": [], "error": error, "citations": [],
                "citation_text": "", "answer_type": "ai", "answer": "ระบบแปลงคำถามเป็นคำค้นไม่ได้ กรุณาลองถามใหม่ให้เจาะจงขึ้น"}
    monkeypatch.setattr(api.lab8b, "ask", fake_ask)
    try:
        result = api.ask(AskRequest(question="วิชาเลือกเสรีเลือกเรียนจากที่ไหนได้บ้าง", program="dsba_no_coop"))
    except HTTPException as exc:
        return exc.status_code, None
    return 200, AskResponse(**result)


def test_api_sql_failure_is_answered_not_422(monkeypatch):
    status, body = _api_ask_with(monkeypatch, "OperationalError: no such column: broken")
    assert status == 200
    assert body.answer.startswith(NOT_FOUND) and "ลองถามใหม่" in body.answer and body.rows == [] and body.sql is None


@pytest.mark.parametrize("error", ["ConnectionError: refused", "QueryBudgetExceeded: too many steps"])
def test_api_infra_and_budget_errors_stay_503(monkeypatch, error):
    assert _api_ask_with(monkeypatch, error)[0] == 503


@pytest.mark.parametrize("error", ["ValueError: อนุญาตเฉพาะ SELECT หรือ WITH เท่านั้น", "ValueError: พบคำสั่งที่ไม่อนุญาตใน SQL"])
def test_api_guard_rejection_says_refused(monkeypatch, error):
    """"ลบข้อมูลวิชาทั้งหมด" → โมเดลเขียน DELETE → guard_sql ปฏิเสธ: ตอบ 200 ว่าระบบไม่แก้ไข/ลบข้อมูล (ไม่ใช่ "แปลงคำถามไม่ได้")"""
    status, body = _api_ask_with(monkeypatch, error)
    assert status == 200 and "ไม่แก้ไขหรือลบข้อมูล" in body.answer and "ลองถามใหม่" not in body.answer, body


# ---- กลุ่ม 4: ask() เรียกโมเดลด้วย timeout สั้น (เดิม 600 วินาที = หน้าเว็บค้างได้ 10 นาทีถ้า Ollama ค้าง) งานสกัดทั้งเล่มยังใช้ค่าเดิม ----
def test_ask_uses_short_model_timeout(monkeypatch):
    seen = []

    def fake_generate(prompt, fmt=None, timeout=600, **kw):
        seen.append(timeout)
        return '{"sql": "SELECT NULL WHERE 0"}'
    monkeypatch.setattr(m, "ollama_generate", fake_generate)
    with _db("DSBA/no_coop") as conn:
        m.ask(conn, "นายกรัฐมนตรีไทยคนปัจจุบันคือใคร", verbose=False)
    assert seen and all(t == m.ASK_TIMEOUT for t in seen) and m.ASK_TIMEOUT == 120, seen


def test_extract_keeps_long_timeout():
    import inspect
    assert inspect.signature(m.ollama_generate).parameters["timeout"].default == 600


# ---- กลุ่ม 4: ยกข้อความเล่ม (ไม่ให้โมเดลแต่ง) 8 หัวข้อ จาก runs/<BOOK>/book_quotes.json; คำถามและหน้ามาจากการสำรวจ OCR ทั้ง 4 เล่ม ----
BOOK_QUOTE_CASES = [
    ('DSBA/no_coop', 'plo', 'ผลการเรียนรู้ที่คาดหวังของหลักสูตร DSBA มีอะไรบ้าง', 12, 'ชั้นปีที่ 4 มีความสามารถสืบค้น'),
    ('IT/no_coop', 'plo', 'หลักสูตร IT มี PLO อะไรบ้าง', 16, 'PLO 1 : บัณฑิตสามารถเข้าใจและอธิบายความรู้พื้นฐาน'),
    ('AIT', 'plo', 'What are the program learning outcomes of AIT?', 11, 'PLO 1.1 สามารถจดจำและอธิบายความรู้ด้านคณิตศาสตร์'),
    ('BIT/no_coop', 'plo', 'ผลลัพธ์การเรียนรู้ระดับหลักสูตร BIT คืออะไร', 15, 'บัณฑิตมีทักษะทางด้านภาษาอังกฤษในการสื่อสาร'),
    ('BIT/no_coop', 'free_elective', 'วิชาเลือกเสรีเลือกเรียนวิชาคณะอื่นได้ไหม', 25, 'เลือกเรียนจากรายวิชาที่เปิดสอนในสถาบัน'),
    ('IT/no_coop', 'free_elective', 'Can I take any course as a free elective in IT?', 30, 'จํานวนไม่น้อยกว่า 6 หน่วยกิต'),
    ('AIT', 'free_elective', 'วิชาเลือกเสรีของ AIT ลงอะไรก็ได้หรือเปล่า', 22, 'นักศึกษาสามารถเลือกเรียนในรายวิชา'),
    ('DSBA/no_coop', 'grading', 'หลักเกณฑ์การให้เกรดของหลักสูตร DSBA เป็นยังไง', 78, 'ระดับปริญญาตรี พ.ศ. 2564 (ภาคผนวก ก)'),
    ('AIT', 'grading', 'ระบบการให้ระดับคะแนนของ AIT เป็นแบบไหน', 67, 'พ.ศ. 2565'),
    ('IT/no_coop', 'grading', 'What is the grading system of the IT program?', 89, 'เป็นไปตามข้อบังคับสถาบัน'),
    ('DSBA/no_coop', 'education_system', 'หลักสูตร DSBA ใช้ระบบการจัดการศึกษาแบบไหน', 13, 'ใช้ระบบการศึกษาแบบทวิภาค'),
    ('DSBA/no_coop', 'education_system', 'DSBA มีภาคฤดูร้อนไหม', 13, '1.2 การจัดการศึกษาภาคการศึกษาพิเศษ (ภาคฤดูร้อน) ไม่มี'),
    ('IT/no_coop', 'education_system', 'ภาคฤดูร้อนของ IT กี่สัปดาห์', 18, 'จํานวน 8 สัปดาห์'),
    ('AIT', 'education_system', 'Is there a summer semester in AIT?', 16, 'มีภาคการศึกษาพิเศษ'),
    ('BIT/no_coop', 'education_system', 'BIT ปีหนึ่งมีกี่เทอม', 16, '2 ภาคการศึกษาปกติ'),
    ('AIT', 'semester_calendar', 'AIT เปิดเทอมเดือนไหน', 16, 'ภาคการศึกษาที่ 1 เดือนกรกฎาคม - เดือนพฤศจิกายน'),
    ('DSBA/no_coop', 'semester_calendar', 'ภาคการศึกษาที่ 2 ของ DSBA เริ่มเดือนอะไร', 13, 'ภาคการศึกษาที่ 2 เดือนมกราคม - เดือนเมษายน'),
    ('BIT/no_coop', 'semester_calendar', 'When does the first semester start in BIT?', 16, 'เดือนสิงหาคม - เดือนพฤศจิกายน'),
    ('IT/no_coop', 'semester_calendar', 'หลักสูตร IT เรียนวันไหน', 18, 'วัน - เวลาราชการปกติ'),
    ('DSBA/no_coop', 'credit_transfer', 'DSBA เทียบโอนหน่วยกิตได้ไหม', 14, 'เรื่องการลงทะเบียนเรียนข้ามสถาบันอุดมศึกษา (ภาคผนวก ค)'),
    ('IT/no_coop', 'credit_transfer', 'ลงทะเบียนเรียนข้ามมหาวิทยาลัยได้หรือเปล่า', 20, 'เรื่องการลงทะเบียนเรียนข้ามสถาบันอุดมศึกษา'),
    ('AIT', 'credit_transfer', 'Can I transfer credits from another university to AIT?', 18, 'ประกาศสถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง'),
    ('BIT/no_coop', 'language', 'BIT เรียนเป็นภาษาอังกฤษไหม', 6, 'หลักสูตรจัดการศึกษาเป็นภาษาอังกฤษ'),
    ('DSBA/no_coop', 'language', 'หลักสูตร DSBA ใช้ภาษาอะไรในการเรียนการสอน', 3, 'เป็นภาษาไทยและภาษาอังกฤษ'),
    ('AIT', 'language', 'What language of instruction does AIT use?', 6, 'หลักสูตรจัดการศึกษาเป็นภาษาไทยและภาษาอังกฤษ'),
    ('IT/no_coop', 'language', 'IT เป็นหลักสูตรนานาชาติหรือเปล่า', 7, 'เป็นภาษาไทยและภาษาอังกฤษ'),
    ('DSBA/no_coop', 'coop_timing', 'สหกิจศึกษาของ DSBA ต้องไปกี่สัปดาห์', 62, 'เป็นเวลาอย่างน้อย 16 สัปดาห์'),
    ('BIT/no_coop', 'coop_timing', 'ระยะเวลาสหกิจของ BIT นานเท่าไร', 65, 'ไม่น้อยกว่า 30 ชั่วโมง'),
    ('IT/no_coop', 'coop_timing', 'How long is the co-op in IT?', 73, 'อย่างน้อย 16 สัปดาห์'),
    ('AIT', 'coop_timing', 'สหกิจ AIT ทำงานกี่วันต่อสัปดาห์', 27, '5 วันต่อสัปดาห์'),
]
BOOK_QUOTE_NEGATIVES = [
    'ปรัชญาของหลักสูตร DSBA คืออะไร',
    'หลักสูตรนี้ได้ปริญญาอะไร',
    'จบแล้วทำงานอะไรได้บ้าง',
    'เกณฑ์การสำเร็จการศึกษาของ IT คืออะไร',
    'ต้องได้เกรดเฉลี่ยเท่าไรถึงจะจบ',
    'วิชาเลือกเสรีต้องลงตอนปีไหน',
    'วิชาเลือกเสรีกี่หน่วยกิต',
    'สหกิจศึกษาอยู่ปีไหนเทอมไหน',
    'วิชา 06016315 ได้เกรดอะไรถึงผ่าน',
    'ภาษาอังกฤษพื้นฐาน 1 เรียนปีไหน',
    'ภาคฤดูร้อนต้องลงวิชาอะไรบ้าง',
    'ปี 1 เทอม 1 เรียนอะไรบ้าง',
    'มาตรฐานผลการเรียนรู้ของวิชา Data Mining มีอะไร',
    'วันนี้อากาศเป็นยังไง',
    'วิชา Data Mining สอนเป็นภาษาอะไร',
    'สหกิจได้กี่หน่วยกิต',
]


@pytest.mark.parametrize("rel, topic, question, pdf_page, substring", BOOK_QUOTE_CASES)
def test_book_quote(rel, topic, question, pdf_page, substring, monkeypatch):
    result = _ask(rel, question, monkeypatch)
    assert result["answer_type"] == "ocr" and result["rows"][0]["topic"] == topic, (result["answer_type"], result["answer"][:120])
    def norm(s):                                                   # OCR spacing and ำ / ํา differ between the survey and the quote
        return s.replace("ํา", "ำ").replace(" ", "")
    assert result["rows"][0]["pdf_page"] == pdf_page and norm(substring) in norm(result["answer"]), result["answer"][:200]


@pytest.mark.parametrize("question", BOOK_QUOTE_NEGATIVES)
def test_book_quote_not_triggered(question):
    with _db("DSBA/no_coop") as conn:
        assert m._book_quote_answer(conn, m._prepare_question(conn, question)) is None


def test_book_quote_citation_uses_printed_page(monkeypatch):
    result = _ask("BIT/no_coop", "หลักเกณฑ์การให้เกรดของ BIT เป็นยังไง", monkeypatch)
    assert result["rows"][0]["printed_page"] == "72" and "72" in result["citation_text"], result["citation_text"]



def test_free_elective_rule_keeps_existing_shortcut(monkeypatch):
    """"วิชาเลือกเสรีมีเงื่อนไขอะไรบ้าง" ทางลัดเดิม (ช่องวิชาเลือกเสรีในแผน) ตอบก่อนอยู่แล้วและถูก: ทางลัดยกข้อความเล่มอยู่ท้ายลำดับจึงไม่แย่ง"""
    result = _ask("DSBA/no_coop", "วิชาเลือกเสรีมีเงื่อนไขอะไรบ้าง", monkeypatch)
    assert result["answer_type"] == "database" and "เลือกเรียนจากรายวิชาที่เปิดสอนในสถาบัน" in result["answer"], result["answer"][:200]


# ---- ปรับก่อนสอบ (2026-10-18 คืน): ถ้อยคำที่หลุดจากการทดสอบหน้าเว็บ, ปฏิเสธคำสั่งเขียนข้อมูล, PLO ขึ้นบรรทัดใหม่ ----
@pytest.mark.parametrize("rel, topic, question, substring", [
    ("AIT", "education_system", "ระบบการศึกษาเป็นแบบไหน", "ทวิภาค"),
    ("DSBA/coop", "education_system", "หลักสูตรนี้ใช้ระบบการศึกษาอะไร", "ทวิภาค"),
    ("IT/coop", "coop_timing", "ไปสหกิจช่วงไหน", "ของปีการศึกษาที 3"),
    ("DSBA/coop", "coop_timing", "ออกสหกิจตอนไหน", "ของปีการศึกษาที่ 4"),
    ("BIT/coop", "coop_timing", "ไปสหกิจศึกษาเมื่อไหร่", "ปีการศึกษาที่ 4"),
])
def test_book_quote_new_phrasings(rel, topic, question, substring, monkeypatch):
    result = _ask(rel, question, monkeypatch)
    assert result["answer_type"] == "ocr" and result["rows"][0]["topic"] == topic, (result["answer_type"], result["answer"][:120])
    assert substring in result["answer"], result["answer"][:200]


@pytest.mark.parametrize("question", ["สหกิจศึกษาอยู่ปีไหนเทอมไหน", "ระบบการศึกษาวิชา 06026200 เป็นแบบไหน", "สหกิจได้กี่หน่วยกิต"])
def test_book_quote_new_phrasings_negative(question):
    with _db("DSBA/coop") as conn:
        assert m._book_quote_answer(conn, m._prepare_question(conn, question)) is None


WRITE_REFUSED = "ระบบตอบได้เฉพาะการค้นข้อมูลหลักสูตร ไม่แก้ไขหรือลบข้อมูล"


@pytest.mark.parametrize("question", [
    "ลบข้อมูลวิชาทั้งหมด",
    "แก้หน่วยกิตวิชาแคลคูลัส 1 เป็น 4",
    "ช่วยเปลี่ยนชื่อวิชา 06026200 เป็น Calculus I",
    "เพิ่มวิชาใหม่ลงในปี 1 เทอม 1",
    "DELETE FROM course",
    "drop table course",
    "Delete all courses",
    "update the credits of 06026200 to 4",
])
def test_write_request_refused_by_rule(question, monkeypatch):
    result = _ask("DSBA/coop", question, monkeypatch)
    assert result["answer_type"] == "rule" and WRITE_REFUSED in result["answer"], result["answer"][:160]


@pytest.mark.parametrize("rel, question", [
    ("DSBA/coop", "เปลี่ยนแผนจากสหกิจเป็นไม่สหกิจได้ไหม"),
    ("DSBA/coop", "ถอนวิชาแคลคูลัส 1 จะกระทบวิชาอะไรบ้าง"),
    ("DSBA/coop", "ลงเพิ่มได้กี่หน่วยกิต"),
    ("DSBA/coop", "แก้เกรดได้ไหม"),
    ("DSBA/coop", "อยากเพิ่มวิชาเลือกเสรีต้องทำยังไง"),
    ("DSBA/coop", "What are the prerequisites of 06026201?"),
    ("DSBA/coop", "06026200 แคลคูลัส 1 กี่หน่วยกิต"),
])
def test_write_guard_leaves_questions_alone(rel, question):
    assert m._write_request_answer(question) is None


def test_plo_items_on_their_own_lines(monkeypatch):
    result = _ask("IT/no_coop", "หลักสูตร IT มี PLO อะไรบ้าง", monkeypatch)
    lines = result["answer"].splitlines()
    assert sum(1 for line in lines if line.startswith("PLO ")) >= 6, result["answer"][:300]
    assert "\nPLO 1 :" in result["rows"][0]["body"]


def test_plo_line_breaks_only_for_plo(monkeypatch):
    result = _ask("BIT/no_coop", "เกณฑ์การให้เกรดเป็นอย่างไร", monkeypatch)
    assert "\n" not in result["answer"]


# ---- ปรับก่อนสอบรอบ 2: วิชาตามคำในชื่อ + ปี/เทอม, คำถามอังกฤษเรื่องสอบตก ----
@pytest.mark.parametrize("question, codes, absent", [
    ("วิชาที่มีคำว่า DATA ในชื่อและเรียนปี 3 มีอะไรบ้าง", {"06026212", "06026213", "06026214"}, {"06026206"}),
    ("วิชาที่มีคำว่า data ในชื่อ เรียนปี 2 เทอม 2 มีอะไรบ้าง", {"06026207", "06026208", "06026209", "06066301"}, {"06026206", "06066300"}),
    ("ปี 2 มีวิชาที่ชื่อมีคำว่าข้อมูลอะไรบ้าง", {"06026206", "06066300", "06026207"}, {"06026212"}),
])
def test_name_keyword_by_term(question, codes, absent, monkeypatch):
    result = _ask("DSBA/coop", question, monkeypatch)
    got = {r["code"] for r in result["rows"]}
    assert codes <= got and not (absent & got) and "คำว่า" in result["answer"], (result["answer_type"], result["answer"][:200])


def test_name_keyword_by_term_none_found(monkeypatch):
    result = _ask("DSBA/coop", "วิชาที่มีคำว่า ROBOT ในชื่อและเรียนปี 3 มีอะไรบ้าง", monkeypatch)
    assert result["rows"] == [] and "ไม่มีวิชา" in result["answer"], result["answer"][:200]


@pytest.mark.parametrize("question", ["มีวิชาที่ชื่อมีคำว่าข้อมูลกี่วิชา", "ปี 3 เทอม 1 เรียนอะไรบ้าง", "วิชา DATA WAREHOUSING เรียนปีไหน"])
def test_name_keyword_by_term_leaves_others(question):
    with _db("DSBA/coop") as conn:
        assert m._name_keyword_term_answer(conn, m._prepare_question(conn, question)) is None


@pytest.mark.parametrize("question, expect", [
    ("If I fail Calculus 1, which courses are affected and when do I retake it?", "ถ้าสอบตก Calculus 1 จะกระทบวิชาไหน และต้องเรียนใหม่เทอมไหน"),
    ("If I fail 06026200, which courses are affected?", "ถ้าสอบตก 06026200 จะกระทบวิชาไหน"),
    ("When can I retake Calculus 1 if I fail it?", "ถ้าสอบตก Calculus 1 ต้องเรียนใหม่เทอมไหน"),
    ("What happens if I fail Calculus 1?", "ถ้าสอบตก Calculus 1 จะกระทบวิชาไหน"),
])
def test_english_fail_questions(question, expect):
    import english_questions
    assert english_questions.english_to_thai(question) == expect


def test_english_fail_combined_answer(monkeypatch):
    result = _ask("DSBA/coop", "If I fail Calculus 1, which courses are affected and when do I retake it?", monkeypatch)
    assert "06026201" in result["answer"] and "เทอม 1 ของปีการศึกษาถัดไป" in result["answer"], result["answer"][:300]


# ---- ปรับก่อนสอบรอบ 3 (probe 4): ชื่อแผนที่เป็นหัวเรื่องของคำถาม, "อันไหนก่อน", "จบเลยไหม" ----
@pytest.mark.parametrize("rel, question, expect", [
    ("BIT/coop", "BIT สหกิจอยู่ปีไหน", "ปี 4 เทอม 2"),
    ("DSBA/coop", "DSBA สหกิจอยู่ปีไหน", "ปี 4 เทอม 2"),
    ("IT/coop", "IT สหกิจไปช่วงไหน", "ของปีการศึกษาที 3"),
])
def test_plan_word_kept_when_it_is_the_subject(rel, question, expect, monkeypatch):
    result = _ask(rel, question, monkeypatch)
    assert expect in result["answer"], result["answer"][:200]


def test_plan_name_still_stripped(monkeypatch):
    result = _ask("DSBA/coop", "DSBA สหกิจ ปี 4 เทอม 2 เรียนอะไรบ้าง", monkeypatch)
    assert "ปี 4 เทอม 2" in result["answer"] and result["rows"], result["answer"][:200]


@pytest.mark.parametrize("question", ["แคลคูลัส 1 กับแคลคูลัส 2 ต้องเรียนอันไหนก่อน", "แคลคูลัส 2 กับแคลคูลัส 1 ตัวไหนก่อน"])
def test_which_first_more_phrasings(question, monkeypatch):
    result = _ask("DSBA/coop", question, monkeypatch)
    assert result["answer"].startswith("แคลคูลัส 1 (06026200)") and "เรียนก่อน" in result["answer"], result["answer"][:200]


@pytest.mark.parametrize("question", ["ถ้าเรียนครบ 129 หน่วยกิตจบเลยไหม", "เก็บได้ 120 หน่วยกิต จบเลยมั้ย"])
def test_graduation_jop_loei(question, monkeypatch):
    result = _ask("IT/coop", question, monkeypatch)
    assert "หน่วยกิต" in result["answer"] and ("ครบ" in result["answer"] or "ขาด" in result["answer"]), result["answer"][:200]


# ---- ปรับก่อนสอบรอบ 4: จุดอ่อนที่เหลือจาก probe 4 ----
@pytest.mark.parametrize("question, start", [
    ("ถ้าผ่านแคลคูลัส 1 แล้ว ลงแคลคูลัส 2 ได้เลยไหม", "ได้ —"),
    ("ผ่านแคลคูลัส 1 แล้ว ลงแคลคูลัส 2 ได้ไหม", "ได้ —"),
    ("ผ่านพีชคณิตเชิงเส้นแล้ว ลงแคลคูลัส 2 ได้ไหม", "ยังไม่ได้ —"),
])
def test_passed_one_course_can_register(question, start, monkeypatch):
    result = _ask("DSBA/coop", question, monkeypatch)
    assert result["answer"].startswith(start) and "06026200" in result["answer"], result["answer"][:200]


def test_failed_two_course_form_unchanged(monkeypatch):
    result = _ask("DSBA/coop", "ถ้ายังไม่ผ่านแคลคูลัส 1 ลงแคลคูลัส 2 ได้ไหม", monkeypatch)
    assert result["answer"].startswith("ไม่ได้ —"), result["answer"][:200]


@pytest.mark.parametrize("question", ["วิชาเฉพาะบังคับมีกี่หน่วยกิต", "หมวดวิชาเฉพาะบังคับต้องเรียนกี่หน่วยกิต"])
def test_required_major_credits(question, monkeypatch):
    result = _ask("DSBA/coop", question, monkeypatch)
    assert "96" in result["answer"] and "กลุ่มวิชาแกน 45" in result["answer"] and "12 หน่วยกิต" != result["answer"].strip(), result["answer"][:300]


def test_order_of_three_courses(monkeypatch):
    result = _ask("DSBA/coop", "แคลคูลัส 1 แคลคูลัส 2 และพีชคณิตเชิงเส้น ต้องเรียนตามลำดับยังไง", monkeypatch)
    a = result["answer"]
    assert "06026200" in a and "06026201" in a and "06026202" in a and a.index("06026201") > a.index("06026200"), a[:300]


@pytest.mark.parametrize("rel, question, expect", [
    ("DSBA/coop", "วิชาแคลคุลัส 2 กี่หน่วยกิต", "06026201"),
    ("IT/no_coop", "ถ้าไม่ผ่านวิชาโครงสร้างข้อมูล จะกระทบอะไร", "06066301"),
])
def test_near_course_names(rel, question, expect, monkeypatch):
    result = _ask(rel, question, monkeypatch)
    assert expect in result["answer"], result["answer"][:200]


# ---- "คุณหมายถึง" ส่งคำที่พิมพ์ผิดกลับไปให้หน้าเว็บทำปุ่ม "ใช่ ถามใหม่" ----
@pytest.mark.parametrize("rel, question, typed, code", [
    ("DSBA/coop", "วิชาแคลคุลัส 2 กี่หน่วยกิต", "แคลคุลัส 2", "06026201"),
    ("IT/no_coop", "ถ้าไม่ผ่านวิชาโครงสร้างข้อมูล จะกระทบอะไร", "โครงสร้างข้อมูล", "06066301"),
    ("DSBA/coop", "Calcuus 1 กี่หน่วยกิต", "Calcuus 1", "06026200"),
])
def test_near_match_row_carries_typed_text(rel, question, typed, code, monkeypatch):
    row = _ask(rel, question, monkeypatch)["rows"][0]
    assert row.get("near_match") and row["code"] == code and row["typed"] == typed, row


# ---- ปรับก่อนสอบรอบ 5 (probe 5) ----
@pytest.mark.parametrize("question", ["เพิ่มวิชาเลือกได้กี่ตัว", "ลบวิชาออกได้กี่วิชา", "เปลี่ยนแผนได้เมื่อไหร่", "แก้เกรดได้ที่ไหน"])
def test_write_guard_ignores_questions_with_question_words(question):
    assert m._write_request_answer(question) is None


def test_remaining_credits_with_year_mentioned(monkeypatch):
    result = _ask("DSBA/no_coop", "ผมอยู่ปี 2 สะสมได้ 60 หน่วยกิต ขาดอีกเท่าไหร่", monkeypatch)
    assert result["answer"].startswith("ขาดอีก 72 หน่วยกิต"), result["answer"][:200]


@pytest.mark.parametrize("question", ["ปี 4 เทอม 2 มีช่องวิชาเลือกกี่ช่อง", "ปี 4 เทอม 2 มีวิชาเลือกกี่ช่อง"])
def test_term_slot_count(question, monkeypatch):
    result = _ask("DSBA/no_coop", question, monkeypatch)
    assert "3 ช่อง" in result["answer"] and "วิชาเลือกเสรี 1" in result["answer"], result["answer"][:200]


@pytest.mark.parametrize("question, start", [
    ("ลงแคลคูลัส 2 พร้อมแคลคูลัส 1 ได้ไหม", "ไม่ได้ —"),
    ("เรียนแคลคูลัส 1 กับแคลคูลัส 2 พร้อมกันได้ไหม", "ไม่ได้ —"),
    ("ลงแคลคูลัส 1 และแคลคูลัส 2 ในเทอมเดียวกันได้ไหม", "ไม่ได้ —"),
    ("ลงพีชคณิตเชิงเส้นพร้อมแคลคูลัส 2 ได้ไหม", "ได้ —"),
])
def test_register_two_courses_together(question, start, monkeypatch):
    result = _ask("DSBA/coop", question, monkeypatch)
    assert result["answer"].startswith(start), result["answer"][:200]


def test_two_term_credit_difference(monkeypatch):
    result = _ask("DSBA/no_coop", "ปี 2 เทอม 1 กับปี 2 เทอม 2 ต่างกันกี่หน่วยกิต", monkeypatch)
    assert "18" in result["answer"] and "21" in result["answer"] and "ต่างกัน 3 หน่วยกิต" in result["answer"], result["answer"][:200]


def test_course_that_unlocks_most(monkeypatch):
    result = _ask("DSBA/no_coop", "วิชาไหนเป็นวิชาบังคับก่อนของหลายวิชาที่สุด", monkeypatch)
    assert result["answer"].startswith("06066300") or "06066300 แนวคิดระบบฐานข้อมูล" in result["answer"][:80], result["answer"][:200]


def test_free_elective_credits_from_book_when_structure_missing(monkeypatch):
    result = _ask("BIT/no_coop", "วิชาเลือกเสรีกี่หน่วยกิต", monkeypatch)
    assert "6 หน่วยกิต" in result["answer"] and "ไม่มีข้อมูลโครงสร้าง" not in result["answer"], result["answer"][:200]


# ---- ปรับก่อนสอบรอบ 6: จบช้าไหม, ปรับปรุงปีไหน, SQL ดิบ ----
@pytest.mark.parametrize("question", ["ถ้าตกวิชาการสร้างคลังข้อมูลจะจบช้าไหม", "ถ้าสอบตกแคลคูลัส 1 จะทำให้จบช้าหรือเปล่า"])
def test_fail_graduate_late(question, monkeypatch):
    result = _ask("DSBA/coop", question, monkeypatch)
    a = result["answer"]
    assert "ต้องลงเรียนใหม่" in a and "จบช้า" in a, a[:300]


@pytest.mark.parametrize("rel, question, year", [
    ("DSBA/coop", "หลักสูตรนี้ปรับปรุงปีไหน", "2565"),
    ("IT/no_coop", "หลักสูตรปรับปรุงเมื่อไหร่", "2565"),
    ("BIT/coop", "หลักสูตรนี้เป็นฉบับปีอะไร", "2565"),
    ("AIT", "หลักสูตรนี้ปรับปรุงปีไหน", "2566"),
])
def test_revision_year(rel, question, year, monkeypatch):
    result = _ask(rel, question, monkeypatch)
    assert year in result["answer"] and "พ.ศ." in result["answer"], result["answer"][:200]


@pytest.mark.parametrize("question", ["หลักสูตรนี้เรียนกี่ปี", "ปีไหนเรียนหนักที่สุด", "หลักสูตรนี้ปีไหนเรียนหนักที่สุด", "ปี 1 เทอม 1 เรียนอะไร"])
def test_revision_year_leaves_others(question):
    with _db("DSBA/coop") as conn:
        assert m._revision_year_answer(conn, m._prepare_question(conn, question)) is None


@pytest.mark.parametrize("question", ["SELECT * FROM course", "select code, name_th from course where year = 1", "WITH x AS (SELECT 1) SELECT * FROM x"])
def test_raw_sql_is_not_run(question, monkeypatch):
    result = _ask("DSBA/coop", question, monkeypatch)
    assert result["answer_type"] == "rule" and "SQL" in result["answer"] and "ถูกปฏิเสธ" in result["answer"], result["answer"][:200]


# ---- ปรับก่อนสอบรอบ 7: "เพิ่มวิชาเลือกได้กี่ตัว" — โมเดลเคยอ่าน credits_required=6 (หน่วยกิต) เป็น "6 วิชาเลือก" ----
def _slots(conn, y=None):
    where, args = ("WHERE year = ?", (y,)) if y else ("", ())
    return conn.execute(f"SELECT COUNT(*), SUM(credits) FROM plan_slot {where}", args).fetchone()


@pytest.mark.parametrize("rel", PLANS)
@pytest.mark.parametrize("question", ["เพิ่มวิชาเลือกได้กี่ตัว", "ลงวิชาเลือกได้กี่วิชา", "วิชาเลือกเรียนได้กี่วิชา", "เลือกวิชาเลือกได้กี่ตัว"])
def test_elective_slots_whole_plan(rel, question, monkeypatch):
    with _db(rel) as conn:
        n, credits = _slots(conn)
    result = _ask(rel, question, monkeypatch)
    a = result["answer"]
    assert f"{n} ช่อง" in a and f"รวม {credits} หน่วยกิต" in a and "ไม่ได้กำหนดจำนวนวิชา" in a, a[:300]
    assert result["answer_type"] == "database" and result.get("citation_text"), result.get("citation_text")


def test_elective_slots_one_year(monkeypatch):
    with _db("DSBA/no_coop") as conn:
        n, credits = _slots(conn, 4)
    a = _ask("DSBA/no_coop", "ปี 4 ลงวิชาเลือกได้กี่วิชา", monkeypatch)["answer"]
    assert a.startswith("ปี 4") and f"{n} ช่อง" in a, a[:300]          # มีปี = ทางลัดเดิม "ปี 4 มีวิชาเลือก 0 วิชา (และมีช่อง…อีก 5 ช่อง)" ตอบอยู่แล้ว


@pytest.mark.parametrize("question", ["หลักสูตรนี้มีวิชาเลือกกี่วิชา", "วิชาเลือกเสรีเลือกได้กี่หน่วยกิต", "ปี 4 เทอม 2 มีช่องวิชาเลือกกี่ช่อง",
                                      "วิชาเลือกกลุ่มวิทยาการข้อมูลเลือกได้กี่วิชา", "เลือกวิชาเลือกได้ไหม", "ปี 3 เทอม 1 เรียนอะไร"])
def test_elective_slots_leaves_others(question):
    with _db("DSBA/coop") as conn:
        assert m._elective_slots_answer(conn, m._prepare_question(conn, question)) is None
