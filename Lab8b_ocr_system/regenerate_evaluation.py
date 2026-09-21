"""Regenerate evaluation.json + comparison.csv for one or all Lab7B runs, using the
existing pred_vlm.json (no VLM re-call) against the current ground_truth_scoped/*.json.

เหตุผลที่ต้องมีสคริปต์นี้: `lab7b_curriculum.py --eval-only` แค่ print ผลออก stdout เฉยๆ
ไม่เขียนไฟล์ (ดูโค้ดจริงบรรทัด eval_only branch) ส่วน `evaluation.json`/`comparison.csv`
ที่มีอยู่ในแต่ละ run ถูกเขียนไว้ตอนรันเต็มรอบครั้งแรก (ก่อนแก้ typo ใน ground truth) เลย
ค้างเป็นตัวเลขเก่า สคริปต์นี้เรียก evaluate()/verify_internal()/M.stats_to_dict()/M.save_csv()
ตัวเดียวกับที่ main() ใช้ตอนรันเต็ม แล้วเขียนทับไฟล์ทั้งสองให้ตรงกับ GT ปัจจุบัน

⚠️ ต้องรันผ่าน .venv ที่ activate แล้ว (มี pythainlp) — ถ้าไม่มี WER จะ fallback เป็นตัดคำด้วยช่องว่าง
เงียบๆ ได้เลขผิดแล้วเขียนทับไฟล์ ตรวจว่าบรรทัด "tokenizer สำหรับ WER:" ต้องเป็น pythainlp/newmm
ถ้า activate ไม่ได้: ../.venv/Scripts/python.exe regenerate_evaluation.py

Usage:
    python regenerate_evaluation.py                # ทำครบทั้ง 7 run
    python regenerate_evaluation.py ait bit_coop    # ทำเฉพาะ run ที่ระบุ (ชื่อดูจาก RUNS ด้านล่าง)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "ocr_system"))
sys.path.insert(0, str(ROOT / "src"))

from lab7b_curriculum import evaluate, verify_internal  # noqa: E402
import lab7_metrics as M  # noqa: E402

GT_DIR = ROOT.parent / "Lab9_evaluation" / "ground_truth_scoped"

RUNS = {
    "ait":          (ROOT / "runs" / "AIT" / "lab7b_output",            GT_DIR / "ait_scoped.json"),
    "bit_no_coop":  (ROOT / "runs" / "BIT" / "no_coop" / "lab7b_output", GT_DIR / "bit_no_coop_scoped.json"),
    "bit_coop":     (ROOT / "runs" / "BIT" / "coop" / "lab7b_output",    GT_DIR / "bit_coop_scoped.json"),
    "dsba_no_coop": (ROOT / "runs" / "DSBA" / "no_coop" / "lab7b_output", GT_DIR / "dsba_no_coop_scoped.json"),
    "dsba_coop":    (ROOT / "runs" / "DSBA" / "coop" / "lab7b_output",   GT_DIR / "dsba_coop_scoped.json"),
    "it_no_coop":   (ROOT / "runs" / "IT" / "no_coop" / "lab7b_output",  GT_DIR / "it_no_coop_scoped.json"),
    "it_coop":      (ROOT / "runs" / "IT" / "coop" / "lab7b_output",     GT_DIR / "it_coop_scoped.json"),
    # รอบทดลอง AIT (ตัดตราน้ำ + อ่านซ้ำ) — เฉลยชุดเดียวกับ ait; ไม่อยู่ในค่า default ด้านล่าง (ระบุชื่อเองเมื่อต้องการ)
    **{f"ait_dewm{i}": (ROOT / "runs" / f"AIT_dewm{i}" / "lab7b_output", GT_DIR / "ait_scoped.json") for i in range(1, 7)},
    # รอบทดลองตัดตราน้ำ + อ่านซ้ำของ BIT/IT (run_lab8b_<แผน>_dewm.py) — เฉลยชุดเดียวกับรอบหลักของแผนนั้น; ไม่อยู่ใน DEFAULT_RUNS
    "bit_no_coop_dewm": (ROOT / "runs" / "BIT" / "no_coop_dewm" / "lab7b_output", GT_DIR / "bit_no_coop_scoped.json"),
    "bit_coop_dewm":    (ROOT / "runs" / "BIT" / "coop_dewm" / "lab7b_output",    GT_DIR / "bit_coop_scoped.json"),
    "it_no_coop_dewm":  (ROOT / "runs" / "IT" / "no_coop_dewm" / "lab7b_output",  GT_DIR / "it_no_coop_scoped.json"),
    "it_coop_dewm":     (ROOT / "runs" / "IT" / "coop_dewm" / "lab7b_output",     GT_DIR / "it_coop_scoped.json"),
}
DEFAULT_RUNS = ["ait", "bit_no_coop", "bit_coop", "dsba_no_coop", "dsba_coop", "it_no_coop", "it_coop"]


def regenerate_one(name: str, outdir: Path, gt_path: Path) -> None:
    pred_path = outdir / "pred_vlm.json"
    pred = json.loads(pred_path.read_text(encoding="utf-8"))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))

    stats, align = evaluate(pred, gt)
    M.print_table(stats, f"{name} (vlm)")
    print(f"  จับคู่วิชา: เจอ {align['matched']}/{align['gt_total']} "
          f"| ตก {align['missed']} | แต่งเกิน {align['spurious']}   "
          f"P={align['precision']:.3f} R={align['recall']:.3f} F1={align['f1']:.3f}")
    st = align.get("strict")
    if st:
        print(f"    (ก่อนรอบจับคู่ wildcard: ตก {st['missed']} | แต่งเกิน {st['spurious']}   "
              f"P={st['precision']:.3f} R={st['recall']:.3f} F1={st['f1']:.3f} — รอบ wildcard จับเพิ่ม {align['wildcard_pass_matched']} คู่)")
    M.print_classification_report(align["classification"]["ctype"], "ctype (บังคับ/เลือก)")
    M.print_classification_report(align["classification"]["category"], "category (หมวดวิชา)")

    d = M.stats_to_dict(stats)
    d["alignment"] = align
    d["internal_check"] = verify_internal(pred)
    combined = {"vlm": d}

    (outdir / "evaluation.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    M.save_csv(stats, str(outdir / "comparison.csv"), extra={"pipeline": "vlm"})
    print(f"  ✓ เขียนทับ {outdir / 'evaluation.json'} และ {outdir / 'comparison.csv'}\n")


def require_thai_tokenizer() -> None:
    """หยุดก่อนเขียนไฟล์ ถ้า WER จะถูกคำนวณด้วย tokenizer ที่ไม่ใช่ pythainlp
    (lab7_metrics fallback เป็นตัดคำด้วยช่องว่างแบบเงียบๆ ได้ WER ผิดแล้วเขียนทับ evaluation.json)"""
    if M.TOKENIZER_NAME.startswith("pythainlp"):
        return
    raise SystemExit(
        f"❌ tokenizer สำหรับ WER คือ '{M.TOKENIZER_NAME}' ไม่ใช่ pythainlp — WER ภาษาไทยจะผิด "
        "จึงยังไม่เขียนไฟล์ใดๆ\n"
        f"   Python ที่ใช้: {sys.executable}\n"
        "   แก้: activate .venv (มี pythainlp) แล้วรันใหม่ หรือรัน  "
        "../.venv/Scripts/python.exe regenerate_evaluation.py")


def main() -> None:
    require_thai_tokenizer()
    names = sys.argv[1:] or DEFAULT_RUNS
    unknown = [n for n in names if n not in RUNS]
    if unknown:
        raise SystemExit(f"ไม่รู้จัก run: {unknown} (ตัวเลือกคือ {list(RUNS.keys())})")

    for n in names:
        outdir, gt_path = RUNS[n]
        print("=" * 70)
        print(f"  {n}")
        print("=" * 70)
        regenerate_one(n, outdir, gt_path)


if __name__ == "__main__":
    main()
