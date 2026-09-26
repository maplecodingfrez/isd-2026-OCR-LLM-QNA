"""
สกัด "ช่องตามเล่ม" (wildcard / "หรือ" / เลือก 1 กลุ่ม) จาก Markdown ที่ Typhoon-OCR อ่านได้ตรง ๆ

ทำไมมีไฟล์นี้: plan_item เก็บเฉพาะวิชารหัสจริง 8 หลัก ทำให้หน่วยกิตรวมไม่ตรงเล่ม
(wildcard หาย, คู่ "หรือ" นับซ้ำ, กลุ่ม "เลือก 1 กลุ่ม" นับทุกวิชา) — แต่ข้อมูลเหล่านี้ "อยู่ใน
ผล OCR อยู่แล้ว" ไฟล์นี้จึงไม่รับข้อมูลจากที่อื่นเลย (ไม่อ่านเฉลย ไม่กรอกมือ ไม่เรียก LLM)
เป็นกฎเชิงกำหนดล้วน ๆ จึงรันซ้ำได้ผลเดิมเสมอ

หลักคิด:
  1. หัว "ปีที่ N ภาคการศึกษาที่ M" บอกเทอมของทุกแถวที่ตามมา (รวมแถวที่หัวฝังอยู่กลางตาราง)
  2. แถว "รวม" ที่เล่มพิมพ์ไว้ = checksum ของเทอม
  3. หน่วยกิตของ "เลือก 1 กลุ่ม" = ยอดรวมเทอม − วิชาปกติ − wildcard (คำนวณเอง ไม่ต้องรู้ล่วงหน้า)
  4. หน่วยกิตที่ยังอธิบายไม่ได้ = วิชาที่ OCR ตกจริง → รายงานเป็น "unexplained" (ตรวจ MISS อัตโนมัติ)
"""
from __future__ import annotations

import re
from typing import Any

HEADING_RE = re.compile(r"ปีที่\s*(\d)\s*ภาค(?:การศึกษา|เรียน)?\s*ที่\s*(\d)")
ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh]([^>]*)>(.*?)</t[dh]>", re.S)
REAL_CODE_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")
# wildcard: ตัวเลข/x ผสม 6-12 ตัว มี x อย่างน้อย 2 ตัว (เช่น 060464xx) (OCR สะกดเพี้ยนได้: xxxxxxx, Xxxxxxxx, 9064xxx)
WILD_RE = re.compile(r"(?<![0-9A-Za-z])(?=[0-9xX]{0,11}[xX]{2})[0-9xX]{6,12}(?![0-9A-Za-z])")
CREDIT_RE = re.compile(r"(\d+)\s*\(")
GROUP_HEADING = "กลุ่มวิชาด้าน"
ELECTIVE_PREFIXES = ("วิชาเลือก", "วิชาเสรี")


def _text(cell_html: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", cell_html)
    return re.sub(r"<[^>]+>", "", t).strip()


def _thai_name(text: str) -> str:
    """ชื่อไทยของแถว: ตัดส่วนภาษาอังกฤษตัวพิมพ์ใหญ่ที่ตามมา และหน่วยกิตที่ปนมาในเซลล์"""
    t = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    t = re.split(r"\s[A-Z]{2,}", t, maxsplit=1)[0]
    t = re.sub(r"\d+\s*\(.*$", "", t)
    return t.strip(" -")


def _credit(cells: list[str]) -> int | None:
    for c in cells:
        m = CREDIT_RE.search(c)
        if m:
            return int(m.group(1))
    return None


def _series_no(name: str) -> int | None:
    """เลขลำดับชุดของช่องวิชาเลือก จากชื่อไทย เช่น "วิชาเลือกกลุ่มวิทยาการข้อมูล 2" -> 2 (ไม่มีเลข = None)
    ใช้ "เลขแรก" หลังชื่อ ไม่ใช่เลขท้าย — BIT มี "…ธุรกิจ 1 หรือ กลุ่มวิชาที่ 1-4" (เลขท้าย 4 ไม่ใช่เลขชุด)"""
    th = _thai_name(name)
    if not th.startswith(ELECTIVE_PREFIXES):
        return None
    m = re.search(r"^\D*?(\d+)", th)
    return int(m.group(1)) if m else None


def parse_terms(md: str, inherit_span: bool = False,
                split_series: bool = False) -> dict[tuple[int, int], dict[str, Any]]:
    """คืน {(ปี, เทอม): {total, plain, wildcards, groups, ...}} จาก Markdown ของ OCR

    inherit_span=True: เซลล์รหัส wildcard ที่ rowspan=N ให้แถวที่ถูกครอบ (แถวไม่มีรหัส) แต่ละแถว
    ที่มีหน่วยกิตเป็นช่อง wildcard รหัสเดียวกัน — derive_slots ลองทั้งสองแบบแล้วเลือกแบบที่ยอด "รวม" ลงตัว

    split_series=True: ใต้เซลล์ wildcard ที่ rowspan เดียว ถ้าแถวที่ถูกครอบเป็น "วิชาเลือก… N" ที่ N เป็นเลขชุด
    ใหม่ (ยังไม่มีช่องของเลขนี้ใน rowspan นั้น) และมีหน่วยกิตของตัวเอง = อีกช่องหนึ่งที่เซลล์รหัสหายจาก OCR
    เจอจริง: DSBA ปี 3/1 เล่มพิมพ์ 06026xxx สองช่อง (วิชาเลือกกลุ่ม… 1 / … 2) แต่ Typhoon-OCR รวมเป็น
    rowspan="4" เซลล์เดียว — แถว "… 1" ที่เหลือ (ตัวเลือกอื่นของชุดเดียวกัน) ไม่นับซ้ำ"""
    terms: dict[tuple[int, int], dict[str, Any]] = {}
    cur: tuple[int, int] | None = None
    span_left = 0                              # จำนวนแถวที่เซลล์รหัส wildcard (rowspan) ยังครอบอยู่
    span_code: str | None = ""
    span_series: set[int] = set()              # split_series: เลขชุดที่มีช่องแล้วใน rowspan wildcard ปัจจุบัน
    span_kind = ""                             # "wild" | "mixed" | "real" — ชนิดเซลล์รหัสที่ rowspan ครอบอยู่
    merged_ref: dict | None = None             # เซลล์รหัสหลายตัว rowspan: เก็บหน่วยกิตของแถวที่ถูกครอบ
    span_mixed = False                         # เซลล์ผสม "รหัสจริง+wildcard": wildcard ให้แถวแรกที่ตามมาเท่านั้น
    or_pending: dict | None = None             # แถวที่ชื่อมี "หรือ" รอคู่ทางเลือกถัดไป
    pending: dict | None = None                # wildcard ที่หน่วยกิตว่าง รอเติมจากแถวถัดไป
    nocode_open: dict | None = None            # กลุ่ม "กลุ่มวิชาด้าน…" ที่ไม่มีรหัส — แถวไม่มีรหัสที่ตามมาเป็นชื่อสมาชิก

    def term() -> dict[str, Any]:
        return terms.setdefault(cur, {
            "total": None, "plain": [], "wildcards": [], "choose_one": [],
            "group_cells": [], "group_headings": 0, "dangling": [], "notes": []})

    # อ่านตามลำดับตำแหน่ง: หัวเทอม (ในข้อความหรือในแถว) สลับกับแถวตาราง
    pos = 0
    events: list[tuple[int, str, Any]] = []
    for m in HEADING_RE.finditer(md):
        events.append((m.start(), "heading", (int(m.group(1)), int(m.group(2)))))
    for m in ROW_RE.finditer(md):
        events.append((m.start(), "row", m.group(1)))
    events.sort(key=lambda e: e[0])

    for _, kind, payload in events:
        if kind == "heading":
            cur = payload
            span_left, pending, nocode_open = 0, None, None
            continue
        if cur is None:
            continue
        cells = [(a, _text(h)) for a, h in CELL_RE.findall(payload)]
        if not cells:
            continue
        row_text = " ".join(t for _, t in cells)
        if HEADING_RE.search(row_text):        # แถวที่เป็นหัวเทอมฝังในตาราง — ไม่ใช่วิชา
            m = HEADING_RE.search(row_text)
            cur = (int(m.group(1)), int(m.group(2)))
            nocode_open = None
            continue
        t = term()
        t["group_headings"] += row_text.count(GROUP_HEADING)

        # แถว "รวม": ยอดหน่วยกิตของเทอม (เล่มพิมพ์เอง)
        if any(re.fullmatch(r"รวม\s*\d*", txt.strip()) for _, txt in cells):
            nocode_open = None
            # "รวม" กับตัวเลขอยู่คนละเซลล์ หรือเซลล์เดียวกัน ("รวม 15") — OCR เขียนได้ทั้งสองแบบ
            nums = [int(x) for _, txt in cells
                    for x in re.findall(r"^(?:รวม\s*)?(\d+)$", txt.strip())]
            if nums:
                t["total"] = nums[-1]
            continue
        if cells[0][1].strip() in ("รหัสวิชา", "ชื่อวิชา"):   # แถวหัวตาราง
            continue

        code_cell = cells[0][1]
        credit = _credit([txt for _, txt in cells[1:]])
        reals = REAL_CODE_RE.findall(code_cell)
        wilds = WILD_RE.findall(code_cell)
        name = _thai_name(" ".join(txt for _, txt in cells[1:]) if len(cells) > 1 else "")
        if not name and wilds:                  # colspan: รหัสกับชื่ออยู่เซลล์เดียวกัน
            name = _thai_name(WILD_RE.sub("", code_cell))

        # ชื่อสมาชิกของกลุ่มที่ไม่มีรหัสอาจอยู่คนละแถวกับหัวกลุ่ม (พบจริง: IT ไม่สหกิจ ปี 2/2 รอบ OCR ซ้ำ — หัวกลุ่ม
        # ไม่มี rowspan แถวถัดไปคือ "ระบบโครงสร้างพื้นฐานและการบริการ" ของ 06016420) — เก็บข้อความแถวที่ไม่มีรหัส
        # ต่อท้ายกลุ่มไว้ให้ derive_slots ค้นชื่อ จนกว่าจะเจอแถวที่มีรหัส/หัวกลุ่มใหม่/แถวรวม/หัวเทอม
        if reals or wilds:
            nocode_open = None
        elif nocode_open is not None and not code_cell.lstrip().startswith(GROUP_HEADING):
            nocode_open["text"] += " " + row_text

        # แถวต่อของ rowspan ที่เซลล์รหัสรวมหลายวิชา (span_kind == "merged") บางครั้งเล่ม/OCR ไม่แยกคอลัมน์
        # ให้แถวต่อ แต่ยำรหัสวิชาไว้ในเซลล์บรรยายเดียว (พบจริง: IT ปี 2/2 — แถว "06016419 กลุ่มวิชาด้าน...")
        # ทำให้ REAL_CODE_RE เจอรหัสแล้วเข้าใจผิดว่าเป็นแถวใหม่ (ไม่เข้าเงื่อนไข "not reals and not wilds"
        # ด้านล่าง จึงหลุดไปนับเป็นวิชาปกติทั้งที่เครดิตอยู่ในเซลล์ของแถวเจ้าของ rowspan เท่านั้น — credits=None)
        # ตัวกันนี้จับก่อนด้วยเงื่อนไข "อยู่กลาง rowspan ของกลุ่ม + มีแค่เซลล์เดียว" (แถวข้อมูลปกติมีอย่างน้อย 2 เซลล์เสมอ):
        #   ไม่มี GROUP_HEADING ในเซลล์ = วิชาที่สองของกลุ่มย่อยเดิม (ใช้เครดิตต่อวิชาเดียวกับที่ rowspan ให้มา)
        #   มี GROUP_HEADING = กลุ่มย่อยถัดไปเริ่มแล้ว (เล่มมีมากกว่า 1 กลุ่มใต้ rowspan เดียว แต่ OCR ไม่ได้แยกเซลล์รหัส)
        #   รหัสที่ซ้ำกับกลุ่มที่มีอยู่แล้วในเทอมนี้ = แถวอธิบายซ้ำ (พบจริงหน้าเดียวกัน) — ข้าม ไม่สร้างกลุ่มซ้อน
        if reals and len(cells) == 1 and span_left > 0 and span_kind == "merged":
            new_codes = [rc for rc in reals if not any(rc in g["codes"] for g in t["group_cells"])]
            if new_codes:
                if GROUP_HEADING in code_cell and merged_ref is not None and merged_ref["codes"]:
                    per_credit = merged_ref["credits"][0] if merged_ref["credits"] else None
                    merged_ref = {"codes": [], "credits": []}
                    t["group_cells"].append(merged_ref)
                else:
                    per_credit = merged_ref["credits"][0] if merged_ref and merged_ref["credits"] else None
                if merged_ref is not None:
                    for rc in new_codes:
                        merged_ref["codes"].append(rc)
                        if per_credit:
                            merged_ref["credits"].append(per_credit)
            span_left -= 1
            continue

        # หัว "กลุ่มวิชาด้าน…" ที่ไม่มีเซลล์รหัสของตัวเอง = กลุ่มวิชาที่ OCR ทำรหัสหาย (พบจริง: IT ปี 3/1 ตราน้ำทับ
        # กลุ่มโครงสร้างพื้นฐาน — เซลล์แรกเป็นหัวกลุ่ม + ชื่อวิชา 3 วิชา rowspan="4" ไม่มีรหัส) — เป็น "กลุ่ม" ของ
        # "เลือก 1 กลุ่ม" ไม่ใช่ช่อง wildcard (เดิม inherit_span สร้างเป็น wildcard ปลอม 3 หน่วยกิต ทำให้กลุ่มเหลือ 2)
        # รหัสสมาชิก: แถวรหัสจริงที่อยู่ใต้ rowspan นี้ + (ใน derive_slots) วิชาใน DB ที่ชื่ออยู่ในเซลล์นี้
        if not reals and not wilds and code_cell.lstrip().startswith(GROUP_HEADING):
            entry = {"codes": [], "credits": [], "text": code_cell, "nocode": True}
            t["group_cells"].append(entry)
            m_span = re.search(r'rowspan="(\d+)"', cells[0][0])
            span_left = int(m_span.group(1)) - 1 if m_span else 0
            span_code, span_mixed, span_kind, merged_ref, pending = None, False, "nocode_group", entry, None
            nocode_open = entry
            continue
        if span_left > 0 and span_kind == "nocode_group":
            if len(reals) == 1 and not wilds and merged_ref is not None:
                merged_ref["codes"].append(reals[0])     # แถวรหัสจริงใต้กลุ่มที่ไม่มีรหัส = สมาชิกของกลุ่มนั้น
                span_left -= 1
                continue
            if not reals and not wilds:
                span_left -= 1                           # แถวหน่วยกิตของสมาชิกในกลุ่ม ไม่ใช่วิชาปกติ/ช่อง
                continue

        if not reals and not wilds:
            # แถวต่อของ rowspan (ไม่มีรหัส) — ไม่นับหน่วยกิตเป็นวิชาปกติ
            row_credit = _credit([txt for _, txt in cells])
            m_col = re.search(r'colspan="(\d+)"', cells[0][0])
            if (m_col and int(m_col.group(1)) >= 2 and row_credit
                    and cells[0][1].startswith(ELECTIVE_PREFIXES)):
                # แถวช่องวิชาเลือกที่ไม่มีคอลัมน์รหัสเลย (colspan) — OCR ไม่พิมพ์รหัส xxxxxxxx ให้
                t["wildcards"].append({"code": None, "name_th": _thai_name(cells[0][1]),
                                       "credits": row_credit})
                continue
            series = _series_no(cells[0][1]) if split_series else None
            if pending is not None and pending["credits"] is None and row_credit:
                pending["credits"] = row_credit          # หน่วยกิตของ wildcard อยู่แถวถัดไปใน rowspan เดียวกัน
                if name.startswith("วิชาเลือก"):
                    pending["name_th"] = name
            elif (split_series and span_left > 0 and span_kind == "wild" and row_credit
                  and series is not None and span_series and series not in span_series):
                t["wildcards"].append({"code": span_code, "name_th": _thai_name(cells[0][1]),
                                       "credits": row_credit})
                span_series.add(series)
            elif (inherit_span and span_left > 0 and row_credit and _thai_name(cells[0][1])
                  and (span_kind != "real" or cells[0][1].startswith(ELECTIVE_PREFIXES))):
                slot = {"code": span_code, "name_th": _thai_name(cells[0][1]),
                        "credits": row_credit}
                if span_mixed:
                    span_code = None           # รหัสของแถวหลัง ๆ หายจาก OCR — ไม่เดา
                t["wildcards"].append(slot)
            if span_kind == "merged" and merged_ref is not None and span_left > 0 and row_credit:
                merged_ref["credits"].append(row_credit)
            if span_left > 0:
                span_left -= 1
            continue
        span_left, span_mixed, merged_ref = 0, False, None

        # 1) wildcard: ช่องวิชาเลือก
        for w in wilds:
            if reals:                          # เซลล์ rowspan รวม "รหัสจริง + wildcard" — แถวของ wildcard หาย
                t["dangling"].append({"code": w.lower(), "name_th": name or "วิชาเลือก"})
                m_span = re.search(r'rowspan="(\d+)"', cells[0][0])
                if m_span and int(m_span.group(1)) > 1:
                    span_left, span_code, span_mixed, span_kind = int(m_span.group(1)) - 1, w.lower(), True, "mixed"
            else:
                slot = {"code": w.lower(), "name_th": name or "วิชาเลือก", "credits": credit}
                t["wildcards"].append(slot)
                pending = slot if credit is None else None
                m_span = re.search(r'rowspan="(\d+)"', cells[0][0])
                if m_span and int(m_span.group(1)) > 1:
                    span_left, span_code, span_mixed, span_kind = int(m_span.group(1)) - 1, w.lower(), False, "wild"
                    head_series = _series_no(name)
                    span_series = {head_series} if head_series is not None else set()
        if wilds and not reals:
            continue

        # 2) "A หรือ B" — รหัสคั่นด้วย หรือ ในเซลล์เดียว หรือแถวที่ขึ้นต้นด้วย หรือ (อีกทางเลือกของแถวก่อนหน้า)
        starts_or = code_cell.lstrip().startswith("หรือ")
        if len(reals) >= 2 and "หรือ" in code_cell:
            t["choose_one"].append({"codes": reals, "credits": credit})
            t["plain"].append({"code": reals[0], "credits": credit, "via": "choose_one"})
            continue
        if starts_or and reals and t["plain"]:
            prev = t["plain"][-1]
            t["choose_one"].append({"codes": [prev["code"], reals[0]], "credits": credit or prev["credits"]})
            continue                            # ทางเลือกที่สอง ไม่นับหน่วยกิตซ้ำ

        # 3) เซลล์รหัสหลายตัว: กลุ่ม "เลือก 1 กลุ่ม" ถ้าเทอมนี้มีหัวกลุ่มวิชา ไม่งั้นเป็น rowspan รวมแถว
        if len(reals) >= 2:
            entry = {"codes": reals, "credits": [credit] if credit else []}
            t["group_cells"].append(entry)
            m_span = re.search(r'rowspan="(\d+)"', cells[0][0])
            if m_span and int(m_span.group(1)) > 1:
                span_left, span_code, span_mixed, span_kind = int(m_span.group(1)) - 1, None, False, "merged"
                merged_ref = entry
            continue

        # แถวก่อนหน้าเขียน "... หรือ <ชื่อวิชาที่สอง>" ในเซลล์ชื่อ → แถวนี้คือทางเลือกที่สอง (AIT สหกิจ)
        if or_pending is not None and or_pending["credits"] == credit:
            t["choose_one"].append({"codes": [or_pending["code"], reals[0]], "credits": credit})
            or_pending = None
            continue
        or_pending = None
        rec = {"code": reals[0], "credits": credit, "name_th": name}
        t["plain"].append(rec)
        m_span = re.search(r'rowspan="(\d+)"', cells[0][0])
        if len(reals) == 1 and m_span and int(m_span.group(1)) > 1:
            # รหัสจริง rowspan ครอบแถว "วิชาเลือก..." ที่ไม่มีรหัสข้างล่าง (รหัส xxx ของแถวนั้นหายจาก OCR)
            span_left, span_code, span_mixed, span_kind = int(m_span.group(1)) - 1, None, False, "real"
        if (re.search(r"(?:^|\s)หรือ(?:\s|$)", cells[1][1] if len(cells) > 1 else "")
                or re.search(r"(?:^|\s)หรือ\s*$", code_cell)):
            or_pending = rec
    return terms


def _merged_credits(t: dict) -> int:
    """เทอมที่ไม่มีหัว "กลุ่มวิชาด้าน…": เซลล์รหัสหลายตัว rowspan = วิชาปกติที่ OCR รวมเซลล์
    (จับคู่รหัสกับแถวตามลำดับ) นับหน่วยกิตของแถวเหล่านั้นเป็นวิชาปกติ"""
    if t["group_headings"] >= 2:
        return 0
    return sum(c for g in t["group_cells"] if len(g["credits"]) == len(g["codes"]) for c in g["credits"])


def _loose(text: str) -> str:
    """เทียบชื่อไทยข้าม OCR: ตัดช่องว่าง, "ํา"->"ำ", ตัดวรรณยุกต์/ไม้ไต่คู้/การันต์ (เช่น "ออโตเมชัน" vs "ออโตเมชั่น")"""
    t = (text or "").replace("ํา", "ำ")
    return re.sub(r"[\s็-์​]", "", t)


def derive_slots(md: str, names_by_term: dict[tuple[int, int], dict[str, str]] | None = None
                 ) -> tuple[list[dict], list[dict]]:
    """คืน (slots, term_report) — slots พร้อมใส่ plan_slot, report บอกยอดที่อธิบายได้/ไม่ได้ต่อเทอม

    names_by_term: {(ปี, เทอม): {รหัส: ชื่อไทย}} ของวิชาใน DB — ใช้หาสมาชิกของกลุ่มวิชาที่ OCR ทำรหัสหาย
    (ชื่อวิชาต้องอยู่ในเซลล์หัวกลุ่มนั้น) ไม่ส่งมา = ใช้เฉพาะรหัสที่อยู่ใน Markdown"""
    slots: list[dict] = []
    report: list[dict] = []
    base, spanned = parse_terms(md), parse_terms(md, inherit_span=True)
    series = parse_terms(md, split_series=True)

    def resid(t):
        plain = sum(p["credits"] or 0 for p in t["plain"]) + _merged_credits(t)
        wild = sum(w["credits"] or 0 for w in t["wildcards"])
        return t["total"] - plain - wild

    chosen: dict = {}
    for key, t0 in base.items():
        chosen[key] = t0
        if t0["total"] is None:
            continue
        # แบบที่ตีความ rowspan ต้อง "ลงตัวพอดี" หรือดีกว่าโดยไม่เกินยอดรวม จึงจะใช้ — ยอด "รวม" ใช้เป็นตัว
        # กันนับเกินเท่านั้น จำนวนช่องมาจากโครงสร้างตาราง (rowspan / เลขชุดในชื่อ) ไม่ได้เติมให้พอดียอด
        # ลองตามลำดับ: inherit_span (ของเดิม) ก่อน แล้ว split_series
        for t1 in (spanned.get(key, t0), series.get(key, t0)):
            cur_t = chosen[key]
            r0, r1 = resid(cur_t), resid(t1)
            if t1 is not cur_t and (r1 == 0 and r0 != 0 or (0 <= r1 < r0 and r0 > 0)):
                chosen[key] = t1
    for (year, sem), t in sorted(chosen.items()):
        for g in t["group_cells"]:
            if g.get("nocode"):
                cell = _loose(g["text"])
                for code, name in sorted((names_by_term or {}).get((year, sem), {}).items()):
                    key = _loose(name)
                    if len(key) >= 8 and key in cell and code not in g["codes"]:
                        g["codes"].append(code)
        plain_sum = sum(p["credits"] or 0 for p in t["plain"]) + _merged_credits(t)
        wild_sum = sum(w["credits"] or 0 for w in t["wildcards"])
        total = t["total"]
        residual = None if total is None else total - plain_sum - wild_sum
        notes: list[str] = list(t["notes"])

        for w in t["wildcards"]:
            slots.append({"year": year, "semester": sem, "kind": "wildcard", "code": w["code"],
                          "name_th": w["name_th"], "credits": w["credits"] or 0})
        for o in t["choose_one"]:
            slots.append({"year": year, "semester": sem, "kind": "choose_one",
                          "name_th": "เลือกอย่างใดอย่างหนึ่ง (A หรือ B)", "credits": o["credits"] or 0,
                          "groups": [{"name": "A หรือ B", "codes": o["codes"]}]})

        is_group = t["group_cells"] and t["group_headings"] >= 2
        if is_group:
            g_credit = residual if (residual is not None and residual > 0) else 0
            if residual is None:
                notes.append("ไม่พบแถว รวม ของเทอม: หน่วยกิตของกลุ่มเลือก 1 อนุมานไม่ได้ (ตั้งเป็น 0)")
            slots.append({"year": year, "semester": sem, "kind": "choose_group",
                          "name_th": "เลือก 1 กลุ่มวิชา", "credits": g_credit,
                          "note": "หน่วยกิต = ยอดรวมเทอม − วิชาปกติ − wildcard (คำนวณจากแถว รวม)",
                          "groups": [{"name": f"กลุ่ม {i}", "codes": g["codes"]}
                                     for i, g in enumerate(t["group_cells"], 1)]})
            if residual is not None:
                residual -= g_credit
        elif t["group_cells"]:
            notes.append("เซลล์รหัสหลายตัวที่ไม่มีหัวกลุ่มวิชา — เป็น rowspan รวมแถว นับเป็นวิชาปกติ ไม่ถือเป็นช่อง")

        # wildcard ที่แถวหายเพราะ rowspan รวมกับรหัสจริง: ใช้หน่วยกิตที่เหลือจาก checksum (ถ้าหารลงตัว)
        if t["dangling"] and residual is not None and residual > 0:
            each, rem = divmod(residual, len(t["dangling"]))
            if rem == 0 and each > 0:
                for d in t["dangling"]:
                    slots.append({"year": year, "semester": sem, "kind": "wildcard", "code": d["code"],
                                  "name_th": d["name_th"], "credits": each,
                                  "note": "แถวของ wildcard ถูกรวมกับรหัสจริงในเซลล์ rowspan — หน่วยกิตมาจาก checksum"})
                residual = 0
        report.append({"year": year, "semester": sem, "declared_total": total,
                       "plain": plain_sum, "wildcard": wild_sum,
                       "unexplained": residual, "notes": notes})
    return slots, report


def md_codes_by_term(md: str) -> dict[tuple[int, int], set[str]]:
    """รหัสวิชาจริงที่ปรากฏในแต่ละเทอมของ Markdown (วิชาปกติ + สมาชิกกลุ่ม/ทางเลือก)
    ใช้เทียบกับ plan_item: รหัสที่อยู่ใน Markdown แต่ไม่อยู่ใน DB = วิชาหายที่ขั้น Markdown -> JSON (LLM)"""
    out: dict[tuple[int, int], set[str]] = {}
    for key, t in parse_terms(md).items():
        codes = {p["code"] for p in t["plain"]}
        for g in t["group_cells"]:
            codes.update(g["codes"])
        for o in t["choose_one"]:
            codes.update(o["codes"])
        out[key] = codes
    return out


def recover_terms(md: str, courses: list[dict]) -> list[dict]:
    """กู้ปี/เทอมของวิชารหัสจริงที่ได้ 0/0 (หรือค่านอกช่วง) จากตำแหน่งใน Markdown

    เจอจริง: เซลล์ rowspan ผสม "96643021<br/>06036xxx" ทำให้ขั้น Markdown→JSON เหมารวมวิชาจริงเป็นแถว
    wildcard (ปี/เทอมถูกบังคับ 0/0) แล้ว convert_lab7b ข้ามออกจากแผน ทั้งที่ Markdown บอกเทอมชัดเจน
    กฎ: รหัสต้องปรากฏใน "เทอมเดียว" ของ Markdown เท่านั้น (ถ้าอยู่หลายเทอม เช่น 06016418 จะไม่เดา)
    แก้ courses ในที่ (in place) และคืนรายการที่กู้ได้ไว้รายงาน
    """
    where: dict[str, set[tuple[int, int]]] = {}
    for key, codes in md_codes_by_term(md).items():
        for c in codes:
            where.setdefault(c, set()).add(key)
    recovered: list[dict] = []
    for c in courses:
        try:
            ok = 1 <= int(c.get("year")) <= 8 and 1 <= int(c.get("semester")) <= 3
        except (TypeError, ValueError):
            ok = False
        if ok:
            continue
        reals = REAL_CODE_RE.findall(str(c.get("code") or ""))
        terms = {t for r in reals for t in where.get(r, ())}
        if reals and len(terms) == 1:
            y, sm = next(iter(terms))
            recovered.append({"code": c.get("code"), "from": f"{c.get('year')}/{c.get('semester')}",
                              "to": f"{y}/{sm}"})
            c["year"], c["semester"] = y, sm
    return recovered


def _row_for_code(md: str, code: str) -> list[str] | None:
    """เซลล์ (ข้อความ) ของแถวตารางที่เซลล์แรกเป็นรหัสนี้ "ทั้งเซลล์" — คืน None ถ้าไม่มีหรือมีมากกว่า 1 แถว"""
    found = []
    for m in ROW_RE.finditer(md):
        cells = [_text(h) for _, h in CELL_RE.findall(m.group(1))]
        if cells and re.sub(r"\s+", "", cells[0]) == code:
            found.append(cells)
    return found[0] if len(found) == 1 else None


def fill_missing_rows(md: str, courses: list[dict]) -> list[dict]:
    """เติมวิชาที่ Markdown ของ OCR มีครบ แต่ขั้น Markdown -> JSON (LLM) ทิ้งไป

    เจอจริง: DSBA no_coop ปี 3/2 แถว 90643021 อยู่ใน Markdown ครบ (รหัส/ชื่อ/หน่วยกิต) แต่ qwen ข้ามไป
    เพราะแถวก่อนหน้า (06066100) มี rowspan="2" + แถวว่างที่ OCR สร้างขึ้น — แผน coop แถวเดียวกันอ่านได้ปกติ
    กฎ (ตั้งใจแคบ: ไม่เดา ไม่ใช้เฉลย ไม่เรียก LLM):
      1. เป็นวิชาปกติใน parse_terms (ไม่ใช่สมาชิก "หรือ"/กลุ่ม/wildcard) และอ่านหน่วยกิตได้
      2. รหัสปรากฏใน "เทอมเดียว" ของ Markdown และมีแถวที่เซลล์แรกเป็นรหัสนี้ทั้งเซลล์ "แถวเดียว"
      3. รหัสนี้ไม่อยู่ใน courses เลย (ทุกปี/เทอม รวม 0/0 และคู่ "A หรือ B")
    ฟิลด์ที่ Markdown ไม่บอกตรง ๆ (category/type) ปล่อยเป็น None ไม่เดา
    เพิ่มลง courses ในที่ (in place) และคืนรายการที่เติมไว้รายงาน"""
    present = {rc for c in courses for rc in REAL_CODE_RE.findall(str(c.get("code") or ""))}
    where: dict[str, set[tuple[int, int]]] = {}
    for key, codes in md_codes_by_term(md).items():
        for c in codes:
            where.setdefault(c, set()).add(key)
    added: list[dict] = []
    for (year, sem), term in sorted(parse_terms(md).items()):
        for rec in term["plain"]:
            code = rec["code"]
            if rec.get("via") or rec.get("credits") is None or code in present:
                continue
            if where.get(code) != {(year, sem)}:
                continue
            cells = _row_for_code(md, code)
            if not cells or len(cells) < 3:
                continue
            name_cell = re.sub(r"\s+", " ", cells[1]).strip()
            if "*" in name_cell:                   # label หัวกลุ่มหน้า "*" เช่น "กลุ่มวิชาที่กำหนดโดยคณะ*"
                name_cell = name_cell.split("*", 1)[1].strip()
            name_th = _thai_name(name_cell)
            m_en = re.search(r"[A-Z][A-Z0-9 ,&()'/:-]{3,}$", name_cell)
            credit_text = re.sub(r"\s+", " ", cells[2]).strip()
            if not name_th or not CREDIT_RE.search(credit_text):
                continue
            courses.append({"code": code, "name_th": name_th, "credits": credit_text,
                            "year": year, "semester": sem, "category": None, "type": None,
                            "name_en": m_en.group(0).strip() if m_en else None,
                            "_filled_from_markdown": True})
            present.add(code)
            added.append({"code": code, "term": f"{year}/{sem}", "name_th": name_th,
                          "credits": credit_text})
    return added


def page_check(md: str) -> dict:
    """ตรวจว่า Markdown หนึ่งหน้า "ลงตัวกับยอดรวมของเล่ม" ไหม — ใช้ตัดสินว่าต้องอ่านหน้านั้นซ้ำหรือไม่

    คืน {"ok", "terms", "bad_terms", "score"}: ok = ทุกเทอมที่ปรากฏมียอด "รวม" และอธิบายหน่วยกิตครบพอดี (หน้าที่ไม่มีเทอมเลย terms=0 ถือว่าไม่มีอะไรให้ตรวจ = ok)
    score = ผลรวม |unexplained| (+ 100 ต่อเทอมที่ไม่มียอดรวม) — ยิ่งน้อยยิ่งดี ใช้เลือกรอบที่ดีที่สุดเมื่ออ่านซ้ำแล้วยังไม่ลงตัว
    """
    _, report = derive_slots(md)
    bad, score = [], 0
    for r in report:
        if r["declared_total"] is None:
            bad.append((r["year"], r["semester"], "ไม่พบแถว รวม"))
            score += 100
        elif r["unexplained"]:
            bad.append((r["year"], r["semester"], r["unexplained"]))
            score += abs(r["unexplained"])
    return {"ok": not bad, "terms": len(report), "bad_terms": bad, "score": score}
