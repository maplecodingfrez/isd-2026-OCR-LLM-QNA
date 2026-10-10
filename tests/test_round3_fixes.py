"""รอบแก้จุดอ่อนข้อ 5-7: (5) เลขไทย / เลขคำพูด / "CREDITS" อังกฤษ (6) ชื่อวิชาไม่ครบ + เลข ("โครงงาน 1") → คุณหมายถึง… (7) เทียบสองปีด้วย "มากกว่า/น้อยกว่า"
ข้อกำหนดสำคัญ: ตัวแปลงเลข/คำต้องไม่แตะคำถามทั่วไป ("ไก่สองตัว", "ทั้งสองวิชา", "เทอมหนึ่งร้อนไหม") จนไปตอบข้อมูลหลักสูตรผิด ๆ"""

import json
import re
from contextlib import closing
from pathlib import Path

import pytest

import lab8b_curriculum_db as m

RUNS = Path(__file__).resolve().parents[1] / "Lab7B_Lab8B_ocr_system" / "runs"
PLANS = ["AIT", "BIT/coop", "BIT/no_coop", "DSBA/coop", "DSBA/no_coop", "IT/coop", "IT/no_coop"]


def conn_for(rel="DSBA/coop"):
    return closing(m.open_db(RUNS / rel / "lab8b_output/curriculum.db", readonly=True))


def no_model(monkeypatch):
    monkeypatch.setattr(m, "ollama_generate", lambda *a, **k: pytest.fail("rule must answer without the model"))


def ans(conn, q):
    return m.ask(conn, q, verbose=False)["answer"]


# ---------- (5) เลขไทย ----------
@pytest.mark.parametrize("thai,arabic", [
    ("วิชาแคลคูลัส ๑ กี่หน่วยกิต", "วิชาแคลคูลัส 1 กี่หน่วยกิต"),
    ("แคลคูลัส ๒ เรียนปีไหน", "แคลคูลัส 2 เรียนปีไหน"),
    ("ปี ๓ เทอม ๑ รวมกี่หน่วยกิต", "ปี 3 เทอม 1 รวมกี่หน่วยกิต"),
    ("ปี ๑ เทอม ๒ เรียนอะไรบ้าง", "ปี 1 เทอม 2 เรียนอะไรบ้าง"),
    ("รหัสวิชา ๐๖๐๒๖๒๐๐ กี่หน่วยกิต", "รหัสวิชา 06026200 กี่หน่วยกิต"),
])
def test_thai_digits_answer_like_arabic_digits(thai, arabic, monkeypatch):
    no_model(monkeypatch)
    with conn_for() as conn:
        assert ans(conn, thai) == ans(conn, arabic) and not ans(conn, arabic).startswith("ไม่พบ")


def test_thai_digit_normaliser_unit():
    assert m._normalise_thai_digits("ปี ๑๐ ๐๑๒๓๔๕๖๗๘๙ abc") == "ปี 10 0123456789 abc"
    assert m._normalise_thai_digits("ไม่มีเลข") == "ไม่มีเลข"


# ---------- (5) เลขคำพูด (ข้อมูลจากชื่อวิชาจริง + คำนำปี/เทอม) ----------
@pytest.mark.parametrize("spoken,arabic", [
    ("แคลคูลัสหนึ่ง กี่หน่วยกิต", "แคลคูลัส 1 กี่หน่วยกิต"),
    ("แคลคูลัส สอง กี่หน่วยกิต", "แคลคูลัส 2 กี่หน่วยกิต"),
    ("ภาษาอังกฤษพื้นฐานสอง เรียนปีไหน", "ภาษาอังกฤษพื้นฐาน 2 เรียนปีไหน"),
    ("ปีสอง เทอมหนึ่ง เรียนอะไรบ้าง", "ปี 2 เทอม 1 เรียนอะไรบ้าง"),
    ("ชั้นปีที่สาม ภาคเรียนที่สอง รวมกี่หน่วยกิต", "ชั้นปีที่ 3 ภาคเรียนที่ 2 รวมกี่หน่วยกิต"),
])
def test_spoken_numbers_answer_like_digits(spoken, arabic, monkeypatch):
    no_model(monkeypatch)
    with conn_for() as conn:
        assert ans(conn, spoken) == ans(conn, arabic) and not ans(conn, arabic).startswith("ไม่พบ")


@pytest.mark.parametrize("q", ["ไก่สองตัวมีกี่ขา", "ทั้งสองวิชานี้หน่วยกิตเท่ากันไหม", "สามารถลงทะเบียนได้กี่หน่วยกิต", "ห้าปีเรียนจบไหม",
                               "พี่สี่คนเรียนวิชาไหน", "ปีสองพันห้าร้อยหกสิบเก้าเป็นปีอะไร", "เทอมหนึ่งร้อนไหม"])
def test_number_word_normaliser_leaves_ordinary_words_alone(q):
    with conn_for() as conn:
        assert m._normalise_number_words(conn, q) == q, q       # ระมัดระวัง: เลขคำพูดที่ติดกับตัวอักษรไทยตัวถัดไปไม่แปลง ("เทอมหนึ่งร้อน")


# ---------- (5) "CREDITS" อังกฤษ ----------
@pytest.mark.parametrize("english", ["CALCULUS 1 CREDITS", "Calculus 1 credit", "calculus 1 credits?"])
def test_english_credit_word_is_understood(english, monkeypatch):
    no_model(monkeypatch)
    with conn_for() as conn:
        a = ans(conn, english)
        assert a == ans(conn, "CALCULUS 1 หน่วยกิต") and "06026200" in a and "3 หน่วยกิต" in a, a      # เหมือนถามด้วยคำไทยทุกอย่าง


def test_english_credit_word_normaliser_unit():
    assert m._normalise_credit_words("CALCULUS 1 CREDITS") == "CALCULUS 1 หน่วยกิต"
    assert m._normalise_credit_words("credit card") == "หน่วยกิต card"          # ข้อความทั่วไปยังแปลงได้ แต่จะไปตกกฎ "ไม่ใช่คำถามหลักสูตร" ภายหลัง
    assert m._normalise_credit_words("accredited") == "accredited"                  # เป็นส่วนของคำอื่น = ไม่แตะ


# ---------- (6) ชื่อวิชาไม่ครบ + เลข ----------
@pytest.mark.parametrize("q,code", [
    ("โครงงาน 1 กี่หน่วยกิต", "06026214"),
    ("โครงงาน 2 เรียนปีไหน", "06026215"),
    ("วิชาโครงงาน 1 รหัสอะไร", "06026214"),
])
def test_partial_numbered_name_gets_did_you_mean(q, code, monkeypatch):
    no_model(monkeypatch)
    with conn_for("DSBA/coop") as conn:
        a = ans(conn, q)
    assert a.startswith("ไม่พบข้อมูลนี้ในเล่มหลักสูตร") and "คุณหมายถึง" in a and code in a, a


@pytest.mark.parametrize("q", ["แคลคูลัส 3 กี่หน่วยกิต", "ปี 1 กี่หน่วยกิต", "โครงงาน กี่หน่วยกิต", "แคลคูลัส 1 กี่หน่วยกิต", "ค่าเทอมเท่าไหร่",
                               "ไก่ 2 ตัว กี่หน่วยกิต", "ภาษา 1 กี่หน่วยกิต"])
def test_partial_numbered_rule_stays_quiet(q):
    with conn_for("DSBA/coop") as conn:
        assert m._numbered_stem_answer(conn, m._prepare_question(conn, q)) is None


# ---------- (7) เทียบสองปี มากกว่า/น้อยกว่า ----------
def year_totals(conn):
    return {y: c for y, c in conn.execute("SELECT year, SUM(credits) FROM main.v_semester_credits_full GROUP BY year")}


@pytest.mark.parametrize("rel", PLANS)
def test_year_comparison_states_the_true_direction(rel, monkeypatch):
    no_model(monkeypatch)
    with conn_for(rel) as conn:
        t = year_totals(conn)
        for a, b in [(1, 2), (2, 3), (3, 2), (4, 1)]:
            for word in ("มากกว่า", "น้อยกว่า"):
                out = ans(conn, f"ปี {a} {word}ปี {b} กี่หน่วยกิต")
                diff = abs(t[a] - t[b])
                if t[a] == t[b]:
                    assert "เท่ากัน" in out and f"{t[a]} หน่วยกิต" in out, (rel, a, b, out)
                else:
                    truth = "มากกว่า" if t[a] > t[b] else "น้อยกว่า"
                    assert f"ปี {a} {truth}ปี {b} อยู่ {diff} หน่วยกิต" in out, (rel, a, b, word, out)
                assert f"{t[a]} หน่วยกิต" in out and f"{t[b]} หน่วยกิต" in out and "-" not in out


@pytest.mark.parametrize("q", ["ปี 2569 มากกว่าปี 3 กี่หน่วยกิต", "ปี 3 มากกว่าปี 3 กี่หน่วยกิต", "ปี 3 มากกว่าปี 2 ไหม", "ปี 3 เทอม 1 มากกว่าปี 2 เทอม 1 กี่หน่วยกิต",
                               "ปี 1 กับปี 2 มากกว่า 5 ชั่วโมง"])
def test_year_comparison_rule_stays_quiet(q):
    with conn_for() as conn:
        assert m._two_year_credits_answer(conn, m._prepare_question(conn, q)) is None


# ---------- คำถามทั่วไปไม่ปนกับตัวแปลงใหม่ ----------
TRAPS = ["ไก่สองตัวมีกี่ขา", "เทอมหนึ่งร้อนไหม", "ปีสองพันห้าร้อยหกสิบเก้าเป็นปีอะไร", "ปี ๒๕๖๙ เป็นปีนักษัตรอะไร", "credit card ใช้ยังไง",
         "ปี ๓ มากกว่าปี ๒ กี่ปี", "แคลคูลัสในชีวิตจริงใช้ทำอะไร", "สองบวกสามเท่ากับเท่าไหร่", "ทั้งสองวิชาสนุกไหม"]


@pytest.mark.parametrize("q", TRAPS)
def test_general_questions_are_not_pulled_into_curriculum_answers(q, monkeypatch):
    def gen(prompt, fmt=None, **k):
        return json.dumps({"sql": "SELECT 2+3 AS result"} if fmt and "sql" in fmt.get("properties", {}) else {"answer": "5"})
    monkeypatch.setattr(m, "ollama_generate", gen)
    with conn_for() as conn:
        a = ans(conn, q)
    assert a.startswith(("ไม่พบข้อมูลนี้ในเล่มหลักสูตร", "คำถามยังไม่ชัดเจน")), (q, a)
    assert not re.search(r"\d+ หน่วยกิต|\d+ วิชา", a.split("ตัวอย่าง")[0].split("ลอง")[0]), (q, a)
