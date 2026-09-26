"""ชุดคำถามทอง v2 — 30 ข้อต่อแผน หลากหลายกว่า v1 ตรงเกณฑ์ ch8 (30 ข้อ, ข้อ "ไม่รู้" >= 2, ให้คะแนนจากผล SQL)

เฉลยคำนวณจาก ground_truth_scoped (แก้ให้ตรงเล่มแล้ว) + หน่วยกิตรวม/ปีที่ประกาศ (สองข้อแรกของไฟล์ v1) — ไม่อ่าน DB
สุ่มด้วย seed ตายตัว "gold-v2:<แผน>" รันซ้ำได้ไฟล์เดิมทุกไบต์ — ไฟล์ที่สร้างแล้วถูกล็อก (sha256 ใน meta) ห้ามแก้หลังเห็นผล

    python build_gold_questions_v2.py        # เขียน v2/<แผน>_gold_questions_v2.json + v2/<แผน>_meta.json
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_gold_questions import expected_prerequisite_pairs, is_placed, parse_credits  # noqa: E402

SCOPED_DIR = HERE.parent / "ground_truth_scoped"
OUT_DIR = HERE / "v2"
PLAN_NAMES = ["ait", "bit_coop", "bit_no_coop", "dsba_coop", "dsba_no_coop", "it_coop", "it_no_coop"]
CODE_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")


def norm_th(s: str | None) -> str:
    return re.sub(r"\s+", "", (s or "").replace("ํา", "ำ"))


def norm_en(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").upper()).strip()


def load_scoped(plan: str) -> list[dict]:
    return json.loads((SCOPED_DIR / f"{plan}_scoped.json").read_text(encoding="utf-8"))["courses"]


def placed_courses(rows: list[dict]) -> dict[str, dict]:
    """วิชาที่ระบุตัวชัด = รหัสตัวเลข 8 หลัก + ปี/ภาคแน่นอน (กติกาเดียวกับ v1) — รหัสซ้ำเก็บแถวแรก"""
    out: dict[str, dict] = {}
    for c in rows:
        if re.fullmatch(r"\d{8}", c.get("code") or "") and is_placed(c):
            out.setdefault(c["code"], c)
    return out


def hours(course: dict) -> tuple[int, int, int, int]:
    parsed = parse_credits(course.get("credits"))
    if parsed is None:
        raise ValueError(f"{course.get('code')}: หน่วยกิตอ่านไม่ได้ {course.get('credits')!r}")
    return parsed


def _term_of(c: dict) -> tuple[int, int] | None:
    try:
        return int(c.get("year")), int(c.get("semester"))
    except (TypeError, ValueError):
        return None


def eligible_terms(rows: list[dict], placed: dict[str, dict], allow_year1: bool = False) -> list[tuple[int, int]]:
    """เทอมที่ถามรายเทอมได้โดยไม่ต้องเดา: ทุกแถวเป็นรหัสจริงในแผน, ไม่มีกลุ่มเลือก (note), ไม่มีรหัสซ้ำ,
    หน่วยกิตรวม 9–22 (CHK7); ปี 1 ใช้เฉพาะเมื่อ allow_year1 (v1 ถามปี 1 ภาค 1 ไปแล้ว)"""
    by_term: dict[tuple[int, int], list[dict]] = {}
    for c in rows:
        t = _term_of(c)
        if t and t[0] >= 1 and t[1] >= 1:
            by_term.setdefault(t, []).append(c)
    ok = []
    for (y, s), cs in sorted(by_term.items()):
        if y == 1 and not allow_year1:
            continue
        codes = [c.get("code") for c in cs]
        if any(c.get("note") or c.get("flexible_year_semester") for c in cs):
            continue
        if any(code not in placed for code in codes) or len(codes) != len(set(codes)):
            continue
        if 9 <= sum(hours(placed[code])[0] for code in codes) <= 22:
            ok.append((y, s))
    return ok


def term_codes(rows: list[dict], y: int, s: int) -> list[str]:
    return sorted({c["code"] for c in rows if _term_of(c) == (y, s) and re.fullmatch(r"\d{8}", c.get("code") or "")})


def prereq_maps(placed: dict[str, dict]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(วิชา -> วิชาบังคับก่อน, วิชาบังคับก่อน -> วิชาที่ต้องใช้) — "A หรือ B" = สองรหัส, นับเฉพาะรหัสในแผน"""
    fwd: dict[str, set[str]] = {}
    rev: dict[str, set[str]] = {}
    for code, c in placed.items():
        for req in CODE_RE.findall(c.get("prerequisite") or ""):
            if req in placed and req != code:
                fwd.setdefault(code, set()).add(req)
                rev.setdefault(req, set()).add(code)
    return fwd, rev


def unique_names(placed: dict[str, dict], key: str) -> set[str]:
    """รหัสวิชาที่ชื่อ (key = name_th / name_en) ไม่ว่างและไม่ซ้ำวิชาอื่นในแผน — ถามด้วยชื่อแล้วได้คำตอบเดียว"""
    normf = norm_th if key == "name_th" else norm_en
    counts = Counter(normf(c.get(key)) for c in placed.values() if normf(c.get(key)))
    return {code for code, c in placed.items() if normf(c.get(key)) and counts[normf(c.get(key))] == 1}


def _v1(plan: str) -> list[dict]:
    return json.loads((HERE / f"{plan}_gold_questions.json").read_text(encoding="utf-8"))


def v1_codes(plan: str) -> set[str]:
    """รหัสวิชาที่ชุด v1 ถามถึงหรือเป็นคำตอบ — v2 เลี่ยงวิชาเหล่านี้เมื่อมีตัวเลือกอื่น"""
    out: set[str] = set()
    for q in _v1(plan):
        out |= set(CODE_RE.findall(q["question"])) | set(CODE_RE.findall(json.dumps(q["expect"])))
    return out


def v1_declared(plan: str) -> tuple[str, str]:
    """(หน่วยกิตรวม, จำนวนปี) ที่เล่มประกาศ — ค่าเดียวกับสองข้อแรกของ v1"""
    qs = _v1(plan)
    return str(qs[0]["expect"]["value"]), str(qs[1]["expect"]["value"])


def v1_keyword(plan: str) -> str | None:
    for q in _v1(plan):
        m = re.search(r"มีคำว่า '([^']+)'", q["question"])
        if m:
            return m.group(1)
    return None
