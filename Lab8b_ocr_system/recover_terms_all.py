"""ทดลอง/ใช้ recover_terms กับ run เดิม: แปลง pred JSON ใหม่ด้วย --markdown แล้วเทียบกับ curriculum.json เดิม

python recover_terms_all.py           # dry-run: แสดงความต่าง ไม่เขียนไฟล์
python recover_terms_all.py --apply   # เขียน curriculum.json ใหม่ (สำรองของเดิมเป็น .before_recover.json)
                                      # แล้ว load --replace + load-plan-slots-md + verify ให้ run ที่เปลี่ยน
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB8 = ROOT / "src" / "ocr_system" / "lab8b_curriculum_db.py"
sys.path.insert(0, str(LAB8.parent))
from lab8b_curriculum_db import convert_lab7b  # noqa: E402

APPLY = "--apply" in sys.argv
env = {**os.environ, "PYTHONUTF8": "1"}
for md in sorted((ROOT / "runs").rglob("lab7b_output/intermediate_vlm.md")):
    run = md.parent.parent
    out = run / "lab8b_output"
    cur_path = out / "curriculum.json"
    conv = json.loads((out / "curriculum.conversion.json").read_text(encoding="utf-8")) if (out / "curriculum.conversion.json").exists() else {}
    pred = run / "lab7b_output" / "pred_vlm.json"
    if not (cur_path.exists() and pred.exists()):
        continue
    cur = json.loads(cur_path.read_text(encoding="utf-8"))
    prog = cur["program"]
    data = json.loads(pred.read_text(encoding="utf-8"))
    kw = dict(program_id=prog["program_id"], program_name=prog["name_th"],
              total_credits=prog["total_credits"], years=prog["years"])
    base, _ = convert_lab7b(data, **kw)
    new, rep = convert_lab7b(data, markdown=md.read_text(encoding="utf-8"), **kw)
    same_baseline = base["plan"] == cur["plan"]
    delta = [(p["year"], p["semester"], p["code"]) for p in new["plan"] if p not in base["plan"]]
    name = run.relative_to(ROOT / "runs").as_posix()
    print(f"{name:20s} เดิมตรงกับ curriculum.json: {same_baseline} · กู้ปี/เทอม {len(rep['terms_recovered_from_markdown'])} วิชา -> เพิ่มในแผน {delta}")
    if APPLY and delta:
        if not same_baseline:
            print("   ข้าม: curriculum.json เดิมไม่ได้มาจาก pred_vlm.json ตรง ๆ (อาจมีการแพตช์) — ไม่เขียนทับ")
            continue
        shutil.copy(cur_path, cur_path.with_suffix(".before_recover.json"))
        cur_path.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
        cur_path.with_suffix(".conversion.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        db = out / "curriculum.db"
        # load --replace ลบทั้งไฟล์ DB — ถ้าเดิมมีตารางวิชาเลือก (load-electives) ต้องโหลดกลับ
        con = sqlite3.connect(db)
        had_electives = con.execute("SELECT COUNT(*) FROM elective_group").fetchone()[0] > 0
        con.close()                               # Windows ล็อกไฟล์ที่ยังเปิดอยู่ — ต้องปิดก่อน load --replace
        electives = next((c for c in (run / "electives.json", run.parent / "electives.json")
                          if c.exists()), None)
        steps = [["load", "-i", str(cur_path), "-d", str(db), "--replace"]]
        if had_electives and electives:
            steps.append(["load-electives", "-i", str(electives), "-d", str(db),
                          "--program-id", prog["program_id"]])
        for cmd in (*steps,
                    ["load-plan-slots-md", "-m", str(md), "-d", str(db)],
                    ["verify", "-d", str(db), "-o", str(out / "verify.json")]):
            subprocess.run([sys.executable, str(LAB8), *cmd], check=True, env=env, stdout=subprocess.DEVNULL)
        print("   เขียนใหม่ + โหลด DB + plan_slot + verify แล้ว")
