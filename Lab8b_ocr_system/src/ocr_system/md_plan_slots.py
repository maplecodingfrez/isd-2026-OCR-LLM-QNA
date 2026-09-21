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


def parse_terms(md: str, inherit_span: bool = False) -> dict[tuple[int, int], dict[str, Any]]:
    """คืน {(ปี, เทอม): {total, plain, wildcards, groups, ...}} จาก Markdown ของ OCR

    inherit_span=True: เซลล์รหัส wildcard ที่ rowspan=N ให้แถวที่ถูกครอบ (แถวไม่มีรหัส) แต่ละแถว
    ที่มีหน่วยกิตเป็นช่อง wildcard รหัสเดียวกัน — derive_slots ลองทั้งสองแบบแล้วเลือกแบบที่ยอด "รวม" ลงตัว"""
    terms: dict[tuple[int, int], dict[str, Any]] = {}
    cur: tuple[int, int] | None = None
    span_left = 0                              # จำนวนแถวที่เซลล์รหัส wildcard (rowspan) ยังครอบอยู่
    span_code: str | None = ""
    span_kind = ""                             # "wild" | "mixed" | "real" — ชนิดเซลล์รหัสที่ rowspan ครอบอยู่
    merged_ref: dict | None = None             # เซลล์รหัสหลายตัว rowspan: เก็บหน่วยกิตของแถวที่ถูกครอบ
    span_mixed = False                         # เซลล์ผสม "รหัสจริง+wildcard": wildcard ให้แถวแรกที่ตามมาเท่านั้น
    or_pending: dict | None = None             # แถวที่ชื่อมี "หรือ" รอคู่ทางเลือกถัดไป
    pending: dict | None = None                # wildcard ที่หน่วยกิตว่าง รอเติมจากแถวถัดไป

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
            span_left, pending = 0, None
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
            continue
        t = term()
        t["group_headings"] += row_text.count(GROUP_HEADING)

        # แถว "รวม": ยอดหน่วยกิตของเทอม (เล่มพิมพ์เอง)
        if any(re.fullmatch(r"รวม\s*\d*", txt.strip()) for _, txt in cells):
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
            if pending is not None and pending["credits"] is None and row_credit:
                pending["credits"] = row_credit          # หน่วยกิตของ wildcard อยู่แถวถัดไปใน rowspan เดียวกัน
                if name.startswith("วิชาเลือก"):
                    pending["name_th"] = name
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


def derive_slots(md: str) -> tuple[list[dict], list[dict]]:
    """คืน (slots, term_report) — slots พร้อมใส่ plan_slot, report บอกยอดที่อธิบายได้/ไม่ได้ต่อเทอม"""
    slots: list[dict] = []
    report: list[dict] = []
    base, spanned = parse_terms(md), parse_terms(md, inherit_span=True)
    chosen: dict = {}
    for key, t0 in base.items():
        t1 = spanned.get(key, t0)
        chosen[key] = t0
        if t1["total"] is not None and t1 is not t0:
            def resid(t):
                plain = sum(p["credits"] or 0 for p in t["plain"]) + _merged_credits(t)
                wild = sum(w["credits"] or 0 for w in t["wildcards"])
                return t["total"] - plain - wild
            r0, r1 = resid(t0), resid(t1)
            # แบบที่ตีความ rowspan ต้อง "ลงตัวพอดี" หรือดีกว่าโดยไม่เกินยอดรวม จึงจะใช้
            if r1 == 0 and r0 != 0 or (0 <= r1 < r0 and r0 > 0):
                chosen[key] = t1
    for (year, sem), t in sorted(chosen.items()):
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
