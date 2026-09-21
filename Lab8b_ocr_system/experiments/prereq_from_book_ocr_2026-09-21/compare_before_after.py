"""เทียบ Lab 8B ก่อน/หลังเติมตาราง prerequisite (7 แผนหลัก) — รันจากโฟลเดอร์ Lab8b_ocr_system"""
import json, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = Path(__file__).resolve().parent / "before_lab8b"
PLANS = {"AIT": "AIT", "BIT_no_coop": "BIT/no_coop", "BIT_coop": "BIT/coop", "DSBA_no_coop": "DSBA/no_coop",
         "DSBA_coop": "DSBA/coop", "IT_no_coop": "IT/no_coop", "IT_coop": "IT/coop"}
show_all = "--all" in sys.argv


def pre_rows(db):
    c = sqlite3.connect(db)
    return c.execute("SELECT COUNT(*) FROM prerequisite").fetchone()[0]


tot_b = tot_a = 0
for n, rd in PLANS.items():
    out = ROOT / "runs" / rd / "lab8b_output"
    b_ev = json.loads((D / n / "eval_result.json").read_text(encoding="utf-8"))
    a_ev = json.loads((out / "eval_result.json").read_text(encoding="utf-8"))
    b_vf = {c["id"]: c["ok"] for c in json.loads((D / n / "verify.json").read_text(encoding="utf-8"))}
    a_vf = {c["id"]: c["ok"] for c in json.loads((out / "verify.json").read_text(encoding="utf-8"))}
    cb, ca = sum(q["correct"] for q in b_ev), sum(q["correct"] for q in a_ev)
    vs = ", ".join(f"{k}:{'ผ่าน' if b_vf[k] else 'ตก'}→{'ผ่าน' if a_vf[k] else 'ตก'}" for k in a_vf if b_vf.get(k) != a_vf[k]) or "เหมือนเดิม"
    print(f"{n:13s} prerequisite {pre_rows(D / n / 'curriculum.db')}→{pre_rows(out / 'curriculum.db')} แถว | ตอบถูก {cb}/{len(b_ev)}→{ca}/{len(a_ev)} | verify: {vs}")
    tot_b += cb; tot_a += ca
    for i, (qb, qa) in enumerate(zip(b_ev, a_ev)):
        if qb["correct"] != qa["correct"] or show_all and "prerequisite" in qa["question"]:
            tag = "[ข้อ prerequisite]" if "prerequisite" in qa["question"] else "[ข้ออื่น — ต้องดูว่าแกว่งหรือผลข้างเคียง]"
            print(f"     {tag} #{i}: {qa['question'][:50]} | คาดหวัง {qa['expect'].get('value')} | ก่อน {qb['correct']} ({qb.get('answer')}) → หลัง {qa['correct']} ({qa.get('answer')}) sql={str(qa.get('sql'))[:70]}")
print("รวมตอบถูก", tot_b, "→", tot_a)
