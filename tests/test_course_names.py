import course_names as cn

COURSES = [
    {"code": "06026212", "name_th": "การสร้างคลังข้อมูล", "name_en": "DATA WAREHOUSING"},
    {"code": "06026200", "name_th": "แคลคูลัส 1", "name_en": "CALCULUS 1"},
    {"code": "06026210", "name_th": "แคลคูลัส 10", "name_en": "CALCULUS 10"},
    {"code": "06066303", "name_th": "การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์", "name_en": "PROBLEM SOLVING AND COMPUTER PROGRAMMING"},
    {"code": "06046403", "name_th": "การโปรแกรมคอมพิวเตอร์", "name_en": "COMPUTER PROGRAMMING"},
    {"code": "06099991", "name_th": "สัมมนา", "name_en": "SEMINAR"},
    {"code": "06099992", "name_th": "สัมมนา", "name_en": "SEMINAR II"},
    {"code": "06099993", "name_th": "ก", "name_en": "AI"},
    {"code": "06099994", "name_th": "การจัดการคำสั่งซื้อ", "name_en": None},
]


def codes(question):
    return [code for _, code in cn.course_hints(question, COURSES)]


# Break caught: the model inventing a course code because nothing maps a Thai course name to its code.
def test_thai_name_maps_to_code():
    assert codes("ต้องเรียนวิชาอะไรก่อน ถึงจะเรียนการสร้างคลังข้อมูลได้") == ["06026212"]


# Break caught: English names put into the SQL as if they were codes (code='DATA WAREHOUSING').
def test_english_name_maps_to_code_case_insensitive():
    assert codes("ต้องเรียนวิชาอะไรก่อน ถึงจะเรียน Data  Warehousing ได้") == ["06026212"]


# Break caught: a name typed with spaces or the split sara-am form not matching the stored name.
def test_thai_matching_ignores_spaces_and_split_sara_am():
    assert codes("วิชาบังคับก่อนของ การสร้าง คลังข้อมูล") == ["06026212"]
    assert codes("วิชาบังคับก่อนของการจัดการคําสั่งซื้อ") == ["06099994"]


# Break caught: a short name inside a longer one being hinted as a second course.
def test_longest_name_wins():
    assert codes("ต้องเรียนอะไรก่อนการแก้ปัญหาและการโปรแกรมคอมพิวเตอร์") == ["06066303"]
    assert codes("ต้องเรียนอะไรก่อน PROBLEM SOLVING AND COMPUTER PROGRAMMING") == ["06066303"]


# Break caught: "แคลคูลัส 1" matching inside "แคลคูลัส 10".
def test_trailing_number_must_match_whole():
    assert codes("ก่อนเรียนแคลคูลัส 10 ต้องผ่านอะไร") == ["06026210"]
    assert codes("ก่อนเรียน CALCULUS 10 ต้องผ่านอะไร") == ["06026210"]


# Break caught: picking one code for a name shared by two courses (guessing).
def test_duplicate_name_returns_every_code():
    assert codes("วิชาบังคับก่อนของสัมมนา") == ["06099991", "06099992"]


# Break caught: very short names / English words hinting inside unrelated text.
def test_short_names_and_partial_english_words_are_ignored():
    assert codes("ขอรายละเอียดเพิ่ม MAIL") == []


def test_no_course_name_no_hint():
    assert codes("ปี 1 เทอม 1 เรียนกี่หน่วยกิต") == []


# Break caught: hinting a course whose code the user already typed (nothing to resolve).
def test_course_already_given_by_code_is_skipped():
    assert codes("06026212 การสร้างคลังข้อมูล ต้องเรียนอะไรก่อน") == []


def test_hint_block_lists_name_and_code():
    block = cn.hint_block([("การสร้างคลังข้อมูล", "06026212")])
    assert '"การสร้างคลังข้อมูล" = 06026212' in block
    assert cn.hint_block([]) == ""


NAMES = {"06026200": "แคลคูลัส 1", "06066300": "การโปรแกรมคอมพิวเตอร์", "06026212": "การสร้างคลังข้อมูล"}


# Break caught: a prerequisite answer that is only a code ("06026200") — the user cannot tell which course it is.
def test_answer_codes_get_course_names():
    rows = [{"requires": "06026200"}]
    assert cn.with_course_names("06026200", rows, NAMES) == "06026200 (แคลคูลัส 1)"


def test_every_code_from_the_rows_is_named():
    rows = [{"code": "06026200"}, {"code": "06066300"}]
    assert cn.with_course_names("06026200, 06066300", rows, NAMES) == (
        "06026200 (แคลคูลัส 1), 06066300 (การโปรแกรมคอมพิวเตอร์)")


# Break caught: naming a course twice when the model already wrote its name.
def test_code_already_followed_by_its_name_is_left_alone():
    rows = [{"requires": "06026200"}]
    assert cn.with_course_names("แคลคูลัส 1 (06026200)", rows, NAMES) == "แคลคูลัส 1 (06026200)"


# Break caught: naming a code that did not come from the database result (e.g. echoed from the question).
def test_only_codes_from_the_rows_are_named():
    assert cn.with_course_names("06026212 ไม่มีวิชาบังคับก่อน", [], NAMES) == "06026212 ไม่มีวิชาบังคับก่อน"


def test_unknown_code_is_left_alone():
    rows = [{"requires": "99999999"}]
    assert cn.with_course_names("99999999", rows, NAMES) == "99999999"


def direction(question):
    return cn.prereq_direction(question, cn.course_hints(question, COURSES))


# Break caught: "วิชาตัวต่อจากแคลคูลัส 1" answered "ไม่พบ" — qwen wrote code='X' (what X requires) instead of requires='X'.
def test_courses_that_come_after_x():
    for q in ("วิชาหลังแคลคูลัส 1", "วิชาตัวต่อจากแคลคูลัส 1", "วิชาต่อจากแคลคูลัส 1",
              "วิชาที่ต้องผ่านแคลคูลัส 1 ก่อน", "แคลคูลัส 1 เป็นวิชาบังคับก่อนของวิชาอะไร",
              "เรียนแคลคูลัส 1 แล้วเรียนอะไรต่อ", "วิชาไหนใช้แคลคูลัส 1 เป็นวิชาบังคับก่อน",
              "ผ่านวิชา 06026200 แล้วจะลงวิชาไหนต่อได้บ้าง", "วิชาใดบ้างที่มี 06026200 เป็นวิชาบังคับก่อน"):
        assert direction(q) == ("after", "06026200"), q


def test_courses_that_x_requires():
    for q in ("ก่อนลงวิชา 06026200 ต้องผ่านวิชาอะไรมาก่อน", "แคลคูลัส 1 ต้องเรียนวิชาอะไรก่อน",
              "ถ้าจะลงเรียนแคลคูลัส 1 ต้องผ่านวิชาอะไรมาก่อน", "รหัสวิชา 06026200 มีวิชาบังคับก่อนคือวิชาใด",
              "วิชาบังคับก่อนของแคลคูลัส 1", "ต้องเรียนวิชาอะไรมาก่อนจึงจะลงเรียนแคลคูลัส 1 ได้"):
        assert direction(q) == ("before", "06026200"), q


# Break caught: "ต่อสัปดาห์" (per week) read as "ต่อ" (next); no direction word / no course / two courses = no hint.
def test_no_direction_hint_when_unclear():
    assert direction("วิชาแคลคูลัส 1 มีชั่วโมงบรรยายต่อสัปดาห์กี่ชั่วโมง") is None
    assert direction("แคลคูลัส 1 กี่หน่วยกิต") is None
    assert direction("ความสัมพันธ์วิชาบังคับก่อนมีทั้งหมดกี่คู่") is None
    assert direction("การสร้างคลังข้อมูลต้องเรียนแคลคูลัส 1 มาก่อนไหม") is None


def test_direction_block_names_the_column():
    assert "requires='06026200'" in cn.direction_block(("after", "06026200"))
    assert "code='06026200'" in cn.direction_block(("before", "06026200"))
    assert cn.direction_block(None) == ""


# Break caught (held-out หลังรีวิว): ถ้อยคำอื่นของ "วิชาตัวต่อ" ไม่ถูกจับ → ไม่มีคำสั่งทิศเฉพาะข้อ โมเดลเลยกลับทิศ
def test_other_phrasings_of_courses_that_come_after_x():
    for q in ("วิชา 06026200 เป็นพื้นฐานของวิชาอะไรบ้าง", "เรียนจบวิชา 06026200 แล้วไปต่อวิชาไหนได้",
              "ถ้าผ่านวิชา 06026200 แล้ว ลงเรียนวิชาอะไรได้อีก", "06026200 ปลดล็อกวิชาอะไร",
              "วิชาไหนใช้ 06026200 เป็นพื้นฐาน", "เรียนแคลคูลัส 1 แล้วจะปลดล็อกให้เรียนวิชาอะไรต่อ"):
        assert direction(q) == ("after", "06026200"), q


# Break guarded: คำว่าพื้นฐาน/ปลดล็อก/ไปต่อ ที่ไม่ได้ถามความสัมพันธ์วิชาบังคับก่อนต้องไม่ถูกตีเป็นทิศ
def test_new_direction_patterns_do_not_fire_on_other_questions():
    assert direction("แคลคูลัส 1 เป็นพื้นฐานของสาขาอะไร") is None
    assert direction("เรียนแคลคูลัส 1 แล้วจะได้ความรู้อะไรบ้าง") is None
    assert direction("แคลคูลัส 1 ปลดล็อกศักยภาพด้านใดของนักศึกษา") is None
    assert direction("เรียนจบแคลคูลัส 1 แล้วไปต่อปริญญาโทได้ไหม") is None



# Break caught (probe 62 ข้อ): "X ต้องเรียนก่อนวิชาอะไร" = ถามวิชาตัวต่อของ X แต่ไม่มีกฎ → ไม่มีคำสั่งทิศ โมเดลตอบ error
def test_x_must_be_taken_before_which_course_is_the_after_direction():
    for q in ("วิชา แคลคูลัส 1 ต้องเรียนก่อนวิชาอะไร", "แคลคูลัส 1 ต้องเรียนก่อนวิชาไหน และวิชานั้นอยู่ปีไหน", "06026200 ต้องผ่านก่อนวิชาอะไร"):
        assert direction(q) == ("after", "06026200"), q


# Break guarded: yes/no phrasing ("ต้องเรียนก่อนไหม") and the opposite direction ("ต้องเรียนวิชาอะไรมาก่อน") must not flip
def test_new_after_pattern_does_not_touch_other_directions_or_yes_no_questions():
    assert direction("วิชา แคลคูลัส 1 ต้องเรียนก่อนไหม") is None
    assert direction("วิชา แคลคูลัส 1 ต้องเรียนวิชาอะไรมาก่อน") == ("before", "06026200")


# Break caught (held-out ใหม่ 270 ข้อ): "X เป็นเงื่อนไขก่อนเรียนของวิชาไหนบ้าง" = ถามวิชาตัวต่อของ X แต่ไม่มีกฎ → โมเดลสลับทิศ (WHERE code='X') ตอบ "ไม่พบ" 14 ครั้งใน 7 DB
def test_x_is_a_condition_for_which_course_is_the_after_direction():
    for q in ("วิชา แคลคูลัส 1 เป็นเงื่อนไขก่อนเรียนของวิชาไหนบ้าง", "แคลคูลัส 1 เป็นเงื่อนไขของวิชาอะไร", "06026200 เป็นข้อกำหนดก่อนเรียนของวิชาใดบ้าง",
              "วิชา แคลคูลัส 1 เป็นเงื่อนไขก่อนลงทะเบียนของวิชาไหน", "แคลคูลัส 1 เป็นวิชาเงื่อนไขของวิชาอะไรบ้าง"):
        assert direction(q) == ("after", "06026200"), q


def test_condition_phrasing_does_not_fire_on_other_questions():
    assert direction("วิชา แคลคูลัส 1 มีเงื่อนไขอะไรบ้าง") is None
    assert direction("เงื่อนไขการจบการศึกษาคืออะไร") is None
    assert direction("แคลคูลัส 1 เป็นเงื่อนไขของการสอบไหม") is None


# Break caught (ชุดสำนวนใหม่ที่ subagent เขียน): "X เป็นวิชาที่ต้องเรียนก่อนวิชาไหน" / "X เป็นวิชาพื้นฐานให้วิชาอะไร" = วิชาตัวต่อของ X แต่กฎเดิมต้องติดกัน → โมเดลสลับทิศ ตอบ "ไม่พบ"
def test_x_is_the_course_to_take_before_which_course_is_the_after_direction():
    for q in ("แคลคูลัส 1 เป็นวิชาที่ต้องเรียนก่อนวิชาไหนบ้าง", "แคลคูลัส 1 เป็นวิชาที่ต้องผ่านก่อนวิชาอะไรบ้าง", "วิชา แคลคูลัส 1 เป็นวิชาต้องเรียนก่อนวิชาใด",
              "แคลคูลัส 1 เป็นวิชาพื้นฐานให้วิชาอะไรบ้าง", "แคลคูลัส 1 เป็นวิชาพื้นฐานของวิชาไหน", "06026200 เป็นวิชาที่เป็นพื้นฐานให้วิชาอะไรบ้าง"):
        assert direction(q) == ("after", "06026200"), q


def test_those_phrasings_do_not_fire_on_other_questions():
    assert direction("แคลคูลัส 1 เป็นวิชาที่ยากไหม") is None
    assert direction("แคลคูลัส 1 เป็นวิชาบังคับหรือวิชาเลือก") is None
    assert direction("แคลคูลัส 1 เป็นวิชาพื้นฐานที่สำคัญไหม") is None


# Break caught (DSBA coop): "DATA WAREHOUSE" (user dropped the ING) matched no course, so the model put the text into code='...' and answered "not found".
def test_english_name_with_truncated_ending_maps_to_the_one_course_it_starts():
    assert codes("การจะเรียนวิชา DATA WAREHOUSE ต้องผ่านวิชาอะไรมาก่อน") == ["06026212"]
    assert codes("what are the prerequisites of data warehous") == ["06026212"]


# Break caught: a stem shared by several courses guessed as one of them (COMPUTER PROGRAM -> two courses), or a single common word.
def test_truncated_english_name_shared_by_several_courses_is_not_hinted():
    assert codes("วิชา COMPUTER PROGRAM ต้องผ่านอะไร") == []
    assert codes("วิชา CALCULUS ต้องผ่านอะไร") == []
    assert codes("วิชา DATA ต้องผ่านอะไร") == []


# Break caught: the fallback firing when the exact name is already found (second hint for the same phrase), or on unrelated words.
def test_truncated_fallback_does_not_add_to_an_exact_match_or_unrelated_words():
    assert codes("DATA WAREHOUSING ต้องผ่านอะไร") == ["06026212"]
    assert codes("WAREHOUSES ARE BIG") == ["06026212"] or codes("WAREHOUSES ARE BIG") == []   # trim <=3 chars only; never guess beyond
    assert codes("ขอรายละเอียดเพิ่ม MAILBOX") == []
