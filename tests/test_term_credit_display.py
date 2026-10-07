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
    assert [r["credits_display"] for r in result["rows"] if r.get('code')] == ["3 (2-2-5)", "3 (3-0-6)", "3 (2-2-5)", "3 (2-2-5)", "3 (3-0-6)"]
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


def test_term_lists_cover_all_seven_plans_without_llm(monkeypatch):
    def no_llm(*args, **kwargs):
        raise AssertionError('term lists must use the database')
    monkeypatch.setattr(m, 'ollama_generate', no_llm)
    runs = DB.parents[3]
    databases = sorted(d for d in runs.rglob('lab8b_output/curriculum.db') if '_retry' not in d.parts[-3])   # *_retry are scratch re-runs, not plans
    assert len(databases) == 7
    for database in databases:
        with closing(m.open_db(database, readonly=True)) as conn:
            terms = conn.execute('SELECT year, semester, credits, n_entries FROM v_semester_credits_full').fetchall()
            for y, s, credits, count in terms:
                result = m.ask(conn, QUESTION.replace('ปีที่ 2', f'ปีที่ {y}').replace('ศึกษาที่ 1', f'ศึกษาที่ {s}'), verbose=False)
                assert result['error'] is None, (database, y, s, result)
                assert result['answer_type'] == 'database', (database, y, s)
                rows = result['rows']
                expected = {r[0] for r in conn.execute('SELECT code FROM plan_item WHERE year=? AND semester=?', (y,s))}
                actual = {r['code'] for r in rows if r.get('code')}
                alternative = {r[0] for r in conn.execute('SELECT m.code FROM plan_slot_member m JOIN plan_slot p ON p.id=m.slot_id WHERE p.year=? AND p.semester=?', (y,s))}
                assert actual == expected - alternative
                slots = [r for r in rows if 'slot' in r]
                expected_slots = conn.execute('SELECT name_th, kind FROM plan_slot WHERE year=? AND semester=? ORDER BY id', (y,s)).fetchall()
                assert [(r['slot'],r['kind']) for r in slots] == [tuple(r) for r in expected_slots]
                assert all(r['total_credits'] == credits and r['n_courses'] == count for r in rows)
                assert '0-0-0' not in result['answer']
                for slot in slots:
                    if slot['kind'] in ('choose_one','choose_group'):
                        assert slot['alternatives'] and 'เลือก' in result['answer']
                assert result['citations'], (database, y, s)


def test_term_list_guard_rejects_unrepresented_scope():
    with closing(m.open_db(DB, readonly=True)) as conn:
        for question in ('ปี 7 เทอม 1 มีวิชาอะไรบ้าง', 'ปี 2 เทอม 1 กับปี 3 เทอม 1 มีวิชาอะไรบ้าง',
                         'ปี 2 เทอม 1 และเทอม 2 มีวิชาอะไรบ้าง', 'ปี 12 เทอม 1 มีวิชาอะไรบ้าง',
                         'ปี 2 เทอม 1 มีวิชาบังคับก่อนอะไรบ้าง', 'ปี 2 เทอม 1 มีวิชาอะไรบ้างที่ยาก',
                         'ปี 2 เทอม 1 วิชา 06026206 มีวิชาอะไรบ้าง', 'ปี 2 เทอม 1 มีวิชาเลือกอะไรบ้าง'):
            assert m._term_list_answer(conn, question) is None, question


def test_wildcard_only_elective_term_has_slots():
    database = DB.parents[3] / 'BIT/no_coop/lab8b_output/curriculum.db'
    with closing(m.open_db(database, readonly=True)) as conn:
        result = m._term_kind_list_one(conn, 'ปี 4 เทอม 2 มีวิชาเลือกอะไรบ้าง')
        assert result is not None
        assert len(result[1]) == 4 and sum(r['credits'] for r in result[1]) == 12
