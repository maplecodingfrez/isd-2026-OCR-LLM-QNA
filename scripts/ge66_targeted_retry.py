"""Retry conflicting GE66 image rows, retaining raw evidence and per-field votes."""
import argparse
import ast
import base64
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request

import pymupdf
import pytesseract
from PIL import Image, ImageOps

import ge66_ocr_audit as audit
from ge66_crop_quality import safe_row_crop
from ge66_english_evidence import english_title_image


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, required=True)
    cli.add_argument('--archive', type=Path, required=True)
    cli.add_argument('--page18', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--request-model', required=True)
    args = cli.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    pdf = args.root / 'data/input/GE66_Th_Ed240501.pdf'
    pdf_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    module = args.root / 'Lab7B_Lab8B_ocr_system/src/ocr_system'
    sys.path.insert(0, str(module))
    spec = importlib.util.spec_from_file_location('eec', module / 'extract_elective_catalog.py')
    eec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eec)
    tree = ast.parse((module / 'lab7b_curriculum.py').read_text(encoding='utf-8'))
    prompt = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'TYPHOON_PROMPT' for t in n.targets))
    os.environ.setdefault('OMP_THREAD_LIMIT', '1')
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    observations = defaultdict(list)
    for engine, filename in [('tesseract', 'ge66-tesseract-ocr.json'), ('typhoon', 'ge66-typhoon-ocr.json')]:
        payload = json.loads((args.archive / filename).read_text(encoding='utf-8'))
        if payload['provenance']['pdf_sha256'] != pdf_hash:
            raise RuntimeError('Archived PDF mismatch')
        pages = payload['pages']
        if engine == 'typhoon':
            newer = json.loads(args.page18.read_text(encoding='utf-8'))
            if newer.get('state') != 'complete' or newer['provenance']['pdf_sha256'] != pdf_hash:
                raise RuntimeError('Page 18 retry must be complete and use this PDF')
            pages = [p for p in pages if p['page'] != 18] + newer['pages']
        for row in eec.parse_ge_ocr(pages):
            observations[row['code']].append({**audit.canonical(row), 'engine': engine,
                                              'variant': 'original_plus_page18' if engine == 'typhoon' else 'original'})
    # Plan depends on disagreement/absence, never correct reference names.
    plan = []
    for code, rows in sorted(observations.items()):
        conflicts = [field for field in audit.FIELDS if len({audit.norm(r[field]) for r in rows}) > 1]
        if len(rows) < 2 or conflicts:
            chosen_page = next((r['page'] for r in rows if r['engine'] == 'typhoon'), rows[0]['page'])
            plan.append({'code': code, 'page': chosen_page, 'conflicts': conflicts, 'single_engine': len(rows) < 2})
    audit.write_json(out / 'plan.json', {'pdf_sha256': pdf_hash, 'targets': plan,
                                      'reference_used_for_target_selection': False})
    print('Target rows', len(plan), 'pages', len({r['page'] for r in plan}), flush=True)
    failures = []
    digest = args.request_model.split(':', 1)[-1]
    with pymupdf.open(pdf) as doc:
        for page_number in sorted({r['page'] for r in plan}):
            page_dir = out / f'page-{page_number:03d}'
            page_dir.mkdir(exist_ok=True)
            path = page_dir / 'page.png'
            doc[page_number - 1].get_pixmap(dpi=300, alpha=False).save(path)
            targets = [r for r in plan if r['page'] == page_number]
            with Image.open(path) as image:
                w, h = image.size
                top, left = int(h * .085), int(w * .115)
                code_image = image.crop((left, top, int(w * .235), int(h * .91)))
                code_data = audit.ocr(code_image, 'eng', 6, whitelist='0123456789*', data=True)
                audit.write_json(page_dir / 'code-words.json', code_data)
                anchors = []
                for i, text in enumerate(code_data['text']):
                    match = re.fullmatch(r'(\*{0,2})(9064\d{4})', text.strip())
                    if match:
                        anchors.append({'code': match[2], 'top': top + code_data['top'][i],
                                        'height': code_data['height'][i], 'confidence': float(code_data['conf'][i])})
                anchors.sort(key=lambda a: a['top'])
                for target in targets:
                    indices = [i for i, a in enumerate(anchors) if a['code'] == target['code']]
                    if not indices:
                        failures.append({**target, 'reason': 'no_exact_image_code_anchor'})
                        continue
                    i = indices[0]
                    anchor = anchors[i]
                    # Include Thai upper marks; stop before next row's upper marks.
                    padding = max(12, int(anchor['height'] * .8))
                    y0 = max(top, anchor['top'] - padding)
                    y1 = (anchors[i + 1]['top'] - max(12, int(anchors[i + 1]['height'] * .8))
                          if i + 1 < len(anchors) else min(int(h * .91), anchor['top'] + int(h * .055)))
                    row_dir = page_dir / target['code']
                    row_dir.mkdir(exist_ok=True)
                    row_image, crop_quality = safe_row_crop(image, (left, y0, int(w * .91), y1))
                    previous_input = row_dir / 'input.json'
                    if previous_input.exists() and json.loads(previous_input.read_text(
                            encoding='utf-8')).get('crop_quality') != crop_quality:
                        raise RuntimeError('Crop policy changed; use a new output directory to preserve existing OCR evidence')
                    crop = ImageOps.expand(row_image, border=20, fill='white')
                    crop.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
                    crop.save(row_dir / 'row.png')
                    image_hash = hashlib.sha256((row_dir / 'row.png').read_bytes()).hexdigest()
                    audit.write_json(row_dir / 'input.json', {'pdf_sha256': pdf_hash, 'page': page_number,
                        'anchor': anchor, 'box': [left, y0, int(w * .91), y1], 'image_sha256': image_hash,
                        'text_layer_used_as_input': False, 'reference_used_as_input': False, 'crop_quality': crop_quality})
                    tess_path = row_dir / 'tesseract.txt'
                    if not tess_path.exists():
                        tess_path.write_text(audit.ocr(crop, 'tha+eng', 6), encoding='utf-8')
                    tess_rows = eec.parse_ge_ocr([{'page': page_number, 'text': tess_path.read_text(encoding='utf-8')}])
                    for row in tess_rows:
                        if row['code'] == target['code']:
                            observations[row['code']].append({**audit.canonical(row), 'engine': 'tesseract', 'variant': 'row_crop', 'crop_quality': crop_quality})
                    english_image, english_meta = english_title_image(crop)
                    previous_english = row_dir / 'english-region.json'
                    if previous_english.exists() and json.loads(previous_english.read_text(
                            encoding='utf-8')) != english_meta:
                        raise RuntimeError('English region changed; use a new output directory to preserve OCR evidence')
                    audit.write_json(row_dir / 'english-region.json', english_meta)
                    if english_image is not None:
                        english_image.save(row_dir / 'english-line.png')
                        english_text = audit.ocr(english_image, 'eng', 6).strip()
                        (row_dir / 'english-tesseract.txt').write_text(english_text, encoding='utf-8')
                        if english_text:
                            observations[target['code']].append({'code': target['code'], 'page': page_number,
                                'engine': 'tesseract', 'variant': 'english_line', 'name_en': english_text,
                                'crop_quality': crop_quality})
                    response_path = row_dir / 'typhoon.response.json'
                    if response_path.exists():
                        body = json.loads(response_path.read_text(encoding='utf-8'))
                        if body.get('audit_image_sha256') != image_hash or body.get('audit_model_digest') != digest:
                            raise RuntimeError('Cached row response provenance mismatch')
                    else:
                        payload = {'model': args.request_model, 'stream': False,
                                   'messages': [{'role': 'user', 'content': prompt,
                                      'images': [base64.b64encode((row_dir / 'row.png').read_bytes()).decode('ascii')]}],
                                   'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 2048}}
                        started = time.monotonic()
                        request = urllib.request.Request('http://127.0.0.1:11434/api/chat',
                                  data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
                        try:
                            with urllib.request.urlopen(request, timeout=360) as response:
                                body = json.load(response)
                        except (OSError, ValueError) as exc:
                            failures.append({**target, 'reason': type(exc).__name__})
                            audit.write_json(out / 'failures.json', failures)
                            print('Failed', target['code'], type(exc).__name__, flush=True)
                            continue
                        body.update(audit_image_sha256=image_hash, audit_model_digest=digest,
                                    audit_elapsed_seconds=time.monotonic() - started)
                        audit.write_json(response_path, body)
                    text = body.get('message', {}).get('content', '')
                    (row_dir / 'typhoon.md').write_text(text, encoding='utf-8')
                    if body.get('done_reason') == 'length' or body.get('eval_count', 0) >= 2040:
                        failures.append({**target, 'reason': 'possibly_truncated'})
                    else:
                        fresh_rows = eec.parse_ge_ocr([{'page': page_number, 'text': text}])
                        valid = [r for r in fresh_rows if r['code'] == target['code']]
                        if len(valid) != 1:
                            failures.append({**target, 'reason': 'incomplete_or_wrong_code', 'parsed_codes': [r['code'] for r in fresh_rows]})
                        else:
                            observations[target['code']].append({**audit.canonical(valid[0]), 'engine': 'typhoon', 'variant': 'row_crop', 'crop_quality': crop_quality})
                    audit.write_json(out / 'observations.json', dict(observations))
                    print('Retried', target['code'], 'page', page_number, 'seconds', round(body.get('audit_elapsed_seconds', 0), 1), flush=True)
    # Pick only fields supported by both engine families. Never consult reference to vote.
    candidate, review = [], []
    for code, rows in sorted(observations.items()):
        proposed = {'code': code, 'page': rows[0]['page']}
        unresolved = []
        for field in audit.FIELDS:
            by_value = defaultdict(list)
            for row in rows:
                if field not in row or row.get('crop_quality', {}).get('clipped', False):
                    continue
                by_value[audit.norm(row[field])].append(row)
            eligible = [(key, support) for key, support in by_value.items()
                        if {r['engine'] for r in support} == {'tesseract', 'typhoon'}]
            if len(eligible) != 1:
                unresolved.append(field)
            else:
                proposed[field] = eligible[0][1][0][field]
        if unresolved:
            review.append({'code': code, 'unresolved_fields': unresolved, 'observations': rows})
        else:
            candidate.append(proposed)
    audit.write_json(out / 'candidate.json', {'source': 'image OCR engine agreement; unapproved', 'records': candidate})
    audit.write_json(out / 'review-queue.json', review)
    audit.write_json(out / 'failures.json', failures)
    reference = audit.flat_catalog(json.loads((args.root / 'Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json').read_text(encoding='utf-8')))
    evaluation = audit.metrics(reference, candidate, [{'text': ' '.join(observations)}])
    audit.write_json(out / 'evaluation.json', evaluation)
    # Diagnose remaining errors only after OCR/voting, never use these to fill fields.
    print('Candidate', len(candidate), 'all-fields exact', evaluation['all_fields_exact'],
          'unresolved', len(review), 'retry failures', len(failures), flush=True)


if __name__ == '__main__':
    main()
