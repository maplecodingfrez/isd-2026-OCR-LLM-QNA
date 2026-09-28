"""Pydantic schemas for the OCR System REST API.

Follows ISD Chapter 10 specification:
- Uniform error schema with status, error, and message (Slide 16)
- Resource metadata responses (Slide 18)
- Filtering and sorting parameter validation (Slides 11-13)
- Health check schema (Slides 26-27)
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standardized error response matching ISD Chapter 10 slide 16."""
    status: int = Field(..., description="HTTP status code")
    error: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable explanation of error")
    detail: Any | None = Field(default=None, description="Optional extra error details or validation breakdown")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": 400,
                "error": "InvalidFileFormat",
                "message": "Only PDF, PNG, JPG, and TIFF formats are supported",
                "detail": None,
            }
        }
    }


class APIInfoResponse(BaseModel):
    """Root metadata for API version discovery (Chapter 10 slide 18)."""
    name: str
    version: str
    description: str
    resources: list[str]
    docs_url: str


class HealthResponse(BaseModel):
    """System health check response (Chapter 10 slides 26 & 27)."""
    status: Literal["ok", "degraded"]
    timestamp: str
    supported_engines: list[str]
    default_engine: str
    max_upload_mb: int
    allowed_extensions: list[str]
    pipeline_ready: bool


class OCRLineSchema(BaseModel):
    text: str
    confidence: float | None = None
    box: Any | None = None
    page: int | None = None


class OCRPageSchema(BaseModel):
    page: int
    text: str
    lines: list[OCRLineSchema] = []
    image_path: str | None = None


class DocumentItemSummary(BaseModel):
    doc_id: str
    filename: str
    engine: str
    status: str
    page_count: int
    created_at: str
    preview_text: str


class DocumentListResponse(BaseModel):
    items: list[DocumentItemSummary]
    total: int
    limit: int
    offset: int
    sort: str
    sort_fields: list[str]


class DocumentDetailResponse(BaseModel):
    doc_id: str
    filename: str
    engine: str
    status: str
    created_at: str
    page_count: int
    full_text: str
    pages: list[OCRPageSchema] = []
    extracted_fields: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class CurriculumExtractRequest(BaseModel):
    program: str = Field(default="DSBA", description="Academic program code (e.g. DSBA, IT, BIT, AIT)")
    plan: str = Field(default="no_coop", description="Study plan (coop or no_coop)")
    payload: dict[str, Any] = Field(..., description="OCR JSON payload containing 'pages' list")


class CurriculumExtractResponse(BaseModel):
    program: str
    plan: str
    total_courses: int
    courses: list[dict[str, Any]]
