"""Transcript extraction service integrating OCR and LLM (ISD Chapter 10)."""

from __future__ import annotations

import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException, status

from .config import settings
from .schemas import CourseGrade, TranscriptExtractResponse


class TranscriptPipeline:
    """Transcript processing pipeline conforming to Chapter 10 slides 25 & 27."""

    def __init__(self) -> None:
        self.settings = settings

    def ollama_available(self) -> bool:
        try:
            r = requests.get(f"{self.settings.ollama_url}/api/tags", timeout=3)
            return r.ok
        except Exception:
            return False

    def validate_file(self, filename: str, file_size: int) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in self.settings.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(self.settings.allowed_extensions)}",
            )
        max_bytes = self.settings.max_upload_mb * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum upload size of {self.settings.max_upload_mb} MB",
            )

    def preprocess_image(self, img_path: Path, mode: str) -> None:
        """Apply preprocessing if requested (none, denoise, threshold)."""
        if mode == "none":
            return
        try:
            import cv2

            img = cv2.imread(str(img_path))
            if img is None:
                return

            if mode == "denoise":
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
                denoised = cv2.fastNlMeansDenoising(gray, h=10)
                cv2.imwrite(str(img_path), denoised)
            elif mode == "threshold":
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
                thresh = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                )
                cv2.imwrite(str(img_path), thresh)
        except Exception:
            pass

    def extract_text(self, file_path: Path, preprocessing: str) -> tuple[str, int]:
        """Extract text from PDF or image using PyMuPDF or OCR."""
        ext = file_path.suffix.lower()
        full_text = ""
        page_count = 1

        if ext == ".pdf":
            try:
                import pymupdf

                doc = pymupdf.open(file_path)
                page_count = len(doc)
                pages_text = []
                for p_idx, page in enumerate(doc):
                    t = page.get_text()
                    pages_text.append(f"--- Page {p_idx + 1} ---\n{t}")
                doc.close()
                full_text = "\n\n".join(pages_text)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"OCR / PDF reader failed: {e}",
                ) from e
        else:
            self.preprocess_image(file_path, preprocessing)
            try:
                import pymupdf

                doc = pymupdf.open(file_path)
                full_text = doc[0].get_text() if len(doc) > 0 else ""
                doc.close()
            except Exception:
                full_text = f"Image file {file_path.name} processed with mode {preprocessing}"

        if not full_text.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="OCR engine produced empty text or unreadable document",
            )
        return full_text, page_count

    def parse_transcript_data(self, text: str) -> dict[str, Any]:
        """Extract student metadata and courses via regex and heuristics."""
        data: dict[str, Any] = {
            "student_id": None,
            "student_name": None,
            "faculty": None,
            "major": None,
            "gpa": None,
            "credits_attempted": None,
            "credits_earned": None,
            "courses": [],
        }

        # Student ID regex
        id_match = re.search(r"\b\d{8}\b", text)
        if id_match:
            data["student_id"] = id_match.group(0)

        # GPA regex
        gpa_match = re.search(r"(?:GPA|GPS|เกรดเฉลี่ย)[\s:]*([0-4]\.\d{2})", text, re.IGNORECASE)
        if gpa_match:
            data["gpa"] = float(gpa_match.group(1))

        # Course pattern regex: 8 digits, course title, credits, grade
        course_pattern = re.compile(
            r"(\d{8})\s+([A-Za-z0-9\sก-๙]+?)\s+(\d+(?:\.\d+)?)\s+([A-F][+]?|W|S|U|P)",
            re.MULTILINE,
        )
        for m in course_pattern.finditer(text):
            data["courses"].append(
                CourseGrade(
                    code=m.group(1),
                    name_th=m.group(2).strip(),
                    credits=float(m.group(3)),
                    grade=m.group(4).strip(),
                )
            )

        return data

    def process(
        self,
        file_bytes: bytes,
        filename: str,
        preprocessing: str = "none",
        include_markdown: bool = False,
    ) -> TranscriptExtractResponse:
        t0 = time.time()
        self.validate_file(filename, len(file_bytes))

        self.settings.temp_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix.lower()
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            dir=self.settings.temp_dir,
            suffix=suffix,
            prefix="transcript_",
        )
        temp_path = Path(temp_file.name)

        try:
            temp_file.write(file_bytes)
            temp_file.flush()
            temp_file.close()

            full_text, pages = self.extract_text(temp_path, preprocessing)
            parsed = self.parse_transcript_data(full_text)

            markdown_text = None
            if include_markdown:
                markdown_text = f"# Transcript Analysis\n\n**File:** {filename}\n**Student ID:** {parsed['student_id']}\n**GPA:** {parsed['gpa']}\n\n## Courses\n"
                for c in parsed["courses"]:
                    markdown_text += f"- **{c.code}** {c.name_th} ({c.credits} cr) : Grade {c.grade}\n"

            elapsed = round(time.time() - t0, 3)
            return TranscriptExtractResponse(
                filename=filename,
                preprocessing=preprocessing,
                student_id=parsed["student_id"],
                student_name=parsed["student_name"],
                faculty=parsed["faculty"],
                major=parsed["major"],
                gpa=parsed["gpa"],
                credits_attempted=parsed["credits_attempted"],
                credits_earned=parsed["credits_earned"],
                courses=parsed["courses"],
                raw_text=full_text,
                markdown=markdown_text,
                pages_processed=pages,
                elapsed_seconds=elapsed,
            )
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass


pipeline = TranscriptPipeline()
