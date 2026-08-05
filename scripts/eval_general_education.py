# python scripts/eval_general_education.py

import json
from dataclasses import asdict

from ocr_system.evaluate_curriculum import evaluate_curriculum_from_files
from ocr_system.curriculum_extraction import extract_curriculum_from_file

GT = "data/ground_truth/general_education_ground_truth.json"
RUNS = [
    ("outputs/dsba_curriculum_courses.json", "DSBA"),
    ("outputs/ait_curriculum_courses.json", "AIT"),
    ("outputs/it_curriculum_courses.json", "IT"),
]

# 1) run evaluation against general_education GT for all 3 programs
for courses_path, program in RUNS:
    out_path = f"outputs/general_education_{program.lower()}_evaluation.json"
    result = evaluate_curriculum_from_files(courses_path, GT, out_path)
    r = asdict(result)
    print(f"=== {program} ===")
    print(f"recall={r['recall']} name_en_agreement={r['name_en_agreement']} "
          f"credits_agreement={r['credits_agreement']} name_en_cer={r['name_en_cer']} name_en_wer={r['name_en_wer']}")

# 2) dump full IT mismatch list (worst offender)
print("\n--- IT mismatches ---")
it_eval = json.load(open("outputs/general_education_it_evaluation.json", encoding="utf-8"))
for m in it_eval["mismatched_name_en"]:
    print(m["code"], "|", repr(m["expected"]), "->", repr(m["got"]), "| cer:", round(m["cer"], 2))

# 3) find the real PDF page number for the worst-garbled IT courses
print("\n--- page lookup for worst IT mismatches ---")
bad_codes = [m["code"] for m in it_eval["mismatched_name_en"] if m["cer"] > 0.5]
extracted = extract_curriculum_from_file("outputs/it_curriculum_ocr.json", plan="coop")
for c in extracted["courses"]:
    if c["code"] in bad_codes:
        print(c["code"], "| page:", c["page"], "| name_en:", repr(c["name_en"]))