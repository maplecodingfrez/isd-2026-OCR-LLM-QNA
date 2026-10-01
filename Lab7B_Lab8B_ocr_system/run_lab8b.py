"""Run the Lab 7B -> Lab 8B workflow for one curriculum plan, or all 7.

วิธีรัน (จากโฟลเดอร์ Lab7B_Lab8B_ocr_system, ใช้ python ของ ocr_system/.venv, ต้องเปิด Ollama ก่อนขั้น eval):
    python run_lab8b.py --plan it_coop --skip-lab7   # ใช้ผล Lab 7B เดิม (pred_vlm.json) รันแค่ขั้นซ่อม + Lab 8B + eval
    python run_lab8b.py --plan all --skip-lab7       # ครบ 7 แผน
    python run_lab8b.py --plan ait                   # เต็มรอบ: Lab 7B OCR ใหม่ (Typhoon-OCR + qwen3 จริง, ช้ามาก)

แต่ละแผนอ่านรูปหน้าแผนการศึกษาจาก runs/<แผน>/data_input/ และข้อความ OCR ทั้งเล่มจาก
../outputs/<หลักสูตร>/<หลักสูตร>_curriculum_ocr.txt (Lab 4–6) แล้วเขียนผลลง runs/<แผน>/lab7b_output และ lab8b_output
ขั้น eval ใช้ชุดคำถามทอง ../Lab9_evaluation/gold_questions/<แผน>_gold_questions.json (ล็อก sha256 ใน frozen.json)
ทุกขั้นหลัง OCR เป็นกฎเชิงกำหนด ไม่ใช้เฉลย ไม่แก้มือ — รันซ้ำได้ผลเดิม
(เดิมเป็นสคริปต์แยก run_lab8b_<แผน>.py 7 ไฟล์ที่ต่างกันแค่ค่าในตาราง PLANS)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LAB7 = ROOT / "src" / "ocr_system" / "lab7b_curriculum.py"
LAB8 = ROOT / "src" / "ocr_system" / "lab8b_curriculum_db.py"
GOLD_DIR = ROOT.parent / "Lab9_evaluation" / "gold_questions"
SCOPED_DIR = ROOT.parent / "Lab9_evaluation" / "ground_truth_scoped"
OUTPUTS = ROOT.parent / "outputs"

# แผน: (โฟลเดอร์ใน runs/, เล่ม (outputs/<เล่ม>/), program-id, ชื่อหลักสูตร, หน่วยกิตรวมที่เล่มประกาศ) — ทุกแผน 4 ปี
PLANS = {
    "ait": ("AIT", "ait", "AIT", "เทคโนโลยีปัญญาประดิษฐ์", 120),
    "bit_no_coop": ("BIT/no_coop", "bit", "BIT", "เทคโนโลยีสารสนเทศทางธุรกิจ (หลักสูตรนานาชาติ)", 126),
    "bit_coop": ("BIT/coop", "bit", "BIT", "เทคโนโลยีสารสนเทศทางธุรกิจ (หลักสูตรนานาชาติ)", 126),
    "dsba_no_coop": ("DSBA/no_coop", "dsba", "DSBA-no-coop", "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ", 132),
    "dsba_coop": ("DSBA/coop", "dsba", "DSBA-coop", "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (สหกิจศึกษา)", 132),
    "it_no_coop": ("IT/no_coop", "it", "IT", "เทคโนโลยีสารสนเทศ", 129),
    "it_coop": ("IT/coop", "it", "IT", "เทคโนโลยีสารสนเทศ", 129),
}


# ค่าตั้ง OCR เฉพาะแผน (มีผลเฉพาะตอน OCR ใหม่ ไม่ใส่ --skip-lab7): IT coop ของที่ commit ไว้รันด้วยการตัดตราน้ำ
# (กู้รหัส 06016419/06016420 ที่ตราน้ำบัง — ดู LAB7B_LAB8B_OVERVIEW.md) ต้องเปิดไว้จึงจะได้ผลแบบเดิม
PLAN_ENV = {"it_coop": {"LAB7B_DEWATERMARK": "1"}}


def run(*args: object) -> None:
    subprocess.run([sys.executable, *(str(x) for x in args)], cwd=ROOT, check=True)


def run_plan(plan: str, skip_lab7: bool) -> None:
    rel, book, program_id, program_name, total_credits = PLANS[plan]
    run_dir = ROOT / "runs" / rel
    lab7_out, lab8_out = run_dir / "lab7b_output", run_dir / "lab8b_output"
    book_txt = OUTPUTS / book / f"{book}_curriculum_ocr.txt"
    gt_scoped = SCOPED_DIR / f"{plan}_scoped.json"
    md_file = lab7_out / "intermediate_vlm.md"
    db = lab8_out / "curriculum.db"
    print(f"\n===== {plan} ({rel}) =====")

    os.environ.pop("LAB7B_DEWATERMARK", None)
    os.environ.update(PLAN_ENV.get(plan, {}))
    # ให้ Lab 7B เติมฟิลด์ prerequisite (จากข้อความ OCR ทั้งเล่ม) ก่อนประเมินเทียบเฉลยในรอบเดียวกัน
    if book_txt.exists():
        os.environ["LAB7_BOOK_OCR"] = str(book_txt)
    lab7_out.mkdir(parents=True, exist_ok=True)
    lab8_out.mkdir(parents=True, exist_ok=True)

    if not skip_lab7:
        run(LAB7, "-i", run_dir / "data_input", "-p", "vlm", "-o", lab7_out,
            *(["-g", gt_scoped] if gt_scoped.exists() else []))   # ไม่มีไฟล์เฉลย -> ข้ามการเทียบเฉลย

    prediction = next((p for p in (lab7_out / "pred_vlm.json", lab7_out / "pred_markdown.json") if p.exists()), None)
    if prediction is None:
        raise SystemExit(f"ไม่พบ pred_vlm.json หรือ pred_markdown.json ใน {lab7_out}")

    # วิชารหัสจริงที่ Markdown ของ OCR มีครบแต่ LLM ทิ้งไป -> เติมด้วยกฎเชิงกำหนด (md_plan_slots.fill_missing_rows)
    # ทำก่อนเติม prerequisite เพื่อให้วิชาที่เติมได้ฟิลด์ prerequisite ด้วย; รันซ้ำได้ไม่เติมซ้ำ
    run(LAB7, "--fill-missing-rows", prediction)
    if book_txt.exists():
        # รหัสที่ OCR ทำหาย / ชื่ออังกฤษที่ว่าง / ชื่อไทยสะกดเพี้ยน (ฉันทามติ 7 แผน + เล่ม) — code_from_book.py, name_consensus.py
        run(LAB7, "--recover-codes", prediction, "--book-ocr", book_txt)
        # ใบงาน Lab 7B §3.4: ฟิลด์ prerequisite ต้องอยู่ในผลของ Lab 7B — จากข้อความ OCR ทั้งเล่ม (ไม่เดา: อ่านไม่เจอ = ไม่ใส่)
        run(LAB7, "--fill-prerequisites", prediction, "--book-ocr", book_txt)

    run(LAB8, "schema", "-o", lab8_out / "schema")
    run(LAB8, "import-lab7b", "-i", prediction, "-o", lab8_out / "curriculum.json",
        "--markdown", md_file,        # กู้ปี/เทอมวิชาที่ได้ 0/0 + ชื่อคู่ "A หรือ B" (ถ้ามีไฟล์)
        "--program-id", program_id, "--program-name", program_name,
        "--total-credits", total_credits, "--years", 4)
    run(LAB8, "load", "-i", lab8_out / "curriculum.json", "-d", db, "--replace")
    # ช่องตามเล่ม (wildcard / "หรือ" / เลือก 1 กลุ่ม) สกัดจาก Markdown ของ OCR ด้วยกฎเชิงกำหนด (md_plan_slots.py)
    if md_file.exists():
        run(LAB8, "load-plan-slots-md", "-m", md_file, "-d", db)
    # วิชาบังคับก่อน: สกัดจากข้อความ OCR ทั้งเล่มของ Lab 4–6 (หาไม่เจอ = ไม่มีแถว)
    if book_txt.exists():
        run(LAB8, "load-prerequisites", "-t", book_txt, "-d", db, "-o", lab8_out / "prerequisites_report.json")
    # แคตตาล็อกวิชาเลือกของหลักสูตร (Lab 7B: runs/<หลักสูตร>/electives.json ใช้ร่วมกันทั้ง coop/no_coop) — ไม่มีไฟล์ = ข้าม
    electives = ROOT / "runs" / rel.split("/")[0] / "electives.json"
    if electives.exists():
        run(LAB8, "load-electives", "-d", db, "-i", electives, "--program-id", program_id)
    # แคตตาล็อกหมวดวิชาศึกษาทั่วไป ฉบับ 2566 (python -m ocr_system.extract_elective_catalog --pdf data/input/GE66_Th_Ed240501.pdf
    # --edition 2566) — plan_slot คนละชื่อกับวิชาเลือกของหลักสูตร จึงไม่ลบกัน; BIT เป็นหลักสูตรนานาชาติ ใช้หมวดศึกษาทั่วไปของตัวเอง ไม่โหลดให้
    ge_catalog = ROOT / "runs" / "ge66_catalog.json"
    if ge_catalog.exists() and not rel.startswith("BIT"):
        run(LAB8, "load-electives", "-d", db, "-i", ge_catalog, "--program-id", program_id)
    # โครงสร้างหน่วยกิตต่อหมวด (ก./ข./ค. → กลุ่มย่อย) จากหัวข้อ 3.1.3 ของข้อความ OCR ทั้งเล่ม — ผลรวมหมวดระดับบนไม่ตรงหน่วยกิตรวม = ไม่โหลด
    if book_txt.exists():
        run(LAB8, "load-credit-structure", "-t", book_txt, "-d", db)
    # หน้าในเล่มสำหรับอ้างอิงคำตอบ (citations.py) — ไม่มีไฟล์ที่ต้องใช้ = คำสั่งพิมพ์บอกว่าข้าม
    run(LAB8, "load-course-pages", "-d", db, "--ocr-json", book_txt.with_suffix(".json"),
        "--data-input", run_dir / "data_input", "-m", md_file)
    run(LAB8, "verify", "-d", db, "-o", lab8_out / "verify.json")

    run(LAB8, "eval", "-d", db, "-q", GOLD_DIR / f"{plan}_gold_questions.json", "-o", lab8_out / "eval_result.json")
    print(f"เสร็จแล้ว: {lab8_out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", required=True, choices=[*PLANS, "all"])
    parser.add_argument("--skip-lab7", action="store_true", help="ใช้ pred_vlm.json เดิม ไม่ OCR ใหม่")
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
    plans = list(PLANS) if args.plan == "all" else [args.plan]
    # ชุดคำถามทองต้องตรง sha256 ที่ล็อกไว้ (ตรวจก่อนเริ่ม ไม่ให้สร้าง DB เสร็จแล้วค่อยพัง) — กันรายงานผลจากไฟล์ที่ถูกแก้
    # หลังเห็นผลว่าเป็นชุดทางการ
    sys.path.insert(0, str(GOLD_DIR))
    from build_gold_questions import frozen_ok
    bad = [p for p in plans if not frozen_ok(p)]
    if bad:
        raise SystemExit(f"ชุดคำถามทองของ {', '.join(bad)} ไม่ตรง sha256 ใน gold_questions/frozen.json — "
                         "ห้ามแก้ชุดคำถามหลังล็อก (ดู build_gold_questions.py)")
    for plan in plans:
        run_plan(plan, args.skip_lab7)


if __name__ == "__main__":
    main()
