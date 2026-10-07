"""Question shapes that the model-on sweep found unanswered ("ไม่พบข้อมูล") or answered WRONG by the model:
"โครงงานกี่หน่วยกิต" -> 132 (the whole programme), "วิชาที่ 3 หน่วยกิตมีกี่วิชา" -> 46 (counted the whole course table, the plan has 32),
"สหกิจกี่หน่วยกิต" -> 18 (a term total; each co-op course is 6), "เทอมไหนมีวิชามากที่สุด" -> "2 ภาคการศึกษา".
Each is now answered from the plan's own tables on every plan, without the model."""

import re
from contextlib import closing

import pytest

import lab8b_curriculum_db as m
from lab10_fastapi.curriculum_app import main

plan_questions = pytest.importorskip("plan_questions", reason="plan_questions.py not added yet")
NOT_FOUND = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"
PLANS = ["ait", "bit_coop", "bit_no_coop", "dsba_coop", "dsba_no_coop", "it_coop", "it_no_coop"]
COOP, NO_COOP = ["bit_coop", "dsba_coop", "it_coop"], ["bit_no_coop", "dsba_no_coop", "it_no_coop"]


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
    r = m.ask(conn, q, verbose=False)
    assert r["answer_type"] in ("database", "rule", "course_overview"), (q, r["answer_type"], r["answer"][:80])
    assert NOT_FOUND not in r["answer"], (q, r["answer"][:100])
    return r


def plan_courses(conn):
    return conn.execute("SELECT DISTINCT v.code, c.name_th, c.credits FROM v_plan v JOIN course c ON c.code = v.code ORDER BY v.code").fetchall()


# ---- credits filter ----
@pytest.mark.parametrize("plan", PLANS)
def test_courses_with_n_credits_are_counted_and_listed_from_the_plan_only(plan, no_model):
    with open_plan(plan) as conn:
        by_credit = {}
        for code, name, credits in plan_courses(conn):
            by_credit.setdefault(credits, []).append(code)
        n, codes = max(by_credit.items(), key=lambda kv: len(kv[1]))
        count = ask(conn, f"วิชาที่ {n} หน่วยกิตมีกี่วิชา")
        assert f"{len(codes)} วิชา" in count["answer"], (plan, count["answer"])
        listing = ask(conn, f"วิชาที่ {n} หน่วยกิตมีอะไรบ้าง")
        assert all(c in listing["answer"] for c in codes) and len(listing["rows"]) == len(codes), (plan, n)
        assert all(r["credits"] == n for r in listing["rows"])
        assert f"{len(codes)} วิชา" in ask(conn, f"มีวิชา {n} หน่วยกิตกี่วิชา")["answer"]


# ---- counts per year/term, busiest term, biggest course ----
@pytest.mark.parametrize("plan", PLANS)
def test_number_of_courses_in_a_year_or_term(plan, no_model):
    with open_plan(plan) as conn:
        year = conn.execute("SELECT year, COUNT(*) FROM v_plan GROUP BY year ORDER BY year LIMIT 1 OFFSET 1").fetchone()
        assert f"{year[1]} วิชา" in ask(conn, f"ปี {year[0]} มีกี่วิชา")["answer"]
        assert f"{year[1]} วิชา" in ask(conn, f"ปี {year[0]} เรียนกี่วิชา")["answer"]
        term = conn.execute("SELECT year, semester, COUNT(*) FROM v_plan GROUP BY year, semester ORDER BY year, semester LIMIT 1").fetchone()
        assert f"{term[2]} วิชา" in ask(conn, f"ปี {term[0]} เทอม {term[1]} มีกี่วิชา")["answer"]


@pytest.mark.parametrize("plan", PLANS)
def test_the_term_with_the_most_courses_is_named_with_its_count(plan, no_model):
    with open_plan(plan) as conn:
        counts = conn.execute("SELECT year, semester, COUNT(*) n FROM v_plan GROUP BY year, semester ORDER BY n DESC, year, semester").fetchall()
        winners = [c for c in counts if c[2] == counts[0][2]]
        answer = ask(conn, "เทอมไหนมีวิชามากที่สุด")["answer"]
        assert all(f"ปี {y} เทอม {s}" in answer for y, s, _ in winners) and f"{counts[0][2]} วิชา" in answer, (plan, answer)
        years = conn.execute("SELECT year, COUNT(*) n FROM v_plan GROUP BY year ORDER BY n DESC, year").fetchall()
        top_years = [y for y, n in years if n == years[0][1]]
        year_answer = ask(conn, "ปีไหนมีวิชาเยอะที่สุด")["answer"]
        assert all(f"ปี {y}" in year_answer for y in top_years) and f"{years[0][1]} วิชา" in year_answer


@pytest.mark.parametrize("plan", PLANS)
@pytest.mark.parametrize("word,agg", [("มากที่สุด", "MAX"), ("เยอะที่สุด", "MAX"), ("น้อยที่สุด", "MIN")])
def test_the_course_with_the_most_credits_in_a_term(plan, word, agg, no_model):
    with open_plan(plan) as conn:
        rows = conn.execute("SELECT DISTINCT v.code, c.credits FROM v_plan v JOIN course c ON c.code = v.code WHERE v.year = 2 AND v.semester = 1").fetchall()
        if not rows:
            pytest.skip("no courses")
        best = (max if agg == "MAX" else min)(r[1] for r in rows)
        winners = [r[0] for r in rows if r[1] == best]
        answer = ask(conn, f"ปี 2 เทอม 1 วิชาไหนหน่วยกิต{word}")["answer"]
        assert all(c in answer for c in winners) and f"{best} หน่วยกิต" in answer, (plan, answer)


# ---- prerequisite pair yes/no ----
@pytest.mark.parametrize("plan", PLANS)
@pytest.mark.parametrize("template", ["ต้องผ่านวิชา {r} ก่อนเรียน {c} ไหม", "ต้องเรียน {r} ก่อน {c} ไหม", "{r} เป็นวิชาบังคับก่อนของ {c} ไหม"])
def test_is_one_course_a_prerequisite_of_another(plan, template, no_model):
    with open_plan(plan) as conn:
        alt = {(r[0], r[1]) for r in conn.execute("SELECT code, requires FROM prerequisite_alt")}
        pairs = [(c, r) for c, r in conn.execute("SELECT p.code, p.requires FROM prerequisite p JOIN course a ON a.code = p.code JOIN course b ON b.code = p.requires WHERE p.kind = 'pre'") if (c, r) not in alt]
        c, r = pairs[0]
        yes = ask(conn, template.format(c=c, r=r))["answer"]
        assert yes.startswith("ใช่") and c in yes and r in yes, (plan, yes)
        reverse = ask(conn, template.format(c=r, r=c))["answer"]
        assert reverse.startswith("ไม่"), (plan, reverse)


# ---- co-op ----
@pytest.mark.parametrize("plan", COOP)
def test_co_op_questions_on_a_co_op_plan(plan, no_model):
    with open_plan(plan) as conn:
        courses = conn.execute("SELECT DISTINCT v.code, c.credits FROM v_plan v JOIN course c ON c.code = v.code WHERE c.name_th LIKE '%สหกิจ%'").fetchall()
        assert courses
        has = ask(conn, "มีสหกิจไหม")["answer"]
        assert "สหกิจศึกษา" in has and re.search(r"ปี \d เทอม \d", has) and "ไม่มีสหกิจ" not in has
        credits = ask(conn, "สหกิจกี่หน่วยกิต")["answer"]
        assert all(f"{c} " in credits and f"{cr} หน่วยกิต" in credits for c, cr in courses), (plan, credits)


@pytest.mark.parametrize("plan", NO_COOP)
def test_co_op_questions_on_a_plan_without_it(plan, no_model):
    with open_plan(plan) as conn:
        for q in ("มีสหกิจไหม", "สหกิจกี่หน่วยกิต"):
            answer = ask(conn, q)["answer"]
            assert "ไม่มีสหกิจ" in answer and ("หน่วยกิต" in answer or "ปี" in answer), (plan, q, answer)


@pytest.mark.parametrize("plan", PLANS)
def test_a_name_fragment_asks_credits_for_every_match(plan, no_model):
    with open_plan(plan) as conn:
        courses = plan_courses(conn)
        hits = [(c, n, cr) for c, n, cr in courses if "โครงงาน" in n]
        if not hits:
            pytest.skip("no project course")
        answer = ask(conn, "โครงงานกี่หน่วยกิต")["answer"]
        for code, name, credits in hits:
            line = next((l for l in answer.splitlines() if code in l), None)
            assert line and f"{credits} หน่วยกิต" in line, (plan, code, answer)


# ---- follow-ups and "can I take it now" ----
@pytest.mark.parametrize("plan", PLANS)
def test_which_course_must_this_one_come_before(plan, no_model):
    with open_plan(plan) as conn:
        r = conn.execute("SELECT requires FROM prerequisite p JOIN course c ON c.code = p.code WHERE p.kind = 'pre' GROUP BY requires ORDER BY COUNT(*) DESC, requires").fetchone()[0]
        nxt = [x[0] for x in conn.execute("SELECT DISTINCT code FROM prerequisite WHERE requires = ?", (r,))]
        answer = ask(conn, f"วิชา {r} ต้องเรียนก่อนวิชาอะไร")["answer"]
        assert all(c in answer for c in nxt), (plan, answer)


@pytest.mark.parametrize("plan", PLANS)
def test_courses_that_lead_nowhere(plan, no_model):
    with open_plan(plan) as conn:
        required = {r[0] for r in conn.execute("SELECT requires FROM prerequisite")}
        leaf = [c for c, _, _ in plan_courses(conn) if c not in required]
        r = ask(conn, "วิชาไหนไม่มีวิชาต่อ")
        assert {row["code"] for row in r["rows"]} == set(leaf) and f"{len(leaf)} วิชา" in r["answer"], plan


@pytest.mark.parametrize("plan", PLANS)
def test_can_i_take_it_right_away(plan, no_model):
    with open_plan(plan) as conn:
        with_pre = conn.execute("SELECT p.code, p.requires FROM prerequisite p JOIN course a ON a.code = p.code JOIN course b ON b.code = p.requires WHERE p.kind = 'pre' ORDER BY p.code").fetchone()
        none = next((c for c, _, _ in plan_courses(conn) if m.prerequisite_status(conn, c) == "none"), None)
        blocked = ask(conn, f"เรียน {with_pre[0]} ได้เลยไหม")["answer"]
        assert "ไม่ได้" in blocked and with_pre[1] in blocked, (plan, blocked)
        if none:
            assert "ได้เลย" in ask(conn, f"เรียน {none} ได้เลยไหม")["answer"]


# ---- second sweep: leftovers ----
@pytest.mark.parametrize("plan", PLANS)
def test_how_many_courses_in_a_year_asked_the_other_way_round(plan, no_model):
    with open_plan(plan) as conn:
        year = conn.execute("SELECT year, COUNT(*) FROM v_plan GROUP BY year ORDER BY year LIMIT 1 OFFSET 1").fetchone()
        assert f"{year[1]} วิชา" in ask(conn, f"มีกี่วิชาในปี {year[0]}")["answer"]


@pytest.mark.parametrize("plan", COOP + NO_COOP)
def test_the_english_co_op_question_gets_the_thai_answer(plan, no_model):
    with open_plan(plan) as conn:
        for english in ("Is there a co-op option?", "Does this plan have co-op?"):
            a, b = ask(conn, english), ask(conn, "มีสหกิจไหม")
            assert a["answer"] == b["answer"] and a["question"] == english


@pytest.mark.parametrize("plan", PLANS)
def test_two_course_codes_compare_side_by_side(plan, no_model):
    with open_plan(plan) as conn:
        a, b = [r[0] for r in conn.execute("SELECT DISTINCT code FROM v_plan WHERE code IN (SELECT code FROM course) ORDER BY year, semester, code LIMIT 2")]
        for question in (f"เปรียบเทียบ {a} กับ {b}", f"เปรียบเทียบวิชา {a} กับ {b}"):
            r = ask(conn, question)
            assert a in r["answer"] and b in r["answer"] and r["answer"].count("เรียนปี") == 2, (plan, r["answer"])
            assert [row["code"] for row in r["rows"]] == [a, b]


def test_failing_a_course_is_asked_like_the_formal_wording(no_model):
    with open_plan("dsba_coop") as conn:
        a, b = ask(conn, "ถ้าตก 06066300 กระทบอะไร"), ask(conn, "ถ้าสอบตก 06066300 กระทบอะไร")
        assert a["answer"] == b["answer"] and "06026212" in a["answer"]


# ---- wording and topics ----
@pytest.mark.parametrize("plan", PLANS)
def test_what_do_i_study_without_the_word_list(plan, no_model):
    with open_plan(plan) as conn:
        a, b = ask(conn, "ปี 2 เทอม 1 เรียนอะไร"), ask(conn, "ปี 2 เทอม 1 เรียนอะไรบ้าง")
        assert a["answer"] == b["answer"]


@pytest.mark.parametrize("plan", PLANS)
def test_a_topic_finds_courses_in_the_plan_and_among_the_electives(plan, no_model):
    from lab10_fastapi.curriculum_app import course_search
    with open_plan(plan) as conn:
        for topic, question in (("ฐานข้อมูล", "วิชาที่เกี่ยวกับฐานข้อมูลมีอะไรบ้าง"), ("ฐานข้อมูล", "มีวิชาเกี่ยวกับฐานข้อมูลไหม"), ("AI", "วิชาที่เกี่ยวกับ AI มีอะไรบ้าง")):
            found = course_search.search_courses(conn, topic, limit=500)
            if not found:
                continue
            r = ask(conn, question)
            assert all(f["code"] in r["answer"] for f in found[:5]), (plan, question)
            assert {row["code"] for row in r["rows"]} >= {f["code"] for f in found[:5]}


def test_a_topic_with_no_match_says_so_naming_the_topic(no_model):
    with open_plan("dsba_coop") as conn:
        r = m.ask(conn, "มีวิชาเกี่ยวกับควอนตัมเทเลพอร์ตไหม", verbose=False)
        assert "ควอนตัมเทเลพอร์ต" in r["answer"] and r["rows"] == []


@pytest.mark.parametrize("question", [
    "วิชาที่ 3 หน่วยกิต", "ปี 2", "เทอมไหน", "สหกิจ", "ต้องผ่าน ก่อนเรียน ไหม", "เกี่ยวกับ", "hello", "",
    "มีวิชาเกี่ยวกับเครือข่ายไหม และยากไหม", "วิชาที่เกี่ยวกับเครือข่ายมีอะไรบ้าง และกี่หน่วยกิต",
])
def test_unrelated_text_is_left_alone(question):
    with open_plan("dsba_coop") as conn:
        assert plan_questions.plan_question_answer(conn, question) is None
