"""Lab 11 — ตัวควบคุมใหม่ของหน้าเว็บ: ลิ้นชักตัวอย่าง, ปุ่มล้าง, คำถามล่าสุด, แถบเครื่องมือขวา, ลิงก์แชร์, ปุ่ม /, แถวอ้างอิงใต้คำตอบ.

ไม่มี jsdom ในเครื่อง จึงตรวจเป็น "สัญญา" ของไฟล์ static (โครง HTML, กติกา CSS, ข้อความสำคัญใน JS)
บวกการรัน i18n.js จริงด้วย node (ทุกคีย์ใหม่ต้องมีครบสองภาษา)
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "lab10_fastapi" / "curriculum_app" / "static"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(not (STATIC / "i18n.js").exists(), reason="static/ ไม่ใช่ frontend แบบมี i18n.js")

NEW_KEYS = [
    "btn.clear", "examples.summary", "recent.title", "recent.aria", "tools.summary", "ask.help",
    "search.about", "prereq.about", "withdraw.about", "drawer.summary", "drawer.sql", "drawer.rows",
    "hint.toFocus", "link.btn", "link.done", "err.network.dev", "notfound.note",
]


def read(name):
    return (STATIC / name).read_text(encoding="utf-8")


def tag(html, element_id):
    """แท็กเปิดของ element ตาม id"""
    match = re.search(rf"<[a-z0-9]+\b[^>]*\bid=\"{re.escape(element_id)}\"[^>]*>", html)
    assert match, f"ไม่พบ #{element_id}"
    return match.group(0)


# ---------- HTML ----------

def test_clear_button_starts_hidden_and_is_translated():
    html = read("index.html")
    button = tag(html, "clear-button")
    assert 'type="button"' in button and re.search(r"\bhidden\b", button) and 'data-i18n="btn.clear"' in button


def test_examples_drawer_is_open_by_default_and_keeps_the_question_examples_block():
    html = read("index.html")
    drawer = tag(html, "examples-drawer")
    assert drawer.startswith("<details") and re.search(r"\bopen\b", drawer)
    body = html[html.index(drawer):html.index("</details>", html.index(drawer))]
    assert '<summary data-i18n="examples.summary">' in body
    assert '<div class="question-examples">' in body                # test_curriculum_static ต้องการ wrapper นี้
    for element_id in ("topic-bar", "examples", "recent-wrap", "recent"):
        assert f'id="{element_id}"' in body


def test_recent_questions_block_starts_hidden():
    assert re.search(r"\bhidden\b", tag(read("index.html"), "recent-wrap"))


def test_tools_fold_is_closed_by_default_and_wraps_the_tabs_and_panels():
    html = read("index.html")
    fold = tag(html, "tools-fold")
    assert fold.startswith("<details") and not re.search(r"\bopen\b", fold)
    start = html.index(fold)
    end = html.index("</details>\n    </aside>", start)
    inside = html[start:end]
    for needle in ('id="tool-tabs"', 'id="search-panel"', 'id="prereq-panel"', 'id="withdraw-panel"'):
        assert needle in inside
    assert 'data-i18n="tools.summary"' in inside


def test_every_tool_has_a_one_line_explainer():
    html = read("index.html")
    assert re.findall(r'class="tool-about" data-i18n="(search|prereq|withdraw)\.about"', html) == ["search", "prereq", "withdraw"]


def test_idle_help_line_sits_between_the_form_and_the_examples():
    html = read("index.html")
    assert html.index("</form>") < html.index('class="ask-help"') < html.index('id="examples-drawer"')


def test_citation_block_comes_after_the_answer_and_before_the_copy_buttons():
    html = read("index.html")
    order = [html.index(marker) for marker in ('id="answer-text"', 'class="cite-block"', 'id="cite-tabs"', 'class="citation-box"', 'class="answer-footer"')]
    assert order == sorted(order)


def test_answer_footer_has_copy_result_and_copy_link_buttons():
    html = read("index.html")
    footer = html[html.index('class="answer-footer"'):html.index("</div>", html.index('class="answer-footer"'))]
    assert 'id="copy-button"' in footer and 'id="link-copy-button"' in footer and 'data-i18n="link.btn"' in footer


def test_slash_hint_is_marked_as_keyboard_only():
    html = read("index.html")
    assert 'class="hint-extra"' in html and '<span class="kbd">/</span>' in html


def test_html_has_no_emoji_outside_the_topic_pills():
    emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
    assert not emoji.search(read("index.html")), "อีโมจิอยู่ได้เฉพาะปุ่มหัวข้อ (สร้างใน app.js)"
    strings = read("i18n.js")
    assert not emoji.search(strings), "ข้อความใน i18n.js ต้องไม่มีอีโมจิ"


def test_no_developer_wording_in_the_main_error_text():
    strings = read("i18n.js")
    action = re.search(r'"err\.network\.act":\s*\[(.*?)\]', strings, re.S).group(1)
    assert "uvicorn" not in action
    assert "uvicorn" in re.search(r'"err\.network\.dev":\s*\[(.*?)\]', strings, re.S).group(1)   # คำแนะนำผู้ดูแลอยู่ในรายละเอียด


# ---------- i18n (รัน node จริง) ----------

@pytest.mark.skipif(NODE is None, reason="ต้องมี node")
def test_new_i18n_keys_exist_in_both_languages(tmp_path):
    script = tmp_path / "keys.js"
    script.write_text(
        f"const i = require({json.dumps((STATIC / 'i18n.js').as_posix())});\n"
        f"const keys = {json.dumps(NEW_KEYS)};\n"
        "const out = {};\n"
        "for (const lang of ['th', 'en']) { i.setLang(lang); out[lang] = keys.map(k => i.t(k)); }\n"
        "process.stdout.write(JSON.stringify(out));\n",
        encoding="utf-8",
    )
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    for lang, values in out.items():
        for key, value in zip(NEW_KEYS, values):
            assert value and value != key, (lang, key)
    assert all(th != en for th, en in zip(out["th"], out["en"]) if th not in ("ล้าง",)), "แต่ละคีย์ต้องมีสองภาษาที่ต่างกัน"


@pytest.mark.skipif(NODE is None, reason="ต้องมี node")
def test_english_tools_label_is_short_and_thai_names_the_tools(tmp_path):
    script = tmp_path / "label.js"
    script.write_text(
        f"const i = require({json.dumps((STATIC / 'i18n.js').as_posix())});\n"
        "i.setLang('th'); const th = i.t('tools.summary'); i.setLang('en'); const en = i.t('tools.summary');\n"
        "process.stdout.write(JSON.stringify({th, en}));\n",
        encoding="utf-8",
    )
    out = json.loads(subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=30).stdout)
    assert all(name in out["th"] for name in ("ค้นวิชา", "บังคับก่อน", "ถอนวิชา"))
    assert len(out["en"]) <= 12                                      # แถบด้านขวากว้างแค่ 13rem: ป้ายอังกฤษต้องสั้น


# ---------- app.js ----------

def test_recent_questions_keep_five_and_survive_broken_storage():
    js = read("app.js")
    assert 'var RECENT_KEY = "recent-questions";' in js and "var RECENT_MAX = 5;" in js
    assert "loadRecent().filter(function (q) { return q !== question; })" in js   # ไม่ซ้ำ
    assert "list.unshift(question)" in js and "list.slice(0, RECENT_MAX)" in js
    assert re.search(r"function loadRecent\(\) \{\s*try \{.*?\} catch \(e\) \{ return \[\]; \}", js, re.S)   # JSON เสีย/โหมดส่วนตัว = ไม่มีรายการ
    assert "rememberQuestion(check.value);" in js and js.index("setState(askPanel, \"success\", askControls);") < js.index("rememberQuestion(check.value);")


def test_clear_resets_state_and_the_share_url_and_is_ignored_while_loading():
    js = read("app.js")
    body = js[js.index("function clearAsk()"):js.index("function clearAsk()") + 700]
    assert 'if (askPanel.dataset.state === "loading") return;' in body
    for needle in ('$("question").value = "";', 'syncShareUrl("", null);', 'setState(askPanel, "idle", askControls);', '$("question").focus();'):
        assert needle in body, needle
    assert '$("clear-button").hidden = !$("question").value && askPanel.dataset.state === "idle";' in js


def test_examples_drawer_follows_the_ask_state():
    js = read("app.js")
    assert '$("examples-drawer").open = state !== "success";' in js and "if (state !== \"loading\")" in js


def test_slash_shortcut_does_not_steal_keys_from_fields_or_shortcuts():
    js = read("app.js")
    block = js[js.index('document.addEventListener("keydown"'):js.index('document.addEventListener("keydown"') + 600]
    assert 'event.key !== "/"' in block
    for guard in ("event.ctrlKey", "event.metaKey", "event.altKey", "event.isComposing"):
        assert guard in block
    for tag_name in ('"INPUT"', '"TEXTAREA"', '"SELECT"', "isContentEditable"):
        assert tag_name in block
    assert '$("question").focus();' in block


def test_share_link_reads_plan_and_question_and_writes_them_after_a_good_answer():
    js = read("app.js")
    assert 'new URLSearchParams(location.search)' in js and 'urlParams.get("plan")' in js and 'urlParams.get("q")' in js
    assert "sharedQuestion.slice(0, 500)" in js                       # ตรงกับขีดจำกัด 500 ตัวอักษรของคำถาม
    assert "window.history.replaceState" in js and "syncShareUrl(check.value, program);" in js
    assert "new URLSearchParams({ plan: program || \"\", q: question })" in js


def test_copy_link_falls_back_to_the_selected_text_box():
    js = read("app.js")
    body = js[js.index("async function copyLink()"):js.index("async function copyLink()") + 1300]
    assert "window.location.href" in body and "navigator.clipboard.writeText" in body and "legacyCopy(text)" in body
    assert '$("copy-fallback")' in body and 'link.done' in body


def test_opening_a_search_result_opens_the_folded_tools():
    js = read("app.js")
    handler = js[js.index('$("search-results").addEventListener("click"'):][:600]
    assert '$("tools-fold").open = true;' in handler and "selectTab(1, false)" in handler


def test_sample_questions_start_with_no_topic_selected_and_toggle_off():
    js = read("app.js")
    assert "var currentTopic = -1;" in js
    assert "currentTopic = currentTopic === i ? -1 : i;" in js
    assert "if (!topic) { list.className = \"examples\"; return; }" in js


def test_network_error_detail_carries_the_operator_hint_not_the_main_message():
    js = read("app.js")
    assert 'err.kind === "network"' in js and 't("err.network.dev")' in js


def test_each_citation_page_is_one_row_with_its_course_chips():
    js = read("app.js")
    assert 'className: "cite-row"' in js and 'className: "cite-tab"' in js
    assert 'var hasCitations = items.length === 0 && typeof data.citation_text === "string" && data.citation_text !== "";' in js


# ---------- style.css ----------

def test_tools_are_a_slim_rail_that_widens_when_opened_on_desktop_only():
    css = read("style.css")
    media = css[css.index("@media (min-width: 900px)"):][:900]
    assert re.search(r"\.layout \{ grid-template-columns: minmax\(0, 1fr\) 13rem; \}", media)
    assert re.search(r"\.layout:has\(\.tools-fold\[open\]\) \{ grid-template-columns: minmax\(0, 1fr\) 26rem; \}", media)
    assert re.search(r"\.layout \{[^}]*grid-template-columns: 1fr;", css)    # มือถือ: คอลัมน์เดียว


def test_compare_cards_stack_when_the_answer_panel_is_narrow():
    css = read("style.css")
    assert "container-type: inline-size" in css and "container-name: ask" in css
    assert re.search(r"@container ask \(max-width: 560px\) \{\s*\.overview-compare \{ grid-template-columns: minmax\(0, 1fr\); \}", css)


def test_every_summary_gets_a_drawn_chevron_that_turns_when_open():
    css = read("style.css")
    assert "details > summary::before" in css and "clip-path: polygon" in css
    assert "details[open] > summary::before" in css
    assert not re.search(r"summary::before[^}]*border-(left|right)", css)    # กฎเดิม: ห้ามขอบข้างหนา


def test_slash_hint_is_hidden_on_touch_and_small_screens():
    css = read("style.css")
    assert re.search(r"@media \(pointer: coarse\), \(max-width: 580px\) \{ \.hint-extra \{ display: none; \} \}", css)


def test_citation_tag_is_compact_and_the_block_hides_when_empty():
    css = read("style.css")
    assert re.search(r"\.cite-block:has\(#cite-tabs:empty\) \{ display: none; \}", css)
    tag_rule = css[css.index(".cite-tab {", css.index(".cite-block")):][:400]
    assert "font-size: 16px" in tag_rule and "var(--accent)" in tag_rule


def test_small_controls_reach_the_touch_target_size_on_phones():
    css = read("style.css")
    assert re.search(r"\.brand \{[^}]*min-height: 44px", css) and re.search(r"\.seg \{[^}]*min-height: 44px", css, re.S)
    assert re.search(r"@media \(pointer: coarse\), \(max-width: 580px\) \{\s*\.link-button, \.overview-chip \{ min-height: 44px;", css)
    assert re.search(r"#clear-button \{ min-height: 44px;", css)


def test_no_text_role_is_smaller_than_15px_except_keys_and_code_blocks():
    css = read("style.css")
    for match in re.finditer(r"^([^{\n}]+)\{[^}]*?font-size:\s*(\d+(?:\.\d+)?)px", css, re.M):
        selector, size = match.group(1).strip(), float(match.group(2))
        if size < 15:
            assert selector in (".kbd", "pre"), (selector, size)


# ---------- ตอบจากแผนไหน + สถานะ "ไม่พบ" ----------

def test_not_found_note_is_hidden_by_default_and_sits_before_the_hint():
    html = read("index.html")
    note = tag(html, "notfound-note")
    assert re.search(r"\bhidden\b", note) and 'data-i18n="notfound.note"' in note
    assert html.index('id="notfound-note"') < html.index('id="answer-hint"')


def test_not_found_look_follows_no_real_answer_and_is_cleared_for_real_answers():
    js = read("app.js")
    assert '$("answer-box").classList.toggle("is-notfound", noAnswer);' in js
    assert '$("notfound-note").hidden = !noAnswer;' in js
    assert "var noAnswer = noRealAnswer(data);" in js                    # ใช้เงื่อนไขเดียวกับที่ซ่อนปุ่มคัดลอก


def test_not_found_is_calm_not_an_amber_warning():
    css = read("style.css")
    rule = re.search(r"\.answer-card\.is-notfound #answer-hint \{([^}]*)\}", css).group(1)
    assert "warn" not in rule and "var(--surface-2)" in rule and "dashed" in rule
    title = re.search(r"\.answer-card\.is-notfound \.answer-text p \{([^}]*)\}", css).group(1)
    assert "var(--font-head)" in title and "font-size: 18px" in title    # อยู่ใน type ramp
    assert ".notfound-note" in css


def test_answer_source_is_one_clear_plan_badge():
    css = read("style.css")
    assert len(re.findall(r"^#answer-source \{", css, re.M)) == 1          # ไม่ซ้ำสองกฎ
    rule = re.search(r"^#answer-source \{([^}]*)\}", css, re.M).group(1)
    for needle in ("border: 2px solid var(--line)", "border-radius: 999px", "font-weight: 600", "color: var(--text)"):
        assert needle in rule, needle


def test_answer_source_text_names_the_selected_plan():
    js = read("app.js")
    assert 't("answer.source", { name: select.selectedOptions[0].textContent })' in js


# ---------- พิมพ์ / บันทึกเป็น PDF + สคริปต์สาธิต ----------

def print_block():
    css = read("style.css")
    start = css.index("@media print {")
    return css[start:css.index(chr(10) + "}" + chr(10), start)]


def test_print_hides_tools_and_chrome_but_keeps_the_answer_and_its_citation():
    block = print_block()
    for hidden in (".site-header", ".tools", ".omnibox", ".answer-footer", ".examiner-drawer", ".minimal-stats-grid", ".examples-drawer", ".state-error"):
        assert hidden in block.split("{")[1], hidden
    assert "display: none !important" in block
    for kept in (".answer-card", ".answer-text", ".cite-block", ".cite-tab"):
        assert kept not in block.split("display: none !important")[0], kept      # ไม่อยู่ในรายการที่ซ่อน


def test_print_is_black_on_white_whatever_the_theme_and_prints_the_question():
    block = print_block()
    assert "color: #000 !important" in block and "background: #fff !important" in block
    assert "content: attr(data-question)" in block
    js = read("app.js")
    assert '$("answer-box").dataset.question = typeof data.question === "string" ? data.question : "";' in js


def test_demo_script_in_the_readme_lists_six_questions_with_real_page_numbers():
    readme = (STATIC.parent / "README.md").read_text(encoding="utf-8")
    section = readme[readme.index("## สคริปต์สาธิต"):readme.index("## คำถามที่พบบ่อย")]
    rows = [line for line in section.splitlines() if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    assert len(rows) == 6
    for needle in ("ปี 1 เทอม 1 เรียนกี่หน่วยกิต", "06026201 ต้องเรียนอะไรก่อน", "ถ้าถอนวิชา 06026200", "เปรียบเทียบ 06026200 กับ 06026201", "มหาวิทยาลัยตั้งอยู่ที่ไหน", "AIT"):
        assert needle in section, needle
    assert "หน้า 29 / PDF 30" in section and "หน้า 313 / PDF 314" in section and "120" in section


def test_count_up_is_skipped_when_the_tab_is_hidden_or_motion_is_reduced():
    js = read("app.js")
    body = js[js.index("function animateCount(node, target)"):][:600]
    assert "document.hidden" in body and "prefers-reduced-motion: reduce" in body    # ไม่ค้างที่ 0 เมื่อแท็บถูกซ่อน

