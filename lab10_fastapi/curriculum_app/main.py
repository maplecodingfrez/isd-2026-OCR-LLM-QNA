"""Application 1: curriculum database question answering."""

import json
import os
import sqlite3
import sys
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_ROOT, settings, PROGRAMS, _project_path, program_db_path

# เชื่อม Lab 10 -> Lab 8B โดยตรง: ใช้ open_db, guard_sql และ ollama_generate เดิม
LAB8_DIR = PROJECT_ROOT / "Lab7B_Lab8B_ocr_system" / "src" / "ocr_system"
if str(LAB8_DIR) not in sys.path:
    sys.path.insert(0, str(LAB8_DIR))
os.environ["LAB8_OLLAMA_URL"] = settings.ollama_url
os.environ["LAB8_MODEL_TEXT"] = settings.ollama_model
import lab8b_curriculum_db as lab8b  # noqa: E402

from .database import CurriculumDatabase  # noqa: E402
from .model_service import QwenTextToSQL  # noqa: E402
from .schemas import (  # noqa: E402
    AskRequest, AskResponse, CourseCreate, CourseResponse, HealthResponse, ProgramInfo,
)


STATIC_DIR = Path(__file__).resolve().parent / "static"
app = FastAPI(
    title=f"{settings.app_name} — Curriculum",
    description="Qwen text-to-SQL + SQLite curriculum application",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
database = CurriculumDatabase(lab8b, settings.db_path, settings.max_rows)
model = QwenTextToSQL(settings, lab8b)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> dict:
    db_ready = settings.db_path.exists()
    ollama_ready = model.available()
    return {
        "status": "ok" if db_ready and ollama_ready else "degraded",
        "database": str(settings.db_path),
        "database_ready": db_ready,
        "model": settings.ollama_model,
        "ollama_ready": ollama_ready,
        "lab8b_module": str(Path(lab8b.__file__).resolve()),
    }


@app.get("/api/program")
def get_program() -> dict:
    try:
        program = database.program()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if program is None:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลหลักสูตร")
    return program

@app.get("/api/programs", response_model=list[ProgramInfo])     
def list_programs() -> list[dict]:                                 
    items = []                                               
    for program_id, (label, rel_path) in PROGRAMS.items():         
        path = _project_path(rel_path)                          
        item = {"id": program_id, "label": label,                 
                "available": path.exists()}
        if item["available"]:                                    
            row = CurriculumDatabase(lab8b, path, settings.max_rows).program()   
            if row:                                                
                item["name_th"] = row.get("name_th")
                item["total_credits"] = row.get("total_credits")
                item["years"] = row.get("years")
        items.append(item)                                         
    return items                                                   

@app.get("/api/courses", response_model=list[CourseResponse])
def get_courses(
    search: str = Query(default="", max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    try:
        return database.courses(search, limit, offset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/courses", response_model=CourseResponse,
          status_code=status.HTTP_201_CREATED)
def post_course(course: CourseCreate) -> dict:
    try:
        return database.create_course(course.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="รหัสวิชานี้มีอยู่แล้ว") from exc


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest) -> dict:
    db_path = program_db_path(request.program)
    if db_path is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบหลักสูตร '{request.program}' - ใช้ได้: {', '.join(PROGRAMS)}")
    if not db_path.exists():
        raise HTTPException(status_code=503, detail=f"ไม่พบฐานข้อมูล: {db_path}")
    conn = lab8b.open_db(str(db_path), readonly=True)
    try:
        result = lab8b.ask(conn, request.question, verbose=False)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="ติดต่อ Ollama ไม่ได้") from exc
    finally:
        conn.close()
    if result["error"]:
        raise HTTPException(status_code=422, detail=result["error"])
    result["program"] = request.program
    return result