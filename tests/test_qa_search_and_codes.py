"""Live-audit regressions: truthful topic provenance and complete course identifiers."""
import sqlite3
import pytest
import lab8b_curriculum_db as lab8
import plan_questions

@pytest.fixture
def catalog():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(lab8.DDL + lab8.COURSE_DESCRIPTION_DDL)
    conn.execute("INSERT INTO program(program_id,name_th,total_credits,years) VALUES ('test','Test',120,4)")
    conn.execute("INSERT INTO course(code,name_th,name_en,credits) VALUES ('06020001','ฐานข้อมูล','DATA SYSTEMS',3)")
    conn.execute("INSERT INTO course(code,name_th,name_en,credits) VALUES ('06020002','การวิเคราะห์','DATA ANALYTICS',3)")
    conn.execute("INSERT INTO course_description(code,name_th,description_th) VALUES ('06020002','การวิเคราะห์','ศึกษาฐานข้อมูล')")
    conn.execute("INSERT INTO course_description(code,name_th,description_th) VALUES ('06020003','การประยุกต์','ศึกษาฐานข้อมูล')")
    conn.execute("INSERT INTO elective_group(id,program_id,plan_slot,group_no,name_th) VALUES (1,'test','xxxx',1,'เลือก')")
    conn.execute("INSERT INTO elective_group_course(group_id,code,name_th,credits) VALUES (1,'06020004','ฐานข้อมูลขั้นสูง',3)")
    for code in ('06020001','06020002'):
        conn.execute("INSERT INTO plan_item(program_id,year,semester,code,credits) VALUES ('test',1,1,?,3)",(code,))
    yield conn
    conn.close()

@pytest.mark.parametrize('topic',['ฐานข้อมูล','ควอนตัมเทเลพอร์ต'])
def test_topic_metadata_describes_broad_search_instead_of_fake_sql(catalog,topic):
    answer,rows,provenance = plan_questions._topic(catalog,f'มีวิชาเกี่ยวกับ{topic}ไหม')
    if topic == 'ฐานข้อมูล':
        assert {r['code'] for r in rows} == {'06020001','06020002','06020003','06020004'}
        assert {r['source'] for r in rows} == {'plan','elective','catalog'}
    else:
        assert rows == []
    assert provenance.startswith('-- Search explanation')
    assert 'not an executable SQL query' in provenance
    assert all(line.startswith('--') for line in provenance.splitlines())
    for table in ('course','elective_group_course','course_description'):
        assert table in provenance
    assert 'description' in provenance and 'merge by code' in provenance
    assert topic in provenance
    assert 'SELECT' not in provenance

import json
import re

@pytest.mark.parametrize('limit,model_answer',[
    (2,'DATA SYSTEMS, DATA ANALYTICS'),
    (1,'DATA SYSTEMS'),
    (2,'06020001 DATA SYSTEMS, DATA ANALYTICS'),
    (2,'906020001 DATA SYSTEMS, 906020002 DATA ANALYTICS'),
    (2,'06020001 (ฐานข้อมูล) DATA SYSTEMS; 06020002 (การวิเคราะห์) DATA ANALYTICS'),
])
def test_selected_course_codes_cannot_be_omitted_from_answer(catalog,monkeypatch,limit,model_answer):
    monkeypatch.setattr(lab8,'_SHORTCUTS',())
    sql = f"SELECT code, name_en FROM course WHERE name_en LIKE 'DATA%' ORDER BY code LIMIT {limit}"
    outputs = iter([json.dumps({'sql':sql}),json.dumps({'answer':model_answer})])
    monkeypatch.setattr(lab8,'ollama_generate',lambda *args,**kwargs:next(outputs))
    result = lab8.ask(catalog,'ขอรายวิชาในแผนการศึกษาที่ชื่อภาษาอังกฤษขึ้นต้นด้วย DATA พร้อมรหัสวิชา',verbose=False)
    assert result['error'] is None
    assert len(result['rows']) == limit
    for row in result['rows']:
        assert re.search(rf"(?<!\d){row['code']}(?!\d)",result['answer'])
        assert row['name_en'] in result['answer']
    if 'ฐานข้อมูล' in model_answer:
        assert result['answer'] == model_answer


def test_scalar_count_answer_is_preserved(catalog,monkeypatch):
    monkeypatch.setattr(lab8,'_SHORTCUTS',())
    outputs = iter(['{"sql":"SELECT COUNT(*) AS n FROM course"}',json.dumps({'answer':'มี 2 วิชา'})])
    monkeypatch.setattr(lab8,'ollama_generate',lambda *args,**kwargs:next(outputs))
    result = lab8.ask(catalog,'ขอจำนวนรายการในตาราง',verbose=False)
    assert result['rows'] == [{'n':2}]
    assert result['answer'] == 'มี 2 วิชา'
