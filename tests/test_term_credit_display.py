import json
from contextlib import closing
from copy import deepcopy
from pathlib import Path

import lab8b_curriculum_db as m


DB = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system/runs/DSBA/coop/lab8b_output/curriculum.db"
QUESTION = "ในแผนการศึกษา ชั้นปีที่ 2 ภาคการศึกษาที่ 1 มีรายวิชาทั้งหมดกี่วิชา อะไรบ้าง"


def test_compound_term_answer_has_source_hours_and_preserves_totals(monkeypatch):
    outputs = iter([json.dumps({"sql": m._TERM_SUMMARY_SQL.format(y=2, s=1)}), json.dumps({"answer": "x"})])
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: next(outputs))
    with closing(m.open_db(DB, readonly=True)) as conn:
        result = m.ask(conn, QUESTION, verbose=False)
    assert result["error"] is None
    assert [r["credits_display"] for r in result["rows"]] == ["3 (2-2-5)", "3 (3-0-6)", "3 (2-2-5)", "3 (2-2-5)", "3 (3-0-6)",
                                                                  "3 (3-0-6) หรือ 3 (2-2-5)"]  # ช่องเลือกภาษาเป็นแถวที่ 6 (636927e)
    assert all(r["credits"] == 3 and r["total_credits"] == 18 and r["n_courses"] == 6 for r in result["rows"])
    assert "รวม 18 หน่วยกิต, 6 วิชา" in result["answer"]
    assert "วิชาเลือกด้านภาษาและการสื่อสาร 3 (3-0-6) หรือ 3 (2-2-5) หน่วยกิต" in result["answer"]
    assert result["citations"][0]["pdf_page"] == 32


def test_missing_or_mismatched_credit_data_does_not_invent_hours():
    result = {"rows": [{"code": "06026206", "name_th": "การวิเคราะห์ข้อมูลและการโปรแกรม", "credits": 2}], "answer": "unchanged"}
    before = deepcopy(result)
    with closing(m.open_db(DB, readonly=True)) as conn:
        m._term_full_credits(conn, QUESTION, result)
    assert result == before
    with closing(m.open_db(":memory:")) as conn:
        result["rows"][0]["credits"] = 3
        before = deepcopy(result)
        assert m._term_full_credits(conn, QUESTION, result) == {}
        assert result == before


def test_credit_only_question_is_not_reformatted():
    result = {"rows": [{"credits": 18}], "answer": "18"}
    before = deepcopy(result)
    with closing(m.open_db(DB, readonly=True)) as conn:
        assert m._term_full_credits(conn, "ปี 2 เทอม 1 รวมกี่หน่วยกิต", result) == {}
    assert result == before
