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
