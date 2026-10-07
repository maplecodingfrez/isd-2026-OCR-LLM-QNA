"""Informal Thai phrasings -> the wording the existing shortcuts answer, plus one lookup the shortcuts lacked.

Before this, "เรียนจบต้องใช้กี่หน่วยกิต", "ปีไหนหน่วยกิตเยอะที่สุด", "มี lab มากกว่า 2 ชั่วโมง" or "เทอมฤดูร้อน" missed the
shortcuts by a word, reached the language model and came back "ไม่พบข้อมูลนี้ในเล่มหลักสูตร". Same idea as english_questions:
rewrite to the formal Thai question and let the same data-backed shortcut answer, so both wordings give the same answer.

partial_name_term answers "วิชาโครงงานอยู่ปีไหน": a name fragment that matches several plan courses lists each with its year and term.
"""

import re

_TOTAL = "หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต"
_REWRITES = (
    (re.compile(r"^(?:เรียน)?จบ(?:หลักสูตร)?ต้อง(?:ใช้|เรียน|เก็บ)(?:ทั้งหมด)?กี่หน่วยกิต$"), _TOTAL),
    (re.compile(r"^มีวิชาที่เรียน(?:ใน)?(?:เทอม|ภาค)ฤดูร้อนไหม$"), "มีการเรียนภาคฤดูร้อนไหม"),
)
_SUBS = (
    (re.compile(r"เยอะที่สุด|เยอะสุด|มากสุด"), "มากที่สุด"),
    (re.compile(r"น้อยสุด"), "น้อยที่สุด"),
    (re.compile(r"(ปี|เทอม|ภาคเรียน|ภาคการศึกษา)ไหน\s*หน่วยกิต"), r"\1ไหนเรียนหน่วยกิต"),
    (re.compile(r"\s*(?:\blab\b|แล็บ|แลป)\s*", re.I), "ชั่วโมงปฏิบัติ"),
    (re.compile(r"เทอมฤดูร้อน"), "ภาคฤดูร้อน"),
    (re.compile(r"(?<!สอบ)ถ้าตก"), "ถ้าสอบตก"),
    (re.compile(r"(?<=\d)(\s*(?:เรียน|มี)(?:วิชา)?อะไร)\s*[?]?$"), r"\1บ้าง"),                    # "ปี 4 เทอม 1 เรียนอะไร" = "…เรียนอะไรบ้าง"
)


def informal_to_thai(question: str) -> str | None:
    """The formal Thai wording of an informal question, or None when nothing is rewritten."""
    text = str(question or "").strip()
    if not text:
        return None
    squeezed = re.sub(r"[\s?!.]+", "", re.sub(r"(?:ครับ|ค่ะ|คะ|นะ)$", "", text))
    for rx, formal in _REWRITES:
        if rx.match(squeezed):
            return formal
    out = text
    for rx, repl in _SUBS:
        out = rx.sub(repl, out)
    return out if out != text else None


_ASK_WHEN = re.compile(r"^\s*(?:วิชา)?\s*(?P<frag>.{2,40}?)\s*(?:อยู่|เรียน|ลง)\s*(?:ใน)?\s*(?:ปี(?:ไหน|อะไร)|เทอมไหน|ภาคไหน)(?:\s*(?:เทอมไหน|ภาคไหน|ปีไหน))?\s*[?]?\s*$")
_MAX_LISTED = 15


def _norm(text) -> str:
    return re.sub(r"\s+", "", str(text or "")).casefold()


def partial_name_term(conn, question: str):
    """(answer, rows, sql) listing every plan course whose name contains the fragment, with year and term; else None."""
    found = _ASK_WHEN.match(str(question or ""))
    if not found:
        return None
    fragment = re.sub(r"^(?:วิชา)\s*", "", found.group("frag")).strip()
    key = _norm(fragment)
    if len(key) < 3 or re.search(r"\d{8}", fragment) or re.search(r"สหกิจ|ฤดูร้อน|ทั้งหมด|อะไร|ไหน", fragment):
        return None
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT DISTINCT code, name_th, name_en, year, semester FROM v_plan ORDER BY year, semester, code")]
    except Exception:
        return None
    hits = [r for r in rows if key in _norm(r["name_th"]) or key in _norm(r["name_en"])]
    if not hits or len(hits) > _MAX_LISTED:
        return None
    lines = [f"{r['code']} {r['name_th'] or ''}".rstrip() + (f" / {r['name_en']}" if r.get("name_en") else "")
             + f" — ปี {r['year']} เทอม {r['semester']}" for r in hits]
    head = f"วิชาที่ชื่อมีคำว่า \"{fragment}\" ในแผนนี้ มี {len(hits)} วิชา:" if len(hits) > 1 else ""
    answer = "\n".join(([head] if head else []) + lines)
    sql = f"SELECT DISTINCT code, name_th, year, semester FROM v_plan WHERE name_th LIKE '%{fragment.replace(chr(39), chr(39) * 2)}%'"
    return answer, hits, sql
