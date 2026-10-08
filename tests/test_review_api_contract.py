"""Resource failures must not masquerade as absent curriculum information."""
import sqlite3
import pytest
from fastapi import HTTPException
from lab10_fastapi.curriculum_app import main
from lab10_fastapi.curriculum_app.schemas import AskRequest

@pytest.mark.parametrize('kind',['QueryBudgetExceeded','QueryRowLimitExceeded'])
def test_resource_exhaustion_returns_service_error(monkeypatch,tmp_path,kind):
    path=tmp_path/'placeholder.db'; path.touch()
    monkeypatch.setattr(main,'program_db_path',lambda program:path)
    monkeypatch.setattr(main.lab8b,'open_db',lambda *args,**kwargs:sqlite3.connect(':memory:'))
    monkeypatch.setattr(main.lab8b,'ask',lambda *args,**kwargs:{
        'question':'any question','rows':[],'answer':'failure','sql':None,
        'error':kind+': internal query details','citations':[],'citation_text':''})
    with pytest.raises(HTTPException) as caught:
        main.ask(AskRequest(question='any question'))
    assert caught.value.status_code==503
    assert 'internal query details' not in str(caught.value.detail)


def test_query_limit_ui_guidance_does_not_mark_model_offline(tmp_path):
    from test_curriculum_app_js import run_js
    result = run_js(tmp_path, '''
      const detail = "คำถามนี้ใช้ทรัพยากรมากเกินไป กรุณาระบุเงื่อนไขให้แคบลงแล้วลองใหม่";
      const err = new m.ApiError("http", 503, detail, detail);
      return {down: m.isModelDown(err, "ask"), message: m.describeError(err, "ask"),
              other: m.isModelDown(new m.ApiError("http", 503, "unavailable", "unavailable"), "ask")};
    ''')
    assert result['down'] is False
    assert result['other'] is True
    assert 'แคบลง' in result['message']['action']
