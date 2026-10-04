import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Lab9_evaluation" / "gold_questions"))
import build_gold_questions as g2  # noqa: E402


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


# Break caught: unreadable credits silently counted as 0 in totals.
def test_all_real_plans_have_readable_credits():
    for plan in g2.PLAN_NAMES:
        for c in g2.placed_courses(g2.load_scoped(plan)).values():
            g2.hours(c)


import json  # noqa: E402
import re  # noqa: E402
from collections import Counter  # noqa: E402

BUILT = {plan: g2.build_plan(plan) for plan in g2.PLAN_NAMES}


def test_build_is_deterministic():
    assert g2.build_plan("ait") == BUILT["ait"]


# Break caught: a plan with fewer/more than 30 questions or a lopsided mix (ch8: 30 ข้อ, none >= 2).
def test_every_plan_meets_ch8_and_quota():
    for plan, (qs, _) in BUILT.items():
        cats = Counter(q["category"] for q in qs)
        assert len(qs) == 30, plan
        assert (cats["A"], cats["B"], cats["C"], cats["D"], cats["G"], cats["H"]) == (2, 6, 3, 3, 3, 5), plan
        assert cats["E"] + cats["F"] == 8, plan
        assert sum(q["expect"]["type"] == "none" for q in qs) == 5, plan
        assert len({q["question"] for q in qs}) == 30, plan
        assert len({q["id"] for q in qs}) == 30, plan


# Break caught: term answers that do not match the ground truth when recomputed a different way.
def test_term_answers_recomputed_independently():
    for plan, (qs, _) in BUILT.items():
        rows = g2.load_scoped(plan)
        for q in (q for q in qs if q["category"] == "B"):
            y, s = q["term"]
            mine = {r["code"]: r for r in rows if str(r.get("year")) == str(y) and str(r.get("semester")) == str(s)}
            if q["expect"]["type"] == "set_exact":
                assert q["expect"]["value"] == sorted(mine), (plan, q["id"])
            elif "กี่วิชา" in q["question"]:
                assert q["expect"]["value"] == str(len(mine)), (plan, q["id"])
            else:
                total = sum(int(re.match(r"\s*(\d+)", r["credits"]).group(1)) for r in mine.values())
                assert q["expect"]["value"] == str(total), (plan, q["id"])


# Break caught: BIT coop (one "A หรือ B" prerequisite) producing an empty or wrong prerequisite answer.
def test_prerequisite_questions_have_real_answers():
    for plan, (qs, meta) in BUILT.items():
        fwd, rev = g2.prereq_maps(g2.placed_courses(g2.load_scoped(plan)))
        for q in (q for q in qs if q["category"] == "F" and q["expect"]["type"] == "set_exact"):
            subject = q["about_codes"][0]
            want = sorted(rev[subject]) if q["direction"] == "reverse" else sorted(fwd[subject])
            assert q["expect"]["value"] == want and want, (plan, q["id"])
            assert q["expect"]["ignore"] == [subject]
    bit = [q for q in BUILT["bit_coop"][0] if q["id"] == "F1"][0]
    assert bit["expect"]["value"] == ["06036119", "06036122"]


# Break caught: an "unanswerable" question whose code/name actually exists in some plan.
def test_none_questions_are_unanswerable_everywhere():
    for plan, (qs, _) in BUILT.items():
        for q in (q for q in qs if q["category"] == "H"):
            for code in re.findall(r"\d{8}", q["question"]):
                if q["id"] != "H2":                      # H2 asks the instructor of a real course
                    assert code not in g2.ALL_CODES, (plan, q["id"])
        h5 = [q for q in qs if q["id"] == "H5"][0]
        fake = re.search(r"วิชา(.+?)มีกี่หน่วยกิต", h5["question"]).group(1)
        assert not any(g2.norm_th(fake) in n for n in g2.ALL_NAMES_TH)


# Break caught: v2 re-asking the same courses v1 was tuned on when fresh ones exist.
def test_named_courses_avoid_v1_unless_logged():
    for plan, (qs, meta) in BUILT.items():
        v1 = g2.v1_codes(plan)
        for q in (q for q in qs if q["category"] in "CDE"):
            code = q["about_codes"][0]
            assert code not in v1 or code in meta["fallback_v1_codes"], (plan, q["id"])


# Break caught: a name-based question using an empty or duplicated name.
def test_name_questions_use_unique_nonempty_names():
    for plan, (qs, _) in BUILT.items():
        placed = g2.placed_courses(g2.load_scoped(plan))
        th, en = g2.unique_names(placed, "name_th"), g2.unique_names(placed, "name_en")
        for q in qs:
            if q.get("name_key") == "name_th":
                assert q["about_codes"][0] in th, (plan, q["id"])
            if q.get("name_key") == "name_en":
                assert q["about_codes"][0] in en, (plan, q["id"])


def test_questions_are_json_serialisable_and_levels_set():
    for plan, (qs, _) in BUILT.items():
        json.dumps(qs, ensure_ascii=False)
        assert {q["level"] for q in qs} <= {"1", "2", "none"}
        assert all(q["level"] == "none" for q in qs if q["category"] == "H")


# Break caught: relaxed term choice re-asking year 1 term 1 (the term v1 was tuned on) when others exist.
def test_relaxed_terms_skip_v1_term_when_possible():
    for plan, (_, meta) in BUILT.items():
        rows = g2.load_scoped(plan)
        others = [t for t in g2.eligible_terms(rows, g2.placed_courses(rows), allow_year1=True) if t != (1, 1)]
        if len(others) >= 2:
            assert [1, 1] not in meta["terms"], plan


import hashlib  # noqa: E402


# Break caught: frozen files drifting from the generator, or edited by hand after freezing.
def test_frozen_files_match_generator_and_hash():
    frozen = json.loads(g2.FROZEN.read_text(encoding="utf-8"))
    assert sorted(frozen) == sorted(g2.PLAN_NAMES)
    for plan in g2.PLAN_NAMES:
        path = g2.question_path(plan)
        assert path.read_bytes() == g2.render(BUILT[plan][0]), plan
        assert hashlib.sha256(path.read_bytes()).hexdigest() == frozen[plan]["sha256"], plan
        assert {k: v for k, v in frozen[plan].items() if k != "sha256"} == BUILT[plan][1], plan
        assert g2.frozen_ok(plan), plan


# Break caught: running an edited (unfrozen) question file and reporting it as the locked set.
def test_edited_question_file_is_not_frozen(tmp_path):
    import shutil
    shutil.copy(g2.FROZEN, tmp_path / "frozen.json")
    q = tmp_path / "ait_gold_questions.json"
    q.write_bytes(g2.question_path("ait").read_bytes().replace("หน่วยกิต".encode(), "หน่วยกิจ".encode(), 1))
    assert not g2.frozen_ok("ait", tmp_path)


# Break caught: a name wrapped over two lines in the ground truth ("...AND\nCYBERSECURITY") used verbatim.
def test_names_in_questions_and_answers_have_no_line_breaks():
    for plan, (qs, _) in BUILT.items():
        for q in qs:
            assert "\n" not in q["question"] and "  " not in q["question"], (plan, q["id"])
            if isinstance(q["expect"]["value"], str):
                assert "\n" not in q["expect"]["value"], (plan, q["id"])


# Break caught (review #1): "how many courses..." counted over plan courses while the DB course table also
# holds elective-menu / co-op courses the ground truth does not list -> a correct SQL scored wrong.
def test_overview_questions_scoped_to_years_1_2_and_recomputed():
    for plan, (qs, _) in BUILT.items():
        rows = g2.load_scoped(plan)
        early = {r["code"]: r for r in rows if re.fullmatch(r"\d{8}", r.get("code") or "")
                 and str(r.get("year")) in ("1", "2") and str(r.get("semester")) in ("1", "2")}
        cr = {c: int(re.match(r"\s*(\d+)", r["credits"]).group(1)) for c, r in early.items()}
        lec = {c: int(re.search(r"\(\s*(\d+)", r["credits"]).group(1)) for c, r in early.items()}
        for q in (q for q in qs if q["category"] == "G"):
            assert "ปี 1" in q["question"] or "ชั้นปีที่ 1" in q["question"], (plan, q["id"])
            m_x = re.search(r"เท่ากับ (\d+)|ได้ (\d+) หน่วยกิต", q["question"])
            m_kw = re.search(r"'([^']+)'", q["question"])
            if m_x:
                x = int(m_x.group(1) or m_x.group(2))
                assert q["expect"]["value"] == str(sum(v == x for v in cr.values())), (plan, q["id"])
            elif m_kw:
                n = sum(m_kw.group(1) in r["name_th"] for r in early.values())
                assert q["expect"]["value"] == str(n), (plan, q["id"])
            else:
                assert q["expect"]["value"] == str(max(lec.values())), (plan, q["id"])


# Break caught (review #2): F1 and F2 asking the same course (one fact weighted twice).
def test_prerequisite_questions_ask_different_courses():
    for plan, (qs, _) in BUILT.items():
        fwd_subjects = [q["about_codes"][0] for q in qs if q.get("direction") == "forward"]
        assert len(fwd_subjects) == len(set(fwd_subjects)), plan


# Review finding: a missing frozen.json raised a raw FileNotFoundError instead of refusing to run.
def test_missing_frozen_file_is_not_frozen(tmp_path):
    (tmp_path / "ait_gold_questions.json").write_bytes(g2.question_path("ait").read_bytes())
    assert not g2.frozen_ok("ait", tmp_path)
