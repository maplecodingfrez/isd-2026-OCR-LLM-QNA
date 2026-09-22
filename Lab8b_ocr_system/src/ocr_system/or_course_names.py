"""แก้ชื่อวิชาของคู่ "A หรือ B" (เช่น สหกิจศึกษาในประเทศ/ต่างประเทศ) ที่ตาราง `course` ได้ชื่อซ้ำกันผิด

ทำไมมีปัญหา: หน้าตารางแผนบางแถวเขียนสองรหัสวิชาไว้ในเซลล์เดียว ("A หรือ B") แล้วมีชื่อวิชาสองชื่อคู่กัน
(เช่น "สหกิจศึกษา" กับ "สหกิจศึกษาต่างประเทศ") แต่ qwen3 (ขั้น Markdown -> JSON ของ Lab 7B) จับคู่รหัส
กับชื่อแบบไขว้กัน (สร้างทุกคู่ผสมที่เป็นไปได้) พอ Lab 8B เลือกเก็บชื่อเดียวต่อรหัส มันเลยได้ชื่อซ้ำกันทั้งคู่
ทั้งที่ควรมีชื่อคนละชื่อ — ถ้าไม่แก้ ระบบ NL2SQL จะตอบชื่อวิชาผิดถ้ามีคนถามถึงรหัสที่สอง

กฎเชิงกำหนดล้วน (ไม่เรียก LLM ไม่ใช้เฉลย ไม่เดา): อ่านข้อความ OCR ดิบ (Markdown) หาแถวที่มี "A หรือ B"
สองรหัสจริงในเซลล์เดียว แล้วจับคู่ชื่อกับรหัสตามลำดับที่ปรากฏจริงในเอกสาร (รหัสที่ 1 = ชื่อที่ 1, รหัสที่ 2 = ชื่อที่ 2)
ไม่ใช่การเดาความหมาย — แค่คืนลำดับเดิมที่ Markdown เขียนไว้ถูกอยู่แล้ว แต่ขั้นตอนหลังทำหาย

รองรับ 2 รูปแบบตารางที่เจอจริง:
  1. รหัส "A หรือ B" อยู่ในเซลล์เดียว ไม่มี rowspan ชื่อทั้งสองถูกยัดรวมในอีกเซลล์เดียวคั่นด้วย <br/>
     (เช่น DSBA coop 06026259/06026260) — แยกชื่อด้วยการจับคู่บรรทัดไทย+อังกฤษ (บรรทัดอังกฤษ = ตัวพิมพ์ใหญ่ล้วน)
  2. รหัส "A หรือ B" อยู่ในเซลล์ rowspan ครอบชื่อวิชาคนละแถว (เช่น BIT coop 06036147/06036148)
     — ชื่อของรหัสแรกอยู่แถวเจ้าของ rowspan ชื่อของรหัสถัดไปอยู่แถวต่อ ๆ ไป (แถวละ 1 ชื่อ)

เฉพาะกรณีที่จำนวน "ชุดชื่อ" (บรรทัดไทย/อังกฤษที่จับคู่ได้ หรือจำนวนแถวต่อ) ตรงกับจำนวนรหัสเป๊ะเท่านั้นถึงจะแก้ —
ไม่ตรง = ข้าม (ไม่เดา) เพื่อไม่ให้จับคู่ผิดเงียบ ๆ
"""
from __future__ import annotations

import re
from typing import Any

_CODE = r"(?<!\d)\d{8}(?!\d)"
_ROWSPAN_OR = re.compile(
    rf'<td[^>]*rowspan="(\d+)"[^>]*>\s*({_CODE})\s*(?:<br\s*/?>)?\s*หรือ\s*({_CODE})\s*</td>'
    r'<td[^>]*>(.*?)</td>')
_SINGLE_OR = re.compile(
    rf'<td>\s*({_CODE})\s*(?:<br\s*/?>)?\s*หรือ\s*({_CODE})\s*</td>'
    r'<td[^>]*>(.*?)</td>')
_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_ALLCAPS_EN = re.compile(r"^[A-Z0-9 \-,./()&]+$")


def _clean(text: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", text)
    t = re.sub(r"<[^>]+>", "", t).strip()
    return re.sub(r"\s+", " ", t)


def _thai_first_name(line: str) -> str:
    """ชื่อไทยล้วน (ตัดส่วนภาษาอังกฤษตัวพิมพ์ใหญ่ที่ตามมาถ้ามี)"""
    return re.split(r"\s[A-Z]{2,}", line, maxsplit=1)[0].strip()


def _split_packed_names(cell_html: str, n: int) -> list[str] | None:
    """รูปแบบ 1: เซลล์เดียวมีชื่อของทุกรหัสคั่นด้วย <br/> — จับคู่ (ไทย, อังกฤษ) เรียงเป็นชุด ๆ"""
    lines = [_clean(x) for x in re.split(r"<br\s*/?>", cell_html)]
    lines = [x for x in lines if x]
    pairs: list[str] = []
    i = 0
    while i < len(lines):
        thai = lines[i]
        if _ALLCAPS_EN.match(thai):            # เริ่มด้วยบรรทัดอังกฤษ — รูปแบบไม่ตรงที่คาดไว้
            return None
        if i + 1 < len(lines) and _ALLCAPS_EN.match(lines[i + 1]):
            pairs.append(thai)
            i += 2
        else:
            pairs.append(thai)                  # ไม่มีบรรทัดอังกฤษคู่ — เอาแค่ไทย
            i += 1
    if len(pairs) != n:
        return None
    return pairs


def fix_or_pair_names(md: str) -> dict[str, str]:
    """คืน {รหัส: ชื่อไทยที่ถูกต้อง} เฉพาะคู่ "A หรือ B" ที่จับคู่ได้ชัดเจน (จำนวนชื่อ = จำนวนรหัสเป๊ะ)"""
    out: dict[str, str] = {}

    # รูปแบบ 2: rowspan ครอบชื่อคนละแถว
    for m in _ROWSPAN_OR.finditer(md):
        rowspan, c1, c2, first_name_cell = m.groups()
        codes = [c1, c2]
        names = [_thai_first_name(_clean(first_name_cell))]
        # แถวถัดไปในเอกสาร (แถวต่อของ rowspan) แต่ละแถวคือชื่ออีกรหัสหนึ่ง
        tail = md[m.end():]
        for row_m in _ROW.finditer(tail):
            if len(names) >= len(codes):
                break
            cells = _CELL.findall(row_m.group(1))
            if len(cells) < 1:
                break
            row_text = _clean(cells[0])
            if not row_text or re.fullmatch(r"รวม\s*\d*", row_text):
                break
            names.append(_thai_first_name(row_text))
            if row_m.start() > 400:             # กันเผลอไล่ไกลเกินไปถ้ารูปแบบไม่ตรงคาด
                break
        if len(names) == len(codes) and all(names):
            for code, name in zip(codes, names):
                out[code] = name

    # รูปแบบ 1: เซลล์เดียวยัดชื่อรวม
    for m in _SINGLE_OR.finditer(md):
        c1, c2, name_cell = m.groups()
        codes = [c1, c2]
        names = _split_packed_names(name_cell, len(codes))
        if names:
            for code, name in zip(codes, names):
                out[code] = name

    return out


def apply_to_courses(courses: list[dict[str, Any]], fixes: dict[str, str]) -> int:
    """แก้ course["name_th"] ในที่เดิมตาม fixes คืนจำนวนแถวที่แก้"""
    n = 0
    for c in courses:
        code = c.get("code")
        if code in fixes and c.get("name_th") != fixes[code]:
            c["name_th"] = fixes[code]
            n += 1
    return n
