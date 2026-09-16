"""Regenerate evaluation.json + comparison.csv for one or all Lab7B runs, using the
existing pred_vlm.json (no VLM re-call) against the current ground_truth_scoped/*.json.

เหตุผลที่ต้องมีสคริปต์นี้: `lab7b_curriculum.py --eval-only` แค่ print ผลออก stdout เฉยๆ
ไม่เขียนไฟล์ (ดูโค้ดจริงบรรทัด eval_only branch) ส่วน `evaluation.json`/`comparison.csv`
ที่มีอยู่ในแต่ละ run ถูกเขียนไว้ตอนรันเต็มรอบครั้งแรก (ก่อนแก้ typo ใน ground truth) เลย
ค้างเป็นตัวเลขเก่า สคริปต์นี้เรียก evaluate()/verify_internal()/M.stats_to_dict()/M.save_csv()
ตัวเดียวกับที่ main() ใช้ตอนรันเต็ม แล้วเขียนทับไฟล์ทั้งสองให้ตรงกับ GT ปัจจุบัน

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
}


def regenerate_one(name: str, outdir: Path, gt_path: Path) -> None:
    pred_path = outdir / "pred_vlm.json"
    pred = json.loads(pred_path.read_text(encoding="utf-8"))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))

    stats, align = evaluate(pred, gt)
    M.print_table(stats, f"{name} (vlm)")
    print(f"  จับคู่วิชา: เจอ {align['matched']}/{align['gt_total']} "
          f"| ตก {align['missed']} | แต่งเกิน {align['spurious']}   "
          f"P={align['precision']:.3f} R={align['recall']:.3f} F1={align['f1']:.3f}")
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


def main() -> None:
    names = sys.argv[1:] or list(RUNS.keys())
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
