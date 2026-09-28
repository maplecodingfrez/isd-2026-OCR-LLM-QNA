"""Configuration for OCR System REST API based on ISD Chapter 10 concepts."""

import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class APISettings:
    api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")
    title: str = os.getenv("API_TITLE", "OCR System REST API")
    version: str = os.getenv("API_VERSION", "1.0.0")
    description: str = (
        "Production-style RESTful API for Thai-English OCR, document processing, "
        "and curriculum extraction following ISD Chapter 10 architecture."
    )
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "15"))
    allowed_extensions: tuple[str, ...] = (
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".tif",
    )
    temp_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / os.getenv("API_TEMP_DIR", "temp_uploads")
    )
    output_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / os.getenv("API_OUTPUT_DIR", "outputs")
    )
    default_engine: str = os.getenv("DEFAULT_OCR_ENGINE", "auto")
    host: str = os.getenv("API_HOST", "127.0.0.1")
    port: int = int(os.getenv("API_PORT", "8000"))
    cors_origins: tuple[str, ...] = ("*",)


settings = APISettings()
