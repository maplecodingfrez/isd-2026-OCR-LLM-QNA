"""Strict GE66 catalog gate, then isolated Lab8B copies and Q&A comparison."""
import argparse
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import ge66_ocr_audit as audit


def table_snapshots(conn):
    result = {}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        if name in {'elective_group', 'elective_group_course'}:
            continue
        # Table names are trusted schema identifiers, not user input.
        rows = conn.execute('SELECT * FROM "' + name.replace('"', '""') + '"').fetchall()
        result[name] = hashlib.sha256(json.dumps(sorted(map(repr, rows)), ensure_ascii=False).encode()).hexdigest()
    return result


def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if k not in {'id', 'group_id'}}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return audit.norm(value) if isinstance(value, str) else value


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, required=True)
    cli.add_argument('--archive', type=Path, required=True)
    cli.add_argument('--candidate', type=Path, required=True)
    cli.add_argument('--page18', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = args.root.resolve()
    module = root / 'Lab7B_Lab8B_ocr_system/src/ocr_system'
    sys.path.insert(0, str(module))
    import extract_elective_catalog as eec
    import lab8b_curriculum_db as dbmod
    reference = audit.flat_catalog(json.loads((root / 'Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json').read_text(encoding='utf-8')))
    ref = {r['code']: r for r in reference}
    candidate = json.loads(args.candidate.read_text(encoding='utf-8'))['records']
    evaluation = audit.metrics(reference, candidate, [{'text': ' '.join(r['code'] for r in candidate)}])
    if evaluation['all_fields_exact'] != 303 or len(candidate) != 303 or evaluation['extra_codes']:
        raise RuntimeError('Catalog quality gate failed; no trial DBs created')
    # Flags come from actual OCR rows, independently from reference metadata.
    flags = {}
    payloads = [json.loads((args.archive / f).read_text(encoding='utf-8')) for f in
                ['ge66-tesseract-ocr.json', 'ge66-typhoon-ocr.json']]
    payloads.append(json.loads(args.page18.read_text(encoding='utf-8')))
    for payload in payloads:
        for page in sorted(payload['pages'], key=lambda p: p['page']):
            for row in eec.parse_ge_ocr([page]):
                flags.setdefault(row['code'], row['graded_su'])
    missing_flags = [r['code'] for r in candidate if r['code'] not in flags]
    wrong_flags = [r['code'] for r in candidate if flags.get(r['code']) != ref[r['code']]['graded_su']]
    wrong_pages = [r['code'] for r in candidate if r['page'] != ref[r['code']]['page']]
    if missing_flags or wrong_flags or wrong_pages:
        audit.write_json(args.output / 'gate-failures.json', {'missing_flags': missing_flags, 'wrong_flags': wrong_flags, 'wrong_pages': wrong_pages})
        raise RuntimeError('Page/flag quality gate failed; no trial DBs created')
    groups = []
    for group, (thai, english) in eec.GE_GROUP_NAMES.items():
        courses = [{**r, 'graded_su': flags[r['code']]} for r in candidate if int(r['code'][4]) == group]
        groups.append({'group_no': group, 'name_th': thai, 'name_en': english, 'courses': courses})
    catalog = {'program': 'GE', 'source': 'GE66 image-only Tesseract/Typhoon targeted OCR; development candidate',
               'plan_slot': 'หมวดวิชาศึกษาทั่วไป ฉบับปรับปรุง พ.ศ. 2566', 'credits_required': 24, 'groups': groups}
    catalog_path = args.output / 'ge66-image-ocr-catalog.json'
    audit.write_json(catalog_path, catalog)
    # Catalog must round-trip through the same image-only GE parser.
    pages = []
    for r in candidate:
        pages.append({'page': r['page'], 'text': f"{'*' if flags[r['code']] else ''}{r['code']} {r['name_th']} {r['credits']}\n{r['name_en']}"})
    if len(eec.parse_ge_ocr(pages)) != 303:
        raise RuntimeError('Candidate cannot round-trip through the GE OCR parser')
    plans = ['AIT', 'DSBA/coop', 'DSBA/no_coop', 'IT/coop', 'IT/no_coop']
    protected = [root / 'Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json',
                 *root.glob('Lab7B_Lab8B_ocr_system/runs/**/curriculum.db'), *root.glob('Lab9_evaluation/**/*gold*.json')]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    questions = ['หมวดวิชาศึกษาทั่วไปมีวิชาอะไรบ้าง',
                 'วิชาเลือกด้านภาษาและการสื่อสารมีวิชาอะไรให้เลือกบ้าง',
                 'วิชาเลือกหมวดวิชาศึกษาทั่วไปมีวิชาอะไรให้เลือกบ้าง',
                 'วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง']
    comparisons = []
    for plan in plans:
        source = root / 'Lab7B_Lab8B_ocr_system/runs' / plan / 'lab8b_output/curriculum.db'
        destination = args.output / 'db' / plan / 'lab8b_output/curriculum.db'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.resolve() == source.resolve():
            raise RuntimeError('Trial DB must differ from production')
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original, closing(sqlite3.connect(destination)) as trial:
            original.backup(trial)
            untouched = table_snapshots(trial)
            program_id = trial.execute('SELECT program_id FROM program LIMIT 1').fetchone()[0]
        dbmod.cmd_load_electives(SimpleNamespace(input=str(catalog_path), database=str(destination), program_id=program_id))
        with closing(sqlite3.connect(destination)) as trial:
            assert trial.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not trial.execute('PRAGMA foreign_key_check').fetchall()
            assert table_snapshots(trial) == untouched
            count = trial.execute("SELECT COUNT(*) FROM elective_group_course c JOIN elective_group g ON c.group_id=g.id WHERE g.plan_slot=?", (catalog['plan_slot'],)).fetchone()[0]
            assert count == 303
        for question in questions:
            with closing(dbmod.open_db(source, readonly=True)) as original, closing(dbmod.open_db(destination, readonly=True)) as trial:
                a, b = dbmod.ask(original, question, verbose=False), dbmod.ask(trial, question, verbose=False)
            match = (not a.get('error') and not b.get('error') and
                     normalized(a['rows']) == normalized(b['rows']) and normalized(a['answer']) == normalized(b['answer']))
            comparisons.append({'plan': plan, 'question': question, 'same_rows_and_answer': bool(match), 'original': a, 'trial': b})
            print(plan, question, 'MATCH' if match else 'DIFFERENT', flush=True)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    result = {'catalog_gate': evaluation, 'page_and_flag_checks': True,
              'trial_plans': plans, 'comparisons': comparisons, 'protected_unchanged': before == after,
              'protected_hashes': before, 'passed': sum(r['same_rows_and_answer'] for r in comparisons), 'total': len(comparisons)}
    audit.write_json(args.output / 'report.json', result)
    if before != after or result['passed'] != result['total']:
        raise RuntimeError('Trial comparison/protection gate failed; production remains unchanged')
    print('Trial passed', result['passed'], '/', result['total'], 'protected files', len(protected), flush=True)


if __name__ == '__main__':
    main()
