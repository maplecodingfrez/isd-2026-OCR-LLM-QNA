"""Fixed field-voting policy; reference is used only after selection to score."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import ge66_ocr_audit as audit


def select(observations):
    records, review = [], []
    for code, rows in sorted(observations.items()):
        rejected = [r for r in rows if r.get('crop_quality', {}).get('clipped', False)]
        eligible = [r for r in rows if r not in rejected]
        if not eligible:
            review.append({'code': code, 'reason': 'all_observations_clipped', 'observations': rows})
            continue
        proposed = {'code': code, 'page': next((r['page'] for r in reversed(rows) if r['engine'] == 'typhoon'), rows[0]['page'])}
        evidence = {}
        for field in audit.FIELDS:
            values = defaultdict(list)
            for row in eligible:
                values[audit.norm(row[field])].append(row)
            # Most observations win. Ties: Tesseract for English/credits,
            # Typhoon for Thai, then the original view over an unsupported crop.
            preferred_engine = 'typhoon' if field == 'name_th' else 'tesseract'
            best = max(values.values(), key=lambda support: (
                len(support), sum(r['engine'] == preferred_engine for r in support),
                sum('crop' not in r['variant'] for r in support)))
            proposed[field] = best[-1][field]
            evidence[field] = {'support_count': len(best), 'total': len(rows),
                'engines': sorted({r['engine'] for r in best}), 'different_values': len(values)}
        records.append(proposed)
        if rejected or any(v['different_values'] > 1 or len(v['engines']) < 2 for v in evidence.values()):
            review.append({'code': code, 'evidence': evidence, 'observations': rows,
                           'rejected_clipped_observations': len(rejected)})
    return records, review


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, required=True)
    cli.add_argument('--observations', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    observations = json.loads(args.observations.read_text(encoding='utf-8'))
    records, review = select(observations)
    audit.write_json(args.output / 'candidate.json', {'policy': 'exclude clipped crops; frequency; ties prefer Typhoon Thai / Tesseract English+credits; then original view',
        'source': 'image-only OCR observations; not approved for production', 'records': records})
    audit.write_json(args.output / 'review-queue.json', review)
    reference = audit.flat_catalog(json.loads((args.root / 'Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json').read_text(encoding='utf-8')))
    evaluation = audit.metrics(reference, records, [{'text': ' '.join(observations)}])
    audit.write_json(args.output / 'evaluation.json', evaluation)
    print('Selected', len(records), 'all fields exact', evaluation['all_fields_exact'], 'remaining differences', len(evaluation['differences']))
