"""ชุดคำถามทอง v2 — 30 ข้อต่อแผน หลากหลายกว่า v1 ตรงเกณฑ์ ch8 (30 ข้อ, ข้อ "ไม่รู้" >= 2, ให้คะแนนจากผล SQL)

เฉลยคำนวณจาก ground_truth_scoped (แก้ให้ตรงเล่มแล้ว) + หน่วยกิตรวม/ปีที่ประกาศ (สองข้อแรกของไฟล์ v1) — ไม่อ่าน DB
สุ่มด้วย seed ตายตัว "gold-v2:<แผน>" รันซ้ำได้ไฟล์เดิมทุกไบต์ — ไฟล์ที่สร้างแล้วถูกล็อก (sha256 ใน meta) ห้ามแก้หลังเห็นผล

    python build_gold_questions_v2.py        # เขียน v2/<แผน>_gold_questions_v2.json + v2/<แผน>_meta.json
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_gold_questions import expected_prerequisite_pairs, is_placed, parse_credits  # noqa: E402

SCOPED_DIR = HERE.parent / "ground_truth_scoped"
OUT_DIR = HERE / "v2"
PLAN_NAMES = ["ait", "bit_coop", "bit_no_coop", "dsba_coop", "dsba_no_coop", "it_coop", "it_no_coop"]
CODE_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")


def norm_th(s: str | None) -> str:
    return re.sub(r"\s+", "", (s or "").replace("ํา", "ำ"))


def norm_en(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").upper()).strip()


def load_scoped(plan: str) -> list[dict]:
    return json.loads((SCOPED_DIR / f"{plan}_scoped.json").read_text(encoding="utf-8"))["courses"]


def placed_courses(rows: list[dict]) -> dict[str, dict]:
    """วิชาที่ระบุตัวชัด = รหัสตัวเลข 8 หลัก + ปี/ภาคแน่นอน (กติกาเดียวกับ v1) — รหัสซ้ำเก็บแถวแรก"""
    out: dict[str, dict] = {}
    for c in rows:
        if re.fullmatch(r"\d{8}", c.get("code") or "") and is_placed(c):
            out.setdefault(c["code"], c)
    return out


def hours(course: dict) -> tuple[int, int, int, int]:
    parsed = parse_credits(course.get("credits"))
    if parsed is None:
        raise ValueError(f"{course.get('code')}: หน่วยกิตอ่านไม่ได้ {course.get('credits')!r}")
    return parsed


def _term_of(c: dict) -> tuple[int, int] | None:
    try:
        return int(c.get("year")), int(c.get("semester"))
    except (TypeError, ValueError):
        return None


def eligible_terms(rows: list[dict], placed: dict[str, dict], allow_year1: bool = False) -> list[tuple[int, int]]:
    """เทอมที่ถามรายเทอมได้โดยไม่ต้องเดา: ทุกแถวเป็นรหัสจริงในแผน, ไม่มีกลุ่มเลือก (note), ไม่มีรหัสซ้ำ,
    หน่วยกิตรวม 9–22 (CHK7); ปี 1 ใช้เฉพาะเมื่อ allow_year1 (v1 ถามปี 1 ภาค 1 ไปแล้ว)"""
    by_term: dict[tuple[int, int], list[dict]] = {}
    for c in rows:
        t = _term_of(c)
        if t and t[0] >= 1 and t[1] >= 1:
            by_term.setdefault(t, []).append(c)
    ok = []
    for (y, s), cs in sorted(by_term.items()):
        if y == 1 and not allow_year1:
            continue
        codes = [c.get("code") for c in cs]
        if any(c.get("note") or c.get("flexible_year_semester") for c in cs):
            continue
        if any(code not in placed for code in codes) or len(codes) != len(set(codes)):
            continue
        if 9 <= sum(hours(placed[code])[0] for code in codes) <= 22:
            ok.append((y, s))
    return ok


def term_codes(rows: list[dict], y: int, s: int) -> list[str]:
    return sorted({c["code"] for c in rows if _term_of(c) == (y, s) and re.fullmatch(r"\d{8}", c.get("code") or "")})


def prereq_maps(placed: dict[str, dict]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(วิชา -> วิชาบังคับก่อน, วิชาบังคับก่อน -> วิชาที่ต้องใช้) — "A หรือ B" = สองรหัส, นับเฉพาะรหัสในแผน"""
    fwd: dict[str, set[str]] = {}
    rev: dict[str, set[str]] = {}
    for code, c in placed.items():
        for req in CODE_RE.findall(c.get("prerequisite") or ""):
            if req in placed and req != code:
                fwd.setdefault(code, set()).add(req)
                rev.setdefault(req, set()).add(code)
    return fwd, rev


def unique_names(placed: dict[str, dict], key: str) -> set[str]:
    """รหัสวิชาที่ชื่อ (key = name_th / name_en) ไม่ว่างและไม่ซ้ำวิชาอื่นในแผน — ถามด้วยชื่อแล้วได้คำตอบเดียว"""
    normf = norm_th if key == "name_th" else norm_en
    counts = Counter(normf(c.get(key)) for c in placed.values() if normf(c.get(key)))
    return {code for code, c in placed.items() if normf(c.get(key)) and counts[normf(c.get(key))] == 1}


def _v1(plan: str) -> list[dict]:
    return json.loads((HERE / f"{plan}_gold_questions.json").read_text(encoding="utf-8"))


def v1_codes(plan: str) -> set[str]:
    """รหัสวิชาที่ชุด v1 ถามถึงหรือเป็นคำตอบ — v2 เลี่ยงวิชาเหล่านี้เมื่อมีตัวเลือกอื่น"""
    out: set[str] = set()
    for q in _v1(plan):
        out |= set(CODE_RE.findall(q["question"])) | set(CODE_RE.findall(json.dumps(q["expect"])))
    return out


def v1_declared(plan: str) -> tuple[str, str]:
    """(หน่วยกิตรวม, จำนวนปี) ที่เล่มประกาศ — ค่าเดียวกับสองข้อแรกของ v1"""
    qs = _v1(plan)
    return str(qs[0]["expect"]["value"]), str(qs[1]["expect"]["value"])


def v1_keyword(plan: str) -> str | None:
    for q in _v1(plan):
        m = re.search(r"มีคำว่า '([^']+)'", q["question"])
        if m:
            return m.group(1)
    return None


ALL_CODES: set[str] = {c.get("code") or "" for p in PLAN_NAMES for c in load_scoped(p)}
ALL_NAMES_TH: set[str] = {norm_th(c.get("name_th")) for p in PLAN_NAMES for c in load_scoped(p)}

KEYWORDS = ["ระบบ", "ข้อมูล", "เทคโนโลยี", "คอมพิวเตอร์", "ธุรกิจ", "สารสนเทศ", "ปัญญาประดิษฐ์", "ภาษา", "การจัดการ"]
FAKE_NAMES = ["การเล่นหมากรุกสากลขั้นสูง", "ดาราศาสตร์วิทยุเบื้องต้น", "การทำอาหารไทยเชิงพาณิชย์"]

T = {   # แม่แบบคำถาม — หลายแบบต่อหมวด (ทางการ / ภาษาพูด) สุ่มด้วย seed ของแผน
    "total": ["หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต", "เรียนจบหลักสูตรนี้ต้องเก็บหน่วยกิตทั้งหมดกี่หน่วยกิต"],
    "years": ["หลักสูตรนี้เรียนกี่ปี", "ระยะเวลาการศึกษาตามแผนของหลักสูตรนี้กี่ปี"],
    "t_count": ["ปี {y} เทอม {s} ต้องลงเรียนกี่วิชา", "ในแผนการศึกษา ชั้นปีที่ {y} ภาคการศึกษาที่ {s} มีรายวิชาทั้งหมดกี่วิชา"],
    "t_sum": ["ปี {y} เทอม {s} เรียนรวมกี่หน่วยกิต", "ชั้นปีที่ {y} ภาคการศึกษาที่ {s} มีหน่วยกิตรวมเท่าไร"],
    "t_set": ["ปี {y} เทอม {s} เรียนวิชาอะไรบ้าง ขอเป็นรหัสวิชา", "ชั้นปีที่ {y} ภาคการศึกษาที่ {s} ประกอบด้วยรายวิชารหัสใดบ้าง"],
    "c_th": ["รหัสวิชา {code} ชื่อวิชาภาษาไทยว่าอะไร", "วิชา {code} คือวิชาอะไร (ชื่อภาษาไทย)"],
    "c_en": ["รหัสวิชา {code} มีชื่อภาษาอังกฤษว่าอะไร", "วิชา {code} ชื่อภาษาอังกฤษคืออะไร"],
    "d_th": ["วิชา{name}มีรหัสวิชาอะไร"],
    "d_talk": ["{name} รหัสวิชาอะไรนะ", "ขอรหัสวิชาของ{name}หน่อย"],
    "d_en": ["วิชา {name} รหัสอะไร", "What is the course code of {name}"],
    "e_year": ["วิชา{name}อยู่ในแผนการศึกษาชั้นปีที่เท่าไร", "{name} เรียนตอนปีไหน"],
    "e_credit": ["วิชา{name}มีกี่หน่วยกิต", "{name} กี่หน่วยกิต"],
    "e_lab": ["วิชา{name}มีชั่วโมงปฏิบัติการต่อสัปดาห์กี่ชั่วโมง", "{name} แล็บสัปดาห์ละกี่ชั่วโมง"],
    "e_lec_en": ["วิชา {name} มีชั่วโมงบรรยายต่อสัปดาห์กี่ชั่วโมง", "{name} lecture สัปดาห์ละกี่ชั่วโมง"],
    "f_code": ["รหัสวิชา {code} มีวิชาบังคับก่อนคือวิชาใด", "ก่อนลงวิชา {code} ต้องผ่านวิชาอะไรมาก่อน"],
    "f_name": ["ถ้าจะลงเรียน{name} ต้องผ่านวิชาอะไรมาก่อน", "{name} ต้องเรียนวิชาอะไรก่อน"],
    "f_rev": ["วิชาใดบ้างที่มี {code} เป็นวิชาบังคับก่อน", "ผ่านวิชา {code} แล้วจะลงวิชาไหนต่อได้บ้าง"],
    "f_pairs": ["ในฐานข้อมูลนี้มีคู่วิชากับวิชาบังคับก่อนทั้งหมดกี่คู่", "ความสัมพันธ์วิชาบังคับก่อนมีทั้งหมดกี่คู่"],
    # หมวด G จำกัดแค่แผนปี 1–2: เฉลย scoped ไม่มีวิชาในเมนูวิชาเลือก/คู่สหกิจ (ปี 3–4) ที่ตาราง course มี
    "g_credit": ["ในแผนการศึกษาชั้นปีที่ 1–2 มีรายวิชากี่วิชาที่มีหน่วยกิตเท่ากับ {x}",
                 "ปี 1 กับปี 2 มีวิชาที่ได้ {x} หน่วยกิตกี่วิชา"],
    "g_lec": ["ในแผนการศึกษาชั้นปีที่ 1–2 วิชาที่มีชั่วโมงบรรยายต่อสัปดาห์มากที่สุดมีกี่ชั่วโมง",
              "ปี 1 กับปี 2 วิชาที่บรรยายนานที่สุดสัปดาห์ละกี่ชั่วโมง"],
    "g_kw": ["ในแผนการศึกษาชั้นปีที่ 1–2 มีรายวิชากี่วิชาที่ชื่อภาษาไทยมีคำว่า '{kw}'",
             "ปี 1 กับปี 2 มีวิชาที่ชื่อมีคำว่า '{kw}' กี่วิชา"],
    "h_fee": ["ค่าเทอมของหลักสูตรนี้เท่าไร", "ค่าธรรมเนียมการศึกษาต่อภาคการศึกษาของหลักสูตรนี้คือเท่าไร"],
    "h_teacher": ["ใครเป็นอาจารย์ผู้สอนวิชา {code}", "วิชา {code} อาจารย์ประจำวิชาชื่ออะไร"],
    "h_code": ["รหัสวิชา {code} คือวิชาอะไร", "วิชา {code} มีกี่หน่วยกิต"],
    "h_year7": ["ปี 7 เทอม 1 ต้องเรียนวิชาอะไรบ้าง", "ชั้นปีที่ 7 ภาคการศึกษาที่ 1 มีรายวิชาอะไรบ้าง"],
    "h_name": ["วิชา{name}มีกี่หน่วยกิต"],
}


def build_plan(plan: str) -> tuple[list[dict], dict]:
    seed = f"gold-v2:{plan}"
    rng = random.Random(seed)
    rows = load_scoped(plan)
    placed = placed_courses(rows)
    for c in placed.values():
        hours(c)                                     # หน่วยกิตอ่านไม่ได้ = หยุด ไม่เดา
    v1 = v1_codes(plan)
    total, years = v1_declared(plan)
    th_ok, en_ok = unique_names(placed, "name_th"), unique_names(placed, "name_en")
    meta = {"plan": plan, "seed": seed, "terms": [], "terms_relaxed": False, "fallback_v1_codes": [], "replaced": []}
    qs: list[dict] = []
    used: set[str] = set()

    def add(cat, level, text, expect, **extra):
        n = sum(1 for q in qs if q["category"] == cat) + 1
        qs.append({"id": f"{cat}{n}", "category": cat, "level": level, "question": text, "expect": expect, **extra})

    def tmpl(key, **kw):
        return rng.choice(T[key]).format(**kw)

    def pick(allowed: set[str]) -> str:
        fresh = sorted(c for c in allowed if c not in used and c not in v1)
        if fresh:
            code = rng.choice(fresh)
        else:
            code = rng.choice(sorted(c for c in allowed if c not in used))   # ไม่มีตัวใหม่แล้ว -> ใช้วิชาที่ v1 เคยถาม
            meta["fallback_v1_codes"].append(code)
        used.add(code)
        return code

    def named(code, key):   # ชื่อที่ขึ้นบรรทัดใหม่ในเฉลย (ตัดบรรทัดตามหน้ากระดาษ) = เว้นวรรคเดียว
        return " ".join(placed[code][key].split())

    def extra_e():   # ใช้แทนข้อ F เมื่อแผนไม่มีวิชาบังคับก่อนพอ
        code = pick(th_ok)
        add("E", "1", tmpl("e_credit", name=named(code, "name_th")),
            {"type": "value", "value": str(hours(placed[code])[0])}, about_codes=[code], name_key="name_th")

    # A — ระดับหลักสูตร
    add("A", "1", tmpl("total"), {"type": "value", "value": total})
    add("A", "1", tmpl("years"), {"type": "value", "value": years})

    # B — รายเทอม (ปี 2–4)
    terms = eligible_terms(rows, placed)
    if len(terms) < 2:
        terms = eligible_terms(rows, placed, allow_year1=True)
        meta["terms_relaxed"] = True
        if len([t for t in terms if t != (1, 1)]) >= 2:     # ปี 1 ภาค 1 = เทอมที่ v1 ถามแล้ว เลี่ยงถ้าเลี่ยงได้
            terms = [t for t in terms if t != (1, 1)]
    if len(terms) < 2:
        raise ValueError(f"{plan}: เทอมที่ใช้ได้ไม่ถึง 2")
    chosen = sorted(rng.sample(terms, 2))
    meta["terms"] = [list(t) for t in chosen]
    for y, s in chosen:
        codes = term_codes(rows, y, s)
        add("B", "2", tmpl("t_count", y=y, s=s), {"type": "value", "value": str(len(codes))}, term=[y, s])
        add("B", "2", tmpl("t_sum", y=y, s=s),
            {"type": "value", "value": str(sum(hours(placed[c])[0] for c in codes))}, term=[y, s])
        add("B", "2", tmpl("t_set", y=y, s=s), {"type": "set_exact", "value": codes}, term=[y, s])

    # C — รหัส -> ชื่อ
    for _ in range(2):
        code = pick(set(placed))
        add("C", "1", tmpl("c_th", code=code), {"type": "value", "value": named(code, "name_th")}, about_codes=[code])
    code = pick(en_ok)
    add("C", "1", tmpl("c_en", code=code), {"type": "value", "value": named(code, "name_en")}, about_codes=[code])

    # D — ชื่อ -> รหัส
    for key in ("d_th", "d_talk"):
        code = pick(th_ok)
        add("D", "1", tmpl(key, name=named(code, "name_th")), {"type": "value", "value": code},
            about_codes=[code], name_key="name_th")
    code = pick(en_ok)
    add("D", "1", tmpl("d_en", name=named(code, "name_en")), {"type": "value", "value": code},
        about_codes=[code], name_key="name_en")

    # E — ชื่อ -> ข้อมูลของวิชา
    code = pick(th_ok)
    add("E", "1", tmpl("e_year", name=named(code, "name_th")),
        {"type": "value", "value": str(int(placed[code]["year"]))}, about_codes=[code], name_key="name_th")
    code = pick(th_ok)
    add("E", "1", tmpl("e_credit", name=named(code, "name_th")),
        {"type": "value", "value": str(hours(placed[code])[0])}, about_codes=[code], name_key="name_th")
    code = pick(th_ok)
    add("E", "1", tmpl("e_lab", name=named(code, "name_th")),
        {"type": "value", "value": str(hours(placed[code])[2])}, about_codes=[code], name_key="name_th")
    code = pick(en_ok)
    add("E", "1", tmpl("e_lec_en", name=named(code, "name_en")),
        {"type": "value", "value": str(hours(placed[code])[1])}, about_codes=[code], name_key="name_en")

    # F — วิชาบังคับก่อน
    fwd, rev = prereq_maps(placed)
    if fwd:
        s1 = rng.choice(sorted(fwd))
        add("F", "1", tmpl("f_code", code=s1), {"type": "set_exact", "value": sorted(fwd[s1]), "ignore": [s1]},
            about_codes=[s1], direction="forward")
        by_name = sorted(k for k in fwd if k in th_ok and k != s1)      # ห้ามถามวิชาเดียวกับ F1 ซ้ำ
        if by_name:
            s2 = rng.choice(by_name)
            add("F", "1", tmpl("f_name", name=named(s2, "name_th")),
                {"type": "set_exact", "value": sorted(fwd[s2]), "ignore": [s2]}, about_codes=[s2], name_key="name_th",
                direction="forward")
        else:
            meta["replaced"].append("F2 -> E (ไม่มีวิชาอื่นนอกจาก F1 ที่มีวิชาบังคับก่อนและชื่อไม่ซ้ำ)")
            extra_e()
        r = rng.choice(sorted(rev))
        add("F", "1", tmpl("f_rev", code=r), {"type": "set_exact", "value": sorted(rev[r]), "ignore": [r]},
            about_codes=[r], direction="reverse")
    else:
        meta["replaced"].append("F1-F3 -> E (แผนนี้ไม่มีคู่วิชาบังคับก่อนในแผน)")
        for _ in range(3):
            extra_e()
    add("F", "2", tmpl("f_pairs"), {"type": "value", "value": str(expected_prerequisite_pairs(rows))})

    # G — ภาพรวม
    catalog = [placed[c] for c in sorted(placed) if _term_of(placed[c])[0] in (1, 2)]
    credit_values = [hours(c)[0] for c in catalog]
    x = rng.choice(sorted(set(credit_values)))
    add("G", "2", tmpl("g_credit", x=x), {"type": "value", "value": str(credit_values.count(x))})
    add("G", "2", tmpl("g_lec"), {"type": "value", "value": str(max(hours(c)[1] for c in catalog))})
    kw_count = {k: sum(k in c["name_th"] for c in catalog) for k in KEYWORDS if k != v1_keyword(plan)}
    kws = [k for k, n in kw_count.items() if n >= 2] or [k for k, n in kw_count.items() if n >= 1]
    if not kws:
        raise ValueError(f"{plan}: ไม่มีคำค้นที่ใช้ได้")
    kw = rng.choice(kws)
    add("G", "2", tmpl("g_kw", kw=kw), {"type": "value", "value": str(sum(kw in c["name_th"] for c in catalog))})

    # H — ข้อที่ต้องตอบว่าไม่รู้ (ch8: ระบบที่ตอบทุกคำถามได้เสมอ คือระบบที่แต่งคำตอบ)
    none = {"type": "none", "value": None}
    add("H", "none", tmpl("h_fee"), none)
    add("H", "none", tmpl("h_teacher", code=rng.choice(sorted(placed))), none)
    prefix = Counter(c[:4] for c in placed).most_common(1)[0][0]
    fake = next(f"{prefix}{n:04d}" for n in rng.sample(range(10000), 10000) if f"{prefix}{n:04d}" not in ALL_CODES)
    add("H", "none", tmpl("h_code", code=fake), none)
    add("H", "none", tmpl("h_year7"), none)
    fake_name = rng.choice([n for n in FAKE_NAMES if not any(norm_th(n) in a for a in ALL_NAMES_TH)])
    add("H", "none", tmpl("h_name", name=fake_name), none)

    if len(qs) != 30 or len({q["question"] for q in qs}) != 30:
        raise ValueError(f"{plan}: ได้ {len(qs)} ข้อ / คำถามซ้ำ")
    return qs, meta


def render(qs: list[dict]) -> bytes:
    return (json.dumps(qs, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_plan(plan: str) -> Path:
    qs, meta = build_plan(plan)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"{plan}_gold_questions_v2.json"
    data = render(qs)
    path.write_bytes(data)
    meta["sha256"] = hashlib.sha256(data).hexdigest()
    (OUT_DIR / f"{plan}_meta.json").write_bytes(
        (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return path


def main() -> None:
    for plan in PLAN_NAMES:
        path = write_plan(plan)
        print(f"{plan}: 30 ข้อ -> {path.relative_to(HERE)}")


if __name__ == "__main__":
    main()
