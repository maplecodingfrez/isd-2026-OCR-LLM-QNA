"""RESTful API routes implementing ISD Chapter 10 design principles."""

import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)

from .config import settings
from .schemas import (
    APIInfoResponse,
    CurriculumExtractRequest,
    CurriculumExtractResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    ErrorResponse,
    HealthResponse,
)
from .service import OCRService, repository


router = APIRouter(
    prefix=settings.api_v1_prefix,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)


@router.get(
    "",
    summary="API Discovery and Version Metadata",
    description="Returns API name, version, and available resource endpoints (Chapter 10 slide 18).",
    response_model=APIInfoResponse,
    tags=["System"],
)
def api_root() -> APIInfoResponse:
    return APIInfoResponse(
        name=settings.title,
        version=settings.version,
        description=settings.description,
        resources=[
            f"{settings.api_v1_prefix}/health",
            f"{settings.api_v1_prefix}/ocr/process",
            f"{settings.api_v1_prefix}/documents",
            f"{settings.api_v1_prefix}/curriculum/extract",
        ],
        docs_url="/docs",
    )


@router.get(
    "/health",
    summary="System Health Check",
    description="Reports system status, engine configurations, and limits (Chapter 10 slides 26 & 27).",
    response_model=HealthResponse,
    tags=["System"],
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        supported_engines=["ensemble", "paddle", "tesseract", "trocr"],
        default_engine=settings.default_engine,
        max_upload_mb=settings.max_upload_mb,
        allowed_extensions=list(settings.allowed_extensions),
        pipeline_ready=True,
    )


@router.post(
    "/ocr/process",
    summary="Upload and Process Document OCR",
    description=(
        "Upload a document (PDF, PNG, JPG, TIFF) via multipart/form-data. "
        "Performs validation (415 on bad type, 413 on file too large), "
        "runs OCR, extracts common fields, cleans up temporary files, "
        "and returns HTTP 201 Created (Chapter 10 slides 26, 27 & 30)."
    ),
    response_model=DocumentDetailResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["OCR & Documents"],
)
async def process_document(
    file: Annotated[UploadFile, File(description="Document file (PDF, PNG, JPG, TIFF)")],
    engine: Annotated[str, Form(description="OCR Engine to use")] = settings.default_engine,
    paddle_lang: Annotated[str, Form(description="Language for PaddleOCR (e.g. th, en)")] = "th",
    languages: Annotated[str, Form(description="Languages for Tesseract (e.g. tha+eng)")] = "tha+eng",
    preprocess: Annotated[bool, Form(description="Apply image preprocessing")] = True,
    deskew: Annotated[bool, Form(description="Apply image deskewing")] = True,
    dpi: Annotated[int, Form(description="DPI for PDF rendering")] = 300,
    min_confidence: Annotated[float, Form(description="Minimum confidence filter (0.0 to 1.0)")] = 0.0,
    extract_fields: Annotated[bool, Form(description="Extract common regex fields (ID, date, etc.)")] = True,
) -> DocumentDetailResponse:
    filename = file.filename or "upload.bin"
    file_bytes = await file.read()

    detail = OCRService.process_document(
        file_bytes=file_bytes,
        filename=filename,
        engine=engine,
        paddle_lang=paddle_lang,
        languages=languages,
        preprocess=preprocess,
        deskew=deskew,
        dpi=dpi,
        min_confidence=min_confidence,
        extract_fields=extract_fields,
    )
    return detail


@router.get(
    "/documents",
    summary="List and Filter Processed Documents",
    description=(
        "Retrieve documents with query-based filtering and multi-field sorting "
        "(Chapter 10 slides 11-13)."
    ),
    response_model=DocumentListResponse,
    tags=["OCR & Documents"],
)
def list_documents(
    engine: Annotated[str | None, Query(description="Filter by OCR engine")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="Filter by status")] = None,
    sort: Annotated[str, Query(pattern="^(asc|desc)$", description="Sort direction (asc or desc)")] = "desc",
    sort_fields: Annotated[str, Query(description="Comma-separated fields to sort by (e.g. 'created_at,filename')")] = "created_at",
    limit: Annotated[int, Query(ge=1, le=100, description="Pagination limit")] = 20,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> DocumentListResponse:
    parsed_fields = [f.strip() for f in sort_fields.split(",") if f.strip()]
    items, total = repository.list(
        engine=engine,
        status_filter=status_filter,
        sort=sort,
        sort_fields=parsed_fields,
        limit=limit,
        offset=offset,
    )
    return DocumentListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort=sort,
        sort_fields=parsed_fields,
    )


@router.get(
    "/documents/{doc_id}",
    summary="Get Document OCR Result by ID",
    description="Retrieve full OCR results and extracted fields by document ID (returns HTTP 404 if not found).",
    response_model=DocumentDetailResponse,
    tags=["OCR & Documents"],
)
def get_document(
    doc_id: Annotated[str, Path(description="UUID of the processed document")]
) -> DocumentDetailResponse:
    doc = repository.get(doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' was not found",
        )
    return doc


@router.delete(
    "/documents/{doc_id}",
    summary="Delete Document Result",
    description="Removes document from the store. Returns HTTP 204 No Content on success (Chapter 10 slide 15).",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["OCR & Documents"],
)
def delete_document(
    doc_id: Annotated[str, Path(description="UUID of the document to delete")]
) -> None:
    deleted = repository.delete(doc_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' was not found",
        )


@router.post(
    "/curriculum/extract",
    summary="Extract Structured Curriculum Data",
    description="Extract course listings, categories, and prerequisites from OCR JSON payload.",
    response_model=CurriculumExtractResponse,
    tags=["Curriculum"],
)
def extract_curriculum_endpoint(
    req: CurriculumExtractRequest,
) -> CurriculumExtractResponse:
    try:
        from ..curriculum_extraction import extract_curriculum

        result = extract_curriculum(req.payload, program=req.program, plan=req.plan)
        courses = result.get("courses", [])
        return CurriculumExtractResponse(
            program=req.program,
            plan=req.plan,
            total_courses=len(courses),
            courses=courses,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract curriculum data: {exc}",
        ) from exc
