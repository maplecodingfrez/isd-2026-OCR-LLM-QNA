"""
Lab 6 — run the dataset from all previous labs through one combined
evaluation, reported at three levels of granularity: Field Level, Page
Level, Category Level.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .curriculum_extraction import extract_curriculum_from_file
from .evaluate_curriculum import (
    _is_valid_code,
    _merge_duplicate_courses,
    _normalize_credits,
    _normalize_name,
)
from .gt_page_mapping import classify_pages, group_by_code


# ---------------------------------------------------------------------------
# Field level
# ---------------------------------------------------------------------------


@dataclass
class FieldLevelResult:
    gt_total: int
    matched: int
    recall: float
    name_en_agreement: float
    credits_agreement: float


def evaluate_field_level(
    gt_courses: list[dict[str, Any]], extracted_by_code: dict[str, dict[str, Any]]
) -> FieldLevelResult:
    matched = [(gt, extracted_by_code[gt["code"]]) for gt in gt_courses if gt["code"] in extracted_by_code]

    name_en_ok = sum(
        1 for gt, ex in matched if _normalize_name(gt.get("name_en")) == _normalize_name(ex.get("name_en"))
    )
    credits_ok = sum(
        1 for gt, ex in matched if _normalize_credits(gt.get("credits")) == _normalize_credits(ex.get("credits"))
    )

    gt_total = len(gt_courses)
    n_matched = len(matched)
    return FieldLevelResult(
        gt_total=gt_total,
        matched=n_matched,
        recall=round(n_matched / gt_total, 4) if gt_total else 0.0,
        name_en_agreement=round(name_en_ok / n_matched, 4) if n_matched else 0.0,
        credits_agreement=round(credits_ok / n_matched, 4) if n_matched else 0.0,
    )


# ---------------------------------------------------------------------------
# Page level
# ---------------------------------------------------------------------------


@dataclass
class PageLevelResult:
    gt_total: int
    with_primary_page: int
    page_localization_rate: float
    found_by_code: int
    found_by_name_only: int
    not_found: int
    qa_pairs_checked: int
    qa_pairs_citation_ok: int
    qa_pairs_citation_mismatches: list[dict[str, Any]]


_NOTE_CODE_RE = re.compile(r"code (\d{8})")


def evaluate_page_level(mapping_rows: list[dict[str, Any]], qa_pairs_path: Path | None) -> PageLevelResult:
    gt_total = len(mapping_rows)
    with_primary = sum(1 for r in mapping_rows if r["primary_pages"])
    found = sum(1 for r in mapping_rows if r["status"] == "found")
    name_only = sum(1 for r in mapping_rows if r["status"] == "found_by_name_only")
    not_found = sum(1 for r in mapping_rows if r["status"] == "not_found")

    by_code = {r["code"]: r for r in mapping_rows}

    checked = 0
    ok = 0
    mismatches: list[dict[str, Any]] = []

    if qa_pairs_path and qa_pairs_path.exists():
        with qa_pairs_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("type") != "course":
                    continue
                match = _NOTE_CODE_RE.search(row.get("note") or "")
                if not match:
                    continue
                code = match.group(1)
                mapping_row = by_code.get(code)
                if not mapping_row:
                    continue

                known_pages = {p for p in mapping_row["primary_pages"].split(";") if p}
                known_pages |= {p for p in mapping_row["other_pages"].split(";") if p}
                cited = {p.split("(")[0].strip() for p in (row.get("cited_pages") or "").split(";") if p.strip()}

                checked += 1
                if cited and cited <= known_pages:
                    ok += 1
                else:
                    mismatches.append(
                        {
                            "code": code,
                            "question": row.get("question"),
                            "cited_pages": row.get("cited_pages"),
                            "known_pages": sorted(known_pages, key=lambda x: int(x) if x.isdigit() else 0),
                        }
                    )

    return PageLevelResult(
        gt_total=gt_total,
        with_primary_page=with_primary,
        page_localization_rate=round(with_primary / gt_total, 4) if gt_total else 0.0,
        found_by_code=found,
        found_by_name_only=name_only,
        not_found=not_found,
        qa_pairs_checked=checked,
        qa_pairs_citation_ok=ok,
        qa_pairs_citation_mismatches=mismatches,
    )


# ---------------------------------------------------------------------------
# Category level
# ---------------------------------------------------------------------------


def evaluate_category_level(
    gt_courses: list[dict[str, Any]],
    extracted_by_code: dict[str, dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    group_field: str,
) -> dict[str, dict[str, Any]]:
    mapping_by_code = {r["code"]: r for r in mapping_rows}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for gt in gt_courses:
        key = gt.get(group_field) or "(none)"
        groups[key].append(gt)

    result: dict[str, dict[str, Any]] = {}
    for key, courses in groups.items():
        field = evaluate_field_level(courses, extracted_by_code)
        with_primary = sum(1 for c in courses if mapping_by_code.get(c["code"], {}).get("primary_pages"))
        result[key] = {
            "gt_total": field.gt_total,
            "matched": field.matched,
            "recall": field.recall,
            "name_en_agreement": field.name_en_agreement,
            "credits_agreement": field.credits_agreement,
            "page_localization_rate": round(with_primary / field.gt_total, 4) if field.gt_total else 0.0,
        }
    return result


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_lab6_evaluation(
    ocr_json_path: str | Path,
    ground_truth_path: str | Path,
    qa_pairs_path: str | Path | None = None,
    plan: str = "coop",
) -> dict[str, Any]:
    extracted = extract_curriculum_from_file(ocr_json_path, plan=plan)
    extracted_by_code = _merge_duplicate_courses(extracted["courses"])

    with Path(ground_truth_path).open("r", encoding="utf-8") as f:
        gt = json.load(f)
    gt_courses = [c for c in gt.get("courses", []) if _is_valid_code(c.get("code"))]

    with Path(ocr_json_path).open("r", encoding="utf-8") as f:
        ocr_payload = json.load(f)
    pages_text = {p["page"]: p["text"] for p in ocr_payload.get("pages", [])}

    grouped = group_by_code(extracted["courses"])
    mapping_rows = classify_pages(gt_courses, grouped, pages_text, gt.get("program"), gt.get("plan"))

    field_level = evaluate_field_level(gt_courses, extracted_by_code)
    page_level = evaluate_page_level(mapping_rows, Path(qa_pairs_path) if qa_pairs_path else None)
    category_level = evaluate_category_level(gt_courses, extracted_by_code, mapping_rows, "category")

    return {
        "field_level": asdict(field_level),
        "page_level": asdict(page_level),
        "category_level": category_level,
    }


def _print_summary(result: dict[str, Any]) -> None:
    fl = result["field_level"]
    pl = result["page_level"]

    print("=" * 64)
    print("LAB 6 — FIELD LEVEL")
    print("=" * 64)
    print(f"GT courses:          {fl['gt_total']}")
    print(f"Matched (recall):    {fl['matched']} ({fl['recall'] * 100:.1f}%)")
    print(f"name_en agreement:   {fl['name_en_agreement'] * 100:.1f}% (of matched)")
    print(f"credits agreement:   {fl['credits_agreement'] * 100:.1f}% (of matched)")

    print()
    print("=" * 64)
    print("LAB 6 — PAGE LEVEL")
    print("=" * 64)
    print(f"GT courses:                 {pl['gt_total']}")
    print(f"Found by course code:       {pl['found_by_code']}")
    print(f"Found by name only:         {pl['found_by_name_only']}")
    print(f"Not found at all:           {pl['not_found']}")
    print(f"With a primary page:        {pl['with_primary_page']} ({pl['page_localization_rate'] * 100:.1f}%)")
    print(f"QA citations checked:       {pl['qa_pairs_checked']}")
    print(f"QA citations consistent:    {pl['qa_pairs_citation_ok']} / {pl['qa_pairs_checked']}")
    if pl["qa_pairs_citation_mismatches"]:
        print("QA citation mismatches:")
        for m in pl["qa_pairs_citation_mismatches"]:
            print(f"  - {m['code']}: cited={m['cited_pages']} known={m['known_pages']}")

    print()
    print("=" * 64)
    print("LAB 6 — CATEGORY LEVEL (by 'category')")
    print("=" * 64)
    for key, metrics in result["category_level"].items():
        print(
            f"[{key}]  n={metrics['gt_total']}  recall={metrics['recall'] * 100:.1f}%  "
            f"name_en={metrics['name_en_agreement'] * 100:.1f}%  credits={metrics['credits_agreement'] * 100:.1f}%  "
            f"page_localized={metrics['page_localization_rate'] * 100:.1f}%"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lab 6 - combined Field/Page/Category level evaluation")
    parser.add_argument("--ocr-json", default="outputs/dsba_curriculum_ocr.json")
    parser.add_argument("--ground-truth", default="data/ground_truth/DSBA_academic_plan_coop.json")
    parser.add_argument("--qa-pairs", default="outputs/qa_pairs.csv")
    parser.add_argument("--output", default="outputs/lab6_evaluation.json")
    args = parser.parse_args()

    lab6_result = run_lab6_evaluation(args.ocr_json, args.ground_truth, args.qa_pairs)
    _print_summary(lab6_result)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(lab6_result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved -> {output_path}")