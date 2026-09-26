import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Lab9_evaluation" / "gold_questions"))
import build_gold_questions_v2 as g2  # noqa: E402


def row(code, y, s, credits="3(3-0-6)", name_th=None, name_en=None, prerequisite="ไม่มี", note=None):
    return {"code": code, "year": y, "semester": s, "credits": credits, "name_th": name_th or f"วิชา{code}",
            "name_en": name_en, "prerequisite": prerequisite, "note": note, "flexible_year_semester": None}


# Break caught: IT ground truth stores year/semester as strings ("1").
def test_placed_accepts_string_year_and_dedups():
    rows = [row("06016401", "1", "1"), row("06016401", 1, 1), row("06016xxx", 2, 1), row("06016402", None, None)]
    assert list(g2.placed_courses(rows)) == ["06016401"]


# Break caught: asking a term total where the book has a wildcard slot, a chooser group, year 1, or odd credits.
def test_eligible_terms_rules():
    rows = ([row(f"0601610{i}", 2, 1) for i in range(4)]                     # 12 credits -> ok
            + [row(f"0601611{i}", 2, 2) for i in range(3)] + [row("06016xxx", 2, 2)]   # wildcard -> no
            + [row(f"0601612{i}", 3, 1) for i in range(3)] + [row("06016129", 3, 1, note="กลุ่มวิชา")]  # note -> no
            + [row("06016130", 3, 2, credits="6(0-45-0)")]                     # 6 credits < 9 -> no
            + [row(f"0601614{i}", 1, 1) for i in range(4)])                    # year 1 -> no unless allowed
    placed = g2.placed_courses(rows)
    assert g2.eligible_terms(rows, placed) == [(2, 1)]
    assert g2.eligible_terms(rows, placed, allow_year1=True) == [(1, 1), (2, 1)]
    assert g2.term_codes(rows, 2, 1) == ["06016100", "06016101", "06016102", "06016103"]


# Break caught: "A หรือ B" kept as one prerequisite / prerequisites outside the plan counted.
def test_prereq_maps_split_or_and_drop_unplaced():
    rows = [row("06036119", 1, 1), row("06036122", 1, 1),
            row("06036114", 2, 1, prerequisite="06036119 หรือ 06036122"),
            row("06036115", 2, 1, prerequisite="06099999")]
    fwd, rev = g2.prereq_maps(g2.placed_courses(rows))
    assert fwd == {"06036114": {"06036119", "06036122"}}
    assert rev == {"06036119": {"06036114"}, "06036122": {"06036114"}}


# Break caught: asking by a name that is empty or shared by two courses (answer ambiguous).
def test_unique_names():
    rows = [row("06016401", 1, 1, name_th="สัมมนา", name_en="SEMINAR"),
            row("06016402", 1, 1, name_th="สัมมนา", name_en=None),
            row("06016403", 1, 1, name_th="แคลคูลัส 1", name_en="Calculus  1")]
    placed = g2.placed_courses(rows)
    assert g2.unique_names(placed, "name_th") == {"06016403"}
    assert g2.unique_names(placed, "name_en") == {"06016401", "06016403"}


def test_v1_info_read_from_v1_files():
    assert g2.v1_declared("ait") == ("120", "4")
    assert len(g2.v1_codes("dsba_no_coop")) > 5
    assert g2.v1_keyword("dsba_no_coop") == "เทคโนโลยี"


# Break caught: unreadable credits silently counted as 0 in totals.
def test_all_real_plans_have_readable_credits():
    for plan in g2.PLAN_NAMES:
        for c in g2.placed_courses(g2.load_scoped(plan)).values():
            g2.hours(c)
