"""เทียบช่องที่สกัดจาก OCR (md_plan_slots) กับเฉลย plan_slots_REFERENCE.json ต่อเทอม

เฉลยเป็นข้อมูลกรอกมือ ใช้ "เทียบ" เท่านั้น — ตัวสกัดไม่เคยอ่านไฟล์นี้
เทียบต่อเทอม: จำนวนช่องแต่ละชนิด + หน่วยกิตรวมของช่อง
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "ocr_system"))
from md_plan_slots import derive_slots  # noqa: E402


def sig(slots):
    d: dict = {}
    for s in slots:
        k = (s["year"], s["semester"])
        c = d.setdefault(k, Counter())
        c[(s["kind"], s["credits"])] += 1
    return d


def main(verbose: bool = True) -> int:
    ref = json.loads((ROOT / "plan_slots_REFERENCE.json").read_text(encoding="utf-8"))
    bad_total = 0
    for run, plan in ref["apply"].items():
        md = (ROOT / run / "lab7b_output" / "intermediate_vlm.md").read_text(encoding="utf-8")
        got, report = derive_slots(md)
        want = ref["plans"][plan]["slots"]
        g, w = sig(got), sig(want)
        diffs = []
        for k in sorted(set(g) | set(w)):
            if g.get(k, Counter()) != w.get(k, Counter()):
                diffs.append((k, dict(g.get(k, {})), dict(w.get(k, {}))))
        un = [(r["year"], r["semester"], r["unexplained"]) for r in report if r["unexplained"]]
        print(f"{run:22s} เทอมตรงเฉลย {len(set(g)|set(w))-len(diffs)}/{len(set(g)|set(w))}"
              f" · unexplained(OCR ตก) {un}")
        if verbose:
            for k, a, b in diffs:
                print(f"    {k[0]}/{k[1]} OCR={a}  เฉลย={b}")
        bad_total += len(diffs)
    return bad_total


if __name__ == "__main__":
    main()
