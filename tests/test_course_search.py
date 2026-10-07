"""Course search: one search over every table that names a course (plan, elective groups, book catalogue),
with acronyms, spacing-insensitive Thai matching, ranking and honest tags for courses outside the plan.

Unit tests use a small in-memory database; the API tests use the real DSBA co-op database when it exists.
"""

import sqlite3

import pytest
from starlette.testclient import TestClient

from lab10_fastapi.curriculum_app import main

course_search = pytest.importorskip("lab10_fastapi.curriculum_app.course_search", reason="course_search.py not added yet")

DDL = """
CREATE TABLE course(code TEXT PRIMARY KEY, name_th TEXT, name_en TEXT, credits INT, lecture_h INT, lab_h INT, self_h INT, description_th TEXT);
CREATE TABLE elective_group(id INTEGER PRIMARY KEY, program_id TEXT, plan_slot TEXT, credits_required INT, group_no INT, name_th TEXT, name_en TEXT);
CREATE TABLE elective_group_course(id INTEGER PRIMARY KEY, group_id INT, code TEXT, name_th TEXT, name_en TEXT, credits INT);
CREATE TABLE course_description(code TEXT, name_th TEXT, description_th TEXT, description_en TEXT, pdf_page INT, printed_page TEXT);
"""

PLAN = [
    ("06026200", "แคลคูลัส 1", "CALCULUS 1", 3),
    ("06026201", "แคลคูลัส 2", "CALCULUS 2", 3),
    ("06026207", "ระบบฐานข้อมูลแบบโนเอสคิวแอล", "NOSQL DATABASE SYSTEMS", 3),
    ("06026243", "ระบบฐานข้อมูลขั้นสูง", "ADVANCED DATABASE SYSTEMS", 3),
    ("06026244", "การดูแลและบำรุงรักษาระบบฐานข้อมูล", "DATABASE SYSTEM MAINTENANCE AND ADMINISTRATION", 3),
    ("06016412", "ระบบปฏิบัติการ", "OPERATING SYSTEMS", 3),
    ("06026211", "การเรียนรู้ของเครื่องเชิงประยุกต์", "APPLIED MACHINE LEARNING", 3),
]
ELECTIVE = [
    ("06026216", "ปัญญาประดิษฐ์", "ARTIFICIAL INTELLIGENCE", 3),
    ("06026217", "การเรียนรู้ของเครื่อง", "MACHINE LEARNING", 3),
]
CATALOG = [
    ("06099999", "การพัฒนาเว็บ", "บรรยายการสตรีมข้อมูล", "Covers streaming of data"),
]


@pytest.fixture()
def conn():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(DDL)
    db.executemany("INSERT INTO course(code,name_th,name_en,credits) VALUES (?,?,?,?)", PLAN)
    db.execute("INSERT INTO elective_group VALUES (1,'P','A',3,1,'กลุ่มวิทยาการข้อมูล','Data science')")
    db.executemany("INSERT INTO elective_group_course(group_id,code,name_th,name_en,credits) VALUES (1,?,?,?,?)", ELECTIVE)
    db.executemany("INSERT INTO course_description(code,name_th,description_th,description_en) VALUES (?,?,?,?)", CATALOG)
    yield db
    db.close()


def codes(rows):
    return [r["code"] for r in rows]


def test_search_reaches_elective_and_catalogue_courses_and_tags_them(conn):
    ai = course_search.search_courses(conn, "ปัญญาประดิษฐ์")
    assert codes(ai) == ["06026216"] and ai[0]["source"] == "elective" and ai[0]["credits"] == 3
    (cat,) = course_search.search_courses(conn, "06099999")
    assert cat["source"] == "catalog" and cat["name_en"] is None and cat["credits"] is None
    assert course_search.search_courses(conn, "06026200")[0]["source"] == "plan"


@pytest.mark.parametrize("query,expected", [
    ("ML", {"06026217", "06026211"}),
    ("ml", {"06026217", "06026211"}),
    ("DB", {"06026207", "06026243", "06026244"}),
    ("OS", {"06016412"}),                      # not NoSQL: "OS" is a word, not a substring
    ("AI", {"06026216"}),                      # not MAINTENANCE
])
def test_acronyms_find_their_courses_without_matching_inside_words(conn, query, expected):
    assert set(codes(course_search.search_courses(conn, query))) == expected


@pytest.mark.parametrize("query,expected", [
    ("ฐานข้อมูล ขั้นสูง", "06026243"),         # a space the book does not have
    ("ฐานข้อมูลขั้นสูง", "06026243"),
    ("calc 1", "06026200"),
    ("แคลคูลัส1", "06026200"),
    ("advanced database", "06026243"),
    ("DATABASE   systems advanced", "06026243"),   # words in any order, extra spaces
])
def test_multi_word_and_spacing_variants_find_the_course(conn, query, expected):
    assert expected in codes(course_search.search_courses(conn, query))


def test_machine_learning_is_found_with_or_without_the_space(conn):
    assert set(codes(course_search.search_courses(conn, "machine learning"))) == {"06026217", "06026211"}
    assert set(codes(course_search.search_courses(conn, "machinelearning"))) == {"06026217", "06026211"}


def test_exact_code_first_then_name_start_then_contains_and_plan_before_elective(conn):
    assert course_search.search_courses(conn, "06026216")[0]["code"] == "06026216"
    # "ระบบฐานข้อมูล": two names start with it, one only contains it
    assert codes(course_search.search_courses(conn, "ระบบฐานข้อมูล")) == ["06026207", "06026243", "06026244"]
    # same tier (both names start with the query): the plan course comes before the elective one
    assert codes(course_search.search_courses(conn, "การเรียนรู้ของเครื่อง"))[:2] == ["06026211", "06026217"]


def test_description_only_matches_come_last_and_unmatched_queries_are_empty(conn):
    assert codes(course_search.search_courses(conn, "streaming")) == ["06099999"]
    assert course_search.search_courses(conn, "zzzzqq") == []


def test_limit_and_offset_apply_after_ranking(conn):
    all_ = codes(course_search.search_courses(conn, "database", limit=10))
    assert codes(course_search.search_courses(conn, "database", limit=1, offset=1)) == all_[1:2]


def test_known_course_checks_plan_elective_and_catalogue(conn):
    assert course_search.known_course(conn, "06026200")["source"] == "plan"
    assert course_search.known_course(conn, "06026216")["source"] == "elective"
    assert course_search.known_course(conn, "06099999")["source"] == "catalog"
    assert course_search.known_course(conn, "99999999") is None


def test_missing_optional_tables_do_not_break_search():
    bare = sqlite3.connect(":memory:")
    bare.row_factory = sqlite3.Row
    bare.execute("CREATE TABLE course(code TEXT, name_th TEXT, name_en TEXT, credits INT, lecture_h INT, lab_h INT, self_h INT, description_th TEXT)")
    bare.execute("INSERT INTO course(code,name_th,name_en,credits) VALUES ('00000001','วิชา','COURSE',3)")
    assert codes(course_search.search_courses(bare, "course")) == ["00000001"]
    assert course_search.known_course(bare, "00000009") is None


# ---------- through the HTTP API, on the real DSBA co-op database ----------

DSBA = main.program_db_path("dsba_coop")
real_db = pytest.mark.skipif(DSBA is None or not DSBA.exists(), reason="needs the DSBA co-op database")


@pytest.fixture()
def client():
    return TestClient(main.app)


@real_db
def test_api_search_finds_electives_acronyms_and_spaced_queries(client):
    def search(q):
        r = client.get("/api/courses", params={"search": q, "limit": 100, "program": "dsba_coop"})
        assert r.status_code == 200
        return r.json()
    ai = search("ปัญญาประดิษฐ์")
    assert any(c["code"] == "06026216" and c["source"] == "elective" for c in ai)
    assert search("DB") and search("ML")
    assert any(c["code"] == "06026243" for c in search("ฐานข้อมูล ขั้นสูง"))
    assert all("source" in c for c in ai)


@real_db
def test_api_search_without_a_query_still_lists_only_the_plan_courses(client):
    rows = client.get("/api/courses", params={"limit": 100, "program": "dsba_coop"}).json()
    assert rows and {c["source"] for c in rows} == {"plan"} and len(rows) <= 60


@real_db
def test_prerequisite_and_withdrawal_checks_accept_an_elective_course(client):
    pre = client.get("/api/courses/06026216/prerequisites", params={"program": "dsba_coop"})
    assert pre.status_code == 200
    body = pre.json()
    assert body["code"] == "06026216" and body["prerequisite_status"] == "not_in_plan"
    assert body["prerequisites_required"] == [] and body["unlocked_courses"] == []
    out = client.get("/api/courses/06026216/withdrawal-impact", params={"program": "dsba_coop"})
    assert out.status_code == 200 and out.json()["direct"] == [] and out.json()["indirect"] == []
    assert out.json()["course"]["code"] == "06026216"


@real_db
def test_a_course_unknown_to_the_plan_database_is_still_404(client):
    assert client.get("/api/courses/99999999/prerequisites", params={"program": "dsba_coop"}).status_code == 404
    assert client.get("/api/courses/99999999/withdrawal-impact", params={"program": "dsba_coop"}).status_code == 404


def test_a_short_number_matches_a_standalone_number_not_digits_inside_a_code(conn):
    assert codes(course_search.search_courses(conn, "calc 1")) == ["06026200"]          # not "CALCULUS 2" (code 06026201)
    assert codes(course_search.search_courses(conn, "แคลคูลัส 2")) == ["06026201"]
    assert "06026201" in codes(course_search.search_courses(conn, "0602620"))            # a longer digit run is still a code fragment
