"""
Evaluation for curriculum extraction results against ground truth.

Unlike evaluation.py (which measures CER/WER on plain OCR text), this module
mainly evaluates *structured* extraction quality: given a list of extracted
courses (code, name_th, name_en, credits, ...) and a ground truth course
list, it reports:

  - recall: how many GT courses were found at all (matched by course code)
  - field accuracy: for matched courses, how often name_en / credits agree
    exactly

Whole-document CER/WER doesn't apply directly here, since the ground truth
is a list of course records, not one block of text -- there's no single
"reference text" to diff a "hypothesis text" against. But exact-match alone
is a blunt instrument: a name_en of "RUCTURES AND ALGORITHMS" (truncated,
missing "DATA ST") is *much* closer to the ground truth "DATA STRUCTURES AND
ALGORITHMS" than "NADA" is to "CALCULUS 1", yet both count as a plain 0
under exact-match. So per field (name_en, name_th) we *also* compute CER and
WER per matched course, the same way evaluation.py does for a full document,
just scoped to one field's value instead of a whole page/file. This reuses
`evaluate_text()` from evaluation.py rather than re-implementing CER/WER.
"""

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import mean
from typing import Any

from .evaluation import evaluate_text


@dataclass
class CurriculumEvaluationResult:
    gt_total: int
    matched: int
    missing: int
    recall: float
    name_en_agreement: float
    credits_agreement: float
    name_en_cer: float
    name_en_wer: float
    name_th_cer: float
    name_th_wer: float
    missing_codes: list[str]
    mismatched_name_en: list[dict[str, Any]]
    mismatched_credits: list[dict[str, Any]]


def evaluate_curriculum(extracted: dict[str, Any], ground_truth: dict[str, Any]) -> CurriculumEvaluationResult:
    gt_courses = [c for c in ground_truth.get("courses", []) if _is_valid_code(c.get("code"))]
    extracted_by_code = _merge_duplicate_courses(extracted.get("courses", []))

    matched_courses = []
    missing_codes = []

    for gt_course in gt_courses:
        code = gt_course["code"]
        if code in extracted_by_code:
            matched_courses.append((gt_course, extracted_by_code[code]))
        else:
            missing_codes.append(code)

    name_en_matches = 0
    credits_matches = 0
    mismatched_name_en = []
    mismatched_credits = []
    name_en_cers = []
    name_en_wers = []
    name_th_cers = []
    name_th_wers = []

    for gt_course, extracted_course in matched_courses:
        gt_name_en = _normalize_name(gt_course.get("name_en"))
        got_name_en = _normalize_name(extracted_course.get("name_en"))
        name_en_eval = evaluate_text(gt_name_en, got_name_en, file_name=gt_course["code"])
        name_en_cers.append(name_en_eval.cer)
        name_en_wers.append(name_en_eval.wer)

        if name_en_eval.exact_match:
            name_en_matches += 1
        else:
            mismatched_name_en.append({
                "code": gt_course["code"],
                "expected": gt_course.get("name_en"),
                "got": extracted_course.get("name_en"),
                "cer": name_en_eval.cer,
                "wer": name_en_eval.wer,
            })

        gt_name_th = _normalize_name(gt_course.get("name_th"))
        got_name_th = _normalize_name(extracted_course.get("name_th"))
        name_th_eval = evaluate_text(gt_name_th, got_name_th, file_name=gt_course["code"])
        name_th_cers.append(name_th_eval.cer)
        name_th_wers.append(name_th_eval.wer)

        if _normalize_credits(gt_course.get("credits")) == _normalize_credits(extracted_course.get("credits")):
            credits_matches += 1
        else:
            mismatched_credits.append({
                "code": gt_course["code"],
                "expected": gt_course.get("credits"),
                "got": extracted_course.get("credits"),
            })

    gt_total = len(gt_courses)
    matched = len(matched_courses)

    return CurriculumEvaluationResult(
        gt_total=gt_total,
        matched=matched,
        missing=len(missing_codes),
        recall=round(matched / gt_total, 4) if gt_total else 0.0,
        name_en_agreement=round(name_en_matches / matched, 4) if matched else 0.0,
        credits_agreement=round(credits_matches / matched, 4) if matched else 0.0,
        name_en_cer=round(mean(name_en_cers), 4) if name_en_cers else 0.0,
        name_en_wer=round(mean(name_en_wers), 4) if name_en_wers else 0.0,
        name_th_cer=round(mean(name_th_cers), 4) if name_th_cers else 0.0,
        name_th_wer=round(mean(name_th_wers), 4) if name_th_wers else 0.0,
        missing_codes=missing_codes,
        mismatched_name_en=mismatched_name_en,
        mismatched_credits=mismatched_credits,
    )


def evaluate_curriculum_from_files(
    extracted_path: str | Path,
    ground_truth_path: str | Path,
    output_path: str | Path | None = None,
) -> CurriculumEvaluationResult:
    with Path(extracted_path).open("r", encoding="utf-8") as f:
        extracted = json.load(f)
    with Path(ground_truth_path).open("r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    result = evaluate_curriculum(extracted, ground_truth)

    if output_path:
        with Path(output_path).open("w", encoding="utf-8") as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2)

    return result


def _merge_duplicate_courses(courses: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Merge multiple occurrences of the same course code into one record.

    The same course code can legitimately appear more than once across a
    403-page institution-wide catalog (main curriculum table, elective
    listings, instructor teaching-load pages, index pages, ...). Some of
    those occurrences carry full data (name, credits) and some don't (e.g.
    a bare code in an index). Naively keeping "the last occurrence found"
    can silently overwrite a good record with an empty one. Instead, for
    each field we keep the first non-empty value we encounter across all
    occurrences of that code.

    (Tried a "pick the best-scoring name_en across all occurrences" variant
    to fix a garbled-name issue seen on the AIT catalog -- reverted, it
    regressed the DSBA baseline from 98.7% to ~85-90% name_en agreement.
    See conversation / commit history for why: any word-count-based quality
    heuristic risks preferring a *wrong* but clean-looking name pulled in
    from a neighboring course block over the correct one. Not safe to ship
    without a fundamentally different approach.)
    """
    merged: dict[str, dict[str, Any]] = {}
    fields = ("name_th", "name_en", "credits", "year", "semester", "category", "type", "prerequisite")

    for course in courses:
        code = course.get("code")
        if not _is_valid_code(code):
            continue
        if code not in merged:
            merged[code] = dict(course)
            continue
        existing = merged[code]
        for field in fields:
            if not existing.get(field) and course.get(field):
                existing[field] = course[field]

    return merged


def _is_valid_code(code: Any) -> bool:
    return isinstance(code, str) and code.isdigit()


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", name).strip().upper()


def _normalize_credits(credits: str | None) -> str:
    if not credits:
        return ""
    return re.sub(r"\s+", "", credits)


def _print_summary(result: CurriculumEvaluationResult) -> None:
    print(f"GT courses (valid):     {result.gt_total}")
    print(f"Matched (found):        {result.matched} ({result.recall * 100:.1f}%)")
    print(f"Missing:                {result.missing}")
    print(f"name_en agreement:      {result.name_en_agreement * 100:.1f}% (of matched, exact match)")
    print(f"name_en CER / WER:      {result.name_en_cer * 100:.1f}% / {result.name_en_wer * 100:.1f}% (avg over matched, lower=better)")
    print(f"name_th CER / WER:      {result.name_th_cer * 100:.1f}% / {result.name_th_wer * 100:.1f}% (avg over matched, lower=better)")
    print(f"credits agreement:      {result.credits_agreement * 100:.1f}% (of matched)")
    if result.missing_codes:
        print(f"Missing codes:          {result.missing_codes}")
    if result.mismatched_name_en:
        print(f"\nSample name_en mismatches:")
        for item in result.mismatched_name_en[:5]:
            print(f"  {item['code']}: expected={item['expected']!r} got={item['got']!r} (cer={item['cer']:.2f}, wer={item['wer']:.2f})")
    if result.mismatched_credits:
        print(f"\nSample credits mismatches:")
        for item in result.mismatched_credits[:5]:
            print(f"  {item['code']}: expected={item['expected']!r} got={item['got']!r}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate curriculum extraction against ground truth")
    parser.add_argument("extracted", help="Path to extracted courses JSON (from curriculum_extraction.py)")
    parser.add_argument("ground_truth", help="Path to ground truth JSON (e.g. DSBA_academic_plan_coop.json)")
    parser.add_argument("--output", default="outputs/curriculum_evaluation_result.json", help="Where to save the result JSON")
    args = parser.parse_args()

    result = evaluate_curriculum_from_files(args.extracted, args.ground_truth, args.output)
    _print_summary(result)
    print(f"\nSaved result to {args.output}")
