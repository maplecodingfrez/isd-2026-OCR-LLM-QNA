"""Course overview for a bare course reference.

"วิชา 06066300", "06066300", "ขอข้อมูลวิชา ..." or an exact course name asks nothing, so it used to reach the language
model, which guessed an empty query and answered "ไม่พบข้อมูลนี้ในเล่มหลักสูตร". This answers it straight from the database:
the course line (names, credits, hours), year and semester, prerequisites and follow-ups. A question that names a course
and also asks something ("วิชา X ชื่ออะไร") is not a bare reference and returns None, so the existing shortcuts keep it.

The answer text is plain lines, so it reads fine without the page's card; rows[0] carries the same data as fields.
"""

import re

NOT_FOUND = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"
_PREFIX = r"(?:วิชา|รหัสวิชา|รหัส|ข้อมูลวิชา|ขอข้อมูลวิชา|ขอข้อมูล|course|subject)"
_BARE_CODE = re.compile(rf"^\s*(?:{_PREFIX}\s*)?(\d{{8}})\s*[?!.]*\s*$", re.I)
_BARE_NAME = re.compile(rf"^\s*(?:วิชา|ข้อมูลวิชา|ขอข้อมูลวิชา|course|subject)\s*(.+?)\s*[?!.]*\s*$", re.I)


_WHAT_IS = re.compile(r"\s*(?:ภาษา(?:อังกฤษ|ไทย))?\s*คือ(?:วิชา)?อะไร\s*[?!.]*\s*$")
_NAME_OF = re.compile(r"^\s*ชื่อ(?:ภาษา)?(?:อังกฤษ|ไทย)?ของ\s*(?=วิชา|\d)")
_NAME_OF_CODE = re.compile(r"^\s*ชื่อวิชา\s*(\d{8})\s*(?:ภาษา(?:อังกฤษ|ไทย))?\s*(?:คืออะไร|ว่าอะไร)?\s*[?!.]*\s*$")


def _strip_what_is(text: str) -> str:
    """"X คืออะไร" / "ชื่อภาษาอังกฤษของวิชา X" / "ชื่อวิชา 0602… ภาษาอังกฤษคืออะไร" ask for the course itself: reduce them to "วิชา X"."""
    code = _NAME_OF_CODE.match(text)
    if code:
        return "วิชา " + code.group(1)
    rest = _NAME_OF.sub("", text)
    if rest == text and not _WHAT_IS.search(rest):
        return text
    rest = _WHAT_IS.sub("", rest).strip()
    return rest if rest.startswith(("วิชา", "รหัส")) else "วิชา " + rest


def _table_exists(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (name,)).fetchone() is not None


def _norm(text) -> str:
    return re.sub(r"\s+", "", str(text or "")).casefold()


def _course_row(conn, code: str) -> dict | None:
    have = {c[1] for c in conn.execute("PRAGMA table_info(course)").fetchall()}
    wanted = [c for c in ("code", "name_th", "name_en", "credits", "lecture_h", "lab_h", "self_h") if c in have]
    row = conn.execute(f"SELECT {', '.join(wanted)} FROM course WHERE code = ?", (code,)).fetchone()
    if row is None:
        return None
    data = {c: None for c in ("code", "name_th", "name_en", "credits", "lecture_h", "lab_h", "self_h")}
    data.update({name: row[i] for i, name in enumerate(wanted)})
    return data


def _outside_plan(conn, code: str) -> dict | None:
    """A course the plan does not place: an elective or general-education course, or one the book only describes."""
    if _table_exists(conn, "elective_group_course"):
        row = conn.execute("SELECT name_th, name_en, credits FROM elective_group_course WHERE code = ? LIMIT 1", (code,)).fetchone()
        if row:
            return {"code": code, "name_th": row[0], "name_en": row[1], "credits": row[2], "source": "elective"}
    if _table_exists(conn, "course_description"):
        row = conn.execute("SELECT name_th FROM course_description WHERE code = ? LIMIT 1", (code,)).fetchone()
        if row:
            return {"code": code, "name_th": row[0], "name_en": None, "credits": None, "source": "catalog"}
    return None


def _course_line(c: dict) -> str:
    """Same shape as the answers' course lines, so the page lays it out the same way."""
    line = f"{c['code']} {c['name_th'] or ''}".rstrip()
    if c.get("name_en"):
        line += f" / {c['name_en']}"
    if c.get("credits") is None:
        return line
    hours = ""
    if None not in (c.get("lecture_h"), c.get("lab_h"), c.get("self_h")):
        hours = f" ({c['lecture_h']}-{c['lab_h']}-{c['self_h']})"
    return f"{line} — {c['credits']}{hours} หน่วยกิต"


def _names(items: list[dict]) -> str:
    return ", ".join(f"{i['code']} ({i['name_th']})" if i.get("name_th") else i["code"] for i in items)


def _resolve_name(conn, phrase: str) -> str | None:
    """The one plan course whose Thai or English name is exactly this phrase (spaces and case ignored), else None."""
    wanted = _norm(phrase)
    if not wanted:
        return None
    found = {r[0] for r in conn.execute("SELECT code, name_th, name_en FROM course").fetchall()
             if wanted in (_norm(r[1]), _norm(r[2]))}
    return found.pop() if len(found) == 1 else None


def overview_for_bare_reference(conn, question: str, status_fn):
    """(answer, rows, sql) when the question is only a course reference, else None. status_fn(conn, code) -> prerequisite status."""
    text = _strip_what_is(str(question or ""))
    m = _BARE_CODE.match(text)
    code = m.group(1) if m else None
    if code is None:
        n = _BARE_NAME.match(text)
        if n and not re.search(r"\d{8}", n.group(1)):
            code = _resolve_name(conn, n.group(1))
    if code is None:
        return None
    sql = f"SELECT * FROM course WHERE code = '{code}'"

    course = _course_row(conn, code)
    if course is None:
        outside = _outside_plan(conn, code)
        if outside is None:
            return f"{NOT_FOUND} (ไม่มีรหัสวิชา {code} ในหลักสูตรนี้)", [], sql
        answer = (_course_line(outside) + "\n"
                  "วิชานี้ไม่อยู่ในแผนการเรียนของหลักสูตรนี้ (วิชาเลือกหรือวิชาที่มีในเล่ม) จึงไม่มีข้อมูลปี/เทอมและวิชาบังคับก่อนในระบบ")
        return answer, [{**outside, "lecture_h": None, "lab_h": None, "self_h": None, "terms": [],
                         "prerequisite_status": "not_in_plan", "prerequisites": [], "unlocks": []}], sql

    terms = []
    for table in ("v_plan", "plan_item"):
        if _table_exists(conn, table):
            terms = [[r[0], r[1]] for r in conn.execute(
                f"SELECT DISTINCT year, semester FROM {table} WHERE code = ? ORDER BY year, semester", (code,)).fetchall()]
            if terms:
                break
    prerequisites = [{"code": r[0], "name_th": r[1]} for r in conn.execute(
        "SELECT p.requires, c.name_th FROM prerequisite p LEFT JOIN course c ON c.code = p.requires "
        "WHERE p.code = ? ORDER BY p.requires", (code,)).fetchall()]
    unlocks = [{"code": r[0], "name_th": r[1]} for r in conn.execute(
        "SELECT p.code, c.name_th FROM prerequisite p LEFT JOIN course c ON c.code = p.code "
        "WHERE p.requires = ? ORDER BY p.code", (code,)).fetchall()]
    status = status_fn(conn, code)

    lines = [_course_line(course)]
    lines.append("เรียน" + "; ".join(f"ปี {y} เทอม {s}" for y, s in terms) if terms else "ไม่ระบุปี/เทอมในแผน")
    if prerequisites:
        lines.append("วิชาบังคับก่อน: " + _names(prerequisites))
    elif status == "none":
        lines.append("วิชาบังคับก่อน: ไม่มี")
    else:
        lines.append("วิชาบังคับก่อน: ยังไม่ทราบ (ตรวจเล่มหลักสูตร)")
    lines.append("วิชาต่อ: " + _names(unlocks) if unlocks else "วิชาต่อ: ไม่พบวิชาต่อในข้อมูลที่มี")
    row = {**course, "source": "plan", "terms": terms, "prerequisite_status": status,
           "prerequisites": prerequisites, "unlocks": unlocks}
    return "\n".join(lines), [row], sql


# ---------- "what must I pass before X?" / "what does X lead to?" for one course ----------

_ASKS_MORE = re.compile(r"และ|พร้อม|ยากไหม|ไม่ต้อง|ไม่มี|ไม่ได้|ไม่ใช่|กี่|ปี\s*\d|เทอม|ภาค|หน่วยกิต|ชั่วโมง|ถอน|ตก|ดรอป|ดร็อป|ชื่อ")
_NEXT_Q = re.compile(r"ต้อง(?:เรียน|ผ่าน)ก่อนวิชา(?:อะไร|ใด|ไหน)|วิชาต่อ|เรียนต่อ|ต่อ(?:วิชา|ยอด)|แล้วต่อ|เป็นวิชาบังคับก่อน|เป็นบันได|ปลดล็อก|unlock|follow[- ]?up|lead to", re.I)
_PRE_Q = re.compile(r"วิชาบังคับก่อน|prerequisite|ก่อนเรียน|ต้อง(?:ผ่าน|เรียน|ลง)\s*(?:วิชา)?\s*(?:ใด|อะไร|ไหน)", re.I)


def _course_in_text(conn, question: str) -> tuple[str | None, bool]:
    """(code, ok): ok is False when the text names no course or more than one (then the question is not about a single course)."""
    known = {r[0]: (r[1], r[2]) for r in conn.execute("SELECT code, name_th, name_en FROM course")}
    codes = list(dict.fromkeys(re.findall(r"\d{8}", question)))
    if codes:
        return (codes[0], True) if len(codes) == 1 and codes[0] in known else (None, False)
    text = _norm(question)
    hits = [(len(_norm(n)), code) for code, names in known.items() for n in names if _norm(n) and len(_norm(n)) >= 4 and _norm(n) in text]
    if not hits:
        return None, False
    best = max(length for length, _ in hits)
    top = {code for length, code in hits if length == best}
    # a longer name that contains a shorter one ("แคลคูลัส 2" inside a sentence) wins; two different longest names = not one course
    return (next(iter(top)), True) if len(top) == 1 else (None, False)


def _alt_pairs(conn) -> set:
    if not _table_exists(conn, "prerequisite_alt"):
        return set()
    return {(r[0], r[1]) for r in conn.execute("SELECT code, requires FROM prerequisite_alt")}


def prerequisite_lookup(conn, question: str, status_fn):
    """(answer, rows, sql) for one course asked about its prerequisites or its follow-up courses, else None.
    Direction: "ต้องผ่าน <X> ก่อน" and "X มีวิชาต่อ / เป็นวิชาบังคับก่อนของ…" = follow-ups; "X ต้องผ่านอะไรก่อน / วิชาบังคับก่อนของ X" = prerequisites."""
    text = str(question or "")
    if not text.strip() or not _table_exists(conn, "prerequisite"):
        return None
    code, ok = _course_in_text(conn, text)
    if not ok:
        return None
    course = _course_row(conn, code)
    spellings = [code] + [n for n in ((course or {}).get("name_th"), (course or {}).get("name_en")) if n]
    rest = text
    for n in spellings:                                          # words inside the course's own name ("การวิเคราะห์และออกแบบระบบ") are not part of the question
        rest = re.sub(r"\s*".join(map(re.escape, _norm(n))), " ", rest, flags=re.I)
    if _ASKS_MORE.search(rest):
        return None
    after_must = any(re.search(r"ต้อง(?:ผ่าน|เรียน|ใช้)\s*(?:วิชา)?\s*" + r"\s*".join(map(re.escape, _norm(n))), text, re.I) for n in spellings)
    owner = any(re.search(r"วิชาบังคับก่อน(?:ของ|ที่ต้องใช้ใน)\s*(?:วิชา)?\s*" + r"\s*".join(map(re.escape, _norm(n))), text, re.I) for n in spellings)
    asks_next = bool(_NEXT_Q.search(text)) or after_must          # "วิชาที่ต้องผ่าน X ก่อน" = what X leads to
    asks_pre = bool(_PRE_Q.search(text))
    if owner:                                                    # "วิชาบังคับก่อนของ X" = prerequisites of X ("X เป็นวิชาบังคับก่อนของ…" has X first)
        asks_next, asks_pre = False, True
    elif asks_next:
        asks_pre = False
    if asks_next == asks_pre:
        return None
    head = _course_line({**course, "credits": None, "lecture_h": None}) if course else code
    alt = _alt_pairs(conn)
    names = {r[0]: (r[1], r[2], r[3]) for r in conn.execute("SELECT code, name_th, name_en, credits FROM course")}

    def item(c: str) -> dict:
        n = names.get(c, (None, None, None))
        return {"code": c, "name_th": n[0], "name_en": n[1], "credits": n[2]}

    def label(c: str) -> str:
        course_names = [name for name in names.get(c, (None, None))[:2] if name]
        return f"{c} ({' / '.join(course_names)})" if course_names else c

    if asks_pre:
        required = [r[0] for r in conn.execute("SELECT requires FROM prerequisite WHERE code = ? ORDER BY requires", (code,)).fetchall()]
        sql = f"SELECT requires FROM prerequisite WHERE code = '{code}'"
        if not required:
            status = status_fn(conn, code)
            return head + "\n" + ("วิชาบังคับก่อน: ไม่มี" if status == "none" else "วิชาบังคับก่อน: ยังไม่ทราบ (ตรวจเล่มหลักสูตร)"), [], sql
        either = [c for c in required if (code, c) in alt]
        must = [c for c in required if (code, c) not in alt]
        parts = []
        if must:
            parts.append("; ".join(label(c) for c in must))
        if either:
            parts.append("ผ่านอย่างใดอย่างหนึ่ง: " + " หรือ ".join(label(c) for c in either))
        return head + "\nวิชาบังคับก่อน: " + "; และ ".join(parts), [item(c) for c in required], sql
    follow = [r[0] for r in conn.execute("SELECT DISTINCT code FROM prerequisite WHERE requires = ? ORDER BY code", (code,)).fetchall()]
    sql = f"SELECT code FROM prerequisite WHERE requires = '{code}'"
    if not follow:
        return head + "\nวิชาต่อ: ไม่พบวิชาต่อในข้อมูลที่มี", [], sql
    return f"วิชาต่อที่ต้องผ่าน {code} ก่อน:\n" + "; ".join(label(c) + (" (วิชานี้เป็นทางเลือกหนึ่ง)" if (c, code) in alt else "") for c in follow), [item(c) for c in follow], sql
