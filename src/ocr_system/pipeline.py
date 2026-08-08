import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2
from .config import OCRConfig
from .document_loader import load_document_pages
from .engine_factory import build_engine
from .preprocessing import read_image, preprocess_image, save_debug_image
from .schemas import OCRDocumentResult, OCRPageResult
from .utils.io import ensure_dir, save_json, save_text

def _rows_from_lines(lines, y_tolerance: int = 8) -> str:
    items = []
    for line in lines:
        if not line.text.strip():
            continue
        box = line.box
        if box:
            xs = [p[0] for p in box if len(p) >= 2]
            ys = [p[1] for p in box if len(p) >= 2]
            x = min(xs) if xs else 0
            y = min(ys) if ys else 0
        else:
            x, y = 0, 0
        items.append((y, x, line.text))

    items.sort(key=lambda t: (t[0], t[1]))

    rows = []
    for item in items:
        if rows and abs(item[0] - rows[-1][-1][0]) <= y_tolerance:
            rows[-1].append(item)
        else:
            rows.append([item])

    row_texts = []
    for row in rows:
        row_sorted = sorted(row, key=lambda t: t[1])
        row_texts.append(" ".join(t[2] for t in row_sorted))
    return "\n".join(row_texts)

def _process_page(config: OCRConfig, engine, output_dir: Path, page_no: int, image_path: Path) -> OCRPageResult:
    image = read_image(image_path)
    if config.preprocess:
        image_for_ocr = preprocess_image(image, deskew=config.deskew)
        if config.save_debug_images:
            debug_path = output_dir / "debug" / f"page_{page_no:03d}_preprocessed.png"
            save_debug_image(image_for_ocr, debug_path)
    else:
        image_for_ocr = image

    lines = engine.recognize(image_for_ocr, page=page_no)
    if config.min_confidence > 0:
        lines = [x for x in lines if x.confidence is None or x.confidence >= config.min_confidence]

    text = "\n".join(line.text for line in lines if line.text.strip())
    return OCRPageResult(page=page_no, text=text, lines=lines, image_path=str(image_path))


def run_ocr(config: OCRConfig) -> OCRDocumentResult:
    output_dir = ensure_dir(config.output_dir)
    page_dir = ensure_dir(config.page_image_dir)
    pages = load_document_pages(config.input_path, page_dir, dpi=config.dpi, thread_count=config.workers)
    engine = build_engine(config)

    if config.workers > 1:
        # Each engine.recognize() call for Tesseract spawns its own OS
        # process and, by default, lets that process use every core for its
        # internal OpenMP threading. Running many pages at once on top of
        # that oversubscribes the CPU (N page-workers x M threads each) and
        # ends up *slower* than sequential. Capping each Tesseract process to
        # 1 internal thread and parallelizing across pages instead uses the
        # same total CPU budget far more effectively for a many-page,
        # independent-per-page workload like this one. Only set when workers
        # > 1 so single-worker runs keep Tesseract's own default threading
        # untouched (identical behavior to before this change).
        os.environ.setdefault("OMP_THREAD_LIMIT", "1")

    if config.workers > 1:
        with ThreadPoolExecutor(max_workers=config.workers) as pool:
            futures = [
                pool.submit(_process_page, config, engine, output_dir, page_no, image_path)
                for page_no, image_path in enumerate(pages, start=1)
            ]
            page_results = [f.result() for f in futures]
    else:
        page_results = [
            _process_page(config, engine, output_dir, page_no, image_path)
            for page_no, image_path in enumerate(pages, start=1)
        ]
    # Threads can finish out of submission order; page_results must stay in
    # page order since downstream code (curriculum_extraction.py etc.) reads
    # "pages" as a plain list and relies on list position, not the "page"
    # field, in a couple of places.
    page_results.sort(key=lambda p: p.page)

    full_text = "\n\n".join(f"--- Page {p.page} ---\n{p.text}" for p in page_results)
    result = OCRDocumentResult(
        source_path=str(config.input_path),
        engine=engine.name,
        text=full_text,
        pages=page_results,
    )

    stem = Path(config.input_path).stem
    save_json(result.to_dict(), output_dir / f"{stem}_ocr.json")
    save_text(result.text, output_dir / f"{stem}_ocr.txt")
    return result
