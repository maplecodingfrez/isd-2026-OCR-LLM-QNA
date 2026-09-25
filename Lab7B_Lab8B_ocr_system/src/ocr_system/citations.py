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


HEADING_RE = re.compile(r"ปีที่\s*(\d)\s*ภาค(?:การศึกษา|เรียน)?\s*ที่\s*(\d)")
IMAGE_PAGE_RE = re.compile(r"(\d+)\.(?:jpe?g|png)$", re.I)


def plan_pages(image_names: list[str], md_text: str,
               printed_by_pdf: dict[int, str | None]) -> list[dict]:
    """หน้าตารางแผนของแต่ละเทอม: ส่วนที่ i ของ Markdown (คั่น ---) = ภาพหน้าที่ i เรียงตามเลขหน้า
    ส่วนที่ไม่มีหัวเทอมแต่มีตาราง = ตารางของเทอมก่อนหน้าที่ล้นมาหน้าใหม่; จำนวนไม่ตรงกัน = ไม่คืนอะไร (ไม่เดา)"""
    pages = sorted(int(m.group(1)) for n in image_names if (m := IMAGE_PAGE_RE.search(n)))
    chunks = md_text.split("\n---\n")
    if len(pages) != len(chunks):
        return []
    out: list[dict] = []
    last = None
    for pdf, chunk in zip(pages, chunks):
        terms = [(int(y), int(s)) for y, s in HEADING_RE.findall(chunk)]
        if not terms and last is not None and "<table" in chunk:
            terms = [last]
        for y, s in dict.fromkeys(terms):
            out.append({"year": y, "semester": s, "pdf_page": pdf, "printed_page": printed_by_pdf.get(pdf)})
        if terms:
            last = terms[-1]
    return out


def consistent_printed(printed_by_pdf: dict[int, str | None]) -> dict[int, str | None]:
    """เก็บเลขหน้าที่พิมพ์เฉพาะหน้าที่ต่อเนื่องกับหน้าข้างเคียง (PDF-1 พิมพ์ N-1 หรือ PDF+1 พิมพ์ N+1)
    Tesseract อ่านเลขหน้าผิดบางหน้า (IT PDF 42 อ่านเป็น "27" แทน 37) — ไม่ต่อเนื่อง = ไม่แสดง (อ้างแค่ PDF)
    เทียบกับหน้าข้างเคียง ไม่ใช่ระยะห่างเดียวทั้งเล่ม เพราะบางส่วนของเล่มนับเลขหน้าใหม่ (IT PDF 6-10 = 1-5)"""
    def num(pdf: int) -> int | None:
        p = printed_by_pdf.get(pdf)
        return int(p) if p else None

    out: dict[int, str | None] = {}
    for pdf, p in printed_by_pdf.items():
        n = num(pdf)
        ok = n is not None and (num(pdf - 1) == n - 1 or num(pdf + 1) == n + 1)
        out[pdf] = p if ok else None
    return out
