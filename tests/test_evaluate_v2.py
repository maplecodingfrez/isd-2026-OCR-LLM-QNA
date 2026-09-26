import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Lab9_evaluation"))
import evaluate_lab9 as ev  # noqa: E402

ROWS = [
    {"question": "ปี 2 เทอม 1 เรียนวิชาอะไรบ้าง", "category": "B", "level": "2",
     "expect": {"type": "set_exact", "value": ["06016101", "06016102"]},
     "answer": "06016101 (ก), 06016102 (ข)", "correct": True, "error": None, "seconds": 2.0, "citations": []},
    {"question": "ค่าเทอมเท่าไร", "category": "H", "level": "none", "expect": {"type": "none", "value": None},
     "answer": "ไม่พบข้อมูลนี้ในเล่มหลักสูตร", "correct": True, "error": None, "seconds": 1.0, "citations": []},
    {"question": "วิชา X มีกี่หน่วยกิต", "category": "E", "level": "1", "expect": {"type": "value", "value": "3"},
     "answer": "2 หน่วยกิต", "correct": False, "error": None, "seconds": 3.0, "citations": []},
]


# Break caught: set_exact answers never counted in answer-text accuracy (only "set" was handled).
def test_nl2sql_metrics_handles_set_exact_and_categories():
    m = ev.nl2sql_metrics(ROWS, [])
    assert (m["n"], m["n_correct"], m["answer_text_accuracy"]) == (3, 2, round(2 / 3, 4))
    assert m["category_stats"] == {"B": {"n": 1, "correct": 1}, "H": {"n": 1, "correct": 1},
                                   "E": {"n": 1, "correct": 0}}
    assert m["level_stats"]["none"]["n"] == 1


def test_v2_section_empty_without_v2_and_totals_with_it():
    r = ev.RunMetrics(name="ait", path="x")
    assert ev.v2_section({"ait": r}) == []
    r.v2 = ev.nl2sql_metrics(ROWS, [])
    r.n_questions, r.execution_accuracy = 30, 0.8
    text = "\n".join(ev.v2_section({"ait": r}))
    assert "2/3" in text and "ชุดคำถามทอง v2" in text
