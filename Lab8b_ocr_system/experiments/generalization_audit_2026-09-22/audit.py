"""ตรวจความน่าเชื่อถือของตัวเลข: กัน overfit / underfit / การหลอกตัวเองด้วยเฉลย — อ่านผลที่มีอยู่แล้ว ไม่ OCR ใหม่ ไม่แก้เฉลย

รัน (จาก Lab8b_ocr_system): PYTHONUTF8=1 ../.venv/Scripts/python.exe experiments/generalization_audit_2026-09-22/audit.py [แผน ...]
เขียนผลที่ experiments/generalization_audit_2026-09-22/result.md

ตรวจ 2 เรื่อง (เรื่องที่ 3 — รหัสวิชา/เงื่อนไขเฉพาะเล่มฝังในกฎหรือไม่ — ตรวจด้วย grep/tokenize แยกต่างหาก ผลอยู่ใน PROGRESS.md):
  1. ความไวของเกณฑ์จับคู่ wildcard (_WILD_NAME_MIN = 0.6): ถ้าผลเปลี่ยนมากเมื่อขยับเกณฑ์ = ปรับให้พอดีข้อมูลชุดเดียว (overfit)
  2. ตัวเลข prerequisite ที่ไม่หลอกตัวเอง (สไลด์ ch9 accuracy paradox): baseline ตอบ "ไม่มี" ทุกแถว, ความแม่นเฉพาะแถวที่มีวิชาบังคับก่อนจริง,
     ค่าผิด/ไม่ทราบ, และรายงานเทียบทั้ง "เฉลยเดิมก่อนแก้" กับ "เฉลยที่แก้แล้ว" (เพื่อให้เห็นขนาดผลของการแก้เฉลย)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "ocr_system"), str(ROOT / "src")]
import lab7b_curriculum as L  # noqa: E402

GT_DIR = ROOT.parent / "Lab9_evaluation" / "ground_truth_scoped"
BEFORE_GT = ROOT / "experiments" / "prereq_from_book_ocr_2026-09-21" / "before_gt"
RUNS = {
    "ait": ("AIT", "ait_scoped.json"), "bit_no_coop": ("BIT/no_coop", "bit_no_coop_scoped.json"),
    "bit_coop": ("BIT/coop", "bit_coop_scoped.json"), "dsba_no_coop": ("DSBA/no_coop", "dsba_no_coop_scoped.json"),
    "dsba_coop": ("DSBA/coop", "dsba_coop_scoped.json"), "it_no_coop": ("IT/no_coop", "it_no_coop_scoped.json"),
    "it_coop": ("IT/coop", "it_coop_scoped.json"),
}
names = sys.argv[1:] or list(RUNS)
CODE = re.compile(r"^\d{8}$")


def load(name):
    d, gtf = RUNS[name]
    pred = json.loads((ROOT / "runs" / d / "lab7b_output" / "pred_vlm.json").read_text(encoding="utf-8"))
    gt = json.loads((GT_DIR / gtf).read_text(encoding="utf-8"))
    return pred, gt, gtf


out = []
P = out.append

# ── 1. ความไวของเกณฑ์ wildcard ─────────────────────────────────────────────
P("## 1. ความไวของเกณฑ์จับคู่ wildcard (`_WILD_NAME_MIN`, ใช้จริง = 0.6)\n")
P("ขยับเกณฑ์แล้วดูจำนวนคู่ที่จับเพิ่ม และ F1 — ถ้าเปลี่ยนมากรอบ 0.6 แปลว่าเกณฑ์ถูกปรับให้พอดีข้อมูล\n")
grid = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
P("| แผน | strict F1 | " + " | ".join(f"เกณฑ์ {g}: คู่เพิ่ม / F1" for g in grid) + " |")
P("|---|---|" + "---|" * len(grid))
orig = L._WILD_NAME_MIN
try:
    for n in names:
        pred, gt, _ = load(n)
        cells = []
        strict = None
        for g in grid:
            L._WILD_NAME_MIN = g
            _, al = L.evaluate(pred, gt)
            strict = al["strict"]["f1"]
            cells.append(f"{al['wildcard_pass_matched']} / {al['f1']:.3f}")
        P(f"| {n} | {strict:.3f} | " + " | ".join(cells) + " |")
finally:
    L._WILD_NAME_MIN = orig
P("")

# ── 2. prerequisite ไม่หลอกตัวเอง ────────────────────────────────────────────


def prereq_table(pred, gt):
    """จับคู่ด้วยรหัส 8 หลักที่ไม่ซ้ำ (ไม่ใช้ปี/ภาค) แล้วนับ; แถว wildcard/รหัสซ้ำไม่นับ"""
    pc = {}
    for r in pred["courses"]:
        c = str(r.get("code") or "")
        if CODE.match(c):
            pc.setdefault(c, []).append(r.get("prerequisite"))
    gc = {}
    for r in gt["courses"]:
        c = str(r.get("code") or "")
        if CODE.match(c):
            gc.setdefault(c, []).append(r.get("prerequisite"))
    rows = []
    for c, gv in gc.items():
        if len(set(map(str, gv))) != 1 or c not in pc:
            continue                         # เฉลยขัดกันเอง/หาไม่เจอในผล → ไม่นับ (ไม่ตัดสินแทน)
        rows.append((c, gv[0], pc[c][0]))
    return rows


def summarize(rows):
    n = len(rows)
    pos = [r for r in rows if r[1] not in (None, "ไม่มี")]
    claimed = [r for r in rows if r[2] is not None]
    correct = [r for r in rows if r[2] == r[1]]
    wrong = [r for r in claimed if r[2] != r[1]]
    claimed_pos = [r for r in claimed if r[2] != "ไม่มี"]
    return dict(n=n, pos=len(pos), majority=sum(1 for r in rows if r[1] == "ไม่มี") / n if n else 0,
                exact=len(correct) / n if n else 0, coverage=len(claimed) / n if n else 0,
                acc_claimed=(len(claimed) - len(wrong)) / len(claimed) if claimed else 0, wrong=len(wrong),
                unknown=n - len(claimed), pos_hit=sum(1 for r in pos if r[2] == r[1]),
                pos_any=sum(1 for r in pos if r[2] not in (None, "ไม่มี")),
                claimed_pos=len(claimed_pos), claimed_pos_ok=sum(1 for r in claimed_pos if r[2] == r[1]))


P("## 2. prerequisite: ตัวเลขที่ไม่หลอกตัวเอง\n")
P("แถวที่นับ = วิชารหัส 8 หลักที่เฉลยไม่ขัดกันเองและมีในผลของเรา (แถว wildcard ไม่นับ) — **ไม่ทราบ = เราไม่ใส่ฟิลด์** (ไม่นับเป็นค่าผิด แต่นับเป็นไม่ถูก)\n")
P("| แผน | แถว | มีวิชาบังคับก่อนจริง | baseline ตอบ \"ไม่มี\" ทุกแถว | ตรงเฉลย (exact) | ครอบคลุม (ใส่ค่า) | แม่นเฉพาะที่ใส่ค่า | **ค่าผิด** | ไม่ทราบ | ได้ถูกตรง (แถวมีวิชาบังคับก่อน) | ใส่รหัสแล้วถูก |")
P("|---|---|---|---|---|---|---|---|---|---|---|")
for n in names:
    pred, gt, _ = load(n)
    s = summarize(prereq_table(pred, gt))
    P(f"| {n} | {s['n']} | {s['pos']} | {s['majority']:.3f} | {s['exact']:.3f} | {s['coverage']:.3f} | {s['acc_claimed']:.3f} | **{s['wrong']}** | {s['unknown']} | {s['pos_hit']}/{s['pos']} | {s['claimed_pos_ok']}/{s['claimed_pos']} |")
P("")
P("อ่านตาราง: ถ้า \"ตรงเฉลย (exact)\" ไม่สูงกว่า baseline มากนัก แปลว่าตัวเลขสูงเพราะเฉลยส่วนใหญ่เป็น \"ไม่มี\" (accuracy paradox) — ให้ดู \"ได้ถูกตรง (แถวมีวิชาบังคับก่อน)\" และ \"ค่าผิด\" แทน\n")

P("### เทียบเฉลยเดิม (ก่อนแก้ 6 แถว) กับเฉลยที่แก้แล้ว\n")
P("ขนาดผลของการแก้เฉลย — เฉพาะแผนที่แก้ไฟล์ (AIT, IT no-coop, IT coop)\n")
P("| แผน | เฉลย | exact | ค่าผิด | ได้ถูกตรง (แถวมีวิชาบังคับก่อน) |")
P("|---|---|---|---|---|")
for n in [x for x in names if x in ("ait", "it_no_coop", "it_coop")]:
    pred, gt_new, gtf = load(n)
    gt_old = json.loads((BEFORE_GT / gtf).read_text(encoding="utf-8"))
    for lab, g in (("เดิม (ก่อนแก้)", gt_old), ("แก้แล้ว", gt_new)):
        s = summarize(prereq_table(pred, g))
        P(f"| {n} | {lab} | {s['exact']:.3f} | {s['wrong']} | {s['pos_hit']}/{s['pos']} |")
P("")

res = ROOT / "experiments" / "generalization_audit_2026-09-22" / "result.md"
res.write_text("# ตรวจความน่าเชื่อถือของตัวเลข (overfit / underfit / เฉลย)\n\nสร้างโดย `audit.py` — อ่านผลที่มีอยู่ ไม่ OCR ใหม่ ไม่แก้เฉลย\n\n" + "\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
print(f"\nเขียน {res}")
