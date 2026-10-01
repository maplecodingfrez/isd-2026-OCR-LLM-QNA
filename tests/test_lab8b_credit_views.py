"""หน่วยกิตรายเทอมตามเล่ม — ราก: v_semester_credits ไม่รู้จัก plan_slot (นับสมาชิก "เลือก 1 กลุ่มวิชา" ทุกวิชา → ปี 2/2 ของ IT ได้ 30 ทั้งที่เล่มรวม 18)
ส่วน v_semester_credits_full ถูกตรง; ask() จึงต้องเห็น v_semester_credits ในแบบนับตามเล่ม โดย prompt/DDL ที่โมเดลเห็นไม่เปลี่ยน"""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "Lab7B_Lab8B_ocr_system" / "runs"
ALL_DBS = ["AIT", "BIT/coop", "BIT/no_coop", "DSBA/coop", "DSBA/no_coop", "IT/coop", "IT/no_coop"]


def _make_db(path, with_slots=True):
    c = sqlite3.connect(path)
    c.executescript(m.DDL)
    c.execute("INSERT INTO program VALUES ('P', 'โปรแกรมทดสอบ', 'Test', 'วท.บ.', 129, 4)")
    rows = [(1, 1, f"N1{i}", 3) for i in range(3)]                       # เทอม 1/1: วิชาปกติ 3 วิชา = 9
    rows += [(2, 2, f"A{i}", 3) for i in range(4)]                       # เทอม 2/2: วิชาปกติ 4 วิชา
    rows += [(2, 2, f"M{i}", 3) for i in range(6)]                       # + สมาชิก "เลือก 1 กลุ่มวิชา" 6 วิชา (กลุ่มละ 3)
    for year, sem, code, cr in rows:
        c.execute("INSERT INTO plan_item(program_id, year, semester, code, credits) VALUES ('P', ?, ?, ?, ?)",
                  (year, sem, code, cr))
    if with_slots:
        c.executescript(m.PLAN_SLOT_DDL)
        c.execute("INSERT INTO plan_slot(id, program_id, year, semester, kind, name_th, credits) "
                  "VALUES (1, 'P', 2, 2, 'choose_group', 'เลือก 1 กลุ่มวิชา', 6)")
        for i in range(6):
            c.execute("INSERT INTO plan_slot_member(slot_id, group_no, code) VALUES (1, ?, ?)", (1 + i // 3, f"M{i}"))
    c.commit()
    return c


def _terms(conn):
    return {(r[0], r[1]): (r[2], r[3]) for r in conn.execute(
        "SELECT year, semester, credits, n_courses FROM v_semester_credits")}


def test_the_stored_view_overcounts_choose_group_members(tmp_path):
    """หลักฐานของสาเหตุราก (ไม่แก้ view ที่เก็บใน DB — ดูเหตุผลใน PLAN_SLOT_DDL)"""
    conn = _make_db(tmp_path / "t.db")
    assert _terms(conn)[(2, 2)] == (30, 10)


def test_slot_aware_view_counts_each_term_the_way_the_book_does(tmp_path):
    conn = _make_db(tmp_path / "t.db")
    assert m.use_slot_aware_credit_view(conn) is True
    terms = _terms(conn)
    assert terms[(2, 2)] == (18, 5)          # วิชาปกติ 4×3 + ช่อง "เลือก 1 กลุ่ม" 6; นับเป็น 5 รายการ
    assert terms[(1, 1)] == (9, 3)           # เทอมที่ไม่มี slot เหมือนเดิมทุกประการ


def test_it_is_idempotent_and_works_on_a_read_only_connection(tmp_path):
    path = tmp_path / "t.db"
    _make_db(path).close()
    ro = m.open_db(path, readonly=True)                       # ด่านความปลอดภัยของ ask(): เปิดแบบอ่านอย่างเดียว
    assert m.use_slot_aware_credit_view(ro) is True
    assert m.use_slot_aware_credit_view(ro) is True
    assert _terms(ro)[(2, 2)] == (18, 5)
    with pytest.raises(sqlite3.OperationalError):             # ยังเขียน DB จริงไม่ได้
        ro.execute("INSERT INTO program VALUES ('Q', 'x', 'x', 'x', 100, 4)")


def test_db_without_slot_tables_is_left_untouched(tmp_path):
    conn = _make_db(tmp_path / "t.db", with_slots=False)
    assert m.use_slot_aware_credit_view(conn) is False
    assert conn.execute("SELECT COUNT(*) FROM sqlite_temp_master WHERE name = 'v_semester_credits'").fetchone()[0] == 0
    assert _terms(conn)[(2, 2)] == (30, 10)


def test_ask_answers_from_the_slot_aware_view_without_changing_the_prompt(tmp_path, monkeypatch):
    path = tmp_path / "t.db"
    _make_db(path).close()
    conn = m.open_db(path, readonly=True)          # เหมือนที่เซิร์ฟเวอร์เปิด: อ่านอย่างเดียว + row_factory=Row
    prompts = []

    def fake_generate(prompt, fmt=None, **kw):
        prompts.append(prompt)
        if len(prompts) == 1:
            return json.dumps({"sql": "SELECT credits FROM v_semester_credits WHERE year=2 AND semester=2"})
        return json.dumps({"answer": "18 หน่วยกิต"})

    monkeypatch.setattr(m, "ollama_generate", fake_generate)
    r = m.ask(conn, "ชั้นปีที่ 2 ภาคการศึกษาที่ 2 เรียนกี่หน่วยกิต", verbose=False)
    assert r["error"] is None and r["rows"] == [{"credits": 18}]
    assert "v_semester_credits_full" not in prompts[0]        # โมเดลยังเห็น DDL/ชื่อ view เดิม


@pytest.mark.parametrize("rel", ALL_DBS)
def test_every_real_program_adds_up_to_the_declared_total(rel):
    """ใช้ข้อตรวจในตัว (ไม่ใช้เฉลย): ผลรวมหน่วยกิตทุกเทอมแบบนับตามเล่ม = หน่วยกิตรวมที่หลักสูตรประกาศ"""
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    conn = m.open_db(db, readonly=True)
    assert m.use_slot_aware_credit_view(conn) is True
    declared = conn.execute("SELECT total_credits FROM program").fetchone()[0]
    assert sum(r[0] for r in conn.execute("SELECT credits FROM v_semester_credits")) == declared


def test_sql_prompt_routes_year_level_credits_to_the_credit_view():
    """รวมหน่วยกิตทั้งชั้นปีจาก v_plan จะนับสมาชิกตัวเลือกซ้ำ (IT ปี 4 ได้ 9 แทน 24) — กติกาต้องครอบคลุมรายปีด้วย"""
    assert "ชั้นปีไหนมีกี่หน่วยกิต" in m.SQL_PROMPT
    assert "SUM(credits) จาก v_semester_credits ตาม year" in m.SQL_PROMPT
    assert "ห้ามใช้ SUM(credits) จาก v_plan" in m.SQL_PROMPT
    assert "v_semester_credits_full" not in m.SQL_PROMPT      # โมเดลยังเห็นชื่อ view เดิมเท่านั้น


def test_sql_prompt_states_the_direction_of_the_unlock_relation():
    """prerequisite(code, requires): "X ปลดล็อกอะไร" ต้องกรอง requires = X แล้วเลือก code (ทิศตรงข้ามกับ "X ต้องผ่านอะไรก่อน")"""
    assert "แล้วเรียนอะไรต่อได้" in m.SQL_PROMPT and "ปลดล็อก" in m.SQL_PROMPT
    assert "กรอง requires" in m.SQL_PROMPT and "เลือกคอลัมน์ code" in m.SQL_PROMPT


def test_verify_helpers_keep_reading_the_stored_view_after_ask_installed_the_temp_view(tmp_path):
    """รีวิว M1: ถ้า connection เดียวกันรัน ask() แล้วค่อย verify, CHK1/CHK7 ต้องไม่กลายเป็น CHK1F/CHK7F เงียบ ๆ"""
    with closing(_make_db(tmp_path / "t.db")) as conn:
        assert m.use_slot_aware_credit_view(conn) is True
        stored = {(r[0], r[1]): r[2] for r in m._sem_credits(conn)}
        assert stored[(2, 2)] == 30                       # verify ยังเห็นค่าที่เก็บใน DB
        assert _terms(conn)[(2, 2)][0] == 18              # ส่วนคำถามผ่าน v_semester_credits เห็นแบบนับตามเล่ม


def _scripted_ollama(monkeypatch):
    calls = []

    def fake(prompt, fmt=None, **kw):
        calls.append(prompt)
        if len(calls) == 1:
            return json.dumps({"sql": "SELECT credits FROM v_semester_credits WHERE year=1 AND semester=1"})
        return json.dumps({"answer": "9 หน่วยกิต"})

    monkeypatch.setattr(m, "ollama_generate", fake)


@pytest.mark.parametrize("with_slots,expected", [(True, True), (False, False)])
def test_ask_reports_whether_the_slot_aware_view_was_used(tmp_path, monkeypatch, with_slots, expected):
    """รีวิว M2: ถ้า temp view สร้างไม่ได้ ต้องเห็นในผลลัพธ์ ไม่ใช่กลับไปตอบ 30 หน่วยกิตแบบเงียบ ๆ"""
    path = tmp_path / "t.db"
    _make_db(path, with_slots=with_slots).close()
    _scripted_ollama(monkeypatch)
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, "ปี 1 เทอม 1 เรียนกี่หน่วยกิต", verbose=False)
    assert r["error"] is None and r["slot_aware_credits"] is expected


@pytest.mark.parametrize("rel,year,sem,book,stored", [
    ("IT/no_coop", 2, 2, 18, 30), ("IT/no_coop", 3, 1, 18, 30), ("IT/no_coop", 3, 2, 15, 9),
    ("IT/coop", 2, 2, 18, 30), ("BIT/coop", 3, 2, 15, 9), ("AIT", 3, 2, 13, 4), ("DSBA/coop", 3, 1, 18, 9),
])
def test_real_terms_where_the_stored_view_overcounts_or_undercounts(rel, year, sem, book, stored):
    """รีวิว M4: ตรวจรายเทอมจริง (ไม่ใช่แค่ยอดรวม) — ช่องผิดเทอมจะทำให้ข้อนี้ล้ม"""
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    with closing(m.open_db(db, readonly=True)) as conn:
        stored_value = conn.execute("SELECT credits FROM main.v_semester_credits WHERE year=? AND semester=?",
                                    (year, sem)).fetchone()[0]
        assert m.use_slot_aware_credit_view(conn) is True
        got = conn.execute("SELECT credits FROM v_semester_credits WHERE year=? AND semester=?",
                           (year, sem)).fetchone()[0]
    assert (got, stored_value) == (book, stored)


def test_prerequisite_rule_names_the_kind_column_for_unlock_questions():
    """รีวิว I2: คำตอบผิดเดิมบางข้อใช้ kind='co' ทั้งที่ถามวิชาบังคับก่อน — กติกาต้องบอก kind ด้วย"""
    assert "kind='pre' ยกเว้น" in m.SQL_PROMPT

