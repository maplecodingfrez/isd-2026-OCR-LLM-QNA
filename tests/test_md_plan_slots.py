from pathlib import Path

import md_plan_slots as mps

HEAD = ("ปีที่ 2 ภาคการศึกษาที่ 2\n\n<table><tr><td>รหัสวิชา</td><td>ชื่อวิชา</td><td>หน่วยกิต</td></tr>"
        "<tr><td>06016405</td><td>พื้นฐานความมั่นคงปลอดภัยไซเบอร์</td><td>3(3-0-6)</td></tr>"
        "<tr><td>06016410</td><td>วิศวกรรมซอฟต์แวร์</td><td>3(3-0-6)</td></tr>"
        "<tr><td>06016412</td><td>โครงสร้างระบบคอมพิวเตอร์และระบบปฏิบัติการ</td><td>3(2-2-5)</td></tr>"
        "<tr><td>06066302</td><td>การเขียนโปรแกรมเว็บพื้นฐาน</td><td>3(2-2-5)</td></tr>"
        "<tr><td rowspan=\"3\">06016414, 06016415</td><td>กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์ "
        "ระบบฐานข้อมูลแบบโนเอสคิวแอล การเขียนโปรแกรมเชิงฟังก์ชัน</td><td rowspan=\"3\">3(2-2-5)</td></tr>"
        "<tr><td>กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ โครงสร้างพื้นฐานเครือข่ายการสื่อสาร</td></tr>")
TAIL = ("<tr><td rowspan=\"2\">06016424, 06016425</td><td>กลุ่มวิชาด้านสื่อประสม การออกแบบส่วนต่อประสานกับมนุษย์ "
        "พื้นฐานการออกแบบทัศนศิลป์สำหรับสื่อปฏิสัมพันธ์</td><td rowspan=\"2\">3(3-0-6)</td></tr>"
        "<tr><td colspan=\"2\">รวม</td><td>18</td></tr></table>")
NAMES = {(2, 2): {"06016419": "โครงสร้างพื้นฐานเครือข่ายการสื่อสาร",
                  "06016420": "ระบบโครงสร้างพื้นฐานและการบริการ"}}


def _group_codes(md):
    slots, _ = mps.derive_slots(md, NAMES)
    group = next(s for s in slots if s["kind"] == "choose_group")
    return [g["codes"] for g in group["groups"]]


# Break caught (IT no_coop OCR rerun 2026-09-26): the second member's name sits on the next row, not in the
# "กลุ่มวิชาด้าน…" cell (no rowspan) — 06016420 was left out of the group and counted as a normal course (+3).
def test_nocode_group_takes_member_names_from_following_rows():
    md = HEAD + "<tr><td>ระบบโครงสร้างพื้นฐานและการบริการ INFRASTRUCTURE SYSTEMS AND SERVICES</td></tr>" + TAIL
    assert ["06016419", "06016420"] in _group_codes(md)


# Break caught: extending the search swallowing a row that has its own code (it belongs to the next group/course).
def test_nocode_group_stops_at_the_next_coded_row():
    md = HEAD + TAIL.replace("การออกแบบส่วนต่อประสานกับมนุษย์", "การออกแบบส่วนต่อประสานกับมนุษย์ ระบบโครงสร้างพื้นฐานและการบริการ")
    assert ["06016419"] in _group_codes(md)


# ─── Lab 7B book-text repairs (prereq_from_book / code_from_book) — kept here to avoid a new test file ───
import prereq_from_book as pfb


# Break caught (IT book 2026-09-27): Tesseract dropped the leading credit digit "3(3-0-6)" -> "(3-0-6)", so the
# heading was not recognised and 06066102's prerequisite line was never read (IT DB had no 06066102 -> 06066101).
def test_prereq_heading_with_dropped_leading_credit_digit():
    lines = ["06066102 ระบบสารสนเทศเพื่อการจัดการ                              (3-0-6)",
             "MANAGEMENT INFORMATION SYSTEMS",
             "วิชาบังคับก่อน : 06066101 พื้นฐานทางธุรกิจสําหรับเทคโนโลยี",
             "สารสนเทศ",
             "PREREQUISITE : 06066101 BUSINESS FUNDAMENTALS FOR"]
    res = pfb.extract_prerequisites(lines, ["06066102"], known_codes=["06066102", "06066101"])
    assert res["06066102"]["status"] == "found"
    assert res["06066102"]["requires"] == ["06066101"]


import code_from_book as cfb


def test_duplicate_wrong_english_alias_requires_repeated_exact_title_evidence():
    rows = [{'code':'00000001','name_th':'วิชาแรก','name_en':'SECOND COURSE'},
            {'code':'00000002','name_th':'วิชาสอง','name_en':'SECOND COURSE'}]
    source = ('--- Page 1 ---\n00000001 วิชาแรก 3(3-0-6)\nFIRST COURSE\n'
              '--- Page 100 ---\n00000001 วิชาแรก 3(3-0-6)\nFIRST COURSE\n')
    assert cfb.fill_english_names('',rows,source)
    assert rows[0]['name_en'] == 'FIRST COURSE' and rows[1]['name_en'] == 'SECOND COURSE'
    assert not cfb.fill_english_names('',rows,source)
    detached_page = source.replace('--- Page 100 ---','') + '--- Page 200 ---\n00000001 วิชาแรก 3(3-0-6)\n'
    for bad_source in (detached_page, source.split('--- Page 100 ---')[0], source.replace('--- Page 100 ---',''), source.replace('FIRST COURSE\n','OTHER COURSE\n',1),
                       source.replace('วิชาแรก','วิชาอื่น')):
        candidate = [{'code':'00000001','name_th':'วิชาแรก','name_en':'SECOND COURSE'},
                     {'code':'00000002','name_th':'วิชาสอง','name_en':'SECOND COURSE'}]
        assert not cfb.fill_english_names('',candidate,bad_source)
        assert candidate[0]['name_en'] == 'SECOND COURSE'


def test_missing_zero_credit_plan_row_requires_unambiguous_table_neighbors():
    rows = [{'code': '00000001', 'year': 1, 'semester': 1},
            {'code': '00000002', 'year': 1, 'semester': 1}]
    book = ('--- Page 23 ---\n3.3 แผนการศึกษา\nรหัสวิชา ชื่อวิชา หน่วยกิต\n'
            '00000001 วิชาแรก 3(3-0-6)\n00000002 วิชาที่สอง 3(3-0-6)\n'
            '00000003 วิชาศูนย์หน่วยกิต 0(0-0-45)\n'
            '--- Page 100 ---\n00000003 วิชาศูนย์หน่วยกิต 0(0-0-45)\n')
    assert cfb.repair_with_book('', rows, book)
    added = next(r for r in rows if r['code'] == '00000003')
    assert (added['year'], added['semester'], added['credits']) == (1, 1, '0(0-0-45)')
    assert added['_code_from_book']['pdf_page'] == 23
    assert not cfb.repair_with_book('', rows, book)
    for changed_book, neighbors in [
        (book.replace('รหัสวิชา ชื่อวิชา หน่วยกิต\n', ''), rows[:2]),
        (book.replace('3.3 แผนการศึกษา', '3.4 คำอธิบายรายวิชา'), rows[:2]),
        (book.replace('รหัสวิชา ชื่อวิชา หน่วยกิต', '3.4 คำอธิบายรายวิชา\nรหัสวิชา ชื่อวิชา หน่วยกิต'), rows[:2]),
        (book, [rows[0], {**rows[1], 'semester': 2}]),
        (book, [rows[0]]),
        (book.replace('0(0-0-45)', '3(3-0-6)'), rows[:2]),
    ]:
        trial = [dict(r) for r in neighbors]
        cfb.repair_with_book('', trial, changed_book)
        assert not any(r['code'] == '00000003' for r in trial)

# Real layout of the book's course-description pages (Tesseract text): heading line, then the English name,
# sometimes wrapped over two lines.
BOOK_EN = "\n".join([
    "06016423 การออโตเมชั่นและโครงสร้างพื้นฐานที่สามารถโปรแกรมได้   3(2-2-5)",
    "INFRASTRUCTURE PROGRAMMABILITY AND",
    "AUTOMATION",
    "วิชาบังคับก่อน : 06016413 ...",
    "06016423 การออโตเมชั่นและโครงสร้างพื้นฐานที่สามารถโปรแกรมได้   3(2-2-5)",
    "INFRASTRUCTURE PROGRAMMABILITY AND AUTOMATION",
    "06016414 ระบบฐานข้อมูลแบบโนเอสคิวแอล   3(2-2-5)",
    "NOSQL DATABASE SYSTEMS",
    "06016414 ระบบฐานข้อมูลแบบโนเอสคิวแอล   3(2-2-5)",
    "NOSOL DATABASE SYSTEMS",
    "06016415 การเขียนโปรแกรมเชิงฟังก์ชัน   3(2-2-5)",
    "FUNCTIONAL PROGRAMMING",
    "06016415 การเขียนโปรแกรมเชิงฟังก์ชัน   3(2-2-5)",
    "FUNCTIONAL PROGRAMING",
])


def _course(code, name_en=None):
    return {"code": code, "name_th": "x", "name_en": name_en, "credits": "3(2-2-5)"}


# Break caught (2026-09-27): 32 courses in 6 plans had name_en NULL although the book prints the English name
# under every heading (courses recovered from the book got only name_th; qwen sometimes omits name_en).
def test_name_en_filled_from_book_joining_a_wrapped_line():
    courses = [_course("06016423")]
    cfb.fill_english_names("", courses, BOOK_EN)
    assert courses[0]["name_en"] == "INFRASTRUCTURE PROGRAMMABILITY AND AUTOMATION"


def test_name_en_tie_is_broken_only_by_the_other_ocr():
    courses = [_course("06016414"), _course("06016415")]
    cfb.fill_english_names("<td>ระบบฐานข้อมูลแบบโนเอสคิวแอล<br/>NOSQL DATABASE SYSTEMS</td>", courses, BOOK_EN)
    assert courses[0]["name_en"] == "NOSQL DATABASE SYSTEMS"
    assert courses[1]["name_en"] is None          # 1:1 and Typhoon has neither spelling -> do not guess


def test_name_en_never_overwrites_an_existing_value():
    courses = [_course("06016423", "FROM THE PLAN TABLE")]
    cfb.fill_english_names("", courses, BOOK_EN)
    assert courses[0]["name_en"] == "FROM THE PLAN TABLE"


# Break caught in the dry run (IT coop 4/1): an elective-slot row stamped with a real code ("วิชาเลือก หมวด
# ศึกษาทั่วไป 1" / 90643021) must not get that real course's English name — rule 3 leaves these rows alone too.
def test_name_en_skips_elective_slot_rows_with_a_stamped_code():
    courses = [{**_course("06016423"), "name_th": "วิชาเลือก หมวดศึกษาทั่วไป 1"}]
    cfb.fill_english_names("", courses, BOOK_EN)
    assert courses[0]["name_en"] is None


# ─── Thai names: consensus of the 7 main plans + the 4 program books (name_consensus.fix_plan_names) ───
from name_consensus import fix_plan_names

NOSQL = "ระบบฐานข้อมูลแบบโนเอสคิวแอล"


def _c(code, name):
    return {"code": code, "name_th": name, "name_en": None, "credits": "3(3-0-6)"}


def _book(**names):
    return {code: {"name": name} for code, name in names.items()}


# Break caught (2026-09-27): apply_name_consensus.py was a separate script, so every Lab 8B rerun silently put the
# OCR typos back (IT coop "…ภารบริการ"). The fix now runs inside the pipeline and only touches the plan being run.
def test_plan_typo_is_fixed_by_other_plans_and_the_books():
    mine = [_c("06026207", "ระบบฐานข้อมูลแบบโนเวสคิวแอล")]
    others = {"IT/no_coop": [_c("06016414", NOSQL)]}
    done = fix_plan_names("DSBA/coop", mine, others, {"DSBA": _book(**{"06026207": NOSQL})})
    assert mine[0]["name_th"] == NOSQL
    assert [d["code"] for d in done] == ["06026207"]


# Tesseract repeats the same misreading on every page ("อัลกอริทีม"), so a book is ONE vote, not one per line.
def test_systematic_book_misreading_does_not_beat_the_plans():
    right = "โครงสร้างข้อมูลและอัลกอริทึม"
    mine = [_c("06066301", right)]
    others = {"AIT": [_c("06066301", right)], "IT/coop": [_c("06066301", right)]}
    fix_plan_names("DSBA/coop", mine, others, {"DSBA": _book(**{"06066301": "โครงสร้างข้อมูลและอัลกอริทีม"})})
    assert mine[0]["name_th"] == right


# Similar names of DIFFERENT courses ("เกมขั้นต้น"/"เกมขั้นสูง") share a spelling family across codes; the
# winner must also have been read for THIS code by another source, or nothing changes.
def test_winner_must_be_attested_for_the_same_code():
    mine = [_c("06016447", "การพัฒนาเกมขั้นต้นด้วยเกมเอนจิ้น")]
    others = {"IT/no_coop": [_c("06016448", "การพัฒนาเกมขั้นสูงด้วยเกมเอนจิ้น")],
              "IT/coop": [_c("06016448", "การพัฒนาเกมขั้นสูงด้วยเกมเอนจิ้น")]}
    fix_plan_names("AIT", mine, others, {})
    assert mine[0]["name_th"] == "การพัฒนาเกมขั้นต้นด้วยเกมเอนจิ้น"


def test_slot_rows_and_wildcards_are_untouched():
    mine = [_c("9064xxxx", "วิชาเลือกหมวดวิชาศึกษาทั่วไป"), _c("90643021", "วิชาเลือก หมวดศึกษาทั่วไป 1")]
    others = {"AIT": [_c("90643021", "ผู้ประกอบการสมัยใหม่")]}
    fix_plan_names("IT/coop", mine, others, {"IT": _book(**{"90643021": "ผู้ประกอบการสมัยใหม่"})})
    assert [c["name_th"] for c in mine] == ["วิชาเลือกหมวดวิชาศึกษาทั่วไป", "วิชาเลือก หมวดศึกษาทั่วไป 1"]


# Rerunnable: votes always use the name the VLM read (kept byte-for-byte in _name_th_from), so a second run
# changes nothing, and a fix whose votes disappear is undone instead of sticking forever.
def test_rerun_is_stable_and_a_lost_majority_is_undone():
    raw = "คณิตศาสตร์โมโต่อเนื่อง"
    mine = [_c("06066000", raw)]
    others = {"AIT": [_c("06066000", "คณิตศาสตร์ไม่ต่อเนื่อง")]}
    books = {"IT": _book(**{"06066000": "คณิตศาสตร์ไม่ต่อเนื่อง"})}
    fix_plan_names("IT/no_coop", mine, others, books)
    assert mine[0]["name_th"] == "คณิตศาสตร์ไม่ต่อเนื่อง"
    assert fix_plan_names("IT/no_coop", mine, others, books) == []
    fix_plan_names("IT/no_coop", mine, {}, {})
    assert mine[0]["name_th"] == raw and "_name_th_from" not in mine[0]


# Review finding: the undo must restore the original bytes, not the "ํา"->"ำ" normalised form used for voting.
def test_undo_restores_the_original_bytes():
    raw = "การจัดการระบบสํานักงานผิด"                   # Tesseract-style "ํา"
    mine = [_c("06099999", raw)]
    right = "การจัดการระบบสำนักงาน"
    fix_plan_names("IT/no_coop", mine, {"AIT": [_c("06099999", right)]}, {"IT": _book(**{"06099999": right})})
    assert mine[0]["name_th"] == right
    fix_plan_names("IT/no_coop", mine, {}, {})
    assert mine[0]["name_th"] == raw


# Other plans' rows already fixed by this step still vote with their original VLM reading.
def test_other_plans_vote_with_their_original_reading():
    mine = [_c("06016420", "ระบบโครงสร้างพื้นฐานและการบริการ")]
    fixed = {**_c("06016420", "ระบบโครงสร้างพื้นฐานและการบริการ"), "_name_th_from": "ระบบโครงสร้างพื้นฐานและภารบริการ"}
    others = {"IT/coop": [fixed], "AIT": [_c("06016420", "ระบบโครงสร้างพื้นฐานและภารบริการ")]}
    fix_plan_names("IT/no_coop", mine, others, {})
    assert mine[0]["name_th"] == "ระบบโครงสร้างพื้นฐานและภารบริการ"


# Review finding (HIGH): book votes used to come from rows other plans had already repaired, so the result
# depended on which plan ran first. All four books now vote from their own index, identically for every plan.
def test_result_does_not_depend_on_other_plans_having_run_first():
    mine = [_c("06016414", "ระบบฐานข้อมูลแบบโนเอสคิวแวล")]
    others = {"DSBA/coop": [_c("06026207", "ระบบฐานข้อมูลแบบโนเวสคิวแอล")],
              "DSBA/no_coop": [_c("06026207", "ระบบฐานข้อมูลแบบโนนอสควิวแอล")]}
    books = {"IT": _book(**{"06016414": NOSQL}), "DSBA": _book(**{"06026207": NOSQL})}
    fix_plan_names("IT/coop", mine, others, books)
    assert mine[0]["name_th"] == NOSQL


# Review finding: rows the recovery step added/recoded took only the CODE from the book — the name is Typhoon's
# reading, so they vote (and can be corrected) like any VLM row; only split/_name_from_book rows are book names.
def test_rows_with_a_book_code_but_a_typhoon_name_are_vlm_votes():
    mine = [{**_c("06016422", "อินเทอร์เน็ตของสรรหสิ่ง"), "_code_from_book": {"from": None, "via": "name_in_term"}}]
    others = {"IT/coop": [_c("06016422", "อินเทอร์เน็ตของสรรพสิ่ง")]}
    fix_plan_names("IT/no_coop", mine, others, {"IT": _book(**{"06016422": "อินเทอร์เน็ตของสรรพสิ่ง"})})
    assert mine[0]["name_th"] == "อินเทอร์เน็ตของสรรพสิ่ง"


# Review finding: a plan listing the same code twice must still be ONE vote for that plan.
def test_duplicate_rows_in_one_plan_count_once():
    right = "สหกิจศึกษา"
    mine = [_c("06036147", right)]
    wrong = _c("06036147", "สหกิจศึกษาต่างประเทศ")
    others = {"BIT/no_coop": [wrong, dict(wrong), dict(wrong)]}
    fix_plan_names("BIT/coop", mine, others, {"BIT": _book(**{"06036147": right})})
    assert mine[0]["name_th"] == right                  # 1 (BIT/no_coop) vs 1 (book) + 1 (mine) — not 3 vs 2


# Review finding: the --recover-codes wiring (runs root / run name / sibling books) had no test, and retry runs
# (runs/IT/coop_retry) must not be renamed. Runs the real CLI on a throw-away runs/ + outputs/ tree.
def _recover(tmp_path, run):
    import json, os, subprocess, sys
    lab7 = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "src" / "ocr_system" / "lab7b_curriculum.py"
    out = tmp_path / "runs" / run / "lab7b_output"
    out.mkdir(parents=True)
    (out / "intermediate_vlm.md").write_text("", encoding="utf-8")
    pred = out / "pred_vlm.json"
    pred.write_text(json.dumps({"courses": [_c("06016414", "ระบบฐานข้อมูลแบบโนเอสคิวแวล")]}), encoding="utf-8")
    subprocess.run([sys.executable, str(lab7), "--recover-codes", str(pred), "--book-ocr",
                    str(tmp_path / "outputs" / "it" / "it_curriculum_ocr.txt")], check=True, capture_output=True,
                   env={**os.environ, "PYTHONUTF8": "1"})             # same as run_lab8b_*.py (Thai output)
    return json.loads(pred.read_text(encoding="utf-8"))["courses"][0]["name_th"]


def test_recover_codes_uses_every_program_book_and_skips_retry_runs(tmp_path):
    for prog, code in (("it", "06016414"), ("dsba", "06026207")):
        (tmp_path / "outputs" / prog).mkdir(parents=True)
        (tmp_path / "outputs" / prog / f"{prog}_curriculum_ocr.txt").write_text(
            f"{code} {NOSQL}   3(2-2-5)\n{code} {NOSQL}   3(2-2-5)\n", encoding="utf-8")
    assert _recover(tmp_path, "IT/coop") == NOSQL              # IT book + DSBA book (sibling folder) outvote 1 VLM read
    assert _recover(tmp_path, "IT/coop_retry") == "ระบบฐานข้อมูลแบบโนเอสคิวแวล"


# ─── "A หรือ B" pairs: names fixed inside import-lab7b (was the separate apply_or_course_names.py) ───
import lab8b_curriculum_db as lab8b

DSBA_OR_MD = ("<tr><td>06026259<br/>หรือ 06026260</td><td>สหกิจศึกษาทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ<br/>"
              "COOPERATIVE EDUCATION IN DATA SCIENCE AND BUSINESS ANALYTICS<br/>"
              "สหกิจศึกษาต่างประเทศทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ<br/>"
              "OVERSEA COOPERATIVE EDUCATION IN DATA SCIENCE AND BUSINESS ANALYTICS</td><td>6 (0-35-0)</td></tr>")
BIT_OR_MD = ('<tr><td rowspan="3">06036147<br/>หรือ 06036148</td><td>สหกิจศึกษา<br/>COOPERATIVE EDUCATION</td>'
             '<td>6(0-35-0)</td></tr><tr><td>สหกิจศึกษาต่างประเทศ<br/>OVERSEA COOPERPIENT EDUCATION</td><td></td></tr>'
             '<tr><td colspan="2">รวม</td><td>6</td></tr></table>')


def _convert(courses, md):
    out, _ = lab8b.convert_lab7b({"courses": courses}, program_id="X", program_name="x", total_credits=120,
                                 years=4, markdown=md)
    return {c["code"]: c for c in out["courses"]}


# Break caught (2026-09-27): the committed DSBA coop DB still had both 06026259/06026260 named "สหกิจศึกษาทาง…"
# because the fix lived in a separate script that a Lab 8B rerun silently undid.
def test_or_pair_names_are_fixed_during_import():
    row = {"code": "06026259 หรือ 06026260", "name_th": "สหกิจศึกษาทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ",
           "name_en": "OVERSEA COOPERATIVE EDUCATION IN DATA SCIENCE AND BUSINESS ANALYTICS",
           "credits": "6 (0-35-0)", "year": 4, "semester": 2, "category": "x", "type": "เลือก"}
    got = _convert([row], DSBA_OR_MD)
    assert got["06026259"]["name_th"] == "สหกิจศึกษาทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ"
    assert got["06026260"]["name_th"] == "สหกิจศึกษาต่างประเทศทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ"
    # both codes carried the same (second) English name -> each gets its own line from the same cell
    assert got["06026259"]["name_en"] == "COOPERATIVE EDUCATION IN DATA SCIENCE AND BUSINESS ANALYTICS"
    assert got["06026260"]["name_en"] == "OVERSEA COOPERATIVE EDUCATION IN DATA SCIENCE AND BUSINESS ANALYTICS"


# English names that already differ are left alone: the Markdown line can carry an OCR typo ("COOPERPIENT").
def test_or_pair_keeps_distinct_english_names():
    rows = [{"code": "06036147", "name_th": "สหกิจศึกษาต่างประเทศ", "name_en": "COOPERATIVE EDUCATION",
             "credits": "6(0-35-0)", "year": 4, "semester": 1, "category": "x", "type": "เลือก"},
            {"code": "06036148", "name_th": "สหกิจศึกษาต่างประเทศ", "name_en": "OVERSEA COOPERATIVE EDUCATION",
             "credits": "6(0-35-0)", "year": 4, "semester": 1, "category": "x", "type": "เลือก"}]
    got = _convert(rows, BIT_OR_MD)
    assert got["06036147"]["name_th"] == "สหกิจศึกษา"
    assert got["06036148"]["name_th"] == "สหกิจศึกษาต่างประเทศ"
    assert got["06036148"]["name_en"] == "OVERSEA COOPERATIVE EDUCATION"


# Break caught on a fresh clone (2026-09-27): reports stored absolute paths ("D:\...\ocr_system\outputs\...") so every
# run on another machine rewrote committed files and leaked the local path. Paths inside the repo are stored relative.
def test_report_paths_are_repo_relative():
    # The same tests can validate another worktree's imported production module.
    repo = Path(lab8b.__file__).resolve().parents[3]
    book = repo / "outputs" / "ait" / "ait_curriculum_ocr.txt"
    assert lab8b.repo_relative(book) == "outputs/ait/ait_curriculum_ocr.txt"
    assert lab8b.repo_relative(str(book)) == "outputs/ait/ait_curriculum_ocr.txt"
    outside = repo.parent / "outside-source.txt"
    assert lab8b.repo_relative(outside) == str(outside.resolve())
    outside = Path("C:/elsewhere/x.txt") if book.drive else Path("/elsewhere/x.txt")
    assert lab8b.repo_relative(outside) == str(outside)       # outside the repo: keep as given


# Review finding: "shared English name" must be judged within ONE pair — two different pairs that happen to carry
# the same English name are not the conflation symptom.
def test_or_pair_shared_english_is_scoped_per_pair():
    from or_course_names import apply_to_courses
    courses = [{"code": "A1", "name_th": "ก", "name_en": "SAME"}, {"code": "A2", "name_th": "ข", "name_en": "OTHER"},
               {"code": "B1", "name_th": "ค", "name_en": "SAME"}, {"code": "B2", "name_th": "ง", "name_en": "ELSE"}]
    apply_to_courses(courses, [{"A1": ("ก", "FROM MD 1"), "A2": ("ข", "FROM MD 2")},
                               {"B1": ("ค", "FROM MD 3"), "B2": ("ง", "FROM MD 4")}])
    assert [c["name_en"] for c in courses] == ["SAME", "OTHER", "SAME", "ELSE"]
