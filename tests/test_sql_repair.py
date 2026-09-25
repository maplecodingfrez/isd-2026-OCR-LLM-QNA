"""repair_undefined_aliases: fix LLM SQL that uses a table alias it never defined.

Real failure (all 7 Lab 8B runs): the DDL shown to qwen defines
`v_plan AS SELECT p.code, ... FROM plan_item p`, so qwen writes
`SELECT p.code FROM v_plan WHERE p.year = 1` -> sqlite3 "no such column: p.code".
"""
import sqlite3

import pytest

import lab8b_curriculum_db as lab8b


# Break caught: the repair is a no-op (or only fixes the SELECT list, not WHERE).
def test_strips_alias_that_is_never_defined():
    sql = "SELECT p.code FROM v_plan WHERE p.year = 1 AND p.semester = 1"
    assert lab8b.repair_undefined_aliases(sql) == (
        "SELECT code FROM v_plan WHERE year = 1 AND semester = 1")


# Break caught: stripping every "x." prefix, which would make joined queries ambiguous.
def test_keeps_aliases_defined_in_from_and_join():
    sql = ("SELECT p.code, c.name_th FROM plan_item p "
           "JOIN course c ON c.code = p.code WHERE p.year = 1")
    assert lab8b.repair_undefined_aliases(sql) == sql


# Break caught: only looking at bare aliases and not "AS alias".
def test_keeps_alias_declared_with_as():
    sql = "SELECT pi.code FROM plan_item AS pi WHERE pi.year = 2"
    assert lab8b.repair_undefined_aliases(sql) == sql


# Break caught: treating a real table/view name used as a qualifier as an undefined alias.
def test_keeps_table_name_qualifier():
    sql = "SELECT v_plan.code FROM v_plan WHERE v_plan.year = 1"
    assert lab8b.repair_undefined_aliases(sql) == sql


# Break caught: rewriting inside string literals or decimal numbers.
def test_does_not_touch_string_literals_or_decimals():
    sql = "SELECT p.code FROM v_plan WHERE p.name_th = 'p.x' AND p.credits > 2.5"
    assert lab8b.repair_undefined_aliases(sql) == (
        "SELECT code FROM v_plan WHERE name_th = 'p.x' AND credits > 2.5")


# Break caught: a repair that produces text SQLite still rejects (the actual user-facing failure).
def test_repaired_query_runs_against_the_real_schema():
    conn = sqlite3.connect(":memory:")
    conn.executescript(lab8b.DDL)
    conn.execute("INSERT INTO program VALUES ('X', 'หลักสูตรทดสอบ', NULL, NULL, 120, 4)")
    conn.execute("INSERT INTO course (code, name_th, credits) VALUES ('06016401', 'วิชาก', 3)")
    conn.execute("INSERT INTO course (code, name_th, credits) VALUES ('06016402', 'วิชาข', 3)")
    conn.execute("INSERT INTO plan_item (program_id, year, semester, code, credits) "
                 "VALUES ('X', 1, 1, '06016401', 3)")
    conn.execute("INSERT INTO plan_item (program_id, year, semester, code, credits) "
                 "VALUES ('X', 2, 1, '06016402', 3)")
    bad = "SELECT p.code FROM v_plan WHERE p.year = 1 AND p.semester = 1"
    with pytest.raises(sqlite3.OperationalError):
        conn.execute(bad)
    rows = conn.execute(lab8b.repair_undefined_aliases(bad)).fetchall()
    assert rows == [("06016401",)]


# Break caught: not registering a subquery alias; stripping "t." then makes "code"
# ambiguous between the subquery and course, so a valid query would start failing.
def test_keeps_subquery_alias_in_a_join():
    conn = sqlite3.connect(":memory:")
    conn.executescript(lab8b.DDL)
    conn.execute("INSERT INTO course (code, name_th, credits) VALUES ('06016401', 'วิชาก', 3)")
    sql = ("SELECT t.code, c.name_th FROM (SELECT code FROM course) t "
           "JOIN course c ON c.code = t.code")
    repaired = lab8b.repair_undefined_aliases(sql)
    assert repaired == sql
    assert conn.execute(repaired).fetchall() == [("06016401", "วิชาก")]


# Break caught: ask() not applying the repair, so the real 7/7-run failure
# ("no such column: p.code" on both attempts) still reaches the user.
def test_ask_answers_when_model_uses_an_undefined_alias(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(lab8b.DDL)
    conn.execute("INSERT INTO program VALUES ('X', 'หลักสูตรทดสอบ', NULL, NULL, 120, 4)")
    conn.execute("INSERT INTO course (code, name_th, credits) VALUES ('06016401', 'วิชาก', 3)")
    conn.execute("INSERT INTO plan_item (program_id, year, semester, code, credits) "
                 "VALUES ('X', 1, 1, '06016401', 3)")
    prompts = []

    def fake_ollama(prompt, fmt=None, **kwargs):     # qwen3 behaviour seen in eval_result.json
        prompts.append(prompt)
        if "sql" in (fmt or {}).get("properties", {}):
            return '{"sql": "SELECT p.code FROM v_plan WHERE p.year = 1 AND p.semester = 1"}'
        return '{"answer": "06016401"}'

    monkeypatch.setattr(lab8b, "ollama_generate", fake_ollama)
    result = lab8b.ask(conn, "ในแผนการศึกษา ชั้นปีที่ 1 ภาคการศึกษาที่ 1 ประกอบด้วยรายวิชารหัสใดบ้าง",
                       verbose=False)
    assert result["error"] is None
    assert [dict(r) for r in result["rows"]] == [{"code": "06016401"}]
    assert result["sql"].startswith("SELECT code FROM v_plan WHERE year = 1")
    assert len([p for p in prompts if "SQL" in p]) == 1      # fixed on the first attempt, no retry
