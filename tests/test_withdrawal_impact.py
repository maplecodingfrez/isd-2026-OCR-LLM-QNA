import sqlite3
from types import SimpleNamespace

from lab10_fastapi.curriculum_app.database import CurriculumDatabase
import lab8b_curriculum_db as m
from prereq_from_book import extract_prerequisites


def test_course_display_preserves_zero_hours_and_never_fills_missing_hours():
    from course_display import add_course_display
    from lab10_fastapi.curriculum_app.schemas import CoursePrerequisitesResponse
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE course(code TEXT, name_th TEXT, name_en TEXT, credits INTEGER,
                            lecture_h INTEGER, lab_h INTEGER, self_h INTEGER);
        INSERT INTO course VALUES ('00000001','ไทย','ENGLISH',3,3,0,6),
                                  ('00000002','ขาด','MISSING',3,3,NULL,6);
        """)
        rows = [{"code": "00000001", "name_th": "ไทย", "credits": 3},
                {"code": "00000002", "credits": 3},
                {"code": "00000001", "credits": 2}]
        add_course_display(conn, rows)
        assert rows[0]["credits_display"] == "3 (3-0-6)"
        assert rows[0]["name_en"] == "ENGLISH"
        assert "credits_display" not in rows[1]
        assert "credits_display" not in rows[2]
        response = CoursePrerequisitesResponse(**rows[0], prerequisites_required=[rows[0]])
        assert response.model_dump()["prerequisites_required"][0]["credits_display"] == "3 (3-0-6)"


def test_reverse_impact_handles_branch_cycle_alternative_and_corequisite(tmp_path):
    path = tmp_path / "curriculum.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
        CREATE TABLE course(code TEXT, name_th TEXT, name_en TEXT, credits INTEGER);
        CREATE TABLE prerequisite(code TEXT, requires TEXT, kind TEXT);
        CREATE TABLE prerequisite_alt(code TEXT, requires TEXT, group_no INTEGER);
        INSERT INTO course VALUES ('00000001','A','A',3),('00000002','B','B',3),
          ('00000003','C','C',3),('00000004','D','D',3),('00000005','E','E',3);
        INSERT INTO prerequisite VALUES ('00000002','00000001','pre'),
          ('00000003','00000002','pre'),('00000001','00000003','pre'),
          ('00000004','00000001','co'),('00000002','00000005','pre');
        INSERT INTO prerequisite_alt VALUES ('00000002','00000001',1),('00000002','00000005',1);
        """)

    def open_db(path, readonly=True):
        assert readonly
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    lab = SimpleNamespace(open_db=open_db, _prereq_pair_pages=lambda c: [],
                          _citations_module=lambda: SimpleNamespace(add_course_names=lambda c, rows: None),
                          withdrawal_graph=m.withdrawal_graph)
    db = CurriculumDatabase(lab, path, 100)
    data = db.withdrawal_impact("00000001")
    assert [r["code"] for r in data["direct"]] == ["00000002", "00000004"]
    assert [r["code"] for r in data["indirect"]] == ["00000003"]
    assert data["direct"][0]["path"][0]["alternative"] is True
    assert data["direct"][1]["path"][0]["kind"] == "co"
    assert data["indirect"][0]["depth"] == 2
    assert db.withdrawal_impact("00000005")["direct"][0]["code"] == "00000002"
    assert db.withdrawal_impact("99999999") is None
    assert db.withdrawal_impact("00000004")["direct"] == []


def test_name_prerequisite_requires_exact_unique_name():
    lines = ["90644008 FOUNDATION ENGLISH 2 3 (3-0-6)", "PREREQUISITE : FOUNDATION ENGLISH 1"]
    names = {"90644007": ["ภาษาอังกฤษพื้นฐาน 1", "FOUNDATION ENGLISH 1"]}
    assert extract_prerequisites(lines, ["90644008"], course_names=names)["90644008"]["requires"] == ["90644007"]
    names["99999999"] = ["FOUNDATION ENGLISH 1"]
    assert extract_prerequisites(lines, ["90644008"], course_names=names)["90644008"]["status"] == "unreadable"
    assert extract_prerequisites([lines[0], "PREREQUISITE : FOUNDATION ENGLISH"], ["90644008"], course_names=names)["90644008"]["status"] == "unreadable"
    damaged = ["90644007 ภาษาอังกฤษพื้นฐาน 1 36306)", "FOUNDATION ENGLISH 1", "PREREQUISITE : NONE"]
    names.pop("99999999")
    assert extract_prerequisites(damaged, ["90644007"], course_names=names)["90644007"]["status"] == "none"


def test_named_prerequisite_lists_resolve_every_title():
    names = {"00000001": ["FIRST COURSE", "วิชาแรก"], "00000002": ["SECOND COURSE", "วิชาที่สอง"]}
    header = "00000003 TARGET 3 (3-0-6)"
    for value, op in [("FIRST COURSE OR SECOND COURSE", "or"),
                      ("FIRST COURSE AND SECOND COURSE", "and"),
                      ("วิชาแรก หรือ วิชาที่สอง", "or"),
                      ("วิชาแรก และ วิชาที่สอง", "and")]:
        result = extract_prerequisites([header, "PREREQUISITE : " + value], ["00000003"], course_names=names)["00000003"]
        assert result["requires"] == ["00000001", "00000002"]
        assert result["op"] == op
    for value in ["FIRST COURSE OR UNKNOWN", "FIRST OR SECOND COURSE",
                  "FIRST COURSE OR SECOND COURSE AND FIRST COURSE"]:
        result = extract_prerequisites([header, "PREREQUISITE : " + value], ["00000003"], course_names=names)["00000003"]
        assert result["status"] == "unreadable"
        assert result["requires"] == []
    names["00000004"] = ["SECOND COURSE"]
    result = extract_prerequisites([header, "PREREQUISITE : FIRST COURSE OR SECOND COURSE"], ["00000003"], course_names=names)["00000003"]
    assert result["status"] == "unreadable"


def test_withdrawal_question_uses_graph_without_model(monkeypatch):
    import sqlite3
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must use graph")))
    with m.open_db(":memory:") as conn:
        conn.executescript("""
        CREATE TABLE course(code TEXT, name_th TEXT, name_en TEXT, credits INTEGER);
        CREATE TABLE prerequisite(code TEXT, requires TEXT, kind TEXT);
        INSERT INTO course VALUES ('90644007','ภาษาอังกฤษพื้นฐาน 1','FOUNDATION ENGLISH 1',3),
          ('90644008','ภาษาอังกฤษพื้นฐาน 2','FOUNDATION ENGLISH 2',3),('00000003','C','C',3);
        INSERT INTO prerequisite VALUES ('90644008','90644007','pre'),('00000003','90644008','pre');
        """)
        answer, rows, sql = m._withdrawal_answer(conn, "ถ้าถอนวิชา 90644007 ออกไป")
        assert [r["code"] for r in rows] == ["90644008", "00000003"]
        assert "FOUNDATION ENGLISH 2" in answer and "ทางอ้อม" in answer
        assert "90644007 → 90644008 → 00000003" in answer
        assert {r["code"] for r in conn.execute(sql)} == {r["code"] for r in rows}
        assert m._withdrawal_answer(conn, "ถ้าถอนวิชา 99999999 ออกไป") == m._NOT_FOUND
        assert m._withdrawal_answer(conn, "ถ้าถอนวิชา 90644007 และ 90644008") == m._NOT_FOUND
        assert m._withdrawal_answer(conn, "ถ้าถอนวิชา 90644007 ค่าเทอมคืนไหม") is None


def test_dsba_english_withdrawal_answer_and_tool_agree(monkeypatch):
    from pathlib import Path
    from contextlib import closing
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must use graph")))
    root = Path(__file__).resolve().parents[1]
    for plan in ["coop", "no_coop"]:
        db = CurriculumDatabase(m, root / "Lab7B_Lab8B_ocr_system/runs/DSBA" / plan / "lab8b_output/curriculum.db")
        with closing(m.open_db(db.path, readonly=True)) as conn:
            result = m.ask(conn, "ถ้าถอนวิชา 90644007 ออกไป", verbose=False)
        assert [r["code"] for r in result["rows"]] == ["90644008"]
        assert result["rows"] == db.withdrawal_impact("90644007")["direct"]
        assert [c["pdf_page"] for c in result["citations"]] == [209]
        assert result["answer_type"] == "database"
        assert db.get_course_prerequisites("90644008")["prerequisites_required"][0]["code"] == "90644007"
