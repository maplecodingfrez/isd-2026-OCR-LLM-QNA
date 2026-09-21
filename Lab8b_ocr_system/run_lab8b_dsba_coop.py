"""Run the Lab 7B -> Lab 8B workflow on runs/DSBA/coop/data_input (coop, full 8-semester plan).

สำเนาจาก run_lab8b.py ต้นฉบับ ปรับให้:
- ใช้ runs/DSBA/coop/data_input แทน data/input_C (ครบ 8 ภาคการศึกษาของแผนสหกิจศึกษา แทนที่จะเป็น
  4 หน้าตามขอบเขตที่แจกจริง ซึ่งมีแค่หน้าเดียวของฝั่งสหกิจ คือ DSBA_28.png)
- เขียน output ลง runs/DSBA/coop/lab7b_output, runs/DSBA/coop/lab8b_output (คนละโฟลเดอร์ ไม่ทับ
  work/lab8b_run เดิมที่เป็นงานส่งอาจารย์ตามขอบเขต data/input_C — ไฟล์นั้นยังอยู่ที่เดิม ไม่ได้ย้าย
  เพราะเป็นงานส่งจริงคนละขอบเขต ดู PROGRESS.md หัวข้อจัดระเบียบโฟลเดอร์ 2026-09-16)
- program-id/name เดิมมี "(สหกิจศึกษา)" อยู่แล้วถูกต้องพอดีสำหรับชุดนี้ (ตรงกับที่ Claude Code ตั้ง
  ไว้ใน run_lab8b.py ต้นฉบับตั้งแต่แรก)
- (อัปเดต 2026-09-15) ตอนนี้ส่ง -g/--gt ด้วยแล้ว — เดิมไม่ส่งเพราะ GT ชุดเต็ม
  (data/ground_truth/DSBA_academic_plan_coop.json, 91 วิชา) ไม่ได้ตัดมาเฉพาะหน้าที่ scan จริง
  P/R จะต่ำเทียม แก้โดยสร้าง `Lab9_evaluation/ground_truth_scoped/dsba_coop_scoped.json`
  (กรอง year>=1 ตัดแถว catalog-only/year=0 ทิ้ง) ให้ใช้แทน — ทดสอบ pilot กับ BIT-coop แล้วได้ตัวเลข
  สมเหตุสมผล (P=0.814 R=0.833 F1=0.824) ไม่ต่ำผิดปกติเหมือนที่กลัวไว้ตอนแรก

วิธีรัน (จากโฟลเดอร์ Lab8b_ocr_system):
    python run_lab8b_dsba_coop.py               # เต็มรอบ: Lab7B OCR ใหม่ (เรียก Typhoon-OCR/qwen3 จริง) + Lab8B
    python run_lab8b_dsba_coop.py --skip-lab7   # ข้าม Lab7B ใช้ runs/DSBA/coop/lab7b_output/pred_vlm.json เดิม
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
RUN_DIR = ROOT / "runs" / "DSBA" / "coop"
LAB7_OUT = RUN_DIR / "lab7b_output"
LAB8_OUT = RUN_DIR / "lab8b_output"
# เดิมไม่ส่ง -g เพราะ GT ชุดเต็ม (92 วิชา) ไม่ได้ตัดมาเฉพาะหน้า 3.1.4 ที่ scan จริง P/R จะต่ำเทียม —
# ตอนนี้มี ground_truth_scoped (กรอง year>=1 ตัด catalog-only ทิ้ง) ให้ใช้ได้ความหมายจริงแล้ว
GT_SCOPED = ROOT.parent / "Lab9_evaluation" / "ground_truth_scoped" / "dsba_coop_scoped.json"


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
        run(LAB7, "-i", RUN_DIR / "data_input",
            "-p", "vlm", "-o", LAB7_OUT, *(["-g", GT_SCOPED] if GT_SCOPED.exists() else []))   # ไม่มีไฟล์เฉลย (เช่น branch ที่ไม่มี Lab9_evaluation/) -> ข้ามการเทียบเฉลย

    predictions = [LAB7_OUT / "pred_vlm.json", LAB7_OUT / "pred_markdown.json"]
    prediction = next((p for p in predictions if p.exists()), None)
    if prediction is None:
        raise SystemExit(f"ไม่พบ pred_vlm.json หรือ pred_markdown.json ใน {LAB7_OUT}")

    run(LAB8, "schema", "-o", LAB8_OUT / "schema")
    run(LAB8, "import-lab7b", "-i", prediction,
        "-o", LAB8_OUT / "curriculum.json",
        "--markdown", LAB7_OUT / "intermediate_vlm.md",   # กู้ปี/เทอมวิชาที่ได้ 0/0 (ถ้ามีไฟล์)
        "--program-id", "DSBA-coop",
        "--program-name", "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (สหกิจศึกษา)",
        # เล่มหลักสูตรระบุ "รวมตลอดหลักสูตร 132 หน่วยกิต" ทั้งฝั่งสหกิจและไม่สหกิจ — ยอดรวมเท่ากัน
        # ต่างกันแค่การจัดหน่วยกิตในปี 4 (ฝั่งสหกิจ ภาค 2 มีแค่ 6 หน่วยกิต: วิชาสหกิจศึกษา)
        "--total-credits", 132, "--years", 4)
    run(LAB8, "load", "-i", LAB8_OUT / "curriculum.json",
        "-d", LAB8_OUT / "curriculum.db", "--replace")
    # ช่องตามเล่ม (wildcard / "หรือ" / เลือก 1 กลุ่ม) สกัดจาก Markdown ของ OCR ด้วยกฎเชิงกำหนด
    # ไม่กรอกมือ และไม่แตะ plan_item/verify เดิม (ดู md_plan_slots.py)
    md_file = LAB7_OUT / "intermediate_vlm.md"
    if md_file.exists():
        run(LAB8, "load-plan-slots-md", "-m", md_file, "-d", LAB8_OUT / "curriculum.db")
    run(LAB8, "verify", "-d", LAB8_OUT / "curriculum.db",
        "-o", LAB8_OUT / "verify.json")

    gold = LAB8_OUT / "gold_questions.json"
    sample = LAB7_OUT / "gold_questions_gt.json"
    if not gold.exists() and sample.exists():
        shutil.copyfile(sample, gold)
    if not gold.exists() or len(json.loads(gold.read_text(encoding="utf-8"))) < 30:
        print(f"\nเพิ่มคำถามใน {gold} ให้ครบ 30 ข้อ แล้วรัน:")
        print("python run_lab8b_dsba_coop.py --skip-lab7")
        return

    run(LAB8, "eval", "-d", LAB8_OUT / "curriculum.db",
        "-q", gold, "-o", LAB8_OUT / "eval_result.json")
    print(f"\nเสร็จแล้ว: {LAB8_OUT}")


if __name__ == "__main__":
    main()
