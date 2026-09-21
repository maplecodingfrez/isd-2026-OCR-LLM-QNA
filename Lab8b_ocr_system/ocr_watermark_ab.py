"""ทดลอง A/B: ตัดตราน้ำก่อน OCR ช่วยให้ Typhoon-OCR อ่านแถวใต้ตราน้ำได้นิ่งขึ้นไหม

python ocr_watermark_ab.py <รูป> <จำนวนรอบต่อแบบ> <รหัสที่ต้องเจอ,คั่นด้วยจุลภาค> [ชื่อทดลอง]
เช่น  python ocr_watermark_ab.py runs/AIT/data_input/AIT_023.jpg 4 90641008,90641004 ait19

รัน OCR (ขั้น 1 ของ pipeline_vlm) ซ้ำ N รอบ แบบ "เดิม" และ "ตัดตราน้ำ" (สลับกันเพื่อกันผลจากอุณหภูมิ/แคช)
บันทึก Markdown ทุกรอบที่ experiments/<ชื่อ>/ แล้วสรุปว่าเจอรหัสที่ต้องการกี่รอบ + ยอด "รวม" ที่อ่านได้
"""
import importlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
img_path, n, want = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3].split(",")
tag = sys.argv[4] if len(sys.argv) > 4 else img_path.stem
os.environ.update({"PYTHONUTF8": "1", "LAB7B_OCR_NUM_CTX": "4096", "LAB7B_OCR_NUM_PREDICT": "1200",
                   "LAB7B_REQUEST_TIMEOUT": "7200"})
sys.path.insert(0, str(ROOT / "src" / "ocr_system"))
out = ROOT / "experiments" / tag
out.mkdir(parents=True, exist_ok=True)


def load(dewm: bool):
    os.environ["LAB7B_DEWATERMARK"] = "1" if dewm else "0"
    import lab7b_curriculum as m
    importlib.reload(m)
    return m


results = {"เดิม": [], "ตัดตราน้ำ": []}
for i in range(n):
    for label, dewm in (("เดิม", False), ("ตัดตราน้ำ", True)):
        m = load(dewm)
        png = m.load_pages(str(img_path))[0]
        if i == 0:
            (out / f"input_{'dewm' if dewm else 'orig'}.png").write_bytes(png)
        md = m.ollama_chat(m.MODEL_OCR, [{"role": "user", "content": m.TYPHOON_PROMPT}], images=[png],
                           temperature=0.1, num_ctx=m.OCR_NUM_CTX, num_predict=m.OCR_NUM_PREDICT)
        (out / f"{'dewm' if dewm else 'orig'}_{i + 1}.md").write_text(md, encoding="utf-8")
        found = [c for c in want if c in md]
        totals = re.findall(r"<td[^>]*>\s*รวม[^<]*</td>\s*<td[^>]*>\s*(\d+)", md)
        results[label].append((found, totals))
        print(f"[{i + 1}/{n}] {label}: เจอ {found} · ยอดรวม {totals}", flush=True)

print("\nสรุป (ต้องเจอ " + ", ".join(want) + ")")
for label, rs in results.items():
    full = sum(1 for f, _ in rs if len(f) == len(want))
    print(f"  {label}: เจอครบ {full}/{n} รอบ · เจอเฉลี่ย {sum(len(f) for f, _ in rs) / n:.2f}/{len(want)} รหัส")
