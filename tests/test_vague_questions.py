"""คำถามคลุมเครือ/ไม่ครบ — ราก: ไม่มีกฎดักคำถามที่ไม่ระบุหัวข้อ ("กี่หน่วยกิต", "ปี 1", "Calculus") โมเดลจึงเดาแล้วตอบมั่นใจ
(132 หน่วยกิต / 18 หน่วยกิต / แคลคูลัส 2 วิชาเดียวทั้งที่มี 1 กับ 2). ต้องถามกลับพร้อมตัวอย่าง ไม่เรียกโมเดล ไม่เดา
ข้อกำหนด: คำถามที่ชัดเจนอยู่แล้วต้องไม่ถูกดัก"""

from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
MARK = "คำถามยังไม่ชัดเจน"


def conn_for(rel):
    return closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True))


@pytest.mark.parametrize("rel", ["DSBA/coop", "IT/no_coop", "AIT"])
@pytest.mark.parametrize("q", [
    "กี่หน่วยกิต", "กี่หน่วยกิตครับ", "หน่วยกิตเท่าไร", "กี่เครดิต",
    "ปี 1", "ปีที่ 2", "ชั้นปี 3", "เทอม 2", "ภาคเรียนที่ 1",
    "โปรแกรม", "หลักสูตร", "วิชา",
])
def test_vague_question_asks_back(rel, q, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("vague question must not call the model"))
    with conn_for(rel) as conn:
        result = m.ask(conn, q, verbose=False)
    assert result["answer"].startswith(MARK), result["answer"]
    assert "ลองถาม" in result["answer"]
    assert result["rows"] == [] and result["question"] == q
    assert not any(ch.isdigit() for ch in result["answer"].split("ลองถาม")[0].replace(MARK, "")) or "ปี" in q or "เทอม" in q or "ภาค" in q   # ไม่แต่งตัวเลขเอง


def test_vague_credit_does_not_guess_total(monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("no model"))
    with conn_for("DSBA/coop") as conn:
        assert "132 หน่วยกิต" not in m.ask(conn, "กี่หน่วยกิต", verbose=False)["answer"].split("ลองถาม")[0]


@pytest.mark.parametrize("q,codes", [
    ("Calculus", {"06026200", "06026201"}),
    ("แคลคูลัส", {"06026200", "06026201"}),
    ("คณิต", {"06066000"}),
])
def test_ambiguous_partial_name_lists_candidates(q, codes, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("no model"))
    with conn_for("DSBA/coop") as conn:
        result = m.ask(conn, q, verbose=False)
    assert result["answer"].startswith(MARK), result["answer"]
    assert all(c in result["answer"] for c in codes)
    assert {r["code"] for r in result["rows"]} >= codes


@pytest.mark.parametrize("q", [
    "หลักสูตรนี้กี่หน่วยกิต", "ปี 1 รวมกี่หน่วยกิต", "ปี 1 เทอม 1 เรียนอะไรบ้าง", "ปี 2 เทอม 1 มีกี่หน่วยกิต",
    "Calculus 1 กี่หน่วยกิต", "แคลคูลัส 1", "CALCULUS 1", "ฐานข้อมูลเรียนปีไหน", "เรียนจบกี่ปี", "วิชา Calculus 1",
    "ปี 1 กับปี 2 ต่างกันกี่หน่วยกิต", "06026200 กี่หน่วยกิต", "Discrete Mathematics นับกี่เครดิต",
])
def test_clear_questions_are_not_intercepted(q):
    with conn_for("DSBA/coop") as conn:
        assert m._vague_question_answer(conn, m._prepare_question(conn, q)) is None
