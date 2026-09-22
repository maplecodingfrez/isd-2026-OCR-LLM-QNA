"""ทดสอบ or_course_names.py — แก้ชื่อวิชาคู่ "A หรือ B" ที่ตาราง course ได้ชื่อซ้ำผิด
รัน (จาก Lab8b_ocr_system): PYTHONUTF8=1 ../.venv/Scripts/python.exe experiments/or_course_names_2026-09-22/test_or_course_names.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "ocr_system")]
import or_course_names as O  # noqa: E402

fails = 0


def check(name, cond):
    global fails
    print(("  [ ok ] " if cond else "  [FAIL] ") + name)
    fails += 0 if cond else 1


print("กรณีจริง 1: BIT coop (rowspan ครอบชื่อคนละแถว)")
BIT = ('<tr><td rowspan="3">06036147<br/>หรือ 06036148</td><td>สหกิจศึกษา<br/>COOPERATIVE EDUCATION</td>'
       '<td>6(0-35-0)</td></tr><tr><td>สหกิจศึกษาต่างประเทศ<br/>OVERSEA COOPERPIENT EDUCATION</td><td></td></tr>'
       '<tr><td colspan="2">รวม</td><td>6</td></tr>')
r = O.fix_or_pair_names(BIT)
check("06036147 = สหกิจศึกษา", r.get("06036147") == "สหกิจศึกษา")
check("06036148 = สหกิจศึกษาต่างประเทศ", r.get("06036148") == "สหกิจศึกษาต่างประเทศ")

print("\nกรณีจริง 2: DSBA coop (เซลล์เดียวยัดชื่อรวม)")
DSBA = ('<tr><td>06026259<br/>หรือ 06026260</td><td>สหกิจศึกษาทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ<br/>'
        'COOPERATIVE EDUCATION IN DATA SCIENCE AND BUSINESS ANALYTICS<br/>'
        'สหกิจศึกษาต่างประเทศทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ<br/>'
        'OVERSEA COOPERERATIVE EDUCATION IN DATA SCIENCE AND BUSINESS ANALYTICS</td><td>6 (0-35-0)</td></tr>')
r = O.fix_or_pair_names(DSBA)
check("06026259 = ชื่อในประเทศ", r.get("06026259") == "สหกิจศึกษาทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ")
check("06026260 = ชื่อต่างประเทศ", r.get("06026260") == "สหกิจศึกษาต่างประเทศทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ")

print("\nกรณีที่ต้องไม่แก้ (จำนวนชื่อไม่ตรงจำนวนรหัส หรือรูปแบบกำกวม — ห้ามเดา)")
ONLY_ONE_NAME = '<tr><td>10000001<br/>หรือ 10000002</td><td>ชื่อเดียว<br/>ONLY ONE NAME</td><td>6(0-35-0)</td></tr>'
check("มีแค่ 1 ชื่อสำหรับ 2 รหัส -> ไม่แก้เลย", O.fix_or_pair_names(ONLY_ONE_NAME) == {})

THREE_NAMES_TWO_CODES = ('<tr><td>10000003<br/>หรือ 10000004</td><td>ชื่อหนึ่ง<br/>NAME ONE<br/>ชื่อสอง<br/>NAME TWO<br/>'
                         'ชื่อสาม<br/>NAME THREE</td><td>6(0-35-0)</td></tr>')
check("มี 3 ชุดชื่อสำหรับ 2 รหัส (เกิน) -> ไม่แก้เลย", O.fix_or_pair_names(THREE_NAMES_TWO_CODES) == {})

NO_OR = '<tr><td>10000005</td><td>วิชาเดี่ยว ๆ ไม่มีหรือ<br/>SINGLE COURSE</td><td>3(3-0-6)</td></tr>'
check("แถวปกติไม่มี 'หรือ' -> ไม่จับ", O.fix_or_pair_names(NO_OR) == {})

AMBIGUOUS_MERGE = '<tr><td rowspan="2">10000006 10000007</td><td>วิชาเอ<br/>COURSE A</td><td>3(0-9-0)</td></tr><tr><td>วิชาบีคนละเรื่อง<br/>COURSE B</td><td>3(3-0-6)</td></tr>'
check("รหัสติดกันไม่มีคำว่า 'หรือ' (ambiguous merge แบบเดิม) -> ไม่จับ", O.fix_or_pair_names(AMBIGUOUS_MERGE) == {})

print("\napply_to_courses: แก้ list ของ course dict ในที่เดิม")
courses = [{"code": "06036147", "name_th": "สหกิจศึกษา"}, {"code": "06036148", "name_th": "สหกิจศึกษา"},
           {"code": "99999999", "name_th": "ไม่เกี่ยว"}]
n = O.apply_to_courses(courses, {"06036147": "สหกิจศึกษา", "06036148": "สหกิจศึกษาต่างประเทศ"})
check("แก้เฉพาะแถวที่ชื่อเปลี่ยนจริง (06036147 ชื่อเดิมถูกอยู่แล้ว ไม่นับ)", n == 1)
check("06036148 ถูกแก้เป็นชื่อที่ถูกต้อง", courses[1]["name_th"] == "สหกิจศึกษาต่างประเทศ")
check("แถวที่ไม่เกี่ยวไม่ถูกแตะ", courses[2]["name_th"] == "ไม่เกี่ยว")

print(f"\n{'ผ่านทั้งหมด' if not fails else 'ไม่ผ่าน ' + str(fails) + ' ข้อ'}")
sys.exit(1 if fails else 0)
