"""Independent query limits, including cleanup after interrupted execution."""
import importlib
import json
import sqlite3
from types import SimpleNamespace
import pytest

@pytest.fixture
def connection():
    conn=sqlite3.connect(':memory:')
    conn.row_factory=sqlite3.Row
    conn.execute('CREATE TABLE course(code TEXT)')
    conn.executemany('INSERT INTO course VALUES (?)',[(str(i),) for i in range(30)])
    yield conn
    conn.close()

@pytest.mark.parametrize('sql',[
    "SELECT 'limit' AS label FROM course",
    'SELECT code FROM course LIMIT -1',
    'SELECT code FROM course LIMIT 999999',
    'SELECT code FROM course -- limit',
    'SELECT code FROM course WHERE code IN (SELECT code FROM course LIMIT 20)',
])
def test_excess_rows_are_rejected(connection,sql):
    limits=importlib.import_module('query_limits')
    with pytest.raises(limits.QueryRowLimitExceeded):
        limits.execute_bounded_rows(connection,sql,row_limit=10)
    assert connection.execute('SELECT COUNT(*) FROM course').fetchone()[0]==30

RECURSIVE='WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x<1000000) SELECT count(*) AS n FROM cnt'

def test_recursive_aggregate_has_instruction_budget(connection):
    limits=importlib.import_module('query_limits')
    with pytest.raises(limits.QueryBudgetExceeded):
        limits.execute_bounded_rows(connection,RECURSIVE,instruction_limit=10000)
    assert connection.execute('SELECT 1').fetchone()[0]==1

def test_elapsed_deadline_interrupts_query(connection,monkeypatch):
    limits=importlib.import_module('query_limits')
    ticks=iter([0.0,3.0])
    monkeypatch.setattr(limits.time,'monotonic',lambda:next(ticks,3.0))
    with pytest.raises(limits.QueryBudgetExceeded):
        limits.execute_bounded_rows(connection,RECURSIVE)
    assert connection.execute('SELECT 1').fetchone()[0]==1

def test_normal_aggregate_and_order_are_preserved(connection):
    limits=importlib.import_module('query_limits')
    assert limits.execute_bounded_rows(connection,'SELECT COUNT(*) AS n FROM course',row_limit=1)==[{'n':30}]
    rows=limits.execute_bounded_rows(connection,'SELECT code FROM course ORDER BY CAST(code AS INT) LIMIT 10',row_limit=10)
    assert [row['code'] for row in rows]==[str(i) for i in range(10)]

def test_real_sql_error_is_not_relabelled(connection):
    limits=importlib.import_module('query_limits')
    with pytest.raises(sqlite3.OperationalError,match='no such table'):
        limits.execute_bounded_rows(connection,'SELECT * FROM absent')
    assert connection.execute('SELECT 1').fetchone()[0]==1

@pytest.mark.parametrize('options',[
    {'row_limit':0},{'row_limit':-1},{'row_limit':True},{'row_limit':1.5},
    {'timeout_s':0},{'timeout_s':float('nan')},{'timeout_s':float('inf')},
    {'instruction_limit':0},{'instruction_limit':True},{'instruction_limit':1.5},
])
def test_invalid_budgets_are_rejected(connection,options):
    limits=importlib.import_module('query_limits')
    with pytest.raises(ValueError):
        limits.execute_bounded_rows(connection,'SELECT 1',**options)
    assert connection.execute('SELECT 1').fetchone()[0]==1

def test_cursor_and_handler_cleanup_when_row_conversion_fails():
    limits=importlib.import_module('query_limits')
    closed=[]; handlers=[]
    class BadRow:
        def keys(self): raise ValueError('bad row')
    class Cursor:
        def fetchmany(self,n):
            assert n==11
            return [BadRow()]
        def close(self): closed.append(True)
    conn=SimpleNamespace(execute=lambda sql:Cursor(),set_progress_handler=lambda fn,n:handlers.append((fn,n)))
    with pytest.raises(ValueError,match='bad row'):
        limits.execute_bounded_rows(conn,'SELECT 1',row_limit=10)
    assert closed==[True]
    assert handlers[-1]==(None,0)


def test_adapter_rejects_excess_rows(tmp_path):
    from lab10_fastapi.curriculum_app.database import CurriculumDatabase
    import lab8b_curriculum_db as lab8b
    limits=importlib.import_module('query_limits')
    path=tmp_path/'adapter.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE course(code TEXT)')
        conn.executemany('INSERT INTO course VALUES (?)',[(str(i),) for i in range(30)])
    db=CurriculumDatabase(lab8b,path,max_rows=10)
    with pytest.raises(limits.QueryRowLimitExceeded):
        db.query_from_model("SELECT 'limit' AS label FROM course")


def test_lab8b_budget_failure_is_not_retried(monkeypatch):
    import lab8b_curriculum_db as lab8b
    import course_overview
    conn=lab8b.open_db(':memory:')
    try:
        conn.executescript(lab8b.DDL)
        conn.execute('INSERT INTO program VALUES (?,?,?,?,?,?)',('DSBA_COOP','DSBA','DSBA','BSc',132,4))
        conn.executemany('INSERT INTO course VALUES (?,?,?,?,?,?,?,?)',
            [(str(i).zfill(8),'Name','Name',3,3,0,6,'') for i in range(300)])
        monkeypatch.setattr(lab8b,'_SHORTCUTS',[])
        monkeypatch.setattr(course_overview,'overview_for_bare_reference',lambda *args:None)
        calls=[]
        def generated(*args,**kwargs):
            calls.append(True)
            return json.dumps({"sql": "SELECT code, 'limit' AS label FROM course"})
        monkeypatch.setattr(lab8b,'ollama_generate',generated)
        result=lab8b.ask(conn,'show me unusual course information',verbose=False)
        assert result['rows']==[]
        assert result['error'].startswith('QueryRowLimitExceeded:')
        assert len(calls)==1
        assert conn.execute('SELECT 1').fetchone()[0]==1
    finally:
        conn.close()
