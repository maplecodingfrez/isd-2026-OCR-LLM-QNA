"""แพตช์ผล Lab7B ของ AIT: แทนที่วิชาจากหน้า 19 (ปีที่1/ภาค1 + ปีที่1/ภาค2) ใน
work/lab7b_run_ait/pred_vlm.json (40 วิชา, รันด้วย MAX_IMAGE_DIM=1280 ค่า default)
ด้วยผลจาก work/lab7b_patch_page19_1600/pred_vlm.json (13 วิชา, รันแยกที่ 1600px
ซึ่งอ่านติดวิชา 90641008 ที่ 1280px อ่านตกไป — ดู PROGRESS.md หัวข้อ "ลองไม่ย่อดูก่อน")

ทำไมต้อง merge แบบระบุตำแหน่ง (index) ไม่ใช่จับคู่ด้วยรหัสวิชา (by code):
รหัส wildcard "9064xxxx" ปรากฏซ้ำ 2 จุดใน pred_vlm.json เดิม — index 11 (มาจากหน้า 19
จริง ๆ) กับ index 35 (มาจากหน้าอื่นทีหลัง คนละวิชากันเลย) ถ้า merge ด้วยรหัสจะลบของ
หน้าอื่นทิ้งผิด ๆ โดยไม่ตั้งใจ จึงต้อง hardcode ลำดับ 12 รายการแรกที่รู้แน่ชัดว่ามาจาก
หน้า 19 (ยืนยันจาก intermediate_vlm.md ของรอบรันเต็ม 4 หน้าเดิม) แล้ว assert รหัสให้ตรง
เป๊ะก่อน replace เสมอ — ถ้าไม่ตรง (เช่นมีคนรัน lab7b ใหม่ทั้งชุดแล้วลำดับเปลี่ยน) ให้ script
พังทันทีแทนที่จะเดา/silently corrupt ข้อมูล
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# อัปเดตพาธหลังจัดโฟลเดอร์ใหม่ (2026-09-16): work/lab7b_run_ait -> runs/AIT/lab7b_output,
# work/lab7b_patch_page19_1600 -> archive/lab7b_patch_page19_1600 (ของเก่า ไม่ลบทิ้ง)
# หมายเหตุ: สคริปต์นี้ผูกกับลำดับ index ของ pred_vlm.json รุ่นเก่ามาก (ตอนแพตช์จริง)
# ถ้ารัน AIT ใหม่ไปหลายรอบแล้ว EXPECTED_HEAD_CODES ด้านล่างจะไม่ตรง สคริปต์จะ assert พังเอง
# (ตั้งใจให้พังแทนที่จะเดา — ดู docstring ด้านบน) ไม่ต้องรันซ้ำถ้าไม่มั่นใจว่าไฟล์ต้นทางตรงกัน
ORIGINAL = ROOT / "runs" / "AIT" / "lab7b_output" / "pred_vlm.json"
PATCH = ROOT / "archive" / "lab7b_patch_page19_1600" / "pred_vlm.json"
BACKUP = ROOT / "runs" / "AIT" / "lab7b_output" / "pred_vlm.before_patch19.json"

# 12 รายการแรกของ pred_vlm.json เดิม ที่ยืนยันแล้วว่ามาจากหน้า 19 ทั้งหมด
# (5 วิชา ปีที่1/1 + 4 วิชา ปีที่1/2 + 3 วิชาที่ Typhoon-OCR รอบแรก hallucinate
#  หัวตาราง "ปีที่ 2 ภาคการศึกษา" ทับเข้ามาผิด ๆ ทั้งที่จริงยังเป็นส่วนของ ปีที่1/2)
EXPECTED_HEAD_CODES = [
    "06046400", "06046402", "06066000", "06066001", "06066303",
    "06046401", "06046403", "06066301", "06046404",
    "90641007", "90641004", "9064xxxx",
]


def main() -> None:
    if not ORIGINAL.exists():
        sys.exit(f"[ERROR] ไม่พบไฟล์ต้นฉบับ: {ORIGINAL}")
    if not PATCH.exists():
        sys.exit(f"[ERROR] ไม่พบไฟล์แพตช์: {PATCH}")

    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    patch = json.loads(PATCH.read_text(encoding="utf-8"))

    head = original["courses"][: len(EXPECTED_HEAD_CODES)]
    head_codes = [c["code"] for c in head]
    if head_codes != EXPECTED_HEAD_CODES:
        sys.exit(
            "[ERROR] รหัสวิชา 12 อันดับแรกของ pred_vlm.json ไม่ตรงกับที่คาดไว้ "
            "(ไฟล์อาจถูกรันใหม่/แก้ไปแล้ว) — หยุดเพื่อไม่ให้ merge ผิดตำแหน่ง\n"
            f"  คาดไว้ : {EXPECTED_HEAD_CODES}\n"
            f"  เจอจริง: {head_codes}"
        )

    tail = original["courses"][len(EXPECTED_HEAD_CODES):]
    merged_courses = patch["courses"] + tail

    shutil.copyfile(ORIGINAL, BACKUP)

    original["courses"] = merged_courses
    ORIGINAL.write_text(
        json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"สำรองไฟล์เดิมไว้ที่: {BACKUP}")
    print(f"แทนที่ {len(head)} วิชา (หน้า 19, เดิม) ด้วย {len(patch['courses'])} วิชา (หน้า 19, แพตช์ 1600px)")
    print(f"รวมทั้งหมด: {len(original['courses'])} วิชา (เดิม {len(head) + len(tail)} วิชา)")

    old_codes = {c["code"] for c in head}
    new_codes = {c["code"] for c in patch["courses"]}
    added = new_codes - old_codes
    if added:
        print(f"รหัสที่เพิ่มมาใหม่: {', '.join(sorted(added))}")
    print(f"\nเขียนทับแล้วที่: {ORIGINAL}")
    print("ขั้นต่อไป: python run_lab8b_ait.py --skip-lab7")


if __name__ == "__main__":
    main()
