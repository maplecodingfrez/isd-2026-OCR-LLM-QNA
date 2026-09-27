"""Transcript App configuration loaded from transcript_app/.env."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]
load_dotenv(APP_DIR / ".env")


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv(
        "TRANSCRIPT_APP_NAME", "Transcript Information Extraction Assistant"
    )
    ollama_url: str = os.getenv("TRANSCRIPT_OLLAMA_URL", "http://127.0.0.1:11434")
    ocr_model: str = os.getenv(
        "TRANSCRIPT_OCR_MODEL", "scb10x/typhoon-ocr1.5-3b"
    )
    text_model: str = os.getenv("TRANSCRIPT_TEXT_MODEL", "qwen3:4b")
    max_upload_mb: int = int(os.getenv("TRANSCRIPT_MAX_UPLOAD_MB", "15"))
    temp_dir: Path = field(
        default_factory=lambda: _project_path(
            os.getenv("TRANSCRIPT_TEMP_DIR", "temp_uploads")
        )
    )
    allowed_extensions: tuple[str, ...] = (
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".tif",
    )


settings = Settings()
