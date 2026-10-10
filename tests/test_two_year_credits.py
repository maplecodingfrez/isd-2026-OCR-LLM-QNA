"""หน่วยกิตของ "สองปี" (ต่างกัน/รวม) — ราก: โมเดลเขียน SQL เลขคณิตเองแล้วไม่นิ่ง: ลืม SUM ได้แค่เทอมแรกของแต่ละปี
(IT: "ปี 2 กับปี 3 ต่างกัน" ตอบ 0 ทั้งที่ต่าง 12), ลบกลับด้านได้ "-3" ไม่มีหน่วย. ตอบจากยอดปีตามเล่ม (v_semester_credits_full) โดยไม่เรียกโมเดล"""

import re
from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
ALL = ["AIT", "BIT/coop", "BIT/no_coop", "DSBA/coop", "DSBA/no_coop", "IT/coop", "IT/no_coop"]


def year_totals(conn):
    return {y: c for y, c in conn.execute("SELECT year, SUM(credits) FROM main.v_semester_credits_full GROUP BY year")}


@pytest.mark.parametrize("rel", ALL)
@pytest.mark.parametrize("a,b", [(1, 2), (2, 3), (3, 4)])
def test_year_difference(rel, a, b, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *x, **k: pytest.fail("two-year credits must not call the model"))
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        t = year_totals(conn)
        for q in (f"ปี {a} กับปี {b} ต่างกันกี่หน่วยกิต", f"หน่วยกิตของปี {b} กับปี {a} ต่างกันเท่าไร"):
            ans = m.ask(conn, q, verbose=False)["answer"]
            diff = abs(t[a] - t[b])
            assert f"{diff} หน่วยกิต" in ans, (q, ans)
            assert f"ปี {a}" in ans and f"ปี {b}" in ans and f"{t[a]}" in ans and f"{t[b]}" in ans
            assert "-" not in ans


@pytest.mark.parametrize("rel", ALL)
def test_year_sum(rel, monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *x, **k: pytest.fail("two-year credits must not call the model"))
    with closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True)) as conn:
        t = year_totals(conn)
        for q in ("หน่วยกิตรวมปี 1 กับปี 2", "ปี 1 และปี 2 รวมกันกี่หน่วยกิต"):
            ans = m.ask(conn, q, verbose=False)["answer"]
            assert f"{t[1] + t[2]} หน่วยกิต" in ans, (q, ans)


@pytest.mark.parametrize("q", [
    "ปี 1 กับปี 2 ต่างกันยังไง",                       # ไม่ถามหน่วยกิต
    "ปี 2 เทอม 1 กับปี 3 เทอม 1 ต่างกันกี่หน่วยกิต",    # มีเทอม
    "ปี 1 รวมกี่หน่วยกิต",                             # ปีเดียว (ทางลัดเดิม)
    "ปี 1 กับปี 1 ต่างกันกี่หน่วยกิต",                   # ปีเดียวกัน
    "วิชา Calculus 1 กับปี 2 ต่างกันกี่หน่วยกิต",        # มีชื่อวิชา
])
def test_not_two_year_question(q):
    with closing(m.open_db(RUNS / "DSBA/coop/lab8b_output/curriculum.db", readonly=True)) as conn:
        assert m._two_year_credits_answer(conn, q) is None
