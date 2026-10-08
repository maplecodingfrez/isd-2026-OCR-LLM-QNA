"""A reachable daemon without the configured model is not ready."""
from dataclasses import replace
from types import SimpleNamespace
import pytest
import requests
from lab10_fastapi.curriculum_app import main, model_service
from lab10_fastapi.curriculum_app.config import Settings

class Response:
    def __init__(self,payload,status=200):
        self.payload=payload;self.status_code=status;self.ok=status==200
    def raise_for_status(self):
        if not self.ok: raise requests.HTTPError('HTTP failure')
    def json(self):
        if isinstance(self.payload,Exception): raise self.payload
        return self.payload

def configured(monkeypatch,payload,name='qwen3:4b',status=200):
    def get(url,*,timeout):
        assert url.endswith('/api/tags')
        assert timeout==3
        return Response(payload,status)
    monkeypatch.setattr(model_service.requests,'get',get)
    return model_service.QwenTextToSQL(Settings(ollama_model=name),SimpleNamespace())

@pytest.mark.parametrize('payload,wanted,expected',[
    ({'models':[]},'qwen3:4b',False),
    ({'models':[{'name':'qwen3:8b'}]},'qwen3:4b',False),
    ({'models':[{'name':'qwen3:latest'}]},'qwen3:4b',False),
    ({'models':[{'name':'qwen3:4b'}]},'qwen3:4b',True),
    ({'models':[{'model':'qwen3:4b'}]},'qwen3:4b',True),
    ({'models':[{'name':'qwen3:latest'}]},'qwen3',True),
    ({'models':[{'name':'qwen3'}]},'qwen3:latest',True),
    ({'models':[{'name':'namespace/model:latest'}]},'namespace/model',True),
    ({'models':[{'name':'registry.example:5000/team/model:latest'}]},'registry.example:5000/team/model',True),
    ({'models':[{'name':'team/model:4b'}]},'model:4b',False),
    ({'models':[{'name':' qwen3:4b '}]},' qwen3:4b ',True),
    ({'models':[{'name':'other'}]},'',False),
])
def test_model_inventory_matches_exact_tag(monkeypatch,payload,wanted,expected):
    model=configured(monkeypatch,payload,wanted)
    assert model.available() is expected

@pytest.mark.parametrize('payload',[
    None,[],{}, {'models':None},{'models':{}}, {'models':[None,42,{'name':42}]},ValueError('invalid JSON'),
])
def test_malformed_inventory_is_not_ready(monkeypatch,payload):
    assert configured(monkeypatch,payload).available() is False

def test_http_failure_is_not_ready(monkeypatch):
    assert configured(monkeypatch,{'models':[{'name':'qwen3:4b'}]},status=500).available() is False

@pytest.mark.parametrize('error',[requests.ConnectionError('offline'),requests.Timeout('slow')])
def test_network_failure_is_not_ready(monkeypatch,error):
    def get(*args,**kwargs): raise error
    monkeypatch.setattr(model_service.requests,'get',get)
    model=model_service.QwenTextToSQL(Settings(),SimpleNamespace())
    assert model.available() is False

@pytest.mark.parametrize('inventory,status,ready',[
    ([], 'degraded', False),([{'name':'qwen3:4b'}],'ok',True),
])
def test_health_reflects_actual_inventory(monkeypatch,tmp_path,inventory,status,ready):
    model=configured(monkeypatch,{'models':inventory})
    monkeypatch.setattr(main,'model',model)
    path=tmp_path/'db';path.touch()
    monkeypatch.setattr(main,'settings',replace(main.settings,db_path=path))
    result=main.health()
    assert result['status']==status
    assert result['database_ready'] is True
    assert result['ollama_ready'] is ready
