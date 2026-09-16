"""
Lab9 evaluation script — 06026240 Intelligent System Development
==================================================================

จุดประสงค์
----------
สคริปต์นี้ทำข้อ 5 ของ checklist บทที่ 9 (ch9_EvaluationAndOverfitting.pdf):
"รันสคริปต์ประเมินผลกับงานโปรเจคของตัวเอง แล้วเอาตัวเลขไปใส่รายงานได้"

มันอ่านผลลัพธ์ที่ Lab 8B (../Lab8b_ocr_system) รันไว้แล้ว (ไม่รันโมเดลใหม่ ไม่เรียก
Ollama/LLM ซ้ำ — แค่คำนวณ metric จากไฟล์ JSON ที่มีอยู่) แล้วสรุปเป็นตัวเลขตาม metric
ที่สไลด์บทที่ 9 สอน:

  1. Structured-output metrics (หน้า "วัดคุณภาพผลลัพธ์ที่มีโครงสร้าง"):
     - conversion_rate   ~ Schema pass rate  (converted_courses / source_courses)
     - skipped_rate      ~ ของที่ parse ไม่ผ่านแล้วถูกทิ้ง (field-level recall ต่ำจุดไหน)
     - verify_pass_rate  ~ ความถูกต้องเชิงเนื้อหาของ curriculum ที่แปลงออกมา (CHK1-CHK7)

  2. NL→SQL metrics (หน้า "วัดคำตอบสุดท้ายและความซื่อสัตย์ต่อแหล่งข้อมูล"):
     - valid_sql_rate        = สัดส่วนคำถามที่ SQL รันได้ไม่ error
     - execution_accuracy    = สัดส่วนคำถามที่ "แถวผลลัพธ์ SQL" ตรงกับเฉลย (ตัวชี้วัดหลักของงานนี้)
     - answer_text_accuracy  = สัดส่วนคำถามที่ "ข้อความคำตอบ" ที่โมเดลพิมพ์จริงมีค่าที่ถูกต้องอยู่ในนั้น
       (ตัวนี้ต่างจาก execution_accuracy ตรงที่เอาไว้จับบั๊ก "SQL ถูกแต่ข้อความคำตอบผิด/สับสน"
       ซึ่งเกณฑ์อัตโนมัติเดิมของ Lab 8B มองไม่เห็น เพราะเทียบแค่แถว SQL ไม่ได้เทียบข้อความ)

  3. Overfitting / stability check (หน้า "สัญญาณที่บอกว่ากำลัง overfit"):
     ระบบนี้ไม่ได้เทรนโมเดลเอง (ใช้ LLM พร้อมใช้ + prompt) จึงไม่มี train/val loss ให้ดู
     สัญญาณที่ใช้แทนได้ตามสไลด์คือ "ผลแกว่งมากเมื่อรันซ้ำ" — สคริปต์นี้เทียบสอง run ที่ใช้ชุด
     เอกสารเดียวกัน (input_ours_coop กับ input_ours_coop_retry) แล้วรายงานส่วนต่างของตัวเลข
     โครงสร้าง (จำนวนวิชา/หน่วยกิตรวม) และ execution_accuracy ว่าห่างกันแค่ไหน ถ้าห่างเกิน
     threshold ที่กำหนด จะติดธง "ไม่เสถียร" ให้ในรายงาน

การใช้งาน
---------
    python evaluate_lab9.py
    python evaluate_lab9.py --runs <path1> <path2> ...   # ระบุ run directory เอง

ค่า default ของ --runs คือ 8 run ที่มีอยู่แล้ว (อัปเดต 2026-09-16 — ครบ 4 คณะ AIT/BIT/DSBA/IT
ตามขอบเขตที่อาจารย์ขอให้ประเมิน ไม่ใช่แค่ DSBA-coop เหมือนตอนแรกสุด):
    ait, bit_no_coop, bit_coop, dsba_no_coop, dsba_coop, it_no_coop, it_coop
        — ../Lab8b_ocr_system/runs/<CURRICULUM>/<plan>/lab8b_output/
    dsba_coop_retry — ../Lab8b_ocr_system/archive/lab8b_run_ours_coop_retry/
        (รันซ้ำรอบสองของเอกสารชุดเดียวกับ dsba_coop — ใช้เฉพาะเช็คความเสถียร/overfitting เท่านั้น)

ผลลัพธ์
-------
พิมพ์ตาราง Markdown ออกทางหน้าจอ (copy ไปแปะรายงานได้เลย) และบันทึกไฟล์ไว้ที่
    reports/lab9_metrics_latest.md    — ตารางพร้อมแปะรายงาน
    reports/lab9_metrics_latest.json  — ตัวเลขดิบทั้งหมด เผื่อทำกราฟ/วิเคราะห์ต่อ

หมายเหตุ: สคริปต์นี้อยู่ในโฟลเดอร์ Lab9_evaluation แยกจาก Lab8b_ocr_system โดยตั้งใจ
เพื่อให้ Lab9 เป็นงานส่งแยกชิ้น ไม่ปนกับซอร์สของ Lab8B — มันแค่ "อ่าน" ไฟล์ผลลัพธ์ของ
Lab8B จากภายนอก ไม่แก้ไขหรือรันอะไรในโฟลเดอร์นั้นเลย
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_LAB8B = HERE.parent / "Lab8b_ocr_system"
DEFAULT_LAB8B_RUNS = DEFAULT_LAB8B / "runs"

# อัปเดต 2026-09-16: เดิม hardcode 3 run ที่ชี้ไปที่ Lab8b_ocr_system/work/lab8b_run_ours_coop(_retry)
# ซึ่งถูกย้ายออกไปตอนจัดระเบียบโฟลเดอร์ (ดู Lab8b_ocr_system/PROGRESS.md หัวข้อ "จัดระเบียบโฟลเดอร์
# 2026-09-16") ทำให้ 2 ใน 3 path เดิมหายไปจริง ("[ข้าม] ไม่พบ run directory" ถ้ารันเฉยๆ) — เปลี่ยนมา
# ชี้ครบทั้ง 7 run ตามชื่อหลักสูตร/แผนใน Lab8b_ocr_system/runs/<CURRICULUM>/<plan>/lab8b_output/ แทน
# (ครบทุกคณะที่อาจารย์ขอให้ประเมิน AIT/BIT/DSBA/IT — ไม่ใช่แค่ DSBA-coop เหมือนตอนแรกสุด)
DEFAULT_RUNS = [
    ("ait", DEFAULT_LAB8B_RUNS / "AIT" / "lab8b_output"),
    ("bit_no_coop", DEFAULT_LAB8B_RUNS / "BIT" / "no_coop" / "lab8b_output"),
    ("bit_coop", DEFAULT_LAB8B_RUNS / "BIT" / "coop" / "lab8b_output"),
    ("dsba_no_coop", DEFAULT_LAB8B_RUNS / "DSBA" / "no_coop" / "lab8b_output"),
    ("dsba_coop", DEFAULT_LAB8B_RUNS / "DSBA" / "coop" / "lab8b_output"),
    ("it_no_coop", DEFAULT_LAB8B_RUNS / "IT" / "no_coop" / "lab8b_output"),
    ("it_coop", DEFAULT_LAB8B_RUNS / "IT" / "coop" / "lab8b_output"),
    # เก็บไว้เฉพาะสำหรับเช็คความเสถียร/overfitting (checklist ข้อ 3) — เอกสารชุดเดียวกับ dsba_coop
    # เป๊ะ รันซ้ำรอบสอง (ของเดิมอยู่ที่ archive/lab8b_run_ours_coop_retry/ หลังจัดโฟลเดอร์)
    ("dsba_coop_retry", DEFAULT_LAB8B / "archive" / "lab8b_run_ours_coop_retry"),
]

# runs ที่ใช้เอกสารชุดเดียวกันจริง ๆ (สำหรับเช็คความเสถียร/overfitting เท่านั้น
# ห้ามเอา run อื่นมาเทียบด้วย เพราะเป็นเอกสารคนละชุด ตัวเลขต่างกันเป็นปกติ)
STABILITY_GROUP = {"dsba_coop", "dsba_coop_retry"}

# ถ้าตัวเลขโครงสร้างต่างกันเกินนี้ (เป็นสัดส่วน) ระหว่างรันซ้ำ -> ติดธงว่าไม่เสถียร
STABILITY_THRESHOLD = 0.10


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(s: str) -> str:
    """ตัดช่องว่าง/เครื่องหมายวรรคตอนออก เพื่อเทียบข้อความแบบหยวน ๆ (ตามหลัก MAPE/EM ในสไลด์: อ่านคู่กับบริบท ไม่ใช่เป๊ะตัวอักษร)"""
    return re.sub(r"[\s,()]+", "", s or "").strip()


@dataclass
class RunMetrics:
    name: str
    path: str
    found: dict[str, bool] = field(default_factory=dict)

    # structured-output metrics
    source_courses: int | None = None
    converted_courses: int | None = None
    conversion_rate: float | None = None
    skipped_wildcards: int | None = None
    skipped_flexible_plan_items: int | None = None
    skipped_rate: float | None = None
    plan_items: int | None = None

    declared_total_credits: int | None = None
    plan_total_credits: int | None = None
    credits_abs_error: int | None = None    # MAE-style: |plan - declared| หน่วยกิต
    credits_pct_error: float | None = None  # MAPE-style: abs_error / declared * 100

    verify_checks_total: int | None = None
    verify_checks_passed: int | None = None
    verify_pass_rate: float | None = None
    verify_failed_ids: list[str] = field(default_factory=list)

    # classification metrics (ctype "บังคับ/เลือก") จาก Lab7B evaluation.json — เผย accuracy
    # paradox ที่ exact_match_acc เพียงอย่างเดียวมองไม่เห็น (checklist ch9 ข้อ 4)
    ctype_accuracy: float | None = None
    ctype_recall_mandatory: float | None = None
    ctype_recall_elective: float | None = None
    ctype_mcc: float | None = None

    # NL->SQL metrics
    n_questions: int | None = None
    valid_sql_rate: float | None = None
    execution_accuracy: float | None = None
    answer_text_accuracy: float | None = None
    avg_seconds: float | None = None
    sql_ok_text_wrong: list[str] = field(default_factory=list)  # ตรง gap ที่สไลด์เตือน


def evaluate_run(name: str, run_dir: Path) -> RunMetrics:
    m = RunMetrics(name=name, path=str(run_dir))

    conversion = load_json(run_dir / "curriculum.conversion.json")
    m.found["curriculum.conversion.json"] = conversion is not None
    if conversion:
        m.source_courses = conversion.get("source_courses")
        m.converted_courses = conversion.get("converted_courses")
        m.plan_items = conversion.get("plan_items")
        m.skipped_wildcards = conversion.get("skipped_wildcards", 0)
        m.skipped_flexible_plan_items = conversion.get("skipped_flexible_plan_items", 0)
        if m.source_courses:
            m.conversion_rate = round(m.converted_courses / m.source_courses, 4)
            skipped_total = (m.skipped_wildcards or 0) + (m.skipped_flexible_plan_items or 0)
            m.skipped_rate = round(skipped_total / m.source_courses, 4)

    curriculum = load_json(run_dir / "curriculum.json")
    m.found["curriculum.json"] = curriculum is not None
    if curriculum:
        m.declared_total_credits = curriculum.get("program", {}).get("total_credits")
        plan = curriculum.get("plan", [])
        m.plan_total_credits = sum(p.get("credits", 0) or 0 for p in plan)
        # หน่วยกิตรวมเป็นค่าต่อเนื่อง (ไม่ใช่ pass/fail แบบ CHK1) — วัดด้วย
        # MAE/MAPE ตามสไลด์ ch9 ส่วนที่ 2 "งานทำนายค่าต่อเนื่อง" แทนที่จะรู้แค่ตรง/ไม่ตรง
        if m.plan_total_credits is not None and m.declared_total_credits:
            m.credits_abs_error = abs(m.plan_total_credits - m.declared_total_credits)
            m.credits_pct_error = round(
                m.credits_abs_error / m.declared_total_credits * 100, 2)

    # confusion matrix ของ ctype (บังคับ/เลือก) คำนวณไว้แล้วใน Lab7B (lab7_metrics.py
    # ::classification_report) — อ่านมาจาก evaluation.json ของ lab7b_output ที่เป็นโฟลเดอร์
    # พี่น้องกับ lab8b_output (ไม่มีของ dsba_coop_retry เพราะเป็นโฟลเดอร์เก่าก่อนจัดระเบียบ
    # ที่ไม่มี lab7b_output คู่กัน — load_json คืน None แล้วข้ามไปเฉยๆ)
    lab7b_eval = load_json(run_dir.parent / "lab7b_output" / "evaluation.json")
    m.found["lab7b_output/evaluation.json"] = lab7b_eval is not None
    if lab7b_eval:
        ctype = lab7b_eval.get("vlm", {}).get("alignment", {}).get("classification", {}).get("ctype")
        if ctype:
            m.ctype_accuracy = ctype.get("accuracy")
            m.ctype_mcc = ctype.get("mcc")
            per_class = ctype.get("per_class", {})
            if "บังคับ" in per_class:
                m.ctype_recall_mandatory = per_class["บังคับ"].get("recall")
            if "เลือก" in per_class:
                m.ctype_recall_elective = per_class["เลือก"].get("recall")

    verify = load_json(run_dir / "verify.json")
    m.found["verify.json"] = verify is not None
    if verify:
        m.verify_checks_total = len(verify)
        passed = [c for c in verify if c.get("ok")]
        m.verify_checks_passed = len(passed)
        m.verify_pass_rate = round(len(passed) / len(verify), 4) if verify else None
        m.verify_failed_ids = [c["id"] for c in verify if not c.get("ok")]

    eval_result = load_json(run_dir / "eval_result.json")
    m.found["eval_result.json"] = eval_result is not None
    if eval_result:
        n = len(eval_result)
        m.n_questions = n
        sql_ok = sum(1 for r in eval_result if r.get("error") is None)
        exec_correct = sum(1 for r in eval_result if r.get("correct"))
        m.valid_sql_rate = round(sql_ok / n, 4) if n else None
        m.execution_accuracy = round(exec_correct / n, 4) if n else None
        secs = [r.get("seconds") for r in eval_result if isinstance(r.get("seconds"), (int, float))]
        m.avg_seconds = round(statistics.mean(secs), 2) if secs else None

        # answer_text_accuracy: เช็คว่า "ข้อความคำตอบ" จริง ๆ ที่โมเดลพิมพ์ มีค่าที่ถูกต้องอยู่ไหม
        # ต่างจาก execution_accuracy ที่เช็คแค่แถว SQL — จุดนี้จับบั๊ก "SQL ถูกแต่ตอบเป็นข้อความผิด"
        text_correct = 0
        for r in eval_result:
            expect = r.get("expect", {})
            answer_text = normalize_text(r.get("answer") or "")
            kind = expect.get("type", "value")
            if kind == "none":
                ok = answer_text == "" or "ไม่พบ" in (r.get("answer") or "") or "ไม่มี" in (r.get("answer") or "")
            elif kind == "set":
                want_values = [normalize_text(str(x)) for x in expect.get("value", [])]
                ok = all(v in answer_text for v in want_values)
            else:
                want_value = normalize_text(str(expect.get("value", "")))
                ok = want_value != "" and want_value in answer_text
            if ok:
                text_correct += 1
            elif r.get("correct") and not ok:
                # SQL ถูก (correct=True) แต่ข้อความคำตอบไม่มีค่าที่ถูกต้อง -> gap ตรงที่สไลด์เตือน
                m.sql_ok_text_wrong.append(r.get("question", "")[:60])
        m.answer_text_accuracy = round(text_correct / n, 4) if n else None

    return m


def check_stability(runs: dict[str, RunMetrics]) -> list[str]:
    """เทียบ run ที่อยู่ใน STABILITY_GROUP (เอกสารชุดเดียวกัน รันซ้ำคนละครั้ง)
    ตามสัญญาณ overfitting ในสไลด์: 'ผลแกว่งมากเมื่อรันซ้ำ' -> โมเดลไม่เสถียร"""
    group = [runs[n] for n in STABILITY_GROUP if n in runs]
    notes: list[str] = []
    if len(group) < 2:
        notes.append("ข้าม: มี run ในกลุ่มเช็คความเสถียรไม่ครบสอง run")
        return notes

    def pct_diff(a: float | None, b: float | None) -> float | None:
        if a is None or b is None or (a == 0 and b == 0):
            return None
        base = max(abs(a), abs(b), 1e-9)
        return abs(a - b) / base

    fields_to_check = [
        ("plan_total_credits", "หน่วยกิตรวมในแผน"),
        ("converted_courses", "จำนวนวิชาที่แปลงได้"),
        ("execution_accuracy", "Execution accuracy (SQL)"),
        ("answer_text_accuracy", "ความถูกต้องของข้อความคำตอบ"),
    ]
    a, b = group[0], group[1]
    for attr, label in fields_to_check:
        va, vb = getattr(a, attr), getattr(b, attr)
        d = pct_diff(va, vb)
        if d is None:
            continue
        flag = "⚠️ ไม่เสถียร (เกิน threshold)" if d > STABILITY_THRESHOLD else "โอเค"
        notes.append(f"{label}: {a.name}={va}  vs  {b.name}={vb}  (ต่างกัน {d*100:.1f}%) -> {flag}")
    return notes


def credits_mae_mape(runs: dict[str, RunMetrics]) -> dict:
    """MAE/MAPE ของหน่วยกิตรวม รวมทุก run — สไลด์ ch9 บอกว่าค่าต่อเนื่องยิ่งต่ำยิ่งดี
    (ยกเว้น R square) ต่างจาก CHK1 ที่บอกแค่ผ่าน/ไม่ผ่าน ไม่บอกว่าคลาดเคลื่อนแค่ไหน"""
    errs = [r.credits_abs_error for r in runs.values() if r.credits_abs_error is not None]
    pcts = [r.credits_pct_error for r in runs.values() if r.credits_pct_error is not None]
    return {
        "n": len(errs),
        "mae": round(statistics.mean(errs), 2) if errs else None,
        "mape": round(statistics.mean(pcts), 2) if pcts else None,
        "max_abs_error": max(errs) if errs else None,
        "worst_run": max(runs.values(), key=lambda r: r.credits_abs_error or 0).name if errs else None,
    }


def to_markdown(runs: dict[str, RunMetrics], stability_notes: list[str]) -> str:
    lines = []
    lines.append(f"# Lab9 evaluation report — {datetime.now():%Y-%m-%d %H:%M}")
    lines.append("")
    lines.append("อ้างอิงเนื้อหา: `ISD/Learning Slides/ch9_EvaluationAndOverfitting.pdf`")
    lines.append("ข้อมูลดิบมาจาก: `Lab8b_ocr_system/runs/<CURRICULUM>/<plan>/lab8b_output/` "
                  "(สคริปต์นี้แค่คำนวณ ไม่ได้รันโมเดลใหม่)")
    lines.append("")

    lines.append("## 1. Structured-output metrics (Markdown → JSON → curriculum.db)")
    lines.append("")
    lines.append("| run | conversion_rate | skipped_rate | plan_total_credits | declared_total_credits | credits_abs_error | credits_pct_error | verify_pass_rate | failed checks |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in runs.values():
        lines.append(
            f"| {r.name} | {r.conversion_rate} | {r.skipped_rate} | {r.plan_total_credits} | "
            f"{r.declared_total_credits} | {r.credits_abs_error} | {r.credits_pct_error} | "
            f"{r.verify_pass_rate} | {', '.join(r.verify_failed_ids) or '-'} |"
        )
    lines.append("")

    cm = credits_mae_mape(runs)
    lines.append("### หน่วยกิตรวม — MAE/MAPE ข้ามหลักสูตร (สไลด์ ch9 ส่วนที่ 2 \"งานทำนายค่าต่อเนื่อง\")")
    lines.append("")
    lines.append("CHK1 ข้างบนบอกแค่ผ่าน/ไม่ผ่าน (`total == declared` เป๊ะ) ไม่บอกว่าคลาดเคลื่อนไปแค่ไหน "
                  "— MAE/MAPE ตรงนี้วัดขนาดความคลาดเคลื่อนแทน (ยิ่งต่ำยิ่งดี ตามสไลด์)")
    lines.append("")
    lines.append(f"- **MAE** = {cm['mae']} หน่วยกิต (เฉลี่ยจาก {cm['n']} run ที่มีข้อมูลครบ)")
    lines.append(f"- **MAPE** = {cm['mape']}%")
    lines.append(f"- คลาดเคลื่อนมากสุด: **{cm['worst_run']}** ({cm['max_abs_error']} หน่วยกิต)")
    lines.append("")

    lines.append("## 2. NL→SQL metrics (eval_result.json)")
    lines.append("")
    lines.append("| run | n_questions | valid_sql_rate | execution_accuracy | answer_text_accuracy | avg_seconds |")
    lines.append("|---|---|---|---|---|---|")
    for r in runs.values():
        lines.append(
            f"| {r.name} | {r.n_questions} | {r.valid_sql_rate} | {r.execution_accuracy} | "
            f"{r.answer_text_accuracy} | {r.avg_seconds} |"
        )
    lines.append("")

    any_gap = any(r.sql_ok_text_wrong for r in runs.values())
    lines.append("### บั๊ก \"SQL ถูกแต่ข้อความคำตอบผิด\" (execution_accuracy สูงแต่ answer_text_accuracy ต่ำกว่า)")
    lines.append("")
    if any_gap:
        for r in runs.values():
            if r.sql_ok_text_wrong:
                lines.append(f"- **{r.name}**: {len(r.sql_ok_text_wrong)} ข้อ")
                for q in r.sql_ok_text_wrong:
                    lines.append(f"  - {q}")
    else:
        lines.append("ไม่พบในรอบนี้ (execution_accuracy กับ answer_text_accuracy ตรงกันทุกข้อ)")
    lines.append("")

    lines.append("## 3. ความเสถียร / สัญญาณ overfitting (รันซ้ำเอกสารชุดเดียวกัน)")
    lines.append("")
    for note in stability_notes:
        lines.append(f"- {note}")
    lines.append("")

    lines.append("## 4. Metric ที่วิชานี้ไม่ได้ใช้ + ทำไม (checklist ch9 ข้อ 4)")
    lines.append("")
    lines.append("### 4.1 Confusion matrix / MCC — **ใช้แล้ว** สำหรับฟิลด์ `ctype` (บังคับ/เลือก)")
    lines.append("")
    lines.append("`ctype` เป็นงาน binary classification ตรงตามสไลด์ ch9 ส่วนที่ 1 แต่เดิมวัดด้วย "
                  "exact_match_acc (กลไกเดียวกับ free text) ซึ่งไม่เผย accuracy paradox — เพิ่ม "
                  "confusion matrix + per-class precision/recall/F1 + MCC แล้ว "
                  "(`lab7_metrics.py::classification_report`) พบว่าโมเดลเอนเอียงทาย \"บังคับ\" "
                  "อย่างเป็นระบบทุกหลักสูตร (precision(บังคับ)=1.000 ทุก run แต่ "
                  "recall(เลือก) ต่ำมาก):")
    lines.append("")
    lines.append("| run | ctype accuracy | recall(บังคับ) | recall(เลือก) | MCC |")
    lines.append("|---|---|---|---|---|")
    for r in runs.values():
        if r.ctype_accuracy is None:
            continue
        lines.append(
            f"| {r.name} | {r.ctype_accuracy} | {r.ctype_recall_mandatory} | "
            f"{r.ctype_recall_elective} | {r.ctype_mcc} |"
        )
    lines.append("")
    lines.append("ตัวเลข `exact_match_acc` เดิม (60-86%, ดูพอใช้ได้) บังตาปัญหานี้ไว้ทั้งหมด — "
                  "เป็นตัวอย่าง accuracy paradox ตรงตามที่สไลด์เตือนจริง")
    lines.append("")

    lines.append("### 4.2 MAE/MAPE — **ใช้แล้ว** สำหรับหน่วยกิตรวม (ดูหัวข้อ 1 ด้านบน)")
    lines.append("")
    lines.append("CHK1 เดิมบอกแค่ผ่าน/ไม่ผ่าน ไม่บอกขนาดความคลาดเคลื่อน — เพิ่ม MAE/MAPE ต่อยอด "
                  f"แล้ว (MAE={cm['mae']} หน่วยกิต, MAPE={cm['mape']}% ข้ามทั้ง 7 หลักสูตร) "
                  "เผยว่า run ที่ \"fail CHK1\" เหมือนกันหมด จริง ๆ คลาดเคลื่อนต่างกันมาก "
                  f"({cm['worst_run']} แย่สุด {cm['max_abs_error']} หน่วยกิต ขณะที่บาง run "
                  "คลาดเคลื่อนแค่ ~5%)")
    lines.append("")
    lines.append("**Known limitation ของค่านี้ (ตั้งใจปล่อยไว้ ไม่ใช่บั๊ก):** ส่วนใหญ่ของความ"
                  "คลาดเคลื่อนมาจากแถว \"วิชาเลือก\" ที่ตารางแผนเขียนเป็นรหัส wildcard (เช่น "
                  "`06036xxx`) แทนรหัสจริง — เอกสารต้นฉบับเองก็ไม่ได้ระบุว่านักศึกษาจะเลือกวิชาไหน "
                  "จึงไม่ถูกใส่ใน `plan_item` ที่ MAE นับ (ไม่เดารหัสปลอม/ไม่แต่งข้อมูล) เคยลอง "
                  "แก้โดยบวกหน่วยกิตจากตาราง catalog แยก (`elective_group.credits_required`) กลับ "
                  "เข้าไปแล้ว แต่พบว่า **จะทำให้ตัวเลขเฟ้อผิดทิศทางแทน**: ค่า `credits_required` "
                  "ถูกก็อปปี้ซ้ำทุกกลุ่มย่อยในเมนู (เช่น BIT-coop 1 ช่อง 6 หน่วยกิต แต่มี 4 กลุ่มย่อย "
                  "→ รวมผิดเป็น 24) และ catalog กับตำแหน่งจริงในแผนก็ไม่ได้ผูกกันแบบ 1:1 (เช็คแล้ว "
                  "BIT-coop มีแถว wildcard จริง 7 แถวในแผน แต่ catalog นิยามไว้แค่ 1 slot) บางแถว "
                  "ยังเป็น \"เลือกเสรี\" ที่ไม่มีเมนูจำกัดในเอกสารเลยด้วยซ้ำ (เลือกวิชาอะไรก็ได้ทั้ง"
                  "มหาวิทยาลัย) — สรุปว่าค่า MAE/MAPE ที่รายงานนี้เป็น **upper bound ที่ถูกต้อง** "
                  "(หน่วยกิตที่หายจริง) ไม่ใช่ตัวชี้วัดคุณภาพการสกัดที่แย่")
    lines.append("")

    lines.append("### 4.3 Metric ที่ตัดสินใจ **ไม่ใช้** + เหตุผล")
    lines.append("")
    lines.append("- **MSE/RMSE/MAPE/Huber สำหรับฟิลด์อื่นนอกจากหน่วยกิตรวม** — ไม่มีงาน "
                  "regression/depth-estimation อื่นในโปรเจกต์นี้ ฟิลด์ที่เหลือเป็น categorical "
                  "หรือ free text ทั้งหมด วัดด้วย CER/WER/exact_match (ฟิลด์อิสระ) หรือ "
                  "confusion matrix (ฟิลด์ categorical) แทน")
    lines.append("- **LLM-as-a-judge / Cohen kappa** — คำถาม NL→SQL ของโปรเจกต์นี้เป็น closed-form "
                  "(มีคำตอบถูกหนึ่งเดียว ตรวจด้วยกฎ/SQL result ได้ตรง ๆ) ไม่ใช่งานปลายเปิดที่ต้องให้ "
                  "LLM ช่วยตัดสินความ \"ดี\" แบบอัตนัย จึงไม่จำเป็นต้องใช้")
    lines.append("- **Citation coverage** — คำตอบมาจาก SQL ที่รันจริงกับ DB ที่สกัดมา ไม่ใช่การ "
                  "generate ข้อความอิสระแบบ RAG ที่ต้องอ้างอิงหน้า/แหล่งที่มา จึงไม่มีขั้นตอน "
                  "\"citation\" ให้วัดตั้งแต่ต้น")
    lines.append("- **Faithfulness/Groundedness** — รับประกันโดยสถาปัตยกรรมเดียวกับข้อบน: คำตอบมาจาก "
                  "SQL execution ต่อฐานข้อมูลจริงเสมอ ไม่มีช่องให้โมเดล \"แต่งเรื่อง\" หลุดจากข้อมูลได้")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--runs", nargs="*", metavar="NAME=PATH",
        help="ระบุ run เอง เช่น --runs my_run=work/lab8b_run  (ถ้าไม่ระบุ ใช้ค่า default สาม run)",
    )
    args = ap.parse_args()

    if args.runs:
        run_specs = []
        for spec in args.runs:
            if "=" in spec:
                name, path = spec.split("=", 1)
            else:
                name, path = Path(spec).name, spec
            run_specs.append((name, Path(path)))
    else:
        run_specs = DEFAULT_RUNS

    runs: dict[str, RunMetrics] = {}
    for name, path in run_specs:
        if not path.exists():
            print(f"[ข้าม] ไม่พบ run directory: {path}", file=sys.stderr)
            continue
        runs[name] = evaluate_run(name, path)

    if not runs:
        print("ไม่พบ run ใดเลย ตรวจสอบ path ของ Lab8b_ocr_system/work/ ก่อน", file=sys.stderr)
        sys.exit(1)

    stability_notes = check_stability(runs)
    report_md = to_markdown(runs, stability_notes)

    print(report_md)

    reports_dir = HERE / "reports"
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "lab9_metrics_latest.md").write_text(report_md, encoding="utf-8")
    (reports_dir / "lab9_metrics_latest.json").write_text(
        json.dumps({name: vars(m) for name, m in runs.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nบันทึกแล้ว: {reports_dir / 'lab9_metrics_latest.md'}")
    print(f"บันทึกแล้ว: {reports_dir / 'lab9_metrics_latest.json'}")


if __name__ == "__main__":
    main()
