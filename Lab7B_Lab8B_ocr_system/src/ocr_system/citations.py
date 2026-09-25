"""อ้างอิงหน้าในคำตอบ (ระดับ 1–2)

กฎเชิงกำหนดล้วน ไม่ใช้ LLM ไม่ใช้เฉลย: หน้าไหนมีรหัสวิชา (จาก OCR ทั้งเล่มของ Tesseract) และหน้าไหนเป็น
ตารางแผนของเทอมใด (จากภาพหน้าที่ Lab 7B อ่าน) — หาไม่เจอ = ไม่อ้างอิง ห้ามเดาเลขหน้า"""
from __future__ import annotations

import re

PAGE_NO_RE = re.compile(r"^\s*(\d{1,3})(?:\s|$)")
MAX_CITED = 3


def _norm_th(text: str | None) -> str:
    return re.sub(r"\s+", "", (text or "").replace("ํา", "ำ"))


def _norm_en(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").upper()).strip()


def printed_page(text: str) -> str | None:
    """เลขหน้าที่พิมพ์ในเล่ม = ตัวเลขต้นบรรทัดแรกที่ไม่ว่าง ("33", "19   รายละเอียดหลักสูตร") ไม่ใช่ตัวเลข = None"""
    for line in (text or "").splitlines():
        if line.strip():
            m = PAGE_NO_RE.match(line)
            return m.group(1) if m else None
    return None


def course_pages(ocr_pages: list[dict], courses: list[dict]) -> list[dict]:
    """หน้า (PDF) ที่มีรหัสวิชาแต่ละตัว — primary เมื่อหน้านั้นมีชื่อไทยหรืออังกฤษของวิชาด้วย (กฎ Lab 5)"""
    out = []
    for c in courses:
        code = c["code"]
        th, en = _norm_th(c.get("name_th")), _norm_en(c.get("name_en"))
        code_re = re.compile(rf"(?<!\d){code}(?!\d)")
        for p in ocr_pages:
            text = p.get("text") or ""
            if not code_re.search(text):
                continue
            primary = (len(th) >= 4 and th in _norm_th(text)) or (len(en) >= 4 and en in _norm_en(text))
            out.append({"code": code, "pdf_page": int(p["page"]), "printed_page": printed_page(text),
                        "kind": "primary" if primary else "other"})
    return sorted(out, key=lambda r: (r["code"], r["pdf_page"]))
