"""Regressions for explicit F grade eligibility and English name field routing."""
import sqlite3
import pytest
import lab8b_curriculum_db as lab8

@pytest.fixture
def courses():
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    conn.executescript(lab8.DDL + lab8.PREREQ_ALT_DDL)
    conn.execute("INSERT INTO program(program_id,name_th,total_credits,years) VALUES ('test','Test',120,4)")
    for code,th,en in [('06026200','แคลคูลัส 1','CALCULUS 1'),('06026201','แคลคูลัส 2','CALCULUS 2'),('06026212','การสร้างคลังข้อมูล','DATA WAREHOUSING'),('90644007','ภาษาอังกฤษพื้นฐาน 1','FOUNDATION ENGLISH 1'),('90644008','ภาษาอังกฤษพื้นฐาน 2','FOUNDATION ENGLISH 2')]:
        conn.execute('INSERT INTO course(code,name_th,name_en,credits) VALUES (?,?,?,3)',(code,th,en))
        conn.execute("INSERT INTO plan_item(program_id,year,semester,code,credits) VALUES ('test',1,1,?,3)",(code,))
    conn.execute("INSERT INTO prerequisite(code,requires,kind) VALUES ('06026201','06026200','pre')")
    yield conn
    conn.close()

@pytest.mark.parametrize('word',['ได้ F','ได้เกรด F','ได้เกรด f','ติด F','ยังไม่ผ่าน','สอบตก'])
def test_explicit_failure_answers_registration_eligibility(courses,monkeypatch,word):
    def no_model(*args,**kwargs):
        raise AssertionError('eligibility must use prerequisite data')
    monkeypatch.setattr(lab8,'ollama_generate',no_model)
    result=lab8.ask(courses,f'ถ้า{word} แคลคูลัส 1 ยังลงแคลคูลัส 2 ได้ไหม',verbose=False)
    assert result['answer'].startswith('ไม่ได้')
    assert '06026200' in result['answer'] and '06026201' in result['answer']
    assert result['error'] is None
    assert result['rows'][0]['requires']=='06026200'

@pytest.mark.parametrize('word',['ไม่ได้ F','ได้ File','ได้ F+','ได้ A','F'])
def test_non_failure_grade_text_does_not_trigger_failure_rule(courses,word):
    assert lab8._prereq_yesno_answer(courses,f'ถ้า{word} แคลคูลัส 1 ยังลงแคลคูลัส 2 ได้ไหม') is None

def test_f_does_not_invent_a_missing_prerequisite(courses):
    assert lab8._prereq_yesno_answer(courses,'ถ้าได้ F แคลคูลัส 1 ยังลงการสร้างคลังข้อมูลได้ไหม') is None

@pytest.mark.parametrize('other_status,expected',[('ผ่าน','ได้ —'),('ได้ F','ยังไม่ได้ —')])
def test_f_grade_respects_alternative_prerequisites(courses,other_status,expected):
    courses.execute("INSERT INTO prerequisite(code,requires,kind) VALUES ('06026201','06026212','pre')")
    courses.executemany("INSERT INTO prerequisite_alt(code,requires,group_no) VALUES ('06026201',?,1)",[('06026200',),('06026212',)])
    assert lab8._prereq_yesno_answer(courses,'ถ้าได้ F แคลคูลัส 1 ยังลงแคลคูลัส 2 ได้ไหม') is None
    result=lab8._prereq_scenario_answer(courses,f'ถ้าได้ F แคลคูลัส 1 แต่{other_status}การสร้างคลังข้อมูล แล้วลงแคลคูลัส 2 ได้ไหม')
    assert result is not None and result[0].startswith(expected)

import json

@pytest.mark.parametrize('field',['ชื่อภาษาอังกฤษ','ชื่อวิชาภาษาอังกฤษ','ชื่อวิชาเป็นภาษาอังกฤษ','name_en'])
def test_english_name_field_is_not_a_foundation_english_family(courses,monkeypatch,field):
    question=f'ขอรหัสและ{field}ของวิชาในแผนที่{field}ขึ้นต้นด้วย DATA WAREHOUSING'
    assert lab8._code_family_answer(courses,question) is None
    sql="SELECT p.code, c.name_en FROM v_plan p JOIN course c ON p.code=c.code WHERE c.name_en LIKE 'DATA WAREHOUSING%'"
    outputs=iter([json.dumps({'sql':sql}),json.dumps({'answer':'DATA WAREHOUSING'})])
    monkeypatch.setattr(lab8,'ollama_generate',lambda *args,**kwargs:next(outputs))
    result=lab8.ask(courses,question,verbose=False)
    assert result['error'] is None
    assert {r['code'] for r in result['rows']} == {'06026212'}
    assert '06026212' in result['answer'] and 'DATA WAREHOUSING' in result['answer']
    assert '90644007' not in result['answer']


def test_actual_foundation_english_family_lookup_is_preserved(courses):
    result=lab8._code_family_answer(courses,'ขอรหัสวิชาภาษาอังกฤษ')
    assert result is not None
    assert {r['code'] for r in result[1]} == {'90644007','90644008'}


def test_thai_prefix_shortcut_cannot_drop_english_name_constraint(courses):
    assert lab8._name_prefix_list_answer(courses,"ขอรหัสวิชาที่ชื่อภาษาอังกฤษขึ้นต้นด้วย 'ภาษาอังกฤษ' มีอะไรบ้าง") is None
    result=lab8._name_prefix_list_answer(courses,"วิชาที่ชื่อขึ้นต้นด้วย 'ภาษาอังกฤษ' มีอะไรบ้าง")
    assert result is not None and {r['code'] for r in result[1]} == {'90644007','90644008'}

@pytest.mark.parametrize('question',[
 'ขอรหัสและชื่อภาษาอังกฤษของวิชาในแผนที่ชื่อภาษาอังกฤษขึ้นต้นด้วย DATA WAREHOUSING',
 'ขอรหัสและชื่อวิชาเป็นภาษาอังกฤษของวิชาในแผนที่ชื่อวิชาเป็นภาษาอังกฤษขึ้นต้นด้วย DATA WAREHOUSING',
 'ขอรายวิชาในแผนการศึกษาที่ชื่อภาษาอังกฤษขึ้นต้นด้วย DATA พร้อมรหัสวิชา',
 "วิชาในแผนที่ชื่อภาษาอังกฤษขึ้นต้นด้วย 'DATA WAREHOUSING' มีอะไรบ้าง",
])
def test_explicit_plan_english_prefix_uses_plan_not_electives(courses,monkeypatch,question):
    courses.execute("INSERT INTO course(code,name_th,name_en,credits) VALUES ('06029999','นอกแผน','DATA WAREHOUSING EXTRA',3)")
    def no_model(*args,**kwargs):
        raise AssertionError('explicit plan/name predicate must be deterministic')
    monkeypatch.setattr(lab8,'ollama_generate',no_model)
    result=lab8.ask(courses,question,verbose=False)
    assert result['error'] is None
    assert {r['code'] for r in result['rows']} == {'06026212'}
    assert {r['code'] for r in courses.execute(result['sql'])} == {'06026212'}
    assert 'DATA WAREHOUSING' in result['answer'] and '06026212' in result['answer']

@pytest.mark.parametrize('question',[
 'ขอรหัสวิชาในแผนที่ชื่อภาษาอังกฤษขึ้นต้นด้วย DATA และมี 2 หน่วยกิต',
 'ขอรหัสวิชาในแผนปี 2 ที่ชื่อภาษาอังกฤษขึ้นต้นด้วย DATA',
 'ขอรหัสวิชาที่ชื่อภาษาอังกฤษขึ้นต้นด้วย DATA',
 'ขอรหัสวิชาในแผนที่ชื่อภาษาอังกฤษไม่ได้ขึ้นต้นด้วย DATA',
])
def test_english_prefix_shortcut_declines_unsupported_constraints(courses,question):
    assert lab8._english_plan_prefix_answer(courses,question) is None

def test_empty_english_plan_prefix_is_an_executed_empty_query(courses):
    answer,rows,sql=lab8._english_plan_prefix_answer(courses,'ขอรายวิชาในแผนที่ชื่อภาษาอังกฤษขึ้นต้นด้วย QUANTUM')
    assert rows==[] and list(courses.execute(sql))==[]
    assert 'ไม่พบ' in answer and 'QUANTUM' in answer

@pytest.mark.parametrize('word',['แล็บ','แลป'])
@pytest.mark.parametrize('credit',[2,3])
def test_requested_codes_and_lab_alias_keep_both_predicates(courses,monkeypatch,word,credit):
    courses.execute('UPDATE course SET lecture_h=3,lab_h=0,self_h=6')
    def no_model(*args,**kwargs):
        raise AssertionError('supported lab filter must not need a model')
    monkeypatch.setattr(lab8,'ollama_generate',no_model)
    question=f'ขอรหัสและชื่อรายวิชาในแผนที่มีหน่วยกิตเท่ากับ {credit} และไม่มีชั่วโมง{word}'
    result=lab8.ask(courses,question,verbose=False)
    assert result['error'] is None
    assert len(result['rows']) == (5 if credit==3 else 0)
    assert [dict(r) for r in courses.execute(result['sql'])] == result['rows']
    assert f'c.credits = {credit}' in result['sql'] and 'c.lab_h = 0' in result['sql']

@pytest.mark.parametrize('word',['ชั่วโมงแล็บ','ชั่วโมงแลป','ชั่วโมง lab','lab'])
def test_lab_alias_normalization_never_duplicates_hours(word):
    from informal_questions import informal_to_thai
    formal=informal_to_thai(f'มีวิชาไหนที่ไม่มี{word}')
    assert formal=='มีวิชาไหนที่ไม่มีชั่วโมงปฏิบัติ'
    assert informal_to_thai(formal) is None
