"""Curriculum App HTTP request and response schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ช่องที่มาจาก DB ต้องให้เป็น None ได้ เพราะถ้าไม่มีไฟล์ DB จะอ่านค่าพวกนี้ไม่ได้
class ProgramInfo(BaseModel):
    id: str                             # คีย์ใน PROGRAMS dict
    label: str                          # ชื่อที่โชว์ใน dropdown
    name_th: str | None = None          # จากตาราง program ใน DB
    total_credits: int | None = None    # จากตาราง program ใน DB
    years: int | None = None            # จากตาราง program ใน DB
    available: bool                     # มีไฟล์ DB หรือไม่

class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    program: str | None = None


class AskResponse(BaseModel):
    question: str
    program: str | None = None
    sql: str | None = None
    rows: list[dict[str, Any]]
    answer: str
    citations: list[dict[str, Any]] = []
    citation_text: str = ""
    answer_type: Literal["database", "rule", "ocr", "ai", "hybrid", "course_overview"] | None = None
    processing_seconds: float | None = None


class CourseCreate(BaseModel):
    code: str = Field(pattern=r"^\d{8}$")
    name_th: str = Field(min_length=1, max_length=300)
    name_en: str | None = Field(default=None, max_length=300)
    credits: int = Field(ge=0, le=12)
    lecture_h: int | None = Field(default=None, ge=0, le=60)
    lab_h: int | None = Field(default=None, ge=0, le=60)
    self_h: int | None = Field(default=None, ge=0, le=60)
    description_th: str | None = None


class CourseResponse(CourseCreate):
    pass


class CourseSearchItem(BaseModel):
    """A course found by GET /api/courses. `source` says which table named it: plan (placed in the plan),
    elective (an elective or general-education group) or catalog (only described in the book)."""
    code: str
    name_th: str | None = None
    name_en: str | None = None
    credits: int | None = None
    lecture_h: int | None = None
    lab_h: int | None = None
    self_h: int | None = None
    description_th: str | None = None
    source: Literal["plan", "elective", "catalog"] = "plan"


class SampleExample(BaseModel):
    label_th: str
    label_en: str
    th: str
    en: str
    needs_model: bool = False        # True = the answer uses the language model (slower, a little less predictable)


class SampleTopic(BaseModel):
    key: Literal["credits", "term", "course", "prereq", "withdraw", "compare"]
    examples: list[SampleExample]


class SampleQuestionsResponse(BaseModel):
    topics: list[SampleTopic]


class HealthResponse(BaseModel):
    status: str
    database: str
    database_ready: bool
    model: str
    ollama_ready: bool
    lab8b_module: str


class PrerequisiteItem(BaseModel):
    code: str
    name_th: str | None = None
    name_en: str | None = None
    credits: int | None = None
    credits_display: str | None = None
    kind: str = "pre"
    alternative_group: int | None = None


class CoursePrerequisitesResponse(BaseModel):
    code: str
    name_th: str
    name_en: str | None = None
    credits: int | None = None
    credits_display: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    prerequisite_status: Literal['found', 'none', 'not_found', 'unreadable', 'unknown', 'not_in_plan'] = 'unknown'
    prerequisites_required: list[PrerequisiteItem] = Field(
        default_factory=list,
        description="รายวิชาที่ต้องเรียนผ่านก่อน จึงจะสามารถลงเรียนวิชานี้ได้"
    )
    unlocked_courses: list[PrerequisiteItem] = Field(
        default_factory=list,
        description="รายวิชาที่จะปลดล็อคให้ลงเรียนได้หลังจากเรียนผ่านวิชานี้"
    )



