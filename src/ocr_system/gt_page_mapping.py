import csv
from pathlib import Path

from collections import defaultdict
from typing import Any

from .evaluate_curriculum import _normalize_name, _normalize_credits, _is_valid_code


def group_by_code(courses: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = defaultdict(list)
    for course in courses:
        code = course["code"]
        grouped[code].append(course)
    return grouped

def classify_pages(
    gt_courses: list[dict],
    grouped: dict[str, list[dict]],
    pages_text: dict[int, str],
    program: str,
    plan: str,
) -> list[dict]:
    rows = []
    for gt in gt_courses:
        code = gt["code"]
        if not _is_valid_code(code):
            continue

        occurrences = grouped.get(code, [])
        gt_name_en = _normalize_name(gt.get("name_en"))
        gt_name_th = _normalize_name(gt.get("name_th"))
        gt_credits = _normalize_credits(gt.get("credits"))

        primary_pages = set()
        other_pages = set()

        for occ in occurrences:
            name_en_match = gt_name_en and _normalize_name(occ.get("name_en")) == gt_name_en
            name_th_match = gt_name_th and _normalize_name(occ.get("name_th")) == gt_name_th
            credits_match = gt_credits and _normalize_credits(occ.get("credits")) == gt_credits
            if name_en_match or name_th_match or credits_match:
                primary_pages.add(occ["page"])
            else:
                other_pages.add(occ["page"])

        other_pages -= primary_pages
        status = "found" if occurrences else "not_found"
        note = ""

        if not occurrences and gt_name_en:
            # fallback: code never appears anywhere -- try matching by name instead
            for page_no, text in pages_text.items():
                if gt_name_en in _normalize_name(text):
                    other_pages.add(page_no)
                    status = "found_by_name_only"
                    note = "ไม่พบรหัสวิชาใน OCR เลย พบเฉพาะชื่อวิชา (ไม่ยืนยันด้วยรหัส)"

        rows.append({
            "program": program,
            "plan": plan,
            "code": code,
            "name_th": gt.get("name_th"),
            "name_en": gt.get("name_en"),
            "credits": gt.get("credits"),
            "year": gt.get("year"),
            "semester": gt.get("semester"),
            "category": gt.get("category"),
            "type": gt.get("type"),
            "prerequisite": gt.get("prerequisite"),
            "flexible_year_semester": gt.get("flexible_year_semester"),
            "primary_pages": ";".join(str(p) for p in sorted(primary_pages)),
            "other_pages": ";".join(str(p) for p in sorted(other_pages)),
            "occurrences": len(occurrences),
            "status": status,
            "note": note,
        })

    return rows

def write_csv(rows: list[dict], output_path: str) -> None:
    fields = ["program", "plan", "code", "name_th", "name_en", "credits", "year", "semester", "category", "type", "prerequisite", "flexible_year_semester", "primary_pages", "other_pages", "occurrences", "status", "note"]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)