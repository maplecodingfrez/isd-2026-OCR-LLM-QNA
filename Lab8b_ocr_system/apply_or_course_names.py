"""แก้ชื่อวิชาคู่ "A หรือ B" (เช่น สหกิจศึกษาในประเทศ/ต่างประเทศ) ที่ตาราง course ได้ชื่อซ้ำกันผิด
— ดู src/ocr_system/or_course_names.py สำหรับสาเหตุและกฎที่ใช้แก้ (กฎเชิงกำหนด ไม่ใช้เฉลย ไม่เดา)

รันเฉพาะ 7 แผนหลัก (runs/<แผน>/lab7b_output/intermediate_vlm.md + lab8b_output/curriculum.db)
ไม่แตะรอบทดลอง (retry/dewm/ctrl) เพื่อเก็บเป็นหลักฐานของการทดลองเดิมไว้ (เหมือน apply_name_consensus.py --only-main)

    python apply_or_course_names.py           # dry-run: แสดงสิ่งที่จะแก้ ไม่เขียนไฟล์
    python apply_or_course_names.py --apply   # แก้ course.name_th ใน curriculum.json (สำรอง .before_or_names.json)
                                               # และในตาราง course ของ curriculum.db
"""
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "ocr_system"))
from or_course_names import apply_to_courses, fix_or_pair_names  # noqa: E402

APPLY = "--apply" in sys.argv

MAIN_RUNS = {
    "AIT": "AIT", "BIT/no_coop": "BIT/no_coop", "BIT/coop": "BIT/coop",
    "DSBA/no_coop": "DSBA/no_coop", "DSBA/coop": "DSBA/coop",
    "IT/no_coop": "IT/no_coop", "IT/coop": "IT/coop",
}

total_fixes = 0
for label, rel in MAIN_RUNS.items():
    md_path = ROOT / "runs" / rel / "lab7b_output" / "intermediate_vlm.md"
    cur_path = ROOT / "runs" / rel / "lab8b_output" / "curriculum.json"
    db_path = ROOT / "runs" / rel / "lab8b_output" / "curriculum.db"
    if not md_path.exists() or not cur_path.exists():
        continue
    fixes = fix_or_pair_names(md_path.read_text(encoding="utf-8"))
    if not fixes:
        continue
    data = json.loads(cur_path.read_text(encoding="utf-8"))
    n = apply_to_courses(data["courses"], fixes)
    if not n:
        continue
    print(f"{label}: แก้ {n} รายการ")
    for code, name in fixes.items():
        print(f"   {code} -> {name!r}")
    total_fixes += n
    if APPLY:
        shutil.copy(cur_path, cur_path.with_suffix(".before_or_names.json"))
        cur_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        conn = sqlite3.connect(db_path)
        for code, name in fixes.items():
            conn.execute("UPDATE course SET name_th = ? WHERE code = ?", (name, code))
        conn.commit()
        conn.close()

print(f"\nรวม {total_fixes} รายการ{'(เขียนแล้ว)' if APPLY else ' (dry-run — รัน --apply เพื่อเขียนจริง)'}")
