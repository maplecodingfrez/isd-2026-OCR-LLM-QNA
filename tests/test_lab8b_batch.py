"""โหมดรันคำถามเป็นชุด (ask-batch), keep_alive และ warm_up ของ Lab 8B — เตรียมวัน Challenge:
อาจารย์ส่งชุดคำถามมา เราต้องส่งคำตอบกลับเป็นไฟล์ ข้อไหนพังต้องไม่ทำให้ทั้งชุดหยุด (error = 0 คะแนน)"""

import json
import threading

import pytest
import requests

import lab8b_curriculum_db as m


# ---------- load_questions ----------

def test_load_questions_txt_skips_blank_lines_and_comments(tmp_path):
    f = tmp_path / "q.txt"
    f.write_text("# ชุดทดสอบ\nหลักสูตรนี้กี่หน่วยกิต\n\n  ปี 1 เรียนอะไรบ้าง  \n", encoding="utf-8")
    qs = m.load_questions(f)
    assert [q["question"] for q in qs] == ["หลักสูตรนี้กี่หน่วยกิต", "ปี 1 เรียนอะไรบ้าง"]
    assert [q["id"] for q in qs] == ["q1", "q2"]


def test_load_questions_json_accepts_strings_objects_and_a_questions_key(tmp_path):
    f = tmp_path / "a.json"
    f.write_text(json.dumps(["ข้อหนึ่ง", {"id": "A7", "question": "ข้อสอง", "level": 3}], ensure_ascii=False), encoding="utf-8")
    qs = m.load_questions(f)
    assert qs[0] == {"question": "ข้อหนึ่ง", "id": "q1"}
    assert qs[1]["id"] == "A7" and qs[1]["level"] == 3

    g = tmp_path / "b.json"
    g.write_text(json.dumps({"questions": [{"question": "ข้อเดียว"}]}, ensure_ascii=False), encoding="utf-8")
    assert [q["question"] for q in m.load_questions(g)] == ["ข้อเดียว"]


def test_load_questions_csv_with_bom_and_mixed_case_header(tmp_path):
    f = tmp_path / "q.csv"
    f.write_text("ID,Question,Level\nC1,วิชาเลือกมีอะไรบ้าง,3\nC2,ปี 2 เทอม 1 กี่วิชา,2\n", encoding="utf-8-sig")
    qs = m.load_questions(f)
    assert [(q["id"], q["question"]) for q in qs] == [("C1", "วิชาเลือกมีอะไรบ้าง"), ("C2", "ปี 2 เทอม 1 กี่วิชา")]


@pytest.mark.parametrize("name,content", [
    ("empty.txt", "\n# แค่คอมเมนต์\n"),
    ("nofield.csv", "id,text\n1,xxx\n"),
    ("blankq.json", json.dumps([{"id": "x", "question": "   "}])),
    ("badtype.json", json.dumps([123])),
])
def test_load_questions_rejects_files_with_no_usable_questions(tmp_path, name, content):
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        m.load_questions(f)


# ---------- ask_batch / summarize_batch ----------

def _fake_ask(conn, question, verbose=False):
    if "พัง" in question:
        raise requests.ConnectionError("Ollama down")
    if "ว่าง" in question:
        return {"answer": "", "sql": "SELECT 1", "rows": [], "error": None, "citations": [], "citation_text": ""}
    if "sqlพลาด" in question:
        return {"answer": "ไม่สามารถตอบคำถามนี้ได้ กรุณาตรวจสอบเอง", "sql": None, "rows": [], "error": "OperationalError: x",
                "citations": [], "citation_text": ""}
    return {"answer": "ตอบ: " + question, "sql": "SELECT 20", "rows": [{"a": 1}, {"a": 2}], "error": None,
            "citations": [{"pdf_page": 38, "printed_page": 33}], "citation_text": "(อ้างอิง: เล่มหลักสูตร หน้า 33 (PDF 38))"}


def _clock():
    ticks = iter(range(0, 1000, 3))     # ทุกคำถามใช้เวลา 3 วินาทีพอดี
    return lambda: next(ticks)


def test_ask_batch_keeps_order_and_fills_every_field():
    qs = [{"id": "A", "question": "ข้อ 1"}, {"id": "B", "question": "ข้อ 2", "level": 4}]
    out = m.ask_batch(None, qs, ask_fn=_fake_ask, clock=_clock())
    assert [r["id"] for r in out] == ["A", "B"]
    first = out[0]
    assert first["answer"] == "ตอบ: ข้อ 1" and first["n_rows"] == 2 and first["seconds"] == 3
    assert first["citation_text"].startswith("(อ้างอิง") and first["error"] is None and first["sql"] == "SELECT 20"
    assert out[1]["level"] == 4 and "rows" not in first


def test_ask_batch_one_crash_does_not_stop_the_rest_and_never_leaves_an_empty_answer():
    qs = [{"id": "1", "question": "ข้อปกติ"}, {"id": "2", "question": "ข้อพัง"}, {"id": "3", "question": "ข้อว่าง"},
          {"id": "4", "question": "ข้อsqlพลาด"}, {"id": "5", "question": "ข้อปกติอีกข้อ"}]
    out = m.ask_batch(None, qs, ask_fn=_fake_ask, clock=_clock())
    assert len(out) == 5
    assert out[1]["error"].startswith("ConnectionError") and out[1]["answer"] == m.FALLBACK_ANSWER
    assert out[2]["answer"] == m.FALLBACK_ANSWER                    # ตอบว่างไม่ได้: คำตอบว่างทำให้ judge ให้ 0
    assert out[3]["error"].startswith("OperationalError") and out[3]["answer"].startswith("ไม่สามารถตอบ")
    assert out[4]["error"] is None and out[4]["answer"].startswith("ตอบ:")


def test_ask_batch_with_rows_includes_the_rows():
    out = m.ask_batch(None, [{"id": "1", "question": "ข้อ"}], ask_fn=_fake_ask, clock=_clock(), with_rows=True)
    assert out[0]["rows"] == [{"a": 1}, {"a": 2}]


def test_ask_batch_calls_on_result_for_progress():
    seen = []
    m.ask_batch(None, [{"id": "1", "question": "ก"}, {"id": "2", "question": "ข"}], ask_fn=_fake_ask,
                clock=_clock(), on_result=lambda i, n, r: seen.append((i, n, r["id"])))
    assert seen == [(1, 2, "1"), (2, 2, "2")]


def test_summarize_batch_counts_failures_and_slow_answers():
    results = [{"error": None, "seconds": 2.0}, {"error": "X", "seconds": 7.5}, {"error": None, "seconds": 5.0},
               {"error": None, "seconds": 5.01}]
    s = m.summarize_batch(results)
    assert s == {"n": 4, "ok": 3, "failed": 1, "over_5s": 2, "avg_seconds": 4.88, "max_seconds": 7.5}
    assert m.summarize_batch([])["n"] == 0


# ---------- keep_alive / warm_up ----------

class _Resp:
    def __init__(self, ok=True, body=None):
        self.ok, self._body = ok, body or {"message": {"content": "{}"}}

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError("bad")

    def json(self):
        return self._body


def test_ollama_generate_asks_ollama_to_keep_the_model_loaded(monkeypatch):
    seen = {}
    monkeypatch.setattr(requests, "post", lambda url, json=None, timeout=None: seen.update(url=url, payload=json) or _Resp())
    m.ollama_generate("สวัสดี")
    assert seen["url"].endswith("/api/chat")
    assert seen["payload"]["keep_alive"] == m.KEEP_ALIVE and m.KEEP_ALIVE


def test_warm_up_loads_the_model_and_never_raises(monkeypatch):
    seen = {}
    monkeypatch.setattr(requests, "post", lambda url, json=None, timeout=None: seen.update(url=url, payload=json) or _Resp())
    assert m.warm_up() is True
    assert seen["url"].endswith("/api/generate")
    assert seen["payload"]["model"] == m.MODEL_TEXT and seen["payload"]["keep_alive"] == m.KEEP_ALIVE

    def boom(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(requests, "post", boom)
    assert m.warm_up() is False                                       # Ollama ยังไม่เปิด: ต้องไม่ทำให้เซิร์ฟเวอร์ล้ม


# ---------- cmd_ask_batch ----------

def test_cmd_ask_batch_writes_answers_json_and_prints_a_summary(tmp_path, monkeypatch, capsys):
    qfile = tmp_path / "challenge.txt"
    qfile.write_text("ข้อปกติ\nข้อพัง\n", encoding="utf-8")
    monkeypatch.setattr(m, "open_db", lambda path, readonly=False: type("C", (), {"close": lambda self: None})())
    monkeypatch.setattr(m, "ask", _fake_ask)
    monkeypatch.setattr(m, "warm_up", lambda timeout=180: True)
    args = type("A", (), dict(database="x.db", questions=str(qfile), output="", program="IT ไม่สหกิจ",
                              with_rows=False, no_warmup=False))()
    m.cmd_ask_batch(args)
    out = tmp_path / "challenge_answers.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["meta"]["n"] == 2 and data["meta"]["failed"] == 1 and data["meta"]["program"] == "IT ไม่สหกิจ"
    assert data["meta"]["warmed_up"] is True and data["meta"]["model"] == m.MODEL_TEXT
    assert [r["question"] for r in data["results"]] == ["ข้อปกติ", "ข้อพัง"]
    assert all(r["answer"] for r in data["results"])
    printed = capsys.readouterr().out
    assert "challenge_answers.json" in printed and "1/2" in printed


def test_cmd_ask_batch_skips_warmup_when_asked(tmp_path, monkeypatch):
    qfile = tmp_path / "q.txt"
    qfile.write_text("ข้อ\n", encoding="utf-8")
    monkeypatch.setattr(m, "open_db", lambda path, readonly=False: type("C", (), {"close": lambda self: None})())
    monkeypatch.setattr(m, "ask", _fake_ask)
    called = []
    monkeypatch.setattr(m, "warm_up", lambda timeout=180: called.append(1) or True)
    args = type("A", (), dict(database="x.db", questions=str(qfile), output=str(tmp_path / "o.json"), program="",
                              with_rows=False, no_warmup=True))()
    m.cmd_ask_batch(args)
    assert called == [] and json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))["meta"]["warmed_up"] is None
