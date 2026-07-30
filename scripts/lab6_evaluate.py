# Lab 6 — run the dataset from all previous labs (Lab 4 OCR output + Lab 5
# ground truth / page mapping / QA pairs) through one combined evaluation at
# Field Level, Page Level, and Category Level.
#
# python scripts/lab6_evaluate.py

import json
from pathlib import Path

from ocr_system.evaluate_lab6 import _print_summary, run_lab6_evaluation

OCR_JSON = "outputs/dsba_curriculum_ocr.json"
GROUND_TRUTH = "data/ground_truth/DSBA_academic_plan_coop.json"
QA_PAIRS = "outputs/qa_pairs.csv"
OUTPUT_PATH = Path("outputs/lab6_evaluation.json")

result = run_lab6_evaluation(OCR_JSON, GROUND_TRUTH, QA_PAIRS)
_print_summary(result)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_PATH.open("w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\nSaved -> {OUTPUT_PATH}")