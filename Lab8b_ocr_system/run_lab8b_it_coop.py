"""Run the Lab 7B -> Lab 8B workflow on data/input_it_coop (หลักสูตร IT แผนสหกิจ —
เทคโนโลยีสารสนเทศ)

สำเนาจาก run_lab8b_it_no_coop.py ปรับให้:
- ใช้ data/input_it_coop (7 หน้า: it_curriculum_page_038..044.jpg จาก outputs/it/pages/ ของ
  Lab4-6 เดิม — คือตาราง "แผนการศึกษา" แผนสหกิจของ IT ปีที่ 1-4 — ยืนยัน page range ด้วยแล้ว
  ดู ISD/Learning Slides/Knowledge-based/lab9_progress.md)
- program-id "IT", total_credits 129, years 4
- ใช้ gold_questions.json ที่เตรียมไว้ล่วงหน้าแล้วที่ ../Lab9_evaluation/gold_questions/
  it_coop_gold_questions.json (คำนวณจาก ground truth คำนวณอัตโนมัติ ไม่ใช่เดามือ — ดู
  build_gold_questions.py) แทนที่จะรอ gold_questions_gt.json ที่ Lab7B สร้างเอง

วิธีรัน (จากโฟลเดอร์ Lab8b_ocr_system):
    python run_lab8b_it_coop.py               # เต็มรอบ: Lab7B OCR ใหม่ (เรียก Typhoon-OCR/qwen3 จริง) + Lab8B
    python run_lab8b_it_coop.py --skip-lab7   # ข้าม Lab7B ใช้ runs/IT/coop/lab7b_output/pred_vlm.json เดิม
                                               # รันแค่ Lab8B ต่อ (schema/import/load/verify/eval) — เร็วกว่ามาก
                                               # ใช้ตอนแก้แค่ gold_questions.json หรือ lab8b_curriculum_db.py
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
RUN_DIR = ROOT / "runs" / "IT" / "coop"
LAB7_OUT = RUN_DIR / "lab7b_output"
LAB8_OUT = RUN_DIR / "lab8b_output"
GOLD_SRC = ROOT.parent / "Lab9_evaluation" / "gold_questions" / "it_coop_gold_questions.json"
GT_SCOPED = ROOT.parent / "Lab9_evaluation" / "ground_truth_scoped" / "it_coop_scoped.json"


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
    # ให้ Lab 7B เติมฟิลด์ prerequisite (จากข้อความ OCR ทั้งเล่ม) ก่อนประเมินเทียบเฉลยในรอบเดียวกัน
    _book_txt = ROOT.parent / "outputs" / "it" / "it_curriculum_ocr.txt"
    if _book_txt.exists():
        os.environ["LAB7_BOOK_OCR"] = str(_book_txt)

    LAB7_OUT.mkdir(parents=True, exist_ok=True)
    LAB8_OUT.mkdir(parents=True, exist_ok=True)

    if not args.skip_lab7:
        run(LAB7, "-i", RUN_DIR / "data_input", "-p", "vlm", "-o", LAB7_OUT,
            *(["-g", GT_SCOPED] if GT_SCOPED.exists() else []))   # ไม่มีไฟล์เฉลย (เช่น branch ที่ไม่มี Lab9_evaluation/) -> ข้ามการเทียบเฉลย

    predictions = [LAB7_OUT / "pred_vlm.json", LAB7_OUT / "pred_markdown.json"]
    prediction = next((p for p in predictions if p.exists()), None)
    if prediction is None:
        raise SystemExit(f"ไม่พบ pred_vlm.json หรือ pred_markdown.json ใน {LAB7_OUT}")

    # ใบงาน Lab 7B §3.4: ฟิลด์ prerequisite ต้องอยู่ในผลของ Lab 7B — เติมจากข้อความ OCR ทั้งเล่มด้วยกฎเชิงกำหนด
    # (ไม่ใช้ LLM/เฉลย ไม่เดา: อ่านไม่เจอ = ไม่ใส่ฟิลด์) ทำซ้ำได้ผลเท่าเดิม เก็บสำเนาต้นฉบับ *.before_prereq.json ครั้งแรก
    book_ocr_txt = ROOT.parent / "outputs" / "it" / "it_curriculum_ocr.txt"
    if book_ocr_txt.exists():
        run(LAB7, "--fill-prerequisites", prediction, "--book-ocr", book_ocr_txt)

    run(LAB8, "schema", "-o", LAB8_OUT / "schema")
    run(LAB8, "import-lab7b", "-i", prediction,
        "-o", LAB8_OUT / "curriculum.json",
        "--markdown", LAB7_OUT / "intermediate_vlm.md",   # กู้ปี/เทอมวิชาที่ได้ 0/0 (ถ้ามีไฟล์)
        "--program-id", "IT",
        "--program-name", "เทคโนโลยีสารสนเทศ",
        "--total-credits", 129, "--years", 4)
    run(LAB8, "load", "-i", LAB8_OUT / "curriculum.json",
        "-d", LAB8_OUT / "curriculum.db", "--replace")
    # ช่องตามเล่ม (wildcard / "หรือ" / เลือก 1 กลุ่ม) สกัดจาก Markdown ของ OCR ด้วยกฎเชิงกำหนด
    # ไม่กรอกมือ และไม่แตะ plan_item/verify เดิม (ดู md_plan_slots.py)
    md_file = LAB7_OUT / "intermediate_vlm.md"
    if md_file.exists():
        run(LAB8, "load-plan-slots-md", "-m", md_file, "-d", LAB8_OUT / "curriculum.db")
    # วิชาบังคับก่อน: สกัดจากข้อความ OCR ทั้งเล่มของ Lab 4-6 (กฎเชิงกำหนด ไม่เดา — หาไม่เจอ = ไม่มีแถว)
    # ไม่มีไฟล์ OCR ทั้งเล่ม = ข้ามขั้นนี้ (ตาราง prerequisite ว่างเหมือนเดิม)
    book_ocr = ROOT.parent / "outputs" / "it" / "it_curriculum_ocr.txt"
    if book_ocr.exists():
        run(LAB8, "load-prerequisites", "-t", book_ocr, "-d", LAB8_OUT / "curriculum.db",
            "-o", LAB8_OUT / "prerequisites_report.json")
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
