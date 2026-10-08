"""Failures must not produce stored, synthetic OCR results."""
import io
import sys
from dataclasses import replace
from types import ModuleType

import pytest
import pymupdf
from PIL import Image
from fastapi import HTTPException
from ocr_system.api import service
from ocr_system.schemas import OCRDocumentResult, OCRPageResult

@pytest.fixture
def service_env(monkeypatch, tmp_path):
    monkeypatch.setattr(service, 'settings', replace(service.settings,
        temp_dir=tmp_path/'uploads', output_dir=tmp_path/'outputs'))
    monkeypatch.setattr(service, 'repository', service.DocumentRepository())
    pipeline = ModuleType('ocr_system.pipeline')
    def fail(config):
        raise RuntimeError('native OCR unavailable at private/path')
    pipeline.run_ocr = fail
    monkeypatch.setitem(sys.modules, 'ocr_system.pipeline', pipeline)
    return pipeline

def png_bytes():
    stream = io.BytesIO()
    Image.new('RGB', (4,4), color='white').save(stream, format='PNG')
    return stream.getvalue()

def pdf_bytes(texts):
    with pymupdf.open() as doc:
        for text in texts:
            page = doc.new_page()
            if text:
                page.insert_text((50,72), text)
        return doc.tobytes()

def assert_clean():
    assert service.repository.list()[1] == 0
    assert list(service.settings.temp_dir.iterdir()) == []

@pytest.mark.parametrize('name, data', [
    ('corrupt.png', b'not an image'),
    ('corrupt.jpg', b'not a jpeg'),
    ('corrupt.pdf', b'not a pdf'),
])
def test_corrupt_input_not_stored(service_env, name, data):
    with pytest.raises(HTTPException) as caught:
        service.OCRService.process_document(data, name, engine='tesseract')
    assert caught.value.status_code == 422
    assert 'private/path' not in str(caught.value.detail)
    assert_clean()

@pytest.mark.parametrize('name, payload', [
    ('valid.png', lambda: png_bytes()),
    ('scanned.pdf', lambda: pdf_bytes([''])),
    ('mixed.pdf', lambda: pdf_bytes(['Digital page', ''])),
])
def test_engine_failure_without_complete_text_is_503(service_env, name, payload, caplog):
    with pytest.raises(HTTPException) as caught:
        service.OCRService.process_document(payload(), name, engine='tesseract')
    assert caught.value.status_code == 503
    assert 'private/path' not in str(caught.value.detail)
    assert 'native OCR unavailable' in caplog.text
    assert_clean()

def test_auto_mixed_pdf_does_not_silently_skip_scanned_page(service_env):
    with pytest.raises(HTTPException) as caught:
        service.OCRService.process_document(pdf_bytes(['Digital page','']), 'mixed.pdf',engine='auto')
    assert caught.value.status_code == 503
    assert_clean()

@pytest.mark.parametrize('engine', ['auto','tesseract'])
def test_complete_digital_pdf_preserves_real_text(service_env, engine):
    result = service.OCRService.process_document(
        pdf_bytes(['Email: student@kmitl.ac.th', 'Second page']), 'digital.pdf', engine=engine)
    assert result.status == 'completed'
    assert result.page_count == 2
    assert 'Second page' in result.full_text
    assert result.extracted_fields['email'] == 'student@kmitl.ac.th'
    assert service.repository.get(result.doc_id) is result
    assert list(service.settings.temp_dir.iterdir()) == []

def test_blank_successful_native_ocr_is_allowed(service_env):
    service_env.run_ocr = lambda config: OCRDocumentResult(
        source_path=str(config.input_path), engine='tesseract', text='',
        pages=[OCRPageResult(page=1,text='',lines=[],image_path=str(config.input_path))])
    result = service.OCRService.process_document(png_bytes(),'blank.png',engine='tesseract')
    assert result.status == 'completed'
    assert result.full_text == ''
    assert result.page_count == 1
    assert list(service.settings.temp_dir.iterdir()) == []

def test_pdf_handles_closed_on_validation_and_fallback(service_env, monkeypatch):
    actual_open = pymupdf.open
    opened = []
    def tracked(*args, **kwargs):
        doc = actual_open(*args, **kwargs)
        opened.append(doc)
        return doc
    payload = pdf_bytes(['Digital page'])
    monkeypatch.setattr(pymupdf, 'open', tracked)
    result=service.OCRService.process_document(payload,'digital.pdf',engine='tesseract')
    assert 'Digital page' in result.full_text
    assert opened and all(doc.is_closed for doc in opened)
