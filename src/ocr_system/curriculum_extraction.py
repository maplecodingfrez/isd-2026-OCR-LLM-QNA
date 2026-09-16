import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


CODE_FIND_RE = re.compile(r"(?<![0-9xX])(?:\d{8}|\d{5}[xX]{3}|\d{4}[xX]{4}|[xX]{4,8})(?![0-9xX])")
CREDITS_RE = re.compile(r"\d+\s*\(\s*\d+\s*-\s*\d+\s*-\s*\d+\s*\)")
TOTAL_RE = re.compile(r"(?:รวม|เธฃเธงเธก|total)", re.IGNORECASE)

FOOTER_TOKENS = [
    "เธงเธ—",
    "เธเธ“เธฐ",
    "เธชเธเธฅ",
    "มคอ",
    "วท.บ",
    "สาขาวิชา",
    "คณะเทคโนโลยีสารสนเทศ",
]


def extract_curriculum_from_file(
    ocr_path: str | Path,
    template_path: str | Path | None = None,
    program: str = "DSBA",
    plan: str = "no_coop",
) -> dict[str, Any]:
    payload = _load_ocr_payload(ocr_path)
    parsed = extract_curriculum(payload, program=program, plan=plan)

    # Disable GT/template merge while measuring OCR extraction quality.
    # if template_path:
    #     with Path(template_path).open("r", encoding="utf-8") as f:
    #         template = json.load(f)
    #     return merge_with_template(parsed, template)

    return parsed


def extract_curriculum(payload: dict[str, Any], program: str = "DSBA", plan: str = "no_coop") -> dict[str, Any]:
    courses = []
    for page in payload.get("pages", []):
        courses.extend(_extract_page_courses(page, year=None, semester=None))

    # category / prerequisite / year+semester aren't embedded in the same
    # "code + name + credits" block used above -- they live in separate
    # sections of the document (course-listing category headers, the course
    # description section, and the study-plan table respectively), so they
    # are extracted as independent code -> value lookups and merged in here
    # rather than threaded through _course_from_text().
    category_lookup = _build_category_lookup(payload)
    prerequisite_lookup = _build_prerequisite_lookup(payload)
    name_to_code = _build_name_to_code_map(courses)
    year_semester_lookup = _build_year_semester_lookup(payload, plan, name_to_code)

    for course in courses:
        code = course["code"]
        course["category"] = category_lookup.get(code)
        course["prerequisite"] = prerequisite_lookup.get(code, "ไม่มี")
        if code in year_semester_lookup:
            year, semester, flexible = year_semester_lookup[code]
            course["year"] = year
            course["semester"] = semester
            course["flexible_year_semester"] = flexible

    return {
        "source": "OCR curriculum extraction",
        "description": f"Extracted academic plan from OCR for {program} ({plan})",
        "program": program,
        "plan": plan,
        "courses": courses,
    }


def merge_with_template(parsed: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    parsed_by_code: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for course in parsed.get("courses", []):
        parsed_by_code[str(course.get("code"))].append(course)

    output = {
        "source": template.get("source"),
        "description": template.get("description"),
        "program": template.get("program", parsed.get("program")),
        "plan": template.get("plan", parsed.get("plan")),
        "courses": [],
    }

    for template_course in template.get("courses", []):
        course = dict(template_course)
        code = str(course.get("code"))
        if parsed_by_code[code]:
            parsed_course = parsed_by_code[code].popleft()
            for key in ("name_th", "name_en", "credits", "year", "semester"):
                if course.get(key) in (None, "") and parsed_course.get(key) not in (None, ""):
                    course[key] = parsed_course[key]
        output["courses"].append(course)

    return output


def _load_ocr_payload(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    text = path.read_text(encoding="utf-8")
    pages = []
    for page_no, chunk in _split_text_pages(text):
        pages.append({"page": page_no, "text": chunk})
    return {"source_path": str(path), "engine": "text", "text": text, "pages": pages}


def _split_text_pages(text: str) -> list[tuple[int, str]]:
    matches = list(re.finditer(r"--- Page (\d+) ---", text))
    if not matches:
        return [(1, text)]
    pages = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages.append((int(match.group(1)), text[start:end]))
    return pages


_CATEGORY_VALUES = ["หมวดวิชาศึกษาทั่วไป", "หมวดวิชาเฉพาะ", "หมวดวิชาเลือกเสรี"]


def _build_category_lookup(payload: dict[str, Any]) -> dict[str, str]:
    """Map code -> category, from the course-listing section where each
    category ("ก./ข./ค. หมวดวิชา...") heads a block of course codes.

    Walks each page once, interleaving category-heading matches and code
    matches by their position in the text, and keeps whichever category
    heading most recently preceded a given code. Only the *first* page on
    which a code appears sets its category (matching how courses first
    appear in the listing table, before recurring later in the study-plan
    and course-description sections), so a stray mention of a category name
    on an unrelated page can't override it once set.
    """
    lookup: dict[str, str] = {}
    current: str | None = None
    for page in payload.get("pages", []):
        text = page.get("text", "")
        events: list[tuple[int, str, str]] = []
        for category in _CATEGORY_VALUES:
            for match in re.finditer(re.escape(category), text):
                events.append((match.start(), "category", category))
        for match in CODE_FIND_RE.finditer(text):
            events.append((match.start(), "code", _clean_code(match.group(0))))
        events.sort(key=lambda e: e[0])

        for _, kind, value in events:
            if kind == "category":
                current = value
            elif current is not None and value not in lookup:
                lookup[value] = current
    return lookup


_PREREQ_RE = re.compile(r"วิชาบังคับก่อน\s*[:：]?\s*(\d{8}|ไม่มี)")


def _build_prerequisite_lookup(payload: dict[str, Any]) -> dict[str, str]:
    """Map code -> prerequisite code, from the course-description section.

    Each entry there states "วิชาบังคับก่อน : <code> <name>" (or "... : ไม่มี"
    if there's no prerequisite) right after its own code/name/credits line.
    Courses with no prerequisite don't match this regex at all, so they stay
    unmapped -- the caller defaults those to "ไม่มี", matching ground truth.

    Association is done backward from each "วิชาบังคับก่อน" match to the
    nearest preceding course code -- not forward from each code to the next
    "วิชาบังคับก่อน" -- because when a course *does* have a prerequisite, the
    prerequisite's own 8-digit code sits right after the marker and would
    otherwise be mistaken by a forward search for "the next course", cutting
    the window off one digit-string too early and missing the match.
    """
    lookup: dict[str, str] = {}
    for page in payload.get("pages", []):
        text = page.get("text", "")
        code_positions = [(m.start(), _clean_code(m.group(0))) for m in CODE_FIND_RE.finditer(text)]
        for prereq_match in _PREREQ_RE.finditer(text):
            owner_code = None
            for pos, code in code_positions:
                if pos >= prereq_match.start():
                    break
                owner_code = code
            if owner_code is None or owner_code in lookup:
                continue
            value = prereq_match.group(1)
            lookup[owner_code] = "ไม่มี" if value == "ไม่มี" else _clean_code(value)
    return lookup


_YEAR_SEM_HEADER_RE = re.compile(r"ปีที่\s*(\d+)\s*ภาคการศึกษาที่\s*(\d+)")
_NOCOOP_MARKER_RE = re.compile(r"ไม่เข้า(?:ร่วม)?.{0,20}?สหกิจศึกษา")
_COOP_MARKER_RE = re.compile(r"(?<!ไม่)เข้า(?:ร่วม)?.{0,20}?สหกิจศึกษา")


def _build_name_to_code_map(courses: list[dict[str, Any]]) -> dict[str, str]:
    """Map normalized name_en -> code, from courses already extracted from
    the main course-listing table (reliable code + name + credits blocks).

    Used as a fallback in _build_year_semester_lookup() to recover the code
    for a study-plan-table row where OCR dropped the leading course code but
    kept the course name intact -- e.g. a row that reads just "CALCULUS 1"
    with no "06026200" in front of it. A name that maps to more than one
    distinct code is dropped entirely: an ambiguous match is worse than no
    match, since it risks attributing the wrong year/semester to a course.
    """
    by_name: dict[str, set[str]] = defaultdict(set)
    for course in courses:
        code = course.get("code")
        name = course.get("name_en")
        if not (code and code.isdigit() and name):
            continue
        normalized = re.sub(r"\s+", " ", name).strip().upper()
        # Skip short/generic names (e.g. a stray "AI" or "IT") -- too easy to
        # false-positive match against unrelated text elsewhere in the table.
        if len(normalized) < 8:
            continue
        by_name[normalized].add(code)
    return {name: next(iter(codes)) for name, codes in by_name.items() if len(codes) == 1}


def _build_year_semester_lookup(
    payload: dict[str, Any], plan: str, name_to_code: dict[str, str] | None = None
) -> dict[str, tuple[int | None, int | None, str | None]]:
    """Map code -> (year, semester, flexible_year_semester), from the
    "แผนการศึกษา" (study plan) table, which lists course codes again grouped
    under "ปีที่ N ภาคการศึกษาที่ M" headers.

    Programs with both a coop and no_coop plan (DSBA/IT/BIT) repeat this
    table once per plan; a program with a single plan (AIT) has no
    coop/no_coop marker at all. When both markers are found, the document is
    split at them and only the half matching the requested `plan` is read;
    otherwise the whole table is used as-is.

    Many rows in this table lost their leading course code to OCR entirely,
    leaving just the bare course name (e.g. "CHARM SCHOOL" with no
    "90641001" in front). Where that happens, `name_to_code` -- built from
    the same courses already recovered from the cleaner main listing table --
    is used to recover the code by matching the name text directly.

    A code seen under more than one distinct (year, semester) heading within
    the relevant half is a flexible-slot course (e.g. an elective open to
    "3/1, 3/2, 4/1") -- ground truth represents that as year=0, semester=0,
    flexible_year_semester="3/1, 3/2, 4/1", which is reproduced here.
    """
    full_text = "\n".join(f"--- Page {p['page']} ---\n{p.get('text', '')}" for p in payload.get("pages", []))
    header_matches = list(_YEAR_SEM_HEADER_RE.finditer(full_text))
    if not header_matches:
        return {}

    # The real study-plan table is a tight run of these headers, one per
    # year/semester cell, a few hundred characters apart. A single course
    # description elsewhere in the (300+ page) document can coincidentally
    # contain the same phrase in prose -- that shows up as an isolated match
    # tens of thousands of characters from its neighbors, not part of a run.
    # Clustering by gap size and keeping only the largest cluster reliably
    # picks out the real table and discards those one-off mentions.
    GAP_LIMIT = 5000
    clusters: list[list[re.Match[str]]] = [[header_matches[0]]]
    for match in header_matches[1:]:
        if match.start() - clusters[-1][-1].start() <= GAP_LIMIT:
            clusters[-1].append(match)
        else:
            clusters.append([match])
    table_cluster = max(clusters, key=len)
    table_start = table_cluster[0].start()
    table_end = table_cluster[-1].end() + 800  # margin to catch codes listed after the last header

    # Look for the coop/no_coop split *inside* the table region only (with a
    # small backward margin, since the "3.1.4.1 แผนการศึกษาที่ไม่เข้า..."
    # heading sits a couple dozen characters *before* the first "ปีที่ 1
    # ภาคการศึกษาที่ 1" it introduces), so an incidental mention of
    # "...เข้าโครงการสหกิจศึกษา..." elsewhere in the document (e.g. a
    # one-line summary blurb thousands of characters earlier) can't be
    # mistaken for the real section boundary.
    search_start = max(0, table_start - 300)
    nocoop_match = _NOCOOP_MARKER_RE.search(full_text, search_start, table_end)
    coop_match = _COOP_MARKER_RE.search(full_text, search_start, table_end)

    if nocoop_match and coop_match and coop_match.start() > nocoop_match.start():
        segment = full_text[coop_match.end() : table_end] if plan == "coop" else full_text[table_start : coop_match.start()]
    else:
        segment = full_text[table_start:table_end]

    events: list[tuple[int, str, tuple[int, int] | str]] = []
    for match in _YEAR_SEM_HEADER_RE.finditer(segment):
        events.append((match.start(), "header", (int(match.group(1)), int(match.group(2)))))
    for match in CODE_FIND_RE.finditer(segment):
        events.append((match.start(), "code", _clean_code(match.group(0))))
    for name, code in (name_to_code or {}).items():
        # Match the name's words with flexible whitespace between them (a
        # plain substring search would miss cases where OCR inserted an
        # extra space or line break inside the name), but still require the
        # words themselves to appear in order with nothing else between.
        pattern = re.compile(r"\s+".join(re.escape(word) for word in name.split(" ")))
        for match in pattern.finditer(segment):
            events.append((match.start(), "code", code))
    events.sort(key=lambda e: e[0])

    occurrences: dict[str, list[tuple[int, int]]] = defaultdict(list)
    current: tuple[int, int] | None = None
    for _, kind, value in events:
        if kind == "header":
            current = value  # type: ignore[assignment]
        elif current is not None and current not in occurrences[value]:  # type: ignore[arg-type]
            occurrences[value].append(current)  # type: ignore[arg-type]

    # A real flexible-slot course spans a handful of terms (ground truth's
    # own examples top out around 3, e.g. "3/1, 3/2, 4/1"). A name matching
    # under many more headers than that isn't a genuine flexible course --
    # it's a name-matching false positive (e.g. a generic-sounding elective
    # name recurring in an unrelated reference list elsewhere in the table)
    # -- so it's dropped instead of confidently mislabeling it as flexible.
    MAX_PLAUSIBLE_SLOTS = 4

    lookup: dict[str, tuple[int | None, int | None, str | None]] = {}
    for code, slots in occurrences.items():
        if len(slots) > MAX_PLAUSIBLE_SLOTS:
            continue
        if len(slots) == 1:
            year, semester = slots[0]
            lookup[code] = (year, semester, None)
        else:
            ordered = sorted(slots)
            lookup[code] = (0, 0, ", ".join(f"{y}/{s}" for y, s in ordered))
    return lookup


def _extract_page_courses(page: dict[str, Any], year: int | None, semester: int | None) -> list[dict[str, Any]]:
    # We search for course codes directly on the raw page text (a string),
    # then slice out the substring between consecutive code matches as the
    # "block" describing that course. This preserves original whitespace,
    # which CREDITS_RE relies on (\s* between the digit and the parenthesis)
    # to correctly match credit patterns like "3 (2-2-5)" that may be split
    # across a space, tab, or even a line break by the OCR engine.
    text = page.get("text", "")
    matches = list(CODE_FIND_RE.finditer(text))
    courses = []

    for position, match in enumerate(matches):
        code = _clean_code(match.group(0))
        start = match.end()
        end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        block_text = text[start:end]
        block_text = _trim_block_text(block_text)
        if not block_text.strip():
            continue
        courses.append(_course_from_text(code, block_text, year=year, semester=semester, page_no=page["page"]))

    return courses


def _trim_block_text(block_text: str) -> str:
    credit_match = CREDITS_RE.search(block_text)
    search_start = credit_match.end() if credit_match else 0

    cut_positions = []

    total_match = TOTAL_RE.search(block_text, search_start)
    if total_match:
        cut_positions.append(total_match.start())

    for token in FOOTER_TOKENS:
        idx = block_text.find(token, search_start)
        if idx != -1:
            cut_positions.append(idx)

    if cut_positions:
        block_text = block_text[: min(cut_positions)]

    return block_text


def _course_from_text(code: str, block_text: str, year: int | None, semester: int | None, page_no: int | None) -> dict[str, Any]:
    credit_match = CREDITS_RE.search(block_text)

    if credit_match:
        credits = _normalize_credits(credit_match.group(0))
        before = block_text[: credit_match.start()]
        after = block_text[credit_match.end() :]
    else:
        credits = None
        before = block_text
        after = ""

    name_th = _join_name(_remove_noise(before.split()))
    name_en = _join_english_name(after.split())

    return {
        "page": page_no,
        "code": code,
        "name_th": name_th,
        "name_en": name_en,
        "credits": credits,
        "year": year,
        "semester": semester,
        # category, prerequisite, and flexible_year_semester are filled in
        # afterward by extract_curriculum() via separate code -> value
        # lookups (_build_category_lookup / _build_prerequisite_lookup /
        # _build_year_semester_lookup) -- they don't live in this block of
        # text, so there's nothing to extract here. type and note stay
        # None: no reliable signal for either was found in the source
        # documents (see README Known Limitations).
        "category": None,
        "type": None,
        "prerequisite": None,
        "flexible_year_semester": None,
        "note": None,
    }


def _compact_credit_text(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("))", ")")


def _normalize_credits(text: str) -> str | None:
    compact = _compact_credit_text(text)
    match = re.search(r"(\d+\(\d+-\d+-\d+\))", compact)
    return match.group(1) if match else None


def _remove_noise(texts: list[str]) -> list[str]:
    cleaned = []
    for text in texts:
        value = text.strip()
        if not value:
            continue
        if re.fullmatch(r"\d+", value):
            continue
        if value in {"|", ".", "a"}:
            continue
        cleaned.append(value)
    return cleaned


def _join_name(parts: list[str]) -> str | None:
    value = " ".join(parts).strip()
    return value or None


def _join_english_name(parts: list[str]) -> str | None:
    english_parts = []
    for text in parts:
        if TOTAL_RE.match(text) or _is_footer(text):
            break
        if CREDITS_RE.search(_compact_credit_text(text)):
            # `after` already starts *past* this course's own credits match
            # (see _course_from_text). A credits-pattern token found while
            # still walking `after` therefore belongs to a *different*
            # entry that bled into this block (usually because an
            # intermediate course code failed OCR detection) -- stop here
            # instead of skipping past it and continuing to collect words.
            break
        if _looks_english(text):
            english_parts.append(text.strip())
        elif english_parts and re.fullmatch(r"\d{1,2}", text.strip()):
            # A lone 1-2 digit number right after English words is usually
            # a course-title suffix (e.g. "CALCULUS 1", "FOUNDATION ENGLISH 1"),
            # not unrelated numeric noise, so keep it.
            english_parts.append(text.strip())
        elif english_parts:
            # Any other non-English, non-numeric token ends the name run.
            break
    value = " ".join(english_parts).strip()
    value = re.sub(r"\s+", " ", value)
    return value.upper() if value else None


def _looks_english(text: str) -> bool:
    letters = re.findall(r"[A-Za-z]", text)
    digits = re.findall(r"[0-9]", text)
    if len(digits) >= 4:
        # A token with 4+ digits is almost certainly a stray/garbled course
        # code (e.g. "060464xx", a malformed elective-slot placeholder that
        # CODE_FIND_RE didn't match), not an English word -- never treat it
        # as part of a course name.
        return False
    return bool(letters) and len(letters) >= max(2, len(text.strip()) // 3)


def _is_footer(text: str) -> bool:
    return any(token in text for token in FOOTER_TOKENS)


def _clean_code(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()
