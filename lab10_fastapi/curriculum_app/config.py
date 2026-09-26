"""Curriculum App configuration loaded from curriculum_app/.env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]
load_dotenv(APP_DIR / ".env")

PROGRAMS = {
    "ait": ("AIT", "Lab7B_Lab8B_ocr_system/runs/AIT/lab8b_output/curriculum.db"),
    "bit_no_coop": ("BIT ไม่สหกิจ", "Lab7B_Lab8B_ocr_system/runs/BIT/no_coop/lab8b_output/curriculum.db"),
    "bit_coop": ("BIT สหกิจ", "Lab7B_Lab8B_ocr_system/runs/BIT/coop/lab8b_output/curriculum.db"),
    "dsba_no_coop": ("DSBA ไม่สหกิจ", "Lab7B_Lab8B_ocr_system/runs/DSBA/no_coop/lab8b_output/curriculum.db"),
    "dsba_coop": ("DSBA สหกิจ", "Lab7B_Lab8B_ocr_system/runs/DSBA/coop/lab8b_output/curriculum.db"),
    "it_no_coop": ("IT ไม่สหกิจ", "Lab7B_Lab8B_ocr_system/runs/IT/no_coop/lab8b_output/curriculum.db"),
    "it_coop": ("IT สหกิจ", "Lab7B_Lab8B_ocr_system/runs/IT/coop/lab8b_output/curriculum.db"),
}

def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("CURRICULUM_APP_NAME", "Curriculum Book Assistant")
    db_path: Path = _project_path(
        os.getenv("CURRICULUM_DB_PATH", "work/lab8b_run/curriculum.db")
    )
    ollama_url: str = os.getenv("CURRICULUM_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("CURRICULUM_OLLAMA_MODEL", "qwen3:4b")
    request_timeout: int = int(os.getenv("CURRICULUM_REQUEST_TIMEOUT", "180"))
    max_rows: int = int(os.getenv("CURRICULUM_MAX_ROWS", "100"))


settings = Settings()

def program_db_path(program: str | None) -> Path | None:
    """ชื่อหลักสูตร -> path ของ DB
    None (ไม่ได้ระบุ) = ใช้ค่าจาก .env · ชื่อที่ไม่มีใน PROGRAMS = คืน None"""
    if program is None:
        return settings.db_path
    if program not in PROGRAMS:
        return None
    return _project_path(PROGRAMS[program][1])

