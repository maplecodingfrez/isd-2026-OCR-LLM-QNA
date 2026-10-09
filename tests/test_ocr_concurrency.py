"""OCR should occupy worker slots, not the ASGI event loop."""
import asyncio
import io
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from ocr_system.api import routes
from ocr_system.api.config import APISettings

class Upload:
    filename='sample.png'
    def __init__(self): self.stream = io.BytesIO(b'fixture')
    async def read(self, size=-1): return self.stream.read(size)

def test_ocr_keeps_event_loop_responsive(monkeypatch):
    entered=threading.Event(); release=threading.Event()
    def blocked(**kwargs):
        entered.set()
        assert release.wait(1),'worker did not yield to event loop'
        return 'done'
    monkeypatch.setattr(routes.OCRService,'process_document',blocked)
    async def scenario():
        task=asyncio.create_task(routes.process_document(Upload()))
        try:
            for _ in range(50):
                if entered.is_set(): break
                await asyncio.sleep(.01)
            assert entered.is_set()
            assert not task.done()
            await asyncio.wait_for(asyncio.sleep(0),timeout=.5)
        finally:
            release.set()
            assert await task=='done'
    asyncio.run(scenario())

def test_only_two_workers_are_admitted_and_slots_recover(monkeypatch):
    monkeypatch.setattr(routes,'_ocr_slots',threading.BoundedSemaphore(2),raising=False)
    release=threading.Event(); entered=[threading.Event(),threading.Event()]
    def blocked(*,index):
        entered[index].set()
        assert release.wait(2)
        return index
    monkeypatch.setattr(routes.OCRService,'process_document',blocked)
    wrapper=routes._process_document_limited
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(wrapper,index=i) for i in range(2)]
        try:
            assert all(event.wait(1) for event in entered)
            with pytest.raises(HTTPException) as caught: wrapper(index=0)
            assert caught.value.status_code==503
        finally: release.set()
        assert [f.result() for f in futures]==[0,1]
    monkeypatch.setattr(routes.OCRService,'process_document',lambda **kwargs:'new job')
    assert wrapper()=='new job'

def test_service_exception_releases_slot_and_preserves_error(monkeypatch):
    monkeypatch.setattr(routes,'_ocr_slots',threading.BoundedSemaphore(1),raising=False)
    def fail(**kwargs): raise HTTPException(status_code=422,detail='corrupt input')
    monkeypatch.setattr(routes.OCRService,'process_document',fail)
    with pytest.raises(HTTPException) as caught: routes._process_document_limited()
    assert caught.value.status_code==422
    monkeypatch.setattr(routes.OCRService,'process_document',lambda **kwargs:'ok')
    assert routes._process_document_limited()=='ok'

def test_cancelled_request_does_not_release_running_worker(monkeypatch):
    monkeypatch.setattr(routes,'_ocr_slots',threading.BoundedSemaphore(1),raising=False)
    entered=threading.Event();release=threading.Event();finished=threading.Event()
    def blocked(**kwargs):
        entered.set()
        try:
            assert release.wait(2)
            return 'done'
        finally: finished.set()
    monkeypatch.setattr(routes.OCRService,'process_document',blocked)
    async def scenario():
        task=asyncio.create_task(routes.process_document(Upload()))
        try:
            for _ in range(100):
                if entered.is_set(): break
                await asyncio.sleep(.01)
            assert entered.is_set()
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
            with pytest.raises(HTTPException) as caught: routes._process_document_limited()
            assert caught.value.status_code==503
        finally:
            release.set()
            for _ in range(100):
                if finished.is_set(): break
                await asyncio.sleep(.01)
            assert finished.is_set()
        # Release happens in wrapper finally, after the mocked work finishes.
        for _ in range(100):
            if routes._ocr_slots.acquire(blocking=False):
                routes._ocr_slots.release()
                break
            await asyncio.sleep(.01)
        else: pytest.fail('worker slot leaked after cancellation')
    asyncio.run(scenario())

@pytest.mark.parametrize('value',[0,-1])
def test_invalid_concurrency_limit_is_rejected(value):
    with pytest.raises(ValueError,match='MAX_CONCURRENT_OCR'):
        APISettings(max_concurrent_ocr=value)
