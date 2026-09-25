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
