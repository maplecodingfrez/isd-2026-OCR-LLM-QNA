"""Lab 12 — ทดสอบตรรกะล้วนของ static/app.js ด้วย Node (ไม่ต้องมีเบราว์เซอร์).

app.js เป็น IIFE; เมื่อไม่มี `document` (Node) มันจะ export ฟังก์ชันล้วนผ่าน module.exports
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "lab10_fastapi" / "curriculum_app" / "static"
APP_JS = STATIC / "app.js"
README = REPO / "lab10_fastapi" / "README.md"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="ต้องมี node เพื่อรันตรรกะ JS")


def run_js(tmp_path, body):
    """รันโค้ด JS (มีตัวแปร m = exports ของ app.js) แล้วคืนค่าที่ return เป็น Python object"""
    script = tmp_path / "case.js"
    script.write_text(
        f"const m = require({json.dumps(APP_JS.as_posix())});\n"
        "(async () => {\n"
        f"{body}\n"
        "})().then(v => process.stdout.write(JSON.stringify(v)),"
        " e => { console.error(e); process.exit(1); });\n",
        encoding="utf-8",
    )
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True,
                          encoding="utf-8", timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


# ---------- formatDetail ----------

def test_format_detail_shapes(tmp_path):
    out = run_js(tmp_path, """
      return [
        m.formatDetail("ไม่พบฐานข้อมูล"),
        m.formatDetail([{msg: "ข้อ 1"}, {msg: "ข้อ 2"}]),
        m.formatDetail(["ก", {msg: "ข"}, {}, null]),
        m.formatDetail({a: 1}), m.formatDetail(null), m.formatDetail(undefined), m.formatDetail(422),
      ];""")
    assert out == ["ไม่พบฐานข้อมูล", "ข้อ 1; ข้อ 2", "ก; ข", "", "", "", ""]


# ---------- describeError ----------

CASES = """
  const E = m.ApiError;
  return {
    askPydantic: m.describeError(new E("http", 422, "x", [{msg: "x"}]), "ask"),
    askLab8b: m.describeError(new E("http", 422, "sql พัง", "sql พัง"), "ask"),
    askNoProgram: m.describeError(new E("http", 404, "x", "x"), "ask"),
    prereqCode: m.describeError(new E("http", 422, "x", "x"), "prereq"),
    prereqMissing: m.describeError(new E("http", 404, "x", "x"), "prereq"),
    notReady: m.describeError(new E("http", 503, "x", "x"), "ask"),
    json500: m.describeError(new E("http", 500, "boom", "boom"), "ask"),
    server: m.describeError(new E("server", 500, "Internal Server Error", null), "ask"),
    other4xx: m.describeError(new E("http", 409, "x", "x"), "ask"),
    network: m.describeError(new E("network", 0, ""), "ask"),
    timeout: m.describeError(new E("timeout", 0, ""), "ask"),
    askOllamaDown: m.describeError(new E("http", 422, "ConnectionError: Max retries exceeded", "ConnectionError: Max retries exceeded"), "ask"),
    unexpected: m.describeError(new TypeError("x is undefined"), "ask"),
  };
"""


def test_describe_error_table(tmp_path):
    d = run_js(tmp_path, CASES)
    assert "2–500" in d["askPydantic"]["title"]
    assert "แปลงคำถามเป็นคำค้นไม่ได้" in d["askLab8b"]["title"]
    assert d["askNoProgram"]["title"] == "ไม่พบหลักสูตรที่เลือก"
    assert "8 หลัก" in d["prereqCode"]["title"]
    assert "ไม่พบรายวิชารหัสนี้" in d["prereqMissing"]["title"]
    assert "/api/health" in d["notReady"]["action"]
    assert d["json500"]["title"] == d["server"]["title"] == "เซิร์ฟเวอร์ขัดข้อง"
    assert "รหัส 409" in d["other4xx"]["title"]
    assert d["network"]["title"] == "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้"
    assert "180" in d["timeout"]["title"]
    assert d["unexpected"]["title"].startswith("เกิดข้อผิดพลาดที่ไม่คาดคิด")
    # รีวิว Important 1: Ollama ล่มตอนสร้าง SQL มาเป็น 422 string ต้องไม่บอกให้ผู้ใช้ "ถามใหม่"
    assert d["askOllamaDown"] == d["notReady"]
    # รีวิว Important 2: timeout ไม่ใช่ uvicorn ดับ — คำแนะนำต้องต่างจาก network
    assert "uvicorn" not in d["timeout"]["action"] and d["timeout"]["action"] != d["network"]["action"]


def test_is_model_down_only_matches_requests_exception_names(tmp_path):
    out = run_js(tmp_path, """
      const E = m.ApiError, mk = (st, raw) => new E("http", st, String(raw), raw);
      return [
        m.isModelDown(mk(422, "ConnectionError: HTTPConnectionPool(host=localhost)"), "ask"),
        m.isModelDown(mk(422, "ReadTimeout: read timed out"), "ask"),
        m.isModelDown(mk(422, "OperationalError: no such column: x"), "ask"),
        m.isModelDown(mk(422, "SQL ไม่ผ่านการตรวจ"), "ask"),
        m.isModelDown(mk(422, [{msg: "x"}]), "ask"),
        m.isModelDown(mk(503, "ติดต่อ Ollama ไม่ได้"), "ask"),
        m.isModelDown(mk(422, "ConnectionError: x"), "prereq"),
        m.isModelDown(new E("network", 0, ""), "ask"),
      ];""")
    assert out == [True, True, False, False, False, True, False, False]


def test_describe_error_never_leaks_object_or_undefined(tmp_path):
    for value in run_js(tmp_path, CASES).values():
        for text in (value["title"], value["action"]):
            assert text and "[object" not in text and "undefined" not in text


def test_readme_contract_quotes_every_user_facing_message(tmp_path):
    """README §13 ต้องมีข้อความ title/action ที่หน้าเว็บแสดงจริง (กันเอกสารกับโค้ดเพี้ยนกัน)"""
    text = README.read_text(encoding="utf-8")
    assert "API Contract (Lab 12)" in text
    for value in run_js(tmp_path, CASES).values():
        assert value["title"] in text or "รหัส 409" in value["title"], value["title"]
        assert value["action"] in text, value["action"]


# ---------- validateQuestion / validateCode (Review Focus 1, 3) ----------

def test_validate_question_boundaries(tmp_path):
    out = run_js(tmp_path, """
      const r = (s) => { const v = m.validateQuestion(s); return [v.ok, v.value]; };
      return [
        r("   "), r("ก"), r("  ab  "), r("ก".repeat(500)), r("ก".repeat(501)),
        r("😀".repeat(500)), r("😀".repeat(501)), r(null), r(undefined),
      ];""")
    assert out == [[False, ""], [False, "ก"], [True, "ab"], [True, "ก" * 500], [False, "ก" * 501],
                   [True, "😀" * 500], [False, "😀" * 501], [False, ""], [False, ""]]


def test_validate_question_message_reports_length(tmp_path):
    msg = run_js(tmp_path, "return m.validateQuestion('ก').message;")
    assert msg == "ตอนนี้ 1 ตัวอักษร"          # กฎ 2–500 อยู่ใน title ของ describeError แล้ว ไม่พูดซ้ำ


def test_validate_code_message_does_not_hardcode_a_course_code(tmp_path):
    msg = run_js(tmp_path, "return m.validateCode('abc').message;")
    assert "8 หลัก" in msg and "06016407" not in msg


def test_validate_code_keeps_string_and_rejects_bad_formats(tmp_path):
    out = run_js(tmp_path, """
      const r = (s) => { const v = m.validateCode(s); return [v.ok, v.value]; };
      return [
        r("06016407"), r(" 06016407 "), r("0601640"), r("060164070"), r("๐๖๐๑๖๔๐๗"),
        r("6016407a"), r("0601 407"), r(""), r(null),
      ];""")
    assert out[0] == [True, "06016407"]           # เลข 0 นำหน้าต้องอยู่ครบ
    assert out[1] == [True, "06016407"]           # ตัดช่องว่างหน้า/หลัง
    assert all(ok is False for ok, _ in out[2:])


# ---------- citationItems / answerText / isEmptyResult / buildCopyPayload (Review Focus 4) ----------

def test_citation_items_are_defensive(tmp_path):
    out = run_js(tmp_path, """
      return [
        m.citationItems(null), m.citationItems({}), m.citationItems({citations: "x"}),
        m.citationItems({citations: [
          {pdf_page: 38, printed_page: 33}, {pdf_page: 23, printed_page: null},
          {pdf_page: "9"}, null, {printed_page: 4}, "junk",
        ]}),
      ];""")
    assert out[:3] == [[], [], []]
    assert out[3] == [{"printed": 33, "pdf": 38, "courses": [], "names": {}, "namesEn": {}}, {"printed": None, "pdf": 23, "courses": [], "names": {}, "namesEn": {}}]


# Break caught: backend ส่ง printed_page เป็นสตริง ("334") แต่ UI เช็ค Number.isInteger จึงทิ้งเลขหน้าที่พิมพ์ เหลือแค่ "PDF 335"
def test_citation_items_accept_numeric_string_pages_and_course_lists(tmp_path):
    out = run_js(tmp_path, """
      return m.citationItems({citations: [
        {pdf_page: 335, printed_page: "334", courses: ["06026243", "06026244", 7, null]},
        {pdf_page: 21, printed_page: "abc", courses: "x"},
        {pdf_page: 22, printed_page: " 5 "},
      ]});""")
    assert out == [{"printed": 334, "pdf": 335, "courses": ["06026243", "06026244"], "names": {}, "namesEn": {}},
                   {"printed": None, "pdf": 21, "courses": [], "names": {}, "namesEn": {}},
                   {"printed": 5, "pdf": 22, "courses": [], "names": {}, "namesEn": {}}]


def test_answer_text_and_empty_result(tmp_path):
    out = run_js(tmp_path, """
      return [
        m.answerText({answer: " 20 หน่วยกิต "}), m.answerText({answer: ""}), m.answerText({answer: null}),
        m.answerText(null),
        m.isEmptyResult({rows: []}), m.isEmptyResult({rows: null}), m.isEmptyResult({}),
        m.isEmptyResult({rows: [{a: 1}]}),
      ];""")
    assert out[0] == "20 หน่วยกิต"
    assert out[1] == out[2] == out[3] == "(เซิร์ฟเวอร์ไม่ได้ส่งคำตอบกลับมา)"
    assert out[4:] == [True, True, True, False]


def test_build_copy_payload_has_exactly_five_keys(tmp_path):
    out = run_js(tmp_path, """
      const p = m.buildCopyPayload("ถามอะไร", "", {answer: "ตอบ", citation_text: "(อ้างอิง: เล่มหลักสูตร หน้า 33 (PDF 38))",
                                                   sql: "SELECT 1", rows: [{a: 1}]}, 12.3456);
      const q = m.buildCopyPayload("ก่อน", "it_no_coop", {answer: "ตอบ"}, 0.04);
      return [p, q];""")
    p, q = out
    assert list(p) == ["question", "program", "answer", "citation_text", "elapsed_seconds"]
    assert p["program"] is None and p["elapsed_seconds"] == 12.3
    assert q["program"] == "it_no_coop" and q["citation_text"] == "" and q["elapsed_seconds"] == 0


# ---------- apiFetch (Review Focus 2, 5) ----------

FAKE = """
  const respond = (status, body, type) => async () =>
    new Response(body, {status: status, headers: {"Content-Type": type || "application/json"}});
  const outcome = async (fetchImpl, deps) => {
    try {
      const v = await m.apiFetch("/x", {}, Object.assign({fetch: fetchImpl}, deps || {}));
      return {ok: v};
    } catch (e) {
      return {kind: e.kind, status: e.status, detail: e.detail, raw: e.raw};
    }
  };
"""


def test_api_fetch_success_and_json_errors(tmp_path):
    out = run_js(tmp_path, FAKE + """
      return [
        await outcome(respond(200, JSON.stringify({a: 1}))),
        await outcome(respond(422, JSON.stringify({detail: [{msg: "สั้นไป"}, {msg: "อีกข้อ"}]}))),
        await outcome(respond(422, JSON.stringify({detail: "sql พัง"}))),
        await outcome(respond(404, JSON.stringify({detail: "ไม่พบ"}))),
        await outcome(respond(400, JSON.stringify({x: 1}))),
        await outcome(respond(400, JSON.stringify({detail: {a: 1}}))),
        await outcome(respond(400, JSON.stringify([1, 2]))),
      ];""")
    assert out[0] == {"ok": {"a": 1}}
    assert out[1] == {"kind": "http", "status": 422, "detail": "สั้นไป; อีกข้อ",
                      "raw": [{"msg": "สั้นไป"}, {"msg": "อีกข้อ"}]}
    assert out[2] == {"kind": "http", "status": 422, "detail": "sql พัง", "raw": "sql พัง"}
    assert out[3] == {"kind": "http", "status": 404, "detail": "ไม่พบ", "raw": "ไม่พบ"}
    assert out[4] == {"kind": "http", "status": 400, "detail": "", "raw": None}        # ไม่มีคีย์ detail
    assert out[5] == {"kind": "http", "status": 400, "detail": "", "raw": {"a": 1}}    # detail เป็น object
    assert out[6] == {"kind": "http", "status": 400, "detail": "", "raw": None}        # JSON ระดับบนเป็น array


def test_api_fetch_non_json_bodies_become_server_errors(tmp_path):
    out = run_js(tmp_path, FAKE + """
      return [
        await outcome(respond(500, "Internal Server Error", "text/plain")),
        await outcome(respond(502, "<html>Bad Gateway</html>", "text/html")),
        await outcome(respond(500, "", "text/plain")),
        await outcome(respond(200, "not json at all", "text/plain")),
      ];""")
    assert out[0] == {"kind": "server", "status": 500, "detail": "Internal Server Error", "raw": None}
    assert out[1]["kind"] == "server" and out[1]["status"] == 502
    assert out[2] == {"kind": "server", "status": 500, "detail": "", "raw": None}
    assert out[3]["kind"] == "server" and out[3]["status"] == 200


def test_api_fetch_network_failure_and_timeout(tmp_path):
    out = run_js(tmp_path, FAKE + """
      const neverSettles = (url, init) => new Promise((resolve, reject) => {
        init.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });
      return [
        await outcome(async () => { throw new TypeError("Failed to fetch"); }),
        await outcome(neverSettles, {timeoutMs: 30}),
      ];""")
    assert out[0] == {"kind": "network", "status": 0, "detail": "", "raw": None}
    assert out[1] == {"kind": "timeout", "status": 0, "detail": "", "raw": None}


def test_api_fetch_sends_method_headers_body_and_a_signal(tmp_path):
    seen = run_js(tmp_path, """
      let seen = null;
      await m.apiFetch("/api/ask", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"},
        {fetch: async (url, init) => { seen = {url, method: init.method, type: init.headers["Content-Type"],
                                               body: init.body, hasSignal: !!init.signal};
                                       return new Response("{}", {status: 200}); }});
      return seen;""")
    assert seen == {"url": "/api/ask", "method": "POST", "type": "application/json",
                    "body": "{}", "hasSignal": True}


# ---------- withProgram: แผงตรวจวิชาตามหลักสูตรที่เลือก ----------

def test_with_program_appends_the_encoded_program_param(tmp_path):
    out = run_js(tmp_path, """
      return [
        m.withProgram("/api/courses/06016407/prerequisites", "it_no_coop"),
        m.withProgram("/api/courses?limit=100", "ait"),
        m.withProgram("/api/courses?limit=100", ""),
        m.withProgram("/api/courses/06016407/prerequisites", null),
        m.withProgram("/api/courses", "a b&c=d"),
      ];""")
    assert out == [
        "/api/courses/06016407/prerequisites?program=it_no_coop",
        "/api/courses?limit=100&program=ait",
        "/api/courses?limit=100",
        "/api/courses/06016407/prerequisites",
        "/api/courses?program=a%20b%26c%3Dd",
    ]


# Break caught: course_names from the server ignored, or names for codes not on the page leaking in.
def test_citation_items_keep_names_only_for_listed_courses(tmp_path):
    out = run_js(tmp_path, """
      return m.citationItems({citations: [
        {pdf_page: 5, printed_page: "4", courses: ["06026243"], course_names: {"06026243": "สถิติ", "99999999": "x", "06026244": 7}, course_names_en: {"06026243": "STATISTICS", "99999999": "y"}},
      ]});""")
    assert out == [{"printed": 4, "pdf": 5, "courses": ["06026243"], "names": {"06026243": "สถิติ"}, "namesEn": {"06026243": "STATISTICS"}}]
