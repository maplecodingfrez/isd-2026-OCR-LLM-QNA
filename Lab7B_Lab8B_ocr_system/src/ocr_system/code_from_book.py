"""กู้ "รหัสวิชา" ที่ Typhoon-OCR ทำหายจากตารางแผน โดยค้นจากข้อความ OCR ทั้งเล่ม (Tesseract)

ทำไมต้องมี: บางแถวของตารางแผนการศึกษา OCR อ่านชื่อวิชาและหน่วยกิตได้ครบ แต่เซลล์รหัสหาย
  - AIT ปี 1/2: ตราน้ำทับ -> แถว "โครงงานกลุ่ม 1 | 1 (0-2-1)" กลายเป็น <td colspan="2"> ไม่มีรหัส
    (เล่มพิมพ์ 90641004) LLM จึงไม่ส่งวิชานี้ออกมาเลย
  - IT ปี 3/2 (ไม่สหกิจ) / 4/2 (สหกิจ): สองแถว 90642033 กับ 90644042 ถูกรวมเป็น
    <td rowspan="2">90642033</td> -> LLM คืน 90642033 สองครั้งคนละชื่อ แล้ว Lab 8B ตัดตัวซ้ำทิ้ง
แต่ข้อความ OCR ทั้งเล่มของ Tesseract (outputs/<หลักสูตร>/*_curriculum_ocr.txt — OCR อีกตัวของ
"เล่มเดียวกัน" ไม่ใช่เฉลย) พิมพ์ "<รหัส> <ชื่อวิชา> <หน่วยกิต>" ของวิชาเหล่านี้ไว้หลายจุด

กฎเชิงกำหนดล้วน (ไม่เรียก LLM ไม่ใช้เฉลย) และ "ไม่เดา":
  1. แถวเป้าหมาย = แถวในตารางแผนที่ไม่มีเซลล์รหัสของตัวเอง (colspan หรือแถวต่อใต้ rowspan ของรหัสจริง)
     แต่มีชื่อไทยและหน่วยกิต และไม่ใช่ช่องวิชาเลือก/หัวกลุ่มวิชา/แถว "รวม"
  2. ค้นชื่อไทยนั้น (normalize: ตัดช่องว่าง, "ํา" -> "ำ") ในข้อความทั้งเล่ม: บรรทัดที่ขึ้นด้วยรหัส 8 หลัก
     ตามด้วยชื่อที่ "ตรงทั้งชื่อ" — รหัสที่ได้ต้องมี "รหัสเดียว" และต้องมีอย่างน้อยหนึ่งบรรทัดที่หน่วยกิตตรงกัน
  3. รหัสที่กู้ได้ต้องไม่อยู่ในผลของ LLM อยู่แล้ว (กันชนกับวิชาอื่น)
  4. ถ้า LLM ส่งวิชาชื่อนี้มาด้วยรหัสของแถวเจ้าของ rowspan (รหัสซ้ำ) -> เปลี่ยนเป็นรหัสที่กู้ได้
     ถ้า LLM ไม่ส่งวิชานี้มาเลย -> เพิ่มวิชา (category/type = None ไม่เดา)
ไม่ผ่านเงื่อนไขใดข้อหนึ่ง = ไม่แตะ
"""

from __future__ import annotations

import re
from typing import Any

HEADING_RE = re.compile(r"ปีที่\s*(\d)\s*ภาค(?:การศึกษา|เรียน)?\s*ที่\s*(\d)")
ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh]([^>]*)>(.*?)</t[dh]>", re.S)
CODE8 = re.compile(r"(?<!\d)\d{8}(?!\d)")
CREDIT_RE = re.compile(r"(\d+)\s*\(\s*[\dxX]+\s*-")
BOOK_LINE_RE = re.compile(r"(?<!\d)(\d{8})(?!\d)[\s|*.©:-]*(.+)$")
SKIP_PREFIXES = ("วิชาเลือก", "วิชาเสรี", "กลุ่มวิชา", "หมวดวิชา", "รวม", "รหัสวิชา", "ชื่อวิชา")


def normalize(text: str) -> str:
    """ใช้เทียบชื่อไทยข้าม OCR สองตัว: Tesseract เขียน "ํา" (นิคหิต+สระอา) Typhoon เขียน "ำ" """
    t = (text or "").replace("ํา", "ำ").replace("​", "")
    return re.sub(r"\s+", "", t)


def _cells(row_html: str) -> list[tuple[str, str]]:
    out = []
    for attrs, html in CELL_RE.findall(row_html):
        txt = re.sub(r"<br\s*/?>", "\n", html)
        out.append((attrs, re.sub(r"<[^>]+>", "", txt).strip()))
    return out


def _name_lines(cell_text: str) -> tuple[str | None, str | None]:
    """(ชื่อไทย, ชื่ออังกฤษ) จากเซลล์ชื่อ — ข้ามบรรทัด label เช่น "กลุ่มวิชาตามเกณฑ์ของคณะ (...)" """
    th = en = None
    parts = [p.strip() for p in re.split(r"\n| / ", cell_text) if p.strip()]
    for p in parts:
        if "*" in p:
            p = p.split("*", 1)[1].strip()
            if not p:
                continue
        if re.search(r"[฀-๿]", p):
            if p.startswith(("กลุ่มวิชา", "หมวดวิชา")):
                continue
            if th is None:
                th = p
        elif re.match(r"^[A-Z][A-Z0-9 ,&()'/:-]{3,}$", p) and en is None:
            en = p
    return th, en


def target_rows(md: str) -> list[dict[str, Any]]:
    """แถวในตารางแผนที่ "มีชื่อ+หน่วยกิตแต่ไม่มีเซลล์รหัสของตัวเอง" พร้อมเทอมและรหัสเจ้าของ rowspan (ถ้ามี)"""
    events: list[tuple[int, str, Any]] = []
    for m in HEADING_RE.finditer(md):
        events.append((m.start(), "heading", (int(m.group(1)), int(m.group(2)))))
    for m in ROW_RE.finditer(md):
        events.append((m.start(), "row", m.group(1)))
    events.sort(key=lambda e: e[0])

    cur = None
    span_left, span_code = 0, None
    out: list[dict[str, Any]] = []
    for _, kind, payload in events:
        if kind == "heading":
            cur, span_left, span_code = payload, 0, None
            continue
        cells = _cells(payload)
        if cur is None or not cells:
            continue
        row_text = " ".join(t for _, t in cells)
        m = HEADING_RE.search(row_text)
        if m:                                           # หัวเทอมฝังในแถวตาราง
            cur, span_left, span_code = (int(m.group(1)), int(m.group(2))), 0, None
            continue
        first_attrs, first_text = cells[0]
        own_code = CODE8.findall(first_text)
        if own_code or re.search(r"[0-9xX]{6,}", first_text):
            span = re.search(r'rowspan="(\d+)"', first_attrs)
            span_left = int(span.group(1)) - 1 if span else 0
            span_code = own_code[0] if (own_code and len(own_code) == 1 and span) else None
            continue
        continuation = span_left > 0
        if continuation:
            span_left -= 1
        colspan = re.search(r'colspan="(\d+)"', first_attrs)
        if not (continuation or (colspan and int(colspan.group(1)) >= 2)):
            continue
        name_cell = first_text
        credit_text = " ".join(t for _, t in cells[1:]) if len(cells) > 1 else ""
        credit = CREDIT_RE.search(credit_text)
        if not credit:
            continue
        th, en = _name_lines(name_cell)
        if not th or th.startswith(SKIP_PREFIXES):
            continue
        out.append({"year": cur[0], "semester": cur[1], "name_th": th, "name_en": en,
                    "credits": int(credit.group(1)),
                    "credit_text": re.sub(r"\s+", " ", credit_text).strip(),
                    "span_code": span_code if continuation else None})
    return out


def lookup_code(book_text: str, name_th: str, credits: int) -> str | None:
    """รหัส 8 หลักที่เล่มพิมพ์คู่กับชื่อนี้ "ตรงทั้งชื่อ" — ต้องได้รหัสเดียวและมีบรรทัดที่หน่วยกิตตรง"""
    target = normalize(name_th)
    codes: set[str] = set()
    credit_ok: set[str] = set()
    for line in book_text.splitlines():
        m = BOOK_LINE_RE.search(line)
        if not m:
            continue
        rest = m.group(2)
        name_part = re.split(r"\s{2,}|\||\d+\s*\(", rest, maxsplit=1)[0]
        if normalize(name_part) != target:
            continue
        codes.add(m.group(1))
        c = CREDIT_RE.search(rest)
        if c and int(c.group(1)) == credits:
            credit_ok.add(m.group(1))
    if len(codes) == 1 and codes <= credit_ok:
        return next(iter(codes))
    return None


def recover_codes(md: str, courses: list[dict], book_text: str) -> list[dict]:
    """แก้/เพิ่มใน courses (in place) ตามกฎด้านบน คืนรายการที่ทำเพื่อรายงาน"""
    present = {c for x in courses for c in CODE8.findall(str(x.get("code") or ""))}
    done: list[dict] = []
    for row in target_rows(md):
        code = lookup_code(book_text, row["name_th"], row["credits"])
        if not code or code in present:
            continue
        key = normalize(row["name_th"])
        same_name = [c for c in courses
                     if (c.get("year"), c.get("semester")) == (row["year"], row["semester"])
                     and normalize(str(c.get("name_th") or "")) == key]
        if same_name:
            c = same_name[0]
            old = str(c.get("code") or "")
            # แก้เฉพาะกรณี LLM ใช้รหัสของแถวเจ้าของ rowspan (รหัสซ้ำกับอีกวิชา) — ไม่แตะรหัสอื่น
            if not row["span_code"] or old != row["span_code"]:
                continue
            c["code"] = code
            c["_code_from_book"] = {"from": old}
            done.append({"action": "recode", "from": old, "to": code,
                         "term": f"{row['year']}/{row['semester']}", "name_th": row["name_th"]})
        else:
            courses.append({"code": code, "name_th": row["name_th"], "credits": row["credit_text"],
                            "year": row["year"], "semester": row["semester"],
                            "category": None, "type": None, "name_en": row["name_en"],
                            "_code_from_book": {"from": None}})
            done.append({"action": "add", "to": code,
                         "term": f"{row['year']}/{row['semester']}", "name_th": row["name_th"]})
        present.add(code)
    return done
