# Lab 6 — run the dataset from all previous labs (Lab 4 OCR output + Lab 5
# ground truth / page mapping / QA pairs) through one combined evaluation at
# Field Level, Page Level, and Category Level.
#
# python scripts/lab6_evaluate.py [DSBA_coop|DSBA_no_coop|AIT|IT_coop|IT_no_coop]

import json
from pathlib import Path

from ocr_system.evaluate_lab6 import _print_summary, run_lab6_evaluation

import sys

PROGRAMS = {
    "DSBA_coop":    {"ocr": "outputs/dsba_curriculum_ocr.json", "gt": "data/ground_truth/DSBA_academic_plan_coop.json",    "plan": "coop"},
    "DSBA_no_coop": {"ocr": "outputs/dsba_curriculum_ocr.json", "gt": "data/ground_truth/DSBA_academic_plan_no_coop.json", "plan": "no_coop"},
    "AIT":          {"ocr": "outputs/ait_curriculum_ocr.json",  "gt": "data/ground_truth/AIT_academic_plan.json",          "plan": "none"},
    "IT_coop":      {"ocr": "outputs/it_curriculum_ocr.json",   "gt": "data/ground_truth/IT_academic_plan_coop.json",      "plan": "coop"},
    "IT_no_coop":   {"ocr": "outputs/it_curriculum_ocr.json",   "gt": "data/ground_truth/IT_academic_plan_no_coop.json",   "plan": "no_coop"},
}

key = sys.argv[1] if len(sys.argv) > 1 else "DSBA_coop"
cfg = PROGRAMS[key]

QA_PAIRS = "outputs/qa_pairs.csv"
OUTPUT_PATH = Path(f"outputs/{key.lower()}_lab6_evaluation.json")

result = run_lab6_evaluation(cfg["ocr"], cfg["gt"], QA_PAIRS, plan=cfg["plan"])
_print_summary(result)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_PATH.open("w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\nSaved -> {OUTPUT_PATH}")