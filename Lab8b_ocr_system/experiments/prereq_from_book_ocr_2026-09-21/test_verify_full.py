"""ทดสอบ verify_full_db (CHK1F/CHK7F — นับหน่วยกิตของช่อง plan_slot) ด้วยฐานข้อมูลสังเคราะห์ในหน่วยความจำ
รัน (จาก Lab8b_ocr_system): ../.venv/Scripts/python.exe experiments/prereq_from_book_ocr_2026-09-21/test_verify_full.py

ข้อมูลจำลอง (หลักสูตร 30 หน่วยกิต ตาม CHECK ของตาราง program):
  ภาค 1/1: วิชาปกติ 3 วิชา (9) + wildcard (3) + "เลือก 1 กลุ่ม" ที่มีสมาชิก 3 วิชาใน plan_item แต่นับ 3 = 15
  ภาค 1/2: วิชาปกติ 5 วิชา (15)
  นับตามเล่ม = 30; plan_item อย่างเดียว = 9 + 9 + 15 = 33 (นับสมาชิกกลุ่มทุกตัว และไม่มี wildcard)"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "ocr_system")]
import lab8b_curriculum_db as D  # noqa: E402

fails = 0


def check(name, cond):
    global fails
    print(("  [ ok ] " if cond else "  [FAIL] ") + name)
    fails += 0 if cond else 1


def make(declared, with_slots=True):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(D.DDL)
    if with_slots:
        conn.executescript(D.PLAN_SLOT_DDL)
    conn.execute("INSERT INTO program (program_id, name_th, total_credits, years) VALUES ('T','ทดสอบ',?,1)", (declared,))
    return conn


def add_course(conn, code, credits=3, year=1, sem=1):
    conn.execute("INSERT INTO course (code, name_th, credits) VALUES (?,?,?)", (code, "วิชา " + code, credits))
    conn.execute("INSERT INTO plan_item (program_id, year, semester, code, credits) VALUES ('T',?,?,?,?)",
                 (year, sem, code, credits))


def add_slot(conn, kind, credits, code=None, members=(), year=1, sem=1):
    cur = conn.execute("INSERT INTO plan_slot (program_id, year, semester, kind, code, name_th, credits) "
                       "VALUES ('T',?,?,?,?,?,?)", (year, sem, kind, code, "ช่อง " + kind, credits))
    for m in members:
        conn.execute("INSERT INTO plan_slot_member (slot_id, group_no, code) VALUES (?,1,?)", (cur.lastrowid, m))


def scenario(declared):
    c = make(declared)
    for code in ("10000001", "10000002", "10000003"):           # 1/1 วิชาปกติ
        add_course(c, code)
    for code in ("10000004", "10000005", "10000006"):           # 1/1 สมาชิกกลุ่ม "เลือก 1"
        add_course(c, code)
    for i in range(1, 6):                                       # 1/2 วิชาปกติ 5 วิชา
        add_course(c, f"2000000{i}", sem=2)
    add_slot(c, "wildcard", 3, code="0000xxxx")
    add_slot(c, "choose_group", 3, members=("10000004", "10000005", "10000006"))
    return c


print("นับช่องถูก: ภาค 1/1 = 9 + wildcard 3 + เลือก 1 กลุ่ม 3 (ไม่ใช่ 9) = 15; ภาค 1/2 = 15; รวม 30")
c = scenario(30)
old = {r["id"]: r["ok"] for r in D.verify_db(c)}
full = {r["id"]: r["ok"] for r in D.verify_full_db(c)}
check("CHK1 เดิม (plan_item อย่างเดียว = 33) ไม่ผ่าน — พฤติกรรมเดิมไม่เปลี่ยน", old["CHK1"] is False)
check("CHK1F (นับช่อง = 30) ผ่าน", full["CHK1F"] is True)
check("CHK7F ผ่าน (15 และ 15 หน่วยกิตอยู่ระหว่าง 9-22)", full["CHK7F"] is True)
check("verify_db ยังคืน 7 ข้อเดิม ไม่มี CHK1F/CHK7F ปนเข้ามา", not any(r["id"].endswith("F") for r in D.verify_db(c)))

print("ผลรวมไม่ตรงเล่ม (ประกาศ 33 แต่นับตามเล่มได้ 30)")
full2 = {r["id"]: r for r in D.verify_full_db(scenario(33))}
check("CHK1F ไม่ผ่านเมื่อ 30 != 33 และ detail บอกทั้งสองตัวเลข", full2["CHK1F"]["ok"] is False and "30" in full2["CHK1F"]["detail"] and "33" in full2["CHK1F"]["detail"])

print("หัวกลุ่มหาย -> วิชาในกลุ่มถูกนับเป็นวิชาปกติ ภาคเกิน 22 (เหมือน IT 2/2)")
c3 = make(30)
for i in range(1, 9):
    add_course(c3, f"3000000{i}")                                # 8 วิชา = 24 หน่วยกิตในภาค 1/1 ไม่มี slot ครอบ
add_slot(c3, "wildcard", 3, code="0000xxxx", year=2, sem=1)     # มี slot อยู่ในฐานข้อมูล (ภาคอื่น) จึงถูกตรวจ
full3 = {r["id"]: r for r in D.verify_full_db(c3)}
check("CHK7F ไม่ผ่านเมื่อภาค 1/1 = 24 หน่วยกิต และ detail ระบุภาค", full3["CHK7F"]["ok"] is False and "24" in full3["CHK7F"]["detail"] and "1/1" in full3["CHK7F"]["detail"])

print("ไม่มีข้อมูล plan_slot -> ไม่ตรวจ (ลิสต์ว่าง ไม่ใช่ \"ผ่าน\")")
c4 = make(30, with_slots=False)
add_course(c4, "40000001")
check("ไม่มีตาราง plan_slot -> []", D.verify_full_db(c4) == [])
c5 = make(30)
add_course(c5, "50000001")
check("ตาราง plan_slot ว่าง -> []", D.verify_full_db(c5) == [])

print("ภาคสหกิจ (วิชาเดียว 6 หน่วยกิต) ยกเว้นเหมือน CHK7 เดิม")
c6 = make(30)
add_course(c6, "60000001", credits=6)
add_slot(c6, "wildcard", 0, code="0000xxxx")
check("CHK7F ยกเว้นภาคบล็อก (ไม่ตกที่ 6 หน่วยกิต)", {r["id"]: r["ok"] for r in D.verify_full_db(c6)}["CHK7F"] is True)

print(f"\n{'ผ่านทั้งหมด' if not fails else 'ไม่ผ่าน ' + str(fails) + ' ข้อ'}")
sys.exit(1 if fails else 0)
