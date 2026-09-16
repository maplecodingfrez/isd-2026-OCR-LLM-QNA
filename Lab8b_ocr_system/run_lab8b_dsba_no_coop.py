"""Run the Lab 7B -> Lab 8B workflow on data/input_dsba_no_coop (หลักสูตร DSBA แผนไม่สหกิจ —
วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ)

สำเนาจาก run_lab8b_it_no_coop.py ปรับให้:
- ใช้ data/input_dsba_no_coop (7 หน้า: dsba_curriculum_page_023..029.jpg จาก outputs/dsba/pages/
  ของ Lab4-6 เดิม — คือตาราง "แผนการศึกษา" แผนไม่สหกิจของ DSBA ปีที่ 1-4 — ยืนยัน page range
  ด้วยแล้ว ดู ISD/Learning Slides/Knowledge-based/lab9_progress.md
  (หมายเหตุ: มีโฟลเดอร์เก่า data/input_ours ค้างอยู่จากงานคนละรอบ page range ไม่ตรงกับที่ยืนยันไว้
  — ไม่ได้ใช้ ใช้ data/input_dsba_no_coop ที่ crop ใหม่ตาม page range ที่ถูกต้องแทน)
- program-id "DSBA-no-coop" (ตั้งชื่อคู่กับ "DSBA-coop" ที่ใช้อยู่แล้วใน runs/DSBA/coop/lab8b_output),
  total_credits 132, years 4 (อ่านจากหน้า "3.1.1 จำนวนหน่วยกิตรวมตลอดหลักสูตร 132 หน่วยกิต" ตรงๆ
  — ค่าเดียวกับแผนสหกิจ เพราะเป็นข้อกำหนดรวมของหลักสูตร ไม่ใช่แยกตามแผน)
- ใช้ gold_questions.json ที่เพิ่งสร้างใหม่ที่ ../Lab9_evaluation/gold_questions/
  dsba_no_coop_gold_questions.json (เพิ่ม entry "dsba_no_coop" ใน PLANS ของ
  build_gold_questions.py แล้วรันสร้างใหม่ — คำนวณจาก ground truth
  data/ground_truth/DSBA_academic_plan_no_coop.json อัตโนมัติ ไม่ใช่เดามือ)

วิธีรัน (จากโฟลเดอร์ Lab8b_ocr_system):
    python run_lab8b_dsba_no_coop.py               # เต็มรอบ: Lab7B OCR ใหม่ (เรียก Typhoon-OCR/qwen3 จริง) + Lab8B
    python run_lab8b_dsba_no_coop.py --skip-lab7   # ข้าม Lab7B ใช้ runs/DSBA/no_coop/lab7b_output/pred_vlm.json เดิม
                                                    # รันแค่ Lab8B ต่อ (schema/import/load/verify/eval) — เร็วกว่ามาก
                                                    # ใช้ตอนแก้แค่ gold_questions.json หรือ lab8b_curriculum_db.py
                                                    # (ต้องใช้ venv ที่มี pydantic เช่น ../.venv/Scripts/python.exe
                                                    # ไม่ใช่ system python — ดู PROGRESS.md 2026-09-16 ที่เคยพลาดจุดนี้)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LAB7 = ROOT / "src" / "ocr_system" / "lab7b_curriculum.py"
LAB8 = ROOT / "src" / "ocr_system" / "lab8b_curriculum_db.py"
RUN_DIR = ROOT / "runs" / "DSBA" / "no_coop"
LAB7_OUT = RUN_DIR / "lab7b_output"
LAB8_OUT = RUN_DIR / "lab8b_output"
GOLD_SRC = ROOT.parent / "Lab9_evaluation" / "gold_questions" / "dsba_no_coop_gold_questions.json"
GT_SCOPED = ROOT.parent / "Lab9_evaluation" / "ground_truth_scoped" / "dsba_no_coop_scoped.json"


def run(*args: object) -> None:
    subprocess.run([sys.executable, *(str(x) for x in args)], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-lab7", action="store_true")
    args = parser.parse_args()

    os.environ.update({
        "PYTHONUTF8": "1",
        "LAB7_CHUNK": "1",
        "LAB7B_NUM_CTX": "8192",
        "LAB7B_NUM_PREDICT": "8192",
        "LAB7B_REQUEST_TIMEOUT": "7200",
        "LAB7B_OCR_NUM_CTX": "4096",
        "LAB7B_OCR_NUM_PREDICT": "1200",
    })
    LAB7_OUT.mkdir(parents=True, exist_ok=True)
    LAB8_OUT.mkdir(parents=True, exist_ok=True)

    if not args.skip_lab7:
        run(LAB7, "-i", RUN_DIR / "data_input", "-p", "vlm", "-o", LAB7_OUT,
            "-g", GT_SCOPED)

    predictions = [LAB7_OUT / "pred_vlm.json", LAB7_OUT / "pred_markdown.json"]
    prediction = next((p for p in predictions if p.exists()), None)
    if prediction is None:
        raise SystemExit(f"ไม่พบ pred_vlm.json หรือ pred_markdown.json ใน {LAB7_OUT}")

    run(LAB8, "schema", "-o", LAB8_OUT / "schema")
    run(LAB8, "import-lab7b", "-i", prediction,
        "-o", LAB8_OUT / "curriculum.json",
        "--program-id", "DSBA-no-coop",
        "--program-name", "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ",
        "--total-credits", 132, "--years", 4)
    run(LAB8, "load", "-i", LAB8_OUT / "curriculum.json",
        "-d", LAB8_OUT / "curriculum.db", "--replace")
    run(LAB8, "verify", "-d", LAB8_OUT / "curriculum.db",
        "-o", LAB8_OUT / "verify.json")

    gold = LAB8_OUT / "gold_questions.json"
    if not gold.exists():
        if not GOLD_SRC.exists():
            raise SystemExit(f"ไม่พบ {GOLD_SRC} — รัน build_gold_questions.py ก่อน")
        shutil.copyfile(GOLD_SRC, gold)

    run(LAB8, "eval", "-d", LAB8_OUT / "curriculum.db",
        "-q", gold, "-o", LAB8_OUT / "eval_result.json")
    print(f"\nเสร็จแล้ว: {LAB8_OUT}")


if __name__ == "__main__":
    main()
