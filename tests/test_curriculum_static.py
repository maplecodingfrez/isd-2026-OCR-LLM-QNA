"""Lab 11 — ไฟล์ static ของ curriculum_app: เสิร์ฟได้จริง และตรงกติกาจากสไลด์ L11 (p.8, 13-15, 25)."""

import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from lab10_fastapi.curriculum_app import main

STATIC = Path(main.STATIC_DIR)


def read(name):
    return (STATIC / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


def test_page_and_assets_are_served_with_usable_content_types(client):
    page = client.get("/")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    css = client.get("/static/style.css")
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
    js = client.get("/static/app.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]   # กัน .js ถูกส่งเป็น text/plain บน Windows


# ---------- index.html ----------

def test_html_is_structure_only():
    html = read("index.html")
    assert "<style" not in html.lower()
    assert not re.search(r"\sstyle\s*=", html, re.I)                # ไม่มี inline style
    assert not re.search(r"<script(?![^>]*\bsrc=)", html, re.I)      # ไม่มี script ฝัง
    assert not re.search(r"\son[a-z]+\s*=", html, re.I)              # ไม่มี onclick= ฯลฯ
    assert '<link rel="stylesheet" href="/static/style.css">' in html
    assert '<script src="/static/app.js" defer></script>' in html
    assert 'type="module"' not in html


@pytest.mark.parametrize("panel_id", ["ask-panel", "prereq-panel"])
def test_each_panel_starts_idle_and_has_the_four_state_blocks(panel_id):
    html = read("index.html")
    opening = re.search(rf'<section[^>]*id="{panel_id}"[^>]*>', html)
    assert opening and 'data-state="idle"' in opening.group(0)
    body = html[opening.end():html.index("</section>", opening.end())]
    for state in ("idle", "loading", "success", "error"):
        expected = 0 if panel_id == "ask-panel" and state == "idle" else 1
        assert body.count(f'class="state-{state}"') == expected, (panel_id, state)
    if panel_id == "ask-panel":
        assert '<div class="question-examples">' in body


# ---------- style.css ----------

@pytest.mark.parametrize("state", ["idle", "loading", "success", "error"])
def test_css_shows_the_matching_state_block(state):
    assert f'[data-state="{state}"] > .state-{state}' in read("style.css")


def test_css_quality_floor_and_no_external_resources():
    css = read("style.css")
    assert "prefers-reduced-motion" in css
    assert "max-width: 768px" in css
    assert ":focus-visible" in css
    assert "min-height: 44px" in css
    assert "box-shadow" not in css and "@import" not in css and "http" not in css


def test_css_font_files_exist():
    urls = re.findall(r'url\("(/static/fonts/[^"]+)"\)', read("style.css"))
    assert urls
    for url in urls:
        assert (STATIC / url.removeprefix("/static/")).is_file(), url


# ---------- app.js ----------

@pytest.mark.parametrize("pattern", [
    r"innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\(",
    r"Bearer", r"api[_-]?key", r"\bsk-[a-z0-9]", r"https?://",
])
def test_js_avoids_banned_patterns(pattern):
    assert not re.search(pattern, read("app.js"), re.I), pattern


def test_js_is_one_iife_with_no_top_level_declarations_and_checks_res_ok():
    js = read("app.js")
    assert re.search(r"^\(function \(\) \{$", js, re.M) and js.rstrip().endswith("})();")
    assert '"use strict"' in js
    assert not re.search(r"^(var|let|const|function|class)\s", js, re.M)   # ไม่มี global
    assert "res.ok" in js
    assert "res.json(" not in js                                            # อ่านเป็น text แล้ว parse เอง


def test_every_id_the_script_reads_exists_in_the_html():
    """เรียก $("x") ด้วย id ที่ไม่มีใน HTML = null แล้วสคริปต์ตายตอนโหลด (ทุกอย่างค้าง Idle)"""
    js, html = read("app.js"), read("index.html")
    used = set(re.findall(r'\$\("([A-Za-z0-9_-]+)"\)', js))
    defined = set(re.findall(r'\bid="([A-Za-z0-9_-]+)"', html))
    assert used, "ไม่พบการอ่าน id ใน app.js (ยังไม่ได้ต่อ DOM?)"
    assert used <= defined, sorted(used - defined)
    for prefix in ("ask", "prereq"):                      # id ที่ประกอบแบบไดนามิกใน showError()
        for part in ("title", "action", "detail", "more"):
            assert f"{prefix}-error-{part}" in defined, f"{prefix}-error-{part}"


def test_script_wires_the_controls_and_never_writes_style_directly():
    js = read("app.js")
    for hook in ("ask-form", "prereq-form", "copy-button", "ask-retry", "prereq-retry"):
        assert f'$("{hook}")' in js, hook
    assert ".style." not in js and "style.cssText" not in js       # JS คุมสถานะ ไม่คุมสี (สไลด์ p.14)
    assert "dataset.state" in js


# ---------- ผลตรวจ impeccable (Task 8) ----------

def test_css_has_no_thick_side_border_accent():
    """ขอบซ้าย/ขวาหนาเกิน 1px บนกล่อง error = ลายเซ็นของ UI ที่เจนมา (detector: side-tab)"""
    assert not re.search(r"border-(left|right)\s*:\s*([2-9]|\d{2,})px", read("style.css"))


def test_css_keeps_long_text_inside_the_layout():
    assert "overflow-wrap: anywhere" in read("style.css")
    assert ".visually-hidden" in read("style.css")


def test_html_has_one_persistent_live_region_and_no_hidden_aria_live():
    html = read("index.html")
    assert re.search(r'<p id="live-status" class="visually-hidden" role="status"[^>]*></p>', html)
    assert 'aria-live="polite"' not in html          # live region ต้องอยู่ถาวร ไม่ใช่ในบล็อกที่ display:none


def test_html_does_not_hardcode_a_course_code_from_one_program():
    assert 'placeholder="เช่น 06016407"' not in read("index.html")


def test_script_announces_states_and_focuses_the_invalid_field():
    js = read("app.js")
    assert '$("live-status")' in js
    assert '$("question").focus()' in js and '$("course-code").focus()' in js


# ---------- ผลรีวิวทั้ง branch (Important) ----------

def test_course_code_input_has_no_maxlength_that_would_truncate_a_padded_paste():
    tag = re.search(r'<input[^>]*id="course-code"[^>]*>', read("index.html")).group(0)
    assert "maxlength" not in tag          # วาง " 06016407" แล้วเบราว์เซอร์ตัดเหลือ 8 ตัวก่อน trim() จะทำงาน


def test_timeout_is_not_claimed_to_equal_a_backend_setting():
    readme = (STATIC.parents[1] / "README.md").read_text(encoding="utf-8")
    assert "CURRICULUM_REQUEST_TIMEOUT" not in read("app.js")
    assert "= `CURRICULUM_REQUEST_TIMEOUT`" not in readme
    assert "Ollama ล่มตอนสร้าง SQL" in readme        # แถว 422 ที่ backend ส่งจริงเมื่อ Ollama ไม่ทำงาน


# ---------- Minor ข้อ 3 และ 4 จากรีวิว ----------

def test_copy_result_is_announced_to_screen_readers():
    """spec 3: ป้ายปุ่มเปลี่ยนอย่างเดียวโปรแกรมอ่านหน้าจอไม่ประกาศ -> เขียนลง live region ถาวรด้วย"""
    js = read("app.js")
    assert re.search(r'\$\("live-status"\)\.textContent\s*=\s*"คัดลอกผลแล้ว"', js)
    assert re.search(r'\$\("live-status"\)\.textContent\s*=\s*"คัดลอกอัตโนมัติไม่ได้', js)


def test_empty_result_shows_the_rephrase_hint_from_spec():
    """spec 3.5 'Success ว่าง': ไม่พบข้อมูลนี้ในเล่มหลักสูตร + ลองระบุปีหรือเทอมให้ชัดขึ้น"""
    html, js = read("index.html"), read("app.js")
    assert re.search(r'<p id="answer-hint"[^>]*\bhidden\b[^>]*>ลองระบุปีหรือเทอมให้ชัดขึ้น</p>', html)
    assert '$("answer-hint").hidden = !isEmptyResult(data)' in js


# ---------- Minor ที่เหลือจากรีวิว (ข้อ 1, 2, 3, 5, 7, 9) ----------

def test_state_blocks_do_not_double_announce_next_to_the_live_region():
    html = read("index.html")
    assert 'role="alert"' not in html
    assert len(re.findall(r'role="status"', html)) == 1          # เหลือ live region ถาวรตัวเดียว


def test_local_validation_errors_hide_server_details_and_retry():
    js = read("app.js")
    assert "opts.local" in js
    assert '$(prefix + "-retry").hidden = local' in js
    assert '$(prefix + "-error-more").hidden = local || !detail' in js
    assert js.count("{ local: true }") == 3                      # ถาม ตรวจวิชา และผลกระทบการถอน


def test_focus_returns_to_the_submit_button_after_loading():
    assert "submit.focus()" in read("app.js")


def test_renderers_guard_missing_fields():
    js = read("app.js")
    assert '(data.code || "")' in js
    assert "program.label || program.id" in js
    assert "course.code || \"\"" in js


def test_readme_notes_that_backend_accepts_unicode_digits():
    readme = (STATIC.parents[1] / "README.md").read_text(encoding="utf-8")
    assert "isdigit" in readme


# ---------- ให้เลือกหลักสูตรเองตั้งแต่ต้น: ไม่มีคำว่า "หลักสูตรเริ่มต้น" ในหน้าเว็บ ----------

def test_page_never_shows_a_server_default_program_wording():
    js = read("app.js")
    assert "หลักสูตรเริ่มต้น" not in js
    assert "เริ่มต้นของเซิร์ฟเวอร์" not in js


def test_program_select_starts_on_a_named_program_not_a_default_option():
    js = read("app.js")
    assert 'var INITIAL_PROGRAM = "dsba_coop";' in js
    assert "select.value = " in js             # เลือกค่าเริ่มต้นเป็นหลักสูตรจริง ไม่ใช่ตัวเลือกพิเศษ


def test_readme_prereq_404_title_matches_the_new_wording():
    readme = (STATIC.parents[1] / "README.md").read_text(encoding="utf-8")
    assert "ไม่พบรายวิชารหัสนี้ในหลักสูตรเริ่มต้น" not in readme
    assert "ไม่พบรายวิชารหัสนี้ในหลักสูตรที่ค้น" in readme


# ---------- แผงตรวจวิชาตามหลักสูตรที่เลือก ----------

def test_prereq_panel_and_course_list_follow_the_selected_program():
    js = read("app.js")
    assert 'withProgram("/api/courses/" + encodeURIComponent(check.value) + "/prerequisites", program)' in js
    assert 'withProgram("/api/courses?limit=100", $("program").value)' in js
    assert '$("program").addEventListener("change"' in js
    assert "loadProgramNote" not in js                      # ไม่ต้องถามหลักสูตรเริ่มต้นของเซิร์ฟเวอร์อีกแล้ว
    assert "ไม่ตามตัวเลือกด้านบน" not in js


def test_readme_documents_the_program_param_on_prerequisites_and_courses():
    readme = (STATIC.parents[1] / "README.md").read_text(encoding="utf-8")
    assert "ไม่รับ `program`" not in readme
    assert "/prerequisites?program=" in readme and "/api/courses?limit=100&program=" in readme
