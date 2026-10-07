"""English questions: recognised templates become the Thai question the shortcuts already answer.

Before this, English went to the language model: "any database courses?" returned Calculus 2, and
"what is affected if I withdraw from 06026200?" and the co-op comparison returned "not found".
Pure translation tests need nothing; the answer tests run the real DSBA co-op database with the model switched off.
"""

from contextlib import closing
from pathlib import Path

import pytest

english_questions = pytest.importorskip("english_questions", reason="english_questions.py not added yet")
import lab8b_curriculum_db as m  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DSBA = REPO / "Lab7B_Lab8B_ocr_system" / "runs" / "DSBA" / "coop" / "lab8b_output" / "curriculum.db"

TOTAL = "หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต"
COMPARE = "แผนสหกิจกับไม่สหกิจต่างกันอย่างไร"
TRANSLATIONS = [
    ("How many credits in total does the program have?", TOTAL),
    ("What is the total number of credits in the curriculum?", TOTAL),
    ("How many credits do I need to graduate?", TOTAL),
    ("How many credits in year 1 semester 1?", "ปี 1 เทอม 1 เรียนกี่หน่วยกิต"),
    ("how many credits are there in year 2, term 2", "ปี 2 เทอม 2 เรียนกี่หน่วยกิต"),
    ("How many credits in year 3?", "ปี 3 เรียนรวมกี่หน่วยกิต"),
    ("What courses are in year 2 semester 1?", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง"),
    ("Which courses must I take in year 4 semester 2?", "ปี 4 เทอม 2 เรียนวิชาอะไรบ้าง"),
    ("List the subjects in year 1 term 2", "ปี 1 เทอม 2 เรียนวิชาอะไรบ้าง"),
    ("What courses are in year 3 semester 1 and how many credits in total?", "ปี 3 เทอม 1 มีวิชาอะไรบ้าง และรวมกี่หน่วยกิต"),
    ("What courses are in year 2?", "ปี 2 เรียนวิชาอะไรบ้าง"),
    ("How many credits are required in each course category?", "หมวดวิชาเฉพาะเลือกเก็บกี่หน่วยกิต"),
    ("What are the elective courses of this program?", "วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง"),
    ("Which year do I take the free electives?", "วิชาเลือกเสรีต้องลงตอนปีไหน"),
    ("Are there any database courses?", "มีวิชาเกี่ยวกับฐานข้อมูลไหม"),                  # a known topic word becomes its Thai word
    ("Is there a course about networks?", "มีวิชาเกี่ยวกับเครือข่ายไหม"),
    ("Are there any machine learning courses?", "มีวิชาเกี่ยวกับการเรียนรู้ของเครื่องไหม"),
    ("Is there a course about Robotics?", "มีวิชาเกี่ยวกับ Robotics ไหม"),               # an unknown topic stays as typed
    ("What are the prerequisites of 06026201?", "วิชา 06026201 ต้องผ่านวิชาใดก่อน"),
    ("Year 2 semester 1: which courses?", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง"),                    # a capital letter must not matter
    ("Which courses require 06026200 first?", "วิชาที่ต้องผ่าน 06026200 ก่อนมีอะไรบ้าง"),
    ("What is affected if I withdraw from 06026200?", "ถ้าถอนวิชา 06026200 จะกระทบกับอะไร"),
    ("What happens if I drop Calculus 1?", "ถ้าถอนวิชา Calculus 1 จะกระทบกับอะไร"),
    ("Does 06026200 have follow-up courses?", "วิชา 06026200 มีวิชาต่อไหม"),
    ("What can I take after 06026200?", "วิชา 06026200 มีวิชาต่อไหม"),
    ("How do the co-op and non co-op plans differ?", COMPARE),
    ("What is the difference between the co-op and non-co-op plan?", COMPARE),
    ("How many credits does 06026201 have?", "วิชา 06026201 มีกี่หน่วยกิต"),
    ("How many credits is Database System Concepts?", "วิชา Database System Concepts มีกี่หน่วยกิต"),
    ("Which year is 06066300 taught?", "วิชา 06066300 เรียนปีไหนเทอมไหน"),
    ("What is the name of course 06066300?", "วิชา 06066300 ชื่ออะไร"),
    ("How many credits does the general education category need?", "หมวดวิชาศึกษาทั่วไปต้องเรียนกี่หน่วยกิต"),
    ("How do the co-op and non co-op plans differ in year 4 semester 1?", "แผนสหกิจกับไม่สหกิจ ปี 4 เทอม 1 ต่างกันยังไง"),
    ("Which courses have more than 2 lab hours per week?", "วิชาที่มีชั่วโมงปฏิบัติมากกว่า 2 ชั่วโมงมีอะไรบ้าง"),
    ("How many prerequisite pairs are there in total?", "ในฐานข้อมูลนี้มีคู่วิชากับวิชาบังคับก่อนทั้งหมดกี่คู่"),
    ("What does the non co-op plan add compared with the co-op plan?", COMPARE),
]


# answered from the database by the existing shortcuts (the others use the model for part of the work)
MODEL_FREE = {
    "How many credits in total does the program have?",
    "How many credits in year 1 semester 1?",
    "What courses are in year 2 semester 1?",
    "What courses are in year 3 semester 1 and how many credits in total?",
    "What are the elective courses of this program?",
    "What is affected if I withdraw from 06026200?",
    "How do the co-op and non co-op plans differ?",
}


@pytest.mark.parametrize("english,thai", TRANSLATIONS)
def test_english_template_becomes_its_thai_question(english, thai):
    assert english_questions.english_to_thai(english) == thai


@pytest.mark.parametrize("text", [
    "", "hello", "What is the weather today?", "How many credits?", "What courses are there?",
    "What is the course code of Database System Concepts?",              # the pipeline already has its own handler for this one
    "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง", "ปี 2 term 1 เรียนอะไรบ้าง", "วิชา 06026201 ต้องผ่านวิชาใดก่อน",
])
def test_anything_else_is_left_alone(text):
    assert english_questions.english_to_thai(text) is None


def test_english_and_thai_give_the_same_answer_on_the_real_database(monkeypatch):
    if not DSBA.exists():
        pytest.skip("needs the DSBA co-op database")
    def no_model(*args, **kwargs):
        raise AssertionError("the language model must not be needed for these questions")
    monkeypatch.setattr(m, "ollama_generate", no_model)
    checked = 0
    with closing(m.open_db(DSBA, readonly=True)) as conn:
        for english, thai in TRANSLATIONS:
            if "Robotics" in english or "networks" in english or "machine learning" in english or "Calculus" in english or "Database System Concepts" in english:
                continue                                    # topic and name questions go through the name resolver, covered below
            if english == "What courses are in year 2?":
                continue                                    # the Thai year-only question itself asks the model; translation is checked above
            en = m.ask(conn, english, verbose=False)
            th = m.ask(conn, thai, verbose=False)
            assert en["answer"] == th["answer"], english
            assert en["question"] == english                # the user's own words are kept
            assert en["answer_type"] == th["answer_type"], english
            if english in MODEL_FREE:
                assert en["answer_type"] != "ai", english        # these are answered from the data, no model
            checked += 1
    assert checked >= 15


def test_topic_and_course_name_questions_match_their_thai_form(monkeypatch):
    if not DSBA.exists():
        pytest.skip("needs the DSBA co-op database")
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model used")))
    with closing(m.open_db(DSBA, readonly=True)) as conn:
        for english in ["What happens if I drop Calculus 1?", "How many credits is Database System Concepts?"]:
            thai = english_questions.english_to_thai(english)
            assert m.ask(conn, english, verbose=False)["answer"] == m.ask(conn, thai, verbose=False)["answer"], english
        assert "06066300" in m.ask(conn, "How many credits is Database System Concepts?", verbose=False)["answer"]
