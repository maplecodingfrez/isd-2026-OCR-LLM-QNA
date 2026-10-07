import pytest

import citations


def test_prerequisite_citations_cover_target_evidence_without_page_cap():
    import lab8b_curriculum_db as m
    with m.open_db(':memory:') as conn:
        conn.executescript(m.DDL + m.COURSE_PAGE_DDL)
        for n in range(1, 6):
            code = f'{n:08d}'
            conn.execute('INSERT INTO course(code,name_th,credits) VALUES (?,?,3)', (code, f'วิชา{n}'))
            conn.execute("INSERT INTO course_page VALUES (?, ?, NULL, 'description')", (code, 100+n))
            if n > 1:
                conn.execute("INSERT INTO prerequisite VALUES (?, '00000001', 'pre')", (code,))
        for sql, rows, expected in [
            ("SELECT code FROM prerequisite WHERE requires = '00000001'",
             [{'code': f'{n:08d}'} for n in range(2, 6)], [102,103,104,105]),
            ("SELECT requires FROM prerequisite WHERE code = '00000002'", [{'code': '00000001'}], [102]),
            ("SELECT requires FROM prerequisite WHERE code = 00000002", [{'requires': '00000001'}], [102]),
            ("SELECT requires FROM prerequisite WHERE code = '00000001'",
             [{'code':'00000001','requires':None}], [101]),
        ]:
            result = {'sql':sql, 'rows':rows}
            m._attach_citations(conn,result)
            assert [p['pdf_page'] for p in result['citations']] == expected
        conn.execute("INSERT INTO prerequisite VALUES ('00000001','00000005','pre')")
        result = {'sql':"SELECT COUNT(*) AS n FROM prerequisite WHERE requires='00000001'", 'rows':[{'n':4}]}
        m._attach_citations(conn,result)
        assert [p['pdf_page'] for p in result['citations']] == [102,103,104,105]
        result = {'sql':"SELECT COUNT(*) AS n FROM prerequisite WHERE requires='99999999'", 'rows':[{'n':0}]}
        m._attach_citations(conn,result)
        assert result['citations'] == []


def test_prerequisite_chain_citations_include_root_and_intermediate_edges():
    import lab8b_curriculum_db as m
    with m.open_db(':memory:') as conn:
        conn.executescript(m.DDL + m.COURSE_PAGE_DDL)
        for n in range(1, 4):
            conn.execute('INSERT INTO course(code,name_th,credits) VALUES (?,?,3)', (f'{n:08d}',f'วิชา{n}'))
            conn.execute("INSERT INTO course_page VALUES (?, ?, NULL, 'description')", (f'{n:08d}',100+n))
        conn.executemany("INSERT INTO prerequisite VALUES (?,?,'pre')",
                         [('00000003','00000002'),('00000002','00000001')])
        answer, rows, sql = m._prereq_chain_answer(conn,'วิชา 00000003 มีวิชาบังคับก่อนอะไรบ้าง ไล่ตั้งแต่ต้น')
        result = {'sql':sql,'rows':rows,'answer':answer}
        m._attach_citations(conn,result)
        assert {p['pdf_page'] for p in result['citations']} >= {102,103}


def test_description_locator_uses_verified_header_even_when_code_is_wrong():
    import lab8b_curriculum_db as m
    with m.open_db(':memory:') as conn:
        conn.executescript(m.DDL)
        conn.execute("INSERT INTO course(code,name_th,name_en,credits) VALUES ('00000002','วิชาสอง','SECOND COURSE',3)")
        pages = [{'page':5,'text':'4\n00000009 วิชาสอง 3(3-0-6)\nSECOND COURSE\nPREREQUISITE : NONE'},
                 {'page':6,'text':'5\nอื่น'}]
        m.load_course_pages(conn,pages,[],'')
        got = conn.execute("SELECT code,pdf_page,printed_page FROM course_page WHERE kind='description'").fetchall()
        assert [tuple(r) for r in got] == [('00000002',5,'4')]


# Break caught: only accepting a bare number line (AIT pages start "19   รายละเอียดหลักสูตร").
def test_printed_page_reads_number_at_start_of_first_line():
    assert citations.printed_page("33\nมคอ.2\nปีที่ 1") == "33"
    assert citations.printed_page("\n  19                รายละเอียดหลักสูตร\n3.3") == "19"


def test_plan_course_locator_does_not_copy_the_whole_term_to_each_page():
    import lab8b_curriculum_db as m
    with m.open_db(':memory:') as conn:
        conn.executescript(m.DDL)
        conn.execute("INSERT INTO program(program_id,name_th,total_credits,years) VALUES ('IT','IT',129,4)")
        for code in ('06016481','06016482'):
            conn.execute('INSERT INTO course(code,name_th,credits) VALUES (?,?,6)', (code,code))
            conn.execute("INSERT INTO plan_item(program_id,code,year,semester,credits) VALUES ('IT',?,3,2,6)", (code,))
        pages = [{'page':42,'text':'37\nปีที่ 3 ภาคการศึกษาที่ 2\n06016481'},
                 {'page':43,'text':'38\n06016482'}]
        md = 'ปีที่ 3 ภาคการศึกษาที่ 2\n<table>06016481</table>\n---\n<table>06016482</table>'
        m.load_course_pages(conn,pages,['IT_042.jpg','IT_043.jpg'],md)
        assert [tuple(r) for r in conn.execute("SELECT code,pdf_page FROM course_page WHERE kind='plan' ORDER BY code")] == [('06016481',42),('06016482',43)]


def test_catalog_citations_ship_in_database_without_local_book(tmp_path, monkeypatch):
    import json
    import lab8b_curriculum_db as m
    manifest = tmp_path / 'Lab7B_Lab8B_ocr_system/runs/AIT/electives.json'
    manifest.parent.mkdir(parents=True)
    courses = [{'code':'00000001','name_th':'วิชาแรก','name_en':'FIRST COURSE'}]
    manifest.write_text(json.dumps({'source':'PDF หน้า 21-22','groups':[{'courses':courses}]},ensure_ascii=False),encoding='utf-8')
    monkeypatch.setattr(m,'REPO_ROOT',tmp_path)
    with m.open_db(':memory:') as conn:
        conn.executescript(m.DDL)
        conn.execute("INSERT INTO program(program_id,name_th,total_credits,years) VALUES ('AIT','AIT',129,4)")
        pages = [{'page':20,'text':'16\nอื่น'}, {'page':21,'text':'17\n00000001 วิชาแรก 3(3-0-6)\nFIRST COURSE'},
                 {'page':22,'text':'18\nอื่น'}, {'page':100,'text':'99\n00000001 วิชาแรก\nFIRST COURSE'}]
        m.load_course_pages(conn,pages,[],'')
        rows = [{'code':'00000001'}]
        got = m._elective_catalog_citations(conn,rows,'SELECT code FROM v_elective_group','วิชาเลือกมีอะไรบ้าง')
        assert [(r['pdf_page'],r['printed_page'],r['courses']) for r in got] == [(21,'17',['00000001'])]
        assert got[0]['course_names_en'] == {'00000001':'FIRST COURSE'}
        conn.execute('DELETE FROM course_page')
        assert m._elective_catalog_citations(conn,rows,'SELECT code FROM v_elective_group','วิชาเลือกมีอะไรบ้าง') == []


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
def test_plan_pages_leading_continuation_before_new_term_heading():
    md = ('ปีที่ 3 ภาคการศึกษาที่ 2\n<table><tr><td>06016481</td></tr></table>\n---\n'
          '<table><tr><td>06016482</td></tr><tr><td>รวม</td></tr></table>\n'
          'ปีที่ 4 ภาคการศึกษาที่ 1\n<table><tr><td>06016407</td></tr></table>')
    book = {42: 'ปีที่ 3 ภาคการศึกษาที่ 2\n06016481',
            43: '06016482\nปีที่ 4 ภาคการศึกษาที่ 1\n06016407'}
    got = citations.plan_pages(['IT_042.png','IT_043.png'], md, {}, book)
    assert {(r['year'], r['semester'], r['pdf_page']) for r in got} == {(3,2,42),(3,2,43),(4,1,43)}
    # A different leading table without matching book codes cannot inherit the prior term.
    book[43] = 'ปีที่ 4 ภาคการศึกษาที่ 1\n06016407'
    got = citations.plan_pages(['IT_042.png','IT_043.png'], md, {}, book)
    assert (3,2,43) not in {(r['year'],r['semester'],r['pdf_page']) for r in got}


def test_confirmed_plan_printed_number_needs_neighbor_and_unique_tag():
    md = '<page_number>37</page_number>ปีที่ 3 ภาคการศึกษาที่ 2<table>06016481</table>'
    printed = {41:'36',42:None,43:'38'}
    book = {42:'ปีที่ 3 ภาคการศึกษาที่ 2\n06016481'}
    assert citations.plan_pages(['IT_042.jpg'],md,printed,book)[0]['printed_page'] == '37'
    assert citations.plan_pages(['IT_042.jpg'],md,{42:None},book)[0]['printed_page'] is None
    assert citations.plan_pages(['IT_042.jpg'],md.replace('37','27'),printed,book)[0]['printed_page'] is None
    assert citations.plan_pages(['IT_042.jpg'],md+'<page_number>38</page_number>',printed,book)[0]['printed_page'] is None
    assert citations.plan_pages(['IT_042.jpg'],md,printed,{42:'ไม่มีหลักฐาน'}) == []


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


def test_catalog_citations_cover_all_source_pages_without_description_or_appendix():
    courses = [{"code": "06026216", "name_th": "ก", "name_en": None},
               {"code": "06026230", "name_th": "ข", "name_en": None}]
    pages = [{"page": 19, "text": "18\n06026216 ก"}, {"page": 20, "text": "19\n06026230 ข"},
             {"page": 21, "text": "20\n06026216 ก"}, {"page": 22, "text": "21\n06026230 ข"}]
    got = citations.catalog_citations([{"code": c["code"]} for c in courses], courses, pages)
    assert [c["pdf_page"] for c in got] == [19, 20, 21, 22]
    assert got[0]["courses"] == ["06026216"]
    assert got[0]["course_names"] == {"06026216": "ก"}
    assert citations.catalog_citations([{"code": "99999999"}], courses, pages) == []


def test_catalog_citations_are_order_independent_and_require_actual_code_on_page():
    courses = [{"code": "06026216", "name_th": "ก"}, {"code": "06026230", "name_th": "ข"}]
    pages = [{"page": 19, "text": "18\nก ข ไม่มีรหัส"}, {"page": 20, "text": "19\n06026216 ก 06026230 ข"}]
    rows = [{"code": "06026216"}, {"code": "06026230"}]
    got = citations.catalog_citations(rows, courses, pages)
    assert got == citations.catalog_citations(list(reversed(rows)), courses, pages)
    assert [c["pdf_page"] for c in got] == [20]


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
    conn.execute("INSERT INTO term_page VALUES (1, 1, 38, '33')")
    return conn


# Break caught: term questions (no code in rows) getting no citation.
def test_citations_for_term_question_cites_plan_page():
    lookup = citations.load_lookup(_db_with_pages())
    sql = "SELECT credits FROM v_semester_credits WHERE year=1 AND semester=1"
    assert citations.citations_for([{"credits": 18}], sql, lookup) == [{"pdf_page": 38, "printed_page": "33", "courses": []}]


# Break caught: code taken only from rows (name lookup "WHERE code='X'" returns no code column).
def test_citations_for_code_in_sql_cites_plan_then_primary_not_other():
    lookup = citations.load_lookup(_db_with_pages())
    sql = "SELECT name_th FROM course WHERE code = '06016401'"
    assert citations.citations_for([{"name_th": "ก"}], sql, lookup) == [
        {"pdf_page": 38, "printed_page": "33", "courses": ["06016401"]},
        {"pdf_page": 324, "printed_page": "319", "courses": ["06016401"]}]


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
        "อ้างอิงเล่มหลักสูตร:\n• หน้า 33 (PDF 38)\n• PDF 23")


# Break caught (found in Task 6 on DSBA coop): image files numbered differently from the book PDF
# (DSBA_28.png is PDF 30) — the book's own OCR shows another term's heading there, so no plan page is cited,
# nor for the continuation page that would inherit the rejected term.
def test_plan_pages_drops_page_whose_book_heading_contradicts():
    md = "ปีที่ 1 ภาคการศึกษาที่ 1\n<table>a</table>\n---\n<table>b</table>\n---\nปีที่ 1 ภาคการศึกษาที่ 2\n<table>c</table>"
    book = {28: "27\nปีที่ 3 ภาคการศึกษาที่ 2\n...", 29: "28\nไม่มีหัวเทอม", 30: "29\nปีที่ 1 ภาคการศึกษาที่ 2"}
    got = citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], md, {}, book)
    assert [(t["year"], t["semester"], t["pdf_page"]) for t in got] == [(1, 2, 30)]


# Break caught (final review #1): a plan page accepted only because nothing contradicts it — a misnumbered
# image whose book page has no readable heading and none of the table's codes must not be cited.
def test_plan_pages_needs_positive_confirmation_from_book():
    md = "ปีที่ 1 ภาคการศึกษาที่ 1\n<table>06016401 06016402</table>\n---\n<table>06016403 06016404</table>"
    unconfirmed = {28: "27\nภาคผนวก 90641008", 29: "28\nข้อความอื่น"}
    assert citations.plan_pages(["X_28.png", "X_29.png"], md, {}, unconfirmed) == []
    # AIT-like: no heading read by Tesseract, but the table's codes are on the page -> confirmed
    by_codes = {28: "06016401 x 06016402", 29: "06016403 y 06016404"}
    got = citations.plan_pages(["X_28.png", "X_29.png"], md, {}, by_codes)
    assert [(t["year"], t["semester"], t["pdf_page"]) for t in got] == [(1, 1, 28), (1, 1, 29)]


# Break caught (final review #1): a continuation page whose book heading shows another term.
def test_plan_pages_rejects_continuation_contradicted_by_book_heading():
    md = "ปีที่ 1 ภาคการศึกษาที่ 1\n<table>06016401</table>\n---\n<table>06016403</table>"
    book = {28: "ปีที่ 1 ภาคการศึกษาที่ 1", 29: "ปีที่ 2 ภาคการศึกษาที่ 1\n06016403"}
    got = citations.plan_pages(["X_28.png", "X_29.png"], md, {}, book)
    assert [(t["year"], t["semester"], t["pdf_page"]) for t in got] == [(1, 1, 28)]


# Break caught (review minor #5): a negated term filter (NOT IN / EXCEPT / !=) citing that term's plan page.
def test_citations_for_skips_term_page_for_negated_filters():
    lookup = citations.load_lookup(_db_with_pages())
    for sql in ("SELECT code FROM course WHERE code NOT IN (SELECT code FROM plan_item WHERE year=1 AND semester=1)",
                "SELECT code FROM course EXCEPT SELECT code FROM plan_item WHERE year=1 AND semester=1",
                "SELECT COUNT(*) FROM plan_item WHERE year=1 AND semester != 1"):
        assert citations.citations_for([{"n": 5}], sql, lookup) == [], sql


# Break caught (review minor #8): the 3-page cap dropping the course-description page (it sits late in the book).
def test_course_pages_marks_description_page():
    pages = [{"page": "23", "text": "06016401 คณิตศาสตร์"},
             {"page": "324", "text": "06016401 คณิตศาสตร์ 3(3-0-6)\nวิชาบังคับก่อน : ไม่มี"}]
    kinds = [(r["pdf_page"], r["kind"]) for r in citations.course_pages(pages, [{"code": "06016401", "name_th": "คณิตศาสตร์"}])]
    assert kinds == [(23, "primary"), (324, "description")]


def test_citations_for_puts_description_page_right_after_plan():
    conn = _db_with_pages()
    conn.executemany("INSERT INTO course_page VALUES (?, ?, ?, ?)", [
        ("06016401", 20, "15", "primary"), ("06016401", 21, "16", "primary"), ("06016401", 330, "325", "description")])
    got = citations.citations_for([], "SELECT name_th FROM course WHERE code = '06016401'", citations.load_lookup(conn))
    assert [c["pdf_page"] for c in got] == [38, 330, 20]


# ---------- ระบุวิชาต่อหน้า + ลำดับคงที่ (ผู้ใช้ถามว่า "หน้านี้บอกข้อมูลไหน") ----------

def _multi_course_db():
    conn = _db_with_pages()
    conn.executemany("INSERT INTO course_page VALUES (?, ?, ?, ?)", [
        ("06026243", 335, "334", "description"), ("06026244", 335, "334", "description"),
        ("06026245", 336, "335", "description"), ("06026207", 321, "320", "description")])
    return conn


def test_each_citation_lists_the_courses_found_on_that_page():
    lookup = citations.load_lookup(_multi_course_db())
    rows = [{"code": "06026243"}, {"code": "06026244"}, {"code": "06026207"}]
    got = citations.citations_for(rows, "SELECT code FROM course", lookup)
    assert {c["pdf_page"]: c["courses"] for c in got} == {321: ["06026207"], 335: ["06026243", "06026244"]}


def test_term_page_lists_no_courses():
    lookup = citations.load_lookup(_db_with_pages())
    got = citations.citations_for([{"credits": 18}], "SELECT credits FROM v_semester_credits WHERE year=1 AND semester=1", lookup)
    assert got == [{"pdf_page": 38, "printed_page": "33", "courses": []}]


def test_citations_do_not_depend_on_the_order_of_the_result_rows():
    """ถามซ้ำแล้วโมเดลเรียงแถวต่างกัน → หน้าอ้างอิง 3 หน้าแรกต้องเป็นชุดเดิม"""
    lookup = citations.load_lookup(_multi_course_db())
    rows = [{"code": c} for c in ("06026245", "06026207", "06026244", "06026243")]
    a = citations.citations_for(rows, "SELECT code FROM course", lookup)
    b = citations.citations_for(list(reversed(rows)), "SELECT code FROM course", lookup)
    assert a == b


def test_course_named_in_the_sql_still_comes_first():
    lookup = citations.load_lookup(_multi_course_db())
    sql = "SELECT name_th FROM course WHERE code = '06026245'"
    rows = [{"code": "06026207"}, {"code": "06026245"}]
    assert citations.citations_for(rows, sql, lookup)[0]["pdf_page"] == 336


def test_format_citation_lists_each_course_under_its_page_with_name():
    cites = [{"pdf_page": 335, "printed_page": "334", "courses": ["06026243", "06026244"],
              "course_names": {"06026243": "สถิติ", "06026244": "ข้อมูล"},
              "course_names_en": {"06026243": "STATISTICS"}},
             {"pdf_page": 21, "printed_page": None, "courses": ["06026207"]},
             {"pdf_page": 38, "printed_page": "33", "courses": []}]
    assert citations.format_citation(cites) == (
        "อ้างอิงเล่มหลักสูตร:\n• หน้า 334 (PDF 335)\n   – 06026243 สถิติ / STATISTICS\n   – 06026244 ข้อมูล\n"
        "• PDF 21\n   – 06026207\n• หน้า 33 (PDF 38)")


# Break caught: names looked up for the wrong code or crashing when the course has no name row.
def test_add_course_names_fills_only_known_codes():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE course (code TEXT, name_th TEXT, name_en TEXT)")
    conn.execute("INSERT INTO course VALUES ('06026243', 'สถิติ', 'STATISTICS')")
    conn.execute("INSERT INTO course VALUES ('06026244', 'ข้อมูล', '  ')")
    cites = [{"pdf_page": 1, "printed_page": None, "courses": ["06026243", "06026244", "99999999"]},
             {"pdf_page": 2, "printed_page": None, "courses": []}]
    citations.add_course_names(conn, cites)
    assert cites[0]["course_names"] == {"06026243": "สถิติ", "06026244": "ข้อมูล"}
    assert cites[0]["course_names_en"] == {"06026243": "STATISTICS"}   # ชื่ออังกฤษว่าง = ไม่ใส่
    assert "course_names" not in cites[1] and "course_names_en" not in cites[1]


# ---------- เลขหน้าในชื่อไฟล์ภาพเลื่อนจากเลขหน้า PDF คงที่ (DSBA สหกิจ: DSBA_28.png = PDF 30; เล่มมีตารางแผนสองชุด) ----------

def _shifted_book():
    """หน้าเล่ม: 28–29 เป็นตารางแผนชุดอื่น (หัวเทอมต่างกัน), 30–32 คือหน้าที่ภาพ X_28–X_30 หมายถึงจริง"""
    return {28: "27\nปีที่ 1 ภาคการศึกษาที่ 2", 29: "28\nปีที่ 2 ภาคการศึกษาที่ 2",
            30: "29\nปีที่ 1 ภาคการศึกษาที่ 1", 31: "30\nปีที่ 1 ภาคการศึกษาที่ 2", 32: "31\nปีที่ 2 ภาคการศึกษาที่ 1"}


_SHIFTED_MD = ("ปีที่ 1 ภาคการศึกษาที่ 1\n<table>a</table>\n---\nปีที่ 1 ภาคการศึกษาที่ 2\n<table>b</table>\n---\n"
               "ปีที่ 2 ภาคการศึกษาที่ 1\n<table>c</table>")


# Break caught: DSBA coop had no term_page at all — every image failed confirmation because the file numbers are off by a constant.
def test_plan_pages_finds_a_constant_offset_when_no_page_confirms_at_the_filename_number():
    got = citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], _SHIFTED_MD, {30: "29", 31: "30", 32: "31"}, _shifted_book())
    assert got == [{"year": 1, "semester": 1, "pdf_page": 30, "printed_page": "29"},
                   {"year": 1, "semester": 2, "pdf_page": 31, "printed_page": "30"},
                   {"year": 2, "semester": 1, "pdf_page": 32, "printed_page": "31"}]


# Break guarded: guessing when two offsets both fit (book repeats the same headings) — ambiguous = no citation.
def test_plan_pages_does_not_guess_when_two_offsets_fit():
    book = dict(_shifted_book())
    book.update({31: "ปีที่ 1 ภาคการศึกษาที่ 1", 32: "ปีที่ 1 ภาคการศึกษาที่ 2", 33: "ปีที่ 2 ภาคการศึกษาที่ 1"})   # ชุดเดียวกันซ้ำที่ +3 และ +2
    book[30] = "ปีที่ 1 ภาคการศึกษาที่ 1"
    book[31] = "ปีที่ 1 ภาคการศึกษาที่ 2"
    book[32] = "ปีที่ 2 ภาคการศึกษาที่ 1"
    book[33] = "ปีที่ 1 ภาคการศึกษาที่ 1"
    book[34] = "ปีที่ 1 ภาคการศึกษาที่ 2"
    book[35] = "ปีที่ 2 ภาคการศึกษาที่ 1"
    assert citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], _SHIFTED_MD, {}, book) == []


# Break guarded: shifting on too little evidence (one or two term pages) or when part of the pages already confirm.
def test_plan_pages_only_shifts_with_enough_evidence_and_when_nothing_confirms():
    md = "ปีที่ 1 ภาคการศึกษาที่ 1\n<table>a</table>\n---\nปีที่ 1 ภาคการศึกษาที่ 2\n<table>b</table>"
    book = {30: "ปีที่ 1 ภาคการศึกษาที่ 1", 31: "ปีที่ 1 ภาคการศึกษาที่ 2"}
    assert citations.plan_pages(["X_28.png", "X_29.png"], md, {}, book) == []            # มีหน้าที่มีหัวเทอมแค่ 2 → หลักฐานไม่พอจะเลื่อน
    partly = {28: "ปีที่ 1 ภาคการศึกษาที่ 1", 29: "ปีที่ 9 ภาคการศึกษาที่ 9", 30: "ปีที่ 2 ภาคการศึกษาที่ 1"}
    got = citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], _SHIFTED_MD, {}, partly)
    assert [(t["year"], t["semester"], t["pdf_page"]) for t in got] == [(1, 1, 28), (2, 1, 30)]   # ยืนยันได้บางหน้าที่เลขเดิม → ไม่เลื่อน


def test_plan_pages_without_book_text_never_shifts():
    assert citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], _SHIFTED_MD, {}, None)[0]["pdf_page"] == 28


@pytest.mark.parametrize("rel", ["DSBA/coop", "DSBA/no_coop"])
def test_real_dsba_databases_cite_the_plan_page_of_every_term(rel):
    from pathlib import Path
    db = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs" / rel / "lab8b_output" / "curriculum.db"
    if not db.exists():
        pytest.skip("ไม่มีไฟล์ DB")
    c = sqlite3.connect(db)
    got = {(y, s): p for y, s, p in c.execute("SELECT year, semester, pdf_page FROM term_page")}
    assert {(1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2), (4, 1), (4, 2)} <= set(got)
    start = {"DSBA/coop": 30, "DSBA/no_coop": 23}[rel]            # เล่มเดียวมีตารางแผนสองชุด: ไม่สหกิจ PDF 23–29, สหกิจ PDF 30–36
    assert (got[(1, 1)], got[(2, 1)], got[(3, 1)], got[(4, 1)]) == (start, start + 2, start + 4, start + 6)


# ---------- หลายค่าเลื่อนผ่านพร้อมกัน (เล่มมีตารางแผนสองชุดหัวเทอมซ้ำกัน) → ใช้เลขหน้าที่พิมพ์ในแท็ก <page_number> ของ VLM ตัดสิน ----------

def _two_plans_book():
    """ตารางแผนซ้ำสองชุด: PDF 30–32 (พิมพ์ 29–31) และ PDF 33–35 (พิมพ์ 32–34) — ภาพ X_28–X_30 จึงผ่านทั้งเลื่อน +2 และ +5"""
    heads = ["ปีที่ 1 ภาคการศึกษาที่ 1", "ปีที่ 1 ภาคการศึกษาที่ 2", "ปีที่ 2 ภาคการศึกษาที่ 1"]
    book = {28: "27\nอื่น", 29: "28\nอื่น"}
    for i, h in enumerate(heads):
        book[30 + i] = f"{29 + i}\n{h}"
        book[33 + i] = f"{32 + i}\n{h}"
    printed = {pdf: str(pdf - 1) for pdf in range(28, 36)}
    return book, printed


def _tagged_md(numbers):
    heads = ["ปีที่ 1 ภาคการศึกษาที่ 1", "ปีที่ 1 ภาคการศึกษาที่ 2", "ปีที่ 2 ภาคการศึกษาที่ 1"]
    return "\n---\n".join(f"<page_number>{n}</page_number>\n{h}\n<table>x</table>" for n, h in zip(numbers, heads))


# Break caught: DSBA coop — both offsets −5 and +2 pass the heading check (book repeats the plan); the printed page number picks the right one.
def test_plan_pages_uses_the_vlm_page_number_tag_to_break_an_offset_tie():
    book, printed = _two_plans_book()
    got = citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], _tagged_md([29, 30, 31]), printed, book)
    assert [(t["year"], t["semester"], t["pdf_page"]) for t in got] == [(1, 1, 30), (1, 2, 31), (2, 1, 32)]
    got = citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], _tagged_md([32, 33, 34]), printed, book)
    assert [t["pdf_page"] for t in got] == [33, 34, 35]


def test_plan_pages_tolerates_one_misread_page_number_tag():
    book, printed = _two_plans_book()
    got = citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], _tagged_md([28, 30, 31]), printed, book)   # แท็กแรกอ่านพลาด (28 แทน 29)
    assert [t["pdf_page"] for t in got] == [30, 31, 32]


# Break guarded: a tie that the tags cannot break (no tags, or they favour both offsets equally) must still cite nothing.
def test_plan_pages_stays_silent_when_page_numbers_cannot_break_the_tie():
    book, printed = _two_plans_book()
    untagged = "\n---\n".join(["ปีที่ 1 ภาคการศึกษาที่ 1\n<table>x</table>", "ปีที่ 1 ภาคการศึกษาที่ 2\n<table>x</table>",
                               "ปีที่ 2 ภาคการศึกษาที่ 1\n<table>x</table>"])
    assert citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], untagged, printed, book) == []
    one_tag = _tagged_md([29, 99, 98])                                       # ตรงแค่หน้าเดียว (< 2 หน้า) → หลักฐานไม่พอ
    assert citations.plan_pages(["X_28.png", "X_29.png", "X_30.png"], one_tag, printed, book) == []


# Break caught (AIT PDF 19/120): a plan/structure page whose footnote says "...เป็นรายวิชาบังคับก่อน ที่ไม่นับหน่วยกิต"
# was classed as a course-description page; only the labelled line "วิชาบังคับก่อน :" marks a description page.
def test_course_pages_footnote_mentioning_prerequisite_is_not_a_description_page():
    courses = [{"code": "06046401", "name_th": "แคลคูลัส 2", "name_en": "CALCULUS 2"}]
    footnote = {"page": "19", "text": "15\n06046401 แคลคูลัส 2 3(3-0-6)\n**90641008 เป็นรายวิชาบังคับก่อน ที่ไม่นับหน่วยกิต"}
    desc = {"page": "287", "text": "283\n06046401 แคลคูลัส 2 3(3-0-6)\nวิชาบังคับก่อน : 06046400 แคลคูลัส 1"}
    got = {r["pdf_page"]: r["kind"] for r in citations.course_pages([footnote, desc], courses)}
    assert got == {19: "primary", 287: "description"}
    desc_en = {"page": "300", "text": "296\n06046401 แคลคูลัส 2\nPREREQUISITE : 06046400 CALCULUS 1"}
    assert citations.course_pages([desc_en], courses)[0]["kind"] == "description"
