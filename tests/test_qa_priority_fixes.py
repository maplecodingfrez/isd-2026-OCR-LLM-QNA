"""Regressions from live Q&A: truthful failures and combined hours/credit filters."""
import sqlite3
import pytest
import lab8b_curriculum_db as lab8
from lab10_fastapi.curriculum_app import main
from lab10_fastapi.curriculum_app.schemas import AskRequest
from fastapi import HTTPException

@pytest.fixture
def courses():
    conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row
    conn.executescript(lab8.DDL)
    conn.execute("INSERT INTO program(program_id,name_th,total_credits,years) VALUES ('test','Test',120,4)")
    for i,credit,lecture,lab in [(1,2,2,0),(2,3,3,0),(3,2,1,2),(4,3,0,3)]:
        code=f'0602000{i}'
        conn.execute("INSERT INTO course(code,name_th,credits,lecture_h,lab_h,self_h) VALUES (?,?,?,?,?,?)",(code,f'วิชาทดสอบ {i}',credit,lecture,lab,4))
        conn.execute("INSERT INTO plan_item(program_id,year,semester,code,credits) VALUES ('test',1,1,?,?)",(code,credit))
    yield conn
    conn.close()

@pytest.mark.parametrize('question,expected',[
 ('วิชาที่มี 2 หน่วยกิตและไม่มีชั่วโมงปฏิบัติ มีวิชาไหนบ้าง',{'06020001'}),
 ('รายวิชาในแผนการศึกษาที่มี 3 หน่วยกิตและชั่วโมงปฏิบัติเป็น 0 มีอะไรบ้าง',{'06020002'}),
 ('วิชาที่มี 2 หน่วยกิตและชั่วโมงปฏิบัติมากกว่า 1 ชั่วโมงมีอะไรบ้าง',{'06020003'}),
 ('วิชาที่มีชั่วโมงปฏิบัติเท่ากับ 0 ชั่วโมงและมี 3 หน่วยกิตมีอะไรบ้าง',{'06020002'}),
 ('วิชาที่มีหน่วยกิตเท่ากับ 2 และไม่มีชั่วโมงปฏิบัติมีอะไรบ้าง',{'06020001'}),
 ('วิชาที่มี 4 หน่วยกิตและไม่มีชั่วโมงปฏิบัติมีอะไรบ้าง',set()),
])
def test_combined_credit_and_hours_constraints(courses,question,expected):
    result=lab8._hours_filter_answer(courses,question)
    assert result is not None
    answer,rows,sql=result
    assert {row['code'] for row in rows}==expected
    assert {row['code'] for row in courses.execute(sql)}==expected
    assert 'หน่วยกิต' in answer

@pytest.mark.parametrize('question',[
 'วิชาที่มีมากกว่า 2 หน่วยกิตและไม่มีชั่วโมงปฏิบัติมีอะไรบ้าง',
 'ปี 2 วิชาที่มี 2 หน่วยกิตและไม่มีชั่วโมงปฏิบัติมีอะไรบ้าง',
 'วิชาที่มี 2 หรือ 3 หน่วยกิตและไม่มีชั่วโมงปฏิบัติมีอะไรบ้าง',
])
def test_unsupported_combined_constraints_do_not_get_partially_answered(courses,question):
    assert lab8._hours_filter_answer(courses,question) is None

@pytest.mark.parametrize('error',['OperationalError: no such column: p.lecture_h','ValueError: only SELECT','SQL ไม่ผ่านการตรวจ'])
def test_failed_sql_has_safe_error_response(monkeypatch,tmp_path,caplog,error):
    path=tmp_path/'curriculum.db';path.touch()
    monkeypatch.setattr(main,'program_db_path',lambda program:path)
    monkeypatch.setattr(main.lab8b,'open_db',lambda *args,**kwargs:sqlite3.connect(':memory:'))
    monkeypatch.setattr(main.lab8b,'ask',lambda *args,**kwargs:{'question':'test','rows':[],'sql':'SELECT p.lecture_h FROM v_plan p','error':error,'answer':'ไม่พบข้อมูลนี้ในเล่มหลักสูตร','citations':[],'citation_text':''})
    with pytest.raises(HTTPException) as caught:
        main.ask(AskRequest(question='test'))
    assert caught.value.status_code==422
    assert 'ไม่พบข้อมูล' not in caught.value.detail
    assert 'p.lecture_h' not in caught.value.detail
    assert error in caplog.text

def test_failed_lab8_query_is_not_labelled_not_found(courses,monkeypatch):
    monkeypatch.setattr(lab8,'_SHORTCUTS',())
    monkeypatch.setattr(lab8,'ollama_generate',lambda *args,**kwargs:'{"sql":"SELECT missing FROM course"}')
    result=lab8.ask(courses,'ขอค่าที่ไม่ใช่รูปแบบทางลัด',verbose=False)
    assert result['error'].startswith('OperationalError:')
    assert 'ไม่พบข้อมูล' not in result['answer']
