"""รันซ้ำ (retry) ทุกหลักสูตรที่ยังไม่มีผลรันซ้ำ เพื่อทำ stability check ให้ครบ 7 หลักสูตร/แผน — Lab9 ข้อ 3

รันสคริปต์ run_lab8b_<name>_retry.py ทีละตัวตามลำดับ (เรียกโมเดลจริง ช้ามาก — หลายชั่วโมงรวมกัน)
- ข้าม run ที่มีผลอยู่แล้ว (มี lab8b_output/eval_result.json) เว้นแต่ใส่ --force
- ตัวไหนพัง จะบันทึกไว้แล้วไปตัวถัดไป ท้ายสุดสรุปว่าอะไรสำเร็จ/พัง (รันซ้ำได้ ตัวที่เสร็จแล้วจะถูกข้าม)
- ไม่ทับผลเดิมของ run ปกติ (แต่ละตัวเขียนลงโฟลเดอร์ *_retry ของตัวเอง)

วิธีรัน (จากโฟลเดอร์ Lab8b_ocr_system, ต้อง activate .venv และเปิด Ollama ก่อน):
    python run_all_stability_retries.py            # ทั้ง 4 ที่ยังไม่มี: ait, bit_no_coop, dsba_no_coop, it_no_coop
    python run_all_stability_retries.py ait it_no_coop     # เลือกบางตัว
    python run_all_stability_retries.py --force    # รันใหม่แม้มีผลแล้ว
แล้วดูผล:  cd ../Lab9_evaluation && python evaluate_lab9.py
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = {
    "ait": ROOT / "runs" / "AIT_retry",
    "bit_no_coop": ROOT / "runs" / "BIT" / "no_coop_retry",
    "dsba_no_coop": ROOT / "runs" / "DSBA" / "no_coop_retry",
    "it_no_coop": ROOT / "runs" / "IT" / "no_coop_retry",
}


def main() -> None:
    args = sys.argv[1:]
    force = "--force" in args
    names = [a for a in args if not a.startswith("--")] or list(TARGETS)
    unknown = [n for n in names if n not in TARGETS]
    if unknown:
        raise SystemExit(f"ไม่รู้จัก: {unknown} (ตัวเลือกคือ {list(TARGETS)})")

    summary = []
    for n in names:
        done = (TARGETS[n] / "lab8b_output" / "eval_result.json").exists()
        if done and not force:
            summary.append((n, "ข้าม (มีผลแล้ว)", 0.0))
            continue
        print("=" * 70)
        print(f"  {n}")
        print("=" * 70, flush=True)
        t0 = time.time()
        rc = subprocess.run([sys.executable, str(ROOT / f"run_lab8b_{n}_retry.py")], cwd=ROOT).returncode
        summary.append((n, "สำเร็จ" if rc == 0 else f"พัง (exit {rc})", time.time() - t0))

    print()
    print("=" * 70)
    print("  สรุป")
    print("=" * 70)
    for n, status, sec in summary:
        print(f"  {n:<14} {status:<20} {sec / 60:6.1f} นาที")
    if any("พัง" in s for _, s, _ in summary):
        print()
        print("มีตัวที่พัง — แก้แล้วรันคำสั่งเดิมซ้ำ ตัวที่สำเร็จแล้วจะถูกข้าม")


if __name__ == "__main__":
    main()
