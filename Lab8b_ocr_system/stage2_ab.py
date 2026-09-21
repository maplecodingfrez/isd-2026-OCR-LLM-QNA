"""ทดลองเฉพาะขั้น 2 (Markdown -> JSON ด้วย qwen3:4b) ซ้ำหลายรอบบน Markdown ชุดเดิม (ไม่ OCR ใหม่)

python stage2_ab.py <intermediate_vlm.md> <รอบ> <ชื่อ>
วัด: รหัสที่อยู่ใน Markdown (ตามเทอม) แต่ JSON ไม่มีในเทอมนั้น ("หายหรือผิดเทอม") — 0 = ดีที่สุด
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
md_path, n, tag = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
os.environ.update({"PYTHONUTF8": "1", "LAB7_CHUNK": "1", "LAB7B_NUM_CTX": "8192", "LAB7B_NUM_PREDICT": "8192",
                   "LAB7B_REQUEST_TIMEOUT": "7200"})
sys.path.insert(0, str(ROOT / "src" / "ocr_system"))
import lab7b_curriculum as m  # noqa: E402
from md_plan_slots import md_codes_by_term  # noqa: E402

md = md_path.read_text(encoding="utf-8")
want = md_codes_by_term(md)
pages = md.split("\n\n---\n\n")
out = ROOT / "experiments" / tag
out.mkdir(parents=True, exist_ok=True)
for i in range(n):
    data = m._text_to_json_chunked(pages)
    (out / f"pred_{i + 1}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    have: dict = {}
    for c in data["courses"]:
        for code in re.findall(r"(?<!\d)\d{8}(?!\d)", str(c.get("code"))):
            have.setdefault((c.get("year"), c.get("semester")), set()).add(code)
    miss = {f"{k[0]}/{k[1]}": sorted(v - have.get(k, set())) for k, v in want.items() if v - have.get(k, set())}
    print(f"[{i + 1}/{n}] {tag}: courses={len(data['courses'])} หาย/ผิดเทอม={miss or 'ไม่มี'}", flush=True)
print("จบ", flush=True)
