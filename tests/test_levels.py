import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Lab9_evaluation"))
import levels  # noqa: E402

MAP = [
    {"code": "06016401", "name_th": "คณิตศาสตร์สำหรับเทคโนโลยีสารสนเทศ", "year": "1", "semester": "1",
     "primary_pages": "23;38;324", "other_pages": ""},
    {"code": "06016402", "name_th": "พื้นฐานทางด้านเทคโนโลยีสารสนเทศ", "year": "1", "semester": "1",
     "primary_pages": "23;38", "other_pages": "90"},
]


# Break caught: mis-leveling ch1 examples (field lookup = 1, table/aggregate = 2, unanswerable = none).
def test_question_level_rules():
    assert levels.question_level("รหัสวิชา 06016401 มีชื่อภาษาไทยว่าอะไร", "value") == "1"
    assert levels.question_level("วิชา 'แคลคูลัส 1' มีรหัสวิชาอะไร", "value") == "1"
    assert levels.question_level("หลักสูตรนี้ประกาศจำนวนหน่วยกิตรวมตลอดหลักสูตรไว้กี่หน่วยกิต", "value") == "1"
    assert levels.question_level("ชั้นปีที่ 1 ภาคการศึกษาที่ 1 เรียนรวมทั้งหมดกี่หน่วยกิต", "value") == "2"
    assert levels.question_level("มีรายวิชากี่วิชาที่มีหน่วยกิตเท่ากับ 3", "value") == "2"
    assert levels.question_level("ในฐานข้อมูลนี้มีคู่ความสัมพันธ์วิชาบังคับก่อน (prerequisite) ทั้งหมดกี่คู่", "value") == "2"
    assert levels.question_level("ค่าธรรมเนียมการศึกษา (ค่าเทอม) ของหลักสูตรนี้ต่อภาคการศึกษาคือเท่าไร", "none") == "none"


# Break caught: expected pages from the wrong source (code in expect value, term = most common page).
def test_expected_pages():
    assert levels.expected_pages("รหัสวิชา 06016402 มีชื่อภาษาไทยว่าอะไร", "x", MAP) == {23, 38}  # primary only
    assert levels.expected_pages("วิชา 'คณิตศาสตร์สำหรับ เทคโนโลยีสารสนเทศ' มีรหัสวิชาอะไร", "06016401", MAP) == {23, 38, 324}
    assert levels.expected_pages("ชั้นปีที่ 1 ภาคการศึกษาที่ 1 เรียนรวมทั้งหมดกี่หน่วยกิต", "18", MAP) == {23, 38}
    assert levels.expected_pages("มีรายวิชากี่วิชาที่มีหน่วยกิตเท่ากับ 3", "31", MAP) is None


# Break caught: counting a citation as correct when it misses every expected page.
def test_level_stats():
    rows = [
        {"question": "รหัสวิชา 06016401 มีกี่หน่วยกิต", "expect": {"type": "value", "value": "3"},
         "correct": True, "citations": [{"pdf_page": 38, "printed_page": "33"}]},
        {"question": "รหัสวิชา 06016402 มีกี่หน่วยกิต", "expect": {"type": "value", "value": "3"},
         "correct": True, "citations": [{"pdf_page": 500, "printed_page": None}]},
        {"question": "มีรายวิชากี่วิชาที่มีหน่วยกิตเท่ากับ 3", "expect": {"type": "value", "value": "2"},
         "correct": False, "citations": []},
    ]
    stats = levels.level_stats(rows, MAP)
    assert stats["1"] == {"n": 2, "correct": 2, "with_citation": 2, "cite_checkable": 2, "cite_hit": 1}
    assert stats["2"] == {"n": 1, "correct": 0, "with_citation": 0, "cite_checkable": 0, "cite_hit": 0}


# Break caught (review minor #3): a question the book cannot answer counted as a citation miss when not cited.
def test_level_stats_none_questions_are_not_citation_checkable():
    rows = [{"question": "รายวิชา 06016401 มีอาจารย์ผู้สอนประจำวิชาชื่อว่าอะไร", "expect": {"type": "none"},
             "correct": True, "citations": []}]
    assert levels.level_stats(rows, MAP)["none"] == {
        "n": 1, "correct": 1, "with_citation": 0, "cite_checkable": 0, "cite_hit": 0}


# Break caught (review minor #4): a course with only "other" pages (mentioned, never with its name) gets no expected page.
def test_expected_pages_falls_back_to_other_pages():
    only_other = [{"code": "06016499", "name_th": "x", "year": "", "semester": "",
                   "primary_pages": "", "other_pages": "77;78"}]
    assert levels.expected_pages("รหัสวิชา 06016499 มีกี่หน่วยกิต", "3", only_other) == {77, 78}


# Break caught: colloquial v2 wording ("ปี 2 เทอม 1") mis-levelled by the regex — the question's own level wins.
def test_level_field_overrides_regex():
    assert levels.question_level("ปี 2 เทอม 1 ต้องลงเรียนกี่วิชา", "value", "2") == "2"
    assert levels.question_level("ปี 2 เทอม 1 ต้องลงเรียนกี่วิชา", "value") == "1"   # v1 behaviour kept


# Break caught: name-based / colloquial questions getting no expected page (or pages of the answer codes).
def test_expected_pages_for_uses_about_codes_and_term():
    about = {"question": "แคลคูลัส เรียนตอนปีไหน", "expect": {"type": "value", "value": "1"},
             "about_codes": ["06016402"]}
    assert levels.expected_pages_for(about, MAP) == {23, 38}
    term = {"question": "ปี 1 เทอม 1 เรียนรวมกี่หน่วยกิต", "expect": {"type": "value", "value": "18"}, "term": [1, 1]}
    assert levels.expected_pages_for(term, MAP) == {23, 38}
    v1 = {"question": "รหัสวิชา 06016402 มีชื่อภาษาไทยว่าอะไร", "expect": {"type": "value", "value": "x"}}
    assert levels.expected_pages_for(v1, MAP) == {23, 38}


def test_level_stats_reads_level_field():
    rows = [{"question": "ปี 1 เทอม 1 เรียนรวมกี่หน่วยกิต", "expect": {"type": "value", "value": "18"},
             "level": "2", "term": [1, 1], "correct": True, "citations": [{"pdf_page": 23}]}]
    s = levels.level_stats(rows, MAP)["2"]
    assert (s["n"], s["correct"], s["cite_checkable"], s["cite_hit"]) == (1, 1, 1, 1)
