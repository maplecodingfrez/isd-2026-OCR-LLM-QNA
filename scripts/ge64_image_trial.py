"""Frozen image-only GE64 transfer test. No reference-driven retries or promotion."""
import argparse
import ast
import base64
from collections import defaultdict
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

ROOT = Path(__file__).resolve().parents[1]
cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument('--pdf', type=Path, required=True)
cli.add_argument('--output', type=Path, required=True)
cli.add_argument('--pages', type=int, nargs='+', required=True)
cli.add_argument('--codes',nargs='+',help='Development-only targeted occurrence diagnostics')
cli.add_argument('--chunk-rows',type=int,default=0,help='Optional broad comparison chunks; default uses individual rows only')
cli.add_argument('--development', action='store_true', help='Explicitly allow previously used pages; never a fresh score')
cli.add_argument('--model', default='ggml:8ad769cbef404d27260763e014d082877bbd4d4c4361cd47a141a3d0acff5c47')
args = cli.parse_args()
if args.codes and not args.development:
    cli.error('--codes requires --development; fresh samples must recognize every observed anchor')
OUT = args.output
OUT.mkdir(parents=True, exist_ok=True)
import ge66_ocr_audit as audit
from ge64_trial_artifacts import write_trial_artifacts
from ge66_select_candidate import select, select_occurrences, catalog_from_occurrences
from ge66_crop_quality import safe_row_crop, table_row_crop, code_anchor_left, code_anchor_occurrences
from ge66_english_evidence import english_title_image
from ge66_script_evidence import (thai_title_image, raised_english_text, recognize_region, thai_region_text,
                                  thai_tesseract_readings, typhoon_raised_text, mixed_script_tesseract_reading, catalog_table_delimiters, LITERAL_PROMPT, thai_initial_cluster_reading, typhoon_word_text)

MODULE = ROOT / 'Lab7B_Lab8B_ocr_system/src/ocr_system'
sys.path.insert(0, str(MODULE))
spec = importlib.util.spec_from_file_location('eec', MODULE / 'extract_elective_catalog.py')
eec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eec)
PDF = args.pdf
PAGES = args.pages
MODEL = args.model
os.environ.setdefault('OMP_THREAD_LIMIT', '1')
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
tree = ast.parse((MODULE / 'lab7b_curriculum.py').read_text(encoding='utf-8'))
PROMPT = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'TYPHOON_PROMPT' for t in n.targets))
plan = {'pdf_sha256': hashlib.sha256(PDF.read_bytes()).hexdigest(), 'pages': PAGES,
        'source_url': 'https://gened.kmitl.ac.th/wp-content/uploads/2021/08/GE64_KMITL_Thai_program.pdf',
        'model': MODEL, 'dpi': 300, 'thai_native_dpi': 600,
        'literal_prompt_sha256': hashlib.sha256(LITERAL_PROMPT.encode()).hexdigest(),
        'thai_psm_policy': 'native+half; PSM6; PSM7 only for single Thai line',
        'english_alternate_charset':'uppercase Latin+digits+punctuation OCR hypothesis; no string case conversion; same Tesseract family',
        'english_word_policy': 'Typhoon whole and raised-word images; token alignment required; no Tesseract text fills', 'code_filter':args.codes,'chunk_rows': args.chunk_rows, 'row_max_tokens':1024, 'http_timeout_seconds':600, 'max_image_dimension': 1536,
        'crop_geometry': 'full-page baseline; left from image code boxes with height margin; bounded row/chunk y; full English width unless clear title cell', 'scope': 'known-page development images' if args.development else 'frozen untouched page images; content overlap evaluated later', 'previously_used_pages': [14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155], 'whole_catalog_psm': 4, 'format_policy': 'strip only the separator immediately following a valid observed GE code; preserve all title characters', 'prompt_sha256': hashlib.sha256(PROMPT.encode()).hexdigest(),
        'retry_policy': 'every code occurrence receives bounded row OCR; field retries remain image-only',
        'selection_policy': 'engine families; unique agreement for conflicting titles; agreed shorter titles with longer conflicts stay review',
        'reference_used_as_input': False, 'reference_used_for_retry_selection': False,
        'reference_evaluation': 'after OCR completion only; PDF text layer, not independent human GT',
        'production_mutation': False, 'database_access': False,
        'frozen_source_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            Path(__file__), MODULE / 'extract_elective_catalog.py',
            ROOT / 'scripts/ge66_ocr_audit.py', MODULE / 'lab7b_curriculum.py',
            ROOT / 'scripts/ge66_select_candidate.py', ROOT / 'scripts/ge66_crop_quality.py', ROOT / 'scripts/ge66_english_evidence.py', ROOT / 'scripts/ge66_script_evidence.py', ROOT / 'scripts/ge64_trial_artifacts.py']}}
if not args.development and set(PAGES) & set(plan['previously_used_pages']):
    raise ValueError('Choose pages outside the prior recognition and preflight samples')
if (OUT / 'plan.json').exists():
    assert json.loads((OUT / 'plan.json').read_text(encoding='utf-8')) == plan
else:
    audit.write_json(OUT / 'plan.json', plan)
    snapshot=OUT/'frozen-sources';snapshot.mkdir(exist_ok=True)
    for name in plan['frozen_source_hashes']:
        path=MODULE/name if name in ('extract_elective_catalog.py','lab7b_curriculum.py') else ROOT/'scripts'/name
        (snapshot/name).write_bytes(path.read_bytes())

observations = defaultdict(list)
raw_pages = {'tesseract': [], 'typhoon': []}
failures = []

def recognize(path, max_tokens):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    cached = path.with_suffix('.response.json')
    if cached.exists():
        body = json.loads(cached.read_text(encoding='utf-8'))
        assert body['input_sha256'] == digest and body['prompt_sha256'] == plan['prompt_sha256']
        assert body['model_digest'] == MODEL and body['request_options'] == {'temperature': 0, 'num_ctx': 8192, 'num_predict': max_tokens}
    else:
        payload = {'model': MODEL, 'stream': False,
                   'messages': [{'role': 'user', 'content': PROMPT,
                                 'images': [base64.b64encode(path.read_bytes()).decode('ascii')]}],
                   'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': max_tokens}}
        started = time.monotonic()
        request = urllib.request.Request('http://127.0.0.1:11434/api/chat',
                  data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=600) as response:
            body = json.load(response)
        body.update(input_sha256=digest, prompt_sha256=plan['prompt_sha256'],
                    model_digest=MODEL, request_options=payload['options'], elapsed_seconds=time.monotonic()-started)
        audit.write_json(cached, body)
    text = body.get('message', {}).get('content', '')
    path.with_suffix('.md').write_text(text, encoding='utf-8')
    if body.get('done_reason') == 'length' or body.get('eval_count', 0) >= max_tokens-8:
        failures.append({'image': str(path.relative_to(OUT)), 'reason': 'truncated'})
        return ''
    return text

def add(engine, variant, page, text, required_code=None, quality=None):
    parse_text = catalog_table_delimiters(text) if engine == 'tesseract' else text
    rows = eec.parse_ge_ocr([{'page': page, 'text': parse_text}])
    for row in rows:
        if required_code is None or row['code'] == required_code:
            observations[row['code']].append({**audit.canonical(row), 'engine': engine, 'variant': variant, 'crop_quality': quality or {'clipped': False}})
    return rows

with pymupdf.open(PDF) as doc:
    for page in PAGES:
        folder = OUT / f'page-{page:03d}'
        folder.mkdir(exist_ok=True)
        doc[page-1].get_pixmap(dpi=300, alpha=False).save(folder/'page.png')
        with Image.open(folder/'page.png') as image:
            w, h = image.size
            top, left = int(h*.085), int(w*.28)
            tess = audit.ocr(image, 'tha+eng', 4)
            (folder/'whole-tesseract.txt').write_text(tess, encoding='utf-8')
            raw_pages['tesseract'].append({'page': page, 'text': tess})
            add('tesseract', 'catalog_columns', page, tess)
            data = audit.ocr(image.crop((left, top, int(w*.385), int(h*.91))),
                             'eng', 6, whitelist='0123456789*', data=True)
            audit.write_json(folder/'code-words.json', data)
            anchors = []
            for i, text in enumerate(data['text']):
                match = re.fullmatch(r'\*{0,2}(9064\d{4})', text.strip())
                if match:
                    anchors.append({'code': match[1], 'top': top+data['top'][i],
                                    'height': data['height'][i], 'left': left+data['left'][i]})
            full_data = audit.ocr(image,'tha+eng',6,data=True)
            audit.write_json(folder/'whole-page-words.json',full_data)
            for j, word in enumerate(full_data['text']):
                match=re.fullmatch(r'\*{0,2}(9064\d{4})',word.strip())
                if match:
                    anchors.append({'code':match[1],'top':full_data['top'][j],'height':full_data['height'][j], 'left':full_data['left'][j]})
            anchors = code_anchor_occurrences(anchors)
            if anchors:
                left = code_anchor_left(anchors)
            audit.write_json(folder/'anchors.json', anchors)
            print('Page', page, 'image anchors', len(anchors), flush=True)
            for i, start in enumerate(range(0, len(anchors) if args.chunk_rows else 0, max(1,args.chunk_rows)), 1):
                stop = min(start+args.chunk_rows, len(anchors))
                y0 = max(0, anchors[start]['top']-int(h*.004))
                y1 = anchors[stop]['top']-int(h*.004) if stop<len(anchors) else min(h, anchors[-1]['top']+int(h*.055))
                crop, quality = safe_row_crop(image, (left, y0, int(w*.94), y1))
                crop.thumbnail((1536,1536), Image.Resampling.LANCZOS)
                path = folder/f'chunk-{i:02d}.png'
                crop.save(path)
                text = recognize(path, 4096)
                raw_pages['typhoon'].append({'page': page, 'text': text})
                add('typhoon', 'chunk_crop', page, text, quality=quality)
                print('Chunk',page,i,'parsed',len(eec.parse_ge_ocr([{'page':page,'text':text}])),flush=True)
            for i, anchor in enumerate(anchors):
                code = anchor['code']
                if args.codes and code not in args.codes:
                    continue
                # Always establish row-local association, independent of broad
                # engine agreement on an adjacent or repeated course.
                prior_count = len(observations.get(code, []))
                row_folder=folder/f'occurrence-{code}-{anchor["top"]}'
                row_folder.mkdir(exist_ok=True)
                y0 = max(0, anchor['top']-max(12,int(anchor['height']*.8)))
                y1 = anchors[i+1]['top']-max(12,int(anchors[i+1]['height']*.8)) if i+1<len(anchors) else min(h, anchor['top']+int(h*.055))
                row_box = (left,y0,int(w*.94),y1)
                row_image, quality = table_row_crop(
                    image, anchor['top'] + anchor['height']/2, left, int(w*.94),
                    other_anchor_ys=[a['top']+a['height']/2 for j,a in enumerate(anchors) if j != i])
                if row_image is None:
                    row_image, quality = safe_row_crop(image, row_box)
                crop = ImageOps.expand(row_image, border=20,fill='white')
                crop.thumbnail((1536,1536),Image.Resampling.LANCZOS)
                path = row_folder/f'row-{code}-{anchor["top"]}.png'
                crop.save(path)
                text = audit.ocr(crop,'tha+eng',6)
                path.with_suffix('.tesseract.txt').write_text(text,encoding='utf-8')
                add('tesseract','row_crop',page,text,code,quality)
                text = recognize(path,1024)
                raw_pages['typhoon'].append({'page':page,'text':text})
                add('typhoon','row_crop',page,text,code,quality)
                thai_rows = [r for r in observations[code] if 'name_th' in r]
                thai_conflict = len({audit.norm(r['name_th']) for r in thai_rows}) > 1 or len({r['engine'] for r in thai_rows}) < 2
                if thai_conflict:
                    native_path = folder/'page-600.png'
                    if not native_path.exists():
                        doc[page-1].get_pixmap(dpi=600, alpha=False).save(native_path)
                    with Image.open(native_path) as native_image:
                        if quality.get('crop_method') == 'adjacent_horizontal_rules':
                            native_box = [v*2 for v in quality['box']]
                            native_row = native_image.crop(native_box)
                            native_quality = {**quality, 'box': native_box,
                                              'original_box': [v*2 for v in quality['original_box']],
                                              'crop_method': 'adjacent_horizontal_rules_600dpi'}
                        else:
                            native_row, native_quality = safe_row_crop(
                                native_image, [v*2 for v in quality['box']])
                        thai_image, thai_meta = thai_title_image(native_row)
                    thai_meta.update(dpi=600, crop_quality=native_quality)
                    audit.write_json(row_folder/f'thai-{code}-region.json', thai_meta)
                    if thai_image is not None:
                        thai_path = row_folder/f'thai-{code}.png'
                        thai_image.save(thai_path)
                        mixed_text, mixed_meta = mixed_script_tesseract_reading(thai_image, row_folder/f'thai-{code}-mixed')
                        if mixed_text:
                            observations[code].append({'code':code,'page':page,'engine':'tesseract','variant':'thai_isolated_latin','name_th':mixed_text,'crop_quality':native_quality})
                        for reading in thai_tesseract_readings(thai_image, row_folder/f'thai-{code}-native'):
                            if reading['text']:
                                observations[code].append({'code':code,'page':page,'engine':'tesseract','variant':reading['variant'],'name_th':reading['text'],'crop_quality':native_quality})
                        initial_text, initial_meta = thai_initial_cluster_reading(thai_image, row_folder/f'thai-{code}-{anchor["top"]}-initial')
                        if initial_text:
                            observations[code].append({'code':code,'page':page,'engine':'tesseract','variant':'thai_initial_cluster','name_th':initial_text,'crop_quality':native_quality})
                        raw_thai = recognize_region(thai_path, LITERAL_PROMPT, MODEL)
                        thai_text = thai_region_text(raw_thai)
                        if thai_text:
                            observations[code].append({'code':code,'page':page,'engine':'typhoon','variant':'thai_native_literal','name_th':thai_text,'crop_quality':native_quality})
                english_image, english_meta=english_title_image(crop)
                audit.write_json(row_folder/f'english-{code}-region.json',english_meta)
                if english_image is not None:
                    en_path=row_folder/f'english-{code}.png'
                    english_image.save(en_path)
                    en_text=audit.ocr(english_image,'eng',6).strip()
                    en_path.with_suffix('.tesseract.txt').write_text(en_text,encoding='utf-8')
                    if en_text:
                        observations[code].append({'code':code,'page':page,'engine':'tesseract','variant':'english_line','name_en':en_text,'crop_quality':quality})
                    uppercase_text=audit.ocr(english_image,'eng',6,whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789&(),./:+@%!?=-[]#").strip()
                    en_path.with_suffix('.uppercase-charset.txt').write_text(uppercase_text,encoding='utf-8')
                    if uppercase_text:
                        observations[code].append({'code':code,'page':page,'engine':'tesseract','variant':'english_uppercase_charset','name_en':uppercase_text,'crop_quality':quality})
                    raised_text, raised_meta = raised_english_text(english_image)
                    audit.write_json(row_folder/f'english-{code}-raised.json', raised_meta)
                    if raised_text:
                        observations[code].append({'code':code,'page':page,'engine':'tesseract','variant':'english_raised_parts','name_en':raised_text,'crop_quality':quality})
                    if raised_text:
                        independent, independent_meta = typhoon_raised_text(english_image, row_folder/f'english-{code}-independent', MODEL, raised_meta)
                        audit.write_json(row_folder/f'english-{code}-independent.json', independent_meta)
                        if independent:
                            observations[code].append({'code':code,'page':page,'engine':'typhoon','variant':'english_raised_word','name_en':independent,'crop_quality':quality})
                    from ge66_script_evidence import english_region_text
                    clean = english_region_text(recognize_region(en_path, LITERAL_PROMPT, MODEL))
                    if clean:
                        observations[code].append({'code':code,'page':page,'engine':'typhoon','variant':'english_literal_cell','name_en':clean,'crop_quality':quality})
                    if clean and audit.norm(clean) != audit.norm(en_text):
                        word_text, word_meta = typhoon_word_text(english_image,row_folder/f'english-{code}-{anchor["top"]}-words',MODEL)
                        if word_text:
                            observations[code].append({'code':code,'page':page,'engine':'typhoon','variant':'english_literal_word','name_en':word_text,'crop_quality':quality})
                for reading in observations.get(code, [])[prior_count:]:
                    reading['occurrence_id'] = f'{page}:{anchor["top"]}'
                    if sum(f in reading for f in audit.FIELDS)==1 and ('name_th' in reading or 'name_en' in reading):
                        reading['field_scope']='bounded_title'
                print('Retry',code,'image disagreement only',flush=True)
                audit.write_json(OUT/'observations.json',dict(observations))

# Save candidate and mark recognition complete BEFORE opening reference text.
occurrences, review = select_occurrences(observations, require_scoped=True)
records, conflicts = catalog_from_occurrences(occurrences)
review.extend(conflicts)
write_trial_artifacts(OUT,observations=dict(observations),records=records,occurrences=occurrences,review=review,raw_pages=raw_pages,failures=failures)

audit.write_json(OUT/'report.json', {'plan':plan,'review_count':len(review),
    'failure_count':len(failures),'production_promoted':False,'database_access':False,
    'state':'recognition_complete_pending_score'})
print('OCR completed before scoring. Candidate',len(records),'review',len(review),'failures',len(failures),flush=True)
