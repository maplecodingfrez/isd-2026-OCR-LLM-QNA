"""Informal Thai phrasings used to miss the shortcuts and reach the language model (often answering "ไม่พบข้อมูล"):
"เรียนจบต้องใช้กี่หน่วยกิต", "ปีไหนหน่วยกิตเยอะที่สุด", "lab", "เทอมฤดูร้อน", "X คืออะไร", a partial course name with "อยู่ปีไหน",
"สหกิจเรียนปีไหน" on a plan without co-op, "วิชาไหนมีวิชาบังคับก่อนมากที่สุด". Each is now answered from the data on every plan,
the same as its formal wording, without the model."""

import re
from contextlib import closing

import pytest

import lab8b_curriculum_db as m
from lab10_fastapi.curriculum_app import main

informal = pytest.importorskip("informal_questions", reason="informal_questions.py not added yet")
NOT_FOUND = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"
PLANS = ["ait", "bit_coop", "bit_no_coop", "dsba_coop", "dsba_no_coop", "it_coop", "it_no_coop"]


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


def ask(conn, q):
    return m.ask(conn, q, verbose=False)


SAME_AS = [
    ("เรียนจบต้องใช้กี่หน่วยกิต", "หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต"),
    ("จบหลักสูตรต้องเรียนกี่หน่วยกิต", "หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต"),
    ("ปีไหนหน่วยกิตเยอะที่สุด", "ปีไหนเรียนหน่วยกิตมากที่สุด"),
    ("เทอมไหนหน่วยกิตเยอะสุด", "เทอมไหนเรียนหน่วยกิตมากที่สุด"),
    ("วิชาที่มี lab มากกว่า 2 ชั่วโมงมีอะไรบ้าง", "วิชาที่มีชั่วโมงปฏิบัติมากกว่า 2 ชั่วโมงมีอะไรบ้าง"),
    ("มีวิชาที่เรียนเทอมฤดูร้อนไหม", "มีการเรียนภาคฤดูร้อนไหม"),
]


@pytest.mark.parametrize("plan", PLANS)
@pytest.mark.parametrize("loose,formal", SAME_AS)
def test_an_informal_wording_gets_the_same_answer_as_the_formal_one(plan, loose, formal, no_model):
    with open_plan(plan) as conn:
        a, b = ask(conn, loose), ask(conn, formal)
        assert a["answer"] == b["answer"] and a["answer_type"] == b["answer_type"], (plan, loose, a["answer"][:80])
        assert a["question"] == loose


@pytest.mark.parametrize("plan", PLANS)
@pytest.mark.parametrize("template", ["{n} คืออะไร", "ชื่อภาษาอังกฤษของวิชา {n}", "ชื่อวิชา {c} ภาษาอังกฤษคืออะไร", "{c} คืออะไร"])
def test_what_is_a_course_gets_the_overview(plan, template, no_model):
    with open_plan(plan) as conn:
        c, n = conn.execute("SELECT code, name_th FROM course WHERE code IN (SELECT code FROM v_plan) ORDER BY code LIMIT 1 OFFSET 4").fetchone()
        if conn.execute("SELECT COUNT(*) FROM course WHERE name_th = ?", (n,)).fetchone()[0] != 1:
            pytest.skip("name not unique")
        r = ask(conn, template.format(c=c, n=n))
        assert r["answer_type"] == "course_overview" and r["rows"][0]["code"] == c, (plan, template, r["answer"][:80])


@pytest.mark.parametrize("plan", PLANS)
@pytest.mark.parametrize("template", ["วิชา{w}อยู่ปีไหน", "วิชา {w} เรียนปีไหนเทอมไหน", "{w} เรียนปีไหน"])
def test_a_partial_name_lists_every_plan_course_with_its_year_and_term(plan, template, no_model):
    with open_plan(plan) as conn:
        rows = conn.execute("SELECT DISTINCT code, year, semester FROM v_plan WHERE name_th LIKE '%โครงงาน%' ORDER BY year, semester, code").fetchall()
        if not rows:
            pytest.skip("no project course in this plan")
        r = ask(conn, template.format(w="โครงงาน"))
        assert r["answer_type"] == "database" and NOT_FOUND not in r["answer"], (plan, r["answer"][:80])
        for code, year, sem in rows:
            line = next((l for l in r["answer"].splitlines() if code in l), None)
            assert line and f"ปี {year} เทอม {sem}" in line, (plan, code, r["answer"])


@pytest.mark.parametrize("plan", ["bit_no_coop", "dsba_no_coop", "it_no_coop"])
def test_asking_about_co_op_on_a_plan_without_it_says_so_and_points_to_the_co_op_plan(plan, no_model):
    with open_plan(plan) as conn:
        r = ask(conn, "สหกิจเรียนปีไหน")
        assert "ไม่มีสหกิจ" in r["answer"] and re.search(r"ปี \d เทอม \d", r["answer"]) and NOT_FOUND not in r["answer"], (plan, r["answer"])
        assert r["rows"], plan


@pytest.mark.parametrize("plan", ["bit_coop", "dsba_coop", "it_coop"])
def test_co_op_on_a_co_op_plan_is_unchanged(plan, no_model):
    with open_plan(plan) as conn:
        assert "ไม่มีสหกิจ" not in ask(conn, "สหกิจเรียนปีไหน")["answer"]


@pytest.mark.parametrize("plan", PLANS)
@pytest.mark.parametrize("question", ["วิชาไหนมีวิชาบังคับก่อนมากที่สุด", "วิชาที่มีวิชาบังคับก่อนมากที่สุดคือวิชาอะไร"])
def test_the_course_with_the_most_prerequisites_is_named_with_its_count(plan, question, no_model):
    with open_plan(plan) as conn:
        counts = conn.execute("SELECT p.code, COUNT(DISTINCT p.requires) n FROM prerequisite p JOIN course c ON c.code = p.code GROUP BY p.code ORDER BY n DESC, p.code").fetchall()
        top = counts[0][1]
        winners = [c for c, n in counts if n == top]
        r = ask(conn, question)
        assert all(c in r["answer"] for c in winners) and f"{top} วิชา" in r["answer"], (plan, r["answer"][:120])
        assert not r["answer"].startswith("มี ") or "มากที่สุด" in r["answer"]
        assert {row["code"] for row in r["rows"]} == set(winners)


@pytest.mark.parametrize("question", [
    "เรียนจบ", "คืออะไร", "สหกิจคืออะไร", "โครงงานอยู่", "วิชาไหนมีวิชาบังคับก่อน", "hello", "",
])
def test_unrelated_text_is_left_alone(question):
    assert informal.informal_to_thai(question) is None
