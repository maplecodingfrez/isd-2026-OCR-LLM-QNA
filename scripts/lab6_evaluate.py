# Lab 6 — run the dataset from all previous labs (Lab 4 OCR output + Lab 5
# ground truth / page mapping / QA pairs) and evaluate it at Field Level,
# Page Level, and Category Level. Each level is saved as its own file:
#   {key}_field_level.json, {key}_page_level.json, {key}_category_level.csv
#
# python scripts/lab6_evaluate.py [DSBA_coop|DSBA_no_coop|AIT|IT_coop|IT_no_coop|BIT_coop|BIT_no_coop]

from pathlib import Path

from ocr_system.evaluate_lab6 import _print_summary, run_lab6_evaluation, write_lab6_outputs

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

key = sys.argv[1] if len(sys.argv) > 1 else "DSBA_coop"
cfg = PROGRAMS[key]

QA_PAIRS = "outputs/qa_pairs.csv"
OUTPUT_DIR = Path(f"outputs/{cfg['program'].lower()}")

result = run_lab6_evaluation(cfg["ocr"], cfg["gt"], QA_PAIRS, plan=cfg["plan"])
_print_summary(result)

saved_paths = write_lab6_outputs(result, OUTPUT_DIR, key)
print()
for level, path in saved_paths.items():
    print(f"Saved {level} -> {path}")