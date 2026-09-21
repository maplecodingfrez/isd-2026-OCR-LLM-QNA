"""ทดสอบ prerequisite_alt ("A หรือ B") กับ CHK5 — สำเนา DB ของ BIT no-coop (ไม่แตะไฟล์จริง)
รัน: PYTHONUTF8=1 ../.venv/Scripts/python.exe experiments/prereq_from_book_ocr_2026-09-21/test_prereq_alt.py"""
import shutil, sqlite3, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "ocr_system"))
import lab8b_curriculum_db as m

src = ROOT / "runs" / "BIT" / "no_coop" / "lab8b_output" / "curriculum.db"
ok = fail = 0


def check(name, cond):
    global ok, fail
    ok += cond
    fail += (not cond)
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")


def chk5(conn):
    return {r["id"]: r for r in m.verify_db(conn)}["CHK5"]["ok"]


with tempfile.TemporaryDirectory() as td:
    db = Path(td) / "t.db"
    shutil.copy(src, db)
    conn = m.open_db(db)
    conn.executescript(m.PREREQ_ALT_DDL)
    conn.execute("DELETE FROM prerequisite")
    conn.execute("DELETE FROM prerequisite_alt")
    # เลือกวิชา 3 ตัวที่อยู่คนละภาคเรียน
    rows = conn.execute("SELECT code, year*10+semester AS t FROM plan_item WHERE code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' GROUP BY code ORDER BY t").fetchall()
    early, late1, late2 = rows[0]["code"], rows[-1]["code"], rows[-2]["code"]
    mid = rows[len(rows) // 2]["code"]
    check("มีวิชาคนละภาคเรียนให้ทดสอบ", rows[0]["t"] < rows[len(rows)//2]["t"] < rows[-1]["t"])

    # 1) "และ" ธรรมดา: mid ต้องผ่าน late1 (อยู่หลัง) -> CHK5 ผิด
    conn.execute("INSERT INTO prerequisite VALUES (?,?,'pre')", (mid, late1))
    check("แถวธรรมดาที่อยู่หลัง -> CHK5 ไม่ผ่าน", chk5(conn) is False)

    # 2) "หรือ": mid ต้องผ่าน (late1 หรือ early) — early อยู่ก่อน -> ผ่าน
    conn.execute("INSERT INTO prerequisite VALUES (?,?,'pre')", (mid, early))
    check("ไม่มี prerequisite_alt: ต้องผ่านทั้งคู่ -> CHK5 ยังไม่ผ่าน", chk5(conn) is False)
    conn.executemany("INSERT INTO prerequisite_alt VALUES (?,?,1)", [(mid, late1), (mid, early)])
    check("มี prerequisite_alt และทางเลือกหนึ่งอยู่ก่อน -> CHK5 ผ่าน", chk5(conn) is True)

    # 3) "หรือ" แต่ทุกทางอยู่หลัง -> ผิดจริง
    conn.execute("DELETE FROM prerequisite WHERE requires=?", (early,))
    conn.execute("DELETE FROM prerequisite_alt")
    conn.execute("INSERT INTO prerequisite VALUES (?,?,'pre')", (mid, late2))
    conn.executemany("INSERT INTO prerequisite_alt VALUES (?,?,1)", [(mid, late1), (mid, late2)])
    check("'หรือ' ที่ทุกทางอยู่หลัง -> CHK5 ไม่ผ่าน", chk5(conn) is False)

    # 4) DB ที่ไม่มีตาราง prerequisite_alt -> ทำงานเหมือนเดิม ไม่ error
    conn.execute("DROP TABLE prerequisite_alt")
    check("ไม่มีตาราง prerequisite_alt -> ไม่ error (CHK5 ยังตรวจตามเดิม)", chk5(conn) is False)
    conn.close()

print(f"ผ่าน {ok} · ไม่ผ่าน {fail}")
sys.exit(1 if fail else 0)
