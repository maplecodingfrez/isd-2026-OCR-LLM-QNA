"""Curriculum App HTTP request and response schemas."""

from typing import Any

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


class HealthResponse(BaseModel):
    status: str
    database: str
    database_ready: bool
    model: str
    ollama_ready: bool
    lab8b_module: str

