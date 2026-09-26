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


# ─────────────────────────────────────────────────────────────────────────────
# ซ่อมเพิ่มเติมด้วย "ดัชนีรหัส -> ชื่อ" ของเล่ม (พบจริงใน IT: หน้าที่มีตราน้ำ + ตารางกลุ่มวิชา "เลือก 1 กลุ่ม")
# ─────────────────────────────────────────────────────────────────────────────
FULL_CREDIT_RE = re.compile(r"(\d+)\s*\(\s*[\dxX]+\s*-\s*[\dxX]+\s*-\s*[\dxX]+\s*\)")
MIN_NAME_LEN = 8          # ชื่อสั้นกว่านี้ (หลัง normalize) ไม่ใช้ค้นแบบ substring — กันจับผิดวิชา


def book_index(book_text: str) -> dict[str, dict[str, Any]]:
    """{รหัส: {"name": ชื่อที่เล่มพิมพ์บ่อยสุด, "credits": "3(2-2-5)" | None}} เฉพาะรหัสที่ชื่อ "ชัดเจน":
    ชื่อที่พบบ่อยสุดต้องเจออย่างน้อย 2 บรรทัด และมากกว่าชื่อแบบอื่นของรหัสเดียวกันอย่างชัดเจน
    (OCR ทั้งเล่มสะกดเพี้ยนบางบรรทัด เช่น "คอมพิวตอร์กราิก์…" — ถ้าเพี้ยนเท่า ๆ กัน = ไม่ใช้รหัสนั้น)"""
    names: dict[str, dict[str, list[str]]] = {}
    credits: dict[str, dict[str, int]] = {}
    for line in book_text.splitlines():
        m = BOOK_LINE_RE.search(line)
        if not m:
            continue
        code, rest = m.group(1), m.group(2)
        name = re.split(r"\s{2,}|\||\d+\s*\(", rest, maxsplit=1)[0].strip(" .*-:")
        name = re.sub(r"^[^฀-๿A-Za-z0-9]+", "", name)   # เศษ OCR หน้าชื่อ เช่น "!( "
        if not re.search(r"[฀-๿]", name) or name.startswith(SKIP_PREFIXES):
            continue
        key = normalize(name)
        if len(key) < 4:
            continue
        names.setdefault(code, {}).setdefault(key, []).append(name)
        c = FULL_CREDIT_RE.search(rest)
        if c:
            ct = re.sub(r"\s+", "", c.group(0))
            credits.setdefault(code, {})[ct] = credits.get(code, {}).get(ct, 0) + 1
    out: dict[str, dict[str, Any]] = {}
    for code, variants in names.items():
        ranked = sorted(variants.items(), key=lambda kv: -len(kv[1]))
        top_key, top = ranked[0]
        second = len(ranked[1][1]) if len(ranked) > 1 else 0
        if len(top) < 2 or len(top) <= second:
            continue
        cr = credits.get(code, {})
        best_cr = max(cr, key=cr.get) if cr else None
        out[code] = {"name": top[0].replace("ํา", "ำ"), "key": top_key, "credits": best_cr}
    return out


def book_credits(book_text: str) -> dict[str, str]:
    """{รหัส: หน่วยกิตเต็มรูป เช่น "3(2-2-5)"} ที่พบบ่อยสุดในบรรทัดของรหัสนั้น — ต้องเป็นแบบเดียวที่ชนะชัด
    (แยกจากการเลือกชื่อ: รหัสที่ชื่อสะกดเพี้ยนเท่า ๆ กันยังใช้หน่วยกิตที่พิมพ์ตรงกันได้)"""
    counts: dict[str, dict[str, int]] = {}
    for line in book_text.splitlines():
        m = BOOK_LINE_RE.search(line)
        if not m:
            continue
        c = FULL_CREDIT_RE.search(m.group(2))
        if c:
            ct = re.sub(r"\s+", "", c.group(0))
            counts.setdefault(m.group(1), {})[ct] = counts.get(m.group(1), {}).get(ct, 0) + 1
    out: dict[str, str] = {}
    for code, cs in counts.items():
        ranked = sorted(cs.values(), reverse=True)
        if len(ranked) == 1 or ranked[0] > ranked[1]:
            out[code] = max(cs, key=cs.get)
    return out


def book_variants(book_text: str) -> dict[str, dict[str, tuple[int, str]]]:
    """{รหัส: {ชื่อ normalize: (จำนวนบรรทัด, ชื่อดิบ)}} ทุกแบบสะกด — ใช้กับกฎ 2 ที่มี OCR ตัวที่สองยืนยัน"""
    out: dict[str, dict[str, tuple[int, str]]] = {}
    for line in book_text.splitlines():
        m = BOOK_LINE_RE.search(line)
        if not m:
            continue
        name = re.split(r"\s{2,}|\||\d+\s*\(", m.group(2), maxsplit=1)[0].strip(" .*-:")
        name = re.sub(r"^[^฀-๿A-Za-z0-9]+", "", name)
        if not re.search(r"[฀-๿]", name) or name.startswith(SKIP_PREFIXES):
            continue
        key = normalize(name)
        n, raw = out.setdefault(m.group(1), {}).get(key, (0, name))
        out[m.group(1)][key] = (n + 1, raw)
    return out


def split_merged_codes(courses: list[dict], idx: dict[str, dict[str, Any]]) -> list[dict]:
    """กฎ 1: วิชาที่ช่อง code มีรหัสจริงหลายตัวคั่นด้วยช่องว่าง/จุลภาค (ไม่มี "หรือ" หรือ "/") = OCR/LLM รวมหลายวิชาเป็นแถวเดียว
    (IT ไม่สหกิจ 2/2: "06016414, 06016415") -> แยกเป็นวิชาละแถว ชื่อ/หน่วยกิตจากดัชนีของเล่ม
    ทุกรหัสต้องมีชื่อชัดเจนในดัชนี ไม่งั้นไม่แตะทั้งแถว; รหัสที่มีแถวของตัวเองอยู่แล้วไม่สร้างซ้ำ"""
    done: list[dict] = []
    singles = {str(c.get("code") or "").strip() for c in courses}
    for c in list(courses):
        raw = str(c.get("code") or "")
        codes = CODE8.findall(raw)
        # "หรือ" / "/" = ทางเลือก "A หรือ B" จริง (Lab 8B _ambiguous_code_merge ใช้เกณฑ์เดียวกัน นับหน่วยกิตครั้งเดียว)
        # แยกเฉพาะรหัสที่ OCR รวมด้วยช่องว่าง/จุลภาค (เช่น "06016414, 06016415", "06036146 96642033")
        if len(codes) < 2 or re.search(r"หรือ|/", raw):
            continue
        if not all(k in idx for k in codes):
            continue
        new = []
        for k in codes:
            if k in singles:
                continue
            new.append({**{f: c.get(f) for f in ("year", "semester", "category", "type", "prerequisite")},
                        "code": k, "name_th": idx[k]["name"],
                        "credits": idx[k]["credits"] or c.get("credits"), "name_en": None,
                        "_code_from_book": {"split_from": raw}})
        courses.remove(c)
        courses.extend(new)
        singles.update(n["code"] for n in new)
        done.append({"action": "split", "from": raw, "to": [n["code"] for n in new],
                     "term": f"{c.get('year')}/{c.get('semester')}"})
    return done


def _term_texts(md: str) -> list[tuple[tuple[int, int], str]]:
    """ข้อความ (normalize แล้ว) ของตารางแต่ละเทอม: จากหัว "ปีที่ N ภาค…ที่ M" ถึงหัวถัดไป"""
    heads = [(m.start(), (int(m.group(1)), int(m.group(2)))) for m in HEADING_RE.finditer(md)]
    out = []
    for i, (pos, term) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(md)
        text = re.sub(r"<[^>]+>", " ", md[pos:end])
        out.append((term, normalize(text)))
    return out


def add_names_found_in_term(md: str, courses: list[dict], idx: dict[str, dict[str, Any]],
                            variants: dict[str, dict[str, tuple[int, str]]],
                            credits: dict[str, str] | None = None) -> list[dict]:
    """กฎ 2: ชื่อวิชาของเล่มที่ "อยู่ในตารางเทอมนั้น" แต่รหัสหายจาก OCR และ LLM ไม่ส่งออกมา
    (IT 3/1: กลุ่มวิชาด้านโครงสร้างพื้นฐานฯ โดนตราน้ำ -> 06016421/06016422 ไม่มีรหัสใน Markdown)
    เงื่อนไข: ชื่อ (normalize) ยาว >= MIN_NAME_LEN, อยู่ในตารางของ "เทอมเดียว", ไม่ได้เป็นส่วนหนึ่งของชื่อวิชาอื่น
    ในดัชนีที่ก็อยู่ในเทอมนั้นด้วย, รหัสไม่ปรากฏใน Markdown เลย และไม่อยู่ใน courses
    ชื่อที่ใช้: แบบสะกดที่ Tesseract เจอ >= 2 บรรทัด "และ" Typhoon (Markdown) ก็อ่านได้ตรงกัน — ต้องมีแบบเดียว
    (กรณีเล่มสะกดเพี้ยนเท่า ๆ กัน เช่น 06016422 "…สรรพสิ่ง" 2 ครั้ง / "…สรรหสิ่ง" 2 ครั้ง ใช้ OCR สองตัวที่ตรงกันตัดสิน)"""
    present = {k for c in courses for k in CODE8.findall(str(c.get("code") or ""))}
    md_codes = set(CODE8.findall(md))
    terms = _term_texts(md)
    done: list[dict] = []
    credits = credits or {}
    all_keys = [(o, k) for o, vs in variants.items() for k in vs]
    for code, vs in variants.items():
        if code in present or code in md_codes:
            continue
        confirmed = []
        for key, (n, raw) in vs.items():
            if n < 2 or len(key) < MIN_NAME_LEN:
                continue
            hits = {t for t, text in terms if key in text}
            if len(hits) == 1:
                confirmed.append((key, raw, next(iter(hits))))
        if len(confirmed) != 1:
            continue
        key, raw, term = confirmed[0]
        text = dict(terms)[term]
        longer = [o for o, k in all_keys if o != code and key in k and k != key and k in text]
        if longer:
            continue
        cr = idx.get(code, {}).get("credits") or credits.get(code)
        courses.append({"code": code, "name_th": raw.replace("ํา", "ำ"), "credits": cr,
                        "year": term[0], "semester": term[1], "category": None, "type": None,
                        "name_en": None, "_code_from_book": {"from": None, "via": "name_in_term"}})
        present.add(code)
        done.append({"action": "add", "to": code, "term": f"{term[0]}/{term[1]}", "name_th": raw})
    return done


def fix_placeholder_names(courses: list[dict], idx: dict[str, dict[str, Any]]) -> list[dict]:
    """กฎ 3: วิชารหัสจริง 8 หลักที่ชื่อว่าง หรือชื่อเป็นป้ายช่องวิชาเลือก ("วิชาเลือก…"/"วิชาเสรี…" — รหัสจริง
    ไม่ใช่ช่องเลือก) -> ใช้ชื่อจากดัชนีของเล่ม (เติมหน่วยกิตถ้าว่าง) ไม่แตะชื่อที่เป็นชื่อวิชาปกติอยู่แล้ว"""
    def placeholder(n: str) -> bool:
        return not n or n.startswith(("วิชาเลือก", "วิชาเสรี"))

    real_named = {str(c.get("code") or "").strip() for c in courses
                  if not placeholder(str(c.get("name_th") or "").strip())}
    done: list[dict] = []
    for c in courses:
        code = str(c.get("code") or "").strip()
        if not re.fullmatch(r"\d{8}", code) or code not in idx:
            continue
        name = str(c.get("name_th") or "").strip()
        if not placeholder(name):
            continue
        if code in real_named:
            # รหัสนี้มีแถวชื่อจริงอยู่แล้ว = แถวนี้คือช่องวิชาเลือกที่ LLM ประทับรหัสผิด (เช่น IT coop 4/1
            # "90643021 / 9064xxxx" rowspan) — ไม่เปลี่ยนชื่อ เพราะจะซ่อนความผิดแทนที่จะแก้
            continue
        c["_name_from_book"] = {"from": c.get("name_th")}
        c["name_th"] = idx[code]["name"]
        if not c.get("credits") and idx[code]["credits"]:
            c["credits"] = idx[code]["credits"]
        done.append({"action": "rename", "code": code, "from": name or None, "to": idx[code]["name"]})
    return done


def fix_malformed_credits(courses: list[dict], credits: dict[str, str]) -> list[dict]:
    """กฎ 4: วิชารหัสจริง 8 หลักมีหน่วยกิตได้ "แบบเดียว" — ถ้าช่อง credits มีหลายแบบ ("3(3-0-6) หรือ 3(x-x-x)")
    แปลว่า OCR เลื่อน/รวมเซลล์หน่วยกิตของแถวอื่นมา (พบจริง: IT ไม่สหกิจ 4/2 ตราน้ำทับ แถวหน่วยกิตหลุดออกมา
    เป็นแถวเดียว ทุกแถวได้หน่วยกิตของแถวถัดไป -> 06016407 "โครงงาน 2" ได้ของช่องวิชาเลือก แทน 3(0-9-0))
    แทนด้วยหน่วยกิตที่เล่มพิมพ์ชัดเจนสำหรับรหัสนั้น เฉพาะเมื่อจำนวนหน่วยกิต (ตัวเลขหน้าวงเล็บ) ตรงกัน
    ไม่แตะช่องที่มีหน่วยกิตแบบเดียวอยู่แล้ว (ไม่ override ค่าของ LLM เพียงเพราะเล่มพิมพ์ต่าง)"""
    done: list[dict] = []
    for c in courses:
        code = str(c.get("code") or "").strip()
        text = str(c.get("credits") or "")
        if not re.fullmatch(r"\d{8}", code) or code not in credits:
            continue
        units_found = FULL_CREDIT_RE.findall(text)          # เลขหน่วยกิตของแต่ละแบบ
        if len(units_found) < 2 and "หรือ" not in text:
            continue
        book = credits[code]
        units = {int(n) for n in units_found}
        if units != {int(FULL_CREDIT_RE.match(book).group(1))}:
            continue
        c["_credits_from_book"] = {"from": text}
        c["credits"] = book
        done.append({"action": "credits", "code": code, "from": text, "to": book})
    return done


def repair_with_book(md: str, courses: list[dict], book_text: str) -> list[dict]:
    """กฎ 1-4 ตามลำดับ (แยกรหัสที่รวม -> เพิ่มวิชาที่ชื่ออยู่ในเทอม -> แก้ชื่อว่าง/ป้าย -> แก้หน่วยกิตหลายแบบ) รันซ้ำได้"""
    idx = book_index(book_text)
    credits = book_credits(book_text)
    return (split_merged_codes(courses, idx)
            + add_names_found_in_term(md, courses, idx, book_variants(book_text), credits)
            + fix_placeholder_names(courses, idx)
            + fix_malformed_credits(courses, credits))
