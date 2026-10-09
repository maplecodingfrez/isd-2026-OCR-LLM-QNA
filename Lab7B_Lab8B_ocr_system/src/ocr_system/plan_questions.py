"""Plan questions the model used to guess at (and sometimes got WRONG), answered from the plan's own tables.

The model-on sweep found: "โครงงานกี่หน่วยกิต" -> 132 (the whole programme), "วิชาที่ 3 หน่วยกิตมีกี่วิชา" -> 46 (the whole course table,
the plan has 32), "สหกิจกี่หน่วยกิต" -> 18 (a term total, each co-op course is 6), "เทอมไหนมีวิชามากที่สุด" -> "2 ภาคการศึกษา", plus a
dozen shapes that came back "ไม่พบข้อมูล" although the data is there. Each handler matches ONE narrow shape (the whole question, spaces
ignored) and returns None for anything else, so the older routes keep every question they already answered.

plan_question_answer(conn, question) -> (answer, rows, sql) | None
"""

import re

NOT_RELATED = None
_TAIL = re.compile(r"(?:ครับ|ค่ะ|คะ|นะ)$")
_MAX_LISTED = 20


def _squeeze(text: str) -> str:
    return re.sub(r"[\s?!.]+", "", _TAIL.sub("", str(text or "").strip()))


def _norm(text) -> str:
    return re.sub(r"\s+", "", str(text or "")).casefold()


def _has(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (name,)).fetchone() is not None


def _line(c: dict, with_credits: bool = True) -> str:
    text = f"{c['code']} {c.get('name_th') or ''}".rstrip()
    if c.get("name_en"):
        text += f" / {c['name_en']}"
    if with_credits and c.get("credits") is not None:
        text += f" — {c['credits']} หน่วยกิต"
    return text


def _plan_courses(conn) -> list[dict]:
    """Courses the plan places (one row per code), with their credits."""
    return [dict(r) for r in conn.execute(
        "SELECT DISTINCT v.code AS code, c.name_th AS name_th, c.name_en AS name_en, c.credits AS credits "
        "FROM v_plan v JOIN course c ON c.code = v.code ORDER BY v.code")]


# ---- 1. "วิชาที่ 3 หน่วยกิตมีกี่วิชา / มีอะไรบ้าง" ----
_CREDIT_FILTER = re.compile(r"^(?:มี)?วิชา(?:ที่)?(?:มี)?(\d+)หน่วยกิต(มีกี่วิชา|กี่วิชา|มีอะไรบ้าง|มีวิชาอะไรบ้าง|อะไรบ้าง)$")


def _credits_filter(conn, text: str):
    found = _CREDIT_FILTER.match(_squeeze(text))
    if not found:
        return None
    credits, ask = int(found.group(1)), found.group(2)
    courses = [c for c in _plan_courses(conn) if c["credits"] == credits]
    sql = f"SELECT DISTINCT v.code, c.name_th, c.credits FROM v_plan v JOIN course c ON c.code = v.code WHERE c.credits = {credits}"
    if not courses:
        return f"ไม่มีวิชาที่ {credits} หน่วยกิตในแผนนี้", [], sql
    if "กี่" in ask:
        return f"วิชาในแผนที่มี {credits} หน่วยกิต มี {len(courses)} วิชา", courses, sql
    return f"วิชาในแผนที่มี {credits} หน่วยกิต มี {len(courses)} วิชา:\n" + "\n".join("- " + _line(c) for c in courses), courses, sql


# ---- 2. "ปี 2 มีกี่วิชา" / "ปี 2 เทอม 1 เรียนกี่วิชา" ----
_TERM_COUNT = re.compile(r"^ปี(\d)(?:เทอม(\d))?(?:มี|เรียน)(?:ทั้งหมด)?กี่วิชา$")


_TERM_COUNT_ALT = re.compile(r"^(?:มี)?กี่วิชา(?:ใน)?ปี(\d)(?:เทอม(\d))?$")


def _term_count(conn, text: str):
    found = _TERM_COUNT.match(_squeeze(text)) or _TERM_COUNT_ALT.match(_squeeze(text))
    if not found:
        return None
    year, term = int(found.group(1)), found.group(2)
    where, params, label = "year = ?", [year], f"ปี {year}"
    if term:
        where, params, label = where + " AND semester = ?", params + [int(term)], f"ปี {year} เทอม {term}"
    rows = [dict(r) for r in conn.execute(
        f"SELECT code, name_th, year, semester FROM v_plan WHERE {where} ORDER BY year, semester, id", params)]
    sql = f"SELECT code, name_th, year, semester FROM v_plan WHERE {where.replace('?', '{}').format(*params)}"
    if not rows:
        return f"ไม่พบรายวิชาของ{label}ในแผนนี้", [], sql
    return f"{label} มี {len(rows)} วิชา (นับทุกช่องในแผน รวมช่องวิชาเลือก)", rows, sql


# ---- 3. "เทอมไหนมีวิชามากที่สุด" / "ปีไหนมีวิชาเยอะที่สุด" ----
_BUSIEST = re.compile(r"^(เทอม|ภาคเรียน|ภาคการศึกษา|ปี)ไหน(?:เรียน|มี)วิชา(มาก|เยอะ|น้อย)(?:ที่)?สุด$")


def _busiest_term(conn, text: str):
    found = _BUSIEST.match(_squeeze(text))
    if not found:
        return None
    by_year, most = found.group(1) == "ปี", found.group(2) != "น้อย"
    cols = "year" if by_year else "year, semester"
    counts = [tuple(r) for r in conn.execute(f"SELECT {cols}, COUNT(*) FROM v_plan GROUP BY {cols} ORDER BY {cols}")]
    if not counts:
        return None
    best = (max if most else min)(c[-1] for c in counts)
    winners = [c for c in counts if c[-1] == best]
    names = ["ปี " + str(w[0]) if by_year else f"ปี {w[0]} เทอม {w[1]}" for w in winners]
    sql = f"SELECT {cols}, COUNT(*) FROM v_plan GROUP BY {cols}"
    kind = "ปี" if by_year else "เทอม"
    return (f"{kind}ที่มีวิชา{'มาก' if most else 'น้อย'}ที่สุดคือ " + " และ ".join(names) + f" ({best} วิชา)",
            [{"year": w[0], **({} if by_year else {"semester": w[1]}), "courses": w[-1]} for w in winners], sql)


# ---- 4. "ปี 2 เทอม 1 วิชาไหนหน่วยกิตมากที่สุด" ----
_TERM_EXTREME = re.compile(r"^ปี(\d)เทอม(\d)วิชาไหน(?:มี)?หน่วยกิต(มาก|เยอะ|น้อย)(?:ที่)?สุด$")


def _term_extreme_credits(conn, text: str):
    found = _TERM_EXTREME.match(_squeeze(text))
    if not found:
        return None
    year, term, most = int(found.group(1)), int(found.group(2)), found.group(3) != "น้อย"
    rows = [dict(r) for r in conn.execute(
        "SELECT DISTINCT v.code AS code, c.name_th AS name_th, c.name_en AS name_en, c.credits AS credits "
        "FROM v_plan v JOIN course c ON c.code = v.code WHERE v.year = ? AND v.semester = ? ORDER BY v.code", (year, term))]
    sql = ("SELECT DISTINCT v.code, c.name_th, c.credits FROM v_plan v JOIN course c ON c.code = v.code "
           f"WHERE v.year = {year} AND v.semester = {term}")
    rows = [r for r in rows if r["credits"] is not None]
    if not rows:
        return f"ไม่พบรายวิชาของปี {year} เทอม {term} ในแผนนี้", [], sql
    best = (max if most else min)(r["credits"] for r in rows)
    winners = [r for r in rows if r["credits"] == best]
    return (f"ปี {year} เทอม {term} วิชาที่มีหน่วยกิต{'มาก' if most else 'น้อย'}ที่สุด ({best} หน่วยกิต) มี {len(winners)} วิชา:\n"
            + "\n".join("- " + _line(r, False) for r in winners), winners, sql)


# ---- course references for the two-course and one-course shapes ----
def _course_refs(conn, text: str):
    """(text with every known 8-digit course code replaced by a marker ‹n›, [codes in order of appearance])."""
    known = {r[0] for r in conn.execute("SELECT code FROM course")}
    codes, marked, cursor = [], "", 0
    for m in re.finditer(r"\d{8}", text):
        if m.group(0) in known:
            codes.append(m.group(0))
            marked += text[cursor:m.start()] + f"‹{len(codes)}›"
            cursor = m.end()
    return marked + text[cursor:], codes


def _names_to_codes(conn, text: str) -> str:
    """Replace whole course names by their codes (longest name first, spaces ignored) so the shapes below can rely on codes."""
    known = sorted(((re.sub(r"\s+", "", n or ""), c) for c, n1, n2 in conn.execute("SELECT code, name_th, name_en FROM course") for n in (n1, n2)),
                   key=lambda kv: -len(kv[0]))
    out = text
    for name, code in known:
        if len(name) < 4:
            continue
        pattern = r"\s*".join(map(re.escape, name))
        out = re.sub(pattern, f" {code} ", out, flags=re.I)
    return out


def _requirements(conn, code: str):
    """(required codes, alternative-required codes) for a course from the prerequisite tables."""
    required = [r[0] for r in conn.execute("SELECT DISTINCT requires FROM prerequisite WHERE code = ? ORDER BY requires", (code,))]
    alt = set()
    if _has(conn, "prerequisite_alt"):
        alt = {r[0] for r in conn.execute("SELECT requires FROM prerequisite_alt WHERE code = ?", (code,))}
    return required, alt


def _label(names: dict, code: str) -> str:
    return f"{code} ({names[code]})" if names.get(code) else code


# ---- 5. "ต้องผ่าน A ก่อนเรียน B ไหม" ----
_YN = r"(?:ไหม|หรือไม่|มั้ย|หรือเปล่า|รึเปล่า)"
_PAIR_SHAPES = (
    (re.compile(rf"^ต้อง(?:ผ่าน|เรียน)(?:วิชา)?‹1›ก่อน(?:เรียน)?(?:วิชา)?‹2›{_YN}$"), (0, 1)),      # A is the prerequisite
    (re.compile(rf"^‹1›เป็นวิชาบังคับก่อนของ(?:วิชา)?‹2›{_YN}$"), (0, 1)),
    (re.compile(rf"^(?:วิชา)?‹1›ต้อง(?:ผ่าน|เรียน)(?:วิชา)?‹2›ก่อน{_YN}$"), (1, 0)),               # B is asked first
)


def _pair_prerequisite(conn, text: str):
    marked, codes = _course_refs(conn, _names_to_codes(conn, text))
    if len(codes) != 2 or codes[0] == codes[1]:
        return None
    squeezed = _squeeze(marked)
    for rx, (a_at, b_at) in _PAIR_SHAPES:
        if rx.match(squeezed):
            a, b = codes[a_at], codes[b_at]
            break
    else:
        return None
    names = {r[0]: r[1] for r in conn.execute("SELECT code, name_th FROM course")}
    required, alt = _requirements(conn, b)
    sql = f"SELECT requires FROM prerequisite WHERE code = '{b}'"
    rows = [{"code": c, "name_th": names.get(c)} for c in required]
    if a in required:
        if a in alt:
            return (f"ใช่ ({_label(names, a)} เป็นทางเลือกหนึ่ง): {_label(names, b)} ต้องผ่านอย่างใดอย่างหนึ่งใน "
                    + " หรือ ".join(_label(names, c) for c in sorted(alt))), rows, sql
        return f"ใช่ — {_label(names, b)} ต้องผ่าน {_label(names, a)} ก่อน", rows, sql
    # indirect: A is a prerequisite of something B requires
    seen, frontier = set(required), list(required)
    while frontier:
        nxt = [r[0] for c in frontier for r in conn.execute("SELECT DISTINCT requires FROM prerequisite WHERE code = ?", (c,)) if r[0] not in seen]
        seen |= set(nxt)
        frontier = nxt
    if a in seen:
        return (f"ไม่ใช่วิชาบังคับก่อนโดยตรง — {_label(names, b)} ต้องผ่าน {', '.join(_label(names, c) for c in required)} ก่อน "
                f"ซึ่งต้องผ่าน {_label(names, a)} มาก่อนอีกทอดหนึ่ง"), rows, sql
    if required:
        return f"ไม่ — {_label(names, b)} ต้องผ่าน {', '.join(_label(names, c) for c in required)} ก่อน ไม่ได้ระบุ {_label(names, a)}", rows, sql
    return f"ไม่ — {_label(names, b)} ไม่มี {_label(names, a)} เป็นวิชาบังคับก่อน (ข้อมูลในเล่มหลักสูตรของวิชานี้ไม่มีวิชาบังคับก่อนที่อ่านได้)", rows, sql


# ---- 5b. "เปรียบเทียบ A กับ B" (two codes): both overviews, side by side ----
_COMPARE_CODES = re.compile(r"^เปรียบเทียบ(?:วิชา)?‹1›(?:กับ|และ)(?:วิชา)?‹2›$")


def _compare_codes(conn, text: str, status_fn):
    marked, codes = _course_refs(conn, text)
    if len(codes) != 2 or codes[0] == codes[1] or not _COMPARE_CODES.match(_squeeze(marked)):
        return None
    from course_overview import overview_for_bare_reference
    parts = [overview_for_bare_reference(conn, c, status_fn) for c in codes]
    if not all(parts) or not all(p[1] for p in parts):
        return None
    return "\n\n".join(p[0] for p in parts), [p[1][0] for p in parts], parts[0][2] + "; " + parts[1][2]


# ---- 6. "เรียน X ได้เลยไหม" ----
_RIGHT_AWAY = re.compile(rf"^(?:เรียน|ลงทะเบียน|ลง)(?:วิชา)?‹1›ได้เลย{_YN}$")


def _right_away(conn, text: str, status_fn):
    marked, codes = _course_refs(conn, _names_to_codes(conn, text))
    if len(codes) != 1 or not _RIGHT_AWAY.match(_squeeze(marked)):
        return None
    code = codes[0]
    names = {r[0]: r[1] for r in conn.execute("SELECT code, name_th FROM course")}
    required, alt = _requirements(conn, code)
    sql = f"SELECT requires FROM prerequisite WHERE code = '{code}'"
    if required:
        must = [c for c in required if c not in alt]
        parts = []
        if must:
            parts.append("; ".join(_label(names, c) for c in must))
        if alt:
            parts.append("ผ่านอย่างใดอย่างหนึ่ง: " + " หรือ ".join(_label(names, c) for c in sorted(alt)))
        return (f"ยังไม่ได้ — {_label(names, code)} ต้องผ่านวิชาบังคับก่อน: " + "; และ ".join(parts),
                [{"code": c, "name_th": names.get(c)} for c in required], sql)
    if status_fn(conn, code) == "none":
        return f"ได้เลย — {_label(names, code)} ไม่มีวิชาบังคับก่อน", [], sql
    return f"ยังไม่ทราบ — เล่มหลักสูตรของ {_label(names, code)} อ่านวิชาบังคับก่อนไม่ได้ ตรวจเล่มหลักสูตรอีกครั้ง", [], sql


# ---- 7. "วิชาไหนไม่มีวิชาต่อ" ----
_LEAF = re.compile(r"^(?:มี)?วิชา(?:ไหน|อะไร)?(?:ที่)?ไม่มีวิชาต่อ(?:มีอะไร)?(?:บ้าง)?$")


def _no_follow_ups(conn, text: str):
    if not _LEAF.match(_squeeze(text)) or not _has(conn, "prerequisite"):
        return None
    required = {r[0] for r in conn.execute("SELECT requires FROM prerequisite")}
    leaves = [c for c in _plan_courses(conn) if c["code"] not in required]
    sql = "SELECT DISTINCT v.code FROM v_plan v WHERE v.code NOT IN (SELECT requires FROM prerequisite)"
    if not leaves:
        return "ทุกวิชาในแผนเป็นวิชาบังคับก่อนของวิชาอื่น", [], sql
    return (f"มี {len(leaves)} วิชาในแผนที่ไม่มีวิชาต่อ (ไม่เป็นวิชาบังคับก่อนของวิชาใด):\n" + "\n".join("- " + _line(c, False) for c in leaves)), leaves, sql


# ---- 8. co-op: "มีสหกิจไหม" and "สหกิจกี่หน่วยกิต" (also any name fragment + กี่หน่วยกิต) ----
_HAS_COOP = re.compile(rf"^(?:แผนนี้|หลักสูตรนี้)?มี(?:ตัวเลือก)?(?:ให้เลือก)?(?:การ)?สหกิจ(?:ศึกษา)?(?:ให้เลือก)?{_YN}$")
_CREDITS_OF = re.compile(r"^(?:วิชา)?(?P<frag>[^\d]{3,40}?)(?:มี|เรียน)?กี่หน่วยกิต$")


def _coop_courses(conn) -> list[dict]:
    return [c for c in _plan_courses(conn) if "สหกิจ" in (c["name_th"] or "")]


def _has_coop(conn, text: str):
    if not _HAS_COOP.match(_squeeze(text)):
        return None
    sql = "SELECT v.year, v.semester, v.code, c.name_th, c.credits FROM v_plan v JOIN course c ON c.code = v.code WHERE c.name_th LIKE '%สหกิจ%'"
    rows = [dict(r) for r in conn.execute(sql)]
    if not rows:
        return None
    first = rows[0]
    return ((f"มี — สหกิจศึกษาอยู่ปี {first['year']} เทอม {first['semester']}:\n"
             + "\n".join(f"- {r['code']} {r['name_th']} — {r['credits']} หน่วยกิต" for r in rows)), rows, sql)


def _credits_of_fragment(conn, text: str):
    found = _CREDITS_OF.match(_squeeze(text))
    if not found:
        return None
    fragment = re.sub(r"^วิชา", "", found.group("frag"))
    key = _norm(fragment)
    if len(key) < 3 or re.search(r"หลักสูตร|ทั้งหมด|รวม|ทั้ง|ปี|เทอม|ภาค|หมวด|วิชานี้|อะไร|ไหน", fragment):
        return None
    hits = [c for c in _plan_courses(conn) if key in _norm(c["name_th"]) or key in _norm(c["name_en"])]
    if not hits or len(hits) > _MAX_LISTED:
        return None
    sql = f"SELECT DISTINCT v.code, c.name_th, c.credits FROM v_plan v JOIN course c ON c.code = v.code WHERE c.name_th LIKE '%{fragment.replace(chr(39), chr(39) * 2)}%'"
    head = f"วิชาที่ชื่อมีคำว่า \"{fragment}\" ในแผนนี้ มี {len(hits)} วิชา:\n" if len(hits) > 1 else ""
    return head + "\n".join(("- " if len(hits) > 1 else "") + _line(c) for c in hits), hits, sql


# ---- 9. topics: "วิชาที่เกี่ยวกับ AI มีอะไรบ้าง", "มีวิชาเกี่ยวกับฐานข้อมูลไหม" ----
_TOPIC_LIST = re.compile(r"^วิชา(?:ที่)?เกี่ยวกับ(?P<t>.+?)(?:มีวิชาอะไรบ้าง|มีอะไรบ้าง|อะไรบ้าง|มีไหม)$")
_TOPIC_YN = re.compile(rf"^มีวิชา(?:ที่)?(?:เกี่ยวกับ)?(?P<t>.+?)(?:บ้าง)?{_YN}$")
_SOURCE_LABEL = {"plan": "ในแผน", "elective": "วิชาเลือก", "catalog": "มีในเล่ม"}


def _topic(conn, text: str):
    squeezed = _squeeze(text)
    found = _TOPIC_LIST.match(squeezed) or _TOPIC_YN.match(squeezed)
    if not found:
        return None
    topic = found.group("t").strip()
    if len(_norm(topic)) < 2 or re.search(r"\d{8}|อะไร|ไหน|กี่|ก่อน|ต่อ|ปี|เทอม|ภาค|หน่วยกิต|ชั่วโมง|ไม่|มั้ย|ยาก|และ", topic):
        return None
    try:
        from lab10_fastapi.curriculum_app import course_search
    except ImportError:
        return None
    shown = course_search.search_courses(conn, topic, limit=_MAX_LISTED + 1)
    # Matching and ranking happen in Python after merging the three source tables.
    # An illustrative LIKE query would not reproduce these results.
    sql = (
        "-- Search explanation / วิธีค้นข้อมูล (not an executable SQL query)\n"
        f"-- Topic / หัวข้อ: {topic}\n"
        "-- Sources: course, elective_group_course, course_description; merge by code\n"
        "-- Match every query word against code, Thai/English names and descriptions; "
        "normalize spaces/case and expand course acronyms\n"
        "-- Rank: code, name, description; prefer plan, elective, catalog; break ties by code\n"
        f"-- Display at most {_MAX_LISTED} matches; inspect one extra match for truncation"
    )
    if not shown:
        return f"ไม่พบวิชาที่เกี่ยวกับ \"{topic}\" ในหลักสูตรนี้", [], sql
    more = len(shown) > _MAX_LISTED
    shown = shown[:_MAX_LISTED]
    head = f"วิชาที่เกี่ยวกับ \"{topic}\" ในหลักสูตรนี้ มี{'มากกว่า ' if more else ' '}{len(shown)} วิชา" + (f" (แสดง {_MAX_LISTED} วิชาแรก)" if more else "") + ":"
    lines = [f"- {_line(c)} ({_SOURCE_LABEL.get(c.get('source'), '')})" for c in shown]
    return head + "\n" + "\n".join(lines), shown, sql


def plan_question_answer(conn, question: str, status_fn=None):
    """The first handler that recognises the question's whole shape, else None."""
    text = str(question or "").strip()
    if not text:
        return None
    try:
        for handler in (_credits_filter, _term_count, _busiest_term, _term_extreme_credits, _pair_prerequisite, _no_follow_ups, _has_coop):
            answer = handler(conn, text)
            if answer:
                return answer
        if status_fn is not None:
            for handler in (_right_away, _compare_codes):
                answer = handler(conn, text, status_fn)
                if answer:
                    return answer
        for handler in (_credits_of_fragment, _topic):
            answer = handler(conn, text)
            if answer:
                return answer
    except Exception:           # a table the plan lacks is "not my question", never an HTTP 500
        return None
    return None
