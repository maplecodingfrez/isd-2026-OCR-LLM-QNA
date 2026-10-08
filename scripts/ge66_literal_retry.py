"""Read failing fields literally from image; never send reference values to OCR."""
import argparse
import ast
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import urllib.request

import pytesseract
from PIL import Image, ImageOps
import ge66_ocr_audit as audit


def bands(image):
    gray = image.convert('L')
    width, height = gray.size
    pixels = gray.tobytes()
    active = [y for y in range(height) if sum(v < 180 for v in pixels[y * width:(y + 1) * width]) >= 4]
    groups = []
    for y in active:
        if groups and y - groups[-1][-1] <= 5:
            groups[-1].append(y)
        else:
            groups.append([y])
    return [(max(0, g[0] - 8), min(height, g[-1] + 9)) for g in groups if len(g) >= 3]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, required=True)
    cli.add_argument('--selected', type=Path, required=True)
    cli.add_argument('--targeted', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--request-model', required=True)
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    module = args.root / 'Lab7B_Lab8B_ocr_system/src/ocr_system'
    sys.path.insert(0, str(module))
    spec = importlib.util.spec_from_file_location('eec', module / 'extract_elective_catalog.py')
    eec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eec)
    tree = ast.parse((module / 'lab7b_curriculum.py').read_text(encoding='utf-8'))
    base_prompt = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'TYPHOON_PROMPT' for t in n.targets))
    prompt = base_prompt + '''\nTranscribe exactly as printed, character by character.
Do not correct spelling or change capitalization, hyphens, apostrophes or superscripts.
ถอดข้อความตรงตามภาพทุกตัว ห้ามแก้คำสะกด ห้ามเปลี่ยนตัวพิมพ์ใหญ่เล็กและเครื่องหมายวรรคตอน
ให้คงคำสะกดตามภาพ แม้คำในภาพจะสะกดผิดหรือไม่ใช่คำที่ใช้ทั่วไป'''
    # Evaluation determines which fields need another image read, not their values.
    evaluation = json.loads((args.selected / 'evaluation.json').read_text(encoding='utf-8'))
    targets = [{'code': r['code'], 'fields': r['fields']} for r in evaluation['differences']]
    audit.write_json(args.output / 'plan.json', {'targets': targets, 'selection': 'development evaluation discrepancies; no reference values sent to OCR'})
    records = {r['code']: r for r in json.loads((args.selected / 'candidate.json').read_text(encoding='utf-8'))['records']}
    observations = json.loads((args.targeted / 'observations.json').read_text(encoding='utf-8'))
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    failures = []
    for target in targets:
        code = target['code']
        page = records[code]['page']
        image_path = args.targeted / f'page-{page:03d}' / code / 'row.png'
        if not image_path.exists():
            failures.append({'code': code, 'reason': 'no_saved_image'})
            continue
        row_dir = args.output / code
        row_dir.mkdir(exist_ok=True)
        with Image.open(image_path) as image:
            w, h = image.size
            names = image.crop((int(w * .14), 0, int(w * .82), h))
            spans = bands(names)
            audit.write_json(row_dir / 'bands.json', spans)
            if len(spans) >= 2:
                th_crop = ImageOps.expand(names.crop((0, spans[0][0], names.width, spans[0][1])), border=20, fill='white')
                en_crop = ImageOps.expand(names.crop((0, spans[1][0], names.width, spans[-1][1])), border=20, fill='white')
                th_crop.save(row_dir / 'thai.png')
                en_crop.save(row_dir / 'english.png')
                for label, crop, lang, psm in [('thai', th_crop, 'tha', 7),
                                              ('english', en_crop, 'eng', 7 if len(spans) == 2 else 6)]:
                    text = audit.ocr(crop, lang, psm)
                    (row_dir / f'tesseract-{label}.txt').write_text(text, encoding='utf-8')
        image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
        response_path = row_dir / 'response.json'
        if response_path.exists():
            body = json.loads(response_path.read_text(encoding='utf-8'))
            if body.get('image_sha256') != image_hash or body.get('prompt_sha256') != prompt_hash:
                raise RuntimeError('Cached literal OCR provenance mismatch')
        else:
            payload = {'model': args.request_model, 'stream': False,
                       'messages': [{'role': 'user', 'content': prompt,
                          'images': [base64.b64encode(image_path.read_bytes()).decode('ascii')]}],
                       'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 2048}}
            request = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(payload).encode(),
                                            headers={'Content-Type': 'application/json'})
            started = time.monotonic()
            with urllib.request.urlopen(request, timeout=360) as response:
                body = json.load(response)
            body.update(image_sha256=image_hash, prompt_sha256=prompt_hash,
                        model_request=args.request_model, elapsed_seconds=time.monotonic() - started)
            audit.write_json(response_path, body)
        text = body.get('message', {}).get('content', '')
        (row_dir / 'typhoon.md').write_text(text, encoding='utf-8')
        rows = eec.parse_ge_ocr([{'page': page, 'text': text}])
        valid = [r for r in rows if r['code'] == code]
        if len(valid) != 1 or body.get('done_reason') == 'length' or body.get('eval_count', 0) >= 2040:
            failures.append({'code': code, 'reason': 'incomplete_or_truncated'})
            continue
        observed = audit.canonical(valid[0])
        observations[code].append({**observed, 'engine': 'typhoon', 'variant': 'literal_row_crop'})
        # All failed fields use the new literal read, regardless of its score.
        # Other fields preserve the previously selected values.
        for field in target['fields']:
            records[code][field] = observed[field]
        print('Literal retry', code, 'seconds', round(body.get('elapsed_seconds', 0), 1), flush=True)
    candidate = list(records.values())
    audit.write_json(args.output / 'candidate.json', {'source': 'image-only OCR; new literal reads replace targeted fields', 'records': candidate})
    audit.write_json(args.output / 'observations.json', observations)
    audit.write_json(args.output / 'failures.json', failures)
    reference = audit.flat_catalog(json.loads((args.root / 'Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json').read_text(encoding='utf-8')))
    evaluation = audit.metrics(reference, candidate, [{'text': ' '.join(records)}])
    audit.write_json(args.output / 'evaluation.json', evaluation)
    print('Literal candidate', len(candidate), 'all exact', evaluation['all_fields_exact'], 'remaining', len(evaluation['differences']), flush=True)


if __name__ == '__main__':
    main()
