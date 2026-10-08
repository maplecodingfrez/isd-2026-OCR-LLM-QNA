"""Service and business logic for OCR REST API.

Implements:
- Temporary file management with guaranteed cleanup (Chapter 10 slide 27)
- File validation for media type (HTTP 415) and file size (HTTP 413)
- Multi-field sorting and filtering (Chapter 10 slides 11-13)
- Decoupled integration with ocr_system pipeline
"""

from __future__ import annotations

import datetime
import logging
import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from .config import settings
from .schemas import (
    DocumentDetailResponse,
    DocumentItemSummary,
    OCRLineSchema,
    OCRPageSchema,
)


logger = logging.getLogger(__name__)


def _pdf_page_texts(path: Path) -> list[str]:
    import pymupdf
    # Opening bytes avoids leaked OS handles if parser initialization fails.
    with pymupdf.open(stream=path.read_bytes(), filetype='pdf') as document:
        if not document.is_pdf or document.needs_pass or not len(document):
            raise ValueError('Unreadable PDF')
        return [page.get_text() for page in document]


def _validate_document(path: Path) -> None:
    try:
        if path.suffix.lower() == '.pdf':
            _pdf_page_texts(path)
        else:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
    except Exception as exc:
        logger.exception('Document validation failed')
        raise HTTPException(status_code=422, detail='Document could not be read') from exc


def _extract_complete_pdf_text(path: Path) -> list[str] | None:
    texts = _pdf_page_texts(path)
    return texts if texts and all(text.strip() for text in texts) else None


def _text_pages(texts: list[str]) -> tuple[str, list[OCRPageSchema]]:
    full_text = '\n\n'.join(f'--- Page {i+1} ---\n{text}' for i, text in enumerate(texts))
    pages = [OCRPageSchema(page=i+1, text=text, lines=[
        OCRLineSchema(text=line.strip(), page=i+1)
        for line in text.splitlines() if line.strip()])
        for i, text in enumerate(texts)]
    return full_text, pages


class DocumentRepository:
    """Thread-safe in-memory store for document OCR results."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._docs: dict[str, DocumentDetailResponse] = {}

    def add(self, doc: DocumentDetailResponse) -> None:
        with self._lock:
            self._docs[doc.doc_id] = doc

    def get(self, doc_id: str) -> DocumentDetailResponse | None:
        with self._lock:
            return self._docs.get(doc_id)

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id in self._docs:
                del self._docs[doc_id]
                return True
            return False

    def list(
        self,
        engine: str | None = None,
        status_filter: str | None = None,
        sort: str = "desc",
        sort_fields: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DocumentItemSummary], int]:
        """Filter, sort, and paginate stored document results."""
        with self._lock:
            items = list(self._docs.values())

        # Filtering (Chapter 10 slides 11-12)
        if engine:
            items = [d for d in items if d.engine.lower() == engine.lower()]
        if status_filter:
            items = [d for d in items if d.status.lower() == status_filter.lower()]

        # Sorting (Chapter 10 slide 13)
        sort_fields = sort_fields or ["created_at"]
        reverse = sort.lower() == "desc"

        def sort_key(doc: DocumentDetailResponse) -> tuple:
            keys = []
            for f in sort_fields:
                val = getattr(doc, f, None)
                if val is None:
                    val = doc.metadata.get(f, "")
                keys.append(val or "")
            return tuple(keys)

        items.sort(key=sort_key, reverse=reverse)

        total = len(items)
        paginated = items[offset : offset + limit]

        summaries = [
            DocumentItemSummary(
                doc_id=d.doc_id,
                filename=d.filename,
                engine=d.engine,
                status=d.status,
                page_count=d.page_count,
                created_at=d.created_at,
                preview_text=(d.full_text[:120] + "...") if len(d.full_text) > 120 else d.full_text,
            )
            for d in paginated
        ]
        return summaries, total


repository = DocumentRepository()


class OCRService:
    """Manages document validation, temporary file lifecycle, and OCR execution."""

    @staticmethod
    def validate_file(filename: str, file_size: int) -> None:
        """Validate media type and size constraints according to Chapter 10."""
        ext = Path(filename).suffix.lower()
        if ext not in settings.allowed_extensions:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(settings.allowed_extensions)}",
            )

        max_bytes = settings.max_upload_mb * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum allowed size of {settings.max_upload_mb} MB",
            )

    @classmethod
    def process_document(
        cls,
        file_bytes: bytes,
        filename: str,
        engine: str = "ensemble",
        paddle_lang: str = "th",
        languages: str = "tha+eng",
        preprocess: bool = True,
        deskew: bool = True,
        dpi: int = 300,
        min_confidence: float = 0.0,
        extract_fields: bool = True,
    ) -> DocumentDetailResponse:
        """Process document file bytes via OCR pipeline with safe cleanup."""
        cls.validate_file(filename, len(file_bytes))

        doc_id = str(uuid.uuid4())
        settings.temp_dir.mkdir(parents=True, exist_ok=True)

        temp_suffix = Path(filename).suffix.lower()
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            dir=settings.temp_dir,
            suffix=temp_suffix,
            prefix=f"doc_{doc_id}_",
        )
        temp_path = Path(temp_file.name)

        try:
            temp_file.write(file_bytes)
            temp_file.flush()
            temp_file.close()

            _validate_document(temp_path)
            pages_schemas: list[OCRPageSchema] = []
            full_text = ''
            extracted_fields: dict[str, Any] = {}
            page_texts = (_extract_complete_pdf_text(temp_path)
                          if engine == 'auto' and temp_suffix == '.pdf' else None)
            if page_texts is not None:
                full_text, pages_schemas = _text_pages(page_texts)
            else:
                try:
                    from ..config import OCRConfig
                    from ..pipeline import run_ocr
                    cfg = OCRConfig(
                        input_path=temp_path,
                        output_dir=settings.output_dir / 'api_runs' / doc_id,
                        engine='paddle' if engine == 'auto' else engine,
                        languages=languages, paddle_lang=paddle_lang, dpi=dpi,
                        preprocess=preprocess, deskew=deskew,
                        min_confidence=min_confidence, workers=1,
                    )
                    doc_result = run_ocr(cfg)
                except Exception as engine_error:
                    logger.exception('OCR processing failed')
                    try:
                        page_texts = (_extract_complete_pdf_text(temp_path)
                                      if temp_suffix == '.pdf' else None)
                    except Exception:
                        logger.exception('PDF text fallback failed')
                        page_texts = None
                    if page_texts is None:
                        raise HTTPException(status_code=503,
                            detail='OCR engine could not process this document') from engine_error
                    full_text, pages_schemas = _text_pages(page_texts)
                else:
                    full_text = doc_result.text
                    pages_schemas = [OCRPageSchema(
                        page=page.page, text=page.text, image_path=page.image_path,
                        lines=[OCRLineSchema(text=line.text, confidence=line.confidence,
                            box=line.box, page=line.page) for line in page.lines])
                        for page in doc_result.pages]
            if extract_fields:
                from ..field_extraction import extract_common_fields
                extracted_fields = extract_common_fields(full_text)

            detail = DocumentDetailResponse(
                doc_id=doc_id,
                filename=filename,
                engine=engine,
                status="completed",
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                page_count=len(pages_schemas),
                full_text=full_text,
                pages=pages_schemas,
                extracted_fields=extracted_fields,
                metadata={
                    "filesize_bytes": len(file_bytes),
                    "preprocess": preprocess,
                    "deskew": deskew,
                    "dpi": dpi,
                },
            )
            repository.add(detail)
            return detail

        finally:
            temp_file.close()
            # Temporary file cleanup (Chapter 10 slide 27)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
