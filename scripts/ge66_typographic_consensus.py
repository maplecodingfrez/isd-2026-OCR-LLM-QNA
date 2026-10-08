"""Prefer native per-line English when both OCR engines agree on text content."""
import argparse
import json
from pathlib import Path
import unicodedata

import pytesseract
from PIL import Image, ImageOps
import ge66_ocr_audit as audit


def content_key(text):
    # Equality only; do not rewrite output strings or take values from reference.
    return audit.norm(unicodedata.normalize('NFKC', text).translate(str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"'})))


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, required=True)
    cli.add_argument('--literal', type=Path, required=True)
    cli.add_argument('--targeted', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    records = {r['code']: r for r in json.loads((args.literal / 'candidate.json').read_text(encoding='utf-8'))['records']}
    plan = json.loads((args.literal / 'plan.json').read_text(encoding='utf-8'))['targets']
    decisions = []
    for target in plan:
        if 'name_en' not in target['fields']:
            continue
        code = target['code']
        spans = json.loads((args.literal / code / 'bands.json').read_text(encoding='utf-8'))
        if len(spans) < 2:
            continue
        image_path = args.targeted / f"page-{records[code]['page']:03d}" / code / 'row.png'
        with Image.open(image_path) as image:
            w, h = image.size
            names = image.crop((int(w * .14), 0, int(w * .82), h))
            first_en = ImageOps.expand(names.crop((0, spans[1][0], names.width, spans[1][1])), border=20, fill='white')
            first_en.save(args.output / f'{code}-english.png')
            text = audit.ocr(first_en, 'eng', 7).strip()
        (args.output / f'{code}-english.txt').write_text(text, encoding='utf-8')
        agrees = content_key(text) == content_key(records[code]['name_en'])
        decisions.append({'code': code, 'tesseract': text, 'typhoon': records[code]['name_en'],
                          'content_agreement': agrees, 'selected': 'tesseract' if agrees else 'typhoon'})
        if agrees:
            records[code]['name_en'] = text
    audit.write_json(args.output / 'decisions.json', decisions)
    candidate = list(records.values())
    audit.write_json(args.output / 'candidate.json', {'source': 'image-only OCR with literal retry and per-line English agreement', 'records': candidate})
    reference = audit.flat_catalog(json.loads((args.root / 'Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json').read_text(encoding='utf-8')))
    evaluation = audit.metrics(reference, candidate, [{'text': ' '.join(records)}])
    audit.write_json(args.output / 'evaluation.json', evaluation)
    print('Final candidate', len(candidate), 'strict all-fields exact', evaluation['all_fields_exact'],
          'differences', len(evaluation['differences']), flush=True)
