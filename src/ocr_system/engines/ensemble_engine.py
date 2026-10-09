import math

import numpy as np
from .base import BaseOCREngine
from .paddle_engine import PaddleOCREngine
from .tesseract_engine import TesseractOCREngine
from ocr_system.schemas import OCRLine


class EnsembleOCREngine(BaseOCREngine):
    name = "ensemble"

    def __init__(self, paddle_lang: str = "th", tesseract_languages: str = "tha+eng"):
        self.engines = [
            PaddleOCREngine(lang=paddle_lang),
            TesseractOCREngine(languages=tesseract_languages),
        ]

    def recognize(self, image: np.ndarray, page: int | None = None) -> list[OCRLine]:
        paddle_result = self.engines[0].recognize(image, page=page)
        tesseract_result = self.engines[1].recognize(image, page=page)

        return self.merge(
            paddle_result,
            tesseract_result=tesseract_result,
        )

    def merge(
        self,
        paddle_result: list[OCRLine],
        tesseract_result: list[OCRLine] | None = None,
        trocr_result: list[OCRLine] | None = None,
    ) -> list[OCRLine]:
        candidates: list[OCRLine] = []
        candidates.extend(paddle_result or [])
        candidates.extend(tesseract_result or [])
        candidates.extend(trocr_result or [])

        # Equal text is a duplicate only when it describes the same region.
        lines: list[OCRLine] = []
        regions: dict[tuple[str, int | None], list[int]] = {}
        boxes = []
        for line in candidates:
            text = line.text.strip()
            if not text:
                continue
            key = (text, line.page)
            bounds = _bounds(line.box)
            matched = None
            for index in regions.get(key, []):
                kept = boxes[index]
                if bounds is not None and kept is not None and _iou(bounds, kept) >= 0.5:
                    matched = index
                    break
            if matched is None:
                regions.setdefault(key, []).append(len(lines))
                lines.append(line)
                boxes.append(bounds)
            elif _confidence(line.confidence) > _confidence(lines[matched].confidence):
                lines[matched] = line
                boxes[matched] = bounds
        lines.sort(key=lambda line: _box_top(line.box))
        return lines


def _bounds(box) -> tuple[float, float, float, float] | None:
    if box is None:
        return None
    try:
        points = [(float(point[0]), float(point[1])) for point in box]
        if not points or not all(math.isfinite(value) for point in points for value in point):
            return None
        xs, ys = zip(*points)
        bounds = (min(xs), min(ys), max(xs), max(ys))
        return bounds if bounds[2] > bounds[0] and bounds[3] > bounds[1] else None
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _iou(a, b) -> float:
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, right-left) * max(0.0, bottom-top)
    area_a = (a[2]-a[0]) * (a[3]-a[1])
    area_b = (b[2]-b[0]) * (b[3]-b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _confidence(value) -> float:
    try:
        score = float(value)
        return score if math.isfinite(score) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _box_top(box) -> float:
    bounds = _bounds(box)
    return bounds[1] if bounds is not None else 10**9
