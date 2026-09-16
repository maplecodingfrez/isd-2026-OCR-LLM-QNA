# python scripts/lab5_page_mapping.py "ชื่อโปรแกรม" (DSBA_coop, DSBA_no_coop, AIT, IT_coop, IT_no_coop, BIT_coop, BIT_no_coop)

import csv
import json

from ocr_system.curriculum_extraction import extract_curriculum_from_file
from ocr_system.evaluate_curriculum import _is_valid_code, expand_multicode_courses
from ocr_system.gt_page_mapping import group_by_code, classify_pages
import sys

PROGRAMS = {
    "DSBA_coop":    {"ocr": "outputs/dsba/dsba_curriculum_ocr.json", "gt": "data/ground_truth/DSBA_academic_plan_coop.json",    "program": "DSBA", "plan": "coop"},
    "DSBA_no_coop": {"ocr": "outputs/dsba/dsba_curriculum_ocr.json", "gt": "data/ground_truth/DSBA_academic_plan_no_coop.json", "program": "DSBA", "plan": "no_coop"},
    "AIT":          {"ocr": "outputs/ait/ait_curriculum_ocr.json",  "gt": "data/ground_truth/AIT_academic_plan.json",          "program": "AIT",  "plan": "none"},
    "IT_coop":      {"ocr": "outputs/it/it_curriculum_ocr.json",   "gt": "data/ground_truth/IT_academic_plan_coop.json",      "program": "IT",   "plan": "coop"},
    "IT_no_coop":   {"ocr": "outputs/it/it_curriculum_ocr.json",   "gt": "data/ground_truth/IT_academic_plan_no_coop.json",   "program": "IT",   "plan": "no_coop"},
    "BIT_coop":     {"ocr": "outputs/bit/bit_curriculum_ocr.json",  "gt": "data/ground_truth/BIT_academic_plan_coop.json",     "program": "BIT",  "plan": "coop"},
    "BIT_no_coop":  {"ocr": "outputs/bit/bit_curriculum_ocr.json",  "gt": "data/ground_truth/BIT_academic_plan_no_coop.json",  "program": "BIT",  "plan": "no_coop"},
}

program = sys.argv[1] if len(sys.argv) > 1 else "DSBA"
cfg = PROGRAMS[program]

# 1) extract all course occurrences (with page numbers) from the OCR JSON
result = extract_curriculum_from_file(cfg["ocr"], plan=cfg["plan"])
grouped = group_by_code(result["courses"])

# 2) load ground truth
gt = json.load(open(cfg["gt"], encoding="utf-8"))
gt_courses = [c for c in expand_multicode_courses(gt["courses"]) if _is_valid_code(c.get("code"))]

# 3) page-number -> raw OCR text, needed for the name-only fallback
ocr = json.load(open(cfg["ocr"], encoding="utf-8"))
pages = {p["page"]: p["text"] for p in ocr["pages"]}

# 4) classify each GT course's occurrences into primary / other pages
rows = classify_pages(gt_courses, grouped, pages, gt.get("program"), gt.get("plan"))

# 5) summary
print("total:", len(rows))
found = sum(1 for r in rows if r["status"] == "found")
name_only = sum(1 for r in rows if r["status"] == "found_by_name_only")
with_primary = sum(1 for r in rows if r["primary_pages"])
print("found by code:", found, "| found by name only:", name_only, "| with primary page:", with_primary)
print("found but no primary:", [r["code"] for r in rows if r["status"] == "found" and not r["primary_pages"]])
print("not found at all:", [r["code"] for r in rows if r["status"] == "not_found"])

# 6) write results to CSV
from ocr_system.gt_page_mapping import write_csv  # ไปรวมกับ import อื่นด้านบนก็ได้
out_path = f"outputs/{cfg['program'].lower()}/{program.lower()}_course_page_mapping.csv"
write_csv(rows, out_path)
print("saved ->", out_path)
