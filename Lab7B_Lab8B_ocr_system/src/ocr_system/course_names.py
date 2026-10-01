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
          r"@เป็นพื้นฐาน(?:ของ|ให้)(?:วิชา)?(?:อะไร|ไหน|ใด)", r"ใช้@เป็น(?:วิชา)?พื้นฐาน",
          r"@ปลดล็อกวิชา(?:อะไร|ไหน|ใด)", r"@แล้ว(?:ไป)?ต่อ(?:วิชา)?(?:อะไร|ไหน|ใด)",
          r"@แล้ว.*วิชา(?:อะไร|ไหน|ใด)(?:บ้าง)?ได้อีก"]
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
