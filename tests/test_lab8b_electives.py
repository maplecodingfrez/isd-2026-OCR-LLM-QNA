"""วิชาเลือก + ค้นวิชาตามหัวข้อ — ราก: elective_group ว่างทั้ง 7 DB (ไม่เคยรัน load-electives) และโมเดลเดาชื่อ view ผิด
(v_elective_group_course) / ตอบ SQL ว่างเมื่อถามตามหัวข้อ. คำใบ้เปิดเฉพาะเมื่อคำถามพูดถึงเรื่องนั้น → prompt ของคำถามอื่น (รวมชุดเฉลย) เหมือนเดิมทุกตัวอักษร"""

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "Lab7B_Lab8B_ocr_system" / "runs"
ALL_DBS = ["AIT", "BIT/coop", "BIT/no_coop", "DSBA/coop", "DSBA/no_coop", "IT/coop", "IT/no_coop"]
MARKER_ELECTIVE = "วิชาเลือกของหลักสูตรนี้ (จากแคตตาล็อก)"
MARKER_TOPIC = "ค้นวิชาตามหัวข้อ"


def _make_db(path, electives=True):
    c = sqlite3.connect(path)
    c.executescript(m.DDL)
    c.execute("INSERT INTO program VALUES ('P', 'โปรแกรมทดสอบ', 'Test', 'วท.บ.', 129, 4)")
    if electives:
        c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) "
                  "VALUES (1, 'P', 'ช่องทดสอบ', 6, 1, 'กลุ่มทดสอบ')")
        for code, name in (("06010001", "วิชาเลือก ก"), ("06010002", "วิชาเลือก ข")):
            c.execute("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (1, ?, ?, 'X', 3)",
                      (code, name))
    c.commit()
    return c


# ---------- pipeline: ขั้นโหลดแคตตาล็อกต้องอยู่ใน run_lab8b.py เพื่อให้รันซ้ำแล้วได้ผลเหมือนเดิม ----------

def test_the_pipeline_runner_loads_the_elective_catalog():
    src = (REPO / "Lab7B_Lab8B_ocr_system" / "run_lab8b.py").read_text(encoding="utf-8")
    assert '"load-electives"' in src and "electives.json" in src and '"--program-id", program_id' in src


@pytest.mark.parametrize("rel", ALL_DBS)
def test_every_real_database_has_the_elective_catalog_loaded(rel):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    with closing(m.open_db(db, readonly=True)) as conn:
        n_groups, n_courses = conn.execute(
            "SELECT COUNT(DISTINCT group_no), COUNT(*) FROM v_elective_group").fetchone()
    assert n_groups >= 1 and n_courses >= 9


# ---------- คำใบ้วิชาเลือก ----------

def test_elective_hint_names_the_view_and_columns_when_the_question_is_about_electives(tmp_path):
    with closing(_make_db(tmp_path / "t.db")) as conn:
        hint = m._elective_hint_text(conn, "วิชาเลือกมีอะไรบ้าง")
    assert MARKER_ELECTIVE in hint and "v_elective_group" in hint and "course_name_th" in hint
    assert hint.endswith("\n\n")                                  # รูปแบบเดียวกับ hint อื่นที่แทรกก่อนบรรทัดคำถาม


@pytest.mark.parametrize("question", [
    "หลักสูตรนี้มีหน่วยกิตรวมกี่หน่วยกิต",                          # ไม่เกี่ยวกับวิชาเลือก
    "วิชาเลือกเสรีเลือกได้กี่หน่วยกิต",                              # วิชาเลือกเสรี ไม่ใช่แคตตาล็อกเฉพาะทาง
    "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง",
])
def test_elective_hint_stays_silent_for_other_questions(tmp_path, question):
    with closing(_make_db(tmp_path / "t.db")) as conn:
        assert m._elective_hint_text(conn, question) == ""


def test_elective_hint_stays_silent_when_the_catalog_is_empty(tmp_path):
    with closing(_make_db(tmp_path / "t.db", electives=False)) as conn:
        assert m._elective_hint_text(conn, "วิชาเลือกมีอะไรบ้าง") == ""


# ---------- คำใบ้ค้นตามหัวข้อ ----------

@pytest.mark.parametrize("question", ["มีวิชาเกี่ยวกับ AI หรือ machine learning ไหม", "วิชาที่เกี่ยวกับฐานข้อมูลมีอะไรบ้าง",
                                      "วิชาไหนเกี่ยวข้องกับเครือข่าย"])
def test_topic_hint_explains_like_search_over_course_names(tmp_path, question):
    with closing(_make_db(tmp_path / "t.db")) as conn:
        hint = m._topic_hint_text(conn, question)
    assert MARKER_TOPIC in hint and "LIKE" in hint and "name_en" in hint and "v_elective_group" in hint


@pytest.mark.parametrize("question", ["หลักสูตรนี้เกี่ยวกับอะไร", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง", "06016407 ชื่อวิชาอะไร"])
def test_topic_hint_stays_silent_without_a_topic_question(tmp_path, question):
    with closing(_make_db(tmp_path / "t.db")) as conn:
        assert m._topic_hint_text(conn, question) == ""


def test_topic_hint_skips_the_elective_union_when_the_view_is_missing(tmp_path):
    with closing(sqlite3.connect(tmp_path / "old.db")) as conn:   # DB เก่าที่ไม่มีตาราง/view วิชาเลือก
        conn.executescript("CREATE TABLE course(code TEXT, name_th TEXT, name_en TEXT);")
        hint = m._topic_hint_text(conn, "มีวิชาเกี่ยวกับ AI ไหม")
    assert MARKER_TOPIC in hint and "v_elective_group" not in hint


# ---------- ต่อเข้า ask(): prompt เปลี่ยนเฉพาะคำถามที่เกี่ยวข้อง ----------

def _prompts_for(tmp_path, monkeypatch, question):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)                       # test เรียกฟังก์ชันนี้หลายรอบใน tmp_path เดียวกัน
    _make_db(path).close()
    prompts = []

    def fake(prompt, fmt=None, **kw):
        prompts.append(prompt)
        return json.dumps({"sql": "SELECT code FROM v_elective_group"}) if len(prompts) == 1 else json.dumps({"answer": "ok"})

    monkeypatch.setattr(m, "ollama_generate", fake)
    with closing(m.open_db(path, readonly=True)) as conn:
        m.ask(conn, question, verbose=False)
    return prompts[0]


def test_ask_adds_the_elective_hint_only_for_elective_questions(tmp_path, monkeypatch):
    assert MARKER_ELECTIVE in _prompts_for(tmp_path, monkeypatch, "วิชาเลือกมีอะไรบ้าง")
    plain = _prompts_for(tmp_path, monkeypatch, "หลักสูตรนี้มีหน่วยกิตรวมกี่หน่วยกิต")
    assert MARKER_ELECTIVE not in plain and MARKER_TOPIC not in plain


def test_ask_adds_the_topic_hint_only_for_topic_questions(tmp_path, monkeypatch):
    assert MARKER_TOPIC in _prompts_for(tmp_path, monkeypatch, "มีวิชาเกี่ยวกับเครือข่ายไหม")
    assert MARKER_TOPIC not in _prompts_for(tmp_path, monkeypatch, "ปี 1 เทอม 1 กี่หน่วยกิต")


# ---------- รายการหลายคอลัมน์: คำตอบของโมเดลโดนตัดกลางสตริง (num_predict) → ต้องไม่ส่งคำตอบว่างให้ผู้ตรวจ ----------

def _ask_with_model_answer(tmp_path, monkeypatch, model_answer_raw, rows_sql="SELECT group_no, code, course_name_th, credits FROM v_elective_group"):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _make_db(path).close()
    calls = []

    def fake(prompt, fmt=None, **kw):
        calls.append(prompt)
        return json.dumps({"sql": rows_sql}) if len(calls) == 1 else model_answer_raw

    monkeypatch.setattr(m, "ollama_generate", fake)
    with closing(m.open_db(path, readonly=True)) as conn:
        return m.ask(conn, "วิชาเลือกมีอะไรบ้าง", verbose=False)


def test_truncated_model_answer_for_a_multi_column_list_is_rebuilt_from_the_rows(tmp_path, monkeypatch):
    truncated = '{"answer": "วิชาเลือก ก, วิชาเลือ'                       # โดนตัด → JSON ไม่ครบ
    r = _ask_with_model_answer(tmp_path, monkeypatch, truncated)
    assert "วิชาเลือก ก" in r["answer"] and "วิชาเลือก ข" in r["answer"] and "06010001" in r["answer"]


def test_garbled_thai_in_a_multi_column_list_is_replaced_by_the_exact_values(tmp_path, monkeypatch):
    garbled = json.dumps({"answer": "วิชาเลือก ก, วิชาเลือก ฃ"})              # ตัวอักษรเพี้ยน
    r = _ask_with_model_answer(tmp_path, monkeypatch, garbled)
    assert "วิชาเลือก ข" in r["answer"]


def test_a_complete_multi_column_answer_is_left_untouched(tmp_path, monkeypatch):
    good = json.dumps({"answer": "06010001 วิชาเลือก ก, 06010002 วิชาเลือก ข"})
    r = _ask_with_model_answer(tmp_path, monkeypatch, good)
    assert r["answer"].startswith("06010001 วิชาเลือก ก") and "|" not in r["answer"]


# ---------- แถวซ้ำต่างกันแค่การสะกด (ำ เทียบ ํา) ----------

def test_rows_for_the_same_course_that_differ_only_in_thai_spelling_collapse_to_one():
    rows = [{"code": "06026244", "name_th": "การดูแลและบํารุงรักษา", "credits": 3},      # ํา แยกอักขระ (จาก OCR)
            {"code": "06026244", "name_th": "การดูแลและบำรุงรักษา", "credits": 3},
            {"code": "06026207", "name_th": "ก", "credits": 3}]
    got = m._dedupe_rows(rows)
    assert [r["code"] for r in got] == ["06026244", "06026207"]
    assert got[0]["name_th"] == "การดูแลและบำรุงรักษา"                                  # เก็บแบบสะกดมาตรฐาน


def test_same_course_in_different_terms_is_not_collapsed():
    rows = [{"code": "06026244", "year": 2}, {"code": "06026244", "year": 3}]
    assert m._dedupe_rows(rows) == rows


def test_rows_without_a_code_column_are_left_alone():
    rows = [{"credits": 3}, {"credits": 3}]
    assert m._dedupe_rows(rows) == rows


# ---------- คำถามควบ "ปี/เทอมนี้ กี่หน่วยกิต + มีวิชาอะไรบ้าง" ----------
# ราก: มีคำว่า "กี่หน่วยกิต/กี่วิชา" → โมเดลเลือก v_semester_credits (มีแค่ credits, n_courses ไม่มีชื่อวิชา);
# ถามแบบ "…มีวิชาอะไรบ้าง" → เลือก v_plan (ได้ชื่อวิชา แต่ไม่มียอดรวม) — ได้ครึ่งเดียวทั้งสองทาง

MARKER_TERM = "สรุปรายเทอมพร้อมรายวิชา"
GOLD = sorted((REPO / "Lab9_evaluation" / "gold_questions").glob("*_gold_questions.json"))


@pytest.mark.parametrize("question", [
    "ปี 2 เทอม 1 มีกี่หน่วยกิต และมีกี่วิชาอะไรบ้าง",
    "ปี 2 เทอม 1 เรียนกี่หน่วยกิต มีวิชาอะไรบ้าง",
    "ชั้นปีที่ 3 ภาคการศึกษาที่ 2 มีกี่วิชา และวิชาอะไรบ้าง",
    "เทอม 2 ปี 1 รวมกี่หน่วยกิต แล้วต้องเรียนอะไรบ้าง",
])
def test_term_summary_hint_fires_when_both_a_total_and_a_course_list_are_asked(question):
    hint = m._term_summary_hint_text(question)
    assert MARKER_TERM in hint and "v_plan" in hint and "v_semester_credits" in hint and "total_credits" in hint
    assert hint.endswith("\n\n")


@pytest.mark.parametrize("question", [
    "ปี 2 เทอม 1 เรียนกี่หน่วยกิต",                              # ถามยอดอย่างเดียว
    "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง",                                # ถามรายวิชาอย่างเดียว
    "ในแผนการศึกษา ชั้นปีที่ 2 ภาคการศึกษาที่ 1 มีรายวิชาทั้งหมดกี่วิชา",
    "หลักสูตรนี้มีวิชาอะไรบ้าง กี่หน่วยกิต",                          # ไม่ระบุปี/เทอม
])
def test_term_summary_hint_stays_silent_otherwise(question):
    assert m._term_summary_hint_text(question) == ""


@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.name)
def test_no_gold_question_gets_the_term_summary_hint(path):
    """prompt ของชุดเฉลยต้องไม่เปลี่ยนจากคำใบ้นี้ (ไม่ปรับตามชุดเฉลย)"""
    for q in json.loads(path.read_text(encoding="utf-8")):
        assert m._term_summary_hint_text(q["question"]) == "", q["question"]


def test_ask_adds_the_term_summary_hint_only_for_compound_term_questions(tmp_path, monkeypatch):
    assert MARKER_TERM in _prompts_for(tmp_path, monkeypatch, "ปี 2 เทอม 1 มีกี่หน่วยกิต และมีวิชาอะไรบ้าง")
    assert MARKER_TERM not in _prompts_for(tmp_path, monkeypatch, "ปี 2 เทอม 1 เรียนกี่หน่วยกิต")


def test_totals_are_reported_once_not_repeated_on_every_course_row(tmp_path, monkeypatch):
    rows_sql = ("SELECT code, course_name_th AS name_th, credits, 6 AS total_credits, 2 AS n_courses "
                "FROM v_elective_group")
    r = _ask_with_model_answer(tmp_path, monkeypatch, json.dumps({"answer": "x"}), rows_sql=rows_sql)
    assert r["answer"].count("(รวม 6 หน่วยกิต, 2 วิชา)") == 1 and r["answer"].count("หน่วยกิต") == 1
    assert "06010001 วิชาเลือก ก" in r["answer"] and "06010002 วิชาเลือก ข" in r["answer"]



# ---------- ตัวสำรอง: คำถามควบแต่โมเดลตอบแค่ยอดรวม (ไม่มีชื่อวิชา) → รัน SQL แม่แบบเอง ----------

def _plan_db(path):
    c = _make_db(path, electives=False)
    c.execute("INSERT INTO course (code, name_th, credits) VALUES ('06010001', 'วิชาก', 3), ('06010002', 'วิชาข', 3)")
    c.executemany("INSERT INTO plan_item (program_id, year, semester, code, credits) VALUES ('P', ?, ?, ?, 3)",
                  [(2, 1, "06010001"), (2, 1, "06010002"), (3, 2, "06010001")])
    c.commit()
    return c


def _ask_compound(tmp_path, monkeypatch, question, model_sql):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _plan_db(path).close()
    calls = []

    def fake(prompt, fmt=None, **kw):
        calls.append(prompt)
        return json.dumps({"sql": model_sql}) if len(calls) == 1 else json.dumps({"answer": "ok"})

    monkeypatch.setattr(m, "ollama_generate", fake)
    with closing(m.open_db(path, readonly=True)) as conn:
        return m.ask(conn, question, verbose=False)


def test_compound_question_answered_with_totals_only_falls_back_to_the_template_sql(tmp_path, monkeypatch):
    r = _ask_compound(tmp_path, monkeypatch, "ปี 2 เทอม 1 มีกี่หน่วยกิต และมีกี่วิชาอะไรบ้าง",
                      "SELECT credits, n_courses FROM v_semester_credits WHERE year=2 AND semester=1")
    assert [row["name_th"] for row in r["rows"]] == ["วิชาก", "วิชาข"]
    assert "v_plan" in r["sql"] and "(รวม 6 หน่วยกิต, 2 วิชา)" in r["answer"]


def test_template_fallback_reads_year_and_term_from_the_question_in_either_order(tmp_path, monkeypatch):
    r = _ask_compound(tmp_path, monkeypatch, "เทอม 2 ของปี 3 รวมกี่หน่วยกิต แล้วเรียนอะไรบ้าง",
                      "SELECT credits FROM v_semester_credits WHERE year=3 AND semester=2")
    assert [row["name_th"] for row in r["rows"]] == ["วิชาก"]


def test_template_fallback_leaves_a_correct_model_sql_alone(tmp_path, monkeypatch):
    good = ("SELECT p.code, p.name_th, p.credits, s.credits AS total_credits, s.n_courses FROM v_plan p "
            "JOIN v_semester_credits s ON s.year = p.year AND s.semester = p.semester WHERE p.year = 2 AND p.semester = 1")
    r = _ask_compound(tmp_path, monkeypatch, "ปี 2 เทอม 1 มีกี่หน่วยกิต และมีวิชาอะไรบ้าง", good)
    assert r["sql"].startswith(good)                         # guard_sql ต่อท้าย LIMIT ให้ แต่ไม่ถูกแทนด้วยแม่แบบ


def test_template_fallback_does_not_touch_non_compound_questions(tmp_path, monkeypatch):
    sql = "SELECT credits FROM v_semester_credits WHERE year=2 AND semester=1"
    r = _ask_compound(tmp_path, monkeypatch, "ปี 2 เทอม 1 เรียนกี่หน่วยกิต", sql)
    assert r["sql"].startswith("SELECT credits FROM v_semester_credits") and "name_th" not in r["rows"][0]


# ---------- ช่องที่นักศึกษาเลือกเอง (plan_slot) ต่อท้ายคำตอบสรุปรายเทอม ----------
# n_courses นับช่องด้วย แต่ v_plan ไม่มีช่อง wildcard → "6 วิชา" ลิสต์ 5 ชื่อ ผู้ใช้สงสัยว่าอีกวิชาหายไปไหน

def _db_with_slot(path, extra_slot_in_other_term=True):
    c = _plan_db(path)
    c.executescript(m.PLAN_SLOT_DDL)
    c.execute("INSERT INTO plan_slot (program_id, year, semester, kind, code, name_th, credits) "
              "VALUES ('P', 2, 1, 'wildcard', '90644xxx', 'วิชาเลือกด้านภาษา', 3)")
    if extra_slot_in_other_term:
        c.execute("INSERT INTO plan_slot (program_id, year, semester, kind, code, name_th, credits) "
                  "VALUES ('P', 4, 2, 'choose_one', NULL, 'เลือกอย่างใดอย่างหนึ่ง', 6)")
    c.commit()
    return c


def _ask_compound_with_slots(tmp_path, monkeypatch, question, model_sql):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _db_with_slot(path).close()
    calls = []

    def fake(prompt, fmt=None, **kw):
        calls.append(prompt)
        return json.dumps({"sql": model_sql}) if len(calls) == 1 else json.dumps({"answer": "ok"})

    monkeypatch.setattr(m, "ollama_generate", fake)
    with closing(m.open_db(path, readonly=True)) as conn:
        return m.ask(conn, question, verbose=False)


def test_self_chosen_slot_is_listed_after_the_courses_of_a_compound_term_answer(tmp_path, monkeypatch):
    r = _ask_compound_with_slots(tmp_path, monkeypatch, "ปี 2 เทอม 1 มีกี่หน่วยกิต และมีวิชาอะไรบ้าง",
                                 "SELECT credits, n_courses FROM v_semester_credits WHERE year=2 AND semester=1")
    assert r["answer"].count("ช่องที่นักศึกษาเลือกเอง: วิชาเลือกด้านภาษา 3 หน่วยกิต") == 1
    assert "วิชาก" in r["answer"] and r["answer"].index("วิชาข") < r["answer"].index("ช่องที่นักศึกษาเลือกเอง")


def test_slots_of_other_terms_are_not_listed(tmp_path, monkeypatch):
    r = _ask_compound_with_slots(tmp_path, monkeypatch, "ปี 4 เทอม 2 มีกี่หน่วยกิต และมีวิชาอะไรบ้าง",
                                 "SELECT credits, n_courses FROM v_semester_credits WHERE year=4 AND semester=2")
    assert "วิชาเลือกด้านภาษา" not in r["answer"]


def test_slot_line_is_not_added_to_non_compound_answers(tmp_path, monkeypatch):
    r = _ask_compound_with_slots(tmp_path, monkeypatch, "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง",
                                 "SELECT name_th FROM v_plan WHERE year=2 AND semester=1")
    assert "ช่องที่นักศึกษาเลือกเอง" not in r["answer"]


def test_compound_answer_without_a_slot_table_is_unchanged(tmp_path, monkeypatch):
    r = _ask_compound(tmp_path, monkeypatch, "ปี 2 เทอม 1 มีกี่หน่วยกิต และมีวิชาอะไรบ้าง",
                      "SELECT credits, n_courses FROM v_semester_credits WHERE year=2 AND semester=1")
    assert "ช่องที่นักศึกษาเลือกเอง" not in r["answer"]


# ---------- ช่อง "เลือกเอง" ที่เล่มไม่ระบุรายชื่อ: หมวดศึกษาทั่วไป/ภาษาและการสื่อสาร (เลือกจากที่ สจล. เปิดสอน, ภาคผนวก ง)
# และวิชาเลือกเสรี — ตอบตามถ้อยคำเล่ม ไม่ลิสต์วิชารหัสขึ้นต้นเดียวกัน (รวมวิชาบังคับ/กลุ่มอื่นมั่ว ๆ) ----------

def _wildcard_db(path):
    c = _plan_db(path)
    c.executescript(m.PLAN_SLOT_DDL)
    c.executescript(m.COURSE_PAGE_DDL)
    c.executemany("INSERT INTO course (code, name_th, credits) VALUES (?, ?, 3)",
                  [("90644001", "ภาษาอังกฤษ 1"), ("90644002", "การนำเสนอ")])
    c.executemany("INSERT INTO plan_slot (program_id, year, semester, kind, code, name_th, credits) VALUES ('P', ?, ?, 'wildcard', ?, ?, 3)",
                  [(2, 1, "90644xxx", "วิชาเลือกด้านภาษาและการสื่อสาร"),
                   (3, 1, "9064xxxx", "วิชาเลือกหมวดวิชาศึกษาทั่วไป"),
                   (4, 1, "9064xxxx", "วิชาเลือกหมวดวิชาศึกษาทั่วไป"),
                   (4, 1, "xxxxxxx", "วิชาเลือกเสรี 1"),
                   (4, 1, "xxxxxxx", "วิชาเลือกเสรี 2"),
                   (3, 2, "06026xxx", "วิชาเลือกกลุ่มวิทยาการข้อมูล")])
    c.execute("INSERT INTO term_page VALUES (2, 1, 16, '15')")
    c.commit()
    return c


def _ask_wildcard(tmp_path, monkeypatch, question, model_sql="SELECT code, name_th FROM course WHERE 1 = 0"):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _wildcard_db(path).close()
    calls = []

    def fake(prompt, fmt=None, **kw):
        calls.append(prompt)
        return json.dumps({"sql": model_sql}) if len(calls) == 1 else json.dumps({"answer": "ok"})

    monkeypatch.setattr(m, "ollama_generate", fake)
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


@pytest.mark.parametrize("question", [
    "วิชาเลือกด้านภาษาและการสื่อสารมีวิชาอะไรให้เลือกบ้าง",
    "ปี 2 เทอม 1 ด้านภาษาและการสื่อสาร เลือกเรียนวิชาอะไรได้บ้าง",
])
def test_ge_slot_answers_as_the_book_does_without_listing_courses(tmp_path, monkeypatch, question):
    r = _ask_wildcard(tmp_path, monkeypatch, question)
    assert "ไม่ได้กำหนดรายวิชาตายตัว" in r["answer"] and "ภาคผนวก ง" in r["answer"] and "3 หน่วยกิต" in r["answer"]
    assert "ภาษาอังกฤษ 1" not in r["answer"] and "90644001" not in r["answer"]      # ไม่ลิสต์วิชารหัสขึ้นต้นเดียวกัน
    assert r["rows"] == [{"year": 2, "semester": 1, "slot": "วิชาเลือกด้านภาษาและการสื่อสาร",
                          "code_pattern": "90644xxx", "credits": 3}]
    assert r["model_calls"] == 0 and r["error"] is None


def test_ge_slot_answer_cites_the_plan_page_of_its_term(tmp_path, monkeypatch):
    r = _ask_wildcard(tmp_path, monkeypatch, "ปี 2 เทอม 1 วิชาเลือกด้านภาษาและการสื่อสารมีอะไรให้เลือกบ้าง")
    assert [c["pdf_page"] for c in r["citations"]] == [16]


def test_ge_slot_in_several_terms_names_each_term_unless_the_question_picks_one(tmp_path, monkeypatch):
    both = _ask_wildcard(tmp_path, monkeypatch, "วิชาเลือกหมวดวิชาศึกษาทั่วไป มีวิชาอะไรให้เลือกบ้าง")
    assert [(x["year"], x["semester"]) for x in both["rows"]] == [(3, 1), (4, 1)]
    assert "ปี 3 เทอม 1" in both["answer"] and "ปี 4 เทอม 1" in both["answer"]
    one = _ask_wildcard(tmp_path, monkeypatch, "ปี 4 เทอม 1 วิชาเลือกหมวดวิชาศึกษาทั่วไป มีวิชาอะไรให้เลือกบ้าง")
    assert [(x["year"], x["semester"]) for x in one["rows"]] == [(4, 1)]


def test_a_slot_named_in_full_in_the_question_is_the_only_one_answered(tmp_path, monkeypatch):
    r = _ask_wildcard(tmp_path, monkeypatch, "วิชาเลือกเสรี 2 เลือกวิชาอะไรได้บ้าง")
    assert [x["slot"] for x in r["rows"]] == ["วิชาเลือกเสรี 2"]
    generic = _ask_wildcard(tmp_path, monkeypatch, "วิชาเลือกเสรีเลือกวิชาอะไรได้บ้าง")
    assert [x["slot"] for x in generic["rows"]] == ["วิชาเลือกเสรี 1", "วิชาเลือกเสรี 2"]


def test_free_elective_answer_says_there_is_no_fixed_list(tmp_path, monkeypatch):
    r = _ask_wildcard(tmp_path, monkeypatch, "วิชาเลือกเสรี 1 เลือกวิชาอะไรได้บ้าง")
    assert "ไม่มีรายชื่อวิชากำหนด" in r["answer"] and "ที่เปิดสอนในสถาบัน" in r["answer"]
    assert r["model_calls"] == 0


@pytest.mark.parametrize("question", [
    "ปี 2 เทอม 1 วิชาเลือกด้านภาษาและการสื่อสารกี่หน่วยกิต",       # ถามหน่วยกิต ไม่ใช่รายชื่อ → ทางเดิม (โมเดล)
    "วิชาเลือกกลุ่มวิทยาการข้อมูลมีวิชาอะไรบ้าง",                    # ช่องที่มีแคตตาล็อกจริง → ทางเดิม
    "ภาษาและการสื่อสารมีวิชาอะไรบ้าง",                               # ไม่ได้ถามถึง "วิชาเลือก" → ทางเดิม
])
def test_questions_that_are_not_about_choosing_a_course_use_the_normal_path(tmp_path, monkeypatch, question):
    assert _ask_wildcard(tmp_path, monkeypatch, question)["model_calls"] >= 1


# ---------- เลขหน้าใน source ของแคตตาล็อกคือเลขหน้า PDF (ตัวคั่น "--- Page N ---") ไม่ใช่เลขที่พิมพ์ในเล่ม ----------

@pytest.mark.parametrize("path", sorted(RUNS.glob("*/electives.json")), ids=lambda p: p.parent.name)
def test_elective_catalog_source_says_the_pages_are_pdf_pages(path):
    source = json.loads(path.read_text(encoding="utf-8"))["source"]
    assert re.search(r"PDF หน้า \d+-\d+$", source), source


def test_the_extractor_writes_the_same_wording_so_a_rerun_keeps_it():
    src = (REPO / "Lab7B_Lab8B_ocr_system" / "src" / "ocr_system" / "extract_elective_catalog.py").read_text(encoding="utf-8")
    assert "PDF หน้า {args.start_page}-{args.end_page}" in src


# ---------- แคตตาล็อกหมวดวิชาศึกษาทั่วไป ฉบับ 2566 จาก PDF (text layer) ----------

import extract_elective_catalog as eec

GE_PDF = REPO / "data" / "input" / "GE66_Th_Ed240501.pdf"
GE_GT = REPO / "data" / "ground_truth" / "general_education_ground_truth.json"


def test_fix_pua_restores_thai_tone_marks():
    assert eec.fix_pua("ด\uf70bาน") == "ด้าน" and eec.fix_pua("กลุ\uf70aม") == "กลุ่ม"
    assert eec.fix_pua("ฟ\uf704\uf714น") == "ฟื้น" and eec.fix_pua("ฝ\uf703ก") == "ฝึก"
    assert eec.fix_pua("ไวยากรณ\uf70e") == "ไวยากรณ์"


def test_fix_pua_collapses_doubled_marks_both_kinds():
    assert eec.fix_pua("ขั\uf710้น") == "ขั้น"                 # อักขระเดี่ยวซ้ำ (หลังแปลง PUA)
    assert eec.fix_pua("ขั้ั้นสูง") == "ขั้นสูง"                # คู่ ั้ ซ้ำ — มาแบบนี้ใน PDF จริง (90642020)
    assert eec.fix_pua("สร\uf70bางสรรค\uf70e") == "สร้างสรรค์"   # ข้อความปกติไม่ถูกแตะ


@pytest.mark.skipif(not GE_PDF.exists(), reason="ไม่มี GE66 PDF")
def test_ge66_catalog_is_clean_complete_and_consistent_with_the_older_gt():
    courses = eec.parse_ge_pdf(GE_PDF)
    assert len(courses) >= 300
    assert not any(0xF700 <= ord(ch) <= 0xF7FF for c in courses for ch in c["name_th"] + c["name_en"])
    assert {c["group"] for c in courses} == {1, 2, 3, 4, 5}        # 5 = เรียนรู้ตลอดชีวิต (ภาคผนวก ฉ, เทียบโอน)
    gt = {c["code"]: c for c in json.loads(GE_GT.read_text(encoding="utf-8"))["courses"]}
    both = [c for c in courses if c["code"] in gt]
    assert len(both) >= 200
    assert all(re.sub(r"\s+", "", c["credit_text"]) == re.sub(r"\s+", "", gt[c["code"]]["credits"]) for c in both)
    assert sum(c["name_th"] == gt[c["code"]]["name_th"] for c in both) >= 185      # ที่เหลือส่วนใหญ่ GT พิมพ์ผิดเอง
    by_code = {c["code"]: c for c in courses}
    assert by_code["90641007"]["graded_su"] is True and by_code["90644009"]["group"] == 4


@pytest.mark.skipif(not GE_PDF.exists(), reason="ไม่มี GE66 PDF")
def test_build_ge_catalog_has_the_shape_the_elective_loader_expects():
    data = eec.build_ge_catalog(GE_PDF, "2566")
    assert data["plan_slot"] == "หมวดวิชาศึกษาทั่วไป ฉบับปรับปรุง พ.ศ. 2566" and data["program"] == "GE"
    assert [g["group_no"] for g in data["groups"]] == [1, 2, 3, 4, 5]
    assert sum(len(g["courses"]) for g in data["groups"]) == len(eec.parse_ge_pdf(GE_PDF))
    c = data["groups"][3]["courses"][0]
    assert set(c) >= {"code", "name_th", "name_en", "credits"} and re.match(r"\d+ \(\d+-\d+-\d+\)", c["credits"])
