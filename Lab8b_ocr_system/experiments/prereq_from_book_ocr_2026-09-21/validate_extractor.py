"""ตรวจตัวสกัด prereq_from_book กับเฉลย scoped ทั้ง 7 แผน
รัน (จาก Lab8b_ocr_system):  ../.venv/Scripts/python.exe experiments/prereq_from_book_ocr_2026-09-21/validate_extractor.py [--detail]
known_codes = รหัสวิชาจริงใน pred_vlm.json ของรัน (เหมือนที่ pipeline จะมีตอนโหลดเข้า DB)
"""
import json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
sys.path[:0] = [str(ROOT / "src" / "ocr_system")]
import prereq_from_book as P  # noqa: E402

PLANS = {  # เฉลย : (โฟลเดอร์รัน, ข้อความ OCR ทั้งเล่ม)
    "ait": ("AIT", "ait"), "bit_no_coop": ("BIT/no_coop", "bit"), "bit_coop": ("BIT/coop", "bit"),
    "dsba_no_coop": ("DSBA/no_coop", "dsba"), "dsba_coop": ("DSBA/coop", "dsba"),
    "it_no_coop": ("IT/no_coop", "it"), "it_coop": ("IT/coop", "it"),
}
CODE8 = re.compile(r"(?<![0-9])(\d{8})(?![0-9])")
detail = "--detail" in sys.argv


def norm_gt(p):
    p = (p or "").strip()
    if p in ("", "ไม่มี"):
        return ("none", ())
    cs = tuple(sorted(CODE8.findall(p)))
    return ("or" if "หรือ" in p and len(cs) > 1 else ("and" if len(cs) > 1 else "one"), cs)


def norm_ex(r):
    if r["status"] == "none":
        return ("none", ())
    cs = tuple(sorted(r["requires"]))
    return ("or" if r["op"] == "or" else ("and" if len(cs) > 1 else "one"), cs)


tot = Counter()
for g, (rd, book) in PLANS.items():
    lines = (REPO / "outputs" / book / f"{book}_curriculum_ocr.txt").read_text(encoding="utf-8").replace("\r", "").split("\n")
    pred = json.loads((ROOT / "runs" / rd / "lab7b_output" / "pred_vlm.json").read_text(encoding="utf-8"))
    gt = json.loads((REPO / "Lab9_evaluation" / "ground_truth_scoped" / f"{g}_scoped.json").read_text(encoding="utf-8"))
    known = {c["code"] for c in pred["courses"] if re.fullmatch(r"\d{8}", str(c.get("code")))}
    gtmap = {c["code"]: c for c in gt["courses"] if re.fullmatch(r"\d{8}", c["code"])}
    res = P.extract_prerequisites(lines, sorted(known & set(gtmap)), known_codes=known)
    c = Counter(r["status"] for r in res.values())
    agree = dis = 0
    bad = []
    for code, r in res.items():
        if r["status"] not in ("found", "none"):
            continue
        ok = norm_ex(r) == norm_gt(gtmap[code].get("prerequisite"))
        agree += ok
        if not ok:
            dis += 1
            bad.append((code, gtmap[code].get("prerequisite"), P.to_gt_string(r), r["note"]))
    print(f"{g:13s} รหัสจริง {len(res):2d} | found {c['found']:2d} none {c['none']:2d} not_found {c['not_found']:2d} unreadable {c['unreadable']:2d} | เทียบเฉลย (เฉพาะที่อ่านได้) ตรง {agree}/{agree+dis}")
    for b in bad:
        print("     ต่างจากเฉลย:", b)
    tot.update({"agree": agree, "dis": dis, "found": c["found"], "none": c["none"], "not_found": c["not_found"], "unreadable": c["unreadable"]})
    if detail:
        for code, r in res.items():
            if r["status"] in ("not_found", "unreadable"):
                print("     ไม่ทราบ:", code, r["status"], r["dropped"])
print(dict(tot))
