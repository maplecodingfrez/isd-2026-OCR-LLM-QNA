"""Lab 11 — Catoz frontend: OR-group prerequisite labels (Thai/English) and no Challenge-bonus text.

ทดสอบกับ frontend ที่มี i18n.js (Catoz); ถ้า static/ ยังเป็น UI เก่าที่ไม่มี i18n.js จะข้าม
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "lab10_fastapi" / "curriculum_app" / "static"
APP_JS = STATIC / "app.js"
I18N_JS = STATIC / "i18n.js"
NODE = shutil.which("node")

pytestmark = [
    pytest.mark.skipif(NODE is None, reason="ต้องมี node เพื่อรันตรรกะ JS"),
    pytest.mark.skipif(not I18N_JS.exists(), reason="static/ ไม่ใช่ frontend แบบมี i18n.js"),
]


def run_js(tmp_path, body):
    script = tmp_path / "case.js"
    script.write_text(
        f"const m = require({json.dumps(APP_JS.as_posix())});\n"
        f"const i18n = require({json.dumps(I18N_JS.as_posix())});\n"
        f"{body}\n",
        encoding="utf-8",
    )
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_or_group_prerequisite_is_labelled_in_thai_and_english(tmp_path):
    out = run_js(tmp_path, '''
      const c = {code: "06036119", name_th: "ก", name_en: "A", credits_display: "3 (2-2-5)"};
      const show = lang => { i18n.setLang(lang); return [
        m.prerequisiteDisplay(c), m.prerequisiteDisplay({...c, alternative_group: 1}),
        m.prerequisiteDisplay({...c, kind: "co", alternative_group: 1})]; };
      process.stdout.write(JSON.stringify({th: show("th"), en: show("en")}));
    ''')
    th, en = out["th"], out["en"]
    assert "ทางเลือกกลุ่ม" not in th[0] and "option group" not in en[0]      # AND prerequisite: no label
    assert "(ทางเลือกกลุ่ม 1: ผ่านอย่างใดอย่างหนึ่ง)" in th[1]
    assert "(option group 1: pass any one)" in en[1]
    assert "(เรียนร่วมกัน)" in th[2] and "(co-requisite)" in en[2]            # co-requisite wins over the group label
    assert "ผ่านอย่างใดอย่างหนึ่ง" not in th[2] and "pass any one" not in en[2]


def test_prerequisite_list_renders_through_prerequisite_display():
    js = APP_JS.read_text(encoding="utf-8")
    # regression: OR groups read as AND because the label never reached the rendered list; the tag now rides on each course line
    assert re.search(r'fillCourseList\(\$\("prereq-required"\),[^;]*prereqTag\)', js)
    assert "buildCourseLine(entryFromCourse(course, { tag:" in js


def test_i18n_has_both_languages_for_prerequisite_labels(tmp_path):
    strings = run_js(tmp_path, 'process.stdout.write(JSON.stringify(i18n.strings));')
    for key in ("prereq.co", "prereq.alt"):
        th, en = strings[key]
        assert th.strip() and en.strip()
    assert "{n}" in strings["prereq.alt"][0] and "{n}" in strings["prereq.alt"][1]


def test_no_challenge_bonus_text_in_the_frontend():
    for path in (STATIC / "app.js", STATIC / "i18n.js", STATIC / "index.html", STATIC / "style.css"):
        assert "Bonus" not in path.read_text(encoding="utf-8"), path.name


def test_citations_are_not_repeated_and_the_original_answer_lives_in_the_drawer():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    assert "citation-details" not in html and "cite-detail" not in html        # same pages and codes as the citation cards
    assert 'id="original-text"' in html and '$("original-text").textContent' in js
    assert "original-answer" not in js                                          # no per-answer-type "view original" block


def test_empty_answers_drop_the_copy_button_and_the_empty_citation_heading():
    js = APP_JS.read_text(encoding="utf-8")
    i18n = I18N_JS.read_text(encoding="utf-8")
    assert '.querySelector(".citation-box").hidden = !hasCitations' in js
    assert "var noAnswer = noRealAnswer(data)" in js and '.querySelector(".answer-footer").hidden = noAnswer' in js   # not "rows are empty": rule answers have no rows
    assert '"answer.hintGeneric"' in i18n and "answer.hintGeneric" in js        # the year/term hint only for year/term questions


def test_overview_card_does_not_show_the_internal_plan_id_or_the_cryptic_credit_unit():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    assert "dash-program-badge" not in html and "dash-program-badge" not in js    # showed the raw id, for example dsba_coop
    assert '"dash.unit": ["{n} หน่วยกิต"' in I18N_JS.read_text(encoding="utf-8")  # was "{n} น."


def test_search_results_tag_courses_outside_the_plan_and_the_idle_hint_names_acronyms():
    js = APP_JS.read_text(encoding="utf-8")
    i18n = I18N_JS.read_text(encoding="utf-8")
    assert 'course.source === "elective" || course.source === "catalog"' in js and '"search.tagElective"' in i18n
    assert 'data.prerequisite_status === "not_in_plan"' in js and '"prereq.notInPlan"' in i18n
    idle = next(line for line in i18n.splitlines() if line.strip().startswith('"search.idle"'))
    assert "DB" in idle and "ML" in idle                                         # the hint tells people acronyms work


def test_a_rule_answer_without_rows_is_a_real_answer_but_not_found_and_blank_are_not(tmp_path):
    out = run_js(tmp_path, '''
      const cases = [
        {answer: "ไม่พบข้อมูลนี้ในเล่มหลักสูตร", rows: []},                                   // not found
        {answer: "", rows: []},                                                            // nothing to show
        {answer: "หลักสูตรนี้มีแผนการเรียนแผนเดียว ไม่แยกแผนสหกิจ/ไม่สหกิจ", rows: []},      // a rule answer: real, no rows
        {answer: "ปี 1 เทอม 1 รวม 18 หน่วยกิต", rows: [{credits: 18}]},
        null,
      ];
      process.stdout.write(JSON.stringify(cases.map(c => m.noRealAnswer(c))));
    ''')
    assert out == [True, True, False, False, True]
