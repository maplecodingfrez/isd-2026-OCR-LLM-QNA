"""Quote the curriculum book for content questions the DB does not hold (PLO, free-elective rule, grading, semester system...).

Build once from the committed OCR text (run from the repo root):
    python Lab7B_Lab8B_ocr_system/src/ocr_system/book_quotes.py
writes Lab7B_Lab8B_ocr_system/runs/<BOOK>/book_quotes.json (topic -> heading, body, pdf_page, printed_page).

At question time quote_answer() only reads that JSON: no model, no DB, the answer is the book's own text with its page.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BOOKS = {"AIT": "ait", "BIT": "bit", "DSBA": "dsba", "IT": "it"}       # runs/<BOOK> folder -> outputs/<book> OCR

# key, label shown in the answer, question regex, question exclude regex
TOPICS = (
    ("plo", "ผลลัพธ์การเรียนรู้ของหลักสูตร",
     r"(?i)\bPLOs?\b|learning\s+outcomes?|ผลลัพธ์การเรียนรู้|ผลการเรียนรู้(?:ที่คาดหวัง|ระดับหลักสูตร|ของหลักสูตร)",
     r"\d{8}|มาตรฐานผลการเรียนรู้|รายวิชา|วิชา(?!การ)\S"),
    ("free_elective", "หมวดวิชาเลือกเสรี",
     r"(?i)(?:(?:วิชา|หมวดวิชา)?เลือกเสรี|free\s+electives?).{0,40}(?:เงื่อนไข|อะไรก็ได้|วิชาไหนก็ได้|คณะอื่น|ข้ามคณะ|ต่างคณะ|นอกคณะ|"
     r"เลือก(?:เรียน|ลง)?(?:จาก)?(?:อะไร|ไหน|ที่ไหน|ยังไง)|ลง(?:อะไร|ไหน|ยังไง)|คืออะไร|หมายถึง|ต้องเป็น|นับ|(?:ไหม|มั้ย|หรือเปล่า|หรือไม่|ป่าว|ปะ)|"
     r"rules?|conditions?|any\s+course|which\s+courses|what\s+(?:is|are|counts)|can\s+i)|(?:any\s+course|which\s+courses?|can\s+i\s+take).{0,30}free\s+electives?|"
     r"(?:เงื่อนไข|กฎ).{0,10}(?:วิชา)?เลือกเสรี",
     r"(?i)\d{8}|ปี\s*\d|ปีไหน|เทอม|ภาค(?:การศึกษา|เรียน)|ตอนปี|กี่หน่วยกิต|หน่วยกิตเท่า|กี่วิชา|\bwhen\b|which\s+(?:year|term|semester)|how\s+many"),
    ("grading", "หลักเกณฑ์การให้ระดับคะแนน (เกรด)",
     r"(?i)(?:ระบบ|เกณฑ์|หลักเกณฑ์|กฎ(?:ระเบียบ)?|การ)(?:การ)?(?:ให้|ตัด|คิด)?(?:เกรด|ระดับคะแนน)|ตัดเกรด|ให้เกรด|เกรด(?:มี)?(?:อะไรบ้าง|กี่ระดับ|แบบไหน|ยังไง)|"
     r"ระดับคะแนน(?:มี)?(?:อะไรบ้าง|กี่ระดับ)|grading|grade\s+(?:scale|system|criteria|policy|levels?)|how\s+(?:are|is)\s+.{0,20}grad(?:ed|ing)",
     r"(?i)\d{8}|เกียรตินิยม|honou?rs?|จบ|สำเร็จการศึกษา|graduat|รีไทร์|พ้นสภาพ|retire|เฉลี่ย|GPA|GPAX|วิชา(?!การ)\S"),
    ("education_system", "ระบบการจัดการศึกษา",
     r"(?i)ระบบการ(?:จัดการ)?ศึกษา|ทวิภาค|ไตรภาค|ระบบ(?:ภาค|เทอม)|(?:ปีหนึ่ง|ปี\s*1|ปีละ|1\s*ปี|หนึ่งปี)(?:การศึกษา)?(?:มี)?(?:กี่|มีกี่)(?:เทอม|ภาค)|"   # "ปีหนึ่ง" arrives as "ปี 1"
     r"กี่(?:เทอม|ภาค(?:การศึกษา)?)(?:ต่อ|ใน)\s*(?:1\s*)?ปี|(?:มี|เปิด)(?:ภาค)?(?:ฤดูร้อน|ซัมเมอร์)\s*(?:ไหม|มั้ย|หรือเปล่า|หรือไม่|ป่าว|ปะ)|"
     r"(?:ภาค)?(?:ฤดูร้อน|ซัมเมอร์)(?:มี|เปิด)?\s*(?:ไหม|มั้ย|หรือเปล่า|หรือไม่|ป่าว|ปะ)|(?:ภาค)?(?:ฤดูร้อน|ซัมเมอร์).{0,10}(?:กี่สัปดาห์|นานเท่า|กี่เดือน)|"
     r"is\s+there\s+(?:a\s+)?summer|summer\s+(?:term|semester|session)|semester\s+system|how\s+many\s+(?:semesters|terms)\s+(?:per|a|in\s+a|each)\s+year",
     r"(?i)\d{8}|วิชา|รหัส|หน่วยกิต|ลงทะเบียน|ปี\s*\d\s*เทอม|ปี\s*\d\s*ภาค|course|credit"),
    ("semester_calendar", "วัน-เวลาในการดำเนินการเรียนการสอน",
     r"(?i)เปิด(?:เทอม|ภาค(?:การศึกษา|เรียน)?)(?:\s*\d)?(?:เดือน|วัน|ตอน|เมื่อ|กี่โมง|ไหน)|ปิด(?:เทอม|ภาค(?:การศึกษา|เรียน)?)|"
     r"(?:เทอม|ภาค(?:การศึกษา|เรียน)?)(?:ที่)?\s*\d?\s*(?:เริ่ม|เปิด|จบ|สิ้นสุด|ปิด)(?:เดือน|ตอน|เมื่อ|วัน)?|"
     r"(?:เทอม|ภาค(?:การศึกษา|เรียน)?).{0,20}(?:เริ่ม|เปิด|จบ|สิ้นสุด|ปิด)(?:เดือน|ตอนไหน|เมื่อไร|เมื่อไหร่|วันไหน)|"
     r"(?:เริ่ม|เปิด)เรียน(?:เดือน|วันไหน|ตอนไหน|เมื่อไร|เมื่อไหร่)|วัน\s*-?\s*เวลา(?:ใน)?(?:การ)?(?:ดำเนินการ)?(?:เรียน|สอน)|"
     r"เรียน(?:วันไหน|วันอะไร|ในเวลาราชการ|นอกเวลา)|ปฏิทินการศึกษา|academic\s+calendar|"
     r"when\s+does\s+(?:the\s+)?(?:first\s+|second\s+)?(?:semester|term)\s+(?:start|begin|end)|semester\s+(?:dates|months)",
     r"(?i)\d{8}|วิชา|รหัส|หน่วยกิต|สหกิจ|ลงทะเบียน|สอบ|course|credit|exam"),
    ("credit_transfer", "การเทียบโอนหน่วยกิต",
     r"(?i)เทียบโอน|โอน(?:ผลการเรียน|หน่วยกิต|รายวิชา)|ลงทะเบียน(?:เรียน)?ข้าม(?:สถาบัน|มหาวิทยาลัย|มหาลัย|มอ)|เรียนข้าม(?:สถาบัน|มหาวิทยาลัย|มหาลัย|มอ)|"
     r"credit\s+transfer|transfer\s+(?:of\s+)?(?:credits?|หน่วยกิต)|cross[-\s]?(?:institution|university)\s+(?:registration|enrol)",   # ask() turns "credits" into หน่วยกิต
     r"\d{8}|โอนย้ายสาขา|ย้ายสาขา|ย้ายคณะ"),
    ("language", "ภาษาที่ใช้",
     r"(?i)(?:เรียน|สอน|จัดการศึกษา|ใช้)(?:เป็น|ด้วย)?ภาษา(?:อะไร|ไหน)|(?:เรียน|สอน|จัดการศึกษา)(?:เป็น|ด้วย)?ภาษา(?:อังกฤษ|ไทย)(?:ทั้งหมด|ล้วน)?\s*(?:ไหม|มั้ย|หรือเปล่า|หรือไม่|ป่าว|ปะ)|"
     r"ภาษาที่ใช้(?:ใน)?(?:การ)?(?:เรียน|สอน|หลักสูตร)?|(?:หลักสูตร)?(?:นานาชาติ|อินเตอร์|อินเตอ)\s*(?:ไหม|มั้ย|หรือเปล่า|หรือไม่|ป่าว|ปะ)|"
     r"language\s+of\s+(?:instruction|teaching)|(?:taught|teach|instruction|classes)\s+in\s+(?:english|thai)|what\s+language|international\s+program(?:me)?\s*\?",
     r"(?i)\d{8}|(?<!สาขา)วิชา(?!การ)|ภาษาอังกฤษ(?:พื้นฐาน|เพื่อ|สำหรับ)|กี่หน่วยกิต|กี่วิชา|หน่วยกิต|course|credit|toeic|ielts"),
    ("coop_timing", "ช่วงเวลาและการจัดเวลาสหกิจศึกษา",
     r"(?i)สหกิจ(?:ศึกษา)?.{0,20}(?:กี่สัปดาห์|กี่เดือน|กี่วัน|นานเท่า|นานแค่ไหน|นานไหม|ระยะเวลา|ช่วงเวลา|ทำงานกี่วัน|ต่อสัปดาห์)|"
     r"(?:ระยะเวลา|ช่วงเวลา)(?:ของ|ใน|การ)?(?:ไป|ฝึก)?สหกิจ|(?:ไป|ออก|ฝึก)?สหกิจ(?:ศึกษา)?(?:ช่วง|ตอน)(?:ไหน|ใด)|(?:ไป|ออก|ฝึก)สหกิจ(?:ศึกษา)?(?:เมื่อไร|เมื่อไหร่)|co-?op(?:erative)?(?:\s+education|\s+program(?:me)?)?.{0,30}(?:how\s+long|duration|weeks|days\s+a\s+week)|"
     r"how\s+long\s+is\s+(?:the\s+)?co-?op",
     r"(?i)\d{8}|ปีไหน|เทอมไหน|ภาค(?:การศึกษา)?ไหน|กี่หน่วยกิต|หน่วยกิต|วิชา(?!การ)\S|which\s+(?:year|term|semester)"),
)
_TOPIC_RX = [(key, label, re.compile(q), re.compile(x)) for key, label, q, x in TOPICS]


def topic_of(question: str) -> tuple[str, str] | None:
    """(key, label) of the one topic the question asks about; none or more than one = None."""
    hits = [(key, label) for key, label, q, x in _TOPIC_RX if q.search(question) and not x.search(question)]
    return hits[0] if len(hits) == 1 else None


def book_of(program_id: str | None) -> str | None:
    """runs/<BOOK> folder from a program_id such as 'DSBA-no-coop' or 'AIT'."""
    m = re.match(r"(AIT|BIT|DSBA|IT)(?![A-Z])", (program_id or "").upper())
    return m.group(1) if m else None


def quote_answer(program_id: str | None, question: str, root: Path = REPO_ROOT) -> tuple[str, list[dict]] | None:
    """Answer text + one row {topic, heading, body, pdf_page, printed_page}; topic not asked / no file / topic missing in this book = None."""
    hit, book = topic_of(question), book_of(program_id)
    if not hit or not book:
        return None
    path = root / "Lab7B_Lab8B_ocr_system" / "runs" / book / "book_quotes.json"
    try:
        quotes = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    q = quotes.get(hit[0])
    if not q or not q.get("body"):
        return None
    body = q["body"]
    if hit[0] == "plo":                                            # one outcome per line, in the answer text that gets copied and on the page
        body = re.sub(r"\s+(?=PLO\s*\d)", "\n", body)
    row = {"topic": hit[0], "heading": q["heading"], "body": body, "pdf_page": q["pdf_page"], "printed_page": q.get("printed_page")}
    return f"{hit[1]} (ตามเล่มหลักสูตร): {body}", [row]


# ---------------- build from OCR text (offline, run once) ----------------

_HEADINGS = {   # topic -> regex on lab8b._section_key(title); free_elective has its own unnumbered rule
    "plo": r"^ผล(?:การเรยนร|ลพธการเรยนร)(?:ทคาดหวง)?$",
    "grading": r"^กฎระเบยบหรอหลกเกณฑในการใหระดบคะแนน",
    "education_system": r"^ระบบการจดการศกษา$",
    "semester_calendar": r"^.{1,3}-?เวลาในการดาเนนการเรยนการสอน$",
    "credit_transfer": r"^การเทยบโอนหนวยกต",
    "language": r"^ภาษาทใช$",
}
_CAPS = {"plo": 2200, "grading": 800, "education_system": 1500, "semester_calendar": 600, "credit_transfer": 800, "language": 400}
_COOP_PARENT, _COOP_CHILDREN = r"^องคประกอบเกยวกบประสบการณภาคสนาม", (r"^ชวงเวลา$", r"^การจดเวลาและตารางสอน$")
_UNCHECKED = re.compile(r"^(?:\[\s*\.?\s*\]|\|\s*\]|\[\s*\|(?!\S)|L[UI]\s|\[\s+\.\])")      # OCR of an empty tick box
_CHECKED = re.compile(r"^(?:\[[ๆทฑ์ีฑ]+\s*\|?\]?\|?|M[1IV]?\]?|MV\]|Vv\]?|v\])\s*")     # OCR of a ticked box
_UNIT = re.compile(r"^(?:วัน|หน่วย|สัปดาห์|ชม|ชั่วโมง|ด้าน)")
_PERSON = re.compile(r"^(?:ศ|รศ|ผศ|อ|ดร|ตร)[\.,]")
_MIXED = re.compile(r"[ก-๏][0-9A-Za-z]+[ก-๏]|[0-9A-Za-z][ก-๏]+[0-9A-Za-z]")
_GIB = re.compile(r"(.)\1\1|[ฝฑฒฌฎฏ].*[ฝฑฒฌฎฏ]")
_RUNHEAD = re.compile(r"^\d{1,3}\s+รายละเอ\S*ยดหล\S*กสูตร$")


def _junk(line: str) -> bool:
    if _RUNHEAD.match(line):
        return True
    toks = line.split()
    if any(_MIXED.search(t) for t in toks):
        return True
    size = sum(len(t) for t in toks) or 1
    if sum(len(t) for t in toks if _GIB.search(t)) / size >= 0.3:
        return True
    return sum(len(t) for t in toks if len(t) >= 4) / size < 0.5


def _successors(num: str) -> set[str]:
    parts = [int(x) for x in num.split(".")]
    return {".".join(map(str, parts[:k] + [parts[k] + 1])) for k in range(len(parts))}


def _body(lab8b, lines, i: int, num: str, cap: int) -> list[tuple[int, str]]:
    """Lines after heading i up to its next sibling/ancestor heading, a new หมวด, a table, or cap characters."""
    out, size, succ = [], 0, _successors(num)
    for pg, ln in lines[i + 1:]:
        h = lab8b._section_heading(ln)
        if h and h[0] in succ and not _PERSON.match(h[2]) and not _UNIT.match(h[2]):
            break
        if re.match(r"^หมวดที่?\s*\d", ln) or re.match(r"^ตาราง", ln):
            break
        if _UNCHECKED.match(ln) or _junk(ln):
            continue
        ln2 = _CHECKED.sub("", ln)
        clean = ln2 if h else lab8b._section_clean(ln2)
        if not clean:
            continue
        if size + len(clean) > cap:
            break
        out.append((pg, clean))
        size += len(clean) + 1
    return out


def _plausible(pdf_page: int, value) -> bool:
    return bool(value) and str(value).isdigit() and 0 <= pdf_page - int(value) <= 15     # front matter is at most 15 pages


def _printed_page(raw: dict, printed: dict, pdf_page: int) -> str | None:
    """Printed page of pdf_page. OCR reads a leading 7 as 1 over whole runs (BIT PDF 77 '12' = 72, IT PDF 73 '12' = 72) and
    consistent_printed accepts such runs, so an implausible value is first retried with that 1 -> 7; otherwise the nearest
    plausible page lends its offset (the IT book renumbers mid-way, so this is only the fallback)."""
    for v in (printed.get(pdf_page), raw.get(pdf_page)):
        if _plausible(pdf_page, v):
            return str(v)
        if v and str(v).startswith("1") and _plausible(pdf_page, "7" + str(v)[1:]):
            return "7" + str(v)[1:]
    for pg in sorted(printed, key=lambda p: (abs(p - pdf_page), p)):
        if _plausible(pg, printed.get(pg)):
            return str(pdf_page - (pg - int(printed[pg])))
    return None


def build_book(book: str) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import citations
    import lab8b_curriculum_db as lab8b
    text = (REPO_ROOT / "outputs" / book / f"{book}_curriculum_ocr.txt").read_text(encoding="utf-8").replace("\r", "")
    marks = list(lab8b._STRUCT_PAGE_RE.finditer(text))
    pages = {int(mk.group(1)): text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)] for i, mk in enumerate(marks)}
    raw = {pg: citations.printed_page(body) for pg, body in pages.items()}
    printed = citations.consistent_printed(raw)
    lines = lab8b._section_lines(text)
    toc = {pg for pg, ln in lines if re.search(r"สารบ[ัญ]*ญ|สารบญ", ln)}
    heads = [(i, h) for i, (pg, ln) in enumerate(lines) if pg not in toc and (h := lab8b._section_heading(ln))]

    def key(title: str) -> str:
        return lab8b._section_key(title.replace("ำ", "ํา"))

    def entry(heading: str, body: list[tuple[int, str]], pdf_page: int) -> dict:
        joined = " ".join(x for _, x in body).replace("ํา", "ำ")
        return {"heading": heading.replace("ํา", "ำ"), "body": joined, "pdf_page": pdf_page, "printed_page": _printed_page(raw, printed, pdf_page)}

    out: dict[str, dict] = {}
    for topic, rx in _HEADINGS.items():
        hit = next(((i, h) for i, h in heads if re.search(rx, key(h[2]))), None)
        if not hit:
            continue
        i, (num, _, title) = hit
        body = _body(lab8b, lines, i, num, _CAPS[topic])
        if topic == "plo":                       # AIT puts a survey summary before the list: start at the first PLO line
            k = next((j for j, (_, x) in enumerate(body) if re.search(r"\bPLO", x)), None)
            body = body[k:] if k else body
        if body:
            out[topic] = entry(f"{num} {title}", body, lines[i][0])
    for i, (pg, ln) in enumerate(lines):         # "ค. หมวดวิชาเลือกเสรี" is not a numbered heading; OCR reads ค. as A.
        if re.match(r"^(?:[คA]\s*[\.,]\s*)?หมวดวิชาเลือกเสรี", ln) and all(w in " ".join(x for _, x in lines[i + 1:i + 3]) for w in ("เลือก", "ไม่น้อยกว่า")):
            body = [(pg, re.sub(r"^[คA]\s*[\.,]\s*", "ค. ", ln).rstrip(" |"))]
            for pg2, ln2 in lines[i + 1:i + 4]:
                if re.match(r"^(?:[ก-ฮA-Za-z]\s*[\.,]\s*หมวด|ความหมายของรหัส|\d+(?:\.\d+)+\s|\*)", ln2):
                    break
                body.append((pg2, ln2))
                if "หน่วยกิต" in ln2:
                    break
            out["free_elective"] = entry("หมวดวิชาเลือกเสรี", body, pg)
            break
    par = next(((i, h) for i, h in heads if re.search(_COOP_PARENT, key(h[2]))), None)
    if par:                                      # only 4.2 ช่วงเวลา and 4.3 การจัดเวลา (4.1 is a table in AIT)
        pi, (pnum, _, ptitle) = par
        body, first = [], None
        for crx in _COOP_CHILDREN:
            ch = next(((i, h) for i, h in heads if i > pi and h[0].startswith(pnum + ".") and re.search(crx, key(h[2]))), None)
            if ch:
                ci, (cnum, _, ctitle) = ch
                body += [(lines[ci][0], f"{cnum} {ctitle}")] + _body(lab8b, lines, ci, cnum, 400)
                first = first or lines[ci][0]
        if body:
            out["coop_timing"] = entry(f"{pnum} {ptitle}", body, first)
    return out


def main() -> None:
    for folder, book in BOOKS.items():
        quotes = build_book(book)
        dest = REPO_ROOT / "Lab7B_Lab8B_ocr_system" / "runs" / folder / "book_quotes.json"
        dest.write_text(json.dumps(quotes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{dest.relative_to(REPO_ROOT).as_posix()}: {len(quotes)} topics: {', '.join(quotes)}")


if __name__ == "__main__":
    main()
