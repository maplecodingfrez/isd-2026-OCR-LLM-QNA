import sqlite3

import lab8b_curriculum_db as lab8b


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(lab8b.DDL)
    conn.execute("INSERT INTO program VALUES ('X', 'หลักสูตรทดสอบ', NULL, NULL, 120, 4)")
    conn.execute("INSERT INTO course (code, name_th, credits) VALUES ('06016401', 'คณิตศาสตร์', 3)")
    conn.execute("INSERT INTO plan_item (program_id, year, semester, code, credits) VALUES ('X', 1, 1, '06016401', 3)")
    return conn


# Neighbouring pages carry consecutive printed numbers, as in a real book (consistent_printed needs them).
OCR = [{"page": "37", "text": "32\nมคอ.2"},
       {"page": "38", "text": "33\nปีที่ 1 ภาคการศึกษาที่ 1\n06016401 คณิตศาสตร์ 3(3-0-6)"},
       {"page": "89", "text": "85\nมคอ.2"},
       {"page": "90", "text": "86\n06016401 ในภาคผนวก"}]
MD = "ปีที่ 1 ภาคการศึกษาที่ 1\n<table>06016401</table>"


# Break caught: plan rows not written per plan_item code, or rerun duplicating rows.
def test_load_course_pages_writes_course_and_plan_rows_and_is_rerunnable():
    conn = _db()
    for _ in range(2):
        counts = lab8b.load_course_pages(conn, OCR, ["it_curriculum_page_038.jpg"], MD)
    rows = [tuple(r) for r in conn.execute(
        "SELECT code, pdf_page, printed_page, kind FROM course_page ORDER BY kind, pdf_page")]
    assert rows == [("06016401", 90, "86", "other"), ("06016401", 38, "33", "plan"),
                    ("06016401", 38, "33", "primary")]
    assert counts == {"primary": 1, "other": 1, "plan": 1}


# Break caught: storing a misread printed page number (raw printed_page instead of consistent_printed).
def test_load_course_pages_stores_null_for_misread_printed_number():
    conn = _db()
    ocr = [dict(p) for p in OCR]
    ocr[1] = {"page": "38", "text": "27\nปีที่ 1 ภาคการศึกษาที่ 1\n06016401 คณิตศาสตร์ 3(3-0-6)"}
    lab8b.load_course_pages(conn, ocr, ["it_curriculum_page_038.jpg"], MD)
    printed = {tuple(r) for r in conn.execute("SELECT pdf_page, printed_page FROM course_page WHERE pdf_page = 38")}
    assert printed == {(38, None)}
