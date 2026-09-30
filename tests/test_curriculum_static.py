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
        assert body.count(f'class="state-{state}"') == 1, (panel_id, state)


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
