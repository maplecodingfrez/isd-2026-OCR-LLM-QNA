"""
สร้าง gold_questions.json ล่วงหน้าสำหรับ AIT / BIT / IT (ก่อนที่ Lab7B->Lab8B จะถูกรันจริง)
================================================================================

ทำไมต้องมีสคริปต์นี้
--------------------
`Lab9_evaluation` ต้องการวัดผล NL->SQL ให้ครบทุกเล่มหลักสูตร (ไม่ใช่แค่ DSBA-coop) แต่ตอนนี้ยังไม่ได้
รัน Lab7B/8B กับ AIT/BIT/IT จริง (ดู `lab9_progress.md`ข้อ "ยังไม่ได้ทำ") สคริปต์นี้เตรียม
`gold_questions.json` ของแต่ละเล่มไว้ล่วงหน้า โดยคำนวณคำตอบที่ถูกต้องจาก **ground truth ที่มีอยู่แล้ว**
(`data/ground_truth/*.json`) ไม่ใช่เดามือ — พอรัน pipeline จริงเสร็จเมื่อไร เอาไฟล์พวกนี้ไปวาง
เป็น `gold_questions.json` ในโฟลเดอร์ run แล้วรัน `cmd_eval` ของ Lab8B ได้เลย เหมือนที่ DSBA-coop ทำ

ที่มาของคำตอบแต่ละกลุ่มคำถาม
----------------------------
- คำถามระดับหลักสูตร (หน่วยกิตรวม/จำนวนปี) — ใส่ตรงจากตัวเลขที่อ่านได้จากหน้าสุดท้ายของตารางแผน
  ("รวมตลอดหลักสูตร") ยืนยันด้วยตาแล้วตอนหา page range ("รวมตลอดหลักสูตร120/126/129" ตามเล่ม)
- คำถามเจาะจงชั้นปีที่ 1 ภาคการศึกษาที่ 1 (จำนวนวิชา/หน่วยกิตรวม/ชุดรหัสวิชา) — คำนวณจาก
  ground truth กรองเฉพาะแถวที่ปี=1 และภาค=1 (ตรวจแล้วว่าไม่มีวิชาเลือกแบบ "หรือ" ปนในภาคนี้ทุกเล่ม
  จึงบวกหน่วยกิตตรงๆ ได้ไม่ต้องกัน alt_group ซ้ำ)
- คำถามค้นชื่อ/รหัสวิชา และหน่วยกิต/ชั่วโมงบรรยาย-ปฏิบัติการ — ดึงจาก ground truth โดยตรง
  (แยกฟิลด์ "credits" รูปแบบ "3(3-0-6)" เป็นหน่วยกิต/บรรยาย/ปฏิบัติ/ศึกษาด้วยตนเอง)
- คำถามสรุปภาพรวมตาราง course (จำนวนวิชาทั้งหมด, หน่วยกิตต่ำสุด, ชั่วโมงปฏิบัติการสูงสุด ฯลฯ) —
  นับจากวิชาที่ "ระบุได้ชัด" เท่านั้น คือ (1) รหัสเป็นตัวเลขล้วน 8 หลัก ไม่ใช่ code คลุมเครือแบบ 06026xxx
  (2) มีปี/ภาคเรียนระบุแน่นอน ไม่ใช่วิชาเลือกแบบยืดหยุ่น (flexible_year_semester) — กติกาเดียวกับที่
  Lab8B เดิมใช้ตอนแปลง DSBA-coop (มันข้าม wildcard/flexible ไปเหมือนกัน ดู curriculum.conversion.json)
  เพราะพวกนี้ไม่มีทางกลายเป็นแถวใน `course`/`plan_item` ที่ระบุแน่นอนได้
- คำถามวิชาบังคับก่อน (prerequisite) — จำนวนคู่ (วิชา, วิชาบังคับก่อน) ที่ตาราง prerequisite ควรมี คำนวณจากเฉลย scoped
  (`ground_truth_scoped/<แผน>_scoped.json` ที่แก้ให้ตรงเล่มแล้ว) ผ่าน `expected_prerequisite_pairs()`
  (เดิม (ก่อน 2026-09-21) ตอบ 0 เสมอ เพราะ Lab 8B ยังไม่สกัดวิชาบังคับก่อน — ตอนนี้ขั้น `load-prerequisites`
  สกัดจากข้อความ OCR ของภาคผนวกคำอธิบายรายวิชา วิชาที่หาช่องนี้ไม่เจอจะไม่มีแถว จึงอาจทำให้ตอบต่ำกว่าเฉลย)
- คำถามแบบ "none" (ค่าธรรมเนียม/ชื่ออาจารย์/รหัสวิชาที่ไม่มีจริง) — เหมือน DSBA-coop ทุกเล่ม
  ไม่ต้องใช้ข้อมูลอะไรเพิ่ม เป็นการเช็คว่าระบบยอมรับได้ว่า "ไม่รู้" แทนที่จะเดามั่ว

ข้อควรระวังก่อนใช้จริง
----------------------
ไฟล์พวกนี้เป็น "เฉลยที่คำนวณล่วงหน้า" จาก ground truth ที่มีอยู่ ไม่ใช่ผลจากการรัน pipeline จริง
เมื่อรัน Lab7B->Lab8B กับหน้าที่เลือกไว้จริงแล้ว **ควรสุ่มตรวจ 3-5 ข้อเทียบกับ curriculum.db ที่ได้
อีกรอบ** ก่อนใช้รายงานผลจริง เผื่อกรณี OCR อ่านตัวเลขผิดหรือ LLM ตัดวิชาบางตัวออกไปโดยไม่ตั้งใจ
(เช่นเดียวกับที่เจอใน DSBA-coop ตอน CHK1/CHK7 ไม่ผ่าน)

การใช้งาน
---------
    python build_gold_questions.py

อ่าน ground truth จาก ../../data/ground_truth/*.json (relative จากไฟล์นี้) เขียนผลลัพธ์ทับไฟล์ใน
โฟลเดอร์เดียวกัน: ait_gold_questions.json, bit_coop_gold_questions.json,
bit_no_coop_gold_questions.json, it_coop_gold_questions.json, it_no_coop_gold_questions.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
GT_DIR = HERE.parent.parent / "data" / "ground_truth"

CREDIT_RE = re.compile(r"^\s*(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*\)\s*$")


def parse_credits(s: str) -> tuple[int, int, int, int] | None:
    m = CREDIT_RE.match(s or "")
    if not m:
        return None
    credits, lec, lab, self_ = (int(x) for x in m.groups())
    return credits, lec, lab, self_


def is_concrete_code(code: str, valid_prefixes: set[str]) -> bool:
    """รหัสวิชาที่ระบุได้ชัด = ตัวเลขล้วน 8 หลัก ไม่ใช่ 06026xxx / xxxxxxxx
    และรหัส 4 ตัวแรกต้องอยู่ในกลุ่มที่หลักสูตรนี้ใช้จริง (สาขาตัวเอง + วิชาเรียนรวม + GE)

    เหตุผลที่ต้องกรองด้วย prefix: ground truth (GT_Template) มีแถวหลงเหลือข้ามหลักสูตรอยู่บ้าง
    เช่น AIT_academic_plan.json มีแถว 06016401 (รหัส 0601 = ของ IT ไม่ใช่ 0604 ของ AIT) ปนอยู่
    ทั้งที่หน้าแผนการเรียนจริงของ AIT (ตรวจด้วยตาแล้ว) ไม่มีวิชานี้ — DSBA_academic_plan_coop.json
    ก็มีแถวเดียวกันนี้หลงมาเหมือนกัน แต่ gold_questions.json ตัวจริงของ DSBA (ที่ใช้รันจริงแล้ว)
    ก็ไม่ได้นับรวมมันด้วยเช่นกัน ยืนยันว่าต้องกรองทิ้ง"""
    if not re.fullmatch(r"\d{8}", code or ""):
        return False
    return code[:4] in valid_prefixes


def is_placed(course: dict) -> bool:
    """มีปี/ภาคเรียนระบุแน่นอน ไม่ใช่วิชาเลือกแบบยืดหยุ่น (flexible_year_semester)"""
    if course.get("flexible_year_semester"):
        return False
    y, s = course.get("year"), course.get("semester")
    if y in (None, 0, "0") or s in (None, 0, "0"):
        return False
    try:
        int(y)
        int(s)
    except (TypeError, ValueError):
        return False
    return True


def load_courses(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["courses"]


def _gt_course(code: str, name_th: str, credits: str, year: int, semester: int) -> dict:
    return {"code": code, "name_th": name_th, "name_en": None, "credits": credits,
            "year": year, "semester": semester, "category": "หมวดวิชาเฉพาะ", "type": "บังคับ",
            "prerequisite": "ไม่มี", "flexible_year_semester": None, "note": None}


# วิชาสหกิจศึกษา (คู่ "ในประเทศ/ต่างประเทศ") หายไปจาก ground truth ทั้งคู่แบบไม่มีร่องรอยเลย
# (ไม่ใช่แค่ tag ปี/ภาคผิดแบบที่ BIT เจอตอนแรก — ค้นด้วยรหัสแล้วไม่มีแถวนี้ในไฟล์ GT เลย)
# ทั้งที่หน้าตารางแผนจริงมีวิชานี้ชัดเจน (ยืนยันด้วยตาแล้วตอนหา page range) ผลคือถ้าไม่เติมเอง
# ตัวเลขสรุปภาพรวม (จำนวนวิชารวม, ชั่วโมงปฏิบัติการสูงสุด, จำนวนวิชาที่มีคำว่า "เทคโนโลยี") จะผิด
# เพราะวิชาสหกิจมักมีชั่วโมงปฏิบัติการสูงผิดปกติ (0-45-0) และชื่อมักมีคำเฉพาะทางของหลักสูตรอยู่ด้วย
# ยืนยันตัวเลขที่เพิ่มตรงนี้จากการรัน AIT จริงแล้ว (ตาราง course ได้ 34 วิชา ตรงกับ 32 (placed จาก GT)
# + 2 (สหกิจคู่นี้) เป๊ะ, ชั่วโมงปฏิบัติการสูงสุดจริง = 45 ตรงกับ (0-45-0) เป๊ะ)
# ของ BIT ตรวจแล้วเช่นกัน (หน้า 035) ส่วน IT ยังไม่ได้รันจริงเพื่อยืนยัน — ต้องเช็คซ้ำตอนรัน IT จริง
MANUAL_GT_GAPS: dict[str, list[dict]] = {
    "ait": [
        _gt_course("06046443", "สหกิจศึกษาทางเทคโนโลยีปัญญาประดิษฐ์", "6(0-45-0)", 4, 2),
        _gt_course("06046444", "สหกิจศึกษาต่างประเทศทางเทคโนโลยีปัญญาประดิษฐ์", "6(0-45-0)", 4, 2),
    ],
    "bit_coop": [
        _gt_course("06036147", "สหกิจศึกษา", "6(0-35-0)", 4, 2),
        _gt_course("06036148", "สหกิจศึกษาต่างประเทศ", "6(0-35-0)", 4, 2),
    ],
    # bit_no_coop / it_coop / it_no_coop: ยังไม่ได้ตรวจว่า GT ขาดคู่สหกิจแบบเดียวกันหรือไม่
    # (ต้องรัน pipeline จริงก่อนถึงจะยืนยันได้แน่ชัดเหมือนที่ทำกับ AIT/BIT — ดู lab9_progress.md)
}


SCOPED_DIR = HERE.parent / "ground_truth_scoped"


def expected_prerequisite_pairs(scoped_courses: list[dict]) -> int:
    """จำนวนคู่ (วิชา, วิชาบังคับก่อน) ที่ควรอยู่ในตาราง prerequisite ตามเฉลย scoped (แก้ให้ตรงเล่มแล้ว)

    นับเฉพาะวิชาที่ระบุตัวชัด (รหัส 8 หลัก + ปี/ภาคแน่นอน) และวิชาบังคับก่อนที่ก็เป็นวิชาระบุตัวชัดในแผนเดียวกัน
    (ตรงกับที่ตาราง course ของ Lab 8B มี — รหัสที่ไม่อยู่ในแผนถูกทิ้งตอนโหลด); "A หรือ B" นับเป็นสองคู่
    เพราะตาราง prerequisite เก็บแยกรหัส; แถวซ้ำ (เช่น IT 06016418 สองแทร็ก) นับคู่เดียว"""
    placed = {c["code"] for c in scoped_courses if re.fullmatch(r"\d{8}", c["code"] or "") and is_placed(c)}
    pairs = set()
    for c in scoped_courses:
        if c["code"] not in placed:
            continue
        for req in re.findall(r"(?<!\d)\d{8}(?!\d)", c.get("prerequisite") or ""):
            if req in placed and req != c["code"]:
                pairs.add((c["code"], req))
    return len(pairs)


def patch_prerequisite_question(questions: list[dict], n_pairs: int) -> bool:
    """แก้ค่าคาดหวังของคำถาม 'มีคู่ prerequisite กี่คู่' ในไฟล์คำถามที่มีอยู่แล้ว (ใช้กับ dsba_coop ที่ไม่ได้สร้างจากสคริปต์นี้)"""
    for q in questions:
        if "prerequisite" in q["question"] and q["expect"].get("type") == "value":
            q["expect"]["value"] = str(n_pairs)
            return True
    return False


def build_questions(courses: list[dict], declared_total_credits: int, years: int,
                     valid_prefixes: set[str], prereq_pairs: int = 0) -> list[dict]:
    concrete = [c for c in courses if is_concrete_code(c["code"], valid_prefixes)]
    placed = [c for c in concrete if is_placed(c)]

    # dedup by code (แถวเดียวกันอาจถูกอ้างซ้ำ เช่น ปรากฏทั้งใน source_courses/plan)
    #
    # ใช้ "placed" ไม่ใช่ "concrete" ตรงนี้ — เจอบั๊กจริงตอนรัน AIT จริง: ตอนแรกเผลอ dedup
    # จาก concrete ทั้งหมด (รวมวิชาในหมวดเลือกที่ catalog มีแต่ไม่เคยถูกพิมพ์ในตารางแผน
    # ปีที่ N ภาคที่ M เลย เช่น "หัวข้อคัดสรรด้านปัญญาประดิษฐ์" ของ AIT) ได้ตัวเลข 48 วิชา
    # แต่หน้าที่เราป้อนเข้า Lab7B จริงคือหน้าตารางแผนล้วนๆ ไม่มีหน้า catalog เลย ตาราง
    # course ที่ extraction ผลิตได้จริงจึงมีแค่วิชาที่ "placed" (ปรากฏในตารางแผนจริง) เท่านั้น
    # — รันจริงได้ 34 วิชา ตรงกับ placed (32) มากกว่า concrete (48) มาก ยืนยันว่าต้องใช้ placed
    catalog: dict[str, dict] = {}
    for c in placed:
        catalog.setdefault(c["code"], c)

    y1s1 = [c for c in placed if int(c["year"]) == 1 and int(c["semester"]) == 1]
    y1s1_sorted = sorted(y1s1, key=lambda c: c["code"])
    y1s1_credit_sum = 0
    for c in y1s1:
        parsed = parse_credits(c["credits"])
        y1s1_credit_sum += parsed[0] if parsed else 0

    def credits_of(course: dict) -> int:
        parsed = parse_credits(course["credits"])
        return parsed[0] if parsed else 0

    def hours_of(course: dict) -> tuple[int, int, int]:
        parsed = parse_credits(course["credits"])
        return (parsed[1], parsed[2], parsed[3]) if parsed else (0, 0, 0)

    # เลือกวิชาตัวอย่างสำหรับคำถามเจาะจง — เอาวิชาที่ "placed" และมีชื่อไทยไม่ซ้ำกัน
    sample_lookup = []
    seen_names = set()
    for c in y1s1_sorted:
        if c["name_th"] not in seen_names:
            sample_lookup.append(c)
            seen_names.add(c["name_th"])
    # เติมอีก 2-3 ตัวจากปีหลังๆ เพื่อความหลากหลาย (ไม่เอาปี 1 ซ้ำ)
    later = [c for c in placed if int(c["year"]) > 1 and c["name_th"] not in seen_names]
    later_sorted = sorted(later, key=lambda c: (int(c["year"]), int(c["semester"]), c["code"]))
    for c in later_sorted:
        if len(sample_lookup) >= len(y1s1_sorted) + 3:
            break
        if c["name_th"] in seen_names:
            continue
        sample_lookup.append(c)
        seen_names.add(c["name_th"])

    code_name_pairs = sample_lookup[:6]
    name_code_pairs = sample_lookup[6:9] if len(sample_lookup) > 6 else sample_lookup[:3]

    # วิชาตัวอย่างช่วงหลังของหลักสูตร ใช้ถามปี/ภาค/หน่วยกิตเจาะจง
    late_course = later_sorted[len(later_sorted) // 2] if later_sorted else y1s1_sorted[0]

    # อีกสองวิชาไว้ถามชั่วโมงบรรยาย/ปฏิบัติการ (เลือกที่มีค่า lab_h > 0 กับ = 0 อย่างละตัวถ้ามี)
    lab_gt0 = next((c for c in placed if hours_of(c)[1] > 0), None)
    lab_eq0 = next((c for c in placed if hours_of(c)[1] == 0), None)

    all_catalog = list(catalog.values())
    credit_values = [credits_of(c) for c in all_catalog]
    lab_values = [hours_of(c)[1] for c in all_catalog]
    most_common_credit = max(set(credit_values), key=credit_values.count)
    n_most_common = credit_values.count(most_common_credit)
    n_lab_zero = sum(1 for v in lab_values if v == 0)
    max_lab = max(lab_values)
    min_credit = min(credit_values)

    # คำถาม Y1S1 ที่หน่วยกิตต่างจากส่วนใหญ่ (เอาไว้ถาม "รหัสวิชาใดมี X หน่วยกิต")
    y1s1_credits_list = [(c, credits_of(c)) for c in y1s1_sorted]
    credit_counts = {}
    for _, cr in y1s1_credits_list:
        credit_counts[cr] = credit_counts.get(cr, 0) + 1
    unique_credit_course = next(
        (c for c, cr in y1s1_credits_list if credit_counts[cr] == 1), None
    )
    n_gt2 = sum(1 for _, cr in y1s1_credits_list if cr > 2)

    # keyword ที่พบในชื่อวิชาอย่างน้อย 2 ตัว เอาไว้ถาม "มีกี่วิชาที่มีคำว่า ... ในชื่อ"
    keyword_candidates = ["เทคโนโลยี", "ข้อมูล", "คอมพิวเตอร์", "ธุรกิจ", "ระบบ"]
    keyword, keyword_count = None, 0
    for kw in keyword_candidates:
        cnt = sum(1 for c in all_catalog if kw in c["name_th"])
        if cnt >= 2:
            keyword, keyword_count = kw, cnt
            break

    q: list[dict] = []
    q.append({"question": "หลักสูตรนี้ประกาศจำนวนหน่วยกิตรวมตลอดหลักสูตรไว้กี่หน่วยกิต",
               "expect": {"type": "value", "value": str(declared_total_credits)}})
    q.append({"question": "หลักสูตรนี้ใช้ระยะเวลาศึกษากี่ปี",
               "expect": {"type": "value", "value": str(years)}})
    q.append({"question": "ในแผนการศึกษา ชั้นปีที่ 1 ภาคการศึกษาที่ 1 มีรายวิชาทั้งหมดกี่วิชา",
               "expect": {"type": "value", "value": str(len(y1s1))}})
    q.append({"question": "ชั้นปีที่ 1 ภาคการศึกษาที่ 1 เรียนรวมทั้งหมดกี่หน่วยกิต",
               "expect": {"type": "value", "value": str(y1s1_credit_sum)}})
    q.append({"question": "ในแผนการศึกษา ชั้นปีที่ 1 ภาคการศึกษาที่ 1 ประกอบด้วยรายวิชารหัสใดบ้าง",
               "expect": {"type": "set", "value": [c["code"] for c in y1s1_sorted]}})

    for c in code_name_pairs:
        q.append({"question": f"รหัสวิชา {c['code']} มีชื่อภาษาไทยว่าอะไร",
                   "expect": {"type": "value", "value": c["name_th"]}})
    for c in name_code_pairs:
        q.append({"question": f"วิชา '{c['name_th']}' มีรหัสวิชาอะไร",
                   "expect": {"type": "value", "value": c["code"]}})

    q.append({"question": f"รหัสวิชา {late_course['code']} อยู่ในแผนการศึกษาชั้นปีที่เท่าไร",
               "expect": {"type": "value", "value": str(int(late_course["year"]))}})
    q.append({"question": f"รหัสวิชา {late_course['code']} มีกี่หน่วยกิต",
               "expect": {"type": "value", "value": str(credits_of(late_course))}})

    q.append({"question": f"ในฐานข้อมูลนี้มีคำอธิบายรายวิชา (ตาราง course) ทั้งหมดกี่วิชา",
               "expect": {"type": "value", "value": str(len(all_catalog))}})
    q.append({"question": f"มีรายวิชากี่วิชาที่มีหน่วยกิตเท่ากับ {most_common_credit}",
               "expect": {"type": "value", "value": str(n_most_common)}})
    q.append({"question": "มีรายวิชากี่วิชาที่ไม่มีชั่วโมงปฏิบัติการ (ชั่วโมงปฏิบัติการเท่ากับ 0)",
               "expect": {"type": "value", "value": str(n_lab_zero)}})
    q.append({"question": "รายวิชาในหลักสูตรนี้มีชั่วโมงปฏิบัติการต่อสัปดาห์มากที่สุดกี่ชั่วโมง",
               "expect": {"type": "value", "value": str(max_lab)}})
    q.append({"question": "หน่วยกิตที่น้อยที่สุดของรายวิชาในหลักสูตรนี้คือกี่หน่วยกิต",
               "expect": {"type": "value", "value": str(min_credit)}})

    if lab_gt0 is not None:
        q.append({"question": f"รหัสวิชา {lab_gt0['code']} มีชั่วโมงปฏิบัติการต่อสัปดาห์กี่ชั่วโมง",
                   "expect": {"type": "value", "value": str(hours_of(lab_gt0)[1])}})
    if lab_eq0 is not None:
        q.append({"question": f"รหัสวิชา {lab_eq0['code']} มีชั่วโมงบรรยายต่อสัปดาห์กี่ชั่วโมง",
                   "expect": {"type": "value", "value": str(hours_of(lab_eq0)[0])}})

    if keyword:
        q.append({"question": f"มีรายวิชากี่วิชาที่มีคำว่า '{keyword}' อยู่ในชื่อภาษาไทย",
                   "expect": {"type": "value", "value": str(keyword_count)}})

    q.append({"question": "ในแผนการศึกษาชั้นปีที่ 1 ภาคการศึกษาที่ 1 มีกี่วิชาที่มีหน่วยกิตมากกว่า 2",
               "expect": {"type": "value", "value": str(n_gt2)}})
    if unique_credit_course is not None:
        cr = credits_of(unique_credit_course)
        q.append({"question": f"ในแผนการศึกษาชั้นปีที่ 1 ภาคการศึกษาที่ 1 รหัสวิชาใดมี {cr} หน่วยกิต",
                   "expect": {"type": "value", "value": unique_credit_course["code"]}})

    q.append({"question": "ในฐานข้อมูลนี้มีคู่ความสัมพันธ์วิชาบังคับก่อน (prerequisite) ทั้งหมดกี่คู่",
               "expect": {"type": "value", "value": str(prereq_pairs)}})

    q.append({"question": "ค่าธรรมเนียมการศึกษา (ค่าเทอม) ของหลักสูตรนี้ต่อภาคการศึกษาคือเท่าไร",
               "expect": {"type": "none", "value": None}})
    q.append({"question": f"รายวิชา {y1s1_sorted[0]['code']} มีอาจารย์ผู้สอนประจำวิชาชื่อว่าอะไร",
               "expect": {"type": "none", "value": None}})
    q.append({"question": "รหัสวิชา 99999999 เป็นรายวิชาอะไร และมีกี่หน่วยกิต",
               "expect": {"type": "none", "value": None}})

    return q


# valid_prefixes: รหัสสาขาตัวเอง + วิชาเรียนรวมของคณะ (0606) + หมวดศึกษาทั่วไป (9064/9664)
# อ้างอิงจากตาราง "ความหมายของรหัสประจำรายวิชา" ที่อ่านได้จากหน้าจริงของแต่ละเล่ม
PLANS = [
    ("ait", GT_DIR / "AIT_academic_plan.json", 120, 4, {"0604", "0606", "9064"}),
    ("bit_coop", GT_DIR / "BIT_academic_plan_coop.json", 126, 4, {"0603", "9664"}),
    ("bit_no_coop", GT_DIR / "BIT_academic_plan_no_coop.json", 126, 4, {"0603", "9664"}),
    ("it_coop", GT_DIR / "IT_academic_plan_coop.json", 129, 4, {"0601", "0606", "9064"}),
    ("it_no_coop", GT_DIR / "IT_academic_plan_no_coop.json", 129, 4, {"0601", "0606", "9064"}),
    ("dsba_no_coop", GT_DIR / "DSBA_academic_plan_no_coop.json", 132, 4, {"0602", "0606", "9064"}),
]


def main() -> None:
    for name, gt_path, total_credits, years, valid_prefixes in PLANS:
        courses = load_courses(gt_path) + MANUAL_GT_GAPS.get(name, [])
        scoped = load_courses(SCOPED_DIR / f"{name}_scoped.json")
        n_pairs = expected_prerequisite_pairs(scoped)
        questions = build_questions(courses, total_credits, years, valid_prefixes, n_pairs)
        out_path = HERE / f"{name}_gold_questions.json"
        out_path.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{name}: {len(questions)} questions -> {out_path.name} (prerequisite pairs = {n_pairs})")

    # dsba_coop: ไฟล์คำถามเตรียมไว้ก่อนสคริปต์นี้ (อยู่ที่ output ของรัน) — คัดลอกมาไว้ที่นี่แล้วแก้เฉพาะข้อ prerequisite
    out_path = HERE / "dsba_coop_gold_questions.json"
    if not out_path.exists():
        src = HERE.parents[1] / "Lab7B_Lab8B_ocr_system" / "runs" / "DSBA" / "coop" / "lab8b_output" / "gold_questions.json"
        out_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    qs = json.loads(out_path.read_text(encoding="utf-8"))
    n_pairs = expected_prerequisite_pairs(load_courses(SCOPED_DIR / "dsba_coop_scoped.json"))
    patch_prerequisite_question(qs, n_pairs)
    out_path.write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"dsba_coop: {len(qs)} questions -> {out_path.name} (prerequisite pairs = {n_pairs}; แก้เฉพาะข้อ prerequisite)")


if __name__ == "__main__":
    main()
