"""Course display metadata from existing SQLite values, without guessing hours."""

import re


def add_course_display(conn, rows):
    if not rows:
        return
    codes = sorted({row.get("code") for row in rows if row.get("code")})
    if not codes:
        return
    records = {row["code"]: dict(row) for row in conn.execute(
        "SELECT * FROM course WHERE code IN (" + ",".join("?" for _ in codes) + ")", codes)}
    for row in rows:
        course = records.get(row.get("code"))
        if not course:
            continue
        row.setdefault("name_en", course.get("name_en"))
        row.setdefault("credits", course.get("credits"))
        hours = [course.get(key) for key in ("lecture_h", "lab_h", "self_h")]
        if row.get("credits") == course.get("credits") and all(isinstance(h, int) and h >= 0 for h in hours):
            row.setdefault("credits_display", f"{row['credits']} ({hours[0]}-{hours[1]}-{hours[2]})")


def format_course_answer(conn, result):
    """Enrich course-list answers only; keep totals, explanations and routing intact."""
    rows = [row for row in result.get("rows", [])
            if row.get("code")
            and (row.get("name_th") or row.get("course_name_th"))]
    if not rows or not result.get("answer") or result.get("error"):
        return
    add_course_display(conn, rows)
    answer = result["answer"]
    for row in rows:
        if row.get("credits") is None:
            continue
        name = row.get("course_name_th") or row.get("name_th")
        english = row.get("course_name_en") or row.get("name_en")
        title = str(row["code"]) + " " + name
        english_part = r"(?:\s+(?:/\s*)?" + re.escape(english) + r")?" if english else ""
        pattern = (r"(?<!\d)" + re.escape(str(row["code"])) + r"\s+" + re.escape(name)
                   + english_part + r"(?!\w)(?:\s*(?:[:—–-]\s*)?" + re.escape(str(row["credits"]))
                   + r"(?!\d)(?:\s*\(\d+-\d+-\d+\)(?:\s+หรือ\s+\d+\s*\(\d+-\d+-\d+\))*)?"
                   + r"(?:\s*หน่วยกิต)?)?")

        def replace(match):
            # OCR plan labels can list alternative hour structures; retain them.
            full = re.search(r"\d+\s*\(\d+-\d+-\d+\)(?:\s+หรือ\s+\d+\s*\(\d+-\d+-\d+\))*", match.group())
            credits = full.group() if full else row.get("credits_display", str(row["credits"]))
            return title + (" / " + english if english else "") + " — " + credits + " หน่วยกิต"

        answer = re.sub(pattern, replace, answer)
    result["answer"] = answer
