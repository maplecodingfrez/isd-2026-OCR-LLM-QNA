"""ทดสอบรอบจับคู่ wildcard ใน evaluate() (lab7b_curriculum.match_wildcards)
รัน: ../.venv/Scripts/python.exe experiments/wildcard_pass_2026-09-21/test_wildcard_pass.py   (จากโฟลเดอร์ Lab8b_ocr_system)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "ocr_system"), str(ROOT / "src")]
import lab7b_curriculum as L  # noqa: E402
import lab7_metrics as M  # noqa: E402

fails = 0


def check(name, cond):
    global fails
    print(("  [ ok ] " if cond else "  [FAIL] ") + name)
    fails += 0 if cond else 1


def row(code, name, y, s, **kw):
    d = {"code": code, "name_th": name, "name_en": kw.get("en"), "credits": "3(3-0-6)", "year": y, "semester": s,
         "category": "หมวดวิชาเลือกเสรี", "type": "เลือก", "prerequisite": "ไม่มี", "flexible_year_semester": kw.get("flex")}
    return d


def align(gt, pred):
    return M.align_multipass(gt, pred, [L.key_strict, L.key_loose])


print("จับคู่ตามชื่อเมื่อ pred เป็น 0/0")
a = align([row("xxxxxxxx", "วิชาเลือกเสรี 1", 4, 1)], [row("xxxxxxx", "วิชาเลือกเสรี 1", 0, 0)])
check("ก่อนรอบ wildcard: ตก 1 เกิน 1", (len(a.missed), len(a.spurious)) == (1, 1))
pairs = L.match_wildcards(a)
check("หลังรอบ wildcard: จับคู่ได้ 1, ไม่เหลือตก/เกิน", len(pairs) == 1 and not a.missed and not a.spurious and len(a.matched) == 1)

print("ต้องไม่จับ")
a = align([row("xxxxxxxx", "วิชาเลือกเสรี 1", 4, 1)], [row("xxxxxxxx", "วิชาเลือกเสรี 2", 0, 0)])
check("เลขท้ายชื่อคนละเลข (เสรี 1 vs เสรี 2)", not L.match_wildcards(a) and len(a.missed) == 1 and len(a.spurious) == 1)
a = align([row("xxxxxxxx", "วิชาเลือกเสรี 1", 4, 1)], [row("xxxxxxxx", "วิชาเลือกเสรี 1", 3, 1)])
check("ปี/ภาคที่ระบุชัดทั้งสองฝั่งไม่ตรง", not L.match_wildcards(a))
a = align([row("06016402", "พื้นฐานทางด้านเทคโนโลยีสารสนเทศ", 1, 1)], [row("06016402", "พื้นฐานทางด้านเทคโนโลยีสารสนเทศ", 2, 1)])
check("แถวรหัสจริงไม่ถูกแตะ", not L.match_wildcards(a) and len(a.missed) == 1 and len(a.spurious) == 1)
a = align([row("xxxxxxxx", "วิชาเลือกเสรี 1", 4, 1)], [row("xxxxxxxx", "การเขียนโปรแกรมขั้นสูง", 0, 0)])
check("ชื่อคนละเรื่อง", not L.match_wildcards(a))

print("เลือกคู่ที่ดีที่สุด")
gt = [row("xxxxxxxx", "วิชาเลือกเสรี 1", 4, 1), row("xxxxxxxx", "วิชาเลือกเสรี 2", 4, 1)]
pr = [row("xxxxxxxx", "วิชาเลือกเสรี 2", 0, 0), row("xxxxxxxx", "วิชาเลือกเสรี 1", 0, 0)]
a = align(gt, pr)
L.match_wildcards(a)
check("ไม่สลับเสรี 1/2 แม้ลำดับแถวกลับกัน", all(g["name_th"] == p["name_th"] for g, p in a.matched) and len(a.matched) == 2)
gt = [row("06026xxx", "วิชาเลือกกลุ่มวิทยาการข้อมูล 1/วิชาเลือกกลุ่มวิศวกรรมข้อมูล 1", 3, 1)]
pr = [row("06026xxx", "วิชาเลือกกลุ่มวิทยาการข้อมูล 1", 0, 0), row("06026xxx", "วิชาเลือกกลุ่มวิศวกรรมข้อมูล 1", 0, 0)]
a = align(gt, pr)
L.match_wildcards(a)
check("เฉลยรวมหลายกลุ่มแถวเดียว: จับได้ 1 อีก 1 ยังเป็นแถวเกิน (ไม่ปิดบังความต่างของ granularity)", len(a.matched) == 1 and len(a.spurious) == 1)

print("evaluate() ครบวงจร")
gt = {"courses": [row("06016402", "พื้นฐานทางด้านเทคโนโลยีสารสนเทศ", 1, 1), row("xxxxxxxx", "วิชาเลือกเสรี 1", 4, 1)]}
pred = {"courses": [row("06016402", "พื้นฐานทางด้านเทคโนโลยีสารสนเทศ", 1, 1), row("xxxxxxx", "วิชาเลือกเสรี 1", 0, 0)]}
stats, al = L.evaluate(pred, gt)
check("alignment.strict คงตัวเลขแบบเดิม (ตก 1 เกิน 1)", al["strict"]["missed"] == 1 and al["strict"]["spurious"] == 1)
check("ตัวเลขหลักหลังรอบ wildcard: ตก 0 เกิน 0, P=R=1", al["missed"] == 0 and al["spurious"] == 0 and al["precision"] == 1 and al["recall"] == 1)
check("wildcard_pass_matched = 1", al["wildcard_pass_matched"] == 1)
check("year_sem ไม่นับแถว wildcard ที่จับจากรอบใหม่ (n=1 เฉพาะแถวรหัสจริง)", stats["year_sem"].n_items == 1)
check("ฟิลด์อื่นยังนับแถว wildcard (code n=2)", stats["code"].n_items == 2)

print(f"\n{'ผ่านทั้งหมด' if not fails else 'ไม่ผ่าน ' + str(fails) + ' ข้อ'}")
sys.exit(1 if fails else 0)
