"""รัน load-plan-slots-md กับทุก run ที่มี intermediate_vlm.md + curriculum.db อยู่แล้ว (ไม่ต้อง OCR ใหม่)"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB8 = ROOT / "src" / "ocr_system" / "lab8b_curriculum_db.py"
for md in sorted((ROOT / "runs").rglob("lab7b_output/intermediate_vlm.md")):
    db = md.parent.parent / "lab8b_output" / "curriculum.db"
    if not db.exists():
        print("ข้าม", md.parent.parent.relative_to(ROOT), ": ไม่มี curriculum.db")
        continue
    print(md.parent.parent.relative_to(ROOT).as_posix())
    subprocess.run([sys.executable, str(LAB8), "load-plan-slots-md", "-m", str(md), "-d", str(db)],
                   check=True, env={**os.environ, "PYTHONUTF8": "1"})
