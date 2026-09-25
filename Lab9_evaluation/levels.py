"""ระดับคำถาม (ch1: 1 ง่าย = ค้นฟิลด์ตรง ๆ, 2 กลาง = อ่านตาราง/รวม/กรองหลายจุด) และหน้าที่คาดว่าต้องอ้างอิง

ติดป้ายด้วยกฎจากรูปแบบคำถาม (ตกลงกับผู้ใช้ 2026-09-26) — หน้าที่คาดใช้ผลจับคู่หน้าของ Lab 5
(`outputs/<prog>/<run>_course_page_mapping.csv`, สร้างจากเฉลย — ใช้เฉพาะการประเมิน)"""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

CODE_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")
TERM_RE = re.compile(r"ชั้นปีที่\s*(\d)\s*ภาคการศึกษาที่\s*(\d)")
QUOTED_RE = re.compile(r"'([^']+)'")
LEVEL2_RE = re.compile(r"ชั้นปีที่\s*\d\s*ภาคการศึกษาที่\s*\d|ภาคเรียนที่|มีรายวิชากี่วิชา|ที่สุด|ทั้งหมดกี่|กี่คู่")


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").replace("ํา", "ำ"))


def question_level(question: str, expect_type: str) -> str:
    if expect_type == "none":
        return "none"
    if LEVEL2_RE.search(question):
        return "2"
    return "1"


def _pages(row: dict) -> set[int]:
    """หน้าที่คาดว่าควรอ้าง = หน้า primary (มีรหัสและชื่อวิชา) — หน้า other แค่เอ่ยรหัส (เช่นเป็นวิชาบังคับก่อน
    ของวิชาอื่น) ใช้เฉพาะเมื่อไม่มี primary เลย; รวมทั้งสองแบบจะทำให้อัตราอ้างถูกสูงเกินจริง"""
    def split(field: str) -> set[int]:
        return {int(p) for p in (row.get(field) or "").split(";") if p}
    return split("primary_pages") or split("other_pages")


def expected_pages(question: str, expect_value, mapping: list[dict]) -> set[int] | None:
    codes = CODE_RE.findall(question) + CODE_RE.findall(str(expect_value))
    if codes:
        pages = set().union(*(_pages(r) for r in mapping if r["code"] in codes))
        return pages or None
    quoted = QUOTED_RE.search(question)
    if quoted:
        pages = set().union(*(_pages(r) for r in mapping if _norm(r["name_th"]) == _norm(quoted.group(1))))
        return pages or None
    term = TERM_RE.search(question)
    if term:
        y, s = term.groups()
        counts = Counter(p for r in mapping if r["year"] == y and r["semester"] == s for p in _pages(r))
        if not counts:
            return None
        top = max(counts.values())
        return {p for p, n in counts.items() if n == top}
    return None


def load_mapping(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def level_stats(eval_rows: list[dict], mapping: list[dict]) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for r in eval_rows:
        expect = r.get("expect") or {}
        lvl = question_level(r["question"], expect.get("type", "value"))
        s = stats.setdefault(lvl, {"n": 0, "correct": 0, "with_citation": 0, "cite_checkable": 0, "cite_hit": 0})
        s["n"] += 1
        s["correct"] += bool(r.get("correct"))
        cited = {c["pdf_page"] for c in r.get("citations") or []}
        s["with_citation"] += bool(cited)
        # ระดับ none = เล่มไม่มีคำตอบ ไม่อ้างหน้าคือถูก — ไม่นับในอัตราอ้างอิง
        want = expected_pages(r["question"], expect.get("value"), mapping) if lvl != "none" else None
        if want:
            s["cite_checkable"] += 1
            s["cite_hit"] += bool(cited & want)
    return stats
