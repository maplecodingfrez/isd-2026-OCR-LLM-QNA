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
    # regression: the label function existed but fillCourseList never called it, so OR groups read as AND
    assert re.search(r'fillCourseList\(\$\("prereq-required"\),[^;]*prerequisiteDisplay\)', js)
    assert "format(course)" in js


def test_i18n_has_both_languages_for_prerequisite_labels(tmp_path):
    strings = run_js(tmp_path, 'process.stdout.write(JSON.stringify(i18n.strings));')
    for key in ("prereq.co", "prereq.alt"):
        th, en = strings[key]
        assert th.strip() and en.strip()
    assert "{n}" in strings["prereq.alt"][0] and "{n}" in strings["prereq.alt"][1]


def test_no_challenge_bonus_text_in_the_frontend():
    for path in (STATIC / "app.js", STATIC / "i18n.js", STATIC / "index.html", STATIC / "style.css"):
        assert "Bonus" not in path.read_text(encoding="utf-8"), path.name
