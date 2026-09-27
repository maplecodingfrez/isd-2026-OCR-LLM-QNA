"""
ฉันทามติของชื่อวิชาข้ามแผน/ข้ามรอบ — แก้ typo ของ OCR โดยไม่ต้องรู้ชื่อที่ถูกล่วงหน้า

ทำไม: วิชาเดียวกัน (รหัสเดียวกัน) โผล่หลายแผน/หลายรอบ และ OCR สะกดผิดไม่เหมือนกัน
(`06066000` "คณิตศาสตร์ไม่ต่อเนื่อง" ถูกใน AIT แต่ "…โมโต่อเนื่อง" ใน IT) ชื่อเดียวกันยังโผล่ใต้
คนละรหัส (NoSQL ทั้ง IT `06016414` และ DSBA `06026207`) จึงรวมคะแนนเสียงข้ามรหัสได้ด้วย
กฎเชิงกำหนดล้วน ๆ (ไม่เรียก LLM ไม่อ่านเฉลย ไม่กรอกมือ) — รันซ้ำได้ผลเดิม และรันซ้ำบนผลที่แก้แล้วไม่เปลี่ยนอีก

กฎ:
  1. ชื่อที่ "ไม่ใช่ชื่อวิชาจริง" ไม่นับเสียงและถูกแทนที่: ว่าง / เท่ารหัสตัวเอง / label หมวดวิชา
     (มี "*" หรือขึ้นต้น "กลุ่มวิชา"/"หมวดวิชา"/"วิชาเลือก")
  2. สองชื่อถือเป็น "สะกดเพี้ยนของกันและกัน" เมื่อความคล้าย (difflib) ≥ 0.9 และ **ตัวเลขในชื่อเท่ากัน**
     (กัน "โครงงาน 1" กับ "โครงงาน 2" ซึ่งคล้าย 0.97 แต่เป็นคนละวิชา) — รวมเสียงข้ามรหัส
  3. ในกลุ่มการสะกด เลือกสะกดที่ได้เสียงมากที่สุด; เสมอ → ตัดสินไม่ได้ ไม่เปลี่ยน (รายงาน)
  4. ในรหัสเดียวกันถ้ามีชื่อคนละกลุ่มกันโดยสิ้นเชิง (เช่น ชื่อของแถวข้างเคียงหลุดมา) เลือกกลุ่มที่
     เสียงมากที่สุดของรหัสนั้น; เสมอ → ตัดสินไม่ได้

ข้อจำกัดที่ต้องรู้: OCR ผิดแบบเดียวกันซ้ำ ๆ (เช่นแผนที่ใช้ตารางหน้าตาเดียวกัน) จะได้เสียงมากเกินจริง
จึงรายงานคะแนนเสียงทุกครั้ง และไม่แก้เมื่อเสมอ
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Iterable

SIM_THRESHOLD = 0.9
_LABEL_PREFIX = re.compile(r"^\s*(กลุ่มวิชา|หมวดวิชา|วิชาเลือก)")


def is_placeholder(name: str | None, code: str) -> bool:
    n = (name or "").strip()
    return not n or n == code or "*" in n or bool(_LABEL_PREFIX.match(n))


def _norm(name: str) -> str:
    return re.sub(r"\s+", "", name)


def _same_spelling_family(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if re.findall(r"\d+", na) != re.findall(r"\d+", nb):
        return False
    sm = SequenceMatcher(None, na, nb)
    # real_quick_ratio/quick_ratio เป็นขอบบนของ ratio() — ตัดคู่ที่ไม่มีทางถึงเกณฑ์ก่อน ผลเหมือนเดิม แต่เร็วขึ้นมาก
    # (ใน pipeline มีชื่อจากดัชนีเล่มทั้ง 4 เล่ม เทียบทุกคู่)
    return (sm.real_quick_ratio() >= SIM_THRESHOLD and sm.quick_ratio() >= SIM_THRESHOLD
            and sm.ratio() >= SIM_THRESHOLD)


def consensus(observations: Iterable[tuple[str, str, str]]) -> dict:
    """observations = (run, code, name_th) → {"changes": [...], "unresolved": [...], "votes": {...}}

    changes: {run, code, old, new, reason}  (แก้ได้จริง)
    unresolved: {code, candidates:{ชื่อ:เสียง}, reason}  (เสมอ — ไม่แตะ)
    """
    obs = list(observations)
    valid = [(r, c, n) for r, c, n in obs if not is_placeholder(n, c)]

    # 1) กลุ่มการสะกด (union-find บนชื่อที่ต่างกัน) — รวมเสียงข้ามรหัส
    spell = Counter(n for _, _, n in valid)
    names = sorted(spell)
    parent = {n: n for n in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _same_spelling_family(a, b):
                parent[find(a)] = find(b)
    families: dict[str, list[str]] = defaultdict(list)
    for n in names:
        families[find(n)].append(n)

    canonical: dict[str, str | None] = {}     # ชื่อ → สะกดที่ชนะของกลุ่ม (None = เสมอ)
    family_votes: dict[str, dict[str, int]] = {}
    for root, members in families.items():
        top = sorted(members, key=lambda m: -spell[m])
        winner = top[0] if len(top) == 1 or spell[top[0]] > spell[top[1]] else None
        for m in members:
            canonical[m] = winner
        family_votes[root] = {m: spell[m] for m in top}

    # 2) ระดับรหัส: เลือกกลุ่มชื่อที่ชนะของรหัส
    by_code: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r, c, n in valid:
        by_code[c].append((r, n))
    code_family: dict[str, str | None] = {}
    unresolved: list[dict] = []
    for code, lst in by_code.items():
        fam_votes = Counter(find(n) for _, n in lst)
        top = fam_votes.most_common(2)
        if len(top) > 1 and top[0][1] == top[1][1]:
            code_family[code] = None
            unresolved.append({"code": code, "reason": "ชื่อคนละกลุ่มเสียงเท่ากันในรหัสเดียว",
                               "candidates": dict(Counter(n for _, n in lst))})
        else:
            code_family[code] = top[0][0]

    changes: list[dict] = []
    seen_unresolved = {u["code"] for u in unresolved}
    for r, c, n in obs:
        fam = code_family.get(c)
        if fam is None:
            continue                            # รหัสไม่มีชื่อจริงเลย หรือเสมอ — ไม่แก้
        target = canonical[next(m for m in families[fam])]
        if target is None:                      # กลุ่มการสะกดเสมอ: ตัดสินไม่ได้
            if c not in seen_unresolved and not is_placeholder(n, c):
                seen_unresolved.add(c)
                unresolved.append({"code": c, "reason": "สะกดคนละแบบเสียงเท่ากัน",
                                   "candidates": family_votes[fam]})
            continue
        if n == target:
            continue
        if is_placeholder(n, c):
            reason = "ชื่อว่าง/เท่ารหัส/label หมวดวิชา → ใช้ชื่อจากรอบอื่น"
        elif find(n) == fam:
            reason = "สะกดต่างจากเสียงข้างมากของชื่อที่คล้ายกัน"
        else:
            reason = "ชื่อคนละชื่อกับเสียงข้างมากของรหัสนี้"
        changes.append({"run": r, "code": c, "old": n, "new": target, "reason": reason,
                        "votes": family_votes[fam]})
    return {"changes": changes, "unresolved": unresolved,
            "families_with_variants": {k: v for k, v in family_votes.items() if len(v) > 1}}


# ─────────────────────────────────────────────────────────────────────────────
# ใช้ใน pipeline (Lab 7B --recover-codes) — แก้เฉพาะแผนที่กำลังรัน ทุกครั้งที่รัน จึงไม่หายเมื่อรัน Lab 8B ใหม่
# ─────────────────────────────────────────────────────────────────────────────
# แผนหลัก 7 แผน (งานส่ง) — รอบทดลอง (retry/dewm/ctrl) อ่านภาพเดียวกันซ้ำ ผิดแบบเดียวกัน ไม่นับเป็นเสียงอิสระ
MAIN_RUNS = ("AIT", "BIT/no_coop", "BIT/coop", "DSBA/no_coop", "DSBA/coop", "IT/no_coop", "IT/coop")
_REAL_CODE = re.compile(r"\d{8}")


def _vote_name(name: str) -> str:
    return str(name or "").replace("ํา", "ำ").strip()


def _raw_name(c: dict) -> str:
    """ชื่อที่ VLM อ่านมาเดิม (ก่อนขั้นนี้แก้) ตามต้นฉบับทุกไบต์ — รันซ้ำจึงได้ผลเดิม"""
    return str(c["_name_th_from"] if "_name_th_from" in c else (c.get("name_th") or ""))


def _name_is_from_book(c: dict) -> bool:
    """ชื่อของแถวนี้คือข้อความของเล่ม (Tesseract) — แยกรหัสที่รวม / แทนชื่อว่างด้วยชื่อจากเล่ม
    แถวที่ขั้นกู้เอา "แค่รหัส" จากเล่ม (recode / add / name_in_term) ชื่อยังเป็นการอ่านของ Typhoon -> นับเป็นแถว VLM"""
    return "_name_from_book" in c or "split_from" in (c.get("_code_from_book") or {})


def _vlm_rows(courses: list[dict]) -> list[dict]:
    return [c for c in courses if _REAL_CODE.fullmatch(str(c.get("code") or "").strip())
            and not _name_is_from_book(c)]


def fix_plan_names(run: str, courses: list[dict], others: dict[str, list[dict]],
                   books: dict[str, dict[str, dict]]) -> list[dict]:
    """แก้ name_th ของแผน `run` ด้วยฉันทามติชุดเดียวกันทุกแผน (ไม่ขึ้นกับลำดับที่รันแผน):
      - ชื่อดิบของ VLM: แผนละ 1 เสียงต่อ (รหัส, ชื่อ) — แผนนี้ + แผนหลักอื่น (`others`, อ่านอย่างเดียว)
      - เล่ม: `books` = {หลักสูตร: book_index ของเล่มนั้น} เล่มละ 1 เสียงต่อรหัส (Tesseract ผิดซ้ำแบบเดิมทุกหน้า
        เช่น "อัลกอริทีม" จึงนับเป็นหนึ่งเสียง ไม่ใช่หนึ่งเสียงต่อบรรทัด)
    เปลี่ยนเมื่อ: consensus() ให้แก้แถวของแผนนี้ + ชื่อเดิมไม่ใช่ป้าย/ช่องวิชาเลือก + ชื่อที่ชนะ "ถูกอ่านกับรหัสเดียวกันนี้"
    จากแหล่งอื่น (แผนอื่นหรือเล่ม) — กันชื่อคล้ายของคนละวิชา ("เกมขั้นต้น"/"เกมขั้นสูง") ที่รวมเสียงข้ามรหัส
    เก็บชื่อเดิมไว้ใน `_name_th_from`; ถ้ารอบใหม่เสียงไม่ชนะแล้ว คืนชื่อเดิม (ไม่ค้างค่าเก่า)"""
    votes: set[tuple[str, str, str]] = set()
    attested: dict[str, set[str]] = defaultdict(set)
    for r, rows in [(run, courses), *others.items()]:
        for c in _vlm_rows(rows):
            code, name = str(c["code"]).strip(), _vote_name(_raw_name(c))
            votes.add((r, code, name))
            if r != run:
                attested[code].add(name)
    for prog, idx in books.items():
        for code, v in idx.items():
            name = _vote_name(v.get("name"))
            votes.add(("book:" + prog, code, name))
            attested[code].add(name)

    wanted: dict[tuple[str, str], str] = {}
    for ch in consensus(sorted(votes))["changes"]:
        if (ch["run"] == run and not is_placeholder(ch["old"], ch["code"])
                and ch["new"] in attested[ch["code"]]):
            wanted[(ch["code"], ch["old"])] = ch["new"]

    done: list[dict] = []
    for c in _vlm_rows(courses):
        code, raw = str(c["code"]).strip(), _raw_name(c)
        new = wanted.get((code, _vote_name(raw)))
        if new is not None:
            if c.get("name_th") != new:
                c["_name_th_from"] = raw
                c["name_th"] = new
                done.append({"action": "name_th", "code": code, "from": raw, "to": new})
        elif "_name_th_from" in c:                       # เคยแก้ไว้ แต่รอบนี้เสียงไม่ชนะแล้ว -> คืนชื่อที่อ่านได้เดิม
            c["name_th"] = c.pop("_name_th_from")
            done.append({"action": "name_th_undo", "code": code, "to": c["name_th"]})
    return done
