import sqlite3

from course_display import format_course_answer


def test_course_list_answer_has_english_full_credits_and_preserves_totals():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE course(code TEXT, name_th TEXT, name_en TEXT, credits INTEGER,
                            lecture_h INTEGER, lab_h INTEGER, self_h INTEGER);
        INSERT INTO course VALUES ('06026207','ระบบฐานข้อมูลแบบโนเอสคิวแอล','NOSQL DATABASE SYSTEMS',3,2,2,5),
                                  ('00000001','ขาด','MISSING',3,NULL,0,6);
        """)
        result = {"answer": "รวม 6 หน่วยกิต: 06026207 ระบบฐานข้อมูลแบบโนเอสคิวแอล 3; 00000001 ขาด 3",
                  "rows": [{"code": "06026207", "name_th": "ระบบฐานข้อมูลแบบโนเอสคิวแอล", "credits": 3},
                           {"code": "00000001", "name_th": "ขาด", "credits": 3}]}
        format_course_answer(conn, result)
        assert "NOSQL DATABASE SYSTEMS — 3 (2-2-5) หน่วยกิต" in result["answer"]
        assert "MISSING — 3 หน่วยกิต" in result["answer"]
        assert "รวม 6 หน่วยกิต" in result["answer"]
        first = result["answer"]
        format_course_answer(conn, result)
        assert result["answer"] == first
        result["answer"] = "06026207 ระบบฐานข้อมูลแบบโนเอสคิวแอล — 3 (1-4-4) หรือ 3 (2-2-5) หน่วยกิต"
        format_course_answer(conn, result)
        assert "3 (1-4-4) หรือ 3 (2-2-5) หน่วยกิต" in result["answer"]
        for text in ["06026207 ระบบฐานข้อมูลแบบโนเอสคิวแอล: 3 หน่วยกิต",
                     "06026207 ระบบฐานข้อมูลแบบโนเอสคิวแอล NOSQL DATABASE SYSTEMS 3",
                     "06026207 ระบบฐานข้อมูลแบบโนเอสคิวแอล NOSQL DATABASE SYSTEMS"]:
            result["answer"] = text
            format_course_answer(conn, result)
            assert result["answer"] == "06026207 ระบบฐานข้อมูลแบบโนเอสคิวแอล / NOSQL DATABASE SYSTEMS — 3 (2-2-5) หน่วยกิต"


def test_total_only_and_unstructured_book_answers_are_unchanged():
    result = {"answer": "มี 3 วิชา รวม 9 หน่วยกิต", "rows": [{"credits": 9}]}
    format_course_answer(None, result)
    assert result["answer"] == "มี 3 วิชา รวม 9 หน่วยกิต"
