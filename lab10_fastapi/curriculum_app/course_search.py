"""Course search over every table of a curriculum database that names a course.

`course` holds only the courses placed in the plan; the elective and general-education courses live in
`elective_group_course`, and `course_description` names every course the book describes. Searching only
`course` hid roughly 300 courses, so this module merges the three by course code and ranks the matches.

Matching rules (all case-insensitive):
- every word of the query must match (words in any order); spaces never have to line up, so
  "ฐานข้อมูล ขั้นสูง" finds "ฐานข้อมูลขั้นสูง" and "machinelearning" finds "MACHINE LEARNING";
- a short Latin word (up to 3 letters, for example OS or AI) matches a whole word of the English name or an
  acronym, never the inside of a word ("OS" must not match "NOSQL");
- acronyms (ML, DB, OOP ...) expand through the Q&A resolver's ACRONYM_MAP plus a few search-only aliases;
- ranking: exact code, code prefix, name starts with the query, name contains it, then description-only
  matches; ties go plan, elective, catalogue, then code.
"""

import re

SOURCES = ("plan", "elective", "catalog")
_SOURCE_ORDER = {name: i for i, name in enumerate(SOURCES)}

# Search-only aliases that the Q&A resolver does not need: acronym -> (English fragment, Thai fragment)
EXTRA_ALIASES = {
    "DB": ("DATABASE", "ฐานข้อมูล"),
    "AI": ("ARTIFICIAL INTELLIGENCE", "ปัญญาประดิษฐ์"),
}

_LATIN = re.compile(r"^[a-z0-9.\-]+$")
_COURSE_COLUMNS = "code, name_th, name_en, credits, lecture_h, lab_h, self_h, description_th"


def _table_exists(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (name,)).fetchone() is not None


def _compact(text) -> str:
    return re.sub(r"\s+", "", str(text or "")).casefold()


def _blank(code: str, source: str) -> dict:
    return {"code": code, "name_th": None, "name_en": None, "credits": None, "lecture_h": None, "lab_h": None,
            "self_h": None, "description_th": None, "source": source}


def load_catalog(conn) -> list[dict]:
    """Every known course once, merged by code: plan first, then elective groups, then the book catalogue."""
    rows: dict[str, dict] = {}
    have = {c[1] for c in conn.execute("PRAGMA table_info(course)").fetchall()}     # a bare course table may lack the hour columns
    wanted = [c for c in _COURSE_COLUMNS.split(", ") if c in have]
    for r in conn.execute(f"SELECT {', '.join(wanted)} FROM course").fetchall():
        item = _blank(r[0], "plan")
        item.update({name: r[i] for i, name in enumerate(wanted) if i})
        rows[r[0]] = item
    if _table_exists(conn, "elective_group_course"):
        for r in conn.execute("SELECT code, name_th, name_en, credits FROM elective_group_course").fetchall():
            if r[0] and r[0] not in rows:
                item = _blank(r[0], "elective")
                item.update(name_th=r[1], name_en=r[2], credits=r[3])
                rows[r[0]] = item
    if _table_exists(conn, "course_description"):
        for r in conn.execute("SELECT code, name_th, description_th, description_en FROM course_description").fetchall():
            if not r[0]:
                continue
            item = rows.get(r[0])
            if item is None:
                item = _blank(r[0], "catalog")
                item["name_th"] = r[1]
                rows[r[0]] = item
            item["_description"] = f"{r[2] or ''} {r[3] or ''}"
    return list(rows.values())


def known_course(conn, code: str) -> dict | None:
    """The course with this code from any of the three tables (plan beats elective beats catalogue), else None."""
    for item in load_catalog(conn):
        if item["code"] == code:
            return {k: v for k, v in item.items() if not k.startswith("_")}
    return None


def _acronym_targets(text: str) -> list[tuple[str, str]]:
    """(English fragment, compact Thai fragment) the text stands for, from ACRONYM_MAP and EXTRA_ALIASES."""
    import course_names                       # plain script next to lab8b; on sys.path through main.py / the tests' conftest
    found = []
    for pattern, (en, th) in course_names.ACRONYM_MAP:
        if pattern.fullmatch(text) or pattern.fullmatch(text.upper()):
            found.append((en.casefold(), _compact(th)))
    alias = EXTRA_ALIASES.get(text.upper())
    if alias:
        found.append((alias[0].casefold(), _compact(alias[1])))
    return found


class _Row:
    """One course prepared for matching."""

    def __init__(self, item: dict):
        self.item = item
        self.code = item["code"]
        self.th = _compact(item.get("name_th"))
        self.names = f"{item.get('name_th') or ''} {item.get('name_en') or ''}".casefold()     # spaces kept: for standalone numbers
        self.en = str(item.get("name_en") or "").casefold()
        self.en_compact = _compact(item.get("name_en"))
        self.words = set(re.findall(r"[a-z0-9]+", self.en))
        description = f"{item.get('description_th') or ''} {item.get('_description') or ''}"
        self.description = description.casefold()
        self.description_compact = _compact(description)


def _word_hit(token: str, row: _Row, targets: list[tuple[str, str]]) -> int | None:
    """Tier at which one query word matches the row (0-3 name/code, 4 description) or None."""
    if token.isdigit():
        if len(token) >= 4 and token in row.code:                    # a code fragment: "0602", "06026216"
            return 3
        # a short number is a number in the name ("calc 1" = CALCULUS 1), never digits inside a code
        return 3 if re.search(rf"(?<!\d){re.escape(token)}(?!\d)", row.names) else None
    for en, th in targets:
        if en in row.en or (th and th in row.th):
            return 3
    if _LATIN.match(token):
        if len(token) <= 3:
            hit = token in row.words
        else:
            hit = token in row.en or token in row.en_compact
        if hit:
            return 3
        if len(token) >= 4 and token in row.description:
            return 4
        return None
    tc = _compact(token)
    if tc in row.th or tc in row.en_compact:
        return 3
    return 4 if tc and tc in row.description_compact else None


def _tier(query: str, tokens: list[str], whole_targets: list[tuple[str, str]], row: _Row) -> int | None:
    q_compact = _compact(query)
    q_lower = query.casefold()
    if q_lower == row.code:
        return 0
    if q_lower.isdigit() and row.code.startswith(q_lower):
        return 1
    best = None
    # a multi-word query with its spaces removed: "ฐานข้อมูล ขั้นสูง" -> "ฐานข้อมูลขั้นสูง"; a single word is handled
    # word by word below (so "os" can never match inside "nosql")
    spaced = len(tokens) > 1 and q_compact and (not _LATIN.match(q_compact) or len(q_compact) >= 4)
    if spaced and (q_compact in row.th or q_compact in row.en_compact):
        best = 2 if (row.th.startswith(q_compact) or row.en_compact.startswith(q_compact)) else 3
    # whole query as an acronym phrase: "cal 1"
    for en, th in whole_targets:
        if en in row.en or (th and th in row.th):
            start = row.en.startswith(en) or (th and row.th.startswith(th))
            best = min(best if best is not None else 9, 2 if start else 3)
    # every word, in any order
    hits = []
    for token in tokens:
        hit = _word_hit(token, row, _acronym_targets(token))
        if hit is None:
            hits = None
            break
        hits.append(hit)
    if hits is not None:
        tier = max(hits)
        if tier == 3 and tokens and (row.th.startswith(_compact(tokens[0])) or row.en.startswith(tokens[0].casefold())):
            tier = 2
        best = tier if best is None else min(best, tier)
    return best


def search_courses(conn, query: str, limit: int = 20, offset: int = 0) -> list[dict]:
    """Ranked courses matching the query over plan, elective and catalogue courses (see the module docstring)."""
    query = " ".join(str(query or "").split())
    if not query:
        return []
    tokens = [t.casefold() for t in query.split(" ")]
    whole_targets = _acronym_targets(query)
    scored = []
    for item in load_catalog(conn):
        row = _Row(item)
        tier = _tier(query, tokens, whole_targets, row)
        if tier is not None:
            scored.append((tier, _SOURCE_ORDER[item["source"]], item["code"], item))
    scored.sort(key=lambda s: s[:3])
    window = scored[max(offset, 0): max(offset, 0) + max(limit, 0)]
    return [{k: v for k, v in item.items() if not k.startswith("_")} for _, _, _, item in window]
