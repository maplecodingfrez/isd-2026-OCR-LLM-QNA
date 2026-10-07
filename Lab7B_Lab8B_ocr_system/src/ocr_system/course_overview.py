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
    if len(found) == 1:
        return found.pop()

    # Acronym resolution via course_names.ACRONYM_MAP
    try:
        import course_names
    except ImportError:
        from . import course_names
    p_upper = phrase.strip().upper()
    for pat, (en_target, th_target) in course_names.ACRONYM_MAP:
        if pat.fullmatch(p_upper):
            en_norm, th_norm = _norm(en_target), _norm(th_target)
            matches = {r[0] for r in conn.execute("SELECT code, name_th, name_en FROM course").fetchall()
                       if (en_norm and en_norm == _norm(r[2])) or (th_norm and th_norm == _norm(r[1]))}
            if len(matches) == 1:
                return matches.pop()
            if _table_exists(conn, "elective_group_course"):
                el_matches = {r[0] for r in conn.execute("SELECT code, name_th, name_en FROM elective_group_course").fetchall()
                              if (en_norm and en_norm == _norm(r[2])) or (th_norm and th_norm == _norm(r[1]))}
                if len(el_matches) == 1:
                    return el_matches.pop()
            break
    return None


def overview_for_bare_reference(conn, question: str, status_fn):
    """(answer, rows, sql) when the question is only a course reference, else None. status_fn(conn, code) -> prerequisite status."""
    text = str(question or "")
    m = _BARE_CODE.match(text)
    code = m.group(1) if m else None
    if code is None:
        n = _BARE_NAME.match(text)
        if n and not re.search(r"\d{8}", n.group(1)):
            code = _resolve_name(conn, n.group(1))
        elif not n and text.strip() and not re.search(r"\d{8}", text):
            # Bare course acronym (e.g. ISD, DSA, DSDA, ML) without prefix
            code = _resolve_name(conn, text.strip())
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
