# python scripts/build_page_mapping.py

import csv
import json

from ocr_system.curriculum_extraction import extract_curriculum_from_file
from ocr_system.evaluate_curriculum import _is_valid_code
from ocr_system.gt_page_mapping import group_by_code, classify_pages

# 1) extract all course occurrences (with page numbers) from the OCR JSON
result = extract_curriculum_from_file("outputs/dsba_curriculum_ocr.json", plan="coop")
grouped = group_by_code(result["courses"])

# 2) load ground truth
gt = json.load(open("data/ground_truth/DSBA_academic_plan_coop.json", encoding="utf-8"))
gt_courses = [c for c in gt["courses"] if _is_valid_code(c.get("code"))]

# 3) page-number -> raw OCR text, needed for the name-only fallback
ocr = json.load(open("outputs/dsba_curriculum_ocr.json", encoding="utf-8"))
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
write_csv(rows, "outputs/course_page_mapping.csv")
print("saved ->", "outputs/course_page_mapping.csv")

# rows = {r["code"]: r for r in csv.DictReader(open("outputs/course_page_mapping.csv", encoding="utf-8-sig"))}
# for code in ["06026209", "06026212"]:
#     r = rows[code]
#     print(code, "| year:", r.get("year"), "| semester:", r.get("semester"), "| prerequisite:", r.get("prerequisite"))

# rows = {r["code"]: r for r in csv.DictReader(open("outputs/course_page_mapping.csv", encoding="utf-8-sig"))}
# r = rows["06026216"]
# print(r["code"], "| flexible_year_semester:", r.get("flexible_year_semester"), "| year:", r.get("year"))