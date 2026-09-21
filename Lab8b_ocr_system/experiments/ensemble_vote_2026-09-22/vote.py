"""ทดลอง: โหวตข้างมากข้ามรัน OCR อิสระของเอกสารชุดเดียวกัน เพื่อลดความแกว่ง (สไลด์ ch9 หน้า 27: Voting/Averaging ข้าม seed —
"ต้นทุนต่ำสุด เหมาะเป็นด่านแรกของโปรเจกต์") — เป็นการวัดผลแยก ไม่แทนที่ผลหลัก ไม่ใช้เฉลยสร้างผล (เฉลยใช้ตัดสินผลเท่านั้น)

รัน (จาก Lab8b_ocr_system): PYTHONUTF8=1 ../.venv/Scripts/python.exe experiments/ensemble_vote_2026-09-22/vote.py [--retries-new] [แผน ...]
  ค่าเริ่มต้นใช้ผู้โหวตจาก: (ก) รอบหลักปัจจุบัน (ข) รอบหลักเดิมใน git (ก่อนรันใหม่ 2026-09-22) (ค) รอบ retry เดิมใน git
  --retries-new ใช้รอบ retry ปัจจุบันในโฟลเดอร์ runs/ (หลังรัน retry ใหม่ด้วยโค้ดปัจจุบันเสร็จ) แทน (ค)

วิธีโหวต (กำหนดได้ ไม่มีพารามิเตอร์ปรับ):
  - คีย์แถว = (รหัส 8 หลัก, ปี, ภาค); แถวถูกเก็บถ้าพบในผู้โหวต >= n//2 + 1 คน (n=3 → 2; n=4 → 3)
  - ค่าในแถว (ชื่อไทย/อังกฤษ, หน่วยกิต, หมวด, ประเภท, prerequisite ฯลฯ) = เสียงข้างมากรายฟิลด์ของผู้โหวตที่มีแถวนั้น เสมอ → ใช้ค่าของรอบหลักปัจจุบัน
  - แถวรหัส wildcard / ไม่ใช่รหัสจริง: ใช้ตามรอบหลักปัจจุบันทั้งหมด (ไม่โหวต)
รายงาน: F1/P/R ของผู้โหวตแต่ละราย (เฉลี่ย/ต่ำสุด/สูงสุด) เทียบกับผลโหวต; ตัวอย่างเล็ก (3–4 รัน/แผน) จึงเป็นแนวโน้ม ไม่ใช่ข้อสรุป
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
sys.path[:0] = [str(ROOT / "src" / "ocr_system"), str(ROOT / "src")]
import lab7b_curriculum as L  # noqa: E402

GT_DIR = REPO / "Lab9_evaluation" / "ground_truth_scoped"
PLANS = {  # แผน: (โฟลเดอร์หลัก, โฟลเดอร์ retry, ไฟล์เฉลย)
    "ait": ("AIT", "AIT_retry", "ait_scoped.json"),
    "bit_no_coop": ("BIT/no_coop", "BIT/no_coop_retry", "bit_no_coop_scoped.json"),
    "bit_coop": ("BIT/coop", "BIT/coop_retry", "bit_coop_scoped.json"),
    "dsba_no_coop": ("DSBA/no_coop", "DSBA/no_coop_retry", "dsba_no_coop_scoped.json"),
    "dsba_coop": ("DSBA/coop", "DSBA/coop_retry", "dsba_coop_scoped.json"),
    "it_no_coop": ("IT/no_coop", "IT/no_coop_retry", "it_no_coop_scoped.json"),
    "it_coop": ("IT/coop", "IT/coop_retry", "it_coop_scoped.json"),
}
OLD_COMMIT = "96d34c9^"       # คอมมิตก่อนรัน 7 แผนหลักใหม่ (2026-09-22) — ผลเดิมของรอบหลักและ retry
CODE = re.compile(r"^\d{8}$")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
RETRIES_NEW = "--retries-new" in sys.argv
names = args or list(PLANS)


def from_git(rel):
    try:
        raw = subprocess.check_output(["git", "show", f"{OLD_COMMIT}:Lab8b_ocr_system/runs/{rel}/lab7b_output/pred_vlm.json"],
                                      cwd=REPO, stderr=subprocess.DEVNULL)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def from_disk(rel):
    p = ROOT / "runs" / rel / "lab7b_output" / "pred_vlm.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def key(r):
    c = str(r.get("code") or "")
    y, s = r.get("year"), r.get("semester")
    return (c, str(y), str(s)) if CODE.match(c) and y not in (None, "None") else None


def vote(voters):
    """voters[0] = รอบหลักปัจจุบัน (ตัวตั้งต้น/ตัดสินกรณีเสมอ)"""
    n = len(voters)
    need = n // 2 + 1
    rows = [{key(r): r for r in v["courses"] if key(r)} for v in voters]
    seen = Counter(k for d in rows for k in d)
    base = voters[0]
    out = [r for r in base["courses"] if not key(r)]                 # แถว wildcard/ไม่ใช่รหัสจริง: ตามรอบหลัก
    kept = [k for k in dict.fromkeys(k for d in rows for k in d) if seen[k] >= need]
    for k in kept:
        have = [d[k] for d in rows if k in d]
        row = dict(have[0])                                          # เริ่มจากผู้โหวตแรกที่มีแถวนี้ (รอบหลักถ้ามี)
        for f in {f for r in have for f in r}:
            vals = [json.dumps(r.get(f), ensure_ascii=False, sort_keys=True) for r in have]
            top, cnt = Counter(vals).most_common(1)[0]
            ties = [v for v, c in Counter(vals).items() if c == cnt]
            row[f] = json.loads(top if len(ties) == 1 else vals[0])   # เสมอ → ค่าของผู้โหวตแรก
        out.append(row)
    return {**base, "courses": out}


lines = ["| แผน | ผู้โหวต | F1 รายรัน (เฉลี่ย / ต่ำสุด / สูงสุด) | **F1 ผลโหวต** | P / R ผลโหวต | ตก / เกิน ผลโหวต | ตกเฉลี่ยรายรัน |", "|---|---|---|---|---|---|---|"]
summary = []
for n in names:
    d, rdir, gtf = PLANS[n]
    gt = json.loads((GT_DIR / gtf).read_text(encoding="utf-8"))
    cur = from_disk(d)
    voters = [cur, from_git(d)]
    voters.append(from_disk(rdir) if RETRIES_NEW else from_git(rdir))
    if n == "ait" and RETRIES_NEW:                                   # AIT มี retry เพิ่ม (tag 2, 3)
        voters += [from_disk("AIT_retry2"), from_disk("AIT_retry3")]
    voters = [v for v in voters if v and v.get("courses")]
    if len(voters) < 3:
        lines.append(f"| {n} | {len(voters)} | ผู้โหวตไม่พอ (ต้อง ≥ 3) | | | | |")
        continue
    singles = []
    for v in voters:
        _, al = L.evaluate(v, gt)
        singles.append((al["f1"], al["missed"]))
    voted = vote(voters)
    _, av = L.evaluate(voted, gt)
    f1s = [s[0] for s in singles]
    lines.append(f"| {n} | {len(voters)} | {sum(f1s) / len(f1s):.3f} / {min(f1s):.3f} / {max(f1s):.3f} | **{av['f1']:.3f}** | {av['precision']:.3f} / {av['recall']:.3f} | {av['missed']} / {av['spurious']} | {sum(s[1] for s in singles) / len(singles):.1f} |")
    summary.append((n, sum(f1s) / len(f1s), min(f1s), max(f1s), av["f1"]))

if summary:
    lines.append("")
    lines.append(f"**เฉลี่ย {len(summary)} แผน:** F1 รายรัน (เฉลี่ยของค่าเฉลี่ย) {sum(s[1] for s in summary) / len(summary):.3f} · "
                 f"รายรันที่แย่สุดเฉลี่ย {sum(s[2] for s in summary) / len(summary):.3f} · รายรันที่ดีสุดเฉลี่ย {sum(s[3] for s in summary) / len(summary):.3f} · "
                 f"**ผลโหวต {sum(s[4] for s in summary) / len(summary):.3f}** · ผลโหวตดีกว่าค่าเฉลี่ยรายรันใน {sum(1 for s in summary if s[4] > s[1])}/{len(summary)} แผน, "
                 f"ดีกว่ารันที่ดีสุดใน {sum(1 for s in summary if s[4] > s[3])}/{len(summary)} แผน")
text = "\n".join(lines)
tag = "retries_new" if RETRIES_NEW else "retries_old_from_git"
res = ROOT / "experiments" / "ensemble_vote_2026-09-22" / f"result_{tag}.md"
res.write_text(f"# ผลโหวตข้างมากข้ามรัน ({tag})\n\nสร้างโดย `vote.py` — ดูเงื่อนไข/ข้อจำกัดในหัวไฟล์สคริปต์\n\n" + text + "\n", encoding="utf-8")
print(text)
print(f"\nเขียน {res}")
