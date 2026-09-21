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
    return SequenceMatcher(None, na, nb).ratio() >= SIM_THRESHOLD


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
