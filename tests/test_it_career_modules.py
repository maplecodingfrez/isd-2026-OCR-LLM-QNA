"""The IT book groups 9 of its elective courses into 3 career modules (M1 Full-Stack Web, M2 Network/System, M3 Game).
The elective list answer for IT must say so (modules are optional and can be mixed); other plans have no modules and are unchanged."""

from contextlib import closing

import pytest

import lab8b_curriculum_db as m
from lab10_fastapi.curriculum_app import main

MODULES = {
    "M1": ("Full-Stack Web Developer", ["06016428", "06016429", "06016430"]),
    "M2": ("Network/System Engineer", ["06016439", "06016440", "06016441"]),
    "M3": ("Game Developer", ["06016446", "06016447", "06016448"]),
}


@pytest.fixture()
def no_model(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the language model must not be needed")
    monkeypatch.setattr(m, "ollama_generate", refuse)


def ask(plan, question):
    path = main.program_db_path(plan)
    if path is None or not path.exists():
        pytest.skip(f"needs the {plan} database")
    with closing(m.open_db(path, readonly=True)) as conn:
        return m.ask(conn, question, verbose=False)


@pytest.mark.parametrize("plan", ["it_coop", "it_no_coop"])
@pytest.mark.parametrize("question", ["วิชาเลือกมีอะไรบ้าง", "What elective courses are there?"])
def test_it_elective_list_names_the_three_career_modules(plan, question, no_model):
    r = ask(plan, question)
    answer = r["answer"]
    assert "โมดูลอาชีพ" in answer and "ไม่บังคับ" in answer
    for no, (name, codes) in MODULES.items():
        line = next(l for l in answer.splitlines() if l.startswith(f"{no} "))
        assert name in line, (plan, no)
        assert all(code in line for code in codes), (plan, no, line)
    tagged = {row["code"]: row.get("module") for row in r["rows"] if row.get("module")}
    assert tagged == {code: no for no, (_, codes) in MODULES.items() for code in codes}


@pytest.mark.parametrize("plan", ["dsba_coop", "dsba_no_coop", "ait", "bit_coop"])
def test_plans_without_modules_are_unchanged(plan, no_model):
    r = ask(plan, "วิชาเลือกมีอะไรบ้าง")
    assert "โมดูลอาชีพ" not in r["answer"] and not any(row.get("module") for row in r["rows"])
