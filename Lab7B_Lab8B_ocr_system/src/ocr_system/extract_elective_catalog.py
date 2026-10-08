"""ดึง "กลุ่มวิชาเลือก" (elective group) จากหน้า catalog ("3.1.3 รายวิชา") ของเล่มหลักสูตร

คนละส่วนกับ Lab7B/8B ที่ดึงเฉพาะตาราง "แผนการศึกษา" (3.1.4) เท่านั้น — วิชาเลือกในตารางแผนเขียน
เป็นรหัส wildcard (เช่น "06036xxx") เพราะตัวเลือกจริงอยู่คนละหน้า (หน้า catalog) ต่างหาก
สคริปต์นี้ดึงหน้า catalog มาแยกเป็นรายวิชาต่อกลุ่ม ไม่ยุ่งกับ pipeline VLM เดิม — ตาราง catalog
เป็นข้อความสะอาด อ่านจาก OCR ข้อความเต็มเล่มที่มีอยู่แล้ว (`outputs/{program}/{program}_curriculum_ocr.txt`
จาก Lab4-6) ได้ตรงๆ ด้วย regex ไม่ต้องเรียกโมเดลซ้ำ

ใช้ (path ตัวอย่างอิงโครงสร้างโฟลเดอร์ใหม่หลังจัดระเบียบ 2026-09-16 — ดู runs/<CURRICULUM>/):
    python -m ocr_system.extract_elective_catalog \
        --text "../outputs/bit/bit_curriculum_ocr.txt" --start-page 24 --end-page 25 \
        -o runs/BIT/electives.json

GE image-OCR candidate (review before replacing the live catalog):
    python extract_elective_catalog.py --ocr-json <pipeline_ocr.json> --edition 2566 -o <candidate.json>
The --ocr-json path never reads PDF text or ground truth. --pdf remains an explicit
text-layer reference mode; OCR errors are not silently repaired from that reference.
"""

import argparse
import json
import re
from pathlib import Path

PAGE_RE = re.compile(r"^--- Page (\d+) ---\s*$", re.MULTILINE)
GROUP_RE = re.compile(r"^กลุ่มวิชาที่\s*(\d+)\s*[:：]\s*(.+)$")
# บางเล่มไม่แบ่งย่อยแบบ "กลุ่มวิชาที่ 1-4" — AIT/IT มีกลุ่มเดียวแบนๆ "N) กลุ่มวิชาเลือก... N หน่วยกิต"
# (ไม่มีเลข "ที่ N" กำกับ), DSBA มีหลายกลุ่มย่อยขึ้นต้นด้วย "-" เช่น "- กลุ่มวิทยาการข้อมูล 12 หน่วยกิต"
# — รองรับทั้ง 3 แบบด้วย pattern เดียว (prefix "-" หรือ "N)" หรือไม่มีเลยก็ได้) เรียง group_no ตาม
# ลำดับที่เจอเอง หัวข้อระดับบนที่ไม่มีวิชาเลือกได้จริง (แค่รวมกลุ่มย่อยไว้ข้างใน เช่น DSBA
# "3) กลุ่มวิชาชีพเฉพาะด้าน 12 หน่วยกิต" ตามด้วย "-" กลุ่มย่อยทันที ไม่มีวิชาของตัวเอง) จะกลายเป็น
# กลุ่มว่าง (0 วิชา) เพราะ flush ทันทีที่กลุ่มย่อยถัดมาสร้างกลุ่มใหม่ — กรองทิ้งท้ายฟังก์ชันอยู่แล้ว
SECTION_RE = re.compile(r"^(?:-|\d+\))?\s*(กลุ่ม.+?)\s+\d+\s*หน่วยกิต\s*$")
# หน่วยกิตชั่วโมงต่อสัปดาห์อาจเป็นเลข 2 หลัก (เช่น สหกิจศึกษา "6(0-35-0)") ห้ามจำกัดแค่ 1 หลัก
# บางเล่ม (AIT) เว้นวรรคก่อนวงเล็บ "3 (3-0-6)" บางเล่ม (BIT) ไม่เว้น "3(3-0-6)" — รับทั้งคู่
# ตัวคั่นก่อนหน่วยกิตใช้ \s* (ไม่ใช่ \s+) เพราะบาง OCR มีอักขระแปลกปลอมแทรกก่อนตัวเลขหน่วยกิต
# (เจอจริงกับ DSBA "06026225": "...ทางการ »3 (2-2-5)" — ถ้าบังคับ \s+ ตรงหน้าตัวเลขเป๊ะๆ
# ตัว "»" จะกันไม่ให้ match เลย ทั้งที่ชื่อวิชา/หน่วยกิตอ่านออกชัดเจน)
CODE_RE = re.compile(r"^(\d{8})\)?\s+(.+?)\s*(\d+\s*\(\d+-\d+-\d+\))\s*$")
# "วท.บ" ไม่ใช่ "วท.บ." เสมอไป — DSBA เขียน "วท.บ (วิทยาการข้อมูล...)" ไม่มีจุด ตัดจุดออกกันพลาด
# "นักศึกษา..." คือประโยคอธิบายกติกาเลือกวิชา (เจอซ้ำๆ ทั้ง 3 เล่ม เช่น "นักศึกษาเลือกลงทะเบียน...",
# "นักศึกษาสามารถเลือกเรียน...") ไม่ใช่ส่วนของชื่อวิชา ต้องข้ามไปด้วย ไม่งั้นหลุดไปต่อท้าย name_en
# ของวิชาสุดท้ายในกลุ่มก่อนหน้า (เจอจริงกับ DSBA "06026258")
SKIP_PREFIXES = ("รหัสวิชา", "วท.บ", "คณะ", "---", "นักศึกษา")
# หยุดทันทีที่เจอ "หัวข้อ" ของโซนที่ไม่ใช่วิชาเลือกแบบที่ wildcard อื่นชี้ถึง (เลือกเสรี/สหกิจศึกษา/
# โมดูลอาชีพแนะนำของ IT ซึ่งเป็นแค่ subset ของวิชาที่ดึงมาแล้วซ้ำ ไม่ใช่วิชาใหม่)
# ต้อง anchor ที่ต้นบรรทัด (เว้นได้แค่ prefix สั้นๆ แบบ "ก." "A," "-") ห้ามใช้ substring เปล่าๆ
# เพราะเคยเจอ false positive จริง — DSBA มีประโยคบรรยาย "...ไม่เข้าร่วมโครงการสหกิจศึกษา" ที่มีคำว่า
# "สหกิจศึกษา" ปนอยู่กลางประโยค ทำให้ตัดจบเร็วเกินไปก่อนถึงกลุ่มวิชาเลือกจริงที่อยู่ถัดไป
STOP_HEADER_RE = re.compile(
    r"^(?:[ก-ฮ0-9A-Za-z][.,]\s*)?-?\s*"
    r"(หมวดวิชาเลือกเสรี|หมวดวิชาสหกิจศึกษา|สหกิจศึกษา|โมดูลอาชีพ)")


def extract_page_range(text: str, start_page: int, end_page: int) -> str:
    """ตัดข้อความเฉพาะช่วงหน้า [start_page, end_page] จากไฟล์ OCR เต็มเล่ม (marker "--- Page N ---")"""
    spans = {int(m.group(1)): m for m in PAGE_RE.finditer(text)}
    if start_page not in spans:
        raise ValueError(f"ไม่เจอ marker หน้า {start_page} ในไฟล์นี้")
    start = spans[start_page].end()
    after = end_page + 1
    end = spans[after].start() if after in spans else len(text)
    return text[start:end]


def parse_groups(block: str) -> list[dict]:
    """แยกข้อความ catalog เป็นลิสต์กลุ่มวิชา แต่ละกลุ่มมีรายวิชา (code, name_th, name_en, credits)

    รับมือ 2 เคส OCR ที่เจอจริง: (1) ชื่อกลุ่มภาษาอังกฤษวงเล็บ wrap ขึ้นบรรทัดใหม่
    เช่น "ระบบระดับองค์กร (Enterprise System, Business Process\\nImprovement)"
    (2) ชื่อวิชาภาษาอังกฤษ wrap หลายบรรทัด เช่น "INTRODUCTION TO COMPUTER NETWORK AND\\nCYBERSECURITY"
    """
    groups: list[dict] = []
    current: dict | None = None
    pending_group_header: tuple[int, str] | None = None
    pending_course: dict | None = None

    def flush_course() -> None:
        nonlocal pending_course
        if pending_course and current is not None:
            current["courses"].append(pending_course)
        pending_course = None

    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(SKIP_PREFIXES) or line.startswith("มคอ.") or re.fullmatch(r"\d{1,3}", line):
            continue
        if STOP_HEADER_RE.match(line):
            break  # หมดโซนวิชาเลือกแล้ว (ต่อด้วยหมวดวิชาเลือกเสรี/สหกิจศึกษา ไม่ใช่ของกลุ่มนี้)

        m = GROUP_RE.match(line)
        if m:
            flush_course()
            name = m.group(2)
            if "(" in name and ")" not in name:
                pending_group_header = (int(m.group(1)), name)
                continue
            paren = re.search(r"\(([^)]*)\)\s*$", name)
            name_th = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
            current = {"group_no": int(m.group(1)), "name_th": name_th,
                       "name_en": paren.group(1).strip() if paren else None,
                       "courses": []}
            groups.append(current)
            continue

        if pending_group_header:
            no, partial = pending_group_header
            full = partial + " " + line
            close = full.find(")")
            name_th = re.sub(r"\s*\(.*$", "", full).strip()
            name_en = full[full.find("(") + 1:close].strip() if close != -1 else None
            current = {"group_no": no, "name_th": name_th, "name_en": name_en, "courses": []}
            groups.append(current)
            pending_group_header = None
            continue

        # กลุ่มไม่มีเลข "ที่ N" กำกับ (AIT: กลุ่มเดียว, DSBA: หลายกลุ่มขึ้นต้น "-") — สร้างกลุ่มใหม่
        # ทุกครั้งที่เจอหัวข้อแบบนี้ เรียง group_no ตามลำดับที่เจอเอง
        sm = SECTION_RE.match(line)
        if sm:
            flush_course()
            current = {"group_no": len(groups) + 1, "name_th": sm.group(1).strip(),
                       "name_en": None, "courses": []}
            groups.append(current)
            continue

        cm = CODE_RE.match(line)
        if cm:
            flush_course()
            name_th = re.sub(r"[»«|]+\s*$", "", cm.group(2)).strip()  # ล้างอักขระ OCR แปลกปลอมท้ายชื่อ
            pending_course = {"code": cm.group(1), "name_th": name_th,
                               "name_en": None, "credits": cm.group(3)}
            continue

        if pending_course is not None:
            # ชื่อไทยบางวิชาตัดขึ้นบรรทัดใหม่กลางคำ (เจอจริงกับ DSBA 06026225) — ถ้าบรรทัดถัดมา
            # มีอักษรไทยและยังไม่เจอชื่ออังกฤษเลย ถือว่าเป็นส่วนต่อของชื่อไทย ต่อแบบไม่เว้นวรรค
            # (คำเดียวกันถูกตัดพอดี) แทนที่จะไปเป็นชื่ออังกฤษผิดๆ
            if pending_course["name_en"] is None and re.search(r"[ก-๙]", line):
                pending_course["name_th"] += line
            elif pending_course["name_en"] is None:
                pending_course["name_en"] = line
            else:
                pending_course["name_en"] += " " + line
            continue

    flush_course()
    # กลุ่มจริงต้องมีวิชาอย่างน้อย 1 วิชาเสมอ — กลุ่มว่างมาจากได้ 2 ทาง: (1) หัวข้อปลอม เช่น
    # ประโยคบรรยายที่ตัดขึ้นบรรทัดใหม่พอดีจนหน้าตาเหมือนหัวข้อกลุ่ม (เจอจริงกับ DSBA) (2) หัวข้อ
    # หมวดใหญ่ที่ไม่มีวิชาเลือกได้ตรงๆ ของตัวเอง แค่รวมกลุ่มย่อยไว้ข้างใน (เช่น DSBA
    # "3) กลุ่มวิชาชีพเฉพาะด้าน" ตามด้วย "-" กลุ่มย่อยทันที) — กรองทิ้งแล้วเรียงเลขกลุ่มใหม่ให้
    # ต่อเนื่อง 1..N (ไม่งั้นจะมีรอยขาดเช่น 2,3,4,6 จากกลุ่มว่างที่ถูกกรองไปแล้ว)
    kept = [g for g in groups if g["courses"]]
    for i, g in enumerate(kept, start=1):
        g["group_no"] = i
    return kept


# ---------- หมวดวิชาศึกษาทั่วไป (GE) จาก PDF ที่มี text layer (เช่น GE66_Th_Ed240501.pdf) ----------
# ฟอนต์ของไฟล์นี้ใช้อักขระ Private Use (U+F7xx) แทนวรรณยุกต์/สระที่ลอยต่ำ — ตารางนี้หามาจากการเทียบกับ GT เดิม + บริบทของคำ
# (เช่น U+F70B = ไม้โท: "ดาน" = ด้าน, "ฟน" = ฟื้น, "ฝก" = ฝึก)
PUA_TO_THAI = {"": "่", "": "้", "": "์", "": "์", "": "ั",
               "": "็", "": "ิ", "": "ึ", "": "ื", "": "้",
               "": "่"}
_UPPER_VOWEL = "ั็ิีึื"          # ั ็ ิ ี ึ ื
_TONE = "่้๊๋์"                      # ่ ้ ๊ ๋ ์
_CLUSTER_REPEAT = re.compile(rf"((?:[{_UPPER_VOWEL}]?[{_TONE}]|[{_UPPER_VOWEL}]))\1+")   # "ั้ั้" → "ั้", "ัั" → "ั"


def fix_pua(text: str) -> str:
    """แปลงอักขระ Private Use เป็นวรรณยุกต์/สระจริง แล้วตัดเครื่องหมายที่ซ้ำติดกัน (มีซ้ำใน PDF จริง เช่น "ขั้ั้น")"""
    return _CLUSTER_REPEAT.sub(r"\1", "".join(PUA_TO_THAI.get(c, c) for c in text))


_GE_CREDIT = re.compile(r"^(\d+)\s*\((\d+)-(\d+)-(\d+)\)\s*$")
_GE_CODE = re.compile(r"^\*{0,2}(9064\d{4})$")      # "*" = ประเมินผลแบบ ผ่าน/ไม่ผ่าน (S/U), "**" = วิชาบังคับก่อนที่ไม่นับหน่วยกิต
GE_GROUP_NAMES = {1: ("กลุ่มทักษะส่งเสริมอัตลักษณ์สถาบันฯ", "KMITL IDENTITY SKILLS"),
                  2: ("กลุ่มทักษะบุคคลและส่งเสริมวิชาชีพ", "PERSONAL AND PROFESSIONAL SKILLS"),
                  3: ("กลุ่มทักษะการจัดการและภาวะความเป็นผู้นำ", "MANAGEMENT AND LEADERSHIP SKILLS"),
                  4: ("กลุ่มทักษะภาษาและการสื่อสาร", "LANGUAGE AND COMMUNICATION SKILLS"),
                  # ภาคผนวก ฉ: รหัสสำหรับ "เทียบโอน" จากการศึกษานอกระบบ/สะสมหน่วยกิต (1–2 หน่วยกิต) ไม่ใช่วิชาเลือกที่ลงเรียนปกติ
                  5: ("กลุ่มทักษะเพื่อการเรียนรู้ตลอดชีวิต (เพื่อการเทียบโอน)", "LIFE-LONG LEARNING SKILLS (CREDIT TRANSFER)")}


def parse_ge_pdf(pdf_path) -> list[dict]:
    """รายวิชาของ GE จาก PDF: แต่ละวิชาเป็นบรรทัด รหัส / ชื่อไทย / ชื่ออังกฤษ (หลายบรรทัดได้) / หน่วยกิต "n (a-b-c)"
    กลุ่มดูจากรหัสตัวที่ 5 (1 อัตลักษณ์ 2 บุคคลและวิชาชีพ 3 การจัดการและผู้นำ 4 ภาษาและการสื่อสาร); เจอรหัสซ้ำ = เก็บครั้งแรก"""
    import pymupdf
    courses: dict[str, dict] = {}
    for pno, page in enumerate(pymupdf.open(pdf_path), start=1):
        lines = [fix_pua(l.strip()) for l in page.get_text().split("\n") if l.strip()]
        i = 0
        while i < len(lines):
            m = _GE_CODE.match(lines[i])
            if m:
                block, j = [], i + 1
                while j < len(lines) and not _GE_CODE.match(lines[j]) and not _GE_CREDIT.match(lines[j]) and j - i < 8:
                    block.append(lines[j])
                    j += 1
                if j < len(lines) and _GE_CREDIT.match(lines[j]) and block:
                    code = m.group(1)
                    courses.setdefault(code, {
                        "code": code, "name_th": block[0], "name_en": " ".join(block[1:]),
                        "credits": int(_GE_CREDIT.match(lines[j]).group(1)), "credit_text": lines[j],
                        "group": int(code[4]), "graded_su": lines[i].startswith("*"), "page": pno})
                    i = j
            i += 1
    return sorted(courses.values(), key=lambda c: c["code"])


def parse_ge_ocr(pages: list[dict]) -> list[dict]:
    """Read GE catalog rows from image OCR only; keep errors visible, never fill from PDF text/GT.

    Require an exact eight-digit code, Thai title, English title and complete
    credit structure. Conflicting duplicate records are excluded for review.
    """
    from html import unescape

    header = re.compile(r"^\s*(\*{0,2})(9064\d{4})(?:\s+(.+))?$")
    # A malformed next code must still terminate this row; do not borrow its credit.
    boundary = re.compile(r"^\*{0,2}9[0-9A-Za-z)]{6,10}(?:\s|$)")
    credit = re.compile(r"(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*\)")
    english = re.compile(r"^[A-Za-z][A-Za-z0-9 &'(),./:+@%!?=\[\]#-]*$")

    def components(parts):
        """Reorder observed fields only; never repair names, codes or digits."""
        names_th, names_en, hours_found = [], [], []
        separate_english = any(english.fullmatch(credit.sub("", p).strip()) for p in parts)
        for part in parts:
            hours_found.extend(credit.findall(part))
            name = credit.sub("", part).strip()
            if not name:
                continue
            thai = list(re.finditer(r"[ก-๙]", name))
            if thai:
                if names_en:             # Footer/description, not a title continuation.
                    # A credit in this line belongs to another field/row: refuse.
                    if credit.search(part):
                        return None
                    break
                # Typhoon sometimes puts Thai and English on the same line/cell.
                # Split after the final Thai character; preserve embedded DNA etc.
                start_en = re.search(r"(?<!\S)[A-Za-z]", name[thai[-1].end():])
                if start_en and not separate_english:
                    split = thai[-1].end() + start_en.start()
                    # Multiple bilingual titles or English preceding Thai indicate
                    # shifted/merged rows. Do not assign a previous row's title.
                    prefix = name[:split]
                    if re.search(r"[A-Za-z]", prefix[:thai[0].start()]) or re.search(
                            r"[A-Za-z]+\s+[A-Za-z]+", prefix):
                        return None
                    names_th.append(name[:split].strip())
                    candidate_en = name[split:].strip()
                    if not english.fullmatch(candidate_en):
                        return None
                    names_en.append(candidate_en)
                else:
                    names_th.append(name)
            elif english.fullmatch(name):
                names_en.append(name)
            else:
                break
        if not names_th or not names_en or len(hours_found) != 1:
            return None
        return " ".join(names_th), " ".join(names_en), tuple(map(int, hours_found[0]))

    courses, conflicts = {}, set()
    for page in sorted(pages, key=lambda p: int(p["page"])):
        text = unescape(page.get("text", ""))
        # These tags can incorrectly wrap credits, not just printed page numbers.
        text = re.sub(r"</?page_number\b[^>]*>", "", text, flags=re.I)
        if re.search(r"<table\b", text, flags=re.I):
            # Reuse the existing Markdown table reader; this is format conversion,
            # not name/credit repair. Incomplete rows never become course records.
            from code_from_book import _cells
            converted = []
            for table_html in re.findall(r"<table\b[^>]*>(.*?)(?:</table>|(?=<table\b)|$)", text, flags=re.S | re.I):
                pending = None
                for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table_html, flags=re.S | re.I):
                    tagged_cells = _cells(row_html)
                    cells = [unescape(value).strip() for _, value in tagged_cells]
                    if not cells:
                        pending = None
                        continue
                    own_code = _GE_CODE.fullmatch(cells[0])
                    parts = [part.strip() for cell in cells[1:] for part in cell.splitlines() if part.strip()]
                    if own_code:
                        code = cells[0]
                        fields = components(parts)
                        pending = (code, parts, bool(re.search(
                            r"rowspan\s*=\s*['\"]?2\b", tagged_cells[0][0], re.I))) if not fields else None
                    elif pending:
                        code, previous, explicit_span = pending
                        pending = None
                        # A continuation must be marked by rowspan/colspan and
                        # contain only English/credit, not the next Thai title.
                        colspan = any(re.search(r"colspan\s*=\s*['\"]?[23]\b", attrs, re.I)
                                      for attrs, _ in tagged_cells)
                        continuation = [part.strip() for cell in cells for part in cell.splitlines() if part.strip()]
                        if not (explicit_span or colspan) or any(re.search(r"[ก-๙]", p) for p in continuation):
                            continue
                        fields = components([*previous, *continuation])
                    else:
                        continue
                    if fields:
                        th, en, hours = fields
                        total, lecture, practice, study = hours
                        converted.extend([f"{code} {th} {total} ({lecture}-{practice}-{study})", en])
            text = "\n".join(converted)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            match = header.match(line)
            if not match or int(match[2][4]) not in GE_GROUP_NAMES:
                continue
            block = [match[3] or ""]
            for following in lines[i + 1:i + 8]:
                if boundary.match(following):
                    break
                block.append(following)
            fields = components(block)
            if fields is None:
                continue
            name_th, name_en, (total, lecture, practice, study) = fields
            if total > 12 or any(h > 99 for h in (lecture, practice, study)):
                continue
            row = {"code": match[2], "name_th": name_th, "name_en": name_en,
                   "credits": total, "credit_text": f"{total} ({lecture}-{practice}-{study})",
                   "group": int(match[2][4]), "graded_su": bool(match[1]), "page": int(page["page"])}
            previous = courses.get(row["code"])
            if previous and any(previous[key] != row[key] for key in ("name_th", "name_en", "credits", "credit_text")):
                conflicts.add(row["code"])
            else:
                courses.setdefault(row["code"], row)
    return [courses[code] for code in sorted(courses) if code not in conflicts]


def build_ge_catalog(pdf_path, edition: str, *, ocr_json=None) -> dict:
    """รูปแบบเดียวกับ electives.json (ใช้ load-electives เดิมได้) — plan_slot ชื่อใหม่ จึงไม่ลบแคตตาล็อกวิชาเลือกเดิมของหลักสูตร"""
    if ocr_json is not None:
        payload = json.loads(Path(ocr_json).read_text(encoding="utf-8"))
        if not payload.get("engine") or not isinstance(payload.get("pages"), list):
            raise ValueError("GE OCR JSON requires engine and pages")
        courses = parse_ge_ocr(payload["pages"])
        source = f"{Path(ocr_json).name} {payload['engine']} OCR (เลขหน้าเป็นหน้า PDF)"
    else:
        courses = parse_ge_pdf(pdf_path)
        source = f"{Path(pdf_path).name} PDF text layer (เลขหน้าเป็นหน้า PDF)"
    groups = [{"group_no": g, "name_th": GE_GROUP_NAMES[g][0], "name_en": GE_GROUP_NAMES[g][1],
               "courses": [{"code": c["code"], "name_th": c["name_th"], "name_en": c["name_en"],
                            "credits": c["credit_text"], "graded_su": c["graded_su"], "page": c["page"]}
                           for c in courses if c["group"] == g]} for g in GE_GROUP_NAMES]
    return {"program": "GE", "source": source,
            "plan_slot": f"หมวดวิชาศึกษาทั่วไป ฉบับปรับปรุง พ.ศ. {edition}",
            "credits_required": 24, "groups": groups}


def main() -> None:
    parser = argparse.ArgumentParser()
    ge_input = parser.add_mutually_exclusive_group()
    ge_input.add_argument("--pdf", help="โหมด GE จาก PDF text layer (ใช้คู่กับ --edition)")
    ge_input.add_argument("--ocr-json", help="โหมด GE จาก OCR JSON ของ pipeline เดิม ไม่อ่าน PDF text layer (ใช้คู่กับ --edition)")
    parser.add_argument("--edition", help="ปีฉบับของ GE เช่น 2566 (ใช้กับ --pdf)")
    parser.add_argument("--text", help="ไฟล์ OCR เต็มเล่ม (มี marker '--- Page N ---')")
    parser.add_argument("--start-page", type=int)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--program", help="เช่น BIT")
    parser.add_argument("--plan-slot",
                        help="ชื่อช่องในตารางแผนที่ wildcard นี้แทนอยู่ เช่น "
                             "'วิชาเลือกทางเทคโนโลยีสารสนเทศทางธุรกิจ 1/2 (ปี 4/2, รหัส 06036xxx)'")
    parser.add_argument("--credits-required", type=int)
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    if args.pdf or args.ocr_json:                           # GE: choose one explicit source
        if not args.edition:
            parser.error("--pdf/--ocr-json ต้องมี --edition")
        result = build_ge_catalog(args.pdf, args.edition, ocr_json=args.ocr_json)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  พบ {sum(len(g['courses']) for g in result['groups'])} วิชา ใน {len(result['groups'])} กลุ่ม — เขียน {out}")
        return
    if any(getattr(args, a) is None for a in ("text", "start_page", "end_page", "program", "plan_slot", "credits_required")):
        parser.error("โหมด OCR ข้อความต้องมี --text --start-page --end-page --program --plan-slot --credits-required")

    text = Path(args.text).read_text(encoding="utf-8")
    block = extract_page_range(text, args.start_page, args.end_page)
    groups = parse_groups(block)

    n_courses = sum(len(g["courses"]) for g in groups)
    result = {
        "program": args.program,
        "source": f"{args.text} PDF หน้า {args.start_page}-{args.end_page}",   # เลขหน้า PDF (marker --- Page N ---) ไม่ใช่เลขที่พิมพ์
        "plan_slot": args.plan_slot,
        "credits_required": args.credits_required,
        "groups": groups,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  พบ {len(groups)} กลุ่ม, {n_courses} วิชา")
    for g in groups:
        print(f"    กลุ่มที่ {g['group_no']}: {g['name_th']} ({g['name_en']}) — {len(g['courses'])} วิชา")
    print(f"  เขียน {out}")


if __name__ == "__main__":
    main()
