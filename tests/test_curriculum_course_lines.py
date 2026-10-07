"""Lab 11: layered course lines (code | name | credits and hours) parsed from the backend answer text.

The backend text stays unchanged; app.js splits each course line for display and falls back to plain text.
Skipped when static/ is the old UI without parseCourseLine.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
APP_JS = REPO / "lab10_fastapi" / "curriculum_app" / "static" / "app.js"
NODE = shutil.which("node")

pytestmark = [
    pytest.mark.skipif(NODE is None, reason="ต้องมี node เพื่อรันตรรกะ JS"),
    pytest.mark.skipif("parseCourseLine" not in APP_JS.read_text(encoding="utf-8"), reason="static/ ยังไม่มี parseCourseLine"),
]

COURSE = "06016403 เทคโนโลยีสื่อประสม / MULTIMEDIA TECHNOLOGY — 3 (2-2-5) หน่วยกิต"
LAST = "06066304 การวิเคราะห์ / INFORMATION SYSTEM ANALYSIS — 3 (3-0-6) หน่วยกิต (รวม 18 หน่วยกิต, 6 วิชา/ช่องในแผน; กลุ่มทางเลือกนับหนึ่งรายการ)"
SLOT = "ช่องที่นักศึกษาเลือกเอง: วิชาเลือกกลุ่มวิทยาการข้อมูล 1 3 (3-0-6) หรือ 3 (2-2-5) หน่วยกิต"


def run_js(tmp_path, body):
    script = tmp_path / "case.js"
    script.write_text(f"const m = require({json.dumps(APP_JS.as_posix())});\n{body}\n", encoding="utf-8")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def parse(tmp_path, *texts):
    return run_js(tmp_path, f"process.stdout.write(JSON.stringify({json.dumps(list(texts), ensure_ascii=False)}.map(m.parseCourseLine)));")


def test_course_line_is_split_into_code_names_credits_and_hours(tmp_path):
    (entry,) = parse(tmp_path, COURSE)
    assert entry["kind"] == "course" and entry["code"] == "06016403"
    assert entry["name"] == "เทคโนโลยีสื่อประสม" and entry["nameEn"] == "MULTIMEDIA TECHNOLOGY"
    assert entry["credits"] == "3" and entry["hours"] == ["2", "2", "5"]
    assert entry["lead"] == "" and entry["note"] is None


def test_term_heading_and_total_note_are_kept_apart_from_the_course(tmp_path):
    first, last = parse(tmp_path, "ปี 2 เทอม 1: " + COURSE, LAST)
    assert first["lead"] == "ปี 2 เทอม 1:" and first["code"] == "06016403"
    assert last["code"] == "06066304" and last["note"].startswith("รวม 18 หน่วยกิต")
    assert "นับหนึ่งรายการ" in last["note"]            # the "; " inside the parentheses must not split the note


def test_elective_slot_keeps_every_credit_option(tmp_path):
    (slot,) = parse(tmp_path, SLOT)
    assert slot["kind"] == "slot" and slot["name"] == "วิชาเลือกกลุ่มวิทยาการข้อมูล 1"
    assert slot["credits"] == "3 (3-0-6) หรือ 3 (2-2-5)"


def test_course_without_english_name_or_hours_still_parses(tmp_path):
    (entry,) = parse(tmp_path, "06010001 วิชาก — 3 หน่วยกิต")
    assert entry["name"] == "วิชาก" and entry["nameEn"] == "" and entry["hours"] is None


@pytest.mark.parametrize("text", ["06026200", "ไม่พบข้อมูลนี้ในเล่มหลักสูตร", "", "18 ครั้ง", "06016403 ชื่อ — 3 หน่วยกิตเกิน"])
def test_lines_that_are_not_course_lines_fall_back_to_plain_text(tmp_path, text):
    assert parse(tmp_path, text) == [None]


def test_consecutive_course_paragraphs_become_one_block_and_others_stay(tmp_path):
    out = run_js(tmp_path, f'''
      const paragraphs = {json.dumps([COURSE, LAST, SLOT, "ข้อความอื่น"], ensure_ascii=False)}.map(text => ({{type: "paragraph", text}}));
      const blocks = m.groupCourseBlocks(paragraphs.concat([{{type: "list", items: ["x"]}}]));
      process.stdout.write(JSON.stringify(blocks.map(b => b.type + ":" + (b.entries ? b.entries.length : 1))));
    ''')
    assert out == ["courses:3", "paragraph:1", "list:1"]


def test_bare_code_and_name_answer_becomes_a_line_without_credits(tmp_path):
    (entry,) = parse(tmp_path, "06026200 (แคลคูลัส 1)")
    assert entry["kind"] == "course" and entry["code"] == "06026200" and entry["name"] == "แคลคูลัส 1"
    assert entry["credits"] is None and entry["hours"] is None


def test_withdrawal_path_suffix_is_kept_as_a_tag(tmp_path):
    (entry,) = parse(tmp_path, "06026201 แคลคูลัส 2 / CALCULUS 2 — 3 (3-0-6) หน่วยกิต (เส้นทาง 06026200 → 06026201)")
    assert entry["code"] == "06026201" and entry["path"] == "06026200 → 06026201"
    assert entry["credits"] == "3" and entry["hours"] == ["3", "0", "6"]


def test_bulleted_course_lists_are_grouped_but_mixed_lists_are_not(tmp_path):
    out = run_js(tmp_path, '''
      const line = "06026201 แคลคูลัส 2 / CALCULUS 2 — 3 (3-0-6) หน่วยกิต (เส้นทาง 06026200 → 06026201)";
      const blocks = m.groupCourseBlocks([{type: "list", items: [line]}, {type: "list", items: [line, "ข้อความอื่น"]}]);
      process.stdout.write(JSON.stringify(blocks.map(b => b.type)));
    ''')
    assert out == ["courses", "list"]


@pytest.mark.parametrize("display,expected", [
    ("3 (2-2-5)", {"credits": "3", "hours": ["2", "2", "5"]}),
    (3, {"credits": "3", "hours": None}),
    ("", {"credits": "", "hours": None}),
])
def test_split_credits_from_the_api_display_value(tmp_path, display, expected):
    out = run_js(tmp_path, f"process.stdout.write(JSON.stringify(m.splitCredits({json.dumps(display)})));")
    assert out == expected


def test_prerequisite_tag_marks_co_requisites_and_option_groups_only(tmp_path):
    out = run_js(tmp_path, '''
      const tag = c => m.prereqTag(c);
      process.stdout.write(JSON.stringify([tag({kind: "pre"}), tag({kind: "co"}), tag({kind: "pre", alternative_group: 2})]));
    ''')
    assert out[0] == "" and out[1] == "เรียนร่วมกัน" and "กลุ่ม 2" in out[2] and "ผ่านอย่างใดอย่างหนึ่ง" in out[2]


# ---------- credit structure answers: "หมวด: N หน่วยกิต — ประกอบด้วย กลุ่ม n, กลุ่ม n ..." ----------

GE = "หมวดวิชาศึกษาทั่วไป: 30 หน่วยกิต — ประกอบด้วย กลุ่มวิชาพื้นฐาน 6, กลุ่มวิชาด้านภาษาและการสื่อสาร 9, กลุ่มวิชาตามเกณฑ์ของคณะ 9, กลุ่มวิชาเลือกหมวดวิชาการศึกษาทั่วไป 6"
SPECIFIC_NOTE = "หมวดวิชาเฉพาะ: 93 หน่วยกิต — ประกอบด้วย กลุ่มวิชาแกน 12, กลุ่มวิชาเฉพาะด้าน 57, กลุ่มวิชาบังคับเฉพาะสาขา 15, กลุ่มวิชาเลือกทางเทคโนโลยีสารสนเทศ 9, กลุ่มวิชาการศึกษาทางเลือก 6 (หมายเหตุ: กลุ่มวิชาการศึกษาทางเลือก 6 ไม่นับรวมใน 93)"


def credit(tmp_path, *texts):
    return run_js(tmp_path, f"process.stdout.write(JSON.stringify({json.dumps(list(texts), ensure_ascii=False)}.map(m.parseCreditLine)));")


def test_credit_structure_line_is_split_into_total_and_groups(tmp_path):
    (entry,) = credit(tmp_path, GE)
    assert entry["title"] == "หมวดวิชาศึกษาทั่วไป" and entry["credits"] == 30
    assert [(p["name"], p["credits"]) for p in entry["parts"]] == [
        ("กลุ่มวิชาพื้นฐาน", 6), ("กลุ่มวิชาด้านภาษาและการสื่อสาร", 9), ("กลุ่มวิชาตามเกณฑ์ของคณะ", 9),
        ("กลุ่มวิชาเลือกหมวดวิชาการศึกษาทั่วไป", 6)]
    assert entry["note"] is None


def test_credit_structure_note_in_parentheses_is_kept_apart(tmp_path):
    specific, elective, bare = credit(
        tmp_path, SPECIFIC_NOTE, "กลุ่มวิชาเลือก: 6 หน่วยกิต (อยู่ในกลุ่มวิชาการศึกษาทางเลือก)", "หมวดวิชาศึกษาทั่วไป: 24 หน่วยกิต")
    assert specific["credits"] == 93 and len(specific["parts"]) == 5
    assert specific["note"] == "หมายเหตุ: กลุ่มวิชาการศึกษาทางเลือก 6 ไม่นับรวมใน 93"
    assert elective["title"] == "กลุ่มวิชาเลือก" and elective["credits"] == 6 and elective["parts"] == []
    assert elective["note"] == "อยู่ในกลุ่มวิชาการศึกษาทางเลือก"
    assert bare["credits"] == 24 and bare["parts"] == [] and bare["note"] is None


@pytest.mark.parametrize("text", [
    "ปี 2 เทอม 1: 06026206 การวิเคราะห์ / DATA — 3 (2-2-5) หน่วยกิต", "หน่วยกิตรวมตลอดหลักสูตร 132 หน่วยกิต",
    "ปี 3 เรียนรวม 36 หน่วยกิต", "ไม่มีข้อมูลโครงสร้างหน่วยกิตตามหมวดของหลักสูตรนี้ในระบบ (อ่านจากเล่มได้ไม่น่าเชื่อถือ)",
    "หมวด: 30 หน่วยกิต — ประกอบด้วย กลุ่มหนึ่ง กลุ่มสอง", "", "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"])
def test_lines_that_are_not_credit_structure_stay_plain(tmp_path, text):
    assert credit(tmp_path, text) == [None]


def test_consecutive_credit_paragraphs_become_one_credits_block(tmp_path):
    out = run_js(tmp_path, f'''
      const p = {json.dumps([SPECIFIC_NOTE, "กลุ่มวิชาเลือก: 6 หน่วยกิต (อยู่ในกลุ่มวิชาการศึกษาทางเลือก)", "ข้อความอื่น"], ensure_ascii=False)}.map(text => ({{type: "paragraph", text}}));
      const blocks = m.groupCreditBlocks(p);
      process.stdout.write(JSON.stringify(blocks.map(b => b.type + ":" + (b.entries ? b.entries.length : 1))));
    ''')
    assert out == ["credits:2", "paragraph:1"]


# ---------- course overview card (answer_type "course_overview") ----------

ROW = {"code": "06066300", "name_th": "แนวคิดระบบฐานข้อมูล", "name_en": "DATABASE SYSTEM CONCEPTS", "credits": 3,
       "lecture_h": 2, "lab_h": 2, "self_h": 5, "source": "plan", "terms": [[2, 1]], "prerequisite_status": "none",
       "prerequisites": [], "unlocks": [{"code": "06026212", "name_th": "การสร้างคลังข้อมูล"}]}


def test_overview_row_is_mapped_to_the_course_line_and_the_facts(tmp_path):
    out = run_js(tmp_path, f"process.stdout.write(JSON.stringify(m.overviewParts({json.dumps(ROW, ensure_ascii=False)})));")
    assert out["entry"]["code"] == "06066300" and out["entry"]["name"] == "แนวคิดระบบฐานข้อมูล"
    assert out["entry"]["nameEn"] == "DATABASE SYSTEM CONCEPTS" and out["entry"]["credits"] == "3" and out["entry"]["hours"] == ["2", "2", "5"]
    assert out["terms"] == [{"year": 2, "semester": 1}] and out["status"] == "none" and out["source"] == "plan"
    assert out["prerequisites"] == [] and out["unlocks"] == [{"code": "06026212", "name": "การสร้างคลังข้อมูล"}]


def test_overview_row_outside_the_plan_has_no_hours_or_terms(tmp_path):
    row = {"code": "06026216", "name_th": "ปัญญาประดิษฐ์", "name_en": "ARTIFICIAL INTELLIGENCE", "credits": 3, "lecture_h": None,
           "lab_h": None, "self_h": None, "source": "elective", "terms": [], "prerequisite_status": "not_in_plan",
           "prerequisites": [], "unlocks": []}
    out = run_js(tmp_path, f"process.stdout.write(JSON.stringify([m.overviewParts({json.dumps(row, ensure_ascii=False)}), m.overviewParts(null), m.overviewParts({{}})]));")
    assert out[0]["entry"]["hours"] is None and out[0]["terms"] == [] and out[0]["source"] == "elective"
    assert out[1] is None and out[2] is None                      # no row, or a row without a code: nothing to draw


def test_page_draws_the_overview_card_and_chips_ask_for_that_course():
    js = APP_JS.read_text(encoding="utf-8")
    assert 'data.answer_type === "course_overview"' in js and "buildOverviewCard" in js
    assert '"วิชา " + code' in js                                  # a chip asks for that course next


# ---------- comparing two courses: two overview cards side by side ----------

ROW2 = {**ROW, "code": "06026212", "name_th": "การสร้างคลังข้อมูล", "name_en": "DATA WAREHOUSING", "terms": [[3, 1]],
        "prerequisite_status": "found", "prerequisites": [{"code": "06066300", "name_th": "แนวคิดระบบฐานข้อมูล"}], "unlocks": []}


def compare_rows(tmp_path, data):
    return run_js(tmp_path, f"process.stdout.write(JSON.stringify(m.compareRows({json.dumps(data, ensure_ascii=False)})));")


def test_two_course_rows_for_a_compare_question_are_drawn_side_by_side(tmp_path):
    rows = compare_rows(tmp_path, {"question": "เปรียบเทียบ 06066300 กับ 06026212", "answer_type": "database", "rows": [ROW, ROW2]})
    assert [r["code"] for r in rows] == ["06066300", "06026212"]
    assert compare_rows(tmp_path, {"question": "compare 06066300 and 06026212", "rows": [ROW, ROW2]}) is not None


def test_other_answers_are_not_turned_into_a_comparison(tmp_path):
    assert compare_rows(tmp_path, {"question": "วิชาไหนไม่มีวิชาต่อ", "rows": [ROW, ROW2]}) is None          # not a compare question
    assert compare_rows(tmp_path, {"question": "เปรียบเทียบ 06066300 กับ 06026212", "rows": [ROW]}) is None   # not two courses
    assert compare_rows(tmp_path, {"question": "เปรียบเทียบ A กับ B", "rows": [ROW, {"credits": 3}]}) is None  # a row without a code
    assert compare_rows(tmp_path, {"question": "เปรียบเทียบ A กับ B", "rows": []}) is None


def test_page_and_style_have_the_compare_layout():
    js = APP_JS.read_text(encoding="utf-8")
    css = (APP_JS.parent / "style.css").read_text(encoding="utf-8")
    assert "compareRows(data)" in js and "overview-compare" in js
    assert ".overview-compare" in css and "grid-template-columns" in css.split(".overview-compare", 1)[1].split("}", 1)[0]
    # the two cards share the answer column, so the course line is stacked there (a 3-column line squeezed the name to one letter per row)
    assert ".overview-compare .course-line" in css and ".overview-compare .course-meta" in css
