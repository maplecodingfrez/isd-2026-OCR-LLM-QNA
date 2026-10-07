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


@pytest.mark.parametrize("text", ["06026200 (แคลคูลัส 1)", "ไม่พบข้อมูลนี้ในเล่มหลักสูตร", "", "18 ครั้ง", "06016403 ชื่อ — 3 หน่วยกิตเกิน"])
def test_lines_that_are_not_course_lines_fall_back_to_plain_text(tmp_path, text):
    assert parse(tmp_path, text) == [None]


def test_consecutive_course_paragraphs_become_one_block_and_others_stay(tmp_path):
    out = run_js(tmp_path, f'''
      const paragraphs = {json.dumps([COURSE, LAST, SLOT, "ข้อความอื่น"], ensure_ascii=False)}.map(text => ({{type: "paragraph", text}}));
      const blocks = m.groupCourseBlocks(paragraphs.concat([{{type: "list", items: ["x"]}}]));
      process.stdout.write(JSON.stringify(blocks.map(b => b.type + ":" + (b.entries ? b.entries.length : 1))));
    ''')
    assert out == ["courses:3", "paragraph:1", "list:1"]
