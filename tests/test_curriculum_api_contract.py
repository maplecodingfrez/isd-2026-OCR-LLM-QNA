"""Lab 11 — สัญญา API ระหว่าง curriculum_app กับหน้าเว็บ (ไม่ต้องเปิด Ollama).

ทุกแถวในตาราง error ของ README §13 ต้องเป็นจริงกับ backend ปัจจุบัน — ถ้าเทสต์ไหนล้ม
แปลว่า README/หน้าเว็บเข้าใจ backend ผิด ให้แก้เอกสาร/frontend (ห้ามแก้ backend)
"""

from pathlib import Path

import threading

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


@pytest.mark.parametrize("answer_type", ["database", "rule", "ocr", "ai", "hybrid", None])
def test_ask_provenance_is_additive_and_keeps_existing_result(client, fake_db, monkeypatch, answer_type):
    monkeypatch.setattr(main.lab8b, "ask", lambda conn, q, verbose=False: _result(answer_type=answer_type))
    response = client.post("/api/ask", json={"question": "หลักสูตรนี้มีกี่หน่วยกิต"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer_type"] == answer_type
    assert data["processing_seconds"] >= 0
    assert {"question", "program", "sql", "rows", "answer", "citations", "citation_text"} <= data.keys()


@pytest.mark.parametrize("payload", [{"question": "ก"}, {"question": "ก" * 501}, {}])
def test_ask_422_pydantic_detail_is_a_list_of_msg(client, payload):
    r = client.post("/api/ask", json=payload)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, list) and detail
    assert all(isinstance(item.get("msg"), str) for item in detail)


def test_ask_422_lab8b_infrastructure_error_detail_is_a_string(client, fake_db, monkeypatch):
    monkeypatch.setattr(main.lab8b, "ask", lambda conn, q, verbose=False: _result(
        error="ConnectionError: Ollama ไม่ตอบ", rows=[], answer=""))
    r = client.post("/api/ask", json={"question": "คำถามที่ Ollama ล่ม"})
    assert r.status_code == 422
    assert r.json()["detail"] == "ConnectionError: Ollama ไม่ตอบ"


# Failed SQL is distinct from an executed query with no matching rows.
@pytest.mark.parametrize("error", ["OperationalError: ambiguous column name: name_th", "SQL ไม่ผ่านการตรวจ", "ValueError: only SELECT"])
def test_ask_reports_failed_sql_generation_as_safe_query_error(client, fake_db, monkeypatch, error):
    monkeypatch.setattr(main.lab8b, "ask", lambda conn, q, verbose=False: _result(error=error, rows=[], answer="ไม่สามารถตอบคำถามนี้ได้ กรุณาตรวจสอบเอง"))
    response = client.post("/api/ask", json={"question": "คำถามที่ทำให้ SQL พัง"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str) and "แปลงคำถาม" in detail
    assert error not in detail and "ไม่พบข้อมูล" not in detail


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


def test_prerequisite_status_and_alternatives_survive_http_contract(client, tmp_path, monkeypatch):
    import sqlite3
    from lab10_fastapi.curriculum_app.database import CurriculumDatabase
    path = tmp_path / 'curriculum.db'
    with main.lab8b.open_db(path) as conn:
        conn.executescript(main.lab8b.DDL + main.lab8b.PREREQ_STATUS_DDL +
                           main.lab8b.PREREQ_ALT_DDL + main.lab8b.COURSE_PAGE_DDL)
        for n, status in [(1,'none'),(2,'not_found'),(3,'unreadable'),(4,'found')]:
            code = f'{n:08d}'
            conn.execute('INSERT INTO course(code,name_th,credits) VALUES (?,?,3)', (code,f'วิชา{n}'))
            conn.execute('INSERT INTO prerequisite_status VALUES (?,?)',(code,status))
        conn.executemany("INSERT INTO prerequisite VALUES ('00000004',?,'pre')", [('00000001',),('00000002',)])
        conn.executemany("INSERT INTO prerequisite_alt VALUES ('00000004',?,1)", [('00000001',),('00000002',)])
        conn.execute("INSERT INTO course_page VALUES ('00000001',10,'9','description')")
    db = CurriculumDatabase(main.lab8b,path,100)
    monkeypatch.setattr(main,'database',db)
    for n, status in [(1,'none'),(2,'not_found'),(3,'unreadable'),(4,'found')]:
        response = client.get(f'/api/courses/{n:08d}/prerequisites')
        assert response.status_code == 200
        assert response.json()['prerequisite_status'] == status
    none = client.get('/api/courses/00000001/prerequisites').json()
    assert any(p['pdf_page']==10 for p in none['citations'])
    found = client.get('/api/courses/00000004/prerequisites').json()
    assert [r['alternative_group'] for r in found['prerequisites_required']] == [1,1]
    with sqlite3.connect(path) as conn:
        conn.execute('DROP TABLE prerequisite_status')
        conn.execute('DROP TABLE prerequisite_alt')
    assert client.get('/api/courses/00000001/prerequisites').json()['prerequisite_status'] == 'unknown'
    props = client.get('/openapi.json').json()['components']['schemas']['CoursePrerequisitesResponse']['properties']
    assert props['prerequisite_status']['default'] == 'unknown'


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
    r = client.post("/api/ask", json={"question": "หลักสูตรนี้ยากไหม"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and r.json()["detail"].startswith("ConnectionError")


# ---------- ?program= : แผงตรวจวิชาและรายการวิชาตามหลักสูตรที่ผู้ใช้เลือก ----------

def _program_dbs_exist(*ids):
    return all((p := main.program_db_path(i)) is not None and p.exists() for i in ids)


@pytest.mark.skipif(not _program_dbs_exist("it_no_coop", "dsba_coop"), reason="ต้องมี DB ของ IT และ DSBA")
def test_prerequisites_follow_the_program_query_param(client):
    """06016407 (โครงงาน 2) อยู่ใน IT แต่ไม่อยู่ใน DSBA สหกิจ — ผลต้องต่างตามหลักสูตรที่ส่งมา"""
    in_it = client.get("/api/courses/06016407/prerequisites?program=it_no_coop")
    assert in_it.status_code == 200 and in_it.json()["code"] == "06016407"
    not_in_dsba = client.get("/api/courses/06016407/prerequisites?program=dsba_coop")
    assert not_in_dsba.status_code == 404


@pytest.mark.skipif(not _program_dbs_exist("it_no_coop", "ait"), reason="ต้องมี DB ของ IT และ AIT")
def test_courses_follow_the_program_query_param(client):
    ait = client.get("/api/courses?limit=3&program=ait").json()
    it = client.get("/api/courses?limit=3&program=it_no_coop").json()
    assert ait and it and ait[0]["code"] != it[0]["code"]
    assert all(c["code"].startswith("06046") for c in ait)        # รหัสวิชาของ AIT


@pytest.mark.parametrize("path", ["/api/courses?program=nope", "/api/courses/06016407/prerequisites?program=nope"])
def test_program_param_unknown_is_404_with_string_detail(client, path):
    r = client.get(path)
    assert r.status_code == 404
    assert isinstance(r.json()["detail"], str) and "nope" in r.json()["detail"]


@pytest.mark.parametrize("path", ["/api/courses?program=it_no_coop", "/api/courses/06016407/prerequisites?program=it_no_coop"])
def test_program_param_with_missing_database_is_503(client, monkeypatch, tmp_path, path):
    monkeypatch.setattr(main, "program_db_path", lambda program: tmp_path / "missing.db")
    r = client.get(path)
    assert r.status_code == 503
    assert isinstance(r.json()["detail"], str)


# ---------- อุ่นโมเดลตอนเริ่มเซิร์ฟเวอร์ (คำถามแรกของ Challenge ไม่ต้องรอโหลดโมเดล) ----------

def test_server_warms_up_the_model_in_the_background_on_startup(monkeypatch):
    started = threading.Event()
    monkeypatch.setattr(main.lab8b, "warm_up", lambda timeout=180: started.set() or True)
    with TestClient(main.app):                       # ใช้ with เพื่อให้ lifespan ทำงาน
        assert started.wait(3), "ไม่มีการเรียก warm_up ตอนเริ่มเซิร์ฟเวอร์"


def test_startup_survives_when_warm_up_raises(monkeypatch):
    def boom(timeout=180):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(main.lab8b, "warm_up", boom)
    with TestClient(main.app) as c:                  # เธรดเบื้องหลังล้มได้ แต่เซิร์ฟเวอร์ต้องยังตอบ
        assert c.get("/api/programs").status_code == 200


# เจอตอนทดสอบ clone สะอาด: ค่าตั้งต้นของ CURRICULUM_DB_PATH ชี้ไป work/lab8b_run/ ซึ่งไม่อยู่ใน repo (gitignore) → เครื่องที่ clone มา
# (ไม่มี .env) ขึ้น "ไม่พบฐานข้อมูล" และ /api/ask ที่ไม่ส่ง program ตอบ 503 — ค่าตั้งต้นต้องเป็นฐานข้อมูลที่ติดมากับ repo
def test_default_database_path_is_a_file_that_ships_with_the_repo(monkeypatch):
    import importlib
    monkeypatch.delenv("CURRICULUM_DB_PATH", raising=False)
    import lab10_fastapi.curriculum_app.config as cfg
    import dotenv
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    fresh = importlib.reload(cfg)
    try:
        assert "work" not in fresh.settings.db_path.parts
        assert fresh.settings.db_path.exists()
        assert str(fresh.settings.db_path.relative_to(fresh.PROJECT_ROOT)).replace("\\", "/") == fresh.PROGRAMS["dsba_coop"][1]
    finally:
        importlib.reload(cfg)
