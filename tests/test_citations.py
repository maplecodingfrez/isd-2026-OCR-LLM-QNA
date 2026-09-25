import citations


# Break caught: only accepting a bare number line (AIT pages start "19   รายละเอียดหลักสูตร").
def test_printed_page_reads_number_at_start_of_first_line():
    assert citations.printed_page("33\nมคอ.2\nปีที่ 1") == "33"
    assert citations.printed_page("\n  19                รายละเอียดหลักสูตร\n3.3") == "19"


# Break caught: returning a number from a later line when the header is not a page number.
def test_printed_page_none_when_first_line_is_not_a_number():
    assert citations.printed_page("มคอ.2\n33") is None
    assert citations.printed_page("") is None


# Break caught: kind decided without looking at the name (all pages "primary").
def test_course_pages_primary_when_name_on_page_else_other():
    pages = [
        {"page": "38", "text": "33\nมคอ.2\n06016401 คณิตศาสตร์สำหรับเทคโนโลยีสารสนเทศ 3(3-0-6)"},
        {"page": "84", "text": "80\nมคอ.2\nรายวิชา 06016401 และ 06016402"},
        {"page": "90", "text": "86\nไม่มีรหัสวิชาในหน้านี้"},
    ]
    courses = [{"code": "06016401", "name_th": "คณิตศาสตร์สำหรับ เทคโนโลยีสารสนเทศ", "name_en": None}]
    assert citations.course_pages(pages, courses) == [
        {"code": "06016401", "pdf_page": 38, "printed_page": "33", "kind": "primary"},
        {"code": "06016401", "pdf_page": 84, "printed_page": "80", "kind": "other"},
    ]


# Break caught: matching a code inside a longer digit run (Review Focus 5).
def test_course_pages_ignores_code_inside_longer_number():
    pages = [{"page": "5", "text": "1\nโทร 0601640123 ต่อ 2"}]
    courses = [{"code": "06016401", "name_th": "วิชาก", "name_en": None}]
    assert citations.course_pages(pages, courses) == []


# Break caught: English-name match not used (Thai name garbled by OCR, English intact).
def test_course_pages_primary_by_english_name():
    pages = [{"page": "7", "text": "3\n06016409 กํารประมวล PHYSICAL  COMPUTING 3(2-2-5)"}]
    courses = [{"code": "06016409", "name_th": "การประมวลผลทางกายภาพ", "name_en": "Physical Computing"}]
    assert citations.course_pages(pages, courses)[0]["kind"] == "primary"


# Break caught: pairing chunks with images in directory order instead of page order.
def test_plan_pages_pairs_chunks_with_pages_in_page_order():
    md = "ปีที่ 1 ภาคการศึกษาที่ 1\n<table>..</table>\n---\nปีที่ 1 ภาคการศึกษาที่ 2\n<table>..</table>"
    got = citations.plan_pages(["x_page_039.jpg", "x_page_038.jpg"], md, {38: "33", 39: "34"})
    assert got == [
        {"year": 1, "semester": 1, "pdf_page": 38, "printed_page": "33"},
        {"year": 1, "semester": 2, "pdf_page": 39, "printed_page": "34"},
    ]


# Break caught: a table continuing on the next page is not credited to its term (Review Focus 3).
def test_plan_pages_continuation_page_belongs_to_previous_term():
    md = ("ปีที่ 3 ภาคการศึกษาที่ 1\n<table>..</table>\nปีที่ 3 ภาคการศึกษาที่ 2\n<table>..\n"
          "---\n<table>..รวม 15</table>")
    got = citations.plan_pages(["AIT_036.jpg", "AIT_037.jpg"], md, {36: None, 37: None})
    assert got == [
        {"year": 3, "semester": 1, "pdf_page": 36, "printed_page": None},
        {"year": 3, "semester": 2, "pdf_page": 36, "printed_page": None},
        {"year": 3, "semester": 2, "pdf_page": 37, "printed_page": None},
    ]


# Break caught: shifting every term onto the wrong page when counts disagree (Review Focus 4).
def test_plan_pages_empty_when_image_and_chunk_counts_differ():
    md = "ปีที่ 1 ภาคการศึกษาที่ 1\n<table/>\n---\nปีที่ 1 ภาคการศึกษาที่ 2\n<table/>"
    assert citations.plan_pages(["a_001.jpg"], md, {}) == []


# Break caught: citing a misread printed number (real case: IT PDF 42 read as "27", book offset is 5).
def test_consistent_printed_drops_numbers_off_the_book_offset():
    raw = {38: "33", 39: "34", 40: "35", 42: "27", 43: None}
    assert citations.consistent_printed(raw) == {38: "33", 39: "34", 40: "35", 42: None, 43: None}


# Break caught: a whole-book offset dropping correct numbers in sections that restart numbering
# (real: IT PDF 6-10 printed 1-5, BIT PDF 75-79 printed 10-14).
def test_consistent_printed_keeps_sections_with_their_own_numbering():
    raw = {6: "1", 7: "2", 8: "3", 38: "30", 39: "31", 40: "32", 41: "33"}   # offsets 5 (section) vs 8 (body)
    assert citations.consistent_printed(raw) == raw


import sqlite3  # noqa: E402

import lab8b_curriculum_db as lab8b  # noqa: E402


def _db_with_pages():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(lab8b.DDL)
    conn.executescript(lab8b.COURSE_PAGE_DDL)
    conn.execute("INSERT INTO program VALUES ('X', 'ท', NULL, NULL, 120, 4)")
    conn.execute("INSERT INTO course (code, name_th, credits) VALUES ('06016401', 'ก', 3)")
    conn.execute("INSERT INTO plan_item (program_id, year, semester, code, credits) VALUES ('X', 1, 1, '06016401', 3)")
    conn.executemany("INSERT INTO course_page VALUES (?, ?, ?, ?)", [
        ("06016401", 38, "33", "plan"), ("06016401", 324, "319", "primary"), ("06016401", 23, None, "other")])
    return conn


# Break caught: term questions (no code in rows) getting no citation.
def test_citations_for_term_question_cites_plan_page():
    lookup = citations.load_lookup(_db_with_pages())
    sql = "SELECT credits FROM v_semester_credits WHERE year=1 AND semester=1"
    assert citations.citations_for([{"credits": 18}], sql, lookup) == [{"pdf_page": 38, "printed_page": "33"}]


# Break caught: code taken only from rows (name lookup "WHERE code='X'" returns no code column).
def test_citations_for_code_in_sql_cites_plan_then_primary_not_other():
    lookup = citations.load_lookup(_db_with_pages())
    sql = "SELECT name_th FROM course WHERE code = '06016401'"
    assert citations.citations_for([{"name_th": "ก"}], sql, lookup) == [
        {"pdf_page": 38, "printed_page": "33"}, {"pdf_page": 324, "printed_page": "319"}]


# Break caught: guessing a page for an unknown code / no-pages DB (Review Focus 1).
def test_citations_empty_for_unknown_code_and_missing_table():
    lookup = citations.load_lookup(_db_with_pages())
    assert citations.citations_for([{"code": "99999999"}], "SELECT code FROM course", lookup) == []
    bare = sqlite3.connect(":memory:")
    assert citations.load_lookup(bare) is None


# Break caught: wrong format when the printed page is unknown.
def test_format_citation():
    assert citations.format_citation([]) == ""
    assert citations.format_citation([{"pdf_page": 38, "printed_page": "33"}, {"pdf_page": 23, "printed_page": None}]) == (
        "(อ้างอิง: เล่มหลักสูตร หน้า 33 (PDF 38), PDF 23)")
