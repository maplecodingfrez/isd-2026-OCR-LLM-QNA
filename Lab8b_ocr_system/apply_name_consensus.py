"""ฉันทามติชื่อวิชาข้ามทุก run (ขั้นหลังรันครบทุกแผน) — ดู src/ocr_system/name_consensus.py

python apply_name_consensus.py           # dry-run: แสดงสิ่งที่จะแก้ ไม่เขียนไฟล์
python apply_name_consensus.py --apply   # แก้ course.name_th ใน curriculum.json (สำรอง .before_names.json)
                                         # และในตาราง course ของ curriculum.db แล้วเขียน runs/name_consensus_report.json
ไม่โหลด DB ใหม่ (UPDATE เฉพาะ name_th) จึงไม่กระทบ plan_item/plan_slot/ตารางวิชาเลือก
"""
import json
import shutil
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "ocr_system"))
from name_consensus import consensus  # noqa: E402

APPLY = "--apply" in sys.argv
runs = {}
for cur in sorted((ROOT / "runs").rglob("lab8b_output/curriculum.json")):
    runs[cur.parent.parent.relative_to(ROOT / "runs").as_posix()] = cur
obs = []
for run, cur in runs.items():
    for c in json.loads(cur.read_text(encoding="utf-8"))["courses"]:
        obs.append((run, c["code"], c["name_th"]))

res = consensus(obs)
print(f"{len(runs)} run, {len(obs)} การอ่านชื่อ, แก้ได้ {len(res['changes'])} จุด, ตัดสินไม่ได้ {len(res['unresolved'])} รหัส")
for ch in res["changes"]:
    print(f"  {ch['run']:20s} {ch['code']}  {ch['old']!r} -> {ch['new']!r}  [{ch['reason']}] เสียง={ch['votes']}")
for u in res["unresolved"]:
    print(f"  ตัดสินไม่ได้ {u['code']}: {u['reason']} {u['candidates']}")

if APPLY and res["changes"]:
    per_run = defaultdict(dict)
    for ch in res["changes"]:
        per_run[ch["run"]][ch["code"]] = ch["new"]
    for run, fixes in per_run.items():
        cur = runs[run]
        shutil.copy(cur, cur.with_suffix(".before_names.json"))
        data = json.loads(cur.read_text(encoding="utf-8"))
        for c in data["courses"]:
            if c["code"] in fixes:
                c["name_th"] = fixes[c["code"]]
        cur.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        con = sqlite3.connect(cur.parent / "curriculum.db")
        for code, name in fixes.items():
            con.execute("UPDATE course SET name_th = ? WHERE code = ?", (name, code))
        con.commit()
        con.close()
    (ROOT / "runs" / "name_consensus_report.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"เขียนแล้ว {len(per_run)} run + runs/name_consensus_report.json")
