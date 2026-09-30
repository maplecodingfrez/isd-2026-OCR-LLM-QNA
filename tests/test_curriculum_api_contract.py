"""Lab 11 — สัญญา API ระหว่าง curriculum_app กับหน้าเว็บ (ไม่ต้องเปิด Ollama).

ทุกแถวในตาราง error ของ README §13 ต้องเป็นจริงกับ backend ปัจจุบัน — ถ้าเทสต์ไหนล้ม
แปลว่า README/หน้าเว็บเข้าใจ backend ผิด ให้แก้เอกสาร/frontend (ห้ามแก้ backend)
"""

from pathlib import Path

import pytest
import requests
from starlette.testclient import TestClient

from lab10_fastapi.curriculum_app import main


@pytest.fixture()
def client():
    return TestClient(main.app)


class _Conn:
    def close(self):
        pass


@pytest.fixture()
def fake_db(monkeypatch, tmp_path):
    """program 'it_no_coop' และ None (ค่าเริ่มต้น) ชี้ไฟล์ที่มีอยู่จริง; ชื่ออื่น = ไม่รู้จัก"""
    db = tmp_path / "curriculum.db"
    db.write_bytes(b"")
    monkeypatch.setattr(main, "program_db_path",
                        lambda program: db if program in (None, "it_no_coop") else None)
    monkeypatch.setattr(main.lab8b, "open_db", lambda path, readonly=True: _Conn())
    return db


def _result(**over):
    base = {
        "question": "ปี 1 เทอม 1 กี่หน่วยกิต", "sql": "SELECT 20 AS credits",
        "rows": [{"credits": 20}], "answer": "20 หน่วยกิต", "error": None,
        "citations": [{"pdf_page": 38, "printed_page": 33}],
        "citation_text": "(อ้างอิง: เล่มหลักสูตร หน้า 33 (PDF 38))",
    }
    base.update(over)
    return base


# ---------- POST /api/ask ----------

def test_ask_200_has_every_key_the_page_reads(client, fake_db, monkeypatch):
    monkeypatch.setattr(main.lab8b, "ask", lambda conn, q, verbose=False: _result())
    r = client.post("/api/ask", json={"question": "ปี 1 เทอม 1 กี่หน่วยกิต", "program": "it_no_coop"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"question", "program", "sql", "rows", "answer", "citations", "citation_text"}
    assert body["program"] == "it_no_coop"
    assert body["citations"] == [{"pdf_page": 38, "printed_page": 33}]
    # ชนิดข้อมูลที่ README §13.2 ประกาศไว้
    assert isinstance(body["question"], str) and isinstance(body["answer"], str)
    assert isinstance(body["sql"], str) and isinstance(body["citation_text"], str)
    assert isinstance(body["rows"], list) and all(isinstance(r, dict) for r in body["rows"])
    assert all(isinstance(c["pdf_page"], int) for c in body["citations"])


def test_ask_200_with_empty_rows_is_not_an_error(client, fake_db, monkeypatch):
    monkeypatch.setattr(main.lab8b, "ask", lambda conn, q, verbose=False: _result(
        rows=[], answer="ไม่พบข้อมูลนี้ในเล่มหลักสูตร", citations=[], citation_text=""))
    r = client.post("/api/ask", json={"question": "วิชาที่ไม่มีอยู่จริง"})
    assert r.status_code == 200
    assert r.json()["rows"] == []


@pytest.mark.parametrize("question", ["ab", "ก" * 500])
def test_ask_accepts_length_boundaries(client, fake_db, monkeypatch, question):
    monkeypatch.setattr(main.lab8b, "ask", lambda conn, q, verbose=False: _result())
    assert client.post("/api/ask", json={"question": question}).status_code == 200


@pytest.mark.parametrize("payload", [{"question": "ก"}, {"question": "ก" * 501}, {}])
def test_ask_422_pydantic_detail_is_a_list_of_msg(client, payload):
    r = client.post("/api/ask", json=payload)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, list) and detail
    assert all(isinstance(item.get("msg"), str) for item in detail)


def test_ask_422_lab8b_error_detail_is_a_string(client, fake_db, monkeypatch):
    monkeypatch.setattr(main.lab8b, "ask", lambda conn, q, verbose=False: _result(
        error="SQL ไม่ผ่านการตรวจ", rows=[], answer=""))
    r = client.post("/api/ask", json={"question": "คำถามที่ทำให้ SQL พัง"})
    assert r.status_code == 422
    assert r.json()["detail"] == "SQL ไม่ผ่านการตรวจ"


def test_ask_404_unknown_program(client, fake_db):
    r = client.post("/api/ask", json={"question": "คำถามทดสอบ", "program": "nope"})
    assert r.status_code == 404
    assert isinstance(r.json()["detail"], str)


def test_ask_503_when_database_file_is_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "program_db_path", lambda program: tmp_path / "missing.db")
    r = client.post("/api/ask", json={"question": "คำถามทดสอบ"})
    assert r.status_code == 503
    assert r.json()["detail"].startswith("ไม่พบฐานข้อมูล")


def test_ask_503_when_ollama_is_unreachable(client, fake_db, monkeypatch):
    def boom(conn, q, verbose=False):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(main.lab8b, "ask", boom)
    r = client.post("/api/ask", json={"question": "คำถามทดสอบ"})
    assert r.status_code == 503
    assert r.json()["detail"] == "ติดต่อ Ollama ไม่ได้"


# ---------- GET /api/courses/{code}/prerequisites ----------

_PREREQ = {"code": "06016407", "name_th": "โครงงาน 2", "name_en": "Project 2", "credits": 3,
           "prerequisites_required": [{"code": "06016406", "name_th": "โครงงาน 1", "credits": 3, "kind": "pre"}],
           "unlocked_courses": []}


def test_prerequisites_200_shape(client, monkeypatch):
    monkeypatch.setattr(main.database, "get_course_prerequisites", lambda code: dict(_PREREQ))
    r = client.get("/api/courses/06016407/prerequisites")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"code", "name_th", "name_en", "credits", "prerequisites_required", "unlocked_courses"}
    assert body["prerequisites_required"][0]["code"] == "06016406"
    # ชนิดข้อมูลที่ README §13.3 ประกาศไว้
    assert isinstance(body["code"], str) and isinstance(body["credits"], int)
    assert isinstance(body["prerequisites_required"], list) and isinstance(body["unlocked_courses"], list)


@pytest.mark.parametrize("code", ["abc", "1234567", "123456789"])
def test_prerequisites_422_when_code_is_not_8_digits(client, code):
    r = client.get(f"/api/courses/{code}/prerequisites")
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


def test_prerequisites_404_when_course_missing(client, monkeypatch):
    monkeypatch.setattr(main.database, "get_course_prerequisites", lambda code: None)
    r = client.get("/api/courses/99999999/prerequisites")
    assert r.status_code == 404
    assert "99999999" in r.json()["detail"]


def test_prerequisites_503_when_database_missing(client, monkeypatch):
    def boom(code):
        raise FileNotFoundError("ไม่พบฐานข้อมูล")
    monkeypatch.setattr(main.database, "get_course_prerequisites", boom)
    assert client.get("/api/courses/06016407/prerequisites").status_code == 503


# ---------- endpoint เสริมตอนโหลดหน้า ----------

def test_program_503_when_database_missing(client, monkeypatch):
    def boom():
        raise FileNotFoundError("ไม่พบฐานข้อมูล")
    monkeypatch.setattr(main.database, "program", boom)
    assert client.get("/api/program").status_code == 503


def test_program_200_shape(client, monkeypatch):
    monkeypatch.setattr(main.database, "program",
                        lambda: {"name_th": "เทคโนโลยีสารสนเทศ", "total_credits": 129, "years": 4})
    body = client.get("/api/program").json()
    assert body["name_th"] and body["total_credits"] == 129


def test_programs_lists_id_label_available(client):
    r = client.get("/api/programs")
    assert r.status_code == 200
    items = r.json()
    assert items and all({"id", "label", "available"} <= set(i) for i in items)
    assert all(isinstance(i["available"], bool) for i in items)


def test_courses_200_shape(client, monkeypatch):
    monkeypatch.setattr(main.database, "courses", lambda search, limit, offset: [
        {"code": "06016407", "name_th": "โครงงาน 2", "credits": 3}])
    r = client.get("/api/courses?limit=100")
    assert r.status_code == 200
    assert r.json()[0]["code"] == "06016407"


def test_health_reports_database_and_ollama_flags(client, monkeypatch):
    monkeypatch.setattr(main.model, "available", lambda: True)
    body = client.get("/api/health").json()
    assert body["status"] in ("ok", "degraded")
    assert isinstance(body["database_ready"], bool) and body["ollama_ready"] is True


@pytest.mark.skipif(not main.settings.db_path.exists(), reason="ต้องมีไฟล์ DB เริ่มต้นเพื่อรัน lab8b.ask จริง")
def test_ask_422_when_ollama_is_down_during_sql_generation(client, monkeypatch):
    """เส้นทางจริง: lab8b.ask จับทุก exception ในขั้นสร้าง SQL แล้วคืน error เป็นสตริง -> 422 (ไม่ใช่ 503)"""
    def boom(*args, **kwargs):
        raise requests.ConnectionError("Max retries exceeded")
    monkeypatch.setattr(main.lab8b, "ollama_generate", boom)
    r = client.post("/api/ask", json={"question": "หลักสูตรนี้มีหน่วยกิตรวมกี่หน่วยกิต"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and r.json()["detail"].startswith("ConnectionError")
