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
    assert counts == {"primary": 1, "description": 0, "other": 1, "plan": 1}


# Break caught: storing a misread printed page number (raw printed_page instead of consistent_printed).
def test_load_course_pages_stores_null_for_misread_printed_number():
    conn = _db()
    ocr = [dict(p) for p in OCR]
    ocr[1] = {"page": "38", "text": "27\nปีที่ 1 ภาคการศึกษาที่ 1\n06016401 คณิตศาสตร์ 3(3-0-6)"}
    lab8b.load_course_pages(conn, ocr, ["it_curriculum_page_038.jpg"], MD)
    printed = {tuple(r) for r in conn.execute("SELECT pdf_page, printed_page FROM course_page WHERE pdf_page = 38")}
    assert printed == {(38, None)}


# Break caught: load_course_pages not passing the book OCR to plan_pages (contradicted plan page still cited).
def test_load_course_pages_skips_plan_page_contradicted_by_book_heading():
    conn = _db()
    ocr = [dict(p) for p in OCR]
    ocr[1] = {"page": "38", "text": "33\nปีที่ 3 ภาคการศึกษาที่ 2\n06016401 คณิตศาสตร์ 3(3-0-6)"}
    counts = lab8b.load_course_pages(conn, ocr, ["it_curriculum_page_038.jpg"], MD)
    assert counts["plan"] == 0


# Break caught (final review #2): term pages rebuilt by joining plan rows on course code — a code planned in
# two terms would get term A's page cited for term B.
def test_term_page_not_leaked_to_other_term_sharing_a_code():
    import citations
    conn = _db()
    conn.execute("INSERT INTO plan_item (program_id, year, semester, code, credits) VALUES ('X', 1, 2, '06016401', 3)")
    lab8b.load_course_pages(conn, OCR, ["it_curriculum_page_038.jpg"], MD)
    lookup = citations.load_lookup(conn)
    sql_1_2 = "SELECT credits FROM v_semester_credits WHERE year=1 AND semester=2"
    assert citations.citations_for([{"credits": 3}], sql_1_2, lookup) == []
    sql_1_1 = "SELECT credits FROM v_semester_credits WHERE year=1 AND semester=1"
    assert citations.citations_for([{"credits": 3}], sql_1_1, lookup) == [{"pdf_page": 38, "printed_page": "33", "courses": []}]


# Break caught (review minor #7): a run without data_input aborting the whole run instead of skipping citations.
def test_cmd_load_course_pages_skips_with_message_when_inputs_missing(tmp_path, capsys):
    import argparse
    db = tmp_path / "c.db"
    lab8b.open_db(str(db)).close()
    args = argparse.Namespace(database=str(db), ocr_json=str(tmp_path / "none.json"),
                              data_input=str(tmp_path / "no_dir"), markdown=str(tmp_path / "none.md"))
    lab8b.cmd_load_course_pages(args)
    assert "ข้าม" in capsys.readouterr().out


def _pair_db():
    conn = _db()
    conn.executescript(lab8b.COURSE_PAGE_DDL)
    conn.execute("INSERT INTO course (code, name_th, credits) VALUES ('06016402', 'โปรแกรมมิ่ง', 3)")
    conn.execute("INSERT INTO prerequisite VALUES ('06016402', '06016401', 'pre')")
    conn.execute("INSERT INTO course_page VALUES ('06016402', 90, '86', 'description')")
    conn.execute("INSERT INTO course_page VALUES ('06016401', 38, '33', 'plan')")
    return conn


# Break caught: counting all prerequisite pairs answered with no page (the pairs are read from the course-description pages).
def test_pair_count_cites_description_pages_of_courses_that_have_a_prerequisite():
    conn = _pair_db()
    res = {"question": "ความสัมพันธ์วิชาบังคับก่อนมีทั้งหมดกี่คู่", "rows": [{"n": 1}],
           "sql": "SELECT COUNT(*) FROM prerequisite WHERE kind='pre'"}
    lab8b._attach_citations(conn, res)
    assert [c["pdf_page"] for c in res["citations"]] == [90]
    assert res["citations"][0]["courses"] == ["06016402"]


# Break caught: guessing a page when no description page is known for the pair's course.
def test_pair_count_cites_nothing_without_description_pages():
    conn = _pair_db()
    conn.execute("DELETE FROM course_page WHERE kind='description'")
    res = {"question": "มีกี่คู่", "rows": [{"n": 1}], "sql": "SELECT COUNT(*) FROM prerequisite"}
    lab8b._attach_citations(conn, res)
    assert res["citations"] == []


# Break caught: the 4-page cap dropping courses from the pair-count citation (IT cited 6 of 8 courses) — every course with a prerequisite row must be cited.
def test_pair_count_cites_every_course_with_a_prerequisite_without_a_page_cap():
    conn = _pair_db()
    for i in range(10):
        code = f"0602620{i}"
        conn.execute("INSERT INTO course (code, name_th, credits) VALUES (?, ?, 3)", (code, f"วิชา{i}"))
        conn.execute("INSERT INTO prerequisite VALUES (?, '06016401', 'pre')", (code,))
        conn.execute("INSERT INTO course_page VALUES (?, ?, NULL, 'description')", (code, 100 + i))
    res = {"question": "มีกี่คู่", "rows": [{"n": 11}], "sql": "SELECT COUNT(*) FROM prerequisite"}
    lab8b._attach_citations(conn, res)
    cited = {c for cit in res["citations"] for c in cit["courses"]}
    assert cited == {"06016402"} | {f"0602620{i}" for i in range(10)}
    assert [c["pdf_page"] for c in res["citations"]] == sorted(c["pdf_page"] for c in res["citations"])
