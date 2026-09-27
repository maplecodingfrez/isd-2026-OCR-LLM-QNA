"""อ้างอิงหน้าในคำตอบ (ระดับ 1–2)

กฎเชิงกำหนดล้วน ไม่ใช้ LLM ไม่ใช้เฉลย: หน้าไหนมีรหัสวิชา (จาก OCR ทั้งเล่มของ Tesseract) และหน้าไหนเป็น
ตารางแผนของเทอมใด (จากภาพหน้าที่ Lab 7B อ่าน) — หาไม่เจอ = ไม่อ้างอิง ห้ามเดาเลขหน้า"""
from __future__ import annotations

import re
import sqlite3

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


# หน้าคำอธิบายรายวิชามีบรรทัดวิชาบังคับก่อนของแต่ละวิชา — ตารางเทียบหลักสูตรในภาคผนวก (เช่น DSBA PDF 353) ไม่มี
DESCRIPTION_RE = re.compile(r"วิชาบังคับก่อน|prerequisite", re.I)


def course_pages(ocr_pages: list[dict], courses: list[dict]) -> list[dict]:
    """หน้า (PDF) ที่มีรหัสวิชาแต่ละตัว — primary เมื่อหน้านั้นมีชื่อไทยหรืออังกฤษของวิชาด้วย (กฎ Lab 5);
    primary ที่เป็นหน้าคำอธิบายรายวิชา = description (ให้ขึ้นก่อน ไม่ถูกตัดตอนจำกัด MAX_CITED)"""
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
            kind = ("description" if DESCRIPTION_RE.search(text) else "primary") if primary else "other"
            out.append({"code": code, "pdf_page": int(p["page"]), "printed_page": printed_page(text), "kind": kind})
    return sorted(out, key=lambda r: (r["code"], r["pdf_page"]))


HEADING_RE = re.compile(r"ปีที่\s*(\d)\s*ภาค(?:การศึกษา|เรียน)?\s*ที่\s*(\d)")
IMAGE_PAGE_RE = re.compile(r"(\d+)\.(?:jpe?g|png)$", re.I)


def _confirmed(chunk: str, terms: list[tuple[int, int]], book_text: str) -> bool:
    """หน้าเล่มยืนยันว่าเป็นตารางของเทอมนี้: หัวเทอมตรง หรือ (ไม่มีหัวเทอม) รหัสวิชาตรง >= ครึ่งหนึ่ง"""
    book_terms = {(int(y), int(s)) for y, s in HEADING_RE.findall(book_text)}
    if book_terms:
        return bool(book_terms & set(terms))
    codes = set(re.findall(r"(?<!\d)\d{8}(?!\d)", chunk))
    return bool(codes) and len(codes & set(re.findall(r"(?<!\d)\d{8}(?!\d)", book_text))) * 2 >= len(codes)


def plan_pages(image_names: list[str], md_text: str,
               printed_by_pdf: dict[int, str | None],
               book_text_by_pdf: dict[int, str] | None = None) -> list[dict]:
    """หน้าตารางแผนของแต่ละเทอม: ส่วนที่ i ของ Markdown (คั่น ---) = ภาพหน้าที่ i เรียงตามเลขหน้า
    ส่วนที่ไม่มีหัวเทอมแต่มีตาราง = ตารางของเทอมก่อนหน้าที่ล้นมาหน้าใหม่; จำนวนไม่ตรงกัน = ไม่คืนอะไร (ไม่เดา)
    เลขในชื่อไฟล์ภาพไม่จำเป็นต้องเป็นเลขหน้า PDF ของเล่ม (DSBA coop: DSBA_28.png = PDF 30) — จึงต้องยืนยันกับ
    OCR ทั้งเล่มของหน้านั้น (book_text_by_pdf): มีหัวเทอม → ต้องมีเทอมเดียวกับที่ VLM อ่าน; ไม่มีหัวเทอม (Tesseract
    อ่านไม่ออก เช่น AIT) → รหัสวิชาในตารางของหน้านั้นต้องอยู่ในหน้าเล่มอย่างน้อยครึ่งหนึ่ง; ยืนยันไม่ได้ = ไม่อ้าง
    (และหน้าต่อเนื่องของเทอมนั้น)"""
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
        if terms and book_text_by_pdf is not None and not _confirmed(chunk, terms, book_text_by_pdf.get(pdf, "")):
            last = None
            continue
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


CODE_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")
YEAR_SQL_RE = re.compile(r"\byear\s*=\s*'?(\d)'?", re.I)
SEM_SQL_RE = re.compile(r"\bsemester\s*=\s*'?(\d)'?", re.I)
# ตัวกรองเทอมแบบปฏิเสธ ("ไม่อยู่ในเทอม 1/1") — หน้าตารางของเทอมนั้นไม่ใช่ที่มาของคำตอบ
NEGATED_SQL_RE = re.compile(r"\bNOT\s+IN\b|\bEXCEPT\b|!=|<>", re.I)


def load_lookup(conn: sqlite3.Connection):
    """(หน้าต่อรหัสวิชา, หน้าต่อเทอม) จากตาราง course_page — ไม่มีตาราง = None (ตอบได้ตามปกติ ไม่อ้างอิง)"""
    try:
        rows = conn.execute("SELECT code, pdf_page, printed_page, kind FROM course_page "
                            "ORDER BY code, pdf_page").fetchall()
        term_rows = conn.execute("SELECT year, semester, pdf_page, printed_page FROM term_page "
                                 "ORDER BY year, semester, pdf_page").fetchall()
    except sqlite3.OperationalError:
        return None
    by_kind: dict[str, dict[str, list]] = {"plan": {}, "description": {}, "primary": {}, "other": {}}
    for code, pdf, printed, kind in rows:
        by_kind[kind].setdefault(code, []).append((pdf, printed))
    # หน้าคำอธิบายรายวิชาอยู่หลังตารางแผน (มคอ.2 หมวด 3.1.5 ต่อจาก 3.1.4) — หน้าก่อนนั้นที่มีคำว่าวิชาบังคับก่อน
    # (เช่น หน้าโครงสร้างหลักสูตร) ให้อยู่ท้าย
    last_plan = max((r[2] for r in term_rows), default=0)
    course: dict[str, list] = {}
    for code in {r[0] for r in rows}:
        desc = sorted(by_kind["description"].get(code, []), key=lambda p: (p[0] <= last_plan, p[0]))
        pages = by_kind["plan"].get(code, []) + desc + by_kind["primary"].get(code, [])
        course[code] = pages or by_kind["other"].get(code, [])
    term: dict[tuple[int, int], list] = {}
    for y, s, pdf, printed in term_rows:
        term.setdefault((y, s), []).append((pdf, printed))
    return course, term


def citations_for(rows: list[dict], sql: str | None, lookup) -> list[dict]:
    """หน้าอ้างอิงของคำตอบ: หน้าตารางแผนของเทอมที่ SQL กรอง (year= และ semester=) ก่อน แล้วหน้าของรหัสวิชา
    ที่อยู่ใน SQL หรือในแถวผลลัพธ์ — ไม่เกิน MAX_CITED หน้า; ไม่มีข้อมูล = [] (ไม่เดา)"""
    course, term = lookup
    cited: list[tuple[int, str | None]] = []

    def add(pages):
        for p in pages:
            if p not in cited:
                cited.append(p)

    sql = sql or ""
    y, s = YEAR_SQL_RE.search(sql), SEM_SQL_RE.search(sql)
    if y and s and not NEGATED_SQL_RE.search(sql):
        add(term.get((int(y.group(1)), int(s.group(1))), []))
    codes = CODE_RE.findall(sql)
    for r in rows:
        for v in r.values():
            codes += CODE_RE.findall(str(v))
    for code in dict.fromkeys(codes):
        add(course.get(code, []))
    return [{"pdf_page": pdf, "printed_page": printed} for pdf, printed in cited[:MAX_CITED]]


def format_citation(cites: list[dict]) -> str:
    """ "(อ้างอิง: เล่มหลักสูตร หน้า 33 (PDF 38), PDF 23)" — ไม่รู้เลขหน้าที่พิมพ์ = แสดงแค่ PDF"""
    if not cites:
        return ""
    parts = [f"หน้า {c['printed_page']} (PDF {c['pdf_page']})" if c["printed_page"] else f"PDF {c['pdf_page']}"
             for c in cites]
    return f"(อ้างอิง: เล่มหลักสูตร {', '.join(parts)})"
