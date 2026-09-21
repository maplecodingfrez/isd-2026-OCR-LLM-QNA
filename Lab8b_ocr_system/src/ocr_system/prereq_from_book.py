"""สกัด "วิชาบังคับก่อน" (prerequisite) ของแต่ละวิชาจากข้อความ OCR ของหน้า "คำอธิบายรายวิชา" (ภาคผนวก)

ทำไมต้องมี: หน้าแผนการศึกษา (ที่ Lab 7B ทำ OCR) ไม่มีคอลัมน์วิชาบังคับก่อน ข้อมูลอยู่ที่หน้าคำอธิบายรายวิชา
รูปแบบในเล่ม (ทุกหลักสูตรเหมือนกัน):

    06036114  การพัฒนาเว็บแอปพลิเคชันโดยใช้เฟรมเวิร์ก                 3(2-2-5)
              WEB APPLICATION DEVELOPMENT USING FRAMEWORKS
              วิชาบังคับก่อน :  06036119 พื้นฐานการเขียนโปรแกรม หรือ
                                06036122 การสื่อสารด้วยภาพสำหรับธุรกิจ
              PREREQUISITE :    06036119 PROGRAMMING FUNDAMENTALS
                                OR 06036122 VISUAL COMMUNICATION ...

กฎเชิงกำหนดล้วน (ไม่เรียก LLM, ไม่ใช้เฉลย) — อ่านข้อความ OCR ที่มีอยู่แล้ว (`outputs/<หลักสูตร>/*_curriculum_ocr.txt`
จาก Lab 4–6) ไม่ต้อง OCR ใหม่

หลักการสำคัญ: **ไม่เดา** — วิชาที่หาบรรทัด "วิชาบังคับก่อน" ของตัวเองไม่เจอในข้อความ OCR ได้สถานะ `not_found`
(ไม่ใช่ "ไม่มี") ผู้เรียกต้องไม่ตีความว่าไม่มีวิชาบังคับก่อน
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

CODE8 = re.compile(r"(?<![0-9])(\d{8})(?![0-9])")
_HDR = re.compile(r"^\s*(\d{8})\b")
_CRED = re.compile(r"\d\s*\(\s*\d\s*-\s*\d\s*-\s*\d+\s*\)")
_PRE_TH = re.compile(r"บังคับก่อน\s*[):;]?\s*(.*)$")
_PRE_EN = re.compile(r"PRE[\s-]?REQ\w*\s*[):;]?\s*(.*)$", re.I)
_NONE_TH = re.compile(r"ไม่มี")
_NONE_EN = re.compile(r"\bNONE\b", re.I)
_JOIN_TAIL_TH = re.compile(r"(หรือ|และ|,|/)\s*$")
_JOIN_TAIL_EN = re.compile(r"\b(OR|AND)\s*$", re.I)
_WINDOW = 10          # จำนวนบรรทัดหลังหัวรายวิชาที่ยอมค้นหา "วิชาบังคับก่อน"


def _codes(text: str) -> list[str]:
    return CODE8.findall(text)


def _read_block(lines: list[str], start: int, first_tail: str, join_tail: re.Pattern[str]) -> str:
    """อ่านค่าของบรรทัด prerequisite รวมบรรทัดต่อ ตัวอย่างที่พบจริง:
      (ก) บรรทัดก่อนจบด้วย หรือ/และ/OR/AND           →  "... 06036119 ชื่อ หรือ" + "06036122 ชื่อ"
      (ข) บรรทัดถัดไปขึ้นต้นด้วย OR/AND/หรือ/และ       →  "... 06036119 PROGRAMMING" + "OR 06036122 VISUAL"
      (ค) หลัง ':' ว่างเปล่า แล้วรหัสอยู่บรรทัดถัดไป    (ต้องไม่ใช่หัวรายวิชาถัดไปที่มีหน่วยกิต)
    บรรทัดที่เป็นแค่ต่อชื่อวิชา (เช่น "SYSTEMS") ไม่ถูกรวม"""
    text = first_tail
    j = start
    for _ in range(3):
        if j + 1 >= len(lines):
            break
        nxt = lines[j + 1].strip()
        if not nxt or _PRE_EN.search(nxt) or _PRE_TH.search(nxt):
            break
        ends_join = bool(join_tail.search(text.strip()))
        starts_join = bool(re.match(r"^(OR|AND|หรือ|และ)\b", nxt, re.I)) or nxt.startswith(("หรือ", "และ"))
        blank_tail = not re.search(r"[A-Za-z฀-๿0-9]", text)
        is_header = bool(_HDR.match(nxt)) and any(_CRED.search(x) for x in lines[j + 1:j + 4])
        if is_header:
            break
        if (ends_join and _HDR.match(nxt)) or (starts_join and _codes(nxt)) or (blank_tail and _HDR.match(nxt)):
            text += " " + nxt
            j += 1
            continue
        break
    return text


def _parse_value(text: str, none_re: re.Pattern[str]) -> tuple[str, list[str], str | None]:
    """คืน (status, codes, op) — status: none | found | unreadable"""
    if none_re.search(text) and not _codes(text):
        return "none", [], None
    cs = list(dict.fromkeys(_codes(text)))
    if not cs:
        return "unreadable", [], None
    op = None
    if len(cs) > 1:
        op = "or" if re.search(r"หรือ|\bOR\b", text, re.I) else "and"
    return "found", cs, op


def _one_occurrence(lines: list[str], i: int, code: str) -> dict | None:
    """หัวรายวิชาอยู่บรรทัด i — คืนผลของรายวิชานี้ หรือ None ถ้าไม่พบบรรทัด prerequisite ในรายวิชาเดียวกัน"""
    th = en = None
    for j in range(i + 1, min(i + 1 + _WINDOW, len(lines))):
        m0 = _HDR.match(lines[j])
        if m0 and m0.group(1) != code:
            break                                     # เข้ารายวิชาถัดไปแล้ว
        if th is None:
            m = _PRE_TH.search(lines[j])
            if m and "PRE" not in lines[j].upper():
                th = _parse_value(_read_block(lines, j, m.group(1), _JOIN_TAIL_TH), _NONE_TH)
                th_line = j
                continue
        if en is None:
            m = _PRE_EN.search(lines[j])
            if m:
                en = _parse_value(_read_block(lines, j, m.group(1), _JOIN_TAIL_EN), _NONE_EN)
        if th is not None and en is not None:
            break
    if th is None and en is None:
        return None
    return {"th": th, "en": en}


def _merge(th: tuple | None, en: tuple | None) -> tuple[str, list[str], str | None, str | None]:
    """รวมผลบรรทัดไทย/อังกฤษ → (status, codes, op, note)"""
    cands = [x for x in (th, en) if x is not None]
    good = [x for x in cands if x[0] != "unreadable"]
    if not good:
        return "unreadable", [], None, None
    if len(good) == 1:
        return good[0][0], good[0][1], good[0][2], None
    (s1, c1, o1), (s2, c2, o2) = good
    if s1 == s2 and set(c1) == set(c2):
        return s1, c1, o1 or o2, None
    # ไทยกับอังกฤษไม่ตรงกัน (OCR เพี้ยนฝั่งใดฝั่งหนึ่ง) — ใช้ตัวที่ตรงกันก่อน; ไม่มี → ยึดฝั่งไทยแต่ติดธง
    both = [c for c in c1 if c in c2]
    if s1 == s2 == "found" and both:
        return "found", both, ("or" if len(both) > 1 and "or" in (o1, o2) else ("and" if len(both) > 1 else None)), "th_en_partial"
    return s1, c1, o1, "th_en_conflict"


def extract_prerequisites(lines: Iterable[str], wanted: Iterable[str],
                          known_codes: Iterable[str] | None = None) -> dict[str, dict]:
    """สกัดวิชาบังคับก่อนของรหัสใน `wanted` จากข้อความ OCR (แยกเป็นบรรทัด)

    known_codes: รหัสวิชาที่มีจริงในหลักสูตร — ถ้าระบุ จะทิ้งรหัสที่อ่านมาแล้วไม่อยู่ในชุดนี้ (มักเป็นตัวเลข OCR เพี้ยน)
                 ถ้าทิ้งจนไม่เหลือเลย = `unreadable` (ไม่ใช่ none)

    คืน {code: {"status": found|none|not_found|unreadable,
                "requires": [...], "op": and|or|None, "note": ..., "occurrences": n, "dropped": [...]}}
    """
    L = [x.rstrip("\n").replace("\r", "") for x in lines]
    known = set(known_codes) if known_codes is not None else None
    out: dict[str, dict] = {}
    for code in wanted:
        results = []
        for i, l in enumerate(L):
            if not re.match(r"\s*" + re.escape(code) + r"\b", l):
                continue
            if not any(_CRED.search(x) for x in L[i:i + 3]):
                continue
            r = _one_occurrence(L, i, code)
            if r is not None:
                results.append(_merge(r["th"], r["en"]))
        if not results:
            out[code] = {"status": "not_found", "requires": [], "op": None, "note": None,
                         "occurrences": 0, "dropped": []}
            continue
        usable = [r for r in results if r[0] != "unreadable"] or results
        # หลายจุดในเล่มที่ตรงกัน → ใช้ค่าที่พบบ่อยสุด
        key = lambda r: (r[0], tuple(sorted(r[1])), r[2])          # noqa: E731
        best = Counter(map(key, usable)).most_common(1)[0][0]
        status, cs, op = best[0], list(best[1]), best[2]
        note = next((r[3] for r in usable if key(r) == best and r[3]), None)
        dropped: list[str] = []
        if known is not None and status == "found":
            kept = [c for c in cs if c in known and c != code]
            dropped = [c for c in cs if c not in kept]
            cs = kept
            if not cs:
                status, op = "unreadable", None
            elif len(cs) == 1:
                op = None
        out[code] = {"status": status, "requires": cs, "op": op, "note": note,
                     "occurrences": len(results), "dropped": dropped}
    return out


def to_gt_string(res: dict) -> str | None:
    """รูปแบบเดียวกับฟิลด์ prerequisite ของเฉลย: "ไม่มี" / "A" / "A, B" / "A หรือ B" — None = ไม่ทราบ (ไม่ควรกรอก)"""
    if res["status"] == "none":
        return "ไม่มี"
    if res["status"] != "found":
        return None
    sep = " หรือ " if res["op"] == "or" else ", "
    return sep.join(res["requires"])
