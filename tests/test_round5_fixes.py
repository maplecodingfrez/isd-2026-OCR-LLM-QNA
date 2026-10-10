"""รอบ 5: คำถามที่เคยหลุดไปให้โมเดลเดา (ห้ามถามในคลิป 3 ข้อสุดท้าย)
1) "วิชาเลือกเสรีเรียนได้ปีไหนเทอมไหน" แผน IT สหกิจ: ไม่มีช่อง plan_slot ของเลือกเสรี → กฎเดิมคืน None ให้โมเดลเดา SQL "เทอมหน่วยกิตมากสุด"
   ได้รายการปี/เทอมที่ผิดแต่ดูสมเหตุสมผล → ต้อง "ไม่พบ" ห้ามเดา (โน้ตหมวดใน plan_item ไม่ใช้: เทียบเล่มแล้ว 06016426/27 เป็นกลุ่มเลือก IT)
2) "วิชาสหกิจศึกษาต้องผ่านเงื่อนไขอะไรก่อน": "เงื่อนไข…ก่อน" = วิชาบังคับก่อน → ใช้กฎวิชาบังคับก่อนเดิม (ไม่ไปถามโมเดล)
3) "ภาคฤดูร้อนต้องเรียนวิชาอะไร": ทุกแผนมีแค่ภาค 1-2 → "ไม่พบ" ถูกต้องอยู่แล้ว (กันไม่ให้ถูกแก้จนเดา)"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
NOT_FOUND = m._NOT_FOUND[0]


def _ask(rel, question, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("must be answered by a rule, not the model"))
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        return m.ask(conn, question, verbose=False)


@pytest.mark.parametrize("question", [
    "วิชาเลือกเสรีเรียนได้ปีไหนเทอมไหน",
    "วิชาเลือกเสรีต้องลงตอนปีไหนเทอมไหน",
])
def test_it_coop_without_free_elective_slots_is_not_found(question, monkeypatch):
    """เล่ม IT สหกิจปี 3 เทอม 1 มี "กลุ่มวิชาเลือกของ IT" (06016426/27) ไม่ใช่วิชาเลือกเสรี — โน้ตหมวดใน plan_item จากการอ่าน OCR ห้ามเอามาตอบ
    ไม่มีช่อง "วิชาเลือกเสรี N" ใน plan_slot = ไม่พบ (เดิมโมเดลเดา "เทอมหน่วยกิตมากสุด" เป็นรายการปี/เทอมที่ผิด)"""
    result = _ask("IT/coop", question, monkeypatch)
    assert result["answer"] == NOT_FOUND


def test_free_elective_slots_still_answered_from_plan_slot(monkeypatch):
    result = _ask("DSBA/coop", "วิชาเลือกเสรีเรียนได้ปีไหนเทอมไหน", monkeypatch)
    assert "วิชาเลือกเสรี 1" in result["answer"] and "ปี 4 เทอม 1" in result["answer"]


def test_free_elective_without_any_data_is_not_found_not_guessed(monkeypatch):
    src = m.open_db(RUNS / "DSBA/coop/lab8b_output/curriculum.db", readonly=True)
    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    src.backup(mem)
    src.close()
    mem.execute("DELETE FROM plan_slot WHERE name_th LIKE 'วิชาเลือกเสรี%'")
    mem.execute("UPDATE plan_item SET note = '' WHERE note LIKE '%เลือกเสรี%'")
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("must not guess with the model"))
    result = m.ask(mem, "วิชาเลือกเสรีเรียนได้ปีไหนเทอมไหน", verbose=False)
    assert result["answer"] == NOT_FOUND
    mem.close()


@pytest.mark.parametrize("rel,expect", [
    ("IT/coop", "วิชาบังคับก่อน: ไม่มี"),            # เล่ม IT ระบุว่าไม่มี
    ("BIT/coop", "วิชาบังคับก่อน: ไม่มี"),
    ("DSBA/coop", "ยังไม่ทราบ"),                    # เล่ม DSBA ไม่ระบุ = ไม่เดา
    ("AIT", "ยังไม่ทราบ"),
])
@pytest.mark.parametrize("question", [
    "วิชาสหกิจศึกษาต้องผ่านเงื่อนไขอะไรก่อน",
    "วิชาสหกิจศึกษาต้องผ่านวิชาอะไรก่อน",
])
def test_coop_prerequisite_condition_wording(rel, question, expect, monkeypatch):
    answer = _ask(rel, question, monkeypatch)["answer"]
    assert expect in answer
    assert answer != NOT_FOUND


def test_normalise_prerequisite_condition_words():
    assert m._normalise_prereq_words("วิชา X ต้องผ่านเงื่อนไขอะไรก่อน") == "วิชา X ต้องผ่านวิชาอะไรก่อน"
    assert m._normalise_prereq_words("ต้องผ่านวิชาอะไรก่อน") == "ต้องผ่านวิชาอะไรก่อน"
    assert m._normalise_prereq_words("เงื่อนไขการรับสมัคร") == "เงื่อนไขการรับสมัคร"


@pytest.mark.parametrize("rel", ["AIT", "BIT/coop", "BIT/no_coop", "DSBA/coop", "DSBA/no_coop", "IT/coop", "IT/no_coop"])
def test_summer_term_stays_not_found(rel, monkeypatch):
    assert _ask(rel, "ภาคฤดูร้อนต้องเรียนวิชาอะไร", monkeypatch)["answer"] == NOT_FOUND
