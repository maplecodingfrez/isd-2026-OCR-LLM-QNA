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


def hint_block(hints: list[tuple[str, str]]) -> str:
    """ข้อความแนบใน prompt — ว่างเมื่อไม่เจอชื่อวิชา"""
    if not hints:
        return ""
    lines = "\n".join(f'- "{name}" = {code}' for name, code in hints)
    return ("ชื่อวิชาที่พบในคำถาม (จากฐานข้อมูล — ใช้รหัสนี้ใน SQL ห้ามเดารหัสเอง):\n" + lines + "\n\n")
