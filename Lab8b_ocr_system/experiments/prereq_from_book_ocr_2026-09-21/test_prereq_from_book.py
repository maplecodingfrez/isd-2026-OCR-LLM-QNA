"""ทดสอบ prereq_from_book — รัน (จาก Lab8b_ocr_system): ../.venv/Scripts/python.exe experiments/prereq_from_book_ocr_2026-09-21/test_prereq_from_book.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "ocr_system")]
import prereq_from_book as P  # noqa: E402

fails = 0


def check(name, cond):
    global fails
    print(("  [ ok ] " if cond else "  [FAIL] ") + name)
    fails += 0 if cond else 1


def run(txt, wanted, known=None):
    return P.extract_prerequisites(txt.strip("\n").split("\n"), wanted, known_codes=known)


BOOK = """
06036114 การพัฒนาเว็บแอปพลิเคชันโดยใช้เฟรมเวิร์ก                 3(2-2-5)
WEB APPLICATION DEVELOPMENT USING FRAMEWORKS
วิชาบังคับก่อน :      06036119 พื้นฐานการเขียนโปรแกรม หรือ
06036122 การสื่อสารด้วยภาพสำหรับธุรกิจ
PREREQUISITE :        06036119 PROGRAMMING FUNDAMENTALS
OR 06036122 VISUAL COMMUNICATION
FOR BUSINESS
คำอธิบายรายวิชา ...
06036113 การออกแบบส่วนต่อประสานกับมนุษย์       3(3-0-6)
HUMAN INTERFACE DESIGN
วิชาบังคับก่อน : ไม่มี
PREREQUISITE : NONE
06036115 วิชาทดสอบ       3(3-0-6)
TEST
วิชาบังคับก่อน : 06036113 การออกแบบ
PREREQUISITE : 06036113 HUMAN INTERFACE DESIGN
06036116 วิชาไม่มีช่องนี้       3(3-0-6)
NO FIELD HERE
06036117 วิชาอื่น       3(3-0-6)
TEST 2
รายวิชาบังคับก่อน : 06036115 ทดสอบ หรือ รายวิชาเทียบเคียง
PREREQUISITE : 06036115 TEST or EQUIVALENT SUBJECT
06036118 วิชาสอง       3(3-0-6)
TWO
วิชาบังคับก่อน : 06036113 ก และ 06036115 ข
PREREQUISITE : 06036113 A AND 06036115 B
06036119 พื้นฐานการเขียนโปรแกรม       3(2-2-5)
PROGRAMMING FUNDAMENTALS
วิชาบังคับก่อน : ไม่มี
06036122 การสื่อสารด้วยภาพ       3(3-0-6)
VISUAL
วิชาบังคับก่อน : 06036999 เลขเพี้ยน
PREREQUISITE : 06036999 GARBLED
"""
KNOWN = ["06036113", "06036114", "06036115", "06036116", "06036117", "06036118", "06036119", "06036122"]
r = run(BOOK, KNOWN, KNOWN)

print("รูปแบบที่พบจริง")
check("'A หรือ B' ข้ามบรรทัด (ไทยต่อบรรทัดถัดไป + อังกฤษ OR ขึ้นบรรทัดใหม่)", r["06036114"]["requires"] == ["06036119", "06036122"] and r["06036114"]["op"] == "or")
check("'ไม่มี' → none", r["06036113"]["status"] == "none")
check("รหัสเดียว", r["06036115"]["requires"] == ["06036113"] and r["06036115"]["op"] is None)
check("'หรือ รายวิชาเทียบเคียง' ต่อท้ายรหัสเดียว ไม่ใช่ or ของรหัส", r["06036117"]["requires"] == ["06036115"] and r["06036117"]["op"] is None)
check("'A และ B' → and", r["06036118"]["requires"] == ["06036113", "06036115"] and r["06036118"]["op"] == "and")

print("ต้องไม่เดา")
check("ไม่มีช่อง prerequisite ในรายวิชา → not_found (ไม่ใช่ none)", r["06036116"]["status"] == "not_found")
check("รหัสที่อ่านมาไม่อยู่ใน known_codes (OCR เพี้ยน) → unreadable ไม่ใช่ none", r["06036122"]["status"] == "unreadable" and r["06036122"]["dropped"] == ["06036999"])
check("รหัสที่ไม่มีหัวรายวิชาเลย → not_found", run(BOOK, ["99999999"], KNOWN)["99999999"]["status"] == "not_found")
check("ไม่ข้ามไปหยิบ prerequisite ของรายวิชาถัดไป (06036116 ไม่ได้ค่าของ 06036117)", r["06036116"]["requires"] == [])

print("to_gt_string")
check("รูปแบบเดียวกับเฉลย", [P.to_gt_string(r[k]) for k in ("06036114", "06036113", "06036118", "06036116")] == ["06036119 หรือ 06036122", "ไม่มี", "06036113, 06036115", None])

print("ไทยกับอังกฤษไม่ตรงกัน")
X = """
06036120 วิชาเอ็กซ์       3(3-0-6)
X
วิชาบังคับก่อน : 06036113 ก หรือ 06036115 ข
PREREQUISITE : 06036113 A
"""
x = run(X, ["06036120"], KNOWN)["06036120"]
check("ตัวอย่างส่วนที่ตรงกันทั้งสองภาษา + ติดธง th_en_partial", x["requires"] == ["06036113"] and x["note"] == "th_en_partial")

print(f"\n{'ผ่านทั้งหมด' if not fails else 'ไม่ผ่าน ' + str(fails) + ' ข้อ'}")
sys.exit(1 if fails else 0)
