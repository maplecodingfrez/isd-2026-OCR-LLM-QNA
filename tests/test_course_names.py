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


ACR_COURSES = [
    {"code": "06026211", "name_th": "การเรียนรู้ของเครื่องเชิงประยุกต์", "name_en": "APPLIED MACHINE LEARNING"},
    {"code": "06026212", "name_th": "การสร้างคลังข้อมูล", "name_en": "DATA WAREHOUSING"},
    {"code": "06066304", "name_th": "การวิเคราะห์และออกแบบระบบสารสนเทศ", "name_en": "INFORMATION SYSTEMS ANALYSIS AND DESIGN"},
]


# Break caught: acronyms (ML/DW/SAD) reached only the prompt hint, never the deterministic shortcuts (_named_courses).
def test_acronym_courses_resolves_a_single_plan_course():
    assert cn.acronym_courses("วิชา ML อยู่เทอมไหน", ACR_COURSES) == [("06026211", "การเรียนรู้ของเครื่องเชิงประยุกต์")]
    assert cn.acronym_courses("DW กี่หน่วยกิต", ACR_COURSES) == [("06026212", "การสร้างคลังข้อมูล")]
    assert cn.acronym_courses("SAD กี่หน่วยกิต", ACR_COURSES) == [("06066304", "การวิเคราะห์และออกแบบระบบสารสนเทศ")]


# Break caught: lowercase "ml" (millilitre) / "dw" in running text hinted as a course.
def test_short_acronyms_must_be_uppercase():
    assert cn.acronym_courses("ยา 5 ml กินวันละกี่ครั้ง", ACR_COURSES) == []
    assert cn.acronym_courses("what is the dw of this river", ACR_COURSES) == []
    assert codes("ยา 5 ml กินวันละกี่ครั้ง") == []
    assert [c for _, c in cn.course_hints("ยา 5 ml กินวันละกี่ครั้ง", ACR_COURSES)] == []


# Break caught: picking the first of several courses an acronym could mean (guessing = wrong course).
def test_acronym_matching_several_courses_is_not_resolved():
    two = ACR_COURSES + [{"code": "06099999", "name_th": "การสร้างคลังข้อมูลขั้นสูง", "name_en": "ADVANCED DATA WAREHOUSING"}]
    assert cn.acronym_courses("DW กี่หน่วยกิต", two) == []
    assert cn.course_hints("DW กี่หน่วยกิต", two) == []


def test_acronym_absent_from_the_plan_is_not_resolved():
    assert cn.acronym_courses("วิชา SE อยู่เทอมไหน", ACR_COURSES) == []


# Break caught: OS/DIQ were not in ACRONYM_MAP, so "OS" fell to qwen's LIKE '%OS%' and hit NOSQL.
def test_os_and_diq_resolve_to_their_single_course_and_ignore_ios():
    cs = [{"code": "06016412", "name_th": "โครงสร้างระบบคอมพิวเตอร์และระบบปฏิบัติการ", "name_en": "COMPUTER ORGANIZATION AND OPERATING SYSTEM"},
          {"code": "06016414", "name_th": "ระบบฐานข้อมูลแบบโนเอสคิวแอล", "name_en": "NOSQL DATABASE SYSTEMS"},
          {"code": "90641002", "name_th": "ความฉลาดทางดิจิทัล", "name_en": "DIGITAL INTELLIGENCE QUOTIENT"}]
    assert [c for c, _ in cn.acronym_courses("วิชา OS รหัสอะไร", cs)] == ["06016412"]
    assert [c for c, _ in cn.acronym_courses("วิชา DIQ รหัสอะไร", cs)] == ["90641002"]
    assert cn.acronym_courses("แอป iOS ใช้ได้ไหม", cs) == []


DS_COURSES = [
    {"code": "06066301", "name_th": "โครงสร้างข้อมูลและอัลกอริทึม", "name_en": "DATA STRUCTURES AND ALGORITHMS"},
    {"code": "06066302", "name_th": "การออกแบบอัลกอริทึม", "name_en": "ALGORITHM DESIGN"},
]


# Break caught: "Data Struc" (ตัดคำ) / "ดาต้าสตัค" (ทับศัพท์) matched no course -> qwen guessed with no hint.
def test_data_structures_short_and_transliterated_names_resolve_to_the_single_course():
    for q in ("วิชา Data Struc อยู่ปีไหน", "วิชา data struc กี่หน่วยกิต", "วิชา ดาต้าสตัค อยู่ปีไหน", "ดาต้าสตรัคกี่หน่วยกิต", "ดาต้า สตัค รหัสอะไร"):
        assert [c for _, c in cn.course_hints(q, DS_COURSES)] == ["06066301"], q


# Break caught: guessing between two courses that both fit the short name.
def test_data_structures_short_name_matching_two_courses_is_not_resolved():
    two = DS_COURSES + [{"code": "06066399", "name_th": "โครงสร้างข้อมูลขั้นสูง", "name_en": "ADVANCED DATA STRUCTURES"}]
    assert cn.colloquial_courses("วิชา Data Struc อยู่ปีไหน", two) == []
    assert cn.colloquial_courses("วิชา ดาต้าสตัค อยู่ปีไหน", two) == []


def test_data_structures_short_name_does_not_fire_on_unrelated_questions():
    assert cn.colloquial_courses("วิชา ดาต้าไซเอนซ์ อยู่ปีไหน", DS_COURSES) == []
    assert cn.colloquial_courses("วิชา Data Science อยู่ปีไหน", DS_COURSES) == []


NEAR = [
    {"code": "06066302", "name_th": "การเขียนโปรแกรมเว็บพื้นฐาน", "name_en": "FUNDAMENTAL WEB PROGRAMMING"},
    {"code": "06066303", "name_th": "การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์", "name_en": "PROBLEM SOLVING AND COMPUTER PROGRAMMING"},
    {"code": "06066300", "name_th": "แนวคิดระบบฐานข้อมูล", "name_en": "DATABASE SYSTEM CONCEPTS"},
    {"code": "06016414", "name_th": "ระบบฐานข้อมูลแบบโนเอสคิวแอล", "name_en": "NOSQL DATABASE SYSTEMS"},
    {"code": "06016412", "name_th": "โครงสร้างระบบคอมพิวเตอร์และระบบปฏิบัติการ", "name_en": "COMPUTER ORGANIZATION AND OPERATING SYSTEM"},
]


def near(question):
    typed, found = cn.english_fragment_courses(question, NEAR)
    return typed, [c for c, _, _ in found]


# Feature: a typed English name that is only PART of real names -> list those courses (never pick one)
def test_partial_english_name_lists_every_course_whose_name_contains_it():
    assert near("วิชา WEB PROGRAMMING อยู่ปีไหน") == ("WEB PROGRAMMING", ["06066302"])
    assert near("วิชา COMPUTER PROGRAMMING รหัสอะไร")[1] == ["06066303"]
    assert near("วิชา DATABASE SYSTEMS รหัสอะไร")[1] == ["06066300", "06016414"]      # ไม่สนตัว s ท้ายคำ
    assert near("วิชา OPERATING SYSTEMS มีกี่หน่วยกิต")[1] == ["06016412"]


# Break caught: typed name LONGER than a real name (adversarial) or too short / unrelated must not produce candidates.
def test_partial_english_name_needs_to_be_shorter_than_the_real_name_and_long_enough():
    assert near("วิชา WEB PROGRAMMING ADVANCED อยู่ปีไหน")[1] == []              # ชื่อจริงอยู่ในคำที่ยาวกว่า = ทิศตรงข้าม
    assert near("วิชา AI เรียนตอนปีไหน")[1] == []                                  # สั้นเกิน (ห้ามจับกลางคำ)
    assert near("วิชา FUNDAMENTAL WEB PROGRAMMING อยู่ปีไหน")[1] == []            # ชื่อเต็มตรงตัว = ไม่ใช่กรณีนี้
    assert near("ปี 1 เทอม 1 เรียนกี่หน่วยกิต")[1] == []


def test_colloquial_candidates_returns_every_course_but_colloquial_courses_still_needs_one():
    two = [{"code": "1", "name_th": "ฐานข้อมูลก"}, {"code": "2", "name_th": "ฐานข้อมูลข"}]
    assert [c for c, _ in cn.colloquial_candidates("วิชา ฐานข้อมูล อยู่ปีไหน", two)] == ["1", "2"]
    assert cn.colloquial_courses("วิชา ฐานข้อมูล อยู่ปีไหน", two) == []
    assert cn.colloquial_candidates("วิชา ฐานข้อมูลโนเอสคิวแอล อยู่ปีไหน", two) == []      # กฎ NoSQL ตัดสินก่อน ไม่ตกไปกฎกว้าง


LOOSE_COURSES = ACR_COURSES + [
    {"code": "06066102", "name_th": "ระบบสารสนเทศเพื่อการจัดการ", "name_en": "MANAGEMENT INFORMATION SYSTEMS"},
]


def loose(question):
    return [c for c, _ in cn.acronym_courses(question, LOOSE_COURSES)]


# Feature: lower/mixed-case acronyms are accepted from CONTEXT, not from case
def test_lowercase_acronym_is_accepted_after_the_word_wicha():
    assert loose("วิชา ml อยู่เทอมไหน") == ["06026211"]
    assert loose("วิชาml อยู่เทอมไหน") == ["06026211"]
    assert loose("วิชา Dw กี่หน่วยกิต") == ["06026212"]
    assert loose("วิชา sad รหัสอะไร") == ["06066304"]


def test_three_letter_lowercase_acronym_alone_is_accepted_but_two_letters_need_wicha():
    assert loose("sad กี่หน่วยกิต") == ["06066304"]
    assert loose("mis รหัสอะไร") == ["06066102"]
    assert loose("ml อยู่เทอมไหน") == []                    # 2 ตัวอักษรไม่มี "วิชา" = ไม่เสี่ยง
    assert loose("dw กี่หน่วยกิต") == []


# Break caught: units / English sentences read as course acronyms once case is ignored.
def test_lowercase_acronym_next_to_a_number_or_inside_an_english_sentence_is_rejected():
    for q in ("ยา 5 ml กินวันละกี่ครั้ง", "ยา 5ml กินวันละกี่ครั้ง", "วิชา 5 ml กินวันละกี่ครั้ง",
              "what is the dw of this river", "what is sad กี่หน่วยกิต", "ใส่ ml ไป 10 ml"):
        assert loose(q) == [], q


def test_expand_acronyms_replaces_a_lowercase_acronym_in_context_only():
    out = cn.expand_acronyms("วิชา ml ต้องผ่านอะไร", LOOSE_COURSES)
    assert "การเรียนรู้ของเครื่องเชิงประยุกต์" in out and "ml" not in out
    assert cn.expand_acronyms("ยา 5 ml กินวันละกี่ครั้ง", LOOSE_COURSES) == "ยา 5 ml กินวันละกี่ครั้ง"


AB_COURSES = [
    {"code": "06026211", "name_th": "การเรียนรู้ของเครื่องเชิงประยุกต์", "name_en": "APPLIED MACHINE LEARNING"},
    {"code": "06046405", "name_th": "การเรียนรู้ของเครื่องเชิงความน่าจะเป็น", "name_en": "PROBABILISTIC MACHINE LEARNING"},
    {"code": "06066101", "name_th": "พื้นฐานทางธุรกิจสำหรับเทคโนโลยีสารสนเทศ", "name_en": "BUSINESS FUNDAMENTALS FOR INFORMATION TECHNOLOGY"},
]


# Feature: AML (Applied Machine Learning) and BFIT (Business Fundamentals for IT), first letters of each word
def test_aml_and_bfit_resolve_to_their_single_course():
    ab = lambda q: [c for c, _ in cn.acronym_courses(q, AB_COURSES)]
    assert ab("วิชา AML อยู่เทอมไหน") == ["06026211"]
    assert ab("วิชา BFIT รหัสอะไร") == ["06066101"]
    assert ab("bfit กี่หน่วยกิต") == ["06066101"]                  # ตัวเล็กตามบริบท (คำอังกฤษคำเดียว ≥3 ตัวอักษร)
    assert ab("วิชา aml อยู่เทอมไหน") == ["06026211"]


def test_aml_is_not_confused_with_ml_or_other_words():
    ab = lambda q: [c for c, _ in cn.acronym_courses(q, AB_COURSES)]
    assert ab("วิชา ML อยู่เทอมไหน") == []                         # ML ตรง Applied และ Probabilistic = กำกวม ไม่ตอบ
    assert ab("วิชา HAMLET อยู่เทอมไหน") == []                      # ไม่จับกลางคำ


def test_isd_acronym_resolves_one_course_with_existing_case_rules():
    courses = [{"code": "06026240", "name_th": "การพัฒนาระบบอัจฉริยะ", "name_en": "INTELLIGENT SYSTEM DEVELOPMENT"}]
    for q in ("วิชา ISD รหัสอะไร", "วิชา isd กี่หน่วยกิต", "Isd กี่หน่วยกิต"):
        assert [c for c, _ in cn.acronym_courses(q, courses)] == ["06026240"]
    for q in ("วิชา ISD2 รหัสอะไร", "วิชา XISD รหัสอะไร", "5 isd", "what is isd about"):
        assert cn.acronym_courses(q, courses) == []
    assert cn.acronym_courses("ISD รหัสอะไร", []) == []
    assert cn.acronym_courses("ISD รหัสอะไร", courses + [dict(courses[0], code="06099999")]) == []


ADDED_ALIAS_CASES = [
    (('ISAD',), '06066304', 'ANALYSIS AND DESIGN', 'การวิเคราะห์และออกแบบ'),
    (('DSA', 'DSAA', 'DSDA'), '06066301', 'DATA STRUCTURES AND ALGORITHMS', 'โครงสร้างข้อมูลและอัลกอริทึม'),
    (('PSP', 'PSCP'), '06066303', 'PROBLEM SOLVING AND COMPUTER PROGRAMMING', 'การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์'),
    (('DISCRETE',), '06066000', 'DISCRETE MATHEMATICS', 'คณิตศาสตร์ไม่ต่อเนื่อง'),
    (('ITF',), '06016402', 'INFORMATION TECHNOLOGY FUNDAMENTALS', 'พื้นฐานทางด้านเทคโนโลยีสารสนเทศ'),
    (('CNI', 'COMM NET'), '06016419', 'COMMUNICATION NETWORK INFRASTRUCTURE', 'โครงสร้างพื้นฐานเครือข่ายการสื่อสาร'),
    (('BDS',), '06026213', 'BIG DATA SYSTEMS', 'ระบบข้อมูลมหัต'),
    (('ERP',), '06036110', 'ENTERPRISE RESOURCE PLANNING', 'การวางแผนทรัพยากรองค์กร'),
    (('BISAD',), '06036121', 'BUSINESS INFORMATION SYSTEM ANALYSIS AND DESIGN', 'การวิเคราะห์และออกแบบระบบสารสนเทศทางธุรกิจ'),
    (('AIoT',), '06046413', 'ARTIFICIAL INTELLIGENCE AND INTERNET OF THING', 'ปัญญาประดิษฐ์และอินเทอร์เน็ต'),
    (('NoSQL DB',), '06016414', 'NOSQL DATABASE SYSTEMS', 'ระบบฐานข้อมูลแบบโนเอสคิวแอล'),
]


def test_added_catoz_aliases_resolve_without_relaxing_existing_rules():
    for aliases, code, en, th in ADDED_ALIAS_CASES:
        courses = [{'code': code, 'name_en': en, 'name_th': th}]
        for alias in aliases:
            for spelling in (alias, alias.lower(), alias.upper()):
                assert [c for c, _ in cn.acronym_courses(f'วิชา {spelling} รหัสอะไร', courses)] == [code], spelling
            assert cn.acronym_courses(f'วิชา {alias} รหัสอะไร', []) == []
            assert cn.acronym_courses(f'วิชา X{alias} รหัสอะไร', courses) == []
            assert cn.acronym_courses(f'วิชา {alias}2 รหัสอะไร', courses) == []
            assert cn.acronym_courses(f'5 {alias.lower()}', courses) == []
            assert cn.acronym_courses(f'what is {alias.lower()} about', courses) == []
            ambiguous = courses + [dict(courses[0], code='06099999', name_en=en+' ADVANCED', name_th=th+'ขั้นสูง')]
            assert cn.acronym_courses(f'วิชา {alias} รหัสอะไร', ambiguous) == []


def test_unverified_crm_and_ambiguous_nlp_are_not_added():
    courses = [{'code': '06046414', 'name_en': 'NATURAL LANGUAGE PROCESSING', 'name_th': 'การประมวลผลภาษาธรรมชาติ'},
               {'code': '06046410', 'name_en': 'DEEP LEARNING FOR NATURAL LANGUAGE PROCESSING', 'name_th': 'การเรียนรู้เชิงลึกสำหรับการประมวลผลภาษาธรรมชาติ'},
               {'code': '06099999', 'name_en': 'CUSTOMER RELATIONSHIP MANAGEMENT', 'name_th': 'การบริหารลูกค้าสัมพันธ์'}]
    assert cn.acronym_courses('วิชา NLP รหัสอะไร', courses) == []
    assert cn.acronym_courses('วิชา CRM รหัสอะไร', courses) == []
