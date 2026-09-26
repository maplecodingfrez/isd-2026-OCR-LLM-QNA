import lab8b_curriculum_db as lab8b


def got(rows):
    return {"rows": rows}


# Break caught: a list answer passing because SQL returned the whole table (old "set" is subset-only).
def test_set_exact_fails_on_extra_codes():
    exp = {"type": "set_exact", "value": ["06026101"]}
    ok, _ = lab8b.score_one(exp, got([{"code": "06026101"}, {"code": "06026102"}]))
    assert not ok


def test_set_exact_fails_on_missing_codes():
    exp = {"type": "set_exact", "value": ["06026101", "06026102"]}
    ok, _ = lab8b.score_one(exp, got([{"code": "06026101"}]))
    assert not ok


def test_set_exact_passes_on_exact_codes_any_column():
    exp = {"type": "set_exact", "value": ["06026101", "06026102"]}
    ok, _ = lab8b.score_one(exp, got([{"requires": "06026101", "n": 3}, {"requires": "06026102", "n": 3}]))
    assert ok


# Break caught: the asked course's own code (from the question or resolved from its name) counted as extra.
def test_set_exact_ignores_codes_in_question_and_ignore_list():
    exp = {"type": "set_exact", "value": ["06026101"], "ignore": ["06026240"]}
    rows = [{"code": "06026240", "requires": "06026101"}]
    assert lab8b.score_one(exp, got(rows))[0]
    exp2 = {"type": "set_exact", "value": ["06026101"]}
    assert lab8b.score_one(exp2, got(rows), question="รหัสวิชา 06026240 มีวิชาบังคับก่อนคือวิชาใด")[0]


def test_set_exact_empty_rows_fail():
    assert not lab8b.score_one({"type": "set_exact", "value": ["06026101"]}, got([]))[0]


# Break caught: old scoring types changing behaviour (v1 numbers must stay comparable).
def test_old_types_unchanged():
    rows = [{"code": "06026101"}, {"code": "06026102"}]
    assert lab8b.score_one({"type": "set", "value": ["06026101"]}, got(rows))[0]
    assert lab8b.score_one({"type": "value", "value": "06026102"}, got(rows))[0]
    assert lab8b.score_one({"type": "count", "value": 2}, got(rows))[0]
    assert not lab8b.score_one({"type": "none", "value": None}, got(rows))[0]
    assert lab8b.score_one({"type": "none", "value": None}, got([]))[0]
