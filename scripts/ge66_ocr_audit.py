"""GE66 image-only OCR experiment. Reference data is evaluation-only.

Never writes the live catalog/SQLite/Gold. Keep raw output, crops and failures.
Dependencies: PyMuPDF, Pillow, pytesseract; native Tesseract tha+eng.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, ImageOps

CODE = re.compile(r"(?<!\d)9064\d{4}(?!\d)")
CREDIT = re.compile(r"(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*\)")
FIELDS = ("name_th", "name_en", "credits")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def norm(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value)))


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def flat_catalog(payload):
    return [{**c, "credits": c["credits"]} for g in payload["groups"] for c in g["courses"]]


def canonical(row):
    return {"code": row["code"], "name_th": row["name_th"],
            "name_en": row["name_en"], "credits": row.get("credit_text", row["credits"]),
            "page": row["page"]}


def metrics(reference, records, raw_pages):
    # Evaluation happens after recognition; reference never enters OCR/parsing.
    expected = {r["code"]: r for r in reference}
    found = {r["code"]: canonical(r) for r in records}
    raw_codes = set(CODE.findall("\n".join(p.get("raw_text", p["text"]) for p in raw_pages)))
    matched = set(expected) & set(found)
    differences = []
    for code in sorted(matched):
        errors = [key for key in FIELDS if norm(expected[code][key]) != norm(found[code][key])]
        if errors:
            differences.append({"code": code, "page": expected[code]["page"],
                                "fields": errors, "reference": expected[code], "observed": found[code]})
    cer = {}
    for field in ("name_th", "name_en"):
        denominator = sum(len(norm(expected[c][field])) for c in matched)
        cer[field] = (sum(distance(norm(expected[c][field]), norm(found[c][field]))
                         for c in matched) / denominator) if denominator else None
    return {"expected": len(expected), "raw_expected_codes": len(raw_codes & set(expected)),
            "parsed_expected_codes": len(matched), "missing_codes": sorted(set(expected) - set(found)),
            "missing_in_raw": sorted(set(expected) - raw_codes),
            "present_raw_but_not_parsed": sorted((set(expected) & raw_codes) - set(found)),
            "extra_codes": sorted(set(found) - set(expected)),
            "exact_fields": {k: sum(norm(expected[c][k]) == norm(found[c][k]) for c in matched)
                             for k in FIELDS},
            "all_fields_exact": sum(all(norm(expected[c][k]) == norm(found[c][k]) for k in FIELDS)
                                    for c in matched),
            "cer_on_matched": cer, "differences": differences}


def ocr(image, language, psm, *, whitelist=None, data=False):
    config = f"--oem 3 --psm {psm} -c preserve_interword_spaces=1"
    if whitelist:
        config += f" -c tessedit_char_whitelist={whitelist}"
    if data:
        return pytesseract.image_to_data(image, lang=language, config=config,
                                        timeout=90, output_type=pytesseract.Output.DICT)
    return pytesseract.image_to_string(image, lang=language, config=config, timeout=90)


def column_rows(image, page_number, directory):
    """Fixed GE66 column boundaries chosen from page images, not PDF text.

    Code anchors come only from image OCR. A missed/misread anchor stays visible.
    This is a document-specific pilot, not a general table detector.
    """
    width, height = image.size
    left, right = int(width * .115), int(width * .235)
    top, bottom = int(height * .085), int(height * .91)
    code_image = image.crop((left, top, right, bottom))
    code_image.save(directory / "code-column.png")
    data = ocr(code_image, "eng", 6, whitelist="0123456789*", data=True)
    write_json(directory / "code-words.json", data)
    anchors = []
    for i, text in enumerate(data["text"]):
        match = re.fullmatch(r"(\*{0,2})(9064\d{4})", text.strip())
        if match:
            anchors.append({"code": match[2], "stars": match[1],
                            "top": top + data["top"][i], "height": data["height"][i],
                            "confidence": float(data["conf"][i])})
    anchors.sort(key=lambda a: a["top"])
    records, rejects, assembled = [], [], []
    for i, anchor in enumerate(anchors):
        row_top = max(top, anchor["top"] - max(8, int(height * .0025)))
        row_bottom = (anchors[i + 1]["top"] - max(8, int(height * .0025))
                      if i + 1 < len(anchors) else min(bottom, anchor["top"] + int(height * .055)))
        row_dir = directory / f"row-{i + 1:02d}-{anchor['code']}"
        row_dir.mkdir()
        image.crop((left, row_top, int(width * .91), row_bottom)).save(row_dir / "row.png")
        names = ImageOps.expand(image.crop((int(width * .235), row_top,
                                           int(width * .795), row_bottom)), border=20, fill="white")
        credits = ImageOps.expand(image.crop((int(width * .795), row_top,
                                             int(width * .91), row_bottom)), border=20, fill="white")
        names.save(row_dir / "names.png")
        credits.save(row_dir / "credits.png")
        name_text = ocr(names, "tha+eng", 6)
        credit_text = ocr(credits, "eng", 6, whitelist="0123456789()-")
        (row_dir / "names.txt").write_text(name_text, encoding="utf-8")
        (row_dir / "credits.txt").write_text(credit_text, encoding="utf-8")
        lines = [s.strip() for s in name_text.splitlines() if s.strip()]
        th = [s for s in lines if re.search(r"[ก-๙]", s)]
        en = [s for s in lines if re.fullmatch(r"[A-Za-z][A-Za-z0-9 &'(),./:+-]*", s)]
        credit_matches = list(CREDIT.finditer(credit_text))
        observation = {**anchor, "page": page_number, "name_text": name_text,
                       "credit_text_raw": credit_text, "box": [left, row_top, int(width * .91), row_bottom]}
        write_json(row_dir / "observation.json", observation)
        if not th or not en or len(credit_matches) != 1:
            rejects.append({**observation, "reason": "incomplete_or_ambiguous_fields"})
            continue
        values = tuple(map(int, credit_matches[0].groups()))
        if values[0] > 12 or any(x > 99 for x in values[1:]):
            rejects.append({**observation, "reason": "invalid_credit_structure"})
            continue
        normalized_credit = f"{values[0]} ({values[1]}-{values[2]}-{values[3]})"
        row = {"code": anchor["code"], "name_th": " ".join(th), "name_en": " ".join(en),
               "credits": normalized_credit, "page": page_number,
               "code_confidence": anchor["confidence"], "box": observation["box"],
               "graded_su": bool(anchor["stars"])}
        records.append(row)
        assembled.extend([f"{anchor['stars']}{row['code']} {row['name_th']} {normalized_credit}", row["name_en"]])
    write_json(directory / "rejected-rows.json", rejects)
    return records, {"page": page_number, "text": "\n".join(assembled),
                     "raw_text": " ".join(data["text"])}, rejects


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pages", type=int, nargs="+", default=[16, 22, 24, 28, 148])
    parser.add_argument("--dpi", type=int, nargs="+", default=[300, 400])
    parser.add_argument("--reuse", action="store_true", help="Re-score saved images/OCR; do not re-run recognition")
    parser.add_argument("--tesseract", default=r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    pytesseract.pytesseract.tesseract_cmd = args.tesseract
    available = pytesseract.get_languages()
    if not {"tha", "eng"}.issubset(available):
        raise RuntimeError("Tesseract requires installed tha and eng language data")
    pdf = args.root / "data/input/GE66_Th_Ed240501.pdf"
    live_catalog = args.root / "Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json"
    protected = [live_catalog, *args.root.glob("Lab7B_Lab8B_ocr_system/runs/**/curriculum.db"),
                 *args.root.glob("Lab9_evaluation/**/*gold*.json")]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    spec = importlib.util.spec_from_file_location("ge_extractor", args.root /
               "Lab7B_Lab8B_ocr_system/src/ocr_system/extract_elective_catalog.py")
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    # HTML table converter imported by existing extractor resides alongside it.
    import sys
    sys.path.insert(0, str(Path(spec.origin).parent))
    reference = flat_catalog(json.loads(live_catalog.read_text(encoding="utf-8")))
    selected_reference = [r for r in reference if r["page"] in args.pages]
    pdf_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    variants, payloads = {}, {}
    for label, filename in [("old_tesseract", "ge66-tesseract-ocr.json"),
                            ("old_typhoon", "ge66-typhoon-ocr.json")]:
        payload = json.loads((args.archive / filename).read_text(encoding="utf-8"))
        if payload["provenance"]["pdf_sha256"] != pdf_hash:
            raise ValueError("Archived OCR uses a different PDF")
        records = extractor.parse_ge_ocr(payload["pages"])
        original_file = "ge66-ocr-catalog.json" if label == "old_tesseract" else "ge66-typhoon-catalog.json"
        original_records = flat_catalog(json.loads((args.archive / original_file).read_text(encoding="utf-8")))
        write_json(args.output / f"{label}-full-evaluation.json", metrics(reference, original_records, payload["pages"]))
        write_json(args.output / f"{label}-reparsed-full-evaluation.json", metrics(reference, records, payload["pages"]))
        pages = [p for p in payload["pages"] if p["page"] in args.pages]
        selected = [r for r in records if r["page"] in args.pages]
        original_selected = [r for r in original_records if r["page"] in args.pages]
        variants[label] = metrics(selected_reference, original_selected, pages)
        payloads[label] = original_selected
        variants[label + "_reparsed"] = metrics(selected_reference, selected, pages)
        payloads[label + "_reparsed"] = selected
        print(label, variants[label]["parsed_expected_codes"], "of", len(selected_reference), flush=True)
    with pymupdf.open(pdf) as document:
        for dpi in args.dpi:
            whole_pages, split_pages, split_records = [], [], []
            for pno in args.pages:
                started = time.monotonic()
                directory = args.output / f"dpi-{dpi}" / f"page-{pno:03d}"
                directory.mkdir(parents=True, exist_ok=True)
                if args.reuse:
                    text = (directory / "whole-page.txt").read_text(encoding="utf-8")
                    records = json.loads((directory / "rows.json").read_text(encoding="utf-8"))
                    whole_pages.append({"page": pno, "text": text})
                    split_records.extend(records)
                    split_pages.append({"page": pno, "text": "\n".join(
                        f"{r['code']} {r['name_th']} {r['credits']}\n{r['name_en']}" for r in records),
                        "raw_text": " ".join(json.loads((directory / "code-words.json").read_text(
                            encoding="utf-8"))["text"])})
                    continue
                # OCR input is rendered pixels only; no get_text, reference or GT.
                path = directory / "page.png"
                document[pno - 1].get_pixmap(dpi=dpi, alpha=False).save(path)
                with Image.open(path) as image:
                    text = ocr(image, "tha+eng", 6)
                    (directory / "whole-page.txt").write_text(text, encoding="utf-8")
                    whole_pages.append({"page": pno, "text": text})
                    records, split_page, rejected = column_rows(image, pno, directory)
                    split_records.extend(records)
                    split_pages.append(split_page)
                    write_json(directory / "rows.json", records)
                print(f"dpi={dpi} page={pno} rows={len(records)} rejected={len(rejected)} "
                      f"seconds={time.monotonic()-started:.1f}", flush=True)
            for label, pages, records in [(f"whole_{dpi}", whole_pages, extractor.parse_ge_ocr(whole_pages)),
                                          (f"columns_{dpi}", split_pages, split_records)]:
                variants[label] = metrics(selected_reference, records, pages)
                payloads[label] = records
                write_json(args.output / f"{label}-ocr.json", {"engine": label, "pages": pages,
                           "records": records, "provenance": {"pdf_sha256": pdf_hash, "dpi": dpi,
                           "text_layer_used_as_input": False, "reference_used_as_input": False}})
    # Engine disagreement is a review queue, not automatic correction.
    review = []
    observations = {label: {r["code"]: canonical(r) for r in rows} for label, rows in payloads.items()}
    for code in sorted(set().union(*(set(rows) for rows in observations.values()))):
        evidence = {label: rows[code] for label, rows in observations.items() if code in rows}
        conflicts = [key for key in FIELDS if len({norm(r[key]) for r in evidence.values()}) > 1]
        if conflicts or len(evidence) < len(observations):
            review.append({"code": code, "conflicting_fields": conflicts,
                           "missing_variants": sorted(set(observations) - set(evidence)), "observations": evidence})
    write_json(args.output / "review-queue.json", review)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    if before != after:
        raise RuntimeError("Protected data changed")
    report = {"pdf_sha256": pdf_hash, "pages": args.pages, "reference_count": len(reference),
              "sample_count": len(selected_reference), "variants": variants,
              "protected_hashes": before, "protected_unchanged": before == after,
              "versions": {"pymupdf": pymupdf.VersionBind,
                           "tesseract": str(pytesseract.get_tesseract_version()),
                           "pytesseract": pytesseract.__version__},
              "limitations": ["Selected pages are development examples, not held-out evaluation.",
                              "Reference is the current curated text-layer catalog, not independent human GT.",
                              "Fixed image column geometry is GE66-specific; anchors can still be misread.",
                              "Agreement between engines is not proof of correctness."]}
    write_json(args.output / "report.json", report)
    lines = ["# GE66 OCR pilot", "", f"PDF pages: {args.pages}; {len(selected_reference)} reference courses.", "",
             "Reference used only for scoring; OCR inputs are images. No production promotion.", "",
             "| Variant | Raw codes | Parsed codes | Exact Thai | Exact English | Exact credits | All fields exact |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for label, m in variants.items():
        lines.append(f"| {label} | {m['raw_expected_codes']} | {m['parsed_expected_codes']} | "
                     f"{m['exact_fields']['name_th']} | {m['exact_fields']['name_en']} | "
                     f"{m['exact_fields']['credits']} | {m['all_fields_exact']} |")
    lines += ["", "All counts use the same sample denominator. Name CER in JSON covers matched codes only.",
              "Column raw-code recall uses image-derived code-column TSV, including rejected rows.",
              "", f"Review queue: {len(review)} codes. Protected catalog/DB/Gold hashes unchanged.", "",
              *report["limitations"]]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: {"parsed": v["parsed_expected_codes"], "all_exact": v["all_fields_exact"]}
                      for k, v in variants.items()}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
