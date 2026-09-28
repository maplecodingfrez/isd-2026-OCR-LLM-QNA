"""Transcript App HTTP request and response schemas (ISD Chapter 10)."""

from typing import Any
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response format from ISD Chapter 10 slide 16."""
    status: int
    error: str
    message: str
    detail: Any | None = None


class HealthResponse(BaseModel):
    """Health check response for Transcript App (Chapter 10 slide 27)."""
    status: str
    ocr_model: str
    text_model: str
    max_upload_mb: int
    allowed_extensions: list[str]
    ollama_ready: bool
    ocr_ready: bool


class CourseGrade(BaseModel):
    code: str | None = None
    name_th: str | None = None
    name_en: str | None = None
    credits: float | None = None
    grade: str | None = None


class TranscriptExtractResponse(BaseModel):
    """Structured transcript output (Chapter 10 slide 27)."""
    filename: str
    preprocessing: str
    student_id: str | None = None
    student_name: str | None = None
    faculty: str | None = None
    major: str | None = None
    gpa: float | None = None
    credits_attempted: float | None = None
    credits_earned: float | None = None
    courses: list[CourseGrade] = []
    raw_text: str | None = None
    markdown: str | None = None
    pages_processed: int = 1
    elapsed_seconds: float = 0.0
