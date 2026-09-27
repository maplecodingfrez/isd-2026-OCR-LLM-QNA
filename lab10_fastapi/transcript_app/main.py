"""Application 2: transcript extraction API (ISD Chapter 10 slides 25 & 27)."""

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .pipeline_service import pipeline
from .schemas import HealthResponse, TranscriptExtractResponse

STATIC_DIR = Path(__file__).resolve().parent / "static"
app = FastAPI(
    title=f"{settings.app_name} — Transcript",
    description="Transcript OCR extraction application following ISD Chapter 10",
    version="1.0.0",
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> dict:
    """Check transcript app status and configured models (Chapter 10 slide 27)."""
    ollama_ready = pipeline.ollama_available()
    return {
        "status": "ok" if ollama_ready else "degraded",
        "ocr_model": settings.ocr_model,
        "text_model": settings.text_model,
        "max_upload_mb": settings.max_upload_mb,
        "allowed_extensions": list(settings.allowed_extensions),
        "ollama_ready": ollama_ready,
        "ocr_ready": True,
    }


@app.post(
    "/api/transcript/extract",
    response_model=TranscriptExtractResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_transcript(
    file: Annotated[UploadFile, File(description="Transcript file (PDF, PNG, JPG, TIFF)")],
    preprocessing: Annotated[str, Form(description="Preprocessing mode: none, denoise, threshold")] = "none",
    include_markdown: Annotated[bool, Form(description="Include markdown formatted summary")] = False,
) -> TranscriptExtractResponse:
    """Extract student and course info from uploaded transcript (Chapter 10 slide 27)."""
    filename = file.filename or "transcript.pdf"
    file_bytes = await file.read()

    return pipeline.process(
        file_bytes=file_bytes,
        filename=filename,
        preprocessing=preprocessing,
        include_markdown=include_markdown,
    )
