"""เรนเดอร์ PDF ทีละชุดหน้า — ราก: convert_from_path ทั้งเล่มโหลดทุกหน้า (403 หน้า x 300 DPI) เข้าแรมพร้อมกัน → MemoryError ตอนรัน README ข้อ 1.3 ขั้น 2.
ผลต้องเหมือนเดิม: ไฟล์ชื่อ <stem>_page_NNN.jpg เรียงตามหน้า ครบทุกหน้า"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

fitz = pytest.importorskip("fitz")
from ocr_system import document_loader as dl  # noqa: E402


def make_pdf(path: Path, pages: int):
    doc = fitz.open()
    for i in range(pages):
        doc.new_page(width=200, height=200).insert_text((20, 100), f"page {i + 1}")
    doc.save(path)
    doc.close()


def test_pdf_is_rendered_in_chunks_and_names_are_unchanged(tmp_path, monkeypatch):
    pdf = tmp_path / "book.pdf"
    make_pdf(pdf, 5)
    calls = []
    real = dl.convert_from_path

    def spy(*args, **kwargs):
        calls.append((kwargs.get("first_page"), kwargs.get("last_page")))
        return real(*args, **kwargs)

    monkeypatch.setattr(dl, "convert_from_path", spy)
    monkeypatch.setattr(dl, "PDF_CHUNK_PAGES", 2)
    out = dl.pdf_to_images(pdf, tmp_path / "pages", dpi=50)
    assert [p.name for p in out] == [f"book_page_{i:03d}.jpg" for i in range(1, 6)]
    assert all(p.exists() for p in out)
    assert calls == [(1, 2), (3, 4), (5, 5)]            # ไม่เรนเดอร์ทั้งเล่มในครั้งเดียว


def test_single_page_pdf(tmp_path):
    pdf = tmp_path / "one.pdf"
    make_pdf(pdf, 1)
    out = dl.pdf_to_images(pdf, tmp_path / "pages", dpi=50)
    assert [p.name for p in out] == ["one_page_001.jpg"]
