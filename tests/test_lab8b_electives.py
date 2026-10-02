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
    plain = _prompts_for(tmp_path, monkeypatch, "หลักสูตรนี้ยากไหม")
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


# ---------- โหลดแคตตาล็อก GE 2566 เข้า DB (ไม่ลบวิชาเลือกเดิม ไม่โหลดให้ BIT) ----------

GE_SLOT = "หมวดวิชาศึกษาทั่วไป ฉบับปรับปรุง พ.ศ. 2566"
OWN_ELECTIVES = {"AIT": 16, "DSBA/coop": 43, "DSBA/no_coop": 43, "IT/coop": 53, "IT/no_coop": 53, "BIT/coop": 9, "BIT/no_coop": 9}


def test_the_pipeline_runner_loads_the_ge_catalog_and_skips_bit():
    src = (REPO / "Lab7B_Lab8B_ocr_system" / "run_lab8b.py").read_text(encoding="utf-8")
    assert "ge66_catalog.json" in src and 'rel.startswith("BIT")' in src


@pytest.mark.parametrize("rel", [r for r in ALL_DBS if not r.startswith("BIT")])
def test_ge_catalog_is_loaded_next_to_the_programs_own_electives(rel):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    with closing(m.open_db(db, readonly=True)) as conn:
        groups, n = conn.execute("SELECT COUNT(DISTINCT group_no), COUNT(*) FROM v_elective_group WHERE plan_slot = ?",
                                 (GE_SLOT,)).fetchone()
        own = conn.execute("SELECT COUNT(*) FROM v_elective_group WHERE plan_slot != ? AND plan_slot NOT LIKE 'หมวดวิชาศึกษาทั่วไป%'",
                           (GE_SLOT,)).fetchone()[0]
        credit_is_int = conn.execute("SELECT COUNT(*) FROM v_elective_group WHERE plan_slot = ? AND typeof(credits) != 'integer'",
                                     (GE_SLOT,)).fetchone()[0]
    assert (groups, n) == (5, 303) and credit_is_int == 0
    assert own == OWN_ELECTIVES[rel]                       # วิชาเลือกเดิมของหลักสูตรไม่หาย


@pytest.mark.parametrize("rel", ["BIT/coop", "BIT/no_coop"])
def test_bit_does_not_get_the_thai_ge_catalog(rel):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    with closing(m.open_db(db, readonly=True)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM v_elective_group WHERE plan_slot LIKE 'หมวดวิชาศึกษาทั่วไป%'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM v_elective_group").fetchone()[0] == OWN_ELECTIVES[rel]


# ---------- GE ไม่ปนกับ "วิชาเลือกของหลักสูตรนี้" (ความเสี่ยงข้อ 1) ----------

def _db_with_own_and_ge_electives(path):
    c = _make_db(path)                                        # วิชาเลือกของหลักสูตร 2 วิชา (06010001/2)
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) "
              "VALUES (2, 'P', ?, 24, 4, 'กลุ่มทักษะภาษาและการสื่อสาร')", (GE_SLOT,))
    c.executemany("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (2, ?, ?, 'X', 3)",
                  [("90644009", "ออกเสียงภาษาอังกฤษ"), ("90644010", "อ่านเขียนภาษาอังกฤษ")])
    c.commit()
    return c


def _ask_elective(tmp_path, monkeypatch, question, model_sql):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _db_with_own_and_ge_electives(path).close()
    calls = []

    def fake(prompt, fmt=None, **kw):
        calls.append(prompt)
        return json.dumps({"sql": model_sql}) if len(calls) == 1 else json.dumps({"answer": "ok"})

    monkeypatch.setattr(m, "ollama_generate", fake)
    with closing(m.open_db(path, readonly=True)) as conn:
        return m.ask(conn, question, verbose=False)


ALL_ELECTIVES_SQL = "SELECT group_no, group_name_th, code, course_name_th, credits FROM v_elective_group ORDER BY group_no, code"


def test_ge_rows_are_dropped_from_a_program_elective_question_even_if_the_model_ignores_the_hint(tmp_path, monkeypatch):
    r = _ask_elective(tmp_path, monkeypatch, "วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง", ALL_ELECTIVES_SQL)
    assert sorted(x["code"] for x in r["rows"]) == ["06010001", "06010002"]
    assert "90644009" not in r["answer"]


def test_ge_rows_stay_when_the_question_is_about_general_education(tmp_path, monkeypatch):
    r = _ask_elective(tmp_path, monkeypatch, "วิชาเลือกหมวดศึกษาทั่วไปในแคตตาล็อกมีอะไรบ้าง", ALL_ELECTIVES_SQL)
    assert {"90644009", "06010001"} <= {x["code"] for x in r["rows"]}


@pytest.mark.parametrize("rel,expected", [("AIT", 16), ("DSBA/coop", 43), ("IT/coop", 53)])
def test_real_databases_keep_the_program_elective_answer_free_of_ge(tmp_path, monkeypatch, rel, expected):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    monkeypatch.setattr(m, "ollama_generate", lambda prompt, fmt=None, **kw:
                        json.dumps({"sql": ALL_ELECTIVES_SQL}) if "sql" in (fmt or {}).get("properties", {}) else json.dumps({"answer": "ok"}))
    with closing(m.open_db(db, readonly=True)) as conn:
        r = m.ask(conn, "วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง", verbose=False)
    assert len({x["code"] for x in r["rows"]}) == expected and not any(x["code"].startswith("9064") for x in r["rows"])


def test_scoping_the_elective_view_does_not_leak_between_questions_on_one_connection(tmp_path):
    path = tmp_path / "t.db"
    _db_with_own_and_ge_electives(path).close()
    with closing(m.open_db(path, readonly=True)) as conn:
        count = lambda: conn.execute("SELECT COUNT(*) FROM v_elective_group").fetchone()[0]
        assert m.scope_elective_view(conn, "วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง") is True and count() == 2
        assert m.scope_elective_view(conn, "วิชาเลือกหมวดศึกษาทั่วไปมีอะไรบ้าง") is False and count() == 4
        assert m.scope_elective_view(conn, "วิชาเลือกที่หลักสูตรเปิดมีอะไรบ้าง") is True and count() == 2


# ---------- ช่อง GE/ภาษาฯ ตอบรายชื่อจริงจากแคตตาล็อก 2566 (ต้องมีแคตตาล็อกใน DB; ไม่มี = ข้อความระดับ 1 เดิม) ----------

def _db_with_ge_catalog(path, extra_language=0):
    c = _wildcard_db(path)
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) VALUES (20, 'P', ?, 24, 1, 'กลุ่มทักษะส่งเสริมอัตลักษณ์สถาบันฯ')", (GE_SLOT,))
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) VALUES (22, 'P', ?, 24, 2, 'กลุ่มทักษะบุคคลและส่งเสริมวิชาชีพ')", (GE_SLOT,))
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) VALUES (23, 'P', ?, 24, 3, 'กลุ่มทักษะการจัดการและภาวะความเป็นผู้นำ')", (GE_SLOT,))
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) VALUES (24, 'P', ?, 24, 4, 'กลุ่มทักษะภาษาและการสื่อสาร')", (GE_SLOT,))
    rows = [(20, "90641007", "พลเมืองดิจิทัล", 3), (22, "90642001", "ทักษะบุคคล", 3), (22, "90642002", "ทักษะบุคคลสอง", 2),
            (23, "90643001", "ภาวะผู้นำ", 3), (24, "90644001", "ปฏิบัติงานสื่อสาร 1", 1), (24, "90644003", "ปฏิบัติงานสื่อสาร 3", 3),
            (24, "90644009", "การออกเสียงภาษาอังกฤษ", 3), (24, "90644010", "การอ่านและเขียนภาษาอังกฤษ", 3)]
    rows += [(24, f"90644{100 + i}", f"วิชาภาษาเพิ่ม {i}", 3) for i in range(extra_language)]
    c.executemany("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (?, ?, ?, 'X', ?)", rows)
    # วิชาบังคับในแผนของหลักสูตร: 90644007 ไม่อยู่ในแคตตาล็อก (เหมือน DSBA/IT), 90644010 อยู่ในแคตตาล็อกแต่เป็นวิชาบังคับในแผน
    c.executemany("INSERT INTO course (code, name_th, credits) VALUES (?, ?, 3)",
                  [("90644007", "ภาษาอังกฤษพื้นฐาน 1"), ("90644010", "การอ่านและเขียนภาษาอังกฤษ")])
    c.executemany("INSERT INTO plan_item (program_id, year, semester, code, credits) VALUES ('P', 1, 1, ?, 3)",
                  [("90644007",), ("90644010",)])
    c.commit()
    return c


def _ask_with_catalog(tmp_path, monkeypatch, question, extra_language=0):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _db_with_ge_catalog(path, extra_language).close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


def test_language_slot_lists_the_catalog_pool_with_matching_credits_and_without_plan_required_courses(tmp_path, monkeypatch):
    r = _ask_with_catalog(tmp_path, monkeypatch, "วิชาเลือกด้านภาษาและการสื่อสารมีวิชาอะไรให้เลือกบ้าง")
    assert sorted(x["code"] for x in r["rows"]) == ["90644003", "90644009"]          # 3 หน่วยกิต กลุ่ม 4 ไม่รวม 1 หน่วยกิต/วิชาบังคับในแผน
    assert "พ.ศ. 2566" in r["answer"] and "2 วิชา" in r["answer"] and "90644009" in r["answer"]
    assert "บังคับในแผน" in r["answer"] and "90644007" in r["answer"] and "90644010" in r["answer"]
    assert "ภาคผนวก ง" not in r["answer"] and r["model_calls"] == 0                  # ไม่อ้างว่าตรงกับภาคผนวกในเล่ม (คนละฉบับ)


def test_ge_elective_slot_summarises_pool_per_group_and_leaves_out_the_identity_group(tmp_path, monkeypatch):
    r = _ask_with_catalog(tmp_path, monkeypatch, "ปี 3 เทอม 1 วิชาเลือกหมวดวิชาศึกษาทั่วไป มีวิชาอะไรให้เลือกบ้าง")
    assert sorted(x["code"] for x in r["rows"]) == ["90642001", "90643001", "90644003", "90644009"]
    assert "90641007" not in r["answer"] and "กลุ่มทักษะบุคคลและส่งเสริมวิชาชีพ 1 วิชา" in r["answer"]
    assert "กลุ่มทักษะภาษาและการสื่อสาร 2 วิชา" in r["answer"]


def test_long_pool_shows_at_most_eight_examples_but_all_rows(tmp_path, monkeypatch):
    r = _ask_with_catalog(tmp_path, monkeypatch, "วิชาเลือกด้านภาษาและการสื่อสารมีวิชาอะไรให้เลือกบ้าง", extra_language=12)
    assert len(r["rows"]) == 14 and "14 วิชา" in r["answer"]
    assert len(re.findall(r"90644\d{3}", r["answer"].split("บังคับในแผน")[0])) <= 8


def test_without_a_catalog_the_level_one_wording_is_kept(tmp_path, monkeypatch):
    r = _ask_wildcard(tmp_path, monkeypatch, "วิชาเลือกด้านภาษาและการสื่อสารมีวิชาอะไรให้เลือกบ้าง")
    assert "ไม่ได้กำหนดรายวิชาตายตัว" in r["answer"] and "ภาคผนวก ง" in r["answer"]


# ---------- ถามรายเทอม "ปี N เทอม M เลือกอะไรได้บ้าง": สรุปทุกช่องเลือกของเทอมนั้น ----------

def _db_for_term_choices(path):
    c = _db_with_ge_catalog(path)
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) VALUES (30, 'P', 'ช่องวิทยาการข้อมูล', 6, 1, 'กลุ่มวิทยาการข้อมูล')")
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) VALUES (31, 'P', 'ช่องวิทยาการข้อมูล', 6, 2, 'กลุ่มการวิเคราะห์เชิงสถิติ')")
    c.executemany("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (?, ?, ?, 'X', 3)",
                  [(30, "06026216", "ปัญญาประดิษฐ์"), (30, "06026217", "การเรียนรู้ของเครื่อง"), (31, "06026230", "อนุกรมเวลา")])
    c.execute("INSERT INTO plan_slot (id, program_id, year, semester, kind, code, name_th, credits) "
              "VALUES (50, 'P', 4, 2, 'choose_one', NULL, 'เลือกอย่างใดอย่างหนึ่ง (A หรือ B)', 6)")
    c.executemany("INSERT INTO course (code, name_th, credits) VALUES (?, ?, 6)", [("06026259", "สหกิจศึกษา"), ("06026260", "สหกิจศึกษาต่างประเทศ")])
    c.executemany("INSERT INTO plan_slot_member (slot_id, group_no, group_name, code) VALUES (50, 1, 'A หรือ B', ?)", [("06026259",), ("06026260",)])
    c.commit()
    return c


def _ask_term(tmp_path, monkeypatch, question):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _db_for_term_choices(path).close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT code FROM course LIMIT 1"}')
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


def test_term_choices_summarise_every_choice_slot_of_the_term(tmp_path, monkeypatch):
    r = _ask_term(tmp_path, monkeypatch, "ปี 4 เทอม 1 เลือกอะไรได้บ้าง")
    assert "วิชาเลือกหมวดวิชาศึกษาทั่วไป" in r["answer"] and "พ.ศ. 2566" in r["answer"]
    assert "วิชาเลือกเสรี 1" in r["answer"] and "วิชาเลือกเสรี 2" in r["answer"] and "ไม่มีรายชื่อวิชากำหนด" in r["answer"]
    assert [x["slot"] for x in r["rows"]] == ["วิชาเลือกหมวดวิชาศึกษาทั่วไป", "วิชาเลือกเสรี 1", "วิชาเลือกเสรี 2"]
    assert r["model_calls"] == 0 and "(อ้างอิง" not in r["answer"]


def test_term_choices_name_the_program_elective_groups_with_counts(tmp_path, monkeypatch):
    r = _ask_term(tmp_path, monkeypatch, "ปี 3 เทอม 2 วิชาเลือกมีอะไรให้เลือกบ้าง")
    assert "กลุ่มวิทยาการข้อมูล 2 วิชา" in r["answer"] and "กลุ่มการวิเคราะห์เชิงสถิติ 1 วิชา" in r["answer"]
    assert r["model_calls"] == 0


def test_term_choices_list_the_members_of_an_a_or_b_slot(tmp_path, monkeypatch):
    r = _ask_term(tmp_path, monkeypatch, "ปี 4 เทอม 2 เลือกเรียนอะไรได้บ้าง")
    assert "06026259 สหกิจศึกษา" in r["answer"] and "06026260 สหกิจศึกษาต่างประเทศ" in r["answer"] and "A หรือ B" in r["answer"]


@pytest.mark.parametrize("question", [
    "ปี 1 เทอม 1 เลือกอะไรได้บ้าง",                 # เทอมนี้ไม่มีช่องเลือก → ทางเดิม
    "ปี 4 เทอม 1 เลือกอะไรได้กี่หน่วยกิต",           # ถามจำนวน → ทางเดิม
    "ปี 4 เทอม 1 เรียนวิชาอะไรบ้าง",                 # ไม่ได้ถามถึง "เลือก" → ทางเดิม
])
def test_term_choices_do_not_hijack_other_questions(tmp_path, monkeypatch, question):
    assert _ask_term(tmp_path, monkeypatch, question)["model_calls"] >= 1


@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.name)
def test_no_gold_question_is_a_term_choices_question(path):
    for q in json.loads(path.read_text(encoding="utf-8")):
        assert not m._is_term_choices_question(q["question"]), q["question"]


# =============== รอบแก้หลังรีวิวทั้ง branch (C1, I1, I3, I4, M1–M5, M7) ===============

# ---- I2 (ตัดสินแล้ว ไม่แก้โค้ด): 90964xxx เป็นรหัสภาคผนวก ช สำหรับ "หลักสูตรปริญญาตรีต่อเนื่องเพื่อการเทียบโอน" ----
@pytest.mark.skipif(not GE_PDF.exists(), reason="ไม่มี GE66 PDF")
def test_continuing_degree_codes_90964xxx_are_deliberately_not_in_the_catalog():
    codes = {c["code"] for c in eec.parse_ge_pdf(GE_PDF)}
    assert codes and not any(c.startswith("90964") for c in codes)


# ---- C1: คำถามที่มีคำว่า "เลือก" แต่ไม่ได้ถามตัวเลือก ต้องไม่ถูกแย่งไปสรุปช่องเลือก ----
@pytest.mark.parametrize("question", [
    "ปี 4 เทอม 1 มีวิชาบังคับอะไรบ้าง ไม่รวมวิชาเลือก",
    "ปี 3 เทอม 1 มีวิชาอะไรบ้าง รวมวิชาเลือกด้วย",
    "ถ้าเลือกแผนสหกิจ ปี 4 เทอม 2 เรียนวิชาอะไรบ้าง",
    "ปี 3 เทอม 2 วิชาเลือกกลุ่มวิทยาการข้อมูลมีวิชาอะไรบ้าง",        # ระบุกลุ่มของหลักสูตร → ต้องให้ทางโมเดลลิสต์ชื่อวิชา
])
def test_term_choices_do_not_hijack_questions_that_only_mention_choosing(tmp_path, monkeypatch, question):
    assert _ask_term(tmp_path, monkeypatch, question)["model_calls"] >= 1


@pytest.mark.parametrize("question", ["ปี 4 เทอม 1 เลือกอะไรได้บ้าง", "ปี 4 เทอม 1 มีวิชาอะไรให้เลือกบ้าง", "ปี 4 เทอม 1 วิชาเลือกมีอะไรบ้าง",
                                       "ปี 4 เทอม 1 เลือกเรียนวิชาอะไรได้บ้าง"])
def test_term_choices_still_answer_the_real_choice_questions(question):
    assert m._is_term_choices_question(question)


# ---- I4: ถามช่องที่มีอยู่แต่ผิดเทอม → ตอบช่องนั้นพร้อมบอกเทอมจริง ไม่หลุดไปสรุปช่องอื่น ----
def test_a_named_slot_asked_in_the_wrong_term_is_answered_with_its_real_term(tmp_path, monkeypatch):
    r = _ask_with_catalog(tmp_path, monkeypatch, "ปี 3 เทอม 1 วิชาเลือกด้านภาษาและการสื่อสาร เลือกอะไรได้บ้าง")
    assert "ไม่มีช่องนี้ในปี 3 เทอม 1" in r["answer"] and "ปี 2 เทอม 1" in r["answer"] and "90644009" in r["answer"]
    assert r["model_calls"] == 0 and "กลุ่มวิทยาการข้อมูล" not in r["answer"]


# ---- I1: คำใบ้วิชาเลือก — ไม่มี NOT LIKE (TEMP VIEW กรองให้แล้ว) และมีคำใบ้ GE แยกเมื่อถามถึง GE; "GE" ต้องเป็นคำเดี่ยว ----
def test_elective_hint_has_no_redundant_ge_filter_and_a_separate_ge_variant(tmp_path):
    with closing(_db_with_own_and_ge_electives(tmp_path / "t.db")) as conn:
        plain = m._elective_hint_text(conn, "วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง")
        ge = m._elective_hint_text(conn, "วิชาเลือกกลุ่มภาษาและการสื่อสารมีกี่วิชา")
    assert "NOT LIKE" not in plain
    assert "plan_slot LIKE 'หมวดวิชาศึกษาทั่วไป%'" in ge and "group_no = 4" in ge and "COUNT(*)" in ge and "NOT LIKE" not in ge


def test_a_hint_following_model_gets_the_ge_rows_for_a_ge_count_question(tmp_path, monkeypatch):
    path = tmp_path / "t.db"
    _db_with_own_and_ge_electives(path).close()
    captured = {}

    def hint_following(prompt, fmt=None, **kw):                      # โมเดลที่ลอก SQL ตัวอย่างข้อ "นับ" จากคำใบ้ตรง ๆ
        if "sql" in (fmt or {}).get("properties", {}):
            line = next(l for l in prompt.splitlines() if l.startswith("- นับ"))
            captured["sql"] = line.split(": ", 1)[1].replace("<1-4>", "4")
            return json.dumps({"sql": captured["sql"]})
        return json.dumps({"answer": "ok"})

    monkeypatch.setattr(m, "ollama_generate", hint_following)
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, "วิชาเลือกกลุ่มภาษาและการสื่อสารมีกี่วิชา", verbose=False)
    assert r["error"] is None and r["rows"] and list(r["rows"][0].values())[0] == 2      # กลุ่ม 4 ในแคตตาล็อกทดสอบมี 2 วิชา


@pytest.mark.parametrize("question,hidden", [
    ("วิชาเลือก DIGITAL INTELLIGENCE มีอะไรบ้าง", True),          # INTELLIGENCE มีตัวอักษร GE แต่ไม่ใช่คำ GE (คำถามวิชาเลือก → ซ่อน GE)
    ("วิชาเลือก GE ของหลักสูตรนี้มีอะไรบ้าง", False),
    ("general education มีวิชาอะไรบ้าง", False),
    ("วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง", True),
])
def test_ge_term_detection_is_word_based(tmp_path, question, hidden):
    with closing(_db_with_own_and_ge_electives(tmp_path / "t.db")) as conn:
        assert m.scope_elective_view(conn, question) is hidden


def test_question_with_the_word_ge_reaches_the_ge_slot_shortcut(tmp_path, monkeypatch):
    r = _ask_with_catalog(tmp_path, monkeypatch, "วิชาเลือก GE ปี 3 เทอม 1 มีวิชาอะไรให้เลือกบ้าง")
    assert r["model_calls"] == 0 and "พ.ศ. 2566" in r["answer"]


# ---- I3: "หมวดวิชาศึกษาทั่วไปมีวิชาอะไรบ้าง" (ไม่มีคำว่าเลือก) → ภาพรวมของหมวดจากแผน + ช่องเลือก ----
def test_ge_category_question_gets_required_courses_and_choice_slots(tmp_path, monkeypatch):
    r = _ask_with_catalog(tmp_path, monkeypatch, "หมวดวิชาศึกษาทั่วไปมีวิชาอะไรบ้าง")
    assert "90644007" in r["answer"] and "บังคับ" in r["answer"]                      # วิชา GE ที่อยู่ในแผน
    assert "วิชาเลือกด้านภาษาและการสื่อสาร" in r["answer"] and "ปี 2 เทอม 1" in r["answer"]   # ช่องเลือก + เทอม
    assert {x["code"] for x in r["rows"] if x.get("code")} >= {"90644007", "90644010"} and r["model_calls"] == 0


@pytest.mark.parametrize("question", ["หมวดวิชาศึกษาทั่วไปต้องเรียนกี่หน่วยกิต", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง", "ศึกษาทั่วไปคืออะไร"])
def test_ge_category_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    assert _ask_with_catalog(tmp_path, monkeypatch, question)["model_calls"] >= 1


@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.name)
def test_no_gold_question_is_a_ge_category_question(path):
    for q in json.loads(path.read_text(encoding="utf-8")):
        assert not m._is_ge_category_question(q["question"]), q["question"]


# ---- M1: ไม่ให้หลุด exception เมื่อข้อมูลไม่ครบ (M2: plan_item.code เป็น NOT NULL ตามสคีมา จึงไม่เกิด; ใช้ NOT EXISTS อยู่ดี) ----
def test_ge_pool_survives_a_null_credit(tmp_path):
    c = _db_with_ge_catalog(tmp_path / "t.db")
    c.row_factory = sqlite3.Row                                                     # เหมือน open_db จริง
    assert m._ge_pool(c, "90644xxx", None) is None                                 # หน่วยกิตว่าง → ไม่มีคลัง ไม่ใช่ TypeError
    pool = m._ge_pool(c, "90644xxx", 3)
    assert pool and {r["code"] for r in pool[1]} == {"90644003", "90644009"}
    c.close()


def test_a_failure_inside_the_shortcuts_falls_back_to_the_normal_path(tmp_path, monkeypatch):
    path = tmp_path / "t.db"
    _db_with_ge_catalog(path).close()
    monkeypatch.setattr(m, "_open_slot_answer", lambda *a, **k: (_ for _ in ()).throw(TypeError("boom")))
    monkeypatch.setattr(m, "ollama_generate", lambda prompt, fmt=None, **kw:
                        json.dumps({"sql": "SELECT code FROM course LIMIT 1"}) if "sql" in (fmt or {}).get("properties", {}) else json.dumps({"answer": "ok"}))
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, "วิชาเลือกด้านภาษาและการสื่อสารมีวิชาอะไรให้เลือกบ้าง", verbose=False)
    assert r["error"] is None and r["rows"]


# ---- M3/M4: เลขหน้าอ้างอิงของคำตอบช่อง GE และ SQL ที่รันซ้ำได้ ----
def test_ge_pool_answer_still_cites_the_plan_page_of_its_term_and_returns_runnable_sql(tmp_path, monkeypatch):
    path = tmp_path / "t.db"
    _db_with_ge_catalog(path).close()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, "ปี 2 เทอม 1 วิชาเลือกด้านภาษาและการสื่อสารมีอะไรให้เลือกบ้าง", verbose=False)
        assert [c["pdf_page"] for c in r["citations"]] == [16]
        assert len(conn.execute(r["sql"]).fetchall()) == len(r["rows"])            # main.-qualified รันซ้ำได้ (แม้มี TEMP VIEW) และเป็นคำสั่งเดียว


def test_mixed_ge_and_free_answers_return_one_statement(tmp_path, monkeypatch):
    r = _ask_with_catalog(tmp_path, monkeypatch, "ปี 4 เทอม 1 วิชาเลือกศึกษาทั่วไปและวิชาเลือกเสรี เลือกอะไรได้บ้าง")
    assert r["sql"].count("SELECT") == 1 or "/*" in r["sql"]


# =============== แก้คำตอบที่ผิด/ปฏิเสธทั้งที่มีข้อมูล (ผลสำรวจ probe 62 ข้อ): ทางลัดเชิงกำหนดทั่วไป ===============
# ข้อมูลทดสอบ (คำนวณเฉลยมือได้): A แคลคูลัส 1 (ปี1/1) → B แคลคูลัส 2 (ปี1/2) · C ปฏิบัติการเครือข่าย (ปี2/1) → D โครงงาน (ปี2/2) · E สถิติ (ปี2/2)

def _q_db(path):
    c = _make_db(path, electives=False)
    c.executescript(m.PLAN_SLOT_DDL)
    courses = [("06020001", "แคลคูลัส 1", 3, 3, 0, 6), ("06020002", "แคลคูลัส 2", 3, 3, 0, 6),
               ("06020003", "ปฏิบัติการเครือข่าย", 3, 1, 4, 4), ("06020004", "โครงงาน", 3, 0, 9, 0), ("06020005", "สถิติ", 2, 2, 0, 4)]
    c.executemany("INSERT INTO course (code, name_th, name_en, credits, lecture_h, lab_h, self_h) VALUES (?, ?, 'EN', ?, ?, ?, ?)", courses)
    c.executemany("INSERT INTO plan_item (program_id, year, semester, code, credits) VALUES ('P', ?, ?, ?, ?)",
                  [(1, 1, "06020001", 3), (1, 2, "06020002", 3), (2, 1, "06020003", 3), (2, 2, "06020004", 3), (2, 2, "06020005", 2)])
    c.executemany("INSERT INTO prerequisite (code, requires, kind) VALUES (?, ?, 'pre')", [("06020002", "06020001"), ("06020004", "06020003")])
    # แคตตาล็อกวิชาเลือกของหลักสูตร + GE (ไม่อยู่ในตาราง course)
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) VALUES (40, 'P', 'ช่องวิทยาการข้อมูล', 6, 1, 'กลุ่มวิทยาการข้อมูล')")
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) VALUES (41, 'P', ?, 24, 4, 'กลุ่มทักษะภาษาและการสื่อสาร')", (GE_SLOT,))
    c.execute("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (40, '06026216', 'ปัญญาประดิษฐ์', 'ARTIFICIAL INTELLIGENCE', 3)")
    c.execute("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (41, '90644054', 'การอ่านและเขียนภาษาจีนพื้นฐาน', 'BASIC CHINESE', 3)")
    c.commit()
    return c


def _ask_q(tmp_path, monkeypatch, question, model_sql="SELECT 1"):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _q_db(path).close()
    calls = []

    def fake(prompt, fmt=None, **kw):
        calls.append(prompt)
        return json.dumps({"sql": model_sql}) if len(calls) == 1 else json.dumps({"answer": "ok"})

    monkeypatch.setattr(m, "ollama_generate", fake)
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


# ---- 1. วิชาที่ไม่มีวิชาบังคับก่อน (โมเดลเคยตอบ "0" และลิสต์ปนวิชาที่มี prereq) ----
def test_count_of_courses_without_prerequisites(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "มีกี่วิชาที่ไม่มีวิชาบังคับก่อน")
    assert "3 วิชา" in r["answer"] and r["model_calls"] == 0


def test_list_of_courses_without_prerequisites_excludes_those_that_have_one(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "วิชาไหนบ้างที่ไม่มีวิชาบังคับก่อน")
    codes = {x["code"] for x in r["rows"]}
    assert codes == {"06020001", "06020003", "06020005"} and "06020002" not in r["answer"]
    assert all(c in r["answer"] for c in codes) and r["model_calls"] == 0


@pytest.mark.parametrize("question", ["วิชา แคลคูลัส 2 ต้องเรียนวิชาอะไรมาก่อน", "วิชาที่ไม่ต้องเรียนแคลคูลัส 1 ก่อนมีอะไรบ้าง", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง"])
def test_no_prereq_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    assert not m._is_no_prereq_question(question) and _ask_q(tmp_path, monkeypatch, question)["model_calls"] >= 1


# ---- 2. กรองตามชั่วโมง (โมเดลเคยละเงื่อนไข → 36 วิชาแทน 5) ----
@pytest.mark.parametrize("question,expected", [
    ("วิชาที่มีชั่วโมงปฏิบัติมากกว่า 2 ชั่วโมงมีอะไรบ้าง", {"06020003", "06020004"}),
    ("วิชาที่มีชั่วโมงบรรยายน้อยกว่า 2 ชั่วโมงมีอะไรบ้าง", {"06020003", "06020004"}),
    ("วิชาที่ไม่มีชั่วโมงปฏิบัติมีอะไรบ้าง", {"06020001", "06020002", "06020005"}),
    ("วิชาที่มีชั่วโมงศึกษาด้วยตนเองเท่ากับ 6 ชั่วโมงมีอะไรบ้าง", {"06020001", "06020002"}),
    ("วิชาที่ชั่วโมงบรรยายไม่น้อยกว่า 3 ชั่วโมงมีวิชาอะไรบ้าง", {"06020001", "06020002"}),
    ("วิชาที่ชั่วโมงปฏิบัติไม่เกิน 4 ชั่วโมงมีวิชาอะไรบ้าง", {"06020001", "06020002", "06020003", "06020005"}),
])
def test_hours_filter_applies_the_operator_and_the_right_column(tmp_path, monkeypatch, question, expected):
    r = _ask_q(tmp_path, monkeypatch, question)
    assert {x["code"] for x in r["rows"]} == expected and r["model_calls"] == 0


@pytest.mark.parametrize("question", ["วิชา 06020003 มีชั่วโมงบรรยายกี่ชั่วโมง", "วิชา แคลคูลัส 1 มีชั่วโมงปฏิบัติกี่ชั่วโมง", "ชั่วโมงเรียนคืออะไร"])
def test_hours_filter_leaves_single_course_lookups_alone(question):
    assert m._hours_filter_spec(question) is None


# ---- 3. เทอม/ปีที่หน่วยกิตมากสุด-น้อยสุด (ต้องบอกเทอม) ----
def test_max_credit_term_names_the_term(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "เทอมไหนเรียนหน่วยกิตมากที่สุด")
    assert "ปี 2 เทอม 2" in r["answer"] and "5 หน่วยกิต" in r["answer"] and r["model_calls"] == 0


def test_min_credit_term_lists_every_tied_term(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "ภาคการศึกษาไหนเรียนหน่วยกิตน้อยที่สุด")
    assert all(t in r["answer"] for t in ("ปี 1 เทอม 1", "ปี 1 เทอม 2", "ปี 2 เทอม 1")) and "3 หน่วยกิต" in r["answer"]


def test_max_credit_year_and_year_scoped_term(tmp_path, monkeypatch):
    assert "ปี 2" in _ask_q(tmp_path, monkeypatch, "ปีไหนเรียนหน่วยกิตมากที่สุด")["answer"]
    assert "ปี 2 เทอม 2" in _ask_q(tmp_path, monkeypatch, "ปี 2 เทอมไหนเรียนหน่วยกิตมากที่สุด")["answer"]


@pytest.mark.parametrize("question", ["ปี 2 เทอม 1 เรียนกี่หน่วยกิต", "วิชาไหนมีหน่วยกิตมากที่สุด", "ปี 2 เทอม 1 มีวิชาอะไรบ้าง"])
def test_extreme_credit_shortcut_leaves_other_questions_alone(question):
    assert not m._is_extreme_credits_question(question)


# ---- 4. รหัสภายใน lab7b_alt_* ต้องไม่หลุดเข้าแถว/คำตอบ ----
def test_internal_alt_group_ids_never_reach_the_rows_or_the_answer(tmp_path, monkeypatch):
    c = sqlite3.connect(tmp_path / "t.db")
    c.close()
    r = _ask_q(tmp_path, monkeypatch, "ปี 1 เทอม 1 วิชาอะไรบ้าง",
               "SELECT code, name_th, 'lab7b_alt_61' AS alt_group FROM course WHERE code = '06020001'")
    assert all("lab7b" not in json.dumps(x, ensure_ascii=False) for x in r["rows"]) and "lab7b" not in r["answer"]
    assert r["rows"][0]["code"] == "06020001"


def test_alt_group_is_kept_when_it_is_the_only_column_asked_for():
    rows = [{"alt_group": "lab7b_alt_61"}]
    assert m._hide_internal_columns(rows) == rows                  # แถวจะว่างเปล่า → คงเดิมดีกว่าตอบว่าง


# ---- 5. ค้นวิชาในแคตตาล็อก (วิชาเลือก/GE) จากรหัสหรือชื่อ + ให้ค้นตามหัวข้อเห็น GE ----
def test_catalog_course_is_found_by_code_and_by_name(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "วิชา 06026216 ชื่ออะไร")
    assert "ปัญญาประดิษฐ์" in r["answer"] and r["model_calls"] == 0
    r = _ask_q(tmp_path, monkeypatch, "วิชา ปัญญาประดิษฐ์ กี่หน่วยกิต")
    assert "3 หน่วยกิต" in r["answer"] and r["model_calls"] == 0
    r = _ask_q(tmp_path, monkeypatch, "วิชา 06026216 ชื่อภาษาอังกฤษว่าอะไร")
    assert "ARTIFICIAL INTELLIGENCE" in r["answer"]
    r = _ask_q(tmp_path, monkeypatch, "90644054 คือวิชาอะไร อยู่กลุ่มไหน")
    assert "ภาษาจีน" in r["answer"] and "กลุ่มทักษะภาษาและการสื่อสาร" in r["answer"]


@pytest.mark.parametrize("question", ["วิชา 06020001 ชื่ออะไร", "วิชา แคลคูลัส 1 ยากไหม", "วิชา 99999999 ชื่ออะไร", "ปี 1 เทอม 1 เรียนอะไรบ้าง"])
def test_catalog_lookup_leaves_plan_courses_unknown_codes_and_other_questions_alone(tmp_path, monkeypatch, question):
    assert _ask_q(tmp_path, monkeypatch, question)["model_calls"] >= 1


@pytest.mark.parametrize("question,hidden", [
    ("มีวิชาภาษาจีนไหม", False),                          # ค้นตามหัวข้อต้องเห็นแคตตาล็อก GE
    ("วิชา 90644054 ชื่ออะไร", False),
    ("วิชา DIGITAL INTELLIGENCE QUOTIENT รหัสอะไร", False),
    ("วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง", True),          # ซ่อน GE เฉพาะคำถาม "วิชาเลือกของหลักสูตร"
    ("วิชาเลือกกลุ่มภาษาและการสื่อสารมีกี่วิชา", False),
])
def test_ge_catalog_is_hidden_only_for_program_elective_questions(tmp_path, question, hidden):
    with closing(_q_db(tmp_path / "t.db")) as conn:
        assert m.scope_elective_view(conn, question) is hidden


# ---- 6. วิชาบังคับก่อน + ปี/เทอมในคำถามเดียว (โมเดลเคย error "ไม่สามารถตอบ") ----
def test_courses_that_need_x_first_come_with_their_terms(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "วิชา แคลคูลัส 1 ต้องเรียนก่อนวิชาอะไร และวิชานั้นอยู่ปีไหน")
    assert "06020002" in r["answer"] and "ปี 1 เทอม 2" in r["answer"] and "06020004" not in r["answer"] and r["model_calls"] == 0


def test_prerequisites_of_x_come_with_their_terms(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "วิชา โครงงาน ต้องเรียนวิชาอะไรมาก่อน และวิชานั้นอยู่เทอมไหน")
    assert "06020003" in r["answer"] and "ปี 2 เทอม 1" in r["answer"] and r["model_calls"] == 0


def test_a_course_without_dependents_or_prerequisites_says_so(tmp_path, monkeypatch):
    assert "ไม่มี" in _ask_q(tmp_path, monkeypatch, "วิชา สถิติ ต้องเรียนวิชาอะไรมาก่อน และอยู่เทอมไหน")["answer"]


def test_term_listing_with_prerequisites(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "ปี 2 เทอม 2 มีวิชาอะไรบ้าง และวิชาไหนมีวิชาบังคับก่อน")
    assert "06020004" in r["answer"] and "06020005" in r["answer"] and "06020003" in r["answer"] and r["model_calls"] == 0


@pytest.mark.parametrize("question", ["วิชา แคลคูลัส 2 ต้องเรียนวิชาอะไรมาก่อน", "วิชา แคลคูลัส 1 ยากไหม", "ปี 2 เทอม 2 มีวิชาอะไรบ้าง"])
def test_prereq_term_shortcut_leaves_plain_questions_alone(tmp_path, monkeypatch, question):
    assert not m._is_prereq_term_question(question) and _ask_q(tmp_path, monkeypatch, question)["model_calls"] >= 1


# ---- ทุกทางลัดใหม่: ไม่มีคำถามในชุดเฉลย Lab 9 เข้าเงื่อนไข ----
@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.name)
def test_no_gold_question_hits_the_new_shortcuts(path):
    for q in json.loads(path.read_text(encoding="utf-8")):
        text = q["question"]
        assert not m._is_no_prereq_question(text), text
        assert m._hours_filter_spec(text) is None, text
        assert not m._is_extreme_credits_question(text), text
        assert not m._is_prereq_term_question(text), text


# ---- ข้อปรับหลัง probe รอบสอง ----
def test_count_question_for_courses_without_prerequisites_does_not_dump_the_list(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "มีกี่วิชาที่ไม่มีวิชาบังคับก่อน")
    assert "3 วิชา" in r["answer"] and "06020001" not in r["answer"] and len(r["rows"]) == 3      # "ไม่มีวิชา…" ไม่ใช่คำขอรายการ


def test_no_prereq_question_with_a_term_is_scoped_to_that_term(tmp_path, monkeypatch):
    r = _ask_q(tmp_path, monkeypatch, "ปี 2 เทอม 2 วิชาอะไรบ้างที่ไม่มีวิชาบังคับก่อน")
    assert {x["code"] for x in r["rows"]} == {"06020005"} and "ปี 2 เทอม 2" in r["answer"]


@pytest.mark.parametrize("question", ["มีวิชาภาษาจีนไหม", "มีวิชาปัญญาประดิษฐ์หรือไม่", "มีรายวิชาเกี่ยวกับเครือข่ายไหม"])
def test_topic_hint_covers_yes_no_existence_questions(tmp_path, question):
    with closing(_db_with_own_and_ge_electives(tmp_path / "t.db")) as conn:
        assert MARKER_TOPIC in m._topic_hint_text(conn, question)


@pytest.mark.parametrize("question", ["มีวิชาบังคับก่อนไหม", "มีวิชาเลือกไหม", "วิชา แคลคูลัส 1 มีวิชาบังคับก่อนหรือไม่", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง"])
def test_topic_hint_stays_silent_for_non_topic_existence_questions(tmp_path, question):
    with closing(_db_with_own_and_ge_electives(tmp_path / "t.db")) as conn:
        assert m._topic_hint_text(conn, question) == ""


@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.name)
def test_no_gold_question_gets_the_topic_hint(path):
    import sqlite3 as _s
    with closing(_s.connect(":memory:")) as conn:
        conn.executescript("CREATE TABLE course(code TEXT, name_th TEXT, name_en TEXT);")
        for q in json.loads(path.read_text(encoding="utf-8")):
            assert m._topic_hint_text(conn, q["question"]) == "", q["question"]


# =============== วิชาที่ "อ่านวิชาบังคับก่อนไม่ได้" ต้องไม่ถูกนับเป็น "ไม่มีวิชาบังคับก่อน" ===============
# load-prerequisites เติมแถวเฉพาะวิชาที่พบ; not_found/unreadable = ไม่มีแถวเหมือนกับ none → ต้องเก็บสถานะแยก (prerequisite_status)

def _q_db_with_status(path, statuses):
    c = _q_db(path)
    c.executescript(m.PREREQ_STATUS_DDL)
    c.executemany("INSERT INTO prerequisite_status (code, status) VALUES (?, ?)", list(statuses.items()))
    c.commit()
    return c


# A,C = none · B,D = found · E = not_found (อ่านไม่ได้)
_STATUS = {"06020001": "none", "06020002": "found", "06020003": "none", "06020004": "found", "06020005": "not_found"}


def _ask_status(tmp_path, monkeypatch, question):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _q_db_with_status(path, _STATUS).close()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(path, readonly=True)) as conn:
        return m.ask(conn, question, verbose=False)


def test_unreadable_courses_are_not_counted_as_having_no_prerequisite(tmp_path, monkeypatch):
    r = _ask_status(tmp_path, monkeypatch, "มีกี่วิชาที่ไม่มีวิชาบังคับก่อน")
    assert "2 วิชา" in r["answer"] and "อีก 1 วิชา" in r["answer"] and "ไม่ทราบ" in r["answer"]
    assert {x["code"] for x in r["rows"]} == {"06020001", "06020003"}


def test_list_names_the_unknown_courses_apart(tmp_path, monkeypatch):
    r = _ask_status(tmp_path, monkeypatch, "วิชาไหนบ้างที่ไม่มีวิชาบังคับก่อน")
    assert "06020001" in r["answer"] and "06020003" in r["answer"] and "06020005" in r["answer"].split("ไม่ทราบ")[-1]
    assert "06020005" not in {x["code"] for x in r["rows"]}


def test_prerequisite_term_answer_says_unknown_instead_of_none_for_unreadable_courses(tmp_path, monkeypatch):
    assert "ไม่ทราบ" in _ask_status(tmp_path, monkeypatch, "วิชา สถิติ ต้องเรียนวิชาอะไรมาก่อน และอยู่เทอมไหน")["answer"]
    r = _ask_status(tmp_path, monkeypatch, "วิชา แคลคูลัส 1 ต้องเรียนวิชาอะไรมาก่อน และอยู่เทอมไหน")
    assert "ไม่มีวิชาบังคับก่อน" in r["answer"]                      # สถานะ none = ยืนยันว่าไม่มี


def test_the_loader_records_a_status_for_every_course(tmp_path):
    import argparse
    path = tmp_path / "t.db"
    _q_db(path).close()
    book = tmp_path / "book.txt"
    book.write_text("--- Page 1 ---\n06020002 แคลคูลัส 2 3(3-0-6)\nวิชาบังคับก่อน : 06020001\n", encoding="utf-8")
    m.cmd_load_prerequisites(argparse.Namespace(database=str(path), text=str(book), output=None))
    with closing(sqlite3.connect(path)) as c:
        got = dict(c.execute("SELECT code, status FROM prerequisite_status").fetchall())
    assert set(got) == {"06020001", "06020002", "06020003", "06020004", "06020005"}
    assert got["06020002"] == "found" and set(got.values()) <= {"found", "none", "not_found", "unreadable"}


@pytest.mark.parametrize("rel,sure_none", [("DSBA/coop", 24), ("IT/coop", None)])
def test_real_database_statuses_match_the_extraction_report(rel, sure_none):
    import json as _j
    run = RUNS / rel / "lab8b_output"
    if not (run / "curriculum.db").exists():
        pytest.skip("ไม่มีไฟล์ DB")
    report = _j.loads((run / "prerequisites_report.json").read_text(encoding="utf-8"))["per_course"]
    with closing(sqlite3.connect(run / "curriculum.db")) as c:
        got = dict(c.execute("SELECT code, status FROM prerequisite_status").fetchall())
        plan = {r[0] for r in c.execute("SELECT code FROM plan_item")}
    assert got == {k: v["status"] for k, v in report.items()}
    if sure_none:
        assert sum(1 for k in plan if got.get(k) == "none") == sure_none


# =============== โครงสร้างหน่วยกิตต่อหมวด (ก. ศึกษาทั่วไป / ข. เฉพาะ / ค. เลือกเสรี และกลุ่มย่อย) จากส่วน 3.1.3 ของเล่ม ===============
# โมเดลเคยตอบ "6, 24" (หมวดเฉพาะ/เลือกเสรี) และ "99" ผิด; ตรวจความถูกต้องด้วยเลขคณิตของเล่มเอง: ผลรวมหมวดระดับบน = หน่วยกิตรวม

_BOOK_MARKED = """--- Page 1 ---
3.1.1 จํานวนหน่วยกิตรวมตลอดหลักสูตร 132 หน่วยกิต
3.1.2 โครงสร้างหลักสูตร
--- Page 2 ---
3.1.3 รายวิชา
ก. หมวดวิชาศึกษาทั่วไป                      30   หน่วยกิต
1) กลุ่มวิชาพื้นฐาน                           6   หน่วยกิต
2) กลุ่มวิชาด้านภาษาและการสื่อสาร              9   หน่วยกิต
3) กลุ่มวิชาตามเกณฑ์ของคณะ                    9   หน่วยกิต
4) กลุ่มวิชาเลือกหมวดวิชาการศึกษาทั่วไป        6   หน่วยกิต
--- Page 3 ---
ข. หมวดวิชาเฉพาะ                            96   หน่วยกิต
1) กลุ่มวิชาแกน                              45   หน่วยกิต
- กลุ่มคณิตศาสตร์และสถิติ                    15   หน่วยกิต
- กลุ่มพื้นฐานเทคโนโลยีสารสนเทศ              30   หน่วยกิต
2) กลุ่มวิชาพื้นฐานวิชาชีพ                    51   หน่วยกิต
--- Page 4 ---
ค. หมวดวิชาเลือกเสรี นักศึกษาสามารถเลือกเรียนในรายวิชาที่เปิดสอนในสถาบัน
ทหารลาดกระบัง จํานวนไม่น้อยกว่า 6 หน่วยกิต
"""

_BOOK_BARE_NOISY = """--- Page 1 ---
3.1.1 จ้านวนหน่วยกิตรวมตลอดหลักสูตร                       120 หน่วยกิต
3.1.2 โครงสร้างหลักสูตร
ก. หมวดวิชาศึกษาทั่วไป                           24 หหน่วยกิต
ข. หมวดวิชาเฉพาะ                                        90 หหน่วยกิต
กลุ่มวิชาพื้นฐานคณิตศาสตร์และสถิติ                    15 ใหน่วยกิต
กลุ่มวิชาพื้นฐานปัญญาประดิษฐ์                        75 ห+ขหน่วยกิต
ค. หมวดวิชาเลือกเสรี                                       6 หน่วยกิต
3.2 รายวิชา
กลุ่มวิชาตัวอย่างที่ไม่ใช่โครงสร้าง                 5 หน่วยกิต
"""

_BOOK_REPEATED = """--- Page 1 ---
3.3.1.1 จํานวนหน่วยกิตรวมตลอดหลักสูตร 129 หน่วยกิต
ก. หมวดวิชาศึกษาทั่วไป 30 หน่วยกิต
ข. หมวดวิชาเฉพาะ 93 หน่วยกิต
2) กลุ่มวิชาเฉพาะด้าน 87 หน่วยกิต
5) กลุ่มวิชาการศึกษาทางเลือก 6 หน่วยกิต
- สหกิจศึกษา 6 หน่วยกิต
ค. หมวดวิชาเลือกเสรี 6 หน่วยกิต
--- Page 9 ---
ก. หมวดวิชาศึกษาทั่วไป 30 หน่วยกิต
ข. หมวดวิชาเฉพาะ 93 หน่วยกิต
5) กลุ่มวิชาการศึกษาทางเลือก 6 หน่วยกิต
- วิชาสหกิจศึกษา 6 หน่วยกิต
"""


def test_parser_reads_marked_headings_into_a_tree_with_pages():
    total, nodes = m.parse_credit_structure(_BOOK_MARKED)
    assert total == 132
    by = {n["name_th"]: n for n in nodes}
    assert [by[k]["credits"] for k in ("หมวดวิชาศึกษาทั่วไป", "หมวดวิชาเฉพาะ", "หมวดวิชาเลือกเสรี")] == [30, 96, 6]
    assert by["กลุ่มวิชาแกน"]["parent"] == "หมวดวิชาเฉพาะ" and by["กลุ่มคณิตศาสตร์และสถิติ"]["parent"] == "กลุ่มวิชาแกน"
    assert by["หมวดวิชาเฉพาะ"]["pdf_page"] == 3 and by["กลุ่มวิชาพื้นฐาน"]["level"] == 2


def test_parser_reads_a_free_elective_heading_written_as_a_wrapped_sentence():
    _total, nodes = m.parse_credit_structure(_BOOK_MARKED)
    free = [n for n in nodes if n["name_th"] == "หมวดวิชาเลือกเสรี"]
    assert len(free) == 1 and free[0]["credits"] == 6 and free[0]["level"] == 1


def test_parser_tolerates_ocr_noise_and_unmarked_groups_inside_the_structure_block_only():
    total, nodes = m.parse_credit_structure(_BOOK_BARE_NOISY)
    by = {n["name_th"]: n for n in nodes}
    assert total == 120 and by["หมวดวิชาศึกษาทั่วไป"]["credits"] == 24 and by["หมวดวิชาเฉพาะ"]["credits"] == 90
    assert by["กลุ่มวิชาพื้นฐานคณิตศาสตร์และสถิติ"]["credits"] == 15 and by["กลุ่มวิชาพื้นฐานปัญญาประดิษฐ์"]["credits"] == 75
    assert "กลุ่มวิชาตัวอย่างที่ไม่ใช่โครงสร้าง" not in by                     # หลังจบส่วน 3.1.2 (เจอหัวข้อ 3.2) ไม่รับกลุ่มที่ไม่มีหมายเลข


def test_parser_keeps_the_first_occurrence_and_attaches_repeated_children_to_the_right_parent():
    _total, nodes = m.parse_credit_structure(_BOOK_REPEATED)
    assert [n["name_th"] for n in nodes if n["level"] == 1] == ["หมวดวิชาศึกษาทั่วไป", "หมวดวิชาเฉพาะ", "หมวดวิชาเลือกเสรี"]
    by = {n["name_th"]: n for n in nodes}
    assert by["วิชาสหกิจศึกษา"]["parent"] == "กลุ่มวิชาการศึกษาทางเลือก"        # อยู่หลัง 5) ของรอบที่สอง ไม่ใช่ใต้ ค.
    assert by["กลุ่มวิชาการศึกษาทางเลือก"]["parent"] == "หมวดวิชาเฉพาะ"


def _load_structure(tmp_path, text, total_credits=132):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=False)
    c.execute("UPDATE program SET total_credits = ?", (total_credits,))
    c.commit()
    stats = m.load_credit_structure(c, text)
    return c, stats


def test_loader_stores_the_tree_when_the_top_level_credits_add_up(tmp_path):
    c, stats = _load_structure(tmp_path, _BOOK_MARKED, 132)
    assert stats["loaded"] == len(c.execute("SELECT 1 FROM credit_structure").fetchall()) > 8
    assert c.execute("SELECT credits FROM credit_structure WHERE name_th = 'หมวดวิชาเฉพาะ'").fetchone()[0] == 96
    c.close()


def test_loader_refuses_a_structure_whose_top_level_does_not_add_up_to_the_total(tmp_path):
    c, stats = _load_structure(tmp_path, _BOOK_MARKED, 129)                   # เล่มบอกรวม 129 แต่หมวดรวมได้ 132 → อ่านพลาด ไม่โหลด
    assert stats["loaded"] == 0 and "ไม่ตรง" in stats["reason"]
    assert c.execute("SELECT COUNT(*) FROM credit_structure").fetchone()[0] == 0
    c.close()


def _ask_structure(tmp_path, monkeypatch, question, text=_BOOK_MARKED, total=132, load=True):
    path = tmp_path / "t.db"
    c, _ = _load_structure(tmp_path, text, total) if load else (_make_db(path, electives=False), None)
    c.commit()
    c.close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


@pytest.mark.parametrize("question,expect", [
    ("หมวดวิชาเฉพาะมีกี่หน่วยกิต", "96 หน่วยกิต"),
    ("หมวดวิชาศึกษาทั่วไปมีกี่หน่วยกิต", "30 หน่วยกิต"),
    ("วิชาเลือกเสรีต้องเรียนกี่หน่วยกิต", "6 หน่วยกิต"),
    ("กลุ่มวิชาแกนมีกี่หน่วยกิต", "45 หน่วยกิต"),
    ("กลุ่มวิชาด้านภาษาและการสื่อสารกี่หน่วยกิต", "9 หน่วยกิต"),
])
def test_category_credits_are_answered_from_the_book_structure(tmp_path, monkeypatch, question, expect):
    r = _ask_structure(tmp_path, monkeypatch, question)
    assert expect in r["answer"] and r["model_calls"] == 0


def test_a_category_answer_lists_its_sub_groups_and_the_page(tmp_path, monkeypatch):
    r = _ask_structure(tmp_path, monkeypatch, "หมวดวิชาเฉพาะประกอบด้วยอะไรบ้าง กี่หน่วยกิต")
    assert "กลุ่มวิชาแกน 45" in r["answer"] and "กลุ่มวิชาพื้นฐานวิชาชีพ 51" in r["answer"]
    assert all(x.get("pdf_page") for x in r["rows"])


def test_sub_group_names_the_parent_and_its_own_children(tmp_path, monkeypatch):
    r = _ask_structure(tmp_path, monkeypatch, "กลุ่มวิชาแกนมีอะไรบ้าง")
    assert "กลุ่มคณิตศาสตร์และสถิติ 15" in r["answer"] and "กลุ่มพื้นฐานเทคโนโลยีสารสนเทศ 30" in r["answer"]


def test_overview_question_lists_the_top_level_categories_and_the_total(tmp_path, monkeypatch):
    r = _ask_structure(tmp_path, monkeypatch, "โครงสร้างหลักสูตรแบ่งเป็นกี่หมวด")
    assert "3 หมวด" in r["answer"] and "หมวดวิชาเฉพาะ 96" in r["answer"] and "132" in r["answer"]


def test_a_structure_answer_cites_the_page_of_the_heading(tmp_path, monkeypatch):
    assert [c["pdf_page"] for c in _ask_structure(tmp_path, monkeypatch, "หมวดวิชาเฉพาะมีกี่หน่วยกิต")["citations"]] == [3]


@pytest.mark.parametrize("question", [
    "ปี 2 เทอม 1 เรียนกี่หน่วยกิต", "วิชา 06020001 ยากไหม", "วิชา แคลคูลัส 1 ยากไหม",
    "หมวดวิชาเฉพาะมีวิชาอะไรบ้าง", "ทั้งหลักสูตรมีกี่วิชา", "หลักสูตรนี้มีหน่วยกิตรวมเท่าไหร่"])
def test_structure_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    assert not m._is_credit_structure_question(question)


def test_empty_structure_refuses_instead_of_letting_the_model_guess(tmp_path, monkeypatch):
    r = _ask_structure(tmp_path, monkeypatch, "หมวดวิชาเฉพาะมีกี่หน่วยกิต", total=129)        # โหลดไม่ผ่าน → ตารางว่าง
    assert "ไม่มีข้อมูลโครงสร้างหน่วยกิต" in r["answer"] and r["model_calls"] == 0 and not any(c.isdigit() for c in r["answer"].split("ไม่มี")[0])


def test_database_without_the_structure_table_keeps_the_old_path(tmp_path, monkeypatch):
    assert _ask_structure(tmp_path, monkeypatch, "หมวดวิชาเฉพาะมีกี่หน่วยกิต", load=False)["model_calls"] >= 1


@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.name)
def test_no_gold_question_is_a_structure_question(path):
    for q in json.loads(path.read_text(encoding="utf-8")):
        assert not m._is_credit_structure_question(q["question"]), q["question"]


@pytest.mark.parametrize("rel,top,total", [
    ("DSBA/coop", {"หมวดวิชาศึกษาทั่วไป": 30, "หมวดวิชาเฉพาะ": 96, "หมวดวิชาเลือกเสรี": 6}, 132),
    ("DSBA/no_coop", {"หมวดวิชาศึกษาทั่วไป": 30, "หมวดวิชาเฉพาะ": 96, "หมวดวิชาเลือกเสรี": 6}, 132),
    ("AIT", {"หมวดวิชาศึกษาทั่วไป": 24, "หมวดวิชาเฉพาะ": 90, "หมวดวิชาเลือกเสรี": 6}, 120),
    ("IT/coop", {"หมวดวิชาศึกษาทั่วไป": 30, "หมวดวิชาเฉพาะ": 93, "หมวดวิชาเลือกเสรี": 6}, 129),
    ("IT/no_coop", {"หมวดวิชาศึกษาทั่วไป": 30, "หมวดวิชาเฉพาะ": 93, "หมวดวิชาเลือกเสรี": 6}, 129),
])
def test_real_databases_hold_the_structure_the_book_states(rel, top, total):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    with closing(sqlite3.connect(db)) as c:
        got = dict(c.execute("SELECT name_th, credits FROM credit_structure WHERE level = 1").fetchall())
    assert got == top and sum(got.values()) == total


# ---- ตัวตรวจต้องไม่ชนชื่อวิชาที่มีคำว่า "กลุ่ม" (ชุดเฉลย: "โครงงานกลุ่ม 3 กี่หน่วยกิต", "เทคโนโลยีกลุ่มเมฆ กี่หน่วยกิต") ----
@pytest.mark.parametrize("question", ["วิชาโครงงานกลุ่ม 3มีกี่หน่วยกิต", "เทคโนโลยีกลุ่มเมฆ กี่หน่วยกิต"])
def test_course_names_containing_the_word_group_are_not_structure_questions(tmp_path, monkeypatch, question):
    assert not m._is_credit_structure_question(question)
    assert _ask_structure(tmp_path, monkeypatch, question)["model_calls"] >= 1


def test_a_bare_group_name_from_the_structure_table_is_accepted_when_it_is_long_enough(tmp_path, monkeypatch):
    r = _ask_structure(tmp_path, monkeypatch, "กลุ่มคณิตศาสตร์และสถิติกี่หน่วยกิต")
    assert "15 หน่วยกิต" in r["answer"] and "(อยู่ในกลุ่มวิชาแกน)" in r["answer"] and r["model_calls"] == 0


@pytest.mark.parametrize("rel,gold", [("DSBA/coop", "dsba_coop"), ("DSBA/no_coop", "dsba_no_coop"), ("AIT", "ait"), ("IT/coop", "it_coop"),
                                       ("IT/no_coop", "it_no_coop"), ("BIT/coop", "bit_coop"), ("BIT/no_coop", "bit_no_coop")])
def test_no_gold_question_gets_a_structure_answer_on_its_own_database(rel, gold):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    qs = json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8"))
    with closing(m.open_db(db, readonly=True)) as conn:
        for q in qs:
            assert m._credit_structure_answer(conn, q["question"]) is None, q["question"]


# ---- ตรวจชั้นที่สอง: ผลรวมกลุ่มย่อยของแต่ละหมวด = หมวด (BIT: ข อ่านเป็น 96 แต่กลุ่มย่อยรวม 90 ผ่านชั้นแรกโดยบังเอิญ 30+96=126) ----
_BOOK_MISREAD = """--- Page 1 ---
3.1.1 จํานวนหน่วยกิตรวมตลอดหลักสูตร 126 หน่วยกิต
ก. หมวดวิชาศึกษาทั่วไป 30 หน่วยกิต
ข. หมวดวิชาเฉพาะ 96 หน่วยกิต
1) กลุ่มวิชาแกน 12 หน่วยกิต
2) กลุ่มวิชาเฉพาะด้าน 72 หน่วยกิต
3) กลุ่มวิชาเลือกทางเทคโนโลยีสารสนเทศ 6 หน่วยกิต
"""


def test_loader_refuses_when_the_sub_groups_do_not_add_up_to_their_category(tmp_path):
    c, stats = _load_structure(tmp_path, _BOOK_MISREAD, 126)
    assert stats["loaded"] == 0 and "กลุ่มย่อย" in stats["reason"] and c.execute("SELECT COUNT(*) FROM credit_structure").fetchone()[0] == 0
    c.close()


def test_loader_allows_an_alternative_group_counted_on_top_of_the_category(tmp_path):
    book = _BOOK_MARKED.replace("2) กลุ่มวิชาพื้นฐานวิชาชีพ                    51   หน่วยกิต",
                                "2) กลุ่มวิชาพื้นฐานวิชาชีพ                    51   หน่วยกิต\n3) กลุ่มวิชาการศึกษาทางเลือก                 6   หน่วยกิต")
    c, stats = _load_structure(tmp_path, book, 132)             # กลุ่มย่อยรวม 96 + 6 (ทางเลือก) = 102 ≠ 96 แต่ส่วนเกิน = กลุ่ม "ทางเลือก" → ยอม
    assert stats["loaded"] > 0
    c.close()


@pytest.mark.parametrize("rel", ["BIT/coop", "BIT/no_coop"])
def test_bit_structure_is_not_loaded_because_its_numbers_are_inconsistent(rel):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    with closing(sqlite3.connect(db)) as c:
        assert c.execute("SELECT COUNT(*) FROM credit_structure").fetchone()[0] == 0


def test_an_alternative_group_that_exceeds_the_category_total_is_annotated(tmp_path, monkeypatch):
    book = _BOOK_MARKED.replace("2) กลุ่มวิชาพื้นฐานวิชาชีพ                    51   หน่วยกิต",
                                "2) กลุ่มวิชาพื้นฐานวิชาชีพ                    51   หน่วยกิต\n3) กลุ่มวิชาการศึกษาทางเลือก                 6   หน่วยกิต")
    r = _ask_structure(tmp_path, monkeypatch, "หมวดวิชาเฉพาะมีกี่หน่วยกิต", text=book)
    assert "96 หน่วยกิต" in r["answer"] and "กลุ่มวิชาการศึกษาทางเลือก 6 ไม่นับรวมใน 96" in r["answer"]
    plain = _ask_structure(tmp_path, monkeypatch, "หมวดวิชาเฉพาะมีกี่หน่วยกิต")
    assert "ไม่นับรวม" not in plain["answer"]


# =============== คำอธิบายรายวิชา (ภาคผนวกของเล่ม: บรรทัดหัว "รหัส ชื่อ n(a-b-c)" / ชื่ออังกฤษ / วิชาบังคับก่อน / เนื้อหาไทย / เนื้อหาอังกฤษ) ===============
# ผล probe: "วิชา X เรียนเกี่ยวกับอะไร" ตอบเป็นรายการวิชา/ปฏิเสธ — DB ไม่มีคำอธิบายเลยทั้งที่เล่มมีครบ 150–250 วิชา

_BOOK_DESC = """--- Page 5 ---
06020001 แคลคูลัส 1 3(3-0-6)
CALCULUS 1
06020002 แคลคูลัส 2 3(3-0-6)
CALCULUS 2
--- Page 9 ---
5
มคอ. 2
06020001 แคลคูลัส 1 3(3-0-6)
CALCULUS 1
วิชาบังคับก่อน : ไม่มี
PREREQUISITE : None
ลิมิตและความต่อเนื่อง อนุพันธ์ของฟังก์ชัน
การประยุกต์ของอนุพันธ์ ปริพันธ์
Limits and continuity, derivatives of functions,
applications of derivatives, integration.
06020002 แคลคูลัส 2 3(3-0-6)
CALCULUS 2
วิชาบังคับก่อน : 06020001 แคลคูลัส 1
PREREQUISITE : 06020001 CALCULUS 1
ลําดับและอนุกรม ปริพันธ์หลายชั้น
Sequences and series, multiple integrals.
06020003 สั้นมาก 1(1-0-2)
SHORT
วิชาบังคับก่อน : ไม่มี
PREREQUISITE : None
--- Page 10 ---
06020004 วิชาที่มีแต่ภาษาอังกฤษ 3(3-0-6)
ENGLISH ONLY
วิชาบังคับก่อน : ไม่มี
PREREQUISITE : None
This course introduces the basics of probability and statistics for engineers and scientists.
"""


def test_description_parser_uses_the_appendix_block_and_splits_thai_from_english():
    got = {d["code"]: d for d in m.parse_course_descriptions(_BOOK_DESC)}
    d = got["06020001"]
    assert d["description_th"] == "ลิมิตและความต่อเนื่อง อนุพันธ์ของฟังก์ชัน การประยุกต์ของอนุพันธ์ ปริพันธ์"
    assert d["description_en"].startswith("Limits and continuity") and d["description_en"].endswith("integration.")
    assert d["pdf_page"] == 9 and d["name_th"] == "แคลคูลัส 1"                      # ไม่ใช่รายการวิชาหน้า 5 (ไม่มีหัวข้อวิชาบังคับก่อน)
    assert "PREREQUISITE" not in d["description_en"] and "วิชาบังคับก่อน" not in d["description_th"]


def test_description_parser_keeps_english_only_courses_and_drops_empty_ones():
    got = {d["code"]: d for d in m.parse_course_descriptions(_BOOK_DESC)}
    assert got["06020004"]["description_th"] == "" and got["06020004"]["description_en"].startswith("This course introduces")
    assert "06020003" not in got                                                   # ไม่มีเนื้อหาเลย


def _desc_db(tmp_path, with_table=True):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=False)
    c.executemany("INSERT INTO course (code, name_th, name_en, credits) VALUES (?, ?, 'EN', 3)",
                  [("06020001", "แคลคูลัส 1"), ("06020002", "แคลคูลัส 2"), ("06020009", "วิชาไม่มีคำอธิบาย")])
    if with_table:
        stats = m.load_course_descriptions(c, _BOOK_DESC)
        assert stats["loaded"] == 3
    c.commit()
    return c


def test_loader_is_idempotent_and_records_pages(tmp_path):
    c = _desc_db(tmp_path)
    assert m.load_course_descriptions(c, _BOOK_DESC)["loaded"] == 3
    assert c.execute("SELECT COUNT(*) FROM course_description").fetchone()[0] == 3
    assert c.execute("SELECT pdf_page FROM course_description WHERE code='06020002'").fetchone()[0] == 9
    c.close()


def _ask_desc(tmp_path, monkeypatch, question, with_table=True):
    _desc_db(tmp_path, with_table).close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


@pytest.mark.parametrize("question", [
    "วิชา 06020001 เรียนเกี่ยวกับอะไร", "วิชา แคลคูลัส 1 เรียนเกี่ยวกับอะไร", "คำอธิบายรายวิชา แคลคูลัส 1 คืออะไร",
    "แคลคูลัส 1 สอนอะไรบ้าง", "ขอเนื้อหาวิชา 06020001 หน่อย"])
def test_course_description_is_answered_from_the_book_text(tmp_path, monkeypatch, question):
    r = _ask_desc(tmp_path, monkeypatch, question)
    assert "ลิมิตและความต่อเนื่อง" in r["answer"] and "Limits and continuity" in r["answer"] and r["model_calls"] == 0
    assert [c["pdf_page"] for c in r["citations"]] == [9]


def test_english_description_is_used_when_the_thai_one_is_missing(tmp_path, monkeypatch):
    r = _ask_desc(tmp_path, monkeypatch, "วิชา 06020004 เรียนเกี่ยวกับอะไร")
    assert "introduces the basics of probability" in r["answer"] and r["model_calls"] == 0


def test_a_known_course_without_a_description_says_so_instead_of_guessing(tmp_path, monkeypatch):
    r = _ask_desc(tmp_path, monkeypatch, "วิชา วิชาไม่มีคำอธิบาย เรียนเกี่ยวกับอะไร")
    assert "ไม่พบคำอธิบายรายวิชา" in r["answer"] and r["model_calls"] == 0


@pytest.mark.parametrize("question", [
    "วิชา 06020001 ชื่ออะไร", "วิชา แคลคูลัส 1 ยากไหม", "ปี 2 เทอม 1 เรียนอะไรบ้าง", "หลักสูตรนี้เกี่ยวกับอะไร",
    "วิชา 99999999 เรียนเกี่ยวกับอะไร"])
def test_description_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    assert _ask_desc(tmp_path, monkeypatch, question)["model_calls"] >= 1


def test_database_without_the_description_table_keeps_the_old_path(tmp_path, monkeypatch):
    assert _ask_desc(tmp_path, monkeypatch, "วิชา แคลคูลัส 1 เรียนเกี่ยวกับอะไร", with_table=False)["model_calls"] >= 1


@pytest.mark.parametrize("rel,gold", [("DSBA/coop", "dsba_coop"), ("DSBA/no_coop", "dsba_no_coop"), ("AIT", "ait"), ("IT/coop", "it_coop"),
                                       ("IT/no_coop", "it_no_coop"), ("BIT/coop", "bit_coop"), ("BIT/no_coop", "bit_no_coop")])
def test_no_gold_question_gets_a_description_answer_on_its_own_database(rel, gold):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    qs = json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8"))
    with closing(m.open_db(db, readonly=True)) as conn:
        for q in qs:
            assert m._course_description_answer(conn, q["question"]) is None, q["question"]


@pytest.mark.parametrize("rel,plan_min,elective_min", [("DSBA/coop", 0.85, 0.95), ("DSBA/no_coop", 0.85, 0.95), ("AIT", 0.9, 0.95),
                                                         ("IT/coop", 0.75, 0.95), ("IT/no_coop", 0.75, 0.95)])
def test_real_databases_hold_descriptions_for_most_plan_and_elective_courses(rel, plan_min, elective_min):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    with closing(sqlite3.connect(db)) as c:
        have = {r[0] for r in c.execute("SELECT code FROM course_description WHERE length(coalesce(description_th,'')) + length(coalesce(description_en,'')) > 40")}
        plan = {r[0] for r in c.execute("SELECT DISTINCT code FROM plan_item")}
        elect = {r[0] for r in c.execute("SELECT DISTINCT code FROM v_elective_group WHERE plan_slot NOT LIKE 'หมวดวิชาศึกษาทั่วไป%'")}
    assert len(plan & have) / len(plan) >= plan_min and len(elect & have) / len(elect) >= elective_min


def test_dsba_description_text_matches_the_book():
    db = RUNS / "DSBA/coop" / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    with closing(sqlite3.connect(db)) as c:
        th, en = c.execute("SELECT description_th, description_en FROM course_description WHERE code = '06026206'").fetchone()
    assert th.startswith("ในภาคทฤษฎี แนะนํา") and "Introduction to business data analytics" in en


# =============== หัวข้อเล่ม มคอ.2 (ชื่อหลักสูตร/ปริญญา/อาชีพ/ปรัชญา/วัตถุประสงค์/คุณสมบัติ/เกณฑ์จบ) — ยกข้อความตามเล่ม ===============
# OCR เพี้ยนวรรณยุกต์/สระ (ชือ, ซือ, สําเร็จ) และมีเศษขยะหน้ากระดาษ → ต้องจับหัวข้อแบบทนเสียงรบกวน ตัดที่หัวข้อถัดไป ไม่เอาสารบัญ

_BOOK_SEC = """--- Page 1 ---
สารบัญ
1. ชื่อหลักสูตร 1
2. ชื่อปริญญาและสาขาวิชา 1
8. อาชีพที่สามารถประกอบได้หลังสําเร็จการศึกษา 7
--- Page 2 ---
1
มคอ. 2
หมวดที 1 ข้อมูลทัวไป
1. ชือหลักสูตร
ขือภาษาไทย หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาตัวอย่าง
ขื่อภาษาอังกฤษ Bachelor of Science Program in Example
2. ซือปริญญาและสาขาวิชา
Youu (ภาษาไทย) : วิทยาศาสตรบัณฑิต (ตัวอย่าง)
(ภาษาอังกฤษ) : Bachelor of Science (Example)
3. วิชาเอก
ไม่มี
วท.บ (ตัวอย่าง) สาขาวิชาตัวอย่าง
คณะตัวอย่าง สจล.
--- Page 3 ---
2
มคอ. 2
8. อาชีพที่สามารถประกอบได้หลังสําเร็จการศึกษา
1) นักวิทยาการข้อมูล (Data Scientist)
[ๆ 2) นักวิเคราะห์ข้อมูล (Data Analyst)
a   a
วท.บ (ตัวอย่าง) สาขาวิชาตัวอย่าง
คณะตัวอย่าง สจล.
--- Page 4 ---
3
มคอ. 2
3) นักพัฒนาระบบ (System Developer)
9. สถานที่จัดการเรียนการสอน
ในสถานที่ตั้งสถาบันเทคโนโลยีตัวอย่าง
1. ปรัชญา ความสําคัญ และวัตถุประสงค์ของหลักสูตร
1.1 ปรัชญา
ข้อมูลและสารสนเทศมีบทบาทสําคัญ
1.2 ความสําคัญ
ไม่ควรอยู่ในคําตอบ
1.3 วัตถุประสงค์
1) เพื่อผลิตบัณฑิตที่มีความรู้
2) เพื่อพัฒนางานวิจัย
2.2 คุณสมบัติของผู้เข้าศึกษา
สําเร็จการศึกษาระดับมัธยมศึกษาตอนปลายหรือเทียบเท่า
2.3 ปัญหาของนักศึกษาแรกเข้า
ไม่ควรอยู่ในคําตอบ
วท.บ (ตัวอย่าง) สาขาวิชาตัวอย่าง
คณะตัวอย่าง สจล.
--- Page 5 ---
4
มคอ. 2
3. เกณฑ์การสําเร็จการศึกษาตามหลักสูตร
เป็นไปตามข้อบังคับสถาบัน
4. การลงทะเบียน
ไม่ควรอยู่ในคําตอบ
วท.บ (ตัวอย่าง) สาขาวิชาตัวอย่าง
คณะตัวอย่าง สจล.
"""


def _sec(text=_BOOK_SEC):
    return {d["topic"]: d for d in m.parse_book_sections(text)}


def test_sections_ignore_the_table_of_contents_and_tolerate_ocr_marks():
    got = _sec()
    assert got["ชื่อหลักสูตร"]["pdf_page"] == 2 and "Bachelor of Science Program in Example" in got["ชื่อหลักสูตร"]["body"]
    assert got["ชื่อปริญญา"]["body"].startswith("(ภาษาไทย) : วิทยาศาสตรบัณฑิต (ตัวอย่าง)")      # ตัดคำขยะหน้าวงเล็บ "Youu"
    assert "วิชาเอก" not in got["ชื่อปริญญา"]["body"]                                           # หยุดที่หัวข้อถัดไป
    assert "สารบัญ" not in got["ชื่อหลักสูตร"]["body"]


def test_sections_join_across_pages_and_drop_page_furniture():
    body = _sec()["อาชีพ"]["body"]
    assert body.index("Data Scientist") < body.index("Data Analyst") < body.index("System Developer")   # ต่อข้ามหน้า
    assert "ตัวอย่าง สจล." not in body and "มคอ" not in body and "[ๆ" not in body and "สาขาวิชาตัวอย่าง" not in body
    assert _sec()["อาชีพ"]["pdf_page"] == 3


def test_sections_stop_at_the_next_heading_and_prefer_the_exact_heading():
    got = _sec()
    assert got["ปรัชญา"]["body"] == "ข้อมูลและสารสนเทศมีบทบาทสําคัญ"
    assert got["วัตถุประสงค์"]["body"] == "1) เพื่อผลิตบัณฑิตที่มีความรู้ 2) เพื่อพัฒนางานวิจัย"
    assert got["คุณสมบัติผู้เข้าศึกษา"]["body"] == "สําเร็จการศึกษาระดับมัธยมศึกษาตอนปลายหรือเทียบเท่า"
    assert got["เกณฑ์สำเร็จการศึกษา"]["body"] == "เป็นไปตามข้อบังคับสถาบัน"
    assert got["สถานที่จัดการเรียนการสอน"]["body"] == "ในสถานที่ตั้งสถาบันเทคโนโลยีตัวอย่าง"


def test_section_body_is_capped_at_a_line_boundary():
    long_book = "--- Page 1 ---\n1. ปรัชญา\n" + "\n".join(f"บรรทัดที่ {i} " + "ก" * 60 for i in range(60)) + "\n"
    body = _sec(long_book)["ปรัชญา"]["body"]
    assert 400 < len(body) <= m._SECTION_MAX_CHARS and body.endswith("ก") and "บรรทัดที่ 59" not in body


def _sec_db(tmp_path, with_table=True):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=False)
    if with_table:
        assert m.load_book_sections(c, _BOOK_SEC)["loaded"] == 8
    c.commit()
    return c


def test_section_loader_is_idempotent(tmp_path):
    c = _sec_db(tmp_path)
    assert m.load_book_sections(c, _BOOK_SEC)["loaded"] == 8
    assert c.execute("SELECT COUNT(*) FROM book_section").fetchone()[0] == 8
    c.close()


def _ask_sec(tmp_path, monkeypatch, question, with_table=True):
    _sec_db(tmp_path, with_table).close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


@pytest.mark.parametrize("question,needle,page", [
    ("หลักสูตรนี้ชื่ออะไร", "Bachelor of Science Program in Example", 2),
    ("จบแล้วได้รับปริญญาอะไร", "วิทยาศาสตรบัณฑิต (ตัวอย่าง)", 2),
    ("ชื่อปริญญาและสาขาวิชาคืออะไร", "Bachelor of Science (Example)", 2),
    ("จบแล้วประกอบอาชีพอะไรได้บ้าง", "Data Scientist", 3),
    ("อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษามีอะไรบ้าง", "System Developer", 3),
    ("ปรัชญาของหลักสูตรคืออะไร", "ข้อมูลและสารสนเทศมีบทบาทสําคัญ", 4),
    ("วัตถุประสงค์ของหลักสูตรคืออะไร", "เพื่อผลิตบัณฑิตที่มีความรู้", 4),
    ("คุณสมบัติของผู้เข้าศึกษามีอะไรบ้าง", "มัธยมศึกษาตอนปลาย", 4),
    ("ใครสมัครเรียนหลักสูตรนี้ได้บ้าง", "มัธยมศึกษาตอนปลาย", 4),
    ("เกณฑ์การสำเร็จการศึกษาคืออะไร", "ข้อบังคับสถาบัน", 5),
    ("สถานที่จัดการเรียนการสอนอยู่ที่ไหน", "สถาบันเทคโนโลยีตัวอย่าง", 4)])
def test_book_sections_are_answered_from_the_book_text(tmp_path, monkeypatch, question, needle, page):
    r = _ask_sec(tmp_path, monkeypatch, question)
    assert needle in r["answer"] and r["model_calls"] == 0
    assert [c["pdf_page"] for c in r["citations"]] == [page]


def test_a_missing_topic_is_reported_not_guessed(tmp_path, monkeypatch):
    _sec_db(tmp_path).close()
    with closing(sqlite3.connect(tmp_path / "t.db")) as c:
        c.execute("DELETE FROM book_section WHERE topic = 'อาชีพ'")
        c.commit()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, "จบแล้วประกอบอาชีพอะไรได้บ้าง", verbose=False)
    assert "ไม่พบ" in r["answer"] and "อาชีพ" in r["answer"]


@pytest.mark.parametrize("question", [
    "วิชา 06020001 ชื่ออะไร", "วิชา แคลคูลัส 1 ยากไหม", "ปี 2 เทอม 1 เรียนอะไรบ้าง", "วิชาเลือกมีกี่หน่วยกิต",
    "หมวดวิชาเฉพาะมีกี่หน่วยกิต"])
def test_section_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    assert _ask_sec(tmp_path, monkeypatch, question)["model_calls"] >= 1


def test_database_without_the_section_table_keeps_the_old_path(tmp_path, monkeypatch):
    assert _ask_sec(tmp_path, monkeypatch, "ปรัชญาของหลักสูตรคืออะไร", with_table=False)["model_calls"] >= 1


@pytest.mark.parametrize("rel,gold", [("DSBA/coop", "dsba_coop"), ("DSBA/no_coop", "dsba_no_coop"), ("AIT", "ait"), ("IT/coop", "it_coop"),
                                       ("IT/no_coop", "it_no_coop"), ("BIT/coop", "bit_coop"), ("BIT/no_coop", "bit_no_coop")])
def test_no_gold_question_gets_a_section_answer_on_its_own_database(rel, gold):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    qs = json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8"))
    with closing(m.open_db(db, readonly=True)) as conn:
        for q in qs:
            assert m._book_section_answer(conn, q["question"]) is None, q["question"]


@pytest.mark.parametrize("rel,min_topics", [("DSBA/coop", 7), ("DSBA/no_coop", 7), ("AIT", 7), ("IT/coop", 7), ("IT/no_coop", 7), ("BIT/coop", 7), ("BIT/no_coop", 7)])
def test_real_databases_hold_most_book_sections(rel, min_topics):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    with closing(sqlite3.connect(db)) as c:
        rows = {r[0]: r[1] for r in c.execute("SELECT topic, body FROM book_section")}
    assert len(rows) >= min_topics and all(len(b) >= 10 for b in rows.values())


def test_a_heading_with_a_doubled_ocr_letter_is_still_found():
    book = "--- Page 1 ---\n2. ชซือปริญญาและสาขาวิชา\n(ภาษาไทย) : วิทยาศาสตรบัณฑิต (ตัวอย่าง)\n3. วิชาเอก\nไม่มี\n"
    assert "วิทยาศาสตรบัณฑิต" in _sec(book)["ชื่อปริญญา"]["body"]


def test_a_course_name_containing_a_topic_word_is_not_taken_for_a_section_question(tmp_path, monkeypatch):
    _sec_db(tmp_path).close()
    with closing(sqlite3.connect(tmp_path / "t.db")) as c:
        c.execute("INSERT INTO course (code, name_th, name_en, credits) VALUES ('06020077', 'ปรัชญาของการเป็นมืออาชีพ', 'EN', 3)")
        c.commit()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        assert m._book_section_answer(conn, "วิชาปรัชญาของการเป็นมืออาชีพมีกี่หน่วยกิต") is None
        assert m._book_section_answer(conn, "จบแล้วประกอบอาชีพอะไรได้บ้าง") is not None


@pytest.mark.parametrize("question", ["ใครสามารถสมัครเรียนหลักสูตรนี้ได้", "ใครสามารถเข้าเรียนหลักสูตรนี้ได้บ้าง", "ใครเรียนหลักสูตรนี้ได้"])
def test_who_can_apply_phrasings_reach_the_admission_section(tmp_path, monkeypatch, question):
    r = _ask_sec(tmp_path, monkeypatch, question)
    assert "มัธยมศึกษาตอนปลาย" in r["answer"] and r["model_calls"] == 0


# =============== "ขอรหัสวิชา <ชื่อวิชา>" — หาจากชื่อ (ไทย/อังกฤษ) ใน DB แบบกำหนดตายตัว ===============
# ผลเทสต์ซ้ำ: คำถามนี้โมเดลสุ่มเขียน SQL ผิดตาราง (prerequisite) ถูกแค่ ~1 ใน 6 ครั้ง ทั้งที่ชื่อวิชามีใน DB


def _code_db(tmp_path):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path)
    c.executemany("INSERT INTO course (code, name_th, name_en, credits) VALUES (?, ?, ?, 3)",
                  [("06020001", "แคลคูลัส 1", "CALCULUS 1"), ("06020002", "แคลคูลัส 2", "CALCULUS 2"),
                   ("06020003", "ระบบโครงสร้างพื้นฐานและการบริการ", "INFRASTRUCTURE AND SERVICES"),
                   ("06020004", "ระบบ", "SYSTEM")])
    c.commit()
    return c


def _ask_code(tmp_path, monkeypatch, question):
    _code_db(tmp_path).close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


@pytest.mark.parametrize("question,code", [
    ("ขอรหัสวิชาของระบบโครงสร้างพื้นฐานและการบริการหน่อย", "06020003"),
    ("วิชาระบบโครงสร้างพื้นฐานและการบริการมีรหัสวิชาอะไร", "06020003"),
    ("วิชา แคลคูลัส 2 รหัสอะไร", "06020002"),
    ("แคลคูลัส 1 รหัสวิชาคืออะไร", "06020001"),
    ("วิชา CALCULUS 2 รหัสอะไร", "06020002"),
    ("วิชา calculus 1 มีรหัสวิชาอะไร", "06020001"),
    ("รหัสวิชา INFRASTRUCTURE AND SERVICES คืออะไร", "06020003"),
    ("วิชาวิชาเลือก กมีรหัสวิชาอะไร", "06010001")])
def test_course_code_is_looked_up_from_the_name_without_the_model(tmp_path, monkeypatch, question, code):
    r = _ask_code(tmp_path, monkeypatch, question)
    assert code in r["answer"] and r["model_calls"] == 0


def test_the_longest_matching_name_wins_over_a_shorter_name_inside_it(tmp_path, monkeypatch):
    r = _ask_code(tmp_path, monkeypatch, "ขอรหัสวิชาของระบบโครงสร้างพื้นฐานและการบริการ")
    assert "06020003" in r["answer"] and "06020004" not in r["answer"]


@pytest.mark.parametrize("question", [
    "แคลคูลัส 1 ยากไหม", "วิชา แคลคูลัส 2 ต้องเรียนวิชาอะไรก่อน", "ปี 1 เทอม 1 เรียนวิชาอะไรบ้าง ขอเป็นรหัสวิชา",
    "ชั้นปีที่ 2 ภาคการศึกษาที่ 1 ประกอบด้วยรายวิชารหัสใดบ้าง", "ขอรหัสวิชาที่ไม่มีอยู่จริงหน่อย", "วิชา 06020001 ชื่ออะไร",
    "รหัสวิชา 06020002 ต้องเรียนก่อนวิชาอะไร", "แคลคูลัส 1 และแคลคูลัส 2 ต่างกันอย่างไร"])
def test_code_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    assert _ask_code(tmp_path, monkeypatch, question)["model_calls"] >= 1


def test_two_different_courses_in_one_question_are_answered_with_both_codes(tmp_path, monkeypatch):
    r = _ask_code(tmp_path, monkeypatch, "ขอรหัสวิชาแคลคูลัส 1 กับแคลคูลัส 2")        # ไม่ตอบแค่วิชาเดียว (ดู _multi_course_answer)
    assert "06020001" in r["answer"] and "06020002" in r["answer"] and r["model_calls"] == 0


def test_the_same_name_under_two_codes_lists_both(tmp_path, monkeypatch):
    _code_db(tmp_path).close()
    with closing(sqlite3.connect(tmp_path / "t.db")) as c:
        c.execute("INSERT INTO course (code, name_th, name_en, credits) VALUES ('06029999', 'แคลคูลัส 1', 'CALCULUS 1', 3)")
        c.commit()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, "แคลคูลัส 1 รหัสอะไร", verbose=False)
    assert "06020001" in r["answer"] and "06029999" in r["answer"]


def _gold_code_cases():
    out = []
    for rel, gold in (("DSBA/coop", "dsba_coop"), ("DSBA/no_coop", "dsba_no_coop"), ("AIT", "ait"), ("IT/coop", "it_coop"),
                      ("IT/no_coop", "it_no_coop"), ("BIT/coop", "bit_coop"), ("BIT/no_coop", "bit_no_coop")):
        for q in json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8")):
            out.append((rel, q))
    return out


def test_gold_questions_get_only_the_gold_code_from_the_code_shortcut():
    """คำถามทองที่ถามรหัสวิชาจากชื่อจะเข้าทางลัดนี้ได้ แต่ต้องตอบตรงเฉลย; คำถามอื่นห้ามเข้า"""
    checked = 0
    for rel, q in _gold_code_cases():
        db = RUNS / rel / "lab8b_output" / "curriculum.db"
        if not db.exists():
            continue
        with closing(m.open_db(db, readonly=True)) as conn:
            r = m._code_lookup_answer(conn, q["question"])
        if r is None:
            continue
        checked += 1
        gt = q["expect"]
        assert gt.get("type") == "value" and str(gt.get("value")) in r[0] and len(r[1]) == 1, (rel, q["question"], r[0], gt)
    assert checked >= 5                                                    # ทางลัดต้องทำงานกับคำถามทองกลุ่ม "…รหัสอะไร" จริง ๆ


# =============== ผลทดสอบความนิ่ง (ถามทุกข้อทอง 5 รอบ): โมเดลไม่แกว่ง แต่ 7 ข้อผิดเหมือนเดิมทุกรอบ → ทางลัดทั่วไป 3 แบบ ===============
# (1) "course code of <ชื่ออังกฤษ>" (2) ชั่วโมงบรรยาย/ปฏิบัติ/ศึกษาเองของวิชาเดียว (3) วิชาที่ชั่วโมงมาก/น้อยที่สุดในปีที่ระบุ

def _hours_db(tmp_path):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=False)
    c.executemany("INSERT INTO course (code, name_th, name_en, credits, lecture_h, lab_h, self_h) VALUES (?, ?, ?, 3, ?, ?, ?)",
                  [("06020001", "แคลคูลัส 1", "CALCULUS 1", 3, 0, 6), ("06020002", "การเขียนโปรแกรม", "PROGRAMMING", 2, 2, 5),
                   ("06020003", "ฟิสิกส์ 1", "PHYSICS 1", 2, 3, 2), ("06020004", "ภาษาอังกฤษ 3", "ENGLISH 3", 2, 0, 3),
                   ("06020005", "สัมมนา", "SEMINAR", 0, 0, 1)])
    c.executemany("INSERT INTO plan_item (program_id, year, semester, code, credits) VALUES ('P', ?, ?, ?, 3)",
                  [(1, 1, "06020001"), (1, 2, "06020002"), (2, 1, "06020003"), (2, 2, "06020004"), (3, 1, "06020005")])
    c.commit()
    return c


def _ask_hours(tmp_path, monkeypatch, question):
    _hours_db(tmp_path).close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


@pytest.mark.parametrize("question,code", [
    ("What is the course code of CALCULUS 2", None), ("What is the course code of PHYSICS 1", "06020003"),
    ("what is the course code for programming?", "06020002"), ("Course code of English 3", "06020004")])
def test_english_course_code_questions_use_the_code_lookup(tmp_path, monkeypatch, question, code):
    r = _ask_hours(tmp_path, monkeypatch, question)
    if code:
        assert code in r["answer"] and r["model_calls"] == 0
    else:
        assert r["model_calls"] >= 1                                       # ไม่มีวิชานี้ → ทางเดิม ไม่เดา


@pytest.mark.parametrize("question,value", [
    ("แคลคูลัส 1 แล็บสัปดาห์ละกี่ชั่วโมง", 0), ("วิชาแคลคูลัส 1 มีชั่วโมงบรรยายต่อสัปดาห์กี่ชั่วโมง", 3),
    ("วิชา PHYSICS 1 มีชั่วโมงปฏิบัติการต่อสัปดาห์กี่ชั่วโมง", 3), ("วิชา 06020002 ศึกษาด้วยตนเองสัปดาห์ละกี่ชั่วโมง", 5),
    ("การเขียนโปรแกรม ใช้ชั่วโมงบรรยายกี่ชั่วโมงต่อสัปดาห์", 2)])
def test_hours_of_one_named_course_are_read_from_the_course_row(tmp_path, monkeypatch, question, value):
    r = _ask_hours(tmp_path, monkeypatch, question)
    assert r["model_calls"] == 0 and any(str(value) == str(v) for row in r["rows"] for v in row.values())
    assert f"{value} ชั่วโมง" in r["answer"]


@pytest.mark.parametrize("question", [
    "ปี 1 มีวิชาที่แล็บกี่ชั่วโมงบ้าง", "แคลคูลัส 1 ยากไหม",
    "แคลคูลัส 1 และฟิสิกส์ 1 บรรยายสัปดาห์ละกี่ชั่วโมง", "วิชาที่ไม่มีอยู่จริงบรรยายสัปดาห์ละกี่ชั่วโมง", "ชั่วโมงบรรยายรวมของทุกวิชากี่ชั่วโมง"])
def test_hours_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    assert _ask_hours(tmp_path, monkeypatch, question)["model_calls"] >= 1


@pytest.mark.parametrize("question,value,names", [
    ("ปี 1 กับปี 2 วิชาที่บรรยายนานที่สุดสัปดาห์ละกี่ชั่วโมง", 3, ["แคลคูลัส 1"]),
    ("ปี 1 วิชาที่บรรยายนานที่สุดกี่ชั่วโมง", 3, ["แคลคูลัส 1"]),
    ("ทั้งแผนวิชาที่แล็บมากที่สุดสัปดาห์ละกี่ชั่วโมง", 3, ["ฟิสิกส์ 1"]),
    ("ปี 1 ถึงปี 3 วิชาที่ศึกษาด้วยตนเองน้อยที่สุดกี่ชั่วโมง", 1, ["สัมมนา"]),
    ("ในปี 2 วิชาที่ปฏิบัติน้อยที่สุดสัปดาห์ละกี่ชั่วโมง", 0, ["ภาษาอังกฤษ 3"]),
    ("ปี 2 วิชาที่บรรยายมากที่สุดกี่ชั่วโมง", 2, ["ฟิสิกส์ 1", "ภาษาอังกฤษ 3"])])
def test_extreme_hours_over_the_requested_years(tmp_path, monkeypatch, question, value, names):
    r = _ask_hours(tmp_path, monkeypatch, question)
    assert r["model_calls"] == 0 and f"{value} ชั่วโมง" in r["answer"]
    assert sorted(row["name_th"] for row in r["rows"]) == sorted(names)
    assert any(str(value) == str(v) for row in r["rows"] for v in row.values())


@pytest.mark.parametrize("question", [
    "ปี 1 เทอม 1 เรียนหนักที่สุดกี่หน่วยกิต", "วิชาที่บรรยายมากกว่า 2 ชั่วโมงมีกี่วิชา", "เทอมไหนเรียนหน่วยกิตมากที่สุด"])
def test_extreme_hours_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    assert _ask_hours(tmp_path, monkeypatch, question)["model_calls"] >= 1


# ข้อทองที่เฉลยขัดกับเล่ม (ไม่แก้ไฟล์ทองที่ล็อกไว้): IT/coop E3 เล่มพิมพ์ 06016425 เป็น 3(2-2-5) = ปฏิบัติ 2 ชั่วโมง แต่เฉลยทองเขียน 0
_GOLD_DISAGREES_WITH_BOOK = {("IT/coop", "E3"): "ชั่วโมงปฏิบัติ 2 ชั่วโมง"}


def test_no_gold_question_is_taken_by_the_hours_shortcuts_unless_it_is_answered_right():
    """ข้อทองที่เข้าทางลัดชั่วโมงต้องตอบตรงเฉลย (ชนิด value) — ข้ออื่นห้ามเข้า"""
    taken = 0
    for rel, gold in (("DSBA/coop", "dsba_coop"), ("DSBA/no_coop", "dsba_no_coop"), ("AIT", "ait"), ("IT/coop", "it_coop"),
                      ("IT/no_coop", "it_no_coop"), ("BIT/coop", "bit_coop"), ("BIT/no_coop", "bit_no_coop")):
        db = RUNS / rel / "lab8b_output" / "curriculum.db"
        if not db.exists():
            continue
        qs = json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8"))
        with closing(m.open_db(db, readonly=True)) as conn:
            for q in qs:
                for fn in (m._course_hours_answer, m._extreme_hours_answer):
                    r = fn(conn, q["question"])
                    if r is None:
                        continue
                    taken += 1
                    ok, why = m.score_one(q["expect"], {"rows": r[1]}, question=q["question"])
                    if (rel, q["id"]) in _GOLD_DISAGREES_WITH_BOOK:
                        assert not ok and _GOLD_DISAGREES_WITH_BOOK[(rel, q["id"])] in r[0], (rel, q["id"], r[0])
                        continue
                    assert ok, (rel, q["question"], r[0], q["expect"], why)
    assert taken >= 10


# =============== ชั่วโมง (บรรยาย-ปฏิบัติ-ศึกษาเอง) ที่ VLM อ่านจากภาพแผนผิด → เทียบกับ "n(a-b-c)" ที่เล่มพิมพ์ซ้ำหลายที่ ===============
# พบจากการเทียบทุกวิชา 7 DB: IT/no_coop 06016425 ใน DB เป็น 3-0-6 แต่เล่มพิมพ์ 3(2-2-5) ทุกที่ (IT/coop อ่านถูก)

_BOOK_HOURS = """--- Page 5 ---
06020001 แคลคูลัส 1 3(2-2-5)
06020002 ฟิสิกส์ 3(3-0-6)
06020003 วิชาที่เห็นครั้งเดียว 3(2-2-5)
06020004 วิชาที่หน่วยกิตไม่ตรง 3(2-2-5)
06020005 วิชาที่เสียงแตก 3(2-2-5)
--- Page 6 ---
06020001 | แคลคูลัส 1 3(2-2-5)
06020002 ฟิสิกส์ 3(3-0-6)
06020004 วิชาที่หน่วยกิตไม่ตรง 3(2-2-5)
06020005 วิชาที่เสียงแตก 3(3-0-6)
--- Page 7 ---
06020001) แคลคูลัส 1 3(2-2-5)
06020004 วิชาที่หน่วยกิตไม่ตรง 3(2-2-5)
"""


def _hours_book_db(tmp_path):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=False)
    c.executemany("INSERT INTO course (code, name_th, credits, lecture_h, lab_h, self_h) VALUES (?, ?, ?, ?, ?, ?)",
                  [("06020001", "แคลคูลัส 1", 3, 3, 0, 6), ("06020002", "ฟิสิกส์", 3, 3, 0, 6), ("06020003", "เห็นครั้งเดียว", 3, 3, 0, 6),
                   ("06020004", "หน่วยกิตไม่ตรง", 2, 3, 0, 6), ("06020005", "เสียงแตก", 3, 3, 0, 6)])
    c.commit()
    return c


def test_hours_are_corrected_from_the_book_text_only_when_the_book_agrees_with_itself(tmp_path):
    c = _hours_book_db(tmp_path)
    stats = m.reconcile_course_hours(c, _BOOK_HOURS)
    got = {r[0]: (r[1], r[2], r[3]) for r in c.execute("SELECT code, lecture_h, lab_h, self_h FROM course")}
    assert got["06020001"] == (2, 2, 5)                       # 3 ที่ในเล่มตรงกันหมด ต่างจาก DB → แก้ตามเล่ม
    assert got["06020002"] == (3, 0, 6)                       # ตรงกันอยู่แล้ว
    assert got["06020003"] == (3, 0, 6)                       # เห็นที่เดียว ไม่พอยืนยัน
    assert got["06020004"] == (3, 0, 6)                       # หน่วยกิตในเล่ม (3) ไม่ตรงกับ DB (2) → ไม่แตะ
    assert got["06020005"] == (3, 0, 6)                       # เล่มเสียงแตก 1:1 → ไม่แตะ
    assert stats["fixed"] == [("06020001", (3, 0, 6), (2, 2, 5))]
    c.close()


def test_hours_reconciliation_is_idempotent(tmp_path):
    c = _hours_book_db(tmp_path)
    m.reconcile_course_hours(c, _BOOK_HOURS)
    assert m.reconcile_course_hours(c, _BOOK_HOURS)["fixed"] == []
    c.close()


def test_real_it_databases_carry_the_hours_the_book_prints():
    for rel in ("IT/coop", "IT/no_coop"):
        db = RUNS / rel / "lab8b_output" / "curriculum.db"
        if not db.exists():
            pytest.skip("ไม่มีไฟล์ DB")
        with closing(sqlite3.connect(db)) as c:
            assert c.execute("SELECT lecture_h, lab_h, self_h FROM course WHERE code = '06016425'").fetchone() == (2, 2, 5), rel


# =============== held-out ใหม่ 270 ข้อ: "เรียนทั้งหมดกี่ปี" (โมเดลตอบ COUNT(DISTINCT year) FROM program ผิด 7/7 DB) และ
# หน่วยกิต/ปี/เทอมของวิชาเดียว (โมเดลถามตารางผิดเป็นบางครั้ง) → ทางลัดจากตาราง program / course / plan_item ตรง ๆ ===============

def _attr_db(tmp_path):
    c = _hours_db(tmp_path)
    c.execute("INSERT INTO course (code, name_th, name_en, credits) VALUES ('06020006', 'โครงงานทดสอบ', 'TEST PROJECT', 2)")
    c.executemany("INSERT INTO plan_item (program_id, year, semester, code, credits) VALUES ('P', ?, ?, '06020006', 2)", [(3, 1), (3, 2)])
    c.execute("INSERT INTO course (code, name_th, name_en, credits) VALUES ('06020007', 'วิชานอกแผน', 'OFF PLAN', 3)")
    c.commit()
    return c


def _ask_attr(tmp_path, monkeypatch, question):
    _attr_db(tmp_path).close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


@pytest.mark.parametrize("question,needle", [
    ("หลักสูตรนี้เรียนทั้งหมดกี่ปี", "4 ปี"), ("เรียนกี่ปีถึงจะจบ", "4 ปี"), ("หลักสูตรใช้เวลากี่ปี", "4 ปี"),
    ("ต้องเรียนกี่หน่วยกิตถึงจะจบหลักสูตรนี้", "129 หน่วยกิต"), ("รวมแล้วหลักสูตรมีกี่หน่วยกิต", "129 หน่วยกิต"),
    ("หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต", "129 หน่วยกิต")])
def test_program_level_years_and_credits_come_from_the_program_row(tmp_path, monkeypatch, question, needle):
    r = _ask_attr(tmp_path, monkeypatch, question)
    assert needle in r["answer"] and r["model_calls"] == 0
    assert any(str(v) in ("4", "129") for row in r["rows"] for v in row.values())


@pytest.mark.parametrize("question", [
    "ปี 1 เทอม 1 เรียนรวมกี่หน่วยกิต", "หมวดวิชาเฉพาะมีกี่หน่วยกิต", "วิชาเลือกเสรีรวมกี่หน่วยกิต", "แคลคูลัส 1 กี่หน่วยกิต",
    "ปี 2 เรียนกี่ปี", "เทอมนี้เรียนกี่หน่วยกิตทั้งหมด", "วิชาโครงงานทดสอบเรียนกี่ปี"])
def test_program_shortcut_leaves_term_category_and_course_questions_alone(tmp_path, monkeypatch, question):
    r = _ask_attr(tmp_path, monkeypatch, question)
    assert "129 หน่วยกิต" not in r["answer"] and "ตลอดหลักสูตร" not in r["answer"]


@pytest.mark.parametrize("question,needle", [
    ("แคลคูลัส 1 อยู่ปีไหนของแผน", "ปี 1"), ("วิชา ฟิสิกส์ 1 เรียนเทอมไหน", "เทอม 1"), ("วิชาฟิสิกส์ 1 อยู่ปีไหน เทอมไหน", "ปี 2 เทอม 1"),
    ("PHYSICS 1 เรียนตอนปีไหน", "ปี 2"), ("06020004 อยู่ภาคเรียนไหน", "เทอม 2"), ("โครงงานทดสอบมีกี่หน่วยกิต", "2 หน่วยกิต"),
    ("วิชา 06020003 กี่หน่วยกิต", "3 หน่วยกิต"), ("โครงงานทดสอบเรียนปีไหน", "ปี 3")])
def test_credits_year_and_semester_of_one_course_come_from_the_tables(tmp_path, monkeypatch, question, needle):
    r = _ask_attr(tmp_path, monkeypatch, question)
    assert needle in r["answer"] and r["model_calls"] == 0


def test_a_course_in_two_plan_places_lists_both(tmp_path, monkeypatch):
    r = _ask_attr(tmp_path, monkeypatch, "โครงงานทดสอบเรียนเทอมไหน")
    assert "ปี 3 เทอม 1" in r["answer"] and "ปี 3 เทอม 2" in r["answer"]


@pytest.mark.parametrize("question", [
    "วิชานอกแผนเรียนปีไหน", "วิชาที่ไม่มีอยู่จริงกี่หน่วยกิต", "แคลคูลัส 1 ยากไหม",
    "แคลคูลัส 1 ต้องเรียนวิชาอะไรก่อน", "ปี 1 เทอม 1 มีวิชาอะไรบ้างกี่หน่วยกิต", "วิชาอะไรเรียนปีไหนบ้าง"])
def test_course_attribute_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    assert _ask_attr(tmp_path, monkeypatch, question)["model_calls"] >= 1


def test_gold_questions_taken_by_the_program_and_course_attribute_shortcuts_are_answered_right():
    taken = 0
    for rel, gold in (("DSBA/coop", "dsba_coop"), ("DSBA/no_coop", "dsba_no_coop"), ("AIT", "ait"), ("IT/coop", "it_coop"),
                      ("IT/no_coop", "it_no_coop"), ("BIT/coop", "bit_coop"), ("BIT/no_coop", "bit_no_coop")):
        db = RUNS / rel / "lab8b_output" / "curriculum.db"
        if not db.exists():
            continue
        qs = json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8"))
        with closing(m.open_db(db, readonly=True)) as conn:
            for q in qs:
                for fn in (m._program_fact_answer, m._course_attr_answer):
                    r = fn(conn, q["question"])
                    if r is None:
                        continue
                    taken += 1
                    ok, why = m.score_one(q["expect"], {"rows": r[1]}, question=q["question"])
                    assert ok, (rel, q["id"], q["question"], r[0], q["expect"], why)
    assert taken >= 10


# =============== ชุดสำนวนใหม่ล้วน (subagent อิสระเขียน 98 ข้อ): ถูก 78 ผิด 20 ผิดทุกรอบ ไม่แกว่ง — จัด 6 กลุ่มสาเหตุ ===============
# (1) ทิศวิชาบังคับก่อน "เป็นวิชาที่ต้องเรียนก่อนวิชาไหน/เป็นวิชาพื้นฐานให้วิชาอะไร" (ดู tests/test_course_names.py)
# (2) หัวข้อ มคอ.2 สำนวนอื่น (ทำงานตำแหน่งไหน, ผู้ที่จะสมัคร, เกณฑ์การรับ, ปริญญาที่ได้รับคือ…, จะสำเร็จการศึกษาต้องผ่านเกณฑ์)
# (3) คำอธิบายวิชาถามด้วยชื่ออังกฤษ (4) กลุ่มวิชาเลือกถามด้วยชื่อกลุ่ม (5) ภาคต้น/ภาคปลาย (6) ทางลัดข้อมูลหลักสูตรแย่งคำถามเรื่องวิชาที่ไม่มีจริง

@pytest.mark.parametrize("question,needle,page", [
    ("จบ AI ไปแล้วทำงานตำแหน่งไหนได้บ้าง", "Data Scientist", 3), ("จบแล้วไปทำงานเป็นอะไรได้บ้าง", "Data Scientist", 3),
    ("เรียนจบแล้วทำงานสายไหนได้บ้าง", "Data Scientist", 3),
    ("คุณสมบัติของผู้ที่จะสมัครเข้าเรียนหลักสูตรนี้คืออะไร", "มัธยมศึกษาตอนปลาย", 4),
    ("อยากรู้เกณฑ์การรับเข้าศึกษา ต้องจบอะไรมา", "มัธยมศึกษาตอนปลาย", 4),
    ("สมัครเรียนต้องมีคุณสมบัติอะไรบ้าง", "มัธยมศึกษาตอนปลาย", 4),
    ("จะสำเร็จการศึกษาต้องผ่านเกณฑ์อะไร", "ข้อบังคับสถาบัน", 5),
    ("เงื่อนไขในการจบการศึกษาของหลักสูตรนี้คืออะไร", "ข้อบังคับสถาบัน", 5),
    ("ปริญญาที่ได้รับคือชื่อว่าอะไร", "วิทยาศาสตรบัณฑิต (ตัวอย่าง)", 2), ("ปริญญาที่ได้ชื่อว่าอะไร", "วิทยาศาสตรบัณฑิต (ตัวอย่าง)", 2)])
def test_book_sections_are_reached_by_other_natural_phrasings(tmp_path, monkeypatch, question, needle, page):
    r = _ask_sec(tmp_path, monkeypatch, question)
    assert needle in r["answer"] and r["model_calls"] == 0
    assert [c["pdf_page"] for c in r["citations"]] == [page]


@pytest.mark.parametrize("question", [
    "วิชานี้มีการทำงานกลุ่มไหม", "ทำงานหนักไหมในปี 3", "วิชาไหนต้องทำงานเป็นทีม", "ต้องจบอะไรถึงจะเรียนวิชาแคลคูลัส 2 ได้",
    "ผู้สอนวิชานี้ชื่ออะไร"])
def test_section_phrasings_do_not_fire_on_work_degree_or_admission_words_elsewhere(tmp_path, monkeypatch, question):
    assert _ask_sec(tmp_path, monkeypatch, question)["model_calls"] >= 1


def _desc_en_db(tmp_path):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=False)
    c.executemany("INSERT INTO course (code, name_th, name_en, credits) VALUES (?, ?, ?, 3)",
                  [("06020001", "แคลคูลัส 1", "CALCULUS 1"), ("06020002", "แคลคูลัส 2", "CALCULUS 2")])
    m.load_course_descriptions(c, _BOOK_DESC)
    c.commit()
    return c


@pytest.mark.parametrize("question", [
    "CALCULUS 1 สอนเกี่ยวกับอะไรบ้าง", "วิชา Calculus 1 เรียนเรื่องอะไร", "calculus 1 สอนอะไร", "คำอธิบายรายวิชา CALCULUS 1 คืออะไร"])
def test_course_description_is_found_by_the_english_name_too(tmp_path, monkeypatch, question):
    _desc_en_db(tmp_path).close()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    assert "ลิมิตและความต่อเนื่อง" in r["answer"] and "CALCULUS 2" not in r["answer"]


def _grp_db(tmp_path):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=True)
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) "
              "VALUES (2, 'P', 'ช่องการตลาด', 9, 2, 'กลุ่มวิชาเลือกการตลาดดิจิทัล')")
    c.executemany("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (2, ?, ?, 'X', 3)",
                  [("06036141", "การตลาดเนื้อหา"), ("06036142", "การตลาดผ่านสื่อสังคม"), ("06036143", "การวิเคราะห์ตลาด")])
    c.execute("INSERT INTO course (code, name_th, name_en, credits) VALUES ('06036116', 'การตลาดดิจิทัล', 'DIGITAL MARKETING', 3)")
    c.commit()
    return c


def _ask_grp(tmp_path, monkeypatch, question):
    _grp_db(tmp_path).close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


@pytest.mark.parametrize("question,needles", [
    ("กลุ่มวิชาเลือกการตลาดดิจิทัล มีวิชาอะไรบ้าง ขอเป็นรหัสวิชา", ["06036141", "06036142", "06036143"]),
    ("ในกลุ่มวิชาเลือกการตลาดดิจิทัลมีวิชาอะไรให้เลือกบ้าง", ["การตลาดเนื้อหา", "06036143"]),
    ("วิชาเลือกการตลาดดิจิทัลมีกี่วิชา", ["3 วิชา"]), ("กลุ่มวิชาเลือกการตลาดดิจิทัล มีวิชาทั้งหมดกี่วิชา", ["3 วิชา"]),
    ("วิชาเลือกการตลาดดิจิทัล ต้องเลือกรวมกี่หน่วยกิต", ["9 หน่วยกิต"]), ("กลุ่มวิชาเลือกการตลาดดิจิทัลต้องเรียนกี่หน่วยกิต", ["9 หน่วยกิต"])])
def test_elective_group_questions_are_answered_from_the_group(tmp_path, monkeypatch, question, needles):
    r = _ask_grp(tmp_path, monkeypatch, question)
    assert r["model_calls"] == 0 and all(n in r["answer"] for n in needles)
    assert "06036116" not in r["answer"]                       # ชื่อกลุ่มชนชื่อวิชา "การตลาดดิจิทัล" — ต้องตอบเป็นกลุ่ม ไม่ใช่วิชานั้น


@pytest.mark.parametrize("question", [
    "การตลาดดิจิทัลกี่หน่วยกิต", "ปี 3 เทอม 1 เลือกวิชาเลือกอะไรได้", "ต้องเรียนกี่หน่วยกิตถึงจะจบ", "วิชาเลือกมีกี่วิชา",
    "วิชา DIGITAL MARKETING รหัสอะไร", "กลุ่มวิชาเลือกการตลาดดิจิทัลมีวิชาอะไรบ้าง และเรียนปีไหน"])
def test_elective_group_shortcut_leaves_other_questions_alone(tmp_path, monkeypatch, question):
    with closing(_grp_db(tmp_path)) as c:
        c.row_factory = sqlite3.Row
        assert m._elective_group_answer(c, question) is None


@pytest.mark.parametrize("rel,gold", [("DSBA/coop", "dsba_coop"), ("DSBA/no_coop", "dsba_no_coop"), ("AIT", "ait"), ("IT/coop", "it_coop"),
                                       ("IT/no_coop", "it_no_coop"), ("BIT/coop", "bit_coop"), ("BIT/no_coop", "bit_no_coop")])
def test_no_gold_question_gets_an_elective_group_answer(rel, gold):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    qs = json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8"))
    with closing(m.open_db(db, readonly=True)) as conn:
        for q in qs:
            assert m._elective_group_answer(conn, q["question"]) is None, q["question"]


def test_thai_half_year_words_become_semester_numbers():
    assert m._normalise_semester_words("ปี 2 ภาคปลายมีวิชาอะไรบ้าง") == "ปี 2 ภาคการศึกษาที่ 2 มีวิชาอะไรบ้าง"
    assert m._normalise_semester_words("ปี 1 เทอมต้นเรียนอะไร") == "ปี 1 ภาคการศึกษาที่ 1 เรียนอะไร"
    assert m._normalise_semester_words("ภาคฤดูร้อนมีวิชาไหม") == "ภาคฤดูร้อนมีวิชาไหม"
    assert m._normalise_semester_words("ปี 2 เทอม 2 มีวิชาอะไรบ้าง") == "ปี 2 เทอม 2 มีวิชาอะไรบ้าง"


def test_half_year_phrasing_reaches_the_prompt_as_a_semester_number(tmp_path, monkeypatch):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _plan_db(path).close()
    seen = []
    monkeypatch.setattr(m, "ollama_generate", lambda prompt, *a, **k: seen.append(prompt) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(path, readonly=True)) as conn:
        m.ask(conn, "ปี 2 ภาคปลายมีวิชาอะไรบ้าง", verbose=False)
    assert seen and "ภาคการศึกษาที่ 2" in seen[0]


@pytest.mark.parametrize("question", [
    "วิชา Deep Learning ในหลักสูตรนี้กี่หน่วยกิต", "วิชาการทำอาหารไทยในหลักสูตรนี้มีกี่หน่วยกิต", "Quantum Computing กี่หน่วยกิตในหลักสูตรนี้",
    "วิชาบล็อกเชนมีกี่หน่วยกิตในหลักสูตร"])
def test_program_facts_do_not_answer_questions_about_a_course_that_is_not_in_the_book(tmp_path, monkeypatch, question):
    r = _ask_attr(tmp_path, monkeypatch, question)
    assert "129" not in r["answer"] and "ตลอดหลักสูตร" not in r["answer"] and r["model_calls"] >= 1


# =============== ผลรันซ้ำชุดสำนวนใหม่: ทางลัดที่เพิ่งเพิ่มแย่งตอบ 2 ข้อ + วลี "สอนเรื่องอะไร" ===============

@pytest.mark.parametrize("question", [
    "ทั้งหลักสูตรวิทยาการข้อมูลแบบสหกิจใช้กี่หน่วยกิต", "หลักสูตรวิทยาการข้อมูลมีกี่วิชาในแผน", "วิทยาการข้อมูลเรียนกี่หน่วยกิตทั้งหมด"])
def test_a_group_name_inside_the_program_name_is_not_taken_for_the_group(tmp_path, monkeypatch, question):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=True)
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) "
              "VALUES (3, 'P', 'ช่องข้อมูล', 6, 3, 'กลุ่มวิทยาการข้อมูล')")
    c.executemany("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (3, ?, ?, 'X', 3)",
                  [("06026250", "การทำเหมืองข้อมูล"), ("06026251", "การเรียนรู้ของเครื่อง")])
    c.commit()
    c.row_factory = sqlite3.Row
    assert m._elective_group_answer(c, question) is None
    assert m._elective_group_answer(c, "กลุ่มวิทยาการข้อมูลมีกี่วิชา") is not None            # พูดว่า "กลุ่ม" ชัดเจน = ถามกลุ่ม
    c.close()


@pytest.mark.parametrize("question", [
    "CALCULUS 1 ต้องเรียนอะไรมาก่อน", "แคลคูลัส 1 ต้องเรียนวิชาอะไรก่อน", "calculus 1 ต้องผ่านอะไรก่อนถึงจะเรียนได้", "แคลคูลัส 1 หลังจากนี้เรียนอะไรต่อ"])
def test_prerequisite_questions_are_not_taken_for_description_questions(tmp_path, monkeypatch, question):
    _desc_en_db(tmp_path).close()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        assert m._course_description_answer(conn, question) is None


@pytest.mark.parametrize("question", [
    "วิชา CALCULUS 1 สอนเรื่องอะไร", "แคลคูลัส 1 สอนเกี่ยวกับเรื่องอะไร", "calculus 1 เรียนเรื่องอะไรบ้าง", "แคลคูลัส 1 มีเนื้อหาอะไร"])
def test_more_ways_to_ask_what_a_course_teaches(tmp_path, monkeypatch, question):
    _desc_en_db(tmp_path).close()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    assert "ลิมิตและความต่อเนื่อง" in r["answer"]


# =============== การอ้างหน้าที่ขาด: eval ล่าสุด คำตอบถูก 174 ข้อ ไม่มีหน้าอ้างอิง 35 ข้อ (ข้อมูลระดับหลักสูตร 14, นับตามปี 14, นับคู่วิชาบังคับก่อน 7) ===============
# เกณฑ์ ch1: "LLM ตอบคำถาม 30 คะแนน ต้องตอบถูกและอ้างอิงหน้า/หัวข้อในเล่ม"

_BOOK_PROG = """--- Page 2 ---
4. จ้านวนหน่วยกิตทีเรียนตลอดหลักสูตร
129 หน่วยกิต
--- Page 3 ---
5. รูปแบบของหลักสูตร
5.1 รูปแบบ
[ๆ หลักสูตรปริญญาตรี 4 ปี
6. สถานภาพของหลักสูตร
ข้อความอื่น
--- Page 5 ---
5.1.1 ระยะเวลการศึกษาของหลักสูตร
หลักสูตรปริญญาตรี 4 ปี ตามแผน
5.2 อย่างอื่น
ไม่เกี่ยว
"""


def test_total_credits_and_duration_sections_are_stored_with_their_pages():
    got = {d["topic"]: d for d in m.parse_book_sections(_BOOK_PROG)}
    assert got["หน่วยกิตตลอดหลักสูตร"]["pdf_page"] == 2 and "129" in got["หน่วยกิตตลอดหลักสูตร"]["body"]
    assert got["ระยะเวลาการศึกษา"]["pdf_page"] == 5 and "4 ปี" in got["ระยะเวลาการศึกษา"]["body"]       # หัวข้อเข้ม 5.1.1 ชนะ "รูปแบบของหลักสูตร"
    only_format = {d["topic"]: d for d in m.parse_book_sections(_BOOK_PROG.split("--- Page 5 ---")[0])}
    assert only_format["ระยะเวลาการศึกษา"]["pdf_page"] == 3                                           # ไม่มี 5.1.1 → ใช้หัวข้อ "รูปแบบของหลักสูตร"


def _prog_db(tmp_path):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=False)
    m.load_book_sections(c, _BOOK_PROG)
    c.commit()
    return c


@pytest.mark.parametrize("question,answer_part,page", [
    ("หลักสูตรนี้เรียนกี่ปี", "4 ปี", 5), ("ต้องเรียนกี่หน่วยกิตถึงจะจบหลักสูตรนี้", "129 หน่วยกิต", 2)])
def test_program_facts_cite_the_page_where_the_book_states_them(tmp_path, monkeypatch, question, answer_part, page):
    _prog_db(tmp_path).close()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    assert answer_part in r["answer"] and [c["pdf_page"] for c in r["citations"]] == [page]


def test_program_facts_without_the_section_rows_still_answer_without_a_citation(tmp_path, monkeypatch):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    _make_db(path, electives=False).close()
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: '{"sql": "SELECT 1"}')
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, "หลักสูตรนี้เรียนกี่ปี", verbose=False)
    assert "4 ปี" in r["answer"] and r["citations"] == []


def _year_cite_db(tmp_path):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _plan_db(path)
    c.executescript(m.COURSE_PAGE_DDL)
    c.executemany("INSERT INTO term_page VALUES (?, ?, ?, ?)",
                  [(1, 1, 10, "5"), (1, 2, 11, "6"), (2, 1, 12, "7"), (2, 2, 13, "8"), (3, 1, 14, "9")])
    c.commit()
    return c


def _ask_counting(tmp_path, monkeypatch, question, model_sql="SELECT COUNT(*) AS n FROM plan_item WHERE year IN (1, 2)"):
    _year_cite_db(tmp_path).close()
    calls = []

    def fake(prompt, fmt=None, **kw):
        calls.append(prompt)
        return json.dumps({"sql": model_sql}) if len(calls) == 1 else json.dumps({"answer": "3 วิชา"})

    monkeypatch.setattr(m, "ollama_generate", fake)
    with closing(m.open_db(tmp_path / "t.db", readonly=True)) as conn:
        return m.ask(conn, question, verbose=False)


@pytest.mark.parametrize("question,pages", [
    ("ปี 1 กับปี 2 มีกี่วิชา", [10, 11, 12, 13]), ("ในแผนการศึกษาชั้นปีที่ 1–2 มีวิชากี่วิชา", [10, 11, 12, 13]),
    ("ปี 3 มีกี่วิชา", [14]), ("ปี 1 ถึงปี 2 นับวิชาได้กี่วิชา", [10, 11, 12, 13])])
def test_a_count_over_years_cites_the_plan_pages_of_those_years(tmp_path, monkeypatch, question, pages):
    r = _ask_counting(tmp_path, monkeypatch, question)
    assert [c["pdf_page"] for c in r["citations"]] == pages


def test_no_year_in_the_question_means_no_fallback_citation(tmp_path, monkeypatch):
    assert _ask_counting(tmp_path, monkeypatch, "ทั้งหลักสูตรมีกี่วิชา", "SELECT COUNT(*) AS n FROM plan_item")["citations"] == []


def test_an_answer_that_found_nothing_is_never_cited(tmp_path, monkeypatch):
    r = _ask_counting(tmp_path, monkeypatch, "ปี 1 มีกี่วิชาที่ชื่อว่า XYZ", "SELECT code FROM course WHERE name_th = 'XYZ'")
    assert r["citations"] == []


# =============== รีวิวอิสระ (subagent ตรวจโค้ดช่วง 261a991..HEAD): ทางลัดตอบผิดแทนที่จะปฏิเสธ — เทสต์จากกรณีจริงบน DB จริง ===============

def _chain(conn, question):
    """จำลองลำดับใน ask(): ทางลัดตัวแรกที่ตอบได้ (ไม่เรียกโมเดล) — None = ปล่อยให้ไปทางโมเดล"""
    question = m._normalise_semester_words(question)
    m.scope_elective_view(conn, question)
    for fn in m._SHORTCUTS:
        try:
            r = fn(conn, question)
        except Exception:
            r = None
        if r:
            return r
    return None


def _real(rel):
    db = RUNS / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    return m.open_db(db, readonly=True)


# C1 ชื่อยาว/ชื่อที่ไม่มีในเล่ม ห้ามตกไปเป็นชื่อสั้นที่อยู่ข้างใน
@pytest.mark.parametrize("rel,question", [
    ("IT/coop", "Team-Project 1 กี่หน่วยกิต"), ("IT/coop", "วิชา Internet of Things Data Analytics มีชั่วโมงปฏิบัติกี่ชั่วโมง")])
def test_an_unknown_longer_course_name_is_not_answered_as_the_shorter_name_inside_it(rel, question):
    with closing(_real(rel)) as c:
        assert _chain(c, question) is None, question


# ชื่อยาวที่มีในแคตตาล็อกจริง (GE "การเตรียมความพร้อมสหกิจศึกษา" 90642160; "การตลาดเซิงดิจิทัลขั้นสูง" 06036142 สะกด "เซิง" ตาม OCR) ต้องได้คำตอบของวิชานั้น ไม่ใช่ชื่อสั้นที่อยู่ข้างใน
def test_a_long_catalog_name_is_answered_as_itself_not_as_the_shorter_plan_name_inside_it():
    with closing(_real("IT/coop")) as c:
        r = _chain(c, "วิชาการเตรียมความพร้อมสหกิจศึกษามีกี่หน่วยกิต")
    assert r and "90642160" in r[0] and "06016481" not in r[0]
    with closing(_real("BIT/coop")) as c:
        r = _chain(c, "รหัสวิชาการตลาดเชิงดิจิทัลขั้นสูง")
        assert r and "06036142" in r[0] and "06036116" not in r[0]
        assert _chain(c, "การตลาดเชิงดิจิทัลขั้นสูงกี่หน่วยกิต") is None or "06036116" not in _chain(c, "การตลาดเชิงดิจิทัลขั้นสูงกี่หน่วยกิต")[0]


def test_the_same_name_typed_with_or_without_the_two_character_sara_am_finds_the_same_course():
    with closing(_real("BIT/coop")) as c:
        a = _chain(c, "รหัสวิชาเครื่องมือและเทคนิคสำหรับการตลาดเชิงดิจิทัล")
        b = _chain(c, "รหัสวิชาเครื่องมือและเทคนิคสําหรับการตลาดเชิงดิจิทัล")
    assert a and b and "06036141" in a[0] and "06036141" in b[0]


def test_whole_name_boundaries():
    whole = m._name_is_whole
    assert whole("วิชาแคลคูลัส1กี่หน่วยกิต", "แคลคูลัส1") and whole("แคลคูลัส1รหัสอะไร", "แคลคูลัส1") and whole("ขอรหัสวิชาของแคลคูลัส1หน่อย", "แคลคูลัส1")
    assert not whole("การเตรียมความพร้อมสหกิจศึกษากี่หน่วยกิต", "สหกิจศึกษา")             # นำหน้าด้วยอักษรไทยที่ไม่ใช่คำถาม
    assert not whole("การตลาดเชิงดิจิทัลขั้นสูงกี่หน่วยกิต", "การตลาดเชิงดิจิทัล")           # ตามหลังด้วยส่วนของชื่อที่ยาวกว่า
    assert not whole("แคลคูลัส1และ2กี่หน่วยกิต", "แคลคูลัส1")                              # "X 1 และ 2" = สองวิชา
    assert whole("whatisthecoursecodeofcalculus1", "calculus1") is True
    assert not whole("microcalculus1code", "calculus1")                                    # ติดกับตัวอักษรอังกฤษ = คนละคำ


# C2 หัวข้อ มคอ.2 ห้ามแย่งคำถามเรื่องวิชา (รวมวิชา GE) หรือคำถามที่ไม่ได้ถามหัวข้อนั้นจริง
@pytest.mark.parametrize("question", [
    "วิชาปรัชญาเศรษฐกิจพอเพียงกี่หน่วยกิต", "รหัสวิชาปรัชญาเศรษฐกิจพอเพียง", "การเขียนและการพูดในงานอาชีพ กี่หน่วยกิต",
    "วิชาเลือกที่ช่วยเตรียมความพร้อมด้านอาชีพมีอะไรบ้าง", "นักศึกษาสหกิจต้องทำงานอะไรได้บ้าง", "จบปี 3 แล้วทำงานพาร์ทไทม์ได้ไหม",
    "ได้รับวุฒิอะไรหลังผ่านสหกิจ"])
def test_section_shortcut_does_not_hijack_course_or_cooperative_questions(question):
    with closing(_real("IT/coop")) as c:
        assert m._book_section_answer(c, question) is None, question


# C3 คำถามเชิงความสัมพันธ์ (ต่อจาก/เป็นพื้นฐาน/เทอมเดียวกับ/แทน) ห้ามได้คำตอบของวิชาที่ถูกอ้างถึง
@pytest.mark.parametrize("question", [
    "ผ่านแคลคูลัส 1 แล้วไปเรียนอะไรต่อ", "ในเทอมที่เรียนแคลคูลัส 2 เรียนอะไรบ้าง", "ถ้าตกแคลคูลัส 1 ต้องเรียนอะไรแทน",
    "รหัสวิชาที่ต่อจากแคลคูลัส 1", "วิชาที่เรียนเทอมเดียวกับแคลคูลัส 1 มีกี่หน่วยกิต", "วิชาที่ใช้แคลคูลัส 1 เป็นพื้นฐานมีชั่วโมงปฏิบัติกี่ชั่วโมง"])
def test_relational_questions_are_not_answered_with_the_referenced_course_own_attribute(question):
    with closing(_real("DSBA/coop")) as c:
        for fn in (m._course_description_answer, m._code_lookup_answer, m._course_hours_answer, m._course_attr_answer):
            assert fn(c, question) is None, (fn.__name__, question)


# C4 ข้อมูลระดับหลักสูตรต้องเป็นคำถามระดับหลักสูตรจริง ๆ
@pytest.mark.parametrize("question", [
    "ปีแรกเรียนรวมกี่หน่วยกิต", "ปีสุดท้ายเรียนรวมกี่หน่วยกิต", "ซัมเมอร์เรียนรวมกี่หน่วยกิต", "แกนรวมกี่หน่วยกิต",
    "ต้องมีหน่วยกิตสะสมรวมเท่าไหร่ถึงจะออกสหกิจได้", "หลักสูตรนี้เรียนได้นานสุดกี่ปี", "ระยะเวลาการศึกษาสูงสุดไม่เกินกี่ปี", "ต้องเรียนกี่ปีถึงจะได้ออกสหกิจ"])
def test_program_facts_do_not_answer_sub_scope_or_maximum_duration_questions(question):
    with closing(_real("DSBA/coop")) as c:
        assert m._program_fact_answer(c, question) is None, question


@pytest.mark.parametrize("question,part", [
    ("หลักสูตรนี้ต้องเรียนกี่หน่วยกิตถึงจะจบ", "132"), ("หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต", "132"),
    ("หลักสูตรนี้เรียนกี่ปี", "4 ปี"), ("ระยะเวลาการศึกษาตามแผนของหลักสูตรนี้กี่ปี", "4 ปี")])
def test_program_facts_still_answer_the_plain_program_questions(question, part):
    with closing(_real("DSBA/coop")) as c:
        r = m._program_fact_answer(c, question)
    assert r and part in r[0]


# I1 สองวิชาในคำถามเดียว (X 1 และ 2) ห้ามตอบแค่วิชาเดียว — ตอบทุกวิชา (หน่วยกิต/รหัส/ปีเทอม) หรือปล่อยให้โมเดล (ชั่วโมง/เนื้อหา/เปรียบเทียบ)
@pytest.mark.parametrize("question,codes", [
    ("แคลคูลัส 1 และ 2 กี่หน่วยกิต", ["06026200", "06026201"]), ("แคลคูลัส 1 และ 2 เรียนปีไหน", ["06026200", "06026201"]),
    ("รหัสวิชาแคลคูลัส 1 และ 2", ["06026200", "06026201"]), ("รหัสวิชาภาษาอังกฤษพื้นฐาน 1, 2", ["90644007", "90644008"])])
def test_two_courses_in_one_question_are_both_answered(question, codes):
    with closing(_real("DSBA/coop")) as c:
        r = _chain(c, question)
    assert r and all(code in r[0] for code in codes), (question, r and r[0])


@pytest.mark.parametrize("question", [
    "ภาษาอังกฤษพื้นฐาน 1 และ 2 มีชั่วโมงบรรยายกี่ชั่วโมง", "แคลคูลัส 1 และพีชคณิตเชิงเส้นเรียนเกี่ยวกับอะไร"])
def test_two_courses_in_one_question_about_hours_or_content_are_left_to_the_model(question):
    with closing(_real("DSBA/coop")) as c:
        assert _chain(c, question) is None, question


# I2 ปีหลายค่า/ปีแบบคำ
def test_extreme_hours_reads_every_listed_year_and_declines_word_years():
    with closing(_real("IT/coop")) as c:
        r = m._extreme_hours_answer(c, "ในปี 1 และ 3 วิชาที่ปฏิบัติมากที่สุดสัปดาห์ละกี่ชั่วโมง")
        assert r and "36 ชั่วโมง" in r[0]
        assert m._extreme_hours_answer(c, "ปีสุดท้ายวิชาที่ปฏิบัติมากที่สุดกี่ชั่วโมง") is None
        assert m._extreme_hours_answer(c, "ปีหนึ่งวิชาที่บรรยายมากที่สุดกี่ชั่วโมง") is None
        r0 = m._extreme_hours_answer(c, "ชั่วโมงบรรยายน้อยที่สุดแต่ไม่เป็นศูนย์กี่ชั่วโมง")
        assert r0 and all(row["lecture_h"] > 0 for row in r0[1])             # ค่าต่ำสุดในบรรดาค่าที่ > 0 (ไม่ใช่ 0)
    assert m._question_years("ปี 1 และ 3") == {1, 3} and m._question_years("ปี 1, 2 และ 4") == {1, 2, 4}


# I3 กลุ่มวิชาเลือกที่ชื่อเหมือนวิชาในแผน
@pytest.mark.parametrize("question", [
    "วิชาการตลาดเชิงดิจิทัลเป็นวิชาเลือกหรือเปล่า มีกี่หน่วยกิต", "วิชาการตลาดเชิงดิจิทัลอยู่ในกลุ่มวิชาอะไร"])
def test_group_shortcut_does_not_answer_about_a_plan_course_that_shares_the_group_name(question):
    with closing(_real("BIT/coop")) as c:
        assert m._elective_group_answer(c, question) is None, question


# Minor: ตัวโหลดเทียบชั่วโมงต้องไม่ข้ามบรรทัด + ตัวโหลดตารางต้องไม่ทิ้งตารางว่างเมื่อ insert พัง
def test_hours_vote_does_not_cross_a_line_break():
    c = _hours_book_db_for_review()
    book = "--- Page 1 ---\n06020001\n01006505 | 96642015 วิชาอื่น 3(2-2-5)\n06020001\n01006505 | 96642015 วิชาอื่น 3(2-2-5)\n"
    assert m.reconcile_course_hours(c, book)["fixed"] == []
    c.close()


def _hours_book_db_for_review():
    c = sqlite3.connect(":memory:")
    c.executescript(m.DDL)
    c.execute("INSERT INTO program VALUES ('P', 'โปรแกรมทดสอบ', 'Test', 'วท.บ.', 129, 4)")
    c.execute("INSERT INTO course (code, name_th, credits, lecture_h, lab_h, self_h) VALUES ('06020001', 'วิชา', 3, 3, 0, 6)")
    c.commit()
    return c


def test_a_failing_reload_keeps_the_previous_table(tmp_path, monkeypatch):
    c = _sec_db(tmp_path)
    before = c.execute("SELECT COUNT(*) FROM book_section").fetchone()[0]
    assert before == 8
    monkeypatch.setattr(m, "parse_book_sections", lambda text: [{"topic": "x", "heading": "h", "body": None, "pdf_page": "not-an-int-but-ok"},
                                                                 {"topic": "x", "heading": "dup", "body": "b", "pdf_page": 1}])      # topic ซ้ำ ไม่ใช่ปัญหา (REPLACE) → บังคับพังด้วยของแปลก
    monkeypatch.setattr(m, "_citations_module", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        m.load_book_sections(c, _BOOK_SEC)
    assert c.execute("SELECT COUNT(*) FROM book_section").fetchone()[0] == before
    c.close()


# =============== ผลรันซ้ำชุดสำนวนใหม่หลังรีวิว: กฎเข้มทำให้ 3 ข้อที่เคยถูกกลายเป็น "ไม่พบ" — เปิดเฉพาะส่วนที่ไม่เสี่ยง ===============

@pytest.mark.parametrize("question", [
    "เรียนหลักสูตรนี้รวมแล้วกี่หน่วยกิต", "หลักสูตร IT ทั้งหมดกี่หน่วยกิต", "ทั้งหลักสูตรแบบสหกิจใช้กี่หน่วยกิต", "เรียนหลักสูตรสหกิจนานาชาติรวมกี่หน่วยกิต"])
def test_program_credits_are_answered_when_the_question_names_the_program_in_any_form(tmp_path, monkeypatch, question):
    r = _ask_attr(tmp_path, monkeypatch, question)
    assert "129 หน่วยกิต" in r["answer"] and r["model_calls"] == 0


@pytest.mark.parametrize("question", [
    "ต้องมีหน่วยกิตสะสมรวมเท่าไหร่ถึงจะออกสหกิจได้", "ก่อนไปสหกิจต้องเรียนครบกี่หน่วยกิต", "หลักสูตรนี้ต้องผ่านกี่หน่วยกิตก่อนออกสหกิจ"])
def test_program_credits_are_still_not_answered_for_the_requirement_before_cooperative_education(tmp_path, monkeypatch, question):
    r = _ask_attr(tmp_path, monkeypatch, question)
    assert "129 หน่วยกิต" not in r["answer"]


def _same_name_group_db(tmp_path):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _make_db(path, electives=False)
    c.execute("INSERT INTO elective_group(id, program_id, plan_slot, credits_required, group_no, name_th) "
              "VALUES (1, 'P', 'ช่องการตลาด', 6, 1, 'กลุ่มการตลาดดิจิทัล')")
    c.executemany("INSERT INTO elective_group_course(group_id, code, name_th, name_en, credits) VALUES (1, ?, ?, 'X', 3)",
                  [("06036141", "การตลาดเนื้อหา"), ("06036142", "การตลาดผ่านสื่อสังคม")])
    c.execute("INSERT INTO course (code, name_th, name_en, credits) VALUES ('06036116', 'การตลาดดิจิทัล', 'DIGITAL MARKETING', 3)")
    c.commit()
    c.row_factory = sqlite3.Row
    return c


@pytest.mark.parametrize("question", [
    "กลุ่มวิชาเลือกการตลาดดิจิทัล มีวิชาอะไรบ้าง ขอเป็นรหัสวิชา", "กลุ่มการตลาดดิจิทัลมีกี่วิชา", "กลุ่มวิชาการตลาดดิจิทัล ต้องเลือกรวมกี่หน่วยกิต"])
def test_an_explicit_group_name_is_a_group_question_even_when_a_plan_course_has_the_same_name(tmp_path, question):
    with closing(_same_name_group_db(tmp_path)) as c:
        r = m._elective_group_answer(c, question)
    assert r and "06036116" not in r[0]


@pytest.mark.parametrize("question", [
    "การตลาดดิจิทัลมีวิชาอะไรบ้าง", "วิชาการตลาดดิจิทัลมีกี่หน่วยกิต", "วิชาการตลาดดิจิทัลอยู่ในกลุ่มวิชาอะไร", "วิชาการตลาดดิจิทัลเป็นวิชาเลือกหรือเปล่า"])
def test_the_same_name_without_an_explicit_group_word_is_about_the_course(tmp_path, question):
    with closing(_same_name_group_db(tmp_path)) as c:
        assert m._elective_group_answer(c, question) is None


# =============== ชุดหลอก (subagent เขียน 84 ข้อ ตั้งใจให้ทางลัดตอบผิด): ถูก 57 → จัด 7 กลุ่ม ===============
# P1 ทางลัดตอบผิด: _catalog_course_answer จับชื่อสั้นในชื่อยาว, ชั่วโมงต่ำสุด "ที่ไม่ใช่ศูนย์"
# P2 โมเดลตอบผิดเพราะไม่มีทางลัด: ผลรวมหน่วยกิตรายปี, เทอมเดียวกับ X, ภาคฤดูร้อนที่เล่มไม่มี, ชื่อวิชาที่ไม่มีจริง (ตัวขยาย/ลำดับที่ไม่มี), เลือกหรือบังคับ, สองวิชา

@pytest.mark.parametrize("rel,question", [
    ("DSBA/coop", "การเรียนรู้ของเครื่องขั้นสูง กี่หน่วยกิต"), ("DSBA/no_coop", "การเรียนรู้เชิงลึกขั้นสูง รหัสวิชาอะไร")])
def test_catalog_shortcut_does_not_answer_a_longer_unknown_name_as_the_shorter_catalog_course(rel, question):
    with closing(_real(rel)) as c:
        r = m._catalog_course_answer(c, question)
        assert r is None, (question, r and r[0])


@pytest.mark.parametrize("rel,question", [
    ("AIT", "วิชาปฏิบัติการแคลคูลัส 1 มีกี่หน่วยกิต"), ("BIT/coop", "วิชาปฏิบัติการพื้นฐานการเขียนโปรแกรม มีชั่วโมงบรรยายกี่ชั่วโมง"),
    ("DSBA/coop", "การเรียนรู้ของเครื่องขั้นสูง กี่หน่วยกิต"), ("DSBA/no_coop", "การเรียนรู้เชิงลึกขั้นสูง รหัสวิชาอะไร"),
    ("DSBA/no_coop", "วิชาปฏิบัติการการวิเคราะห์ข้อมูลและการโปรแกรม มีกี่หน่วยกิต"), ("IT/coop", "การเขียนโปรแกรมเชิงฟังก์ชันขั้นสูง กี่หน่วยกิต"),
    ("IT/no_coop", "การออกแบบส่วนต่อประสานกับมนุษย์ขั้นสูง รหัสวิชาอะไร"), ("IT/no_coop", "ปฏิบัติการโครงสร้างข้อมูลและอัลกอริทึม กี่หน่วยกิต"),
    ("BIT/no_coop", "ภาษาอังกฤษพื้นฐาน 3 กี่หน่วยกิต")])
def test_a_course_that_is_not_in_the_book_is_reported_as_not_found(rel, question):
    with closing(_real(rel)) as c:
        r = _chain(c, question)
    assert r and "ไม่พบ" in r[0] and r[1] == [], (question, r and r[0])


@pytest.mark.parametrize("rel,question,must", [
    ("AIT", "แคลคูลัส 1 กี่หน่วยกิต", "3 หน่วยกิต"), ("BIT/no_coop", "ภาษาอังกฤษพื้นฐาน 2 กี่หน่วยกิต", "หน่วยกิต"),
    ("DSBA/coop", "การเรียนรู้ของเครื่องเชิงประยุกต์ กี่หน่วยกิต", "06026")])
def test_real_course_names_are_still_answered(rel, question, must):
    with closing(_real(rel)) as c:
        r = _chain(c, question)
    assert r and must in r[0] and "ไม่พบ" not in r[0], (question, r and r[0])


@pytest.mark.parametrize("rel,expected", [("AIT", "2"), ("BIT/coop", "1"), ("DSBA/coop", "1"), ("IT/coop", "1"), ("IT/no_coop", "1")])
def test_lowest_non_zero_lecture_hours(rel, expected):
    with closing(_real(rel)) as c:
        r = m._extreme_hours_answer(c, "ชั่วโมงบรรยายน้อยที่สุดที่ไม่ใช่ศูนย์ของวิชาในแผนคือกี่ชั่วโมง")
    assert r and f"{expected} ชั่วโมง" in r[0] and all(row["lecture_h"] > 0 for row in r[1])


@pytest.mark.parametrize("rel,question,expected", [
    ("DSBA/coop", "ปี 1 เรียนรวมกี่หน่วยกิต", "39"), ("IT/coop", "ปี 4 เรียนรวมกี่หน่วยกิต", "33"), ("AIT", "ปีสุดท้ายต้องเรียนรวมกี่หน่วยกิต", "18"),
    ("AIT", "ปีแรกเรียนทั้งหมดกี่หน่วยกิต", "34")])
def test_year_credit_totals_follow_the_book_term_totals(rel, question, expected):
    with closing(_real(rel)) as c:
        r = _chain(c, question)
    assert r and f"{expected} หน่วยกิต" in r[0] and any(str(v) == expected for row in r[1] for v in row.values()), (question, r and r[0])


@pytest.mark.parametrize("question", [
    "ปี 1 เทอม 1 เรียนรวมกี่หน่วยกิต", "ปี 1 มีวิชาที่ได้ 1 หน่วยกิตกี่วิชา", "ปี 1 กับปี 2 เรียนรวมกี่หน่วยกิต", "ปี 1 เรียนวิชาอะไรบ้าง"])
def test_year_credit_shortcut_leaves_terms_lists_and_several_years_alone(question):
    with closing(_real("DSBA/coop")) as c:
        assert m._year_credits_answer(c, question) is None, question


@pytest.mark.parametrize("rel,question", [
    ("BIT/no_coop", "ภาคฤดูร้อนเรียนกี่หน่วยกิต"), ("DSBA/no_coop", "ภาคฤดูร้อนเรียนกี่หน่วยกิต"), ("IT/no_coop", "ภาคฤดูร้อนต้องลงทะเบียนกี่หน่วยกิต"),
    ("AIT", "ซัมเมอร์มีวิชาอะไรบ้าง")])
def test_a_summer_term_the_plan_does_not_have_is_reported_as_not_found(rel, question):
    with closing(_real(rel)) as c:
        r = _chain(c, question)
    assert r and "ไม่พบ" in r[0] and r[1] == [], (question, r and r[0])


@pytest.mark.parametrize("rel,question,expected", [
    ("BIT/coop", "เทอมเดียวกับเทคโนโลยีกลุ่มเมฆ มีวิชาอะไรอีกบ้าง", ["06036107", "06036110", "06036114", "06036121"]),
    ("DSBA/coop", "เทอมเดียวกับระบบข้อมูลมหัต มีวิชาอะไรอีกบ้าง", ["06026214", "06066100", "90643021"])])
def test_the_other_courses_in_the_same_term_as_a_named_course(rel, question, expected):
    with closing(_real(rel)) as c:
        r = _chain(c, question)
    assert r and sorted(row["code"] for row in r[1]) == expected, (question, r and r[0])


@pytest.mark.parametrize("question", [
    "วิชาที่เรียนเทอมเดียวกับแคลคูลัส 1 มีกี่หน่วยกิต", "เทอมเดียวกับแคลคูลัส 1 กับแคลคูลัส 2 มีวิชาอะไร"])
def test_same_term_shortcut_declines_other_relational_questions(question):
    with closing(_real("DSBA/coop")) as c:
        assert m._same_term_answer(c, question) is None, question


@pytest.mark.parametrize("rel,question", [
    ("BIT/no_coop", "ผู้ประกอบการสมัยใหม่ เป็นวิชาเลือกหรือบังคับ"), ("IT/no_coop", "คอมพิวเตอร์กราฟิกส์และแอนิเมชัน เป็นวิชาเลือกหรือบังคับ")])
def test_elective_or_required_comes_from_the_plan_note(rel, question):
    with closing(_real(rel)) as c:
        r = _chain(c, question)
    assert r and any(row.get("kind") == "เลือก" for row in r[1]) and "เลือก" in r[0], (question, r and r[0])


def test_required_course_is_reported_as_required():
    with closing(_real("DSBA/coop")) as c:
        r = _chain(c, "แคลคูลัส 1 เป็นวิชาบังคับหรือวิชาเลือก")
    assert r and any(row.get("kind") == "บังคับ" for row in r[1])


@pytest.mark.parametrize("rel,question,fragments", [
    ("BIT/no_coop", "ภาษาอังกฤษพื้นฐาน 1 และ 2 รวมกันกี่หน่วยกิต", ["6 หน่วยกิต"]),
    ("DSBA/coop", "รหัสวิชาแคลคูลัส 1 และ 2", ["06026200", "06026201"]),
    ("DSBA/coop", "แคลคูลัส 1 กับแคลคูลัส 2 เรียนปีไหน", ["ปี 1"])])
def test_two_named_courses_are_each_answered(rel, question, fragments):
    with closing(_real(rel)) as c:
        r = _chain(c, question)
    assert r and all(f in r[0] for f in fragments), (question, r and r[0])


@pytest.mark.parametrize("question", [
    "แคลคูลัส 1 กับแคลคูลัส 2 ต่างกันอย่างไร", "แคลคูลัส 1 และพีชคณิตเชิงเส้นเรียนเกี่ยวกับอะไร", "แคลคูลัส 1 และวิชาที่ต่อจากแคลคูลัส 1 กี่หน่วยกิต"])
def test_two_course_shortcut_declines_comparisons_and_descriptions(question):
    with closing(_real("DSBA/coop")) as c:
        assert m._multi_course_answer(c, question) is None, question


def test_a_summed_credit_answer_also_carries_the_total_in_its_rows():
    with closing(_real("BIT/no_coop")) as c:
        r = _chain(c, "ภาษาอังกฤษพื้นฐาน 1 และ 2 รวมกันกี่หน่วยกิต")
    assert r and "รวม 6 หน่วยกิต" in r[0] and any(str(v) == "6" for row in r[1] for v in row.values())


# =============== ปี/เทอมเดียว: "ต้องลงทะเบียนกี่วิชา" / "รวมกี่หน่วยกิต" — โมเดลแกว่ง 1 ใน ~160 ครั้ง (ตอบ 2 แทน 4) → ตายตัวตามยอดรายเทอมของเล่ม ===============

def _ask_term_total(tmp_path, monkeypatch, question):
    path = tmp_path / "t.db"
    path.unlink(missing_ok=True)
    c = _plan_db(path)
    c.executescript(m.PLAN_SLOT_DDL)                         # view v_semester_credits_full (นับตามเล่ม)
    c.commit()
    c.close()
    calls = []
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: calls.append(1) or '{"sql": "SELECT 1"}')
    with closing(m.open_db(path, readonly=True)) as conn:
        r = m.ask(conn, question, verbose=False)
    r["model_calls"] = len(calls)
    return r


@pytest.mark.parametrize("question,needle", [
    ("ปี 2 เทอม 1 ต้องลงทะเบียนกี่วิชา", "2 วิชา"), ("ภาคเรียนที่ 1 ของชั้นปีที่ 2 มีรายวิชาทั้งหมดกี่วิชา", "2 วิชา"),
    ("ปี 2 เทอม 1 รวมกี่หน่วยกิต", "6 หน่วยกิต"), ("ชั้นปีที่ 3 ภาคการศึกษาที่ 2 มีหน่วยกิตรวมเท่าไร", "3 หน่วยกิต"),
    ("ปี 3 ภาค 2 มีกี่วิชา", "1 วิชา")])
def test_term_totals_come_from_the_book_term_view_without_the_model(tmp_path, monkeypatch, question, needle):
    r = _ask_term_total(tmp_path, monkeypatch, question)
    assert needle in r["answer"] and r["model_calls"] == 0 and len(r["rows"]) == 1


@pytest.mark.parametrize("question", [
    "ปี 2 เทอม 1 มีกี่หน่วยกิต และมีวิชาอะไรบ้าง", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง ขอเป็นรหัสวิชา", "ปี 2 เทอม 1 กับปี 3 เทอม 2 รวมกี่หน่วยกิต",
    "ปี 9 เทอม 1 ต้องลงทะเบียนกี่วิชา", "วิชาแคลคูลัส 1 ปี 2 เทอม 1 กี่หน่วยกิต", "ปี 2 เทอม 1 วิชาไหนมีหน่วยกิตมากที่สุด", "ปี 2 เทอม 1 มีกี่วิชาที่ได้ 3 หน่วยกิต"])
def test_term_total_shortcut_leaves_lists_compounds_missing_terms_and_courses_alone(tmp_path, monkeypatch, question):
    assert _ask_term_total(tmp_path, monkeypatch, question)["model_calls"] >= 1 or "ไม่พบ" in _ask_term_total(tmp_path, monkeypatch, question)["answer"]


def test_gold_term_total_questions_taken_by_the_shortcut_match_the_gold_values():
    taken = 0
    for rel, gold in (("DSBA/coop", "dsba_coop"), ("DSBA/no_coop", "dsba_no_coop"), ("AIT", "ait"), ("IT/coop", "it_coop"),
                      ("IT/no_coop", "it_no_coop"), ("BIT/coop", "bit_coop"), ("BIT/no_coop", "bit_no_coop")):
        db = RUNS / rel / "lab8b_output" / "curriculum.db"
        if not db.exists():
            continue
        qs = json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8"))
        with closing(m.open_db(db, readonly=True)) as conn:
            for q in qs:
                r = m._term_total_answer(conn, q["question"])
                if r is None:
                    continue
                taken += 1
                ok, why = m.score_one(q["expect"], {"rows": r[1]}, question=q["question"])
                assert ok, (rel, q["id"], q["question"], r[0], q["expect"], why)
    assert taken >= 20


# บั๊กเก่าที่เพิ่งเห็น: "ปี 2 เทอม 1 วิชาไหนมีหน่วยกิตมากที่สุด" ถูกตอบเป็น "เทอมที่เรียนมากที่สุดคือ…" (ถามวิชา ตอบเทอม)
@pytest.mark.parametrize("question", [
    "ปี 2 เทอม 1 วิชาไหนมีหน่วยกิตมากที่สุด", "ปี 1 วิชาอะไรหน่วยกิตน้อยที่สุด", "เทอม 1 วิชาใดเรียนหนักที่สุด"])
def test_a_question_about_which_course_is_not_answered_with_which_term(question):
    with closing(_real("DSBA/coop")) as c:
        assert m._extreme_credits_answer(c, question) is None, question


@pytest.mark.parametrize("question", ["เทอมไหนเรียนหน่วยกิตมากที่สุด", "ปีไหนเรียนหนักที่สุด", "ปี 3 เทอมไหนเรียนหน่วยกิตน้อยที่สุด"])
def test_which_term_or_year_questions_are_still_answered(question):
    with closing(_real("DSBA/coop")) as c:
        assert m._extreme_credits_answer(c, question) is not None, question


# ---- ทางลัด "นับคู่วิชาบังคับก่อนทั้งหมด" (ปี/ชื่อวิชา/รหัส/ควบ/ต่อเนื่อง = ปฏิเสธ) ----
_ALL_PROGRAMS = ("AIT", "BIT/coop", "BIT/no_coop", "DSBA/coop", "DSBA/no_coop", "IT/coop", "IT/no_coop")
_PAIR_QUESTIONS = [
    "ในฐานข้อมูลนี้มีคู่วิชากับวิชาบังคับก่อนทั้งหมดกี่คู่", "ความสัมพันธ์วิชาบังคับก่อนมีทั้งหมดกี่คู่",
    "หลักสูตรนี้มีวิชาที่ต้องเรียนวิชาอื่นก่อนทั้งหมดกี่คู่", "มีวิชาที่ต้องผ่านวิชาอื่นก่อนทั้งหมดกี่คู่คะ",
    "วิชาที่มีเงื่อนไขต้องเรียนก่อน มีทั้งหมดกี่ความสัมพันธ์", "สรุปให้หน่อย มีวิชาบังคับก่อนรวมกันกี่คู่"]


@pytest.mark.parametrize("rel", _ALL_PROGRAMS)
@pytest.mark.parametrize("question", _PAIR_QUESTIONS)
def test_counting_all_prerequisite_pairs_is_answered_from_the_table(rel, question):
    with closing(_real(rel)) as c:
        n = c.execute("SELECT COUNT(*) FROM prerequisite WHERE kind = 'pre'").fetchone()[0]
        r = _chain(c, question)
        assert r is not None and r[0].startswith(f"{n} คู่"), (rel, question, r)
        assert r[1] == [{"pairs": n}] and "kind = 'pre'" in r[2]


def test_the_gold_pair_count_questions_pass_with_the_shortcut():
    taken = 0
    for rel, gold in (("DSBA/coop", "dsba_coop"), ("DSBA/no_coop", "dsba_no_coop"), ("AIT", "ait"), ("IT/coop", "it_coop"),
                      ("IT/no_coop", "it_no_coop"), ("BIT/coop", "bit_coop"), ("BIT/no_coop", "bit_no_coop")):
        db = RUNS / rel / "lab8b_output" / "curriculum.db"
        if not db.exists():
            continue
        qs = json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8"))
        with closing(m.open_db(db, readonly=True)) as conn:
            for q in qs:
                if "คู่" not in q["question"] or "บังคับก่อน" not in q["question"]:
                    continue
                r = _chain(conn, q["question"])
                assert r is not None, (rel, q["question"])
                taken += 1
                ok, why = m.score_one(q["expect"], {"rows": r[1]}, question=q["question"])
                assert ok, (rel, q["id"], q["question"], r[0], q["expect"], why)
    assert taken >= 1


# ทุกข้อนี้ไม่ใช่ "นับคู่ทั้งหมด": มีปี/เทอม รหัส ชื่อวิชา เรียนควบ ต่อเนื่อง ขอรายชื่อ ไม่มี หรือถามจำนวนวิชา (ไม่ใช่คู่) — ต้องปล่อยทางอื่น
@pytest.mark.parametrize("question", [
    "ปี 2 มีวิชาที่ต้องเรียนก่อนกี่คู่", "ปี 1 เทอม 2 มีวิชาบังคับก่อนกี่คู่", "วิชา 06026201 มีวิชาบังคับก่อนกี่คู่",
    "วิชาแคลคูลัส 2 มีวิชาบังคับก่อนกี่คู่", "ทั้งหลักสูตรมีวิชาที่ต้องเรียนต่อเนื่องกันกี่คู่", "มีวิชาที่ต้องเรียนควบกันกี่คู่",
    "วิชาบังคับก่อนมีคู่ไหนบ้าง", "ขอรายชื่อคู่วิชาบังคับก่อนทั้งหมด", "มีวิชาที่ไม่มีวิชาบังคับก่อนกี่คู่",
    "มีวิชาที่มีวิชาบังคับก่อนกี่วิชา", "คู่วิชาบังคับก่อนคู่ไหนมากที่สุด", "ถ้าไม่ผ่านวิชาบังคับก่อนแล้วต้องทำอย่างไร",
    "มีกี่คู่", "คู่วิชาบังคับก่อนของ IT กับ DSBA ต่างกันกี่คู่"])
def test_pair_count_shortcut_refuses_everything_that_is_not_the_whole_count(question):
    with closing(_real("DSBA/coop")) as c:
        assert m._prereq_pair_count_answer(c, question) is None, question


# ---- คำถามกำกวม "ต่อเนื่อง" / วิชาเรียนควบ: ไม่เดา ----
# ตารางไม่มีแถว kind='co' เลยทั้ง 7 แผน (ตัวสกัดใส่แต่ 'pre') → "0 วิชาเรียนควบ" แปลว่า "ไม่ได้สกัด" ไม่ใช่ "เล่มไม่มี" จึงต้องไม่ตอบ 0
_AMBIGUOUS = [
    "ทั้งหลักสูตรมีวิชาที่ต้องเรียนต่อเนื่องกันกี่คู่", "มีวิชาที่เรียนต่อเนื่องกันกี่ความสัมพันธ์", "วิชาที่ต้องเรียนต่อเนื่องกันมีกี่คู่"]
_COREQ = [
    "มีวิชาที่ต้องลงทะเบียนเรียนควบคู่กันกี่คู่", "มีวิชาไหนบ้างที่ต้องเรียนควบกับวิชาอื่น", "วิชาเรียนควบมีทั้งหมดกี่คู่",
    "วิชาที่ต้องลงทะเบียนควบกันมีอะไรบ้าง"]


@pytest.mark.parametrize("rel", ("DSBA/coop", "IT/no_coop", "AIT"))
@pytest.mark.parametrize("question", _AMBIGUOUS)
def test_ambiguous_continuity_question_asks_which_meaning_instead_of_guessing(rel, question):
    with closing(_real(rel)) as c:
        r = _chain(c, question)
        assert r is not None and "วิชาบังคับก่อน" in r[0] and "วิชาเรียนควบ" in r[0] and r[1] == [], (question, r)
        assert not re.search(r"\d", r[0])                       # ไม่ใส่ตัวเลขที่อาจถูกตรวจเป็นคำตอบ


@pytest.mark.parametrize("rel", ("DSBA/coop", "IT/no_coop", "AIT"))
@pytest.mark.parametrize("question", _COREQ)
def test_corequisite_question_is_not_answered_with_zero_from_an_unextracted_table(rel, question):
    with closing(_real(rel)) as c:
        r = _chain(c, question)
        assert r == m._NOT_FOUND, (question, r)


# ห้ามแย่งคำถามอื่นที่มีคำใกล้เคียง: วิชา "คณิตศาสตร์ไม่ต่อเนื่อง" (06066000) "ควบคุม" "ต่อเนื่อง" ในบริบทอื่น
@pytest.mark.parametrize("question", [
    "คณิตศาสตร์ไม่ต่อเนื่องมีกี่หน่วยกิต", "วิชาคณิตศาสตร์ไม่ต่อเนื่องมีวิชาบังคับก่อนกี่คู่", "ปี 1 เทอม 2 เรียนต่อเนื่องกันกี่วิชา",
    "การควบคุมคุณภาพอยู่ปีไหน", "ในฐานข้อมูลนี้มีคู่วิชากับวิชาบังคับก่อนทั้งหมดกี่คู่", "วิชา 06066000 มีวิชาบังคับก่อนกี่คู่"])
def test_continuity_and_corequisite_guards_leave_other_questions_alone(question):
    with closing(_real("DSBA/coop")) as c:
        assert m._prereq_ambiguity_answer(c, question) is None, question


def test_no_gold_question_is_taken_by_the_ambiguity_guard():
    for gold, rel in (("dsba_coop", "DSBA/coop"), ("it_no_coop", "IT/no_coop"), ("ait", "AIT"), ("bit_coop", "BIT/coop")):
        qs = json.loads((REPO / "Lab9_evaluation" / "gold_questions" / f"{gold}_gold_questions.json").read_text(encoding="utf-8"))
        with closing(_real(rel)) as c:
            assert [q["id"] for q in qs if m._prereq_ambiguity_answer(c, q["question"])] == []
