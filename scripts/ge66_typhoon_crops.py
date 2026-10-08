"""Retry GE66 PDF page 18 in image-only chunks using the existing local model."""
import argparse
import ast
import base64
import hashlib
import importlib.util
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

import ge66_ocr_audit as audit

cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument('--root', type=Path, required=True)
cli.add_argument('--output', type=Path, required=True)
args = cli.parse_args()
ROOT = args.root
OUT = args.output
OUT.mkdir(parents=True, exist_ok=True)
PDF = ROOT / 'data/input/GE66_Th_Ed240501.pdf'
MODULE = ROOT / 'Lab7B_Lab8B_ocr_system/src/ocr_system'
MODEL = 'scb10x/typhoon-ocr1.5-3b:latest'
os.environ.setdefault('OMP_THREAD_LIMIT', '1')
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Read a constant, avoiding importing or modifying the existing runtime.
tree = ast.parse((MODULE / 'lab7b_curriculum.py').read_text(encoding='utf-8'))
prompt = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'TYPHOON_PROMPT' for t in n.targets))
spec = importlib.util.spec_from_file_location('eec', MODULE / 'extract_elective_catalog.py')
eec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eec)
import sys
sys.path.insert(0, str(MODULE))

with pymupdf.open(PDF) as doc:
    doc[17].get_pixmap(dpi=300, alpha=False).save(OUT / 'page.png')

with Image.open(OUT / 'page.png') as image:
    w, h = image.size
    left, top = int(w * .115), int(h * .085)
    code_image = image.crop((left, top, int(w * .235), int(h * .91)))
    data = audit.ocr(code_image, 'eng', 6, whitelist='0123456789*', data=True)
    audit.write_json(OUT / 'code-words.json', data)
    anchors = sorted(top + data['top'][i] for i, t in enumerate(data['text'])
                     if audit.CODE.fullmatch(t.strip('* ')))
    if len(anchors) < 6:
        raise RuntimeError('Not enough image-derived anchors to segment this page safely')
    for i, start in enumerate(range(0, len(anchors), 6), 1):
        stop = min(start + 6, len(anchors))
        y0 = max(top, anchors[start] - int(h * .004))
        y1 = (anchors[stop] - int(h * .004) if stop < len(anchors)
              else min(int(h * .91), anchors[-1] + int(h * .04)))
        crop = image.crop((int(w * .115), y0, int(w * .91), y1))
        crop.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
        crop.save(OUT / f'chunk-{i:02d}.png')

models = json.load(urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=15))['models']
digest = next((m['digest'] for m in models if m['name'] == MODEL), None)
available = digest is not None
prior = json.loads((OUT / 'ocr.json').read_text(encoding='utf-8')) if (OUT / 'ocr.json').exists() else {}
if prior and prior.get('provenance', {}).get('pdf_sha256') != hashlib.sha256(PDF.read_bytes()).hexdigest():
    raise RuntimeError('Saved results belong to a different PDF')
digest = digest or prior.get('model_digest')
chunks = []
failures = []
for image_path in sorted(OUT.glob('chunk-*.png')):
    response_path = image_path.with_suffix('.response.json')
    if response_path.exists():
        body = json.loads(response_path.read_text(encoding='utf-8'))
        previous = next((p for p in prior.get('pages', []) if p['chunk'] == image_path.name), None)
        if not previous or previous['input_sha256'] != hashlib.sha256(image_path.read_bytes()).hexdigest():
            raise RuntimeError('Cached image response cannot be verified; use a new output directory')
    elif not available:
        failures.append({'chunk': image_path.name, 'error': 'Model unavailable in local Ollama tags'})
        continue
    else:
        payload = {'model': MODEL, 'stream': False,
                   'messages': [{'role': 'user', 'content': prompt,
                                 'images': [base64.b64encode(image_path.read_bytes()).decode('ascii')]}],
                   'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 4096}}
        started = time.monotonic()
        print('Starting', image_path.name, flush=True)
        request = urllib.request.Request('http://127.0.0.1:11434/api/chat',
                    data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=360) as response:
                body = json.load(response)
        except (OSError, ValueError) as exc:
            detail = exc.read().decode('utf-8', errors='replace') if isinstance(exc, urllib.error.HTTPError) else str(exc)
            failure = {'chunk': image_path.name, 'error': type(exc).__name__, 'detail': detail}
            failures.append(failure)
            audit.write_json(image_path.with_suffix('.error.json'), failure)
            print('Failed', image_path.name, type(exc).__name__, flush=True)
            available = False
            continue
        body['audit_elapsed_seconds'] = time.monotonic() - started
        audit.write_json(response_path, body)
    text = body['message']['content']
    image_path.with_suffix('.md').write_text(text, encoding='utf-8')
    truncated = body.get('done_reason') == 'length' or body.get('eval_count', 0) >= 4088
    chunks.append({'page': 18, 'text': text, 'chunk': image_path.name,
                   'input_sha256': hashlib.sha256(image_path.read_bytes()).hexdigest(),
                   'possibly_truncated': truncated, 'elapsed_seconds': body.get('audit_elapsed_seconds')})
    audit.write_json(OUT / 'ocr.json', {'engine': MODEL, 'pages': chunks, 'model_digest': digest,
                     'provenance': {'pdf_sha256': hashlib.sha256(PDF.read_bytes()).hexdigest(),
                                    'dpi': 300, 'max_image_dim': 1536,
                                    'text_layer_used_as_input': False, 'reference_used_as_input': False}})
    print('Finished', image_path.name, 'chars', len(text), 'tokens', body.get('eval_count'),
          'truncated', truncated, 'seconds', body.get('audit_elapsed_seconds'), flush=True)

audit.write_json(OUT / 'ocr.json', {'engine': MODEL, 'pages': chunks, 'model_digest': digest,
                 'state': 'partial' if failures else 'complete', 'failures': failures,
                 'provenance': {'pdf_sha256': hashlib.sha256(PDF.read_bytes()).hexdigest(),
                                'dpi': 300, 'max_image_dim': 1536,
                                'text_layer_used_as_input': False, 'reference_used_as_input': False}})

reference = [r for r in audit.flat_catalog(json.loads((ROOT /
              'Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json').read_text(encoding='utf-8')))
             if r['page'] == 18]
records = eec.parse_ge_ocr(chunks)
audit.write_json(OUT / 'records.json', records)
audit.write_json(OUT / 'evaluation.json', audit.metrics(reference, records, chunks))
print('Page 18 evaluation', len(records), 'parsed /', len(reference), 'expected', flush=True)
