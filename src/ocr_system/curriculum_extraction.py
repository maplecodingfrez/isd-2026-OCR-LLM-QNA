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
    for page_index, page in enumerate(payload.get("pages", []), start=1):
        year, semester = _year_semester_for_page(page_index)
        courses.extend(_extract_page_courses(page, year=year, semester=semester))

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


def _year_semester_for_page(page_index: int) -> tuple[int | None, int | None]:
    sequence = {
        1: (1, 1),
        2: (1, 2),
        3: (2, 1),
        4: (2, 2),
        5: (3, 1),
        6: (3, 2),
        7: (4, 1),
    }
    return sequence.get(page_index, (None, None))


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
        courses.append(_course_from_text(code, block_text, year=year, semester=semester))

    return courses


def _trim_block_text(block_text: str) -> str:
    cut_positions = []

    total_match = TOTAL_RE.search(block_text)
    if total_match:
        cut_positions.append(total_match.start())

    for token in FOOTER_TOKENS:
        idx = block_text.find(token)
        if idx != -1:
            cut_positions.append(idx)

    if cut_positions:
        block_text = block_text[: min(cut_positions)]

    return block_text


def _course_from_text(code: str, block_text: str, year: int | None, semester: int | None) -> dict[str, Any]:
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
        "code": code,
        "name_th": name_th,
        "name_en": name_en,
        "credits": credits,
        "year": year,
        "semester": semester,
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
            continue
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
    return bool(letters) and len(letters) >= max(2, len(text.strip()) // 3)


def _is_footer(text: str) -> bool:
    return any(token in text for token in FOOTER_TOKENS)


def _clean_code(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()
