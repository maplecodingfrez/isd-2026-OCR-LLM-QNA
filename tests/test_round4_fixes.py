"""รอบ 4: คำถามสองข้อที่เคยตอบไม่ครบ (ผ่านโมเดล)
1) "เรียนจบหลักสูตรนี้ต้องเรียนครบกี่หน่วยกิต และมีเกณฑ์อะไรบ้าง" ตอบแค่ "132 หน่วยกิต" ไม่มีเกณฑ์ → ต้องตอบหน่วยกิตรวม + เกณฑ์จากเล่ม พร้อมหน้าอ้างอิง
2) "วิชาที่มีหน่วยกิตมากที่สุดคือวิชาอะไร" ตอบวิชาเดียวทั้งที่เสมอกัน (สหกิจ 2 วิชา 6 หน่วยกิต) → ต้องบอกทุกวิชาที่เสมอกัน
ทั้งสองต้องไม่เรียกโมเดล (ตอบด้วยกฎจาก DB)"""

from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
PLANS = ["AIT", "BIT/coop", "BIT/no_coop", "DSBA/coop", "DSBA/no_coop", "IT/coop", "IT/no_coop"]


def _ask(rel, question, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("must be answered by a rule, not the model"))
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        return m.ask(conn, question, verbose=False), conn


def _truth(rel):
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        total = conn.execute("SELECT total_credits FROM program").fetchone()[0]
        criteria = m._clean_book_body(conn.execute("SELECT body FROM book_section WHERE topic = 'เกณฑ์สำเร็จการศึกษา'").fetchone()[0])
        best = conn.execute("SELECT MAX(c.credits) FROM course c JOIN plan_item p ON p.code = c.code").fetchone()[0]
        tops = [r[0] for r in conn.execute(
            "SELECT DISTINCT c.code FROM course c JOIN plan_item p ON p.code = c.code WHERE c.credits = ?", (best,))]
    return total, criteria, best, tops


@pytest.mark.parametrize("rel", PLANS)
@pytest.mark.parametrize("question", [
    "เรียนจบหลักสูตรนี้ต้องเรียนครบกี่หน่วยกิต และมีเกณฑ์อะไรบ้าง",
    "ต้องเรียนกี่หน่วยกิตถึงจะจบ แล้วเกณฑ์การจบมีอะไรบ้าง",
])
def test_total_credits_and_graduation_criteria(rel, question, monkeypatch):
    total, criteria, _best, _tops = _truth(rel)
    result, _ = _ask(rel, question, monkeypatch)
    assert f"{total} หน่วยกิต" in result["answer"]
    assert criteria[:40] in result["answer"]                       # เกณฑ์มาจากเล่มตรง ๆ ไม่ใช่โมเดลเรียบเรียง
    topics = {r.get("topic") for r in result["rows"]}
    assert {"หน่วยกิตตลอดหลักสูตร", "เกณฑ์สำเร็จการศึกษา"} <= topics
    assert all(r.get("pdf_page") for r in result["rows"])         # มีหน้าอ้างอิงทุกแถว


@pytest.mark.parametrize("question", [
    "ปี 2 ต้องเรียนกี่หน่วยกิต และมีเกณฑ์อะไรบ้าง",             # มีปี = ไม่ใช่ทั้งหลักสูตร → ไม่ใช่กฎนี้
    "เกณฑ์การรับสมัครมีอะไรบ้าง และรับกี่คน",                  # ไม่ใช่เรื่องจบ/หน่วยกิต
])
def test_criteria_rule_does_not_swallow_other_questions(question):
    with closing(m.open_db(RUNS / "DSBA/coop/lab8b_output/curriculum.db", readonly=True)) as conn:
        assert m._total_and_criteria_answer(conn, question) is None


@pytest.mark.parametrize("rel", PLANS)
@pytest.mark.parametrize("question", [
    "วิชาที่มีหน่วยกิตมากที่สุดคือวิชาอะไร",
    "วิชาไหนมีหน่วยกิตสูงสุด",
])
def test_max_credit_course_lists_every_tie(rel, question, monkeypatch):
    _total, _crit, best, tops = _truth(rel)
    result, _ = _ask(rel, question, monkeypatch)
    assert f"{best} หน่วยกิต" in result["answer"]
    assert {r["code"] for r in result["rows"]} == set(tops)       # เสมอกันต้องครบทุกวิชา ไม่ใช่วิชาเดียว
    if len(tops) > 1:
        assert f"{len(tops)} วิชา" in result["answer"]


def test_coop_tie_names_both_courses(monkeypatch):
    result, _ = _ask("DSBA/coop", "วิชาที่มีหน่วยกิตมากที่สุดคือวิชาอะไร", monkeypatch)
    assert "06026259" in result["answer"] and "06026260" in result["answer"]


@pytest.mark.parametrize("question", [
    "เทอมไหนมีหน่วยกิตมากที่สุด",                               # ถามเทอม → กฎเดิม _extreme_credits_answer
    "วิชา Calculus 1 กี่หน่วยกิต",                              # วิชาเดียว ไม่ใช่ extreme
    "วิชาไหนมีชั่วโมงบรรยายมากที่สุด",                         # ชั่วโมง ไม่ใช่หน่วยกิต → กฎเดิม
])
def test_credit_extreme_rule_leaves_other_questions(question):
    with closing(m.open_db(RUNS / "DSBA/coop/lab8b_output/curriculum.db", readonly=True)) as conn:
        assert m._extreme_credit_course_answer(conn, question) is None
