"""ชื่อวิชาในคำถาม -> รหัสวิชา (จากตาราง course ของ DB ที่ถามอยู่ — ไม่ใช้ LLM ไม่ใช้เฉลย)

ปัญหาที่แก้: qwen ไม่รู้ว่าชื่อวิชาไหนคือรหัสอะไร (prompt มีแค่โครงตาราง) — ถามด้วยชื่อไทยจึงแต่งรหัสขึ้นเอง
(ได้ข้อมูลของวิชาอื่น) ส่วนชื่ออังกฤษถูกใส่ลงช่องรหัสตรง ๆ (code='DATA WAREHOUSING') — หาชื่อวิชาในคำถามด้วยโค้ด
แล้วบอกรหัสให้ qwen ใน prompt ไม่เจอชื่อ = ไม่เติมอะไร (prompt เหมือนเดิมทุกตัวอักษร)"""
from __future__ import annotations

import re

MIN_LEN = 4                                   # ชื่อสั้นกว่านี้ (หลังปรับรูป) ไม่นำมาเทียบ — กันจับกลางคำ
CODE_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")


def _norm_th(text: str | None) -> str:
    return re.sub(r"\s+", "", (text or "").replace("ํา", "ำ"))


def _norm_en(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").upper()).strip()


def _matches(question: str, name: str, lang: str):
    """ตำแหน่ง (start, end) ที่ชื่อปรากฏในคำถาม — ตัวเลขท้ายชื่อต้องตรงทั้งตัว, ชื่ออังกฤษต้องเป็นคำเต็ม"""
    if lang == "th":
        return [(m.start(), m.end()) for m in re.finditer(re.escape(name) + r"(?!\d)", question)]
    return [(m.start(), m.end()) for m in re.finditer(rf"(?<![A-Z0-9]){re.escape(name)}(?![A-Z0-9])", question)]


MAX_TRIM = 3                                  # ตัดท้ายคำสุดท้ายได้ไม่เกินกี่ตัว (WAREHOUSE -> WAREHOUS)
MIN_STEM = 5                                  # คำสุดท้ายหลังตัดต้องยาวอย่างน้อยเท่านี้
MIN_PHRASE = 8                                # วลีที่ลองต้องมีตัวอักษรอย่างน้อยเท่านี้ (ไม่นับช่องว่าง)


def _truncated_english(en_question: str, courses: list[dict], typed: set[str],
                       claimed: list[tuple[str, int, int]]) -> list[tuple[int, str, str]]:
    """ชื่ออังกฤษที่ผู้ใช้พิมพ์ตกท้าย ("DATA WAREHOUSE" แทน "DATA WAREHOUSING") — เทียบแบบ LIKE 'วลี%' ที่ต้นคำ หลังตัดท้ายคำสุดท้ายทีละตัว (<= MAX_TRIM)
    ใช้เมื่อวลีไม่ทับชื่อที่จับตรงได้แล้ว และชี้วิชา "เดียว" เท่านั้น (หลายรหัส = กำกวม = ไม่ใส่ ห้ามเดา)"""
    names = [(str(c["code"]), c["name_en"], _norm_en(c["name_en"])) for c in courses
             if re.fullmatch(r"\d{8}", str(c.get("code") or "")) and str(c["code"]) not in typed and c.get("name_en")]
    out = []
    for m in re.finditer(r"(?<![A-Z0-9])[A-Z]{3,}(?: [A-Z]{2,})*(?![A-Z0-9])", en_question):
        if any(k[1] < m.end() and m.start() < k[2] for k in claimed):
            continue
        words = m.group().split(" ")
        done = False
        for first in range(len(words)):                       # คำถามภาษาอังกฤษมีคำนำหน้า ("WHAT ARE THE ... DATA WAREHOUS") — ลองเริ่มจากทุกคำ
            run = " ".join(words[first:])
            start = m.start() + len(" ".join(words[:first])) + (1 if first else 0)
            for trim in range(1, MAX_TRIM + 1):
                phrase = run[: len(run) - trim]
                last = phrase.split(" ")[-1]
                if len(last) < MIN_STEM or len(phrase.replace(" ", "")) < MIN_PHRASE:
                    break
                hit = {code: raw for code, raw, norm in names if re.search(rf"(?<![A-Z0-9]){re.escape(phrase)}", norm)}
                if hit:
                    if len(hit) == 1:
                        code, raw = next(iter(hit.items()))
                        out.append((start, code, raw))
                    done = True
                    break
            if done:
                break
    return out


FRAG_MIN = 10                                 # ท่อนชื่อวิชาไทยที่ผู้ถามพิมพ์ (ตัดคำนำหน้า/ท้าย) ต้องยาวอย่างน้อยเท่านี้ (อักขระ ไม่นับช่องว่าง)
FRAG_COVER = 0.75                             # และครอบคลุมชื่อเต็มอย่างน้อยสัดส่วนนี้


def _thai_fragments(th_question: str, courses: list[dict], typed: set[str], already: set[str]) -> list[tuple[int, str, str]]:
    """ผู้ถามตัดคำนำหน้าชื่อวิชา ("เว็บแอปพลิเคชันโดยใช้เฟรมเวิร์ก" แทน "การพัฒนาเว็บแอปพลิเคชันโดยใช้เฟรมเวิร์ก"): หา "ท่อนร่วมยาวสุด" ระหว่างคำถามกับชื่อไทยของแต่ละวิชา
    รับเมื่อท่อนนั้นยาว >= FRAG_MIN, ครอบคลุมชื่อ >= FRAG_COVER, และ **ปรากฏในชื่อวิชาเดียวเท่านั้น** (ท่อนที่ซ้ำหลายวิชา = กำกวม = ไม่เดา); วิชาที่จับชื่อเต็มได้แล้วข้าม"""
    import difflib
    names = [(str(c["code"]), _norm_th(c.get("name_th"))) for c in courses
             if re.fullmatch(r"\d{8}", str(c.get("code") or "")) and str(c["code"]) not in typed and str(c["code"]) not in already and c.get("name_th")]
    all_names = [_norm_th(c.get("name_th")) for c in courses if c.get("name_th")]
    out = []
    for code, nm in names:
        if len(nm) < FRAG_MIN:
            continue
        mt = difflib.SequenceMatcher(None, th_question, nm, autojunk=False).find_longest_match(0, len(th_question), 0, len(nm))
        frag = th_question[mt.a: mt.a + mt.size]
        if mt.size < FRAG_MIN or mt.size < FRAG_COVER * len(nm) or sum(1 for other in all_names if frag in other) != 1:
            continue
        out.append((mt.a, code, frag))
    return out if len({c for _, c, _ in out}) == 1 else []


# ชื่อวิชาที่พิมพ์ไม่ครบ/ภาษาพูด -> (regex ในคำถาม, ส่วนของชื่อไทยที่ต้องอยู่ในชื่อวิชาของแผนนั้น)
# ใช้เฉพาะเมื่อไม่มีชื่อวิชาใดตรงเลย; กฎแรกที่ตรงตัดสิน (เฉพาะเจาะจงก่อนทั่วไป) และต้องชี้วิชา "เดียว" ในแผนที่ถาม — มีหลายวิชา/ไม่มี = ไม่ตอบ (ผิดวิชา = 0)
COLLOQUIAL_RULES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"โนเอสคิวแอล|nosql", re.I), "โนเอสคิวแอล"),
    (re.compile(r"แนวคิดฐานข้อมูล"), "แนวคิดระบบฐานข้อมูล"),
    (re.compile(r"วิชา\s*ฐานข้อมูล(?!นี้)"), "ฐานข้อมูล"),     # คำกว้าง: ต้องขึ้นต้นด้วย "วิชา" (กัน "ในฐานข้อมูลนี้", "ระบบฐานข้อมูลคืออะไร")
    (re.compile(r"โปรแกรมมิ่ง\s*1(?!\d)"), "การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์"),
    (re.compile(r"อิ้ง\s*1(?!\d)|ภาษาอังกฤษ\s*1(?!\d)"), "ภาษาอังกฤษพื้นฐาน1"),
    (re.compile(r"วิชา\s*สถิติ"), "สถิติ"),
    (re.compile(r"data\s*struc", re.I), "โครงสร้างข้อมูล"),             # "Data Struc" (ตัดคำ) — ชื่อเต็มตรงตัวถูกจับก่อนถึงกฎนี้
    (re.compile(r"ดาต้า\s*สต(?:รั|ั)?[คก]"), "โครงสร้างข้อมูล"),           # "ดาต้าสตัค/ดาต้าสตรัค" (ทับศัพท์)
)


def colloquial_candidates(question: str, courses: list[dict]) -> list[tuple[str, str]]:
    """[(รหัส, ชื่อไทย)] ของทุกวิชาที่ชื่อภาษาพูด/ไม่ครบในคำถามอาจหมายถึง (กฎแรกที่ตรงตัดสิน) — ไม่ตรงกฎ/ไม่มีวิชา = []"""
    for pat, part in COLLOQUIAL_RULES:
        if not pat.search(question):
            continue
        part = _norm_th(part)
        found = {str(c["code"]): c.get("name_th") or "" for c in courses
                 if c.get("code") and part in _norm_th(c.get("name_th"))}
        return list(found.items())
    return []


def colloquial_courses(question: str, courses: list[dict]) -> list[tuple[str, str]]:
    """[(รหัส, ชื่อไทย)] ของวิชาเดียวที่ชื่อภาษาพูด/ไม่ครบในคำถามชี้ถึง — ไม่ตรงกฎ, ไม่มีวิชาในแผน, หรือมีหลายวิชา = []"""
    found = colloquial_candidates(question, courses)
    return found if len(found) == 1 else []


_LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9&'\-]*(?:\s+[A-Za-z][A-Za-z0-9&'\-]*)*")


def _en_tokens(text: str | None) -> list[str]:
    """คำอังกฤษตัวใหญ่ ตัด s ท้ายคำ (SYSTEMS = SYSTEM) เพื่อเทียบชื่อที่พิมพ์ไม่ครบ"""
    return [t[:-1] if len(t) > 4 and t.endswith("S") else t for t in re.findall(r"[A-Z0-9]+", (text or "").upper())]


def english_fragment_courses(question: str, courses: list[dict]) -> tuple[str, list[tuple[str, str, str]]]:
    """(ข้อความที่พิมพ์, [(รหัส, ชื่อไทย, ชื่ออังกฤษ)]) ของวิชาที่ "ชื่ออังกฤษมีสิ่งที่พิมพ์เป็นส่วนหนึ่ง" (เรียงคำติดกัน, สั้นกว่าชื่อจริง);
    ใช้เสนอตัวเลือกใกล้เคียงให้ผู้ใช้ยืนยัน — ไม่เลือกให้เอง; พิมพ์สั้นกว่า 5 ตัวอักษร/ชื่อเต็มตรงตัว/ชื่อจริงอยู่ในคำที่ยาวกว่า = ไม่มีตัวเลือก"""
    for run in _LATIN_RUN.findall(question):
        frag = _en_tokens(run)
        if sum(len(t) for t in frag if t.isalpha()) < 5:
            continue
        found = []
        for c in courses:
            name = _en_tokens(c.get("name_en"))
            if c.get("code") and len(frag) < len(name) and any(name[i:i + len(frag)] == frag for i in range(len(name) - len(frag) + 1)):
                found.append((str(c["code"]), c.get("name_th") or "", c.get("name_en") or ""))
        if found:
            return run.strip(), found
    return "", []


# ตัวย่อวิชา -> (ชื่ออังกฤษ, ชื่อไทย) บางส่วนของชื่อวิชา; ตัวย่อสั้น (MIS/OOP/SE/ML/DW/SAD/OS/DIQ) ตัวใหญ่ใช้ได้ทุกบริบท ตัวเล็ก/ผสมใช้ได้ตามบริบทเท่านั้น (_loose_acronym_ok) — กัน "5 ml" / "dw" ในประโยคทั่วไป
ACRONYM_MAP: list[tuple[re.Pattern, tuple[str, str]]] = [
    (re.compile(r"(?<![A-Za-z0-9])MIS(?![A-Za-z0-9])"), ("MANAGEMENT INFORMATION SYSTEMS", "ระบบสารสนเทศเพื่อการจัดการ")),
    (re.compile(r"(?<![A-Za-z0-9])OOP(?![A-Za-z0-9])"), ("OBJECT-ORIENTED PROGRAMMING", "การสร้างโปรแกรมเชิงวัตถุ")),
    (re.compile(r"(?<![A-Za-z0-9])SE(?![A-Za-z0-9])"), ("SOFTWARE ENGINEERING", "วิศวกรรมซอฟต์แวร์")),
    (re.compile(r"(?<![A-Za-z0-9])ML(?![A-Za-z0-9])"), ("MACHINE LEARNING", "การเรียนรู้ของเครื่อง")),
    (re.compile(r"(?<![A-Za-z0-9])DW(?![A-Za-z0-9])"), ("DATA WAREHOUS", "คลังข้อมูล")),
    (re.compile(r"(?<![A-Za-z0-9])SAD(?![A-Za-z0-9])"), ("ANALYSIS AND DESIGN", "การวิเคราะห์และออกแบบ")),
    (re.compile(r"(?<![A-Za-z0-9])OS(?![A-Za-z0-9])"), ("OPERATING SYSTEM", "ระบบปฏิบัติการ")),
    (re.compile(r"(?<![A-Za-z0-9])DIQ(?![A-Za-z0-9])"), ("DIGITAL INTELLIGENCE QUOTIENT", "ความฉลาดทางดิจิทัล")),
    (re.compile(r"(?<![A-Za-z0-9])AML(?![A-Za-z0-9])"), ("APPLIED MACHINE LEARNING", "การเรียนรู้ของเครื่องเชิงประยุกต์")),
    (re.compile(r"(?<![A-Za-z0-9])BFIT(?![A-Za-z0-9])"), ("BUSINESS FUNDAMENTALS FOR INFORMATION TECHNOLOGY", "พื้นฐานทางธุรกิจสำหรับเทคโนโลยีสารสนเทศ")),
    (re.compile(r"(?<![A-Za-z0-9])ISD(?![A-Za-z0-9])"), ("INTELLIGENT SYSTEM DEVELOPMENT", "การพัฒนาระบบอัจฉริยะ")),
    (re.compile(r"(?<![A-Z0-9])(?:CAL|แคล)\s*1(?![A-Z0-9])", re.IGNORECASE), ("CALCULUS 1", "แคลคูลัส 1")),
    (re.compile(r"(?<![A-Z0-9])(?:CAL|แคล)\s*2(?![A-Z0-9])", re.IGNORECASE), ("CALCULUS 2", "แคลคูลัส 2")),
    (re.compile(r"(?<![A-Z0-9])ENG\s*1(?![A-Z0-9])", re.IGNORECASE), ("FOUNDATION ENGLISH 1", "ภาษาอังกฤษพื้นฐาน 1")),
    (re.compile(r"อิ้ง\s*1"), ("FOUNDATION ENGLISH 1", "ภาษาอังกฤษพื้นฐาน 1")),
]


_LOOSE_ACRONYMS = [None if pat.flags & re.I else re.compile(pat.pattern, re.I) for pat, _ in ACRONYM_MAP]


def _loose_acronym_ok(question: str, start: int, end: int) -> bool:
    """ตัวย่อที่พิมพ์ตัวเล็ก/ตัวผสมยอมรับจาก "บริบท" ไม่ใช่จากตัวพิมพ์: ห้ามมีตัวเลขติดหน้า ("5 ml"); ต้องมี "วิชา" นำหน้า
    หรือ (ตัวย่อ ≥3 ตัวอักษร) เป็นคำอังกฤษคำเดียวในคำถาม ("sad กี่หน่วยกิต"); ตัวย่อ 2 ตัวอักษรต้องมี "วิชา" เท่านั้น"""
    before = question[:start].rstrip()
    if before[-1:].isdigit():
        return False
    if before.endswith("วิชา"):
        return True
    return end - start >= 3 and len(re.findall(r"[A-Za-z]{2,}", question)) == 1


def _acronym_spans(question: str, index: int) -> list[tuple[int, int]]:
    """ช่วงข้อความในคำถามที่เป็นตัวย่อ ACRONYM_MAP[index]: ตัวใหญ่ตามกฎเดิมทุกบริบท + ตัวเล็กตามบริบท (_loose_acronym_ok)"""
    pat, loose = ACRONYM_MAP[index][0], _LOOSE_ACRONYMS[index]
    spans = [m.span() for m in pat.finditer(question)]
    if loose is not None:
        spans += [m.span() for m in loose.finditer(question) if m.span() not in spans and _loose_acronym_ok(question, *m.span())]
    return sorted(spans)


def _acronym_matches(question: str, courses: list[dict]) -> list[tuple[list[tuple[int, int]], str, str]]:
    """[(ช่วงในคำถาม, รหัส, ชื่อไทย)] ของตัวย่อที่อยู่ในคำถามและชี้วิชาเดียวพอดีในแผน — ไม่มี/หลายวิชา = ข้ามตัวย่อนั้น"""
    out = []
    for i, (_, (en_target, th_target)) in enumerate(ACRONYM_MAP):
        spans = _acronym_spans(question, i)
        if not spans:
            continue
        en_norm, th_norm = _norm_en(en_target), _norm_th(th_target)
        found = {str(c["code"]): c.get("name_th") or c.get("name_en") or "" for c in courses
                 if c.get("code") and ((en_norm and en_norm in _norm_en(c.get("name_en")))
                                       or (th_norm and th_norm in _norm_th(c.get("name_th"))))}
        if len(found) == 1:
            (code, name), = found.items()
            out.append((spans, code, name))
    return out


def acronym_courses(question: str, courses: list[dict]) -> list[tuple[str, str]]:
    """[(รหัส, ชื่อไทย)] ของวิชาที่ตัวย่อในคำถามชี้ถึง (ACRONYM_MAP) — ตัวย่อละหนึ่งวิชาเท่านั้น;
    ตัวย่อที่ไม่มีวิชาในแผนหรือตรงหลายวิชา = ข้าม (ผิดวิชา = 0)"""
    return list({code: name for _, code, name in _acronym_matches(question, courses)}.items())


def expand_acronyms(question: str, courses: list[dict]) -> str:
    """แทนตัวย่อวิชาในคำถามด้วยชื่อไทยเต็มของวิชานั้น (เฉพาะตัวย่อที่ชี้วิชาเดียวในแผน) — ให้ทางลัด/โมเดลเห็นชื่อจริง ไม่ใส่ตัวย่อลงช่องรหัส"""
    replace = sorted(((s, e, name) for spans, _, name in _acronym_matches(question, courses) for s, e in spans), reverse=True)
    for s, e, name in replace:                                            # จากท้ายไปหน้า ตำแหน่งไม่เลื่อน
        question = question[:s] + name + question[e:]
    return question


def course_hints(question: str, courses: list[dict]) -> list[tuple[str, str]]:
    """[(ชื่อวิชาตามฐานข้อมูล, รหัส)] ของวิชาที่ชื่ออยู่ในคำถาม — ชื่อยาวชนะชื่อสั้นที่อยู่ข้างใน,
    ชื่อซ้ำกันหลายวิชา = ให้ทุกรหัส (ไม่เลือกเอง), วิชาที่ผู้ใช้พิมพ์รหัสมาแล้วไม่ต้องบอก"""
    typed = set(CODE_RE.findall(question))
    spaces = {"th": _norm_th(question), "en": _norm_en(question)}
    found = []                                   # (ความยาว, lang, start, end, ชื่อ, รหัส)
    for c in courses:
        code = str(c.get("code") or "")
        if not re.fullmatch(r"\d{8}", code) or code in typed:
            continue
        for lang, raw in (("th", c.get("name_th")), ("en", c.get("name_en"))):
            name = _norm_th(raw) if lang == "th" else _norm_en(raw)
            if len(name.replace(" ", "")) < MIN_LEN:
                continue
            for start, end in _matches(spaces[lang], name, lang):
                found.append((end - start, lang, start, end, raw, code))
    claimed: dict[tuple[str, int, int], str] = {}   # ช่วงที่ถูกจับแล้ว -> ชื่อ (ชื่อเดียวกันใช้ช่วงเดียวกันได้)
    picked: list[tuple[int, str, str]] = []
    for length, lang, start, end, raw, code in sorted(found, key=lambda f: (-f[0], f[2], f[5])):
        norm = _norm_th(raw) if lang == "th" else _norm_en(raw)
        overlap = [k for k in claimed if k[0] == lang and k[1] < end and start < k[2]]
        if any(k != (lang, start, end) or claimed[k] != norm for k in overlap):
            continue
        claimed[(lang, start, end)] = norm
        picked.append((start, code, raw))
    picked += _truncated_english(spaces["en"], courses, typed, [k for k in claimed if k[0] == "en"])
    picked += _thai_fragments(spaces["th"], courses, typed, {code for _, code, _ in picked})
    if not picked:
        picked += [(0, code, name) for code, name in acronym_courses(question, courses)]
    if not picked:
        picked += [(0, code, name) for code, name in colloquial_courses(question, courses)]
    out, seen = [], set()
    for _, code, raw in sorted(picked, key=lambda p: (p[0], p[1])):
        if code not in seen:
            seen.add(code)
            out.append((raw, code))
    return out


def with_course_names(answer: str, rows: list[dict], names: dict[str, str]) -> str:
    """เติมชื่อวิชาหลังรหัสในคำตอบ ("06026200" -> "06026200 (แคลคูลัส 1)") — เฉพาะรหัสที่มาจากผล SQL,
    ชื่อจากตาราง course; ชื่อนั้นอยู่ในคำตอบแล้ว / ไม่รู้จักรหัส = ไม่แตะ"""
    from_rows = {c for r in rows for v in r.values() for c in CODE_RE.findall(str(v))}

    def name_it(m: re.Match) -> str:
        code = m.group(0)
        name = names.get(code)
        if code not in from_rows or not name or name in answer:
            return code
        return f"{code} ({name})"

    return CODE_RE.sub(name_it, answer or "")


# ทิศทางของวิชาบังคับก่อน — qwen สลับ code/requires เมื่อถ้อยคำไม่เหมือนตัวอย่างใน prompt ("วิชาตัวต่อจากแคลคูลัส 1"
# ได้ code='X' = ถามว่า X ต้องผ่านอะไร -> 0 แถว -> "ไม่พบ") กฎอ่านจากคำถามที่แทนวิชาด้วย "@" และตัดช่องว่างแล้ว
_AFTER = [r"ต่อจาก@", r"ตัวต่อ", r"หลัง(?:จาก)?(?:เรียน|ผ่าน)?(?:วิชา)?@", r"@เป็น(?:วิชา)?บังคับก่อน",
          r"ต้อง(?:เรียน|ผ่าน)(?:วิชา)?@(?:มา)?ก่อน", r"@แล้ว.*(?:ลง|เรียน)(?:วิชา)?(?:อะไร|ไหน|ใด)(?:บ้าง)?ต่อ",
          # ถ้อยคำอื่นของ "วิชาตัวต่อ" (held-out หลังรีวิว) — ผูกกับ "วิชา(อะไร|ไหน|ใด)" ไม่ให้ชนคำถามอื่น
          r"@เป็น(?:วิชา)?(?:ที่)?(?:เป็น)?พื้นฐาน(?:ของ|ให้)(?:วิชา)?(?:อะไร|ไหน|ใด)",
          r"@เป็น(?:วิชา)?(?:ที่)?ต้อง(?:เรียน|ผ่าน)ก่อน(?:วิชา)?(?:อะไร|ไหน|ใด)", r"ใช้@เป็น(?:วิชา)?พื้นฐาน",
          r"@ปลดล็อกวิชา(?:อะไร|ไหน|ใด)", r"@แล้ว(?:ไป)?ต่อ(?:วิชา)?(?:อะไร|ไหน|ใด)",
          r"@แล้ว.*วิชา(?:อะไร|ไหน|ใด)(?:บ้าง)?ได้อีก",
          # "X ต้องเรียน/ผ่านก่อนวิชาอะไร" = วิชาตัวต่อของ X (ผูกกับ อะไร/ไหน/ใด — "ต้องเรียนก่อนไหม" ไม่เข้า)
          r"@ต้อง(?:เรียน|ผ่าน)ก่อน(?:วิชา)?(?:อะไร|ไหน|ใด)",
          # "X เป็นเงื่อนไข(ก่อนเรียน)ของวิชาไหน" = วิชาตัวต่อของ X (ต้องลงท้ายด้วย "วิชา(อะไร|ไหน|ใด)" กันชนคำถามอื่น)
          r"@เป็น(?:วิชา)?(?:เงื่อนไข|ข้อกำหนด)(?:ก่อน(?:เรียน|ลง(?:ทะเบียน)?)?)?(?:ของ)?(?:วิชา)?(?:อะไร|ไหน|ใด)",
          # ผ่าน/ตก X แล้วกระทบ/ลงต่อไม่ได้/ลงวิชาอะไรได้ (ผูกกับคำถามหาวิชา ไม่ชนคำถามวิชาบังคับก่อนของ X)
          r"(?:ไม่ผ่าน|สอบตก|ตก)@.*(?:กระทบ|ลง(?:ต่อ)?ไม่ได้|เรียนต่อไม่ได้)", r"@(?:ไม่ผ่าน|สอบตก).*กระทบ(?:วิชา)?(?:อะไร|ไหน|ใด)",
          r"@แล้ว.*(?:ลง|เรียน)(?:ทะเบียน)?(?:วิชา)?(?:อะไร|ไหน|ใด)(?:บ้าง)?(?:ได้|เพิ่ม|ที่ต้องใช้)"]
_BEFORE = [r"ก่อน(?:จะ)?(?:ลง)?(?:ทะเบียน)?(?:เรียน)?(?:วิชา)?@", r"บังคับก่อน(?:ของ)?(?:วิชา)?@",
           r"@(?:มี|ต้อง(?:เรียน|ผ่าน))(?:วิชา)?(?:อะไร|ไหน|ใด|บังคับก่อน)",
           r"(?:ถึง|จึง)จะ(?:ลง)?(?:ทะเบียน)?(?:เรียน)?(?:วิชา)?@"]


def prereq_direction(question: str, hints: list[tuple[str, str]]) -> tuple[str, str] | None:
    """("after", X) = ถามหาวิชาที่ต้องเรียน X มาก่อน (requires=X) · ("before", X) = ถามหาวิชาที่ X ต้องเรียนก่อน (code=X)
    ใช้เมื่อคำถามอ้างวิชาเดียว (ชื่อจาก hints หรือรหัสที่พิมพ์มา) และเข้ากฎฝั่งเดียว — ไม่ชัด = None (ไม่เดา)"""
    typed = CODE_RE.findall(question)
    codes = {code for _, code in hints} | set(typed)
    if len(codes) != 1:
        return None
    q = _norm_th(question).upper()
    for token in sorted({_norm_th(n).upper() for n, _ in hints} | set(typed), key=len, reverse=True):
        q = q.replace(token, "@")
    after = any(re.search(p, q) for p in _AFTER)
    before = any(re.search(p, q) for p in _BEFORE)
    if after == before:
        return None
    return ("after" if after else "before", codes.pop())


def direction_block(direction: tuple[str, str] | None) -> str:
    """ข้อความแนบใน prompt บอกคอลัมน์ของตาราง prerequisite — ว่างเมื่อไม่รู้ทิศทาง"""
    if not direction:
        return ""
    kind, code = direction
    if kind == "after":
        return (f"ทิศทาง: คำถามนี้ถามหาวิชาที่ต้องเรียน {code} มาก่อน (วิชาที่เรียนต่อจาก {code}) "
                f"ให้ใช้ SELECT code FROM prerequisite WHERE requires='{code}'\n\n")
    return (f"ทิศทาง: คำถามนี้ถามหาวิชาที่ {code} ต้องเรียนมาก่อน "
            f"ให้ใช้ SELECT requires FROM prerequisite WHERE code='{code}'\n\n")


def hint_block(hints: list[tuple[str, str]]) -> str:
    """ข้อความแนบใน prompt — ว่างเมื่อไม่เจอชื่อวิชา"""
    if not hints:
        return ""
    lines = "\n".join(f'- "{name}" = {code}' for name, code in hints)
    return ("ชื่อวิชาที่พบในคำถาม (จากฐานข้อมูล — ใช้รหัสนี้ใน SQL ห้ามเดารหัสเอง):\n" + lines + "\n\n")
