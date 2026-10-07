"""One course + "what must I pass first?" / "what does it unlock?" used to reach the language model, which wrote its own SQL
(often empty -> "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"). It is now answered from the prerequisite table, in every phrasing, on every plan.
A question that asks something else about the course, or names two courses, is left to the old routes."""

import sqlite3
from contextlib import closing

import pytest

import lab8b_curriculum_db as m
from lab10_fastapi.curriculum_app import main

course_overview = pytest.importorskip("course_overview")
NOT_FOUND = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"
PLANS = ["ait", "bit_coop", "bit_no_coop", "dsba_coop", "dsba_no_coop", "it_coop", "it_no_coop"]

PRE = ["วิชา {c} ต้องผ่านวิชาใดก่อน", "วิชา {c} ต้องเรียนอะไรก่อน", "{c} มีวิชาบังคับก่อนอะไรบ้าง", "ก่อนเรียน {c} ต้องผ่านวิชาอะไร",
       "วิชาบังคับก่อนของ {c}", "วิชา {n} ต้องผ่านวิชาอะไรก่อน", "What are the prerequisites of {c}?"]
NEXT = ["วิชา {p} มีวิชาต่อไหม", "วิชาที่ต้องผ่าน {p} ก่อนมีอะไรบ้าง", "เรียน {p} แล้วต่อวิชาอะไรได้", "{p} เป็นวิชาบังคับก่อนของวิชาอะไร",
        "วิชาอะไรต้องใช้ {p} เป็นพื้นฐาน", "Does {p} have follow-up courses?"]


@pytest.fixture()
def no_model(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the language model must not be needed")
    monkeypatch.setattr(m, "ollama_generate", refuse)


def open_plan(plan):
    path = main.program_db_path(plan)
    if path is None or not path.exists():
        pytest.skip(f"needs the {plan} database")
    return closing(m.open_db(path, readonly=True))


def facts(conn):
    """A course with plain prerequisites, one with none, the most-required course, and who each leads to."""
    alt = {(r[0], r[1]) for r in conn.execute("SELECT code, requires FROM prerequisite_alt")} if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='prerequisite_alt'").fetchone() else set()
    pairs = [(r[0], r[1]) for r in conn.execute("SELECT p.code, p.requires FROM prerequisite p JOIN course a ON a.code=p.code JOIN course b ON b.code=p.requires WHERE p.kind='pre'")]
    plain = [(c, r) for c, r in pairs if (c, r) not in alt]
    c = next(c for c, _ in plain if not any(x == c for x, _ in alt))
    top = max({r for _, r in plain}, key=lambda r: (sum(1 for _, y in plain if y == r), r))
    return {
        "c": c, "n": conn.execute("SELECT name_th FROM course WHERE code=?", (c,)).fetchone()[0],
        "pre": sorted(r for x, r in pairs if x == c),
        "p": top, "next": sorted(x for x, r in pairs if r == top),
    }


@pytest.mark.parametrize("plan", PLANS)
def test_prerequisites_of_one_course_are_answered_from_the_data(plan, no_model):
    with open_plan(plan) as conn:
        f = facts(conn)
        for template in PRE:
            q = template.format(**f)
            r = m.ask(conn, q, verbose=False)
            assert r["answer_type"] in ("database", "rule") and NOT_FOUND not in r["answer"], (plan, q, r["answer"][:80])
            assert all(code in r["answer"] for code in f["pre"]), (plan, q, r["answer"])
            assert r["answer"].count(f["c"]) >= 1 and r["question"] == q


@pytest.mark.parametrize("plan", PLANS)
def test_follow_ups_of_one_course_are_answered_from_the_data(plan, no_model):
    with open_plan(plan) as conn:
        f = facts(conn)
        for template in NEXT:
            q = template.format(**f)
            r = m.ask(conn, q, verbose=False)
            assert r["answer_type"] in ("database", "rule") and NOT_FOUND not in r["answer"], (plan, q, r["answer"][:80])
            assert all(code in r["answer"] for code in f["next"]), (plan, q, r["answer"])
            assert {row["code"] for row in r["rows"]} >= set(f["next"])


def test_a_course_with_no_prerequisite_and_no_follow_up_says_so(no_model):
    with open_plan("dsba_coop") as conn:
        pre = m.ask(conn, "วิชา 06066300 ต้องผ่านวิชาใดก่อน", verbose=False)["answer"]
        assert "ไม่มี" in pre and NOT_FOUND not in pre
        nxt = m.ask(conn, "วิชา 06026212 มีวิชาต่อไหม", verbose=False)["answer"]
        assert "ไม่พบวิชาต่อ" in nxt


@pytest.mark.parametrize("plan", ["bit_coop", "bit_no_coop"])
def test_alternative_prerequisites_are_shown_as_either_or(plan, no_model):
    with open_plan(plan) as conn:
        code, other = conn.execute("SELECT code, requires FROM prerequisite_alt LIMIT 1").fetchone()
        answer = m.ask(conn, f"วิชา {code} ต้องผ่านวิชาใดก่อน", verbose=False)["answer"]
        assert "อย่างใดอย่างหนึ่ง" in answer and other in answer and " หรือ " in answer
        follow = m.ask(conn, f"วิชา {other} มีวิชาต่อไหม", verbose=False)["answer"]
        assert code in follow and "ทางเลือก" in follow


@pytest.fixture()
def conn():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE course(code TEXT PRIMARY KEY, name_th TEXT, name_en TEXT, credits INT, lecture_h INT, lab_h INT, self_h INT);
    CREATE TABLE prerequisite(code TEXT, requires TEXT, kind TEXT);
    INSERT INTO course VALUES ('06000004','การวิเคราะห์และออกแบบระบบ','SYSTEMS ANALYSIS AND DESIGN',3,3,0,6),('06000001','แคลคูลัส 1','CALCULUS 1',3,3,0,6),('06000002','แคลคูลัส 2','CALCULUS 2',3,3,0,6),('06000003','สถิติ','STATISTICS',3,3,0,6);
    INSERT INTO prerequisite VALUES ('06000002','06000001','pre'),('06000003','06000002','pre'),('06000004','06000001','pre');
    """)
    yield db
    db.close()


@pytest.mark.parametrize("question", [
    "วิชา 06000002 ชื่ออะไร", "วิชา 06000002 กี่หน่วยกิต", "วิชา 06000002 เรียนปีไหน", "วิชา 06000002 ต้องผ่านวิชาใดก่อน ปี 2",
    "วิชา 06000002 กับ 06000003 ต้องผ่านวิชาใดก่อน", "ต้องผ่านวิชาใดก่อน", "วิชา 99999999 ต้องผ่านวิชาใดก่อน", "hello", "",
    "วิชา 06000002 ต้องผ่านวิชาใดก่อน และอยู่เทอมไหน", "วิชา 06000002 ต้องผ่านวิชาใดก่อน และยากไหม",
    "วิชาที่ไม่ต้องเรียน 06000001 ก่อนมีอะไรบ้าง", "วิชาไหนไม่มีวิชาต่อจาก 06000001", "06000001 ไม่ต้องผ่านวิชาอะไรก่อน",
])
def test_anything_else_is_left_alone(conn, question):
    assert course_overview.prerequisite_lookup(conn, question, lambda c, code: "found") is None


def test_the_direction_follows_where_the_course_stands(conn):
    status = lambda c, code: "found"
    pre = course_overview.prerequisite_lookup(conn, "วิชา 06000002 ต้องผ่านวิชาใดก่อน", status)[0]
    assert "06000001" in pre and "06000003" not in pre
    nxt = course_overview.prerequisite_lookup(conn, "วิชาที่ต้องผ่าน 06000002 ก่อนมีอะไรบ้าง", status)[0]
    assert "06000003" in nxt and "06000001" not in nxt
    by_name = course_overview.prerequisite_lookup(conn, "วิชา แคลคูลัส 2 ต้องผ่านวิชาอะไรก่อน", status)[0]
    assert "06000001" in by_name


def test_a_course_name_that_contains_and_is_not_a_compound_question(conn):
    status = lambda c, code: "found"
    for q in ("วิชา การวิเคราะห์และออกแบบระบบ ต้องผ่านวิชาอะไรก่อน", "วิชา 06000004 ต้องผ่านวิชาใดก่อน"):
        answer = course_overview.prerequisite_lookup(conn, q, status)[0]
        assert "06000004" in answer and "06000001" in answer, q
