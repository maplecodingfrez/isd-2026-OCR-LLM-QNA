"""คำว่า "เครดิต" = "หน่วยกิต" — ราก: กฎ/ทางลัดทั้งหมดดักคำว่า "หน่วยกิต" อย่างเดียว คำถาม "เทอม 1 ของปี 4 ต้องเรียนทั้งหมดกี่เครดิต"
จึงหลุดไปให้โมเดลเขียน SQL + สรุป แล้วได้ "12 ครั้ง". ทางลัดตอบได้เองโดยไม่เรียกโมเดล จึงห้ามเรียกโมเดล"""

from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"


def test_normalise_credit_words():
    assert m._normalise_credit_words("ปี 4 เทอม 1 กี่เครดิต") == "ปี 4 เทอม 1 กี่หน่วยกิต"
    assert m._normalise_credit_words("ปี 4 เทอม 1 กี่หน่วยกิต") == "ปี 4 เทอม 1 กี่หน่วยกิต"
    assert m._normalise_credit_words("วิชาไหนก็ได้") == "วิชาไหนก็ได้"


@pytest.mark.parametrize("rel,question,credits", [
    ("AIT", "เทอม 1 ของปี 4 ต้องเรียนทั้งหมดกี่เครดิต", 12),
    ("BIT/no_coop", "เทอม 1 ของปี 4 ต้องเรียนทั้งหมดกี่เครดิต", 12),
])
def test_term_credits_asked_with_credit_word_use_shortcut(rel, question, credits, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("term credits must not call the model"))
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        result = m.ask(conn, question, verbose=False)
    assert result["question"] == question                      # ข้อความเดิมของผู้ใช้ไม่ถูกแก้
    assert f"{credits} หน่วยกิต" in result["answer"]
    assert "ครั้ง" not in result["answer"]


@pytest.mark.parametrize("rel,question,code,credits", [
    ("DSBA/coop", "Discrete Mathematics นับกี่เครดิต", "06066000", 3),
    ("DSBA/no_coop", "Discrete Mathematics นับกี่หน่วยกิต", "06066000", 3),
    ("DSBA/coop", "คณิตศาสตร์ไม่ต่อเนื่อง นับกี่หน่วยกิต", "06066000", 3),
])
def test_course_credits_with_count_word_use_shortcut(rel, question, code, credits, monkeypatch):
    """ราก: _NAME_SUFFIX_OK ไม่มี "นับ" → ชื่อวิชาตามด้วย "นับกี่…" ไม่ใช่ชื่อเต็ม → ทางลัดไม่ทำงาน → โมเดลใส่ชื่ออังกฤษใน name_th → "ไม่พบ" """
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("course credits must not call the model"))
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        result = m.ask(conn, question, verbose=False)
    assert code in result["answer"] and f"{credits} หน่วยกิต" in result["answer"]
