"""English question -> the Thai question the shortcuts already answer.

The shortcuts in lab8b_curriculum_db.ask() recognise Thai wording, so an English question used to fall through to the
language model: "any database courses?" returned Calculus 2, and the withdrawal and co-op questions returned "not found".
Each template below recognises one English question shape and returns the Thai question that the existing pipeline
already answers deterministically, so English and Thai give the same answer. ask() keeps the user's own text in
result["question"]. Anything that is not a recognised template, and anything that already contains Thai, returns None
and goes the old way.

Course references stay as typed (a code, or an English name, which the Thai resolver already understands).
"""

import re

_THAI = re.compile(r"[฀-๿]")
_CODE = re.compile(r"\b\d{8}\b")
_NUMBER_WORDS = {"first": "1", "second": "2", "third": "3", "fourth": "4"}
_YEAR = re.compile(r"\b(?:year|yr)\s*([1-4])\b|\b([1-4])(?:st|nd|rd|th)\s+year\b|\b(first|second|third|fourth)\s+year\b", re.I)
_SEM = re.compile(r"\b(?:semester|sem|term)\s*([1-3])\b|\b([1-3])(?:st|nd|rd)\s+(?:semester|term)\b|\b(first|second)\s+(?:semester|term)\b", re.I)
_STOP = re.compile(r"\b(?:what|which|will|would|affect|affected|impact|happens?|if|does|do|is|are|can|how)\b", re.I)
def _search(pattern: str, text: str):
    return re.search(pattern, text, re.I)


# Topic words that appear in Thai course names; the Thai shortcut lists the matching courses with codes and credits.
# A topic that is not here stays as typed (the course-name resolver still understands English words).
_TOPICS = {
    "database": "ฐานข้อมูล", "databases": "ฐานข้อมูล", "network": "เครือข่าย", "networks": "เครือข่าย", "networking": "เครือข่าย",
    "statistics": "สถิติ", "statistic": "สถิติ", "machine learning": "การเรียนรู้ของเครื่อง", "artificial intelligence": "ปัญญาประดิษฐ์",
    "ai": "ปัญญาประดิษฐ์", "web": "เว็บ", "mathematics": "คณิตศาสตร์", "math": "คณิตศาสตร์", "maths": "คณิตศาสตร์",
    "english": "ภาษาอังกฤษ", "business": "ธุรกิจ", "project": "โครงงาน", "projects": "โครงงาน", "software": "ซอฟต์แวร์",
    "data": "ข้อมูล", "programming": "โปรแกรม", "security": "ความมั่นคง",
}


_GENERIC = {"program", "programme", "curriculum", "degree", "course", "courses", "subject", "subjects", "it", "this", "that", ""}


def _normalise(question: str) -> str:
    text = str(question or "")
    text = re.sub(r"[?!.,;:\"'“”‘’()]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _number(match) -> str | None:
    if not match:
        return None
    value = next((g for g in match.groups() if g), None)
    return _NUMBER_WORDS.get(value.casefold(), value)


def _ref(text: str, phrase: str = "") -> str:
    """The course the question is about: an 8-digit code anywhere, else the (trimmed) phrase."""
    code = _CODE.search(text)
    if code:
        return code.group(0)
    phrase = re.sub(r"^(?:the )?(?:course |subject )?", "", phrase.strip())
    cut = _STOP.search(phrase)
    if cut:
        phrase = phrase[:cut.start()]
    return phrase.strip()


def _wants_list(text: str) -> bool:
    return bool(_search(r"\b(?:what|which|list|show|name|tell)\b", text))


def english_to_thai(question: str) -> str | None:
    """The Thai question that the existing shortcuts answer for this English question, or None."""
    if not question or _THAI.search(question):
        return None
    t = _normalise(question)
    if not t:
        return None
    year, sem = _number(_YEAR.search(t)), _number(_SEM.search(t))
    low = t.casefold()
    credit = "credit" in low

    # withdrawing from a course
    m = _search(r"\b(?:withdraw(?:ing)?|drop(?:ping)?)\b(?: from| out of)?(.*)$", t)
    if m:
        ref = _ref(t, m.group(1))
        if ref and ref.casefold() not in _GENERIC:
            return f"ถ้าถอนวิชา {ref} จะกระทบกับอะไร"

    # follow-up courses
    if _search(r"follow[- ]?up|\b(?:take|taken|come|comes|go|go on) after\b|\bunlocks?\b|\bnext courses?\b", t):
        m = _search(r"\b(?:after|unlocks?)\b\s*(.*)$", t) or _search(r"\bdoes\b\s*(.+?)\s+(?:have|has)\b", t)
        ref = _ref(t, m.group(1) if m else "")
        if ref and ref.casefold() not in _GENERIC:
            return f"วิชา {ref} มีวิชาต่อไหม"

    # courses that need a given course first
    m = _search(r"\b(?:which|what) (?:courses?|subjects?) (?:require|requires|need|needs|depend on|have)\s+(.+?)(?: first| as an? prerequisite| as prerequisite)?$", t)
    if m and (_CODE.search(t) or "prerequisite" in low or low.endswith(" first")):
        ref = _ref(t, m.group(1))
        if ref and ref.casefold() not in _GENERIC:
            return f"วิชาที่ต้องผ่าน {ref} ก่อนมีอะไรบ้าง"

    # prerequisites of a course
    m = (_search(r"\bprerequisites?\b\s*(?:of|for|to)\s+(.+)$", t)
         or _search(r"\b(?:before taking|before)\s+(.+)$", t) if _search(r"prerequisite|before", t) else None)
    if m:
        ref = _ref(t, m.group(1))
        if ref and ref.casefold() not in _GENERIC:
            return f"วิชา {ref} ต้องผ่านวิชาใดก่อน"

    # co-op against non co-op
    if (_search(r"co-?op", t) and _search(r"non[- ]?co-?op|without co-?op|not co-?op|no co-?op", t)
            and _search(r"differ|difference|compare|comparison|versus|\bvs\b|between", t)):
        return "แผนสหกิจกับไม่สหกิจต่างกันอย่างไร"

    # free electives, then the elective list
    if "free elective" in low and _search(r"\b(?:which|what|when)\b", t):
        return "วิชาเลือกเสรีต้องลงตอนปีไหน"
    if _search(r"\belectives?\b", t) and _wants_list(t) and not year and not credit:
        return "วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง"

    # credits per category
    if credit and _search(r"\b(?:each|per|by)\b", t) and _search(r"categor|\bgroups?\b|\bsections?\b|\btypes?\b", t):
        return "หมวดวิชาเฉพาะเลือกเก็บกี่หน่วยกิต"

    # a year (and semester): courses and/or credits
    if year:
        asks_courses = bool(_search(r"course|subject|\btake\b|study|enrol|register|learn|\blist\b", t))
        if sem:
            if credit and asks_courses and _wants_list(t):
                return f"ปี {year} เทอม {sem} มีวิชาอะไรบ้าง และรวมกี่หน่วยกิต"
            if credit:
                return f"ปี {year} เทอม {sem} เรียนกี่หน่วยกิต"
            if asks_courses or _wants_list(t):
                return f"ปี {year} เทอม {sem} เรียนวิชาอะไรบ้าง"
        else:
            if credit and not asks_courses:
                return f"ปี {year} เรียนรวมกี่หน่วยกิต"
            if asks_courses and not credit:
                return f"ปี {year} เรียนวิชาอะไรบ้าง"
        return None

    # total credits of the program
    if credit and not _CODE.search(t) and _search(r"\b(?:total|whole|entire|overall|graduat\w*|program|programme|curriculum|degree)\b", t):
        return "หลักสูตรนี้มีหน่วยกิตรวมตลอดหลักสูตรกี่หน่วยกิต"

    # one course: credits, year and semester, code, name
    if credit:
        m = (_search(r"\bcredits?\b\s*(?:of|for)\s+(.+)$", t)
             or _search(r"\bhow many credits (?:does|is|are|do)\s+(.+?)(?: have| worth| carry| count)?$", t))
        if m:
            ref = _ref(t, m.group(1))
            if ref and ref.casefold() not in _GENERIC:
                return f"วิชา {ref} มีกี่หน่วยกิต"
    m = _search(r"\b(?:which|what) (?:year|semester|term)\b.*?\b(?:is|take|taken|taught|offered|studied|study)\s+(.+?)(?: taught| offered| taken| studied)?$", t)
    if m:
        ref = _ref(t, m.group(1))
        if ref and ref.casefold() not in _GENERIC:
            return f"วิชา {ref} เรียนปีไหนเทอมไหน"
    # ("what is the course code of ..." is left alone: the pipeline has its own English handler for it)
    m = _search(r"\b(?:what is|whats) the name of\s+(.+)$", t) or _search(r"\bwhat is (?:course )?(\d{8})$", t)
    if m:
        ref = _ref(t, m.group(1))
        if ref and ref.casefold() not in _GENERIC:
            return f"วิชา {ref} ชื่ออะไร"

    # is there a course about a topic
    m = (_search(r"\b(?:are there|is there|do you have|do they have)\b (?:any |a )?(?:courses?|subjects?|classes) (?:about|on|in|related to|for)\s+(.+)$", t)
         or _search(r"\b(?:are there|is there|do you have|do they have)\b (?:any |a )?(.+?) (?:courses?|subjects?)$", t))
    if m:
        topic = re.sub(r"^(?:the )?", "", m.group(1).strip())
        if topic and topic.casefold() not in _GENERIC:
            thai = _TOPICS.get(topic.casefold())
            return f"มีวิชาเกี่ยวกับ{thai}ไหม" if thai else f"มีวิชาเกี่ยวกับ {topic} ไหม"
    return None
