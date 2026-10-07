"""A bare course reference ("วิชา 06066300", "06066300", "ขอข้อมูลวิชา ...", "course 06066300", an exact course name)
asks nothing, so it used to reach the language model, which guessed an empty query and answered "ไม่พบข้อมูลนี้ในเล่มหลักสูตร".
It now answers with the course overview, straight from the database: names, credits and hours, year and semester,
prerequisites and follow-ups. A question that names a course AND asks something ("วิชา X ชื่ออะไร") is left alone.
"""

import sqlite3
from contextlib import closing

import pytest

course_overview = pytest.importorskip("course_overview", reason="course_overview.py not added yet")
import lab8b_curriculum_db as m  # noqa: E402
from lab10_fastapi.curriculum_app import main  # noqa: E402

DDL = """
CREATE TABLE course(code TEXT PRIMARY KEY, name_th TEXT, name_en TEXT, credits INT, lecture_h INT, lab_h INT, self_h INT, description_th TEXT);
CREATE TABLE v_plan(id INTEGER, year INT, semester INT, code TEXT, name_th TEXT, name_en TEXT, credits INT, alt_group INT, note TEXT);
CREATE TABLE prerequisite(code TEXT, requires TEXT, kind TEXT);
CREATE TABLE elective_group_course(id INTEGER PRIMARY KEY, group_id INT, code TEXT, name_th TEXT, name_en TEXT, credits INT);
CREATE TABLE course_description(code TEXT, name_th TEXT, description_th TEXT, description_en TEXT, pdf_page INT, printed_page TEXT);
"""
NOT_FOUND = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"


@pytest.fixture()
def conn():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(DDL)
    db.executemany("INSERT INTO course VALUES (?,?,?,?,?,?,?,NULL)", [
        ("06066300", "แนวคิดระบบฐานข้อมูล", "DATABASE SYSTEM CONCEPTS", 3, 2, 2, 5),
        ("06026212", "การสร้างคลังข้อมูล", "DATA WAREHOUSING", 3, 2, 2, 5),
        ("06026200", "แคลคูลัส 1", "CALCULUS 1", 3, 3, 0, 6),
        ("06026201", "แคลคูลัส 2", "CALCULUS 2", 3, 3, 0, 6),
    ])
    db.executemany("INSERT INTO v_plan(year, semester, code) VALUES (?,?,?)", [(2, 1, "06066300"), (3, 1, "06026212"), (1, 1, "06026200"), (1, 2, "06026201")])
    db.executemany("INSERT INTO prerequisite VALUES (?,?,?)", [("06026212", "06066300", "pre"), ("06026201", "06026200", "pre")])
    db.execute("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (1, '06026216', 'ปัญญาประดิษฐ์', 'ARTIFICIAL INTELLIGENCE', 3)")
    db.execute("INSERT INTO course_description(code, name_th) VALUES ('06099999', 'การพัฒนาเว็บ')")
    yield db
    db.close()


def status(conn, code):
    return {"06066300": "none", "06026212": "found", "06026200": "none", "06026201": "found"}.get(code, "unknown")


def overview(conn, question):
    return course_overview.overview_for_bare_reference(conn, question, status)


@pytest.mark.parametrize("question", [
    "วิชา 06066300", "06066300", "วิชา06066300", "รหัสวิชา 06066300", "ขอข้อมูลวิชา 06066300", "ข้อมูลวิชา 06066300?", "  วิชา 06066300  ",
    "วิชา DATABASE SYSTEM CONCEPTS", "วิชา แนวคิดระบบฐานข้อมูล", "ขอข้อมูลวิชา database system concepts",
])
def test_a_bare_reference_gets_the_course_overview(conn, question):
    answer, rows, sql = overview(conn, question)
    assert answer.splitlines()[0].startswith("06066300 แนวคิดระบบฐานข้อมูล / DATABASE SYSTEM CONCEPTS — 3 (2-2-5) หน่วยกิต")
    assert rows[0]["code"] == "06066300" and rows[0]["source"] == "plan" and "06066300" in sql


@pytest.mark.parametrize("question", [
    "วิชา 06066300 ชื่ออะไร", "วิชา 06066300 กี่หน่วยกิต", "วิชา 06066300 เรียนปีไหน", "06066300 ต้องผ่านวิชาอะไรก่อน",
    "วิชา DATABASE", "วิชา", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง", "", "hello", "วิชาที่ต้องผ่าน 06066300 ก่อนมีอะไรบ้าง", "06066300 06026212",
])
def test_a_question_that_asks_something_is_left_alone(conn, question):
    assert overview(conn, question) is None


def test_overview_lists_year_term_prerequisites_and_follow_ups(conn):
    answer, rows, _ = overview(conn, "วิชา 06066300")
    lines = answer.splitlines()
    assert lines[1] == "เรียนปี 2 เทอม 1"
    assert lines[2] == "วิชาบังคับก่อน: ไม่มี"
    assert lines[3] == "วิชาต่อ: 06026212 (การสร้างคลังข้อมูล)"
    row = rows[0]
    assert row["terms"] == [[2, 1]] and row["prerequisite_status"] == "none" and row["prerequisites"] == []
    assert row["unlocks"] == [{"code": "06026212", "name_th": "การสร้างคลังข้อมูล"}]
    assert (row["lecture_h"], row["lab_h"], row["self_h"], row["credits"]) == (2, 2, 5, 3)


def test_overview_lists_prerequisites_and_says_so_when_the_book_data_is_unknown(conn):
    answer, rows, _ = overview(conn, "วิชา 06026201")
    assert "วิชาบังคับก่อน: 06026200 (แคลคูลัส 1)" in answer and "วิชาต่อ: ไม่พบวิชาต่อในข้อมูลที่มี" in answer
    assert rows[0]["prerequisites"] == [{"code": "06026200", "name_th": "แคลคูลัส 1"}]
    unknown = course_overview.overview_for_bare_reference(conn, "วิชา 06066300", lambda c, code: "unreadable")   # no prerequisite rows and the book was unreadable
    assert "วิชาบังคับก่อน: ยังไม่ทราบ" in unknown[0]


def test_a_course_outside_the_plan_says_so_instead_of_inventing_data(conn):
    elective, rows, _ = overview(conn, "วิชา 06026216")
    assert elective.splitlines()[0] == "06026216 ปัญญาประดิษฐ์ / ARTIFICIAL INTELLIGENCE — 3 หน่วยกิต"
    assert "ไม่อยู่ในแผน" in elective and rows[0]["source"] == "elective"
    catalog, rows, _ = overview(conn, "06099999")
    assert catalog.splitlines()[0] == "06099999 การพัฒนาเว็บ" and rows[0]["source"] == "catalog"


def test_an_unknown_code_gets_the_not_found_sentence_naming_the_code(conn):
    answer, rows, _ = overview(conn, "วิชา 12345678")
    assert answer.startswith(NOT_FOUND) and "12345678" in answer and rows == []


# ---------- through ask() on the real databases, model switched off ----------

PLANS = {"dsba_coop": "DSBA/coop", "it_no_coop": "IT/no_coop", "ait": "AIT", "bit_coop": "BIT/coop"}


@pytest.fixture()
def no_model(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the language model must not be needed")
    monkeypatch.setattr(m, "ollama_generate", refuse)


@pytest.mark.parametrize("plan", sorted(PLANS))
def test_ask_answers_a_bare_code_on_every_plan_without_the_model(plan, no_model):
    path = main.program_db_path(plan)
    if path is None or not path.exists():
        pytest.skip(f"needs the {plan} database")
    with closing(m.open_db(path, readonly=True)) as conn:
        code, name = conn.execute("SELECT code, name_th FROM course ORDER BY code LIMIT 1 OFFSET 3").fetchone()
        for question in (f"วิชา {code}", code, f"course {code}", f"Tell me about course {code}"):
            r = m.ask(conn, question, verbose=False)
            assert r["answer_type"] == "course_overview", (plan, question)
            assert code in r["answer"] and name in r["answer"] and NOT_FOUND not in r["answer"], (plan, question)
            assert r["rows"] and r["rows"][0]["code"] == code and r["question"] == question


def test_ask_answers_a_bare_name_and_an_elective_and_an_unknown_code(no_model):
    path = main.program_db_path("dsba_coop")
    if path is None or not path.exists():
        pytest.skip("needs the DSBA co-op database")
    with closing(m.open_db(path, readonly=True)) as conn:
        by_name = m.ask(conn, "วิชา DATABASE SYSTEM CONCEPTS", verbose=False)
        assert by_name["answer_type"] == "course_overview" and by_name["rows"][0]["code"] == "06066300"
        assert "เรียนปี 2 เทอม 1" in by_name["answer"]
        elective = m.ask(conn, "วิชา 06026216", verbose=False)
        assert "ไม่อยู่ในแผน" in elective["answer"] and elective["rows"][0]["source"] == "elective"
        unknown = m.ask(conn, "วิชา 12345678", verbose=False)
        assert unknown["answer"].startswith(NOT_FOUND) and unknown["rows"] == []


def test_a_question_that_asks_something_still_goes_the_old_way(no_model):
    path = main.program_db_path("dsba_coop")
    if path is None or not path.exists():
        pytest.skip("needs the DSBA co-op database")
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, "วิชา 06066300 ชื่ออะไร", verbose=False)
        assert r["answer_type"] != "course_overview"
