"""Evaluation-only scoring after image recognition; never accesses databases."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import re
import pymupdf
import ge66_ocr_audit as audit
from ge66_select_candidate import select
from ge64_occurrence_score import occurrence_metrics, occurrence_gate, verify_completion_hashes
from ge66_script_evidence import catalog_table_delimiters
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'Lab7B_Lab8B_ocr_system/src/ocr_system'))
import extract_elective_catalog as eec
cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument('--output', type=Path, required=True)
cli.add_argument('--pdf', type=Path)
cli.add_argument('--reference', type=Path, help='Existing evaluation-only JSON for development diagnostics')
args = cli.parse_args()
OUT = args.output
marker = json.loads((OUT/'ocr-complete.json').read_text(encoding='utf-8'))
completion_hashes_verified=verify_completion_hashes(OUT,marker)
candidate_path = OUT/'candidate.json'
occurrence_path = OUT/'occurrence-candidate.json'
original_hashes = {name: hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ('candidate.json','observations.json') + (('occurrence-candidate.json',) if occurrence_path.exists() else ())}
records = json.loads(candidate_path.read_text(encoding='utf-8'))['records']
occurrences = json.loads(occurrence_path.read_text(encoding='utf-8'))['records'] if occurrence_path.exists() else []
observations = json.loads((OUT/'observations.json').read_text(encoding='utf-8'))
if args.reference:
    reference = json.loads(args.reference.read_text(encoding='utf-8'))
    out_of_schema, cross_reference_lines = [], []
    plan = {'pages': sorted({r['page'] for r in reference}), 'scope':'Known-page development diagnostics', 'reference_source_sha256':hashlib.sha256(args.reference.read_bytes()).hexdigest()}
else:
    if not args.pdf or not marker.get('completed_before_reference_extraction'):
        raise RuntimeError('Frozen recognition must complete before opening PDF reference')
    plan = json.loads((OUT/'plan.json').read_text(encoding='utf-8'))
    if hashlib.sha256(args.pdf.read_bytes()).hexdigest() != plan['pdf_sha256']:
        raise RuntimeError('PDF changed after frozen recognition')
    paths = [ROOT/'scripts'/name for name in ('ge64_image_trial.py','ge66_ocr_audit.py','ge66_select_candidate.py','ge66_crop_quality.py','ge66_english_evidence.py','ge66_script_evidence.py')]
    paths += [ROOT/'Lab7B_Lab8B_ocr_system/src/ocr_system'/name for name in ('extract_elective_catalog.py','lab7b_curriculum.py')]
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==plan['frozen_source_hashes'][p.name] for p in paths)
    with pymupdf.open(args.pdf) as doc:
        for page in plan['pages']:
            (OUT/f'page-{page:03d}'/'reference-text-evaluation-only.txt').write_text(doc[page-1].get_text('text'),encoding='utf-8')
    reference = []
    out_of_schema = []
    cross_reference_lines = []
    for page in plan['pages']:
        text = (OUT/f'page-{page:03d}'/'reference-text-evaluation-only.txt').read_text(encoding='utf-8')
        starts = list(re.finditer(r'(?m)^[ \t]*(?:\*[ \t]*){0,2}(9064\d{4})(?=[ \t]|\r?$)', text))
        raw_codes = set(re.findall(r'(?<!\d)9064\d{4}(?!\d)', text))
        page_rows = []
        page_exclusions = []
        for i, start in enumerate(starts):
            end = starts[i+1].start() if i+1<len(starts) else len(text)
            block = eec.fix_pua(text[start.start():end])
            # A numbered curriculum group heading ends a course block; it is not a title.
            heading = re.search(r'(?m)^\s*\d+(?:\.\d+){2,}\s+[^\n]+', block)
            if heading:
                block = block[:heading.start()]
            credit = list(audit.CREDIT.finditer(block))
            if not credit:
                excluded = {'code': start[1], 'page': page, 'reason': 'no_credit_structure_in_reference',
                            'block_sha256': hashlib.sha256(block.encode()).hexdigest()}
                page_exclusions.append(excluded)
                out_of_schema.append(excluded)
                continue
            assert len(credit) == 1, (page,start[1],'ambiguous reference credits')
            lines = [s.strip() for s in block.splitlines() if s.strip()]
            first_name = re.sub(r'^(?:\*[ \t]*){0,2}9064\d{4}(?:[ \t]+|$)', '', lines[0])
            th = [first_name] if first_name else []
            en = []
            for line in lines[1:]:
                if audit.CREDIT.fullmatch(line):
                    if en:
                        break  # Trailing credits terminate names before faculty/appendix prose.
                    continue
                if re.search(r'[\u0e00-\u0e7f]',line):
                    if en and (line.startswith('*') or re.match(r'(?:-\s*)?\u0e23\u0e32\u0e22\u0e27\u0e34\u0e0a\u0e32', line)):
                        break  # Catalog title ended; subsequent starred assessment notes are not names.
                    assert not en, (page,start[1],'unexpected reference Thai after English')
                    th.append(line)
                elif re.search(r'[A-Za-z]',line):
                    en.append(line)
                elif re.fullmatch(r'\d{8}(?:\s+\d{8})*',line):
                    cross_reference_lines.append({'page':page,'course_code':start[1],
                                                  'printed_codes':line,
                                                  'reason':'prior_curriculum_cross_reference'})
                else:
                    assert re.fullmatch(r'(?:\d+|-)',line), (page,start[1],'unrecognized reference line',line)
            assert th and en
            values = tuple(map(int,credit[0].groups()))
            page_rows.append({'code':start[1], 'page':page,'name_th':' '.join(th),
                              'name_en':' '.join(en),'credits':f'{values[0]} ({values[1]}-{values[2]}-{values[3]})'})
        assert {r['code'] for r in page_rows} | {r['code'] for r in page_exclusions} == raw_codes
        assert len(page_rows)+len(page_exclusions) == len(starts)  # Repeated printed courses remain occurrences.
        reference.extend(page_rows)
reference_occurrences = list(reference)
unique = {}
reference_conflicts = {}
for row in reference:
    if row['code'] in unique:
        if not all(audit.norm(row[f])==audit.norm(unique[row['code']][f]) for f in audit.FIELDS):
            reference_conflicts.setdefault(row['code'], [unique[row['code']]]).append(row)
    else: unique[row['code']]=row
reference = [r for c,r in unique.items() if c not in reference_conflicts]
audit.write_json(OUT/'reference-evaluation-only.json',reference)
audit.write_json(OUT/'reference-occurrences-evaluation-only.json',reference_occurrences)
variants = {'candidate':audit.metrics(reference,[r for r in records if r['code'] not in reference_conflicts],[{'text':' '.join(observations)}])}
if (OUT/'raw-pages.json').exists():
    raw_pages=json.loads((OUT/'raw-pages.json').read_text(encoding='utf-8'))
    for engine,pages in raw_pages.items():
        variants[engine]=audit.metrics(reference,[r for r in eec.parse_ge_ocr(pages) if r['code'] not in reference_conflicts],pages)
        if engine=='tesseract':
            formatted=[{**p,'text':catalog_table_delimiters(p['text'])} for p in pages]
            variants['tesseract_same_format']=audit.metrics(reference,[r for r in eec.parse_ge_ocr(formatted) if r['code'] not in reference_conflicts],pages)
reference_ge66=audit.flat_catalog(json.loads((ROOT/'Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json').read_text(encoding='utf-8')))
overlap=sum(any(all(audit.norm(r[f])==audit.norm(audit.canonical(old)[f]) for f in audit.FIELDS) for old in reference_ge66) for r in reference)
review=json.loads((OUT/'review-queue.json').read_text(encoding='utf-8'))
failures=json.loads((OUT/'failures.json').read_text(encoding='utf-8')) if (OUT/'failures.json').exists() else []
assert all(any(f in o and r[f]==o[f] for o in observations[r['code']]) for r in records for f in audit.FIELDS)
assert all(any(f in o and r[f]==o[f] and r['page']==o['page'] and (r.get('occurrence_id')==o.get('occurrence_id') or (r.get('occurrence_id')==str(r['page']) and not o.get('occurrence_id'))) for o in observations[r['code']]) for r in occurrences for f in audit.FIELDS)
per_page={}
for page in plan['pages']:
    page_obs={c:[r for r in rows if r['page']==page] for c,rows in observations.items()}
    page_obs={c:rows for c,rows in page_obs.items() if rows}
    page_records=[r for r in occurrences if r['page']==page] if occurrence_path.exists() else select(page_obs)[0]
    per_page[str(page)]=audit.metrics([r for r in reference_occurrences if r['page']==page],page_records,[{'text':' '.join(page_obs)}])
assert all(hashlib.sha256((OUT/n).read_bytes()).hexdigest()==v for n,v in original_hashes.items())
candidate=variants['candidate']
occurrence_score=occurrence_metrics(reference_occurrences,occurrences) if occurrence_path.exists() else None
occurrence_per_page={str(p):occurrence_metrics([r for r in reference_occurrences if r['page']==p],[r for r in occurrences if r['page']==p]) for p in plan['pages']} if occurrence_score is not None else {}
report={'plan':plan,'scope':'development' if args.reference or plan.get('scope')=='known-page development images' else 'frozen_new_page_images','reference_courses':len(reference),'reference_occurrences':len(reference_occurrences),'reference_unique_codes_including_conflicts':len(unique),'reference_conflicts':reference_conflicts,'selected_total':len(records),'selected_excluded_reference_conflicts':[r['code'] for r in records if r['code'] in reference_conflicts],'reference_content_overlap_with_GE66':overlap,'reference':'Official PDF text layer, not independent human ground truth','variants':variants,'per_page':per_page,'occurrences':occurrence_score,'occurrence_per_page':occurrence_per_page,'passed_occurrence_zero_error_gate':occurrence_gate(occurrence_score,failures=failures) if occurrence_score is not None else None,'review_count':len(review),'withheld':[ {k:r[k] for k in ('code','reason','unresolved_fields') if k in r} for r in review if 'reason' in r],'failures':failures,'out_of_schema':out_of_schema,'cross_reference_lines':cross_reference_lines,'candidate_values_traceable_to_raw_ocr':3*len(records),'occurrence_values_traceable_to_raw_ocr':3*len(occurrences),'immutable_ocr_sha256':original_hashes,'completion_hashes_verified':completion_hashes_verified,'passed_zero_error_gate':candidate['all_fields_exact']==len(reference) and not candidate['extra_codes'] and not failures and not reference_conflicts and bool(reference),'database_access':False,'production_promoted':False}
audit.write_json(OUT/'score.json',report)
print(json.dumps({'scope':report['scope'],'expected':len(reference),'selected':len(records),'exact':candidate['all_fields_exact'],'missing':candidate['missing_codes'],'errors':candidate['differences'],'gate':report['passed_zero_error_gate']},ensure_ascii=False),flush=True)
