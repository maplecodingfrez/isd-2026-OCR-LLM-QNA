"""Sample questions built from one plan's own database.

The page shows six topics with up to three example questions each. Every example is a fixed question shape whose blanks
(a course that really has a prerequisite, the course most others depend on ...) are filled from the plan's data, and an
example is only offered when the plan can answer it: no co-op comparison without a sibling plan, no free-elective
question without a free-elective slot, no general-education question without that credit group, and so on. A topic that
ends up with fewer than two examples is left out.

Each example carries its Thai and English wording (the English one is a shape english_questions understands) and
`needs_model`: True when the answer is produced with the language model (slower, a little less predictable), False when
it comes straight from the data.
"""

TOPIC_ORDER = ("credits", "term", "course", "prereq", "withdraw", "compare")
MAX_EXAMPLES = 3


def _example(label_th: str, label_en: str, th: str, en: str, needs_model: bool = False) -> dict:
    return {"label_th": label_th, "label_en": label_en, "th": th, "en": en, "needs_model": needs_model}


def _one(conn, sql: str, params: tuple = ()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _table_exists(conn, name: str) -> bool:
    return _one(conn, "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (name,)) is not None


def _facts(conn) -> dict:
    """What this plan's data can support, and the real courses to put in the blanks."""
    required = []
    pair_count = 0
    first_with_prereq = None
    if _table_exists(conn, "prerequisite"):
        pair_count = _one(conn, "SELECT COUNT(*) FROM prerequisite") or 0
        required = [r[0] for r in conn.execute(
            "SELECT requires FROM prerequisite WHERE requires IN (SELECT code FROM course) "
            "GROUP BY requires ORDER BY COUNT(*) DESC, requires").fetchall()]
        first_with_prereq = _one(
            conn, "SELECT code FROM prerequisite WHERE code IN (SELECT code FROM course) "
                  "AND requires IN (SELECT code FROM course) ORDER BY code LIMIT 1")
    named = None
    if _table_exists(conn, "v_plan"):
        row = conn.execute("SELECT code, name_en FROM v_plan WHERE year = 2 AND semester = 1 "
                           "AND name_en IS NOT NULL AND name_en <> '' ORDER BY code LIMIT 1").fetchone()
        named = (row[0], row[1]) if row else None
    return {
        "required": required,
        "pairs": pair_count,
        "with_prereq": first_with_prereq,
        "named": named,
        "has_lab": (_one(conn, "SELECT COUNT(*) FROM course WHERE lab_h > 2") or 0) > 0,
        "has_structure": _table_exists(conn, "credit_structure") and (_one(conn, "SELECT COUNT(*) FROM credit_structure") or 0) > 0,
        "has_ge": _table_exists(conn, "credit_structure")
                  and (_one(conn, "SELECT COUNT(*) FROM credit_structure WHERE name_th LIKE '%ศึกษาทั่วไป%'") or 0) > 0,
        "has_free": _table_exists(conn, "plan_slot")
                    and (_one(conn, "SELECT COUNT(*) FROM plan_slot WHERE name_th LIKE '%เสรี%'") or 0) > 0,
    }


def build_samples(conn, has_sibling: bool) -> list[dict]:
    """The topics (key plus 2-3 examples) that this plan's data can answer."""
    f = _facts(conn)
    topics: dict[str, list[dict]] = {}

    credits = [
        _example("หน่วยกิตรวมทั้งหลักสูตร", "Total credits",
                 "หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต", "How many credits in total does the program have?"),
        _example("หน่วยกิตรวมปี 3", "Year 3 credits", "ปี 3 เรียนรวมกี่หน่วยกิต", "How many credits in year 3?"),
    ]
    if f["has_ge"]:
        credits.append(_example("หน่วยกิตหมวดศึกษาทั่วไป", "General education credits",
                                "หมวดวิชาศึกษาทั่วไปต้องเรียนกี่หน่วยกิต", "How many credits does the general education category need?"))
    elif f["has_structure"]:
        credits.append(_example("หน่วยกิตแต่ละหมวดวิชา", "Credits per category",
                                "หมวดวิชาเฉพาะเลือกเก็บกี่หน่วยกิต", "How many credits are required in each course category?"))
    else:        # no credit structure in this plan's data (BIT): "per category" would only answer "no data"
        credits.append(_example("หน่วยกิตรวมปี 4", "Year 4 credits", "ปี 4 เรียนรวมกี่หน่วยกิต", "How many credits in year 4?"))
    topics["credits"] = credits

    topics["term"] = [
        _example("วิชาปี 2 เทอม 1", "Year 2 sem 1 courses", "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง", "What courses are in year 2 semester 1?"),
        _example("วิชาและหน่วยกิตปี 3 เทอม 1", "Year 3 sem 1 courses and credits",
                 "ปี 3 เทอม 1 มีวิชาอะไรบ้าง และรวมกี่หน่วยกิต", "What courses are in year 3 semester 1 and how many credits in total?"),
        _example("วิชาปี 4 เทอม 2", "Year 4 sem 2 courses", "ปี 4 เทอม 2 เรียนวิชาอะไรบ้าง", "What courses are in year 4 semester 2?"),
    ]

    course = [_example("วิชาฐานข้อมูล", "Database courses", "มีวิชาเกี่ยวกับฐานข้อมูลไหม", "Are there any database courses?", True)]
    if f["has_lab"]:
        course.append(_example("วิชาที่ปฏิบัติมากกว่า 2 ชม.", "Courses with over 2 lab hours",
                               "วิชาที่มีชั่วโมงปฏิบัติมากกว่า 2 ชั่วโมงมีอะไรบ้าง", "Which courses have more than 2 lab hours per week?"))
    if f["has_free"]:
        course.append(_example("ปีที่ลงวิชาเลือกเสรี", "When free electives are taken",
                               "วิชาเลือกเสรีต้องลงตอนปีไหน", "Which year do I take the free electives?"))
    if f["named"]:
        code, name_en = f["named"]
        course.append(_example(f"ปี/เทอมของ {name_en.title()}", f"When {name_en.title()} is taught",
                               f"วิชา {name_en} เรียนปีไหนเทอมไหน", f"Which year is {name_en} taught?"))
    topics["course"] = course[:MAX_EXAMPLES]

    if f["pairs"] > 0 and f["with_prereq"] and f["required"]:
        top = f["required"][0]
        topics["prereq"] = [
            _example(f"วิชาบังคับก่อนของ {f['with_prereq']}", f"Prerequisites of {f['with_prereq']}",
                     f"วิชา {f['with_prereq']} ต้องผ่านวิชาใดก่อน", f"What are the prerequisites of {f['with_prereq']}?", True),
            _example(f"วิชาที่ต้องผ่าน {top} ก่อน", f"Courses that need {top} first",
                     f"วิชาที่ต้องผ่าน {top} ก่อนมีอะไรบ้าง", f"Which courses require {top} first?", True),
            _example("จำนวนคู่วิชาบังคับก่อน", "How many prerequisite pairs",
                     "ในฐานข้อมูลนี้มีคู่วิชากับวิชาบังคับก่อนทั้งหมดกี่คู่", "How many prerequisite pairs are there in total?"),
        ]
        withdraw = [_example(f"ถอน {top} กระทบอะไร", f"Withdrawing {top}",
                             f"ถ้าถอนวิชา {top} จะกระทบกับอะไร", f"What is affected if I withdraw from {top}?")]
        if len(f["required"]) > 1:
            second = f["required"][1]
            withdraw.append(_example(f"ถอน {second} กระทบอะไร", f"Withdrawing {second}",
                                     f"ถ้าถอนวิชา {second} จะกระทบกับอะไร", f"What is affected if I withdraw from {second}?"))
        withdraw.append(_example(f"{top} มีวิชาต่อไหม", f"Follow-ups of {top}",
                                 f"วิชา {top} มีวิชาต่อไหม", f"Does {top} have follow-up courses?", True))
        topics["withdraw"] = withdraw[:MAX_EXAMPLES]

    if has_sibling:
        topics["compare"] = [
            _example("เปรียบเทียบแผนสหกิจ", "Co-op vs non co-op",
                     "แผนสหกิจกับไม่สหกิจต่างกันอย่างไร", "How do the co-op and non co-op plans differ?"),
            _example("ต่างกันใน ปี 4 เทอม 1", "Difference in year 4 sem 1",
                     "แผนสหกิจกับไม่สหกิจ ปี 4 เทอม 1 ต่างกันยังไง", "How do the co-op and non co-op plans differ in year 4 semester 1?"),
            _example("วิชาที่แผนไม่สหกิจเพิ่ม", "What the non co-op plan adds",
                     "แผนไม่สหกิจเรียนวิชาอะไรเพิ่มจากแผนสหกิจ", "What does the non co-op plan add compared with the co-op plan?"),
        ]

    return [{"key": key, "examples": topics[key]} for key in TOPIC_ORDER if len(topics.get(key, [])) >= 2]
