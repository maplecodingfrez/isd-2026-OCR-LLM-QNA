"""Plan-aware sample questions: each plan's samples are built from that plan's own database.

Every sample must answer from the data (not "not found") in Thai and in English, for all 7 plans; a sample that
the plan cannot answer (no co-op sibling, no free-elective slot, no GE structure ...) is left out, not faked.
"""

import re
from contextlib import closing

import pytest
import requests
from starlette.testclient import TestClient

from lab10_fastapi.curriculum_app import main
import lab8b_curriculum_db as m

sample_questions = pytest.importorskip("lab10_fastapi.curriculum_app.sample_questions", reason="sample_questions.py not added yet")

PLANS = ["ait", "bit_coop", "bit_no_coop", "dsba_coop", "dsba_no_coop", "it_coop", "it_no_coop"]
TOPICS = {"credits", "term", "course", "prereq", "withdraw", "compare"}
NOT_FOUND = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"           # the real "no answer" sentence (a correct answer may say "ไม่พบ" about one part)


def db_path(plan):
    path = main.program_db_path(plan)
    if path is None or not path.exists():
        pytest.skip(f"needs the {plan} database")
    return path


def samples(plan):
    with closing(m.open_db(db_path(plan), readonly=True)) as conn:
        sibling = (m._sibling_plan_db(conn) or (None, None))[1] is not None
        return sample_questions.build_samples(conn, sibling), sibling


def examples(plan):
    topics, _ = samples(plan)
    return [(t["key"], e) for t in topics for e in t["examples"]]


@pytest.fixture()
def no_model(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the language model must not be needed")
    monkeypatch.setattr(m, "ollama_generate", refuse)


def ollama_up():
    try:
        return requests.get(main.settings.ollama_url.rstrip("/") + "/api/tags", timeout=2).ok
    except Exception:
        return False


@pytest.mark.parametrize("plan", PLANS)
def test_every_plan_gets_topics_with_two_or_three_examples_each(plan):
    topics, sibling = samples(plan)
    keys = [t["key"] for t in topics]
    assert set(keys) <= TOPICS and len(keys) == len(set(keys))
    assert {"credits", "term", "course"} <= set(keys)
    assert all(2 <= len(t["examples"]) <= 3 for t in topics)
    assert ("compare" in keys) == sibling                                   # no co-op sibling (AIT) = no co-op comparison


@pytest.mark.parametrize("plan", PLANS)
def test_examples_have_both_languages_and_use_real_courses(plan):
    with closing(m.open_db(db_path(plan), readonly=True)) as conn:
        known = {r[0] for r in conn.execute("SELECT code FROM course")}
    for key, e in examples(plan):
        assert e["th"].strip() and e["en"].strip() and e["label_th"].strip() and e["label_en"].strip(), (plan, key, e)
        assert isinstance(e["needs_model"], bool)
        th_codes, en_codes = re.findall(r"\d{8}", e["th"]), re.findall(r"\d{8}", e["en"])
        assert th_codes == en_codes, (plan, e)                              # the same course in both languages
        assert set(th_codes) <= known, (plan, e, "course not in this plan")
        assert not re.search(r"[฀-๿]", e["en"]) or re.search(r"[A-Za-z]{3}", e["en"])


@pytest.mark.parametrize("plan", PLANS)
def test_a_sample_is_only_offered_when_the_plan_can_answer_it(plan):
    with closing(m.open_db(db_path(plan), readonly=True)) as conn:
        has_lab = conn.execute("SELECT COUNT(*) FROM course WHERE lab_h > 2").fetchone()[0] > 0
        has_ge = conn.execute("SELECT COUNT(*) FROM credit_structure WHERE name_th LIKE '%ศึกษาทั่วไป%'").fetchone()[0] > 0
        has_free = conn.execute("SELECT COUNT(*) FROM plan_slot WHERE name_th LIKE '%เสรี%'").fetchone()[0] > 0
        has_structure = conn.execute("SELECT COUNT(*) FROM credit_structure").fetchone()[0] > 0
    thai = " ".join(e["th"] for _, e in examples(plan))
    # a plan without a credit structure must not be offered a question whose answer is "no structure data"
    assert ("หมวดวิชาเฉพาะเลือกเก็บกี่หน่วยกิต" in thai) == (has_structure and not has_ge)
    assert ("ปี 4 เรียนรวมกี่หน่วยกิต" in thai) == (not has_structure)
    assert ("ชั่วโมงปฏิบัติมากกว่า" in thai) == has_lab
    assert ("หมวดวิชาศึกษาทั่วไป" in thai) == has_ge
    assert ("วิชาเลือกเสรีต้องลงตอนปีไหน" in thai) == has_free


@pytest.mark.parametrize("plan", PLANS)
def test_samples_that_need_no_model_answer_from_the_data_in_thai_and_english(plan, no_model):
    with closing(m.open_db(db_path(plan), readonly=True)) as conn:
        checked = 0
        for key, e in examples(plan):
            if e["needs_model"]:
                continue
            for language in ("th", "en"):
                r = m.ask(conn, e[language], verbose=False)
                assert not r["error"], (plan, key, e[language])
                answer = str(r["answer"])
                assert answer.strip() and NOT_FOUND not in answer, (plan, key, e[language], answer[:80])
                assert not answer.startswith("ไม่มีข้อมูล"), (plan, key, e[language], answer[:80])     # "no data" is not a sample answer
                assert r["answer_type"] != "ai", (plan, key, e[language])
            checked += 1
        assert checked >= 6                                                 # most samples are answered straight from the data


@pytest.mark.skipif(not ollama_up(), reason="needs Ollama for the questions that use the model")
@pytest.mark.parametrize("plan", PLANS)
def test_samples_that_use_the_model_also_answer(plan):
    with closing(m.open_db(db_path(plan), readonly=True)) as conn:
        for key, e in examples(plan):
            if not e["needs_model"]:
                continue
            for language in ("th", "en"):
                r = m.ask(conn, e[language], verbose=False)
                answer = str(r["answer"])
                assert not r["error"] and answer.strip() and NOT_FOUND not in answer, (plan, key, e[language], answer[:80])


@pytest.fixture()
def client():
    return TestClient(main.app)


def test_endpoint_returns_the_topics_for_the_selected_plan(client):
    db_path("dsba_coop")
    body = client.get("/api/sample-questions", params={"program": "dsba_coop"}).json()
    assert {t["key"] for t in body["topics"]} <= TOPICS and body["topics"]
    first = body["topics"][0]["examples"][0]
    assert set(first) >= {"label_th", "label_en", "th", "en", "needs_model"}
    ait = client.get("/api/sample-questions", params={"program": "ait"}).json() if main.program_db_path("ait").exists() else None
    if ait:
        assert "compare" not in {t["key"] for t in ait["topics"]}


def test_endpoint_rejects_an_unknown_plan_and_a_missing_database(client, monkeypatch, tmp_path):
    assert client.get("/api/sample-questions", params={"program": "nope"}).status_code == 404
    monkeypatch.setattr(main, "program_db_path", lambda program: tmp_path / "missing.db")
    assert client.get("/api/sample-questions", params={"program": "it_coop"}).status_code == 503
