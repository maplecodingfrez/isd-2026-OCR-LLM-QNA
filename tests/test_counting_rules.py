"""นับวิชา/หน่วยกิต — ราก: qwen3:4b ไม่เก่งคำนวณ ตอบตัวเลขผิดอย่างมั่นใจ (วิชาบังคับ 6 แทน 30, ภาษาอังกฤษ 50 แทน 2, วิชาเลือก 258 หน่วยกิตทั้งที่หลักสูตรรวม 132)
แก้ 3 ชั้น: (1) กฎ deterministic นับตามหมวด/ทั้งปี/ทั้งหลักสูตร/ตามคำในชื่อ (2) ด่านตรวจความสมเหตุสมผลของตัวเลขจากโมเดล
(3) หน่วยกิตค่าเดียวเรนเดอร์ข้อความจากโค้ด (เดิมโมเดลเขียนหน่วยเป็น "ครั้ง")"""

import json
from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
PLANS = ["DSBA/coop", "IT/no_coop", "AIT", "BIT/coop"]


def conn_for(rel):
    return closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True))


def no_model(monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("counting must not call the model"))


# ---------- (1) กฎนับ ----------
@pytest.mark.parametrize("rel", PLANS)
@pytest.mark.parametrize("kind", ["บังคับ", "เลือก"])
def test_whole_program_kind_count_phrasings_agree_with_the_explicit_one(rel, kind, monkeypatch):
    no_model(monkeypatch)
    with conn_for(rel) as conn:
        explicit = m.ask(conn, f"มีวิชา{kind}ทั้งหลักสูตรกี่วิชา", verbose=False)["answer"]
        for q in (f"มีวิชา{kind}กี่วิชา", f"วิชา{kind}ทั้งหมดกี่วิชา", f"หลักสูตรนี้มีวิชา{kind}กี่วิชา", f"วิชา{kind}มีทั้งหมดกี่วิชา"):
            assert m.ask(conn, q, verbose=False)["answer"] == explicit, q


def test_dsba_mandatory_count_matches_plan_notes(monkeypatch):
    no_model(monkeypatch)
    with conn_for("DSBA/coop") as conn:
        n = conn.execute("SELECT COUNT(*) FROM plan_item WHERE note LIKE '%| บังคับ'").fetchone()[0]
        assert f"{n} วิชา" in m.ask(conn, "มีวิชาบังคับกี่วิชา", verbose=False)["answer"]


@pytest.mark.parametrize("rel,year", [("DSBA/coop", 3), ("IT/no_coop", 2), ("AIT", 4)])
def test_whole_year_count(rel, year, monkeypatch):
    no_model(monkeypatch)
    with conn_for(rel) as conn:
        base = m.ask(conn, f"ปี {year} มีกี่วิชา", verbose=False)["answer"]
        assert "วิชา" in base and "ไม่พบ" not in base
        for q in (f"ปี {year} ทั้งปีมีกี่วิชา", f"ปี {year} เรียนทั้งปีกี่วิชา"):
            assert m.ask(conn, q, verbose=False)["answer"] == base, q


@pytest.mark.parametrize("rel", PLANS)
def test_whole_program_course_count(rel, monkeypatch):
    no_model(monkeypatch)
    with conn_for(rel) as conn:
        n = conn.execute("SELECT COUNT(DISTINCT code) FROM v_plan").fetchone()[0]
        for q in ("ทั้งหลักสูตรมีกี่วิชา", "มีกี่วิชาในหลักสูตร", "หลักสูตรนี้มีกี่วิชา", "แผนนี้มีทั้งหมดกี่วิชา"):
            ans = m.ask(conn, q, verbose=False)["answer"]
            assert f"{n} วิชา" in ans, (q, ans)


def test_keyword_count_by_course_name(monkeypatch):
    no_model(monkeypatch)
    with conn_for("DSBA/coop") as conn:
        ans = m.ask(conn, "ภาษาอังกฤษต้องเรียนกี่วิชา", verbose=False)
        assert "2 วิชา" in ans["answer"] and "90644007" in ans["answer"] and "90644008" in ans["answer"], ans["answer"]
        assert "50 วิชา" not in ans["answer"]
        one = m.ask(conn, "มีวิชาที่ชื่อมีคำว่าข้อมูลกี่วิชา", verbose=False)["answer"]
        n = conn.execute("SELECT COUNT(DISTINCT p.code) FROM v_plan p JOIN course c ON c.code = p.code WHERE c.name_th LIKE '%ข้อมูล%' OR c.name_en LIKE '%ข้อมูล%'").fetchone()[0]
        assert f"{n} วิชา" in one, one


@pytest.mark.parametrize("q", ["ปี 1 มีกี่วิชา", "วิชาแคลคูลัส 1 กี่หน่วยกิต", "ภาษาอังกฤษพื้นฐาน 1 เรียนปีไหน", "ปี 1 เทอม 1 มีกี่วิชา"])
def test_keyword_count_rule_stays_quiet(q):
    with conn_for("DSBA/coop") as conn:
        assert m._name_keyword_count_answer(conn, m._prepare_question(conn, q)) is None


# ---------- (2) ด่านตรวจตัวเลข ----------
def test_implausible_credits_over_program_total():
    with conn_for("DSBA/coop") as conn:
        why = m._implausible_number(conn, "เรียนจบต้องมีวิชาเลือกกี่หน่วยกิต", [{"x": 258}])
        assert why and "132" in why
        assert m._implausible_number(conn, "ปี 1 รวมกี่หน่วยกิต", [{"credits": 39}]) is None
        assert m._implausible_number(conn, "หลักสูตรนี้กี่หน่วยกิต", [{"total_credits": 132}]) is None


def test_implausible_counts_and_negatives():
    with conn_for("DSBA/coop") as conn:
        courses = conn.execute("SELECT COUNT(*) FROM course").fetchone()[0]
        assert m._implausible_number(conn, "มีกี่วิชา", [{"COUNT(*)": courses + 1}])
        assert m._implausible_number(conn, "มีกี่วิชา", [{"COUNT(*)": courses}]) is None
        assert m._implausible_number(conn, "ปี 3 มากกว่าปี 1 กี่หน่วยกิต", [{"diff": -3}])
        assert m._implausible_number(conn, "ปี 3 มากกว่าปี 1 กี่หน่วยกิต", [{"diff": 3.5}])


@pytest.mark.parametrize("rows", [[], [{"a": 1}, {"a": 2}], [{"a": 1, "b": 2}], [{"name": "x"}], [{"a": None}]])
def test_guard_ignores_shapes_it_does_not_judge(rows):
    with conn_for("DSBA/coop") as conn:
        assert m._implausible_number(conn, "กี่หน่วยกิต", rows) is None


def fake_model(sql, answer=None, calls=None):
    def gen(prompt, fmt=None, **k):
        if calls is not None:
            calls.append("sql" if fmt and "sql" in fmt.get("properties", {}) else "answer")
        if fmt and "sql" in fmt.get("properties", {}):
            return json.dumps({"sql": sql})
        if answer is None:
            pytest.fail("answer model should not be needed")
        return json.dumps({"answer": answer})
    return gen


def test_ask_refuses_an_impossible_model_number(monkeypatch):
    calls = []
    monkeypatch.setattr(m, "ollama_generate", fake_model("SELECT 258 AS credits", "258 หน่วยกิต", calls))
    with conn_for("DSBA/coop") as conn:
        r = m.ask(conn, "ช่วยคำนวณยอดรวมหน่วยกิตให้หน่อยครับ", verbose=False)
    assert calls == ["sql"], calls                         # ไปถึงโมเดลจริง และไม่เสียเวลาเรียกโมเดลเรียบเรียงคำตอบ
    assert r["answer"].startswith("ไม่พบข้อมูลนี้ในเล่มหลักสูตร") and "132" in r["answer"], r["answer"]
    assert r["rows"] == [] and r.get("sql_rejected")


# ---------- (3) หน่วยกิตค่าเดียว: เรนเดอร์จากโค้ด ไม่ใช้ข้อความของโมเดล ----------
def test_single_credit_value_is_rendered_by_code(monkeypatch):
    calls = []
    sql = "SELECT SUM(credits) AS credits FROM plan_item WHERE code LIKE '0602%'"
    monkeypatch.setattr(m, "ollama_generate", fake_model(sql, "12 ครั้ง", calls))
    with conn_for("DSBA/coop") as conn:
        expected = conn.execute(sql).fetchone()[0]
        r = m.ask(conn, "ช่วยคำนวณยอดรวมหน่วยกิตให้หน่อยครับ", verbose=False)
    assert calls == ["sql"], calls                         # ข้อความคำตอบไม่ได้มาจากโมเดล
    assert r["answer"] == f"{expected} หน่วยกิต" and "ครั้ง" not in r["answer"], r["answer"]


def test_model_text_is_still_used_when_the_value_is_not_a_single_credit(monkeypatch):
    calls = []
    monkeypatch.setattr(m, "ollama_generate", fake_model("SELECT COUNT(*) AS n FROM plan_item WHERE year = 4", "ปี 4 มี 3 วิชา", calls))
    with conn_for("DSBA/coop") as conn:
        r = m.ask(conn, "ช่วยนับวิชาปีสุดท้ายให้หน่อย", verbose=False)
    assert "answer" in calls and "3" in r["answer"], (calls, r["answer"])


# ---------- (E) ห้ามใส่ "คำใบ้การคำนวณ" ใน prompt ของ Qwen ----------
def test_no_arithmetic_hint_in_the_sql_prompt():
    """ทดลองจริง (A/B บนข้อชุดทอง 7 ข้อ): เปิดคำใบ้ "ห้ามคิดเลขเอง… GROUP BY year / v_semester_credits" ถูก 2/14, ปิด 14/14 —
    โมเดลเล็กตีความผิดแล้วเลือกวิวผิด/เติม semester = 1 เอง จึงถอดออก (เลขคณิตย้ายไปเป็นกฎ + ด่านตรวจแทน) ห้ามกลับมาโดยไม่วัดกับชุดทอง"""
    assert not hasattr(m, "_arithmetic_hint_text")


# ---------- วิชาเลือกกี่หน่วยกิต: เล่มไม่มียอดก้อนเดียว → แสดงทุกกลุ่มจาก credit_structure ----------
@pytest.mark.parametrize("rel", ["DSBA/coop", "IT/no_coop", "AIT"])
@pytest.mark.parametrize("q", ["เรียนจบต้องมีวิชาเลือกกี่หน่วยกิต", "ต้องเรียนวิชาเลือกกี่หน่วยกิต", "วิชาเลือกทั้งหมดกี่หน่วยกิต"])
def test_generic_elective_credits_lists_the_groups_of_the_book(rel, q, monkeypatch):
    no_model(monkeypatch)
    with conn_for(rel) as conn:
        groups = conn.execute("SELECT name_th, credits FROM credit_structure WHERE name_th LIKE '%เลือก%' AND name_th NOT LIKE '%ทางเลือก%' ORDER BY id").fetchall()
        r = m.ask(conn, q, verbose=False)
    assert groups and all(f"{n} {c} หน่วยกิต" in r["answer"] for n, c in groups), r["answer"]
    assert "เจาะจง" in r["answer"] and not r["answer"].startswith("ไม่พบ")


@pytest.mark.parametrize("q", ["วิชาเลือกเสรีกี่หน่วยกิต", "ปี 3 วิชาเลือกกี่หน่วยกิต", "วิชาเลือกการตลาดดิจิทัลกี่หน่วยกิต", "กลุ่มวิชาเลือกกี่หน่วยกิต", "วิชา Optimization กี่หน่วยกิต"])
def test_elective_credit_overview_stays_quiet(q):
    with conn_for("DSBA/coop") as conn:
        assert m._elective_credit_overview_answer(conn, m._prepare_question(conn, q)) is None
