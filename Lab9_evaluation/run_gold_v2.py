"""รัน Lab 8B eval ด้วยชุดคำถามทอง v2 บน curriculum.db ที่มีอยู่แล้ว (ไม่รัน OCR/สกัดใหม่) -> eval_result_v2.json

ต้องเปิด Ollama และใช้ python ของ ocr_system/.venv:
    .venv\\Scripts\\python Lab9_evaluation\\run_gold_v2.py --plan ait        # ทีละแผน
    .venv\\Scripts\\python Lab9_evaluation\\run_gold_v2.py                   # ครบ 7 แผน
ไฟล์คำถามต้องตรง sha256 ที่ล็อกไว้ใน v2/<แผน>_meta.json ไม่งั้นไม่รัน"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluate_lab9 import DEFAULT_RUNS  # noqa: E402

V2 = HERE / "gold_questions" / "v2"
LAB8 = HERE.parent / "Lab7B_Lab8B_ocr_system" / "src" / "ocr_system" / "lab8b_curriculum_db.py"
PLANS = [name for name, _ in DEFAULT_RUNS[:7]]
RUN_DIRS = dict(DEFAULT_RUNS[:7])


def frozen_ok(plan: str, v2_dir: Path = V2) -> bool:
    q = v2_dir / f"{plan}_gold_questions_v2.json"
    meta = json.loads((v2_dir / f"{plan}_meta.json").read_text(encoding="utf-8"))
    return hashlib.sha256(q.read_bytes()).hexdigest() == meta.get("sha256")


def eval_command(plan: str) -> list[str]:
    run_dir = RUN_DIRS[plan]
    return [sys.executable, str(LAB8), "eval", "-d", str(run_dir / "curriculum.db"),
            "-q", str(V2 / f"{plan}_gold_questions_v2.json"), "-o", str(run_dir / "eval_result_v2.json")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", nargs="*", choices=PLANS, default=PLANS)
    args = ap.parse_args()
    if ".venv" not in sys.prefix:
        print("คำเตือน: ไม่ได้รันด้วย ocr_system/.venv — ใช้ .venv\\Scripts\\python", file=sys.stderr)
    for plan in args.plan:
        if not frozen_ok(plan):
            raise SystemExit(f"{plan}: ไฟล์คำถาม v2 ไม่ตรง sha256 ที่ล็อกไว้ — ไม่รัน")
        print(f"\n=== {plan} ===")
        subprocess.run(eval_command(plan), cwd=LAB8.parents[2], check=True, env={**os.environ, "PYTHONUTF8": "1"})


if __name__ == "__main__":
    main()
