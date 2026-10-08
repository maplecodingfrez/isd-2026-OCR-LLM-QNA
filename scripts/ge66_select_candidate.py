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
        unresolved = []
        for field in audit.FIELDS:
            field_rows=[r for r in eligible if field in r]
            bounded=[r for r in field_rows if r.get('field_scope')=='bounded_title'] if field in ('name_th','name_en') else []
            if bounded and len({r['engine'] for r in bounded}) < 2:
                unresolved.append(field)
                continue
            values = defaultdict(list)
            for row in bounded or field_rows:
                if field in row:
                    values[audit.norm(row[field])].append(row)
            if not values:
                unresolved.append(field)
                continue
            agreement = [support for support in values.values()
                         if len({r['engine'] for r in support}) >= 2]
            if field in ('name_th', 'name_en') and len(agreement) == 1:
                agreed = audit.norm(agreement[0][0][field])
                if agreed and any(agreed != other and agreed in other for other in values):
                    # Independent agreement on a shorter title cannot establish
                    # completeness when another image read contains more text.
                    unresolved.append(field)
                    continue
            if field in ('name_th', 'name_en') and len(values) > 1 and len(agreement) != 1:
                unresolved.append(field)
                continue
            # Engine families win, not repeated reads. Ties: Tesseract for English/credits,
            # Typhoon for Thai, then the original view over an unsupported crop.
            preferred_engine = 'typhoon' if field == 'name_th' else 'tesseract'
            best = max(values.values(), key=lambda support: (
                len({r['engine'] for r in support}),
                any(r['engine'] == preferred_engine for r in support),
                any('crop' not in r['variant'] for r in support)))
            proposed[field] = best[-1][field]
            evidence[field] = {'support_count': len(best), 'total': sum(field in r for r in eligible),
                'engines': sorted({r['engine'] for r in best}), 'different_values': len(values),
                'discarded_unbounded_observations':len(field_rows)-len(bounded) if bounded else 0}
        if unresolved:
            review.append({'code': code, 'reason': 'unresolved_field_agreement',
                           'unresolved_fields': unresolved, 'observations': rows})
            continue
        records.append(proposed)
        if rejected or any(v['different_values'] > 1 or len(v['engines']) < 2 or v.get('discarded_unbounded_observations',0) for v in evidence.values()):
            review.append({'code': code, 'evidence': evidence, 'observations': rows,
                           'rejected_clipped_observations': len(rejected)})
    return records, review


def select_occurrences(observations, *, require_scoped=False):
    """Vote only within a printed page/row occurrence, retaining its identity.

    Scoped row observations supersede unbounded baseline observations for
    that page. They never borrow field support from another printed position.
    Baselines remain in raw observations for audit, rather than being erased.
    """
    records, reviews = [], []
    for code, rows in sorted(observations.items()):
        by_page = defaultdict(list)
        for row in rows:
            by_page[row['page']].append(row)
        for page, page_rows in sorted(by_page.items()):
            scoped = [r for r in page_rows if r.get('occurrence_id')]
            if require_scoped and not scoped:
                reviews.append({'code':code,'page':page,'reason':'no_bounded_code_occurrence','observations':page_rows})
                continue
            groups = defaultdict(list)
            for row in scoped or page_rows:
                groups[row.get('occurrence_id', str(page))].append(row)
            for identity, group in sorted(groups.items()):
                chosen, review = select({code: group})
                for item in chosen+review:
                    item.update(page=page, occurrence_id=identity)
                records.extend(chosen)
                reviews.extend(review)
    return records, reviews


def catalog_from_occurrences(records):
    """Return only a unique catalog supported by consistent printed titles."""
    grouped = defaultdict(list)
    for row in records:
        grouped[row['code']].append(row)
    catalog, conflicts = [], []
    for code, rows in sorted(grouped.items()):
        signatures = {tuple(audit.norm(r[f]) for f in audit.FIELDS) for r in rows}
        if len(signatures) != 1:
            conflicts.append({'code':code,'reason':'printed_title_conflict','occurrences':rows})
        else:
            catalog.append({k:v for k,v in rows[0].items() if k != 'occurrence_id'})
    return catalog, conflicts


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, required=True)
    cli.add_argument('--observations', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    observations = json.loads(args.observations.read_text(encoding='utf-8'))
    records, review = select(observations)
    audit.write_json(args.output / 'candidate.json', {'policy': 'exclude clipped crops; engine-family support; conflicting Thai/English needs unique cross-engine agreement; agreed shorter titles with longer conflicting reads remain unresolved',
        'source': 'image-only OCR observations; not approved for production', 'records': records})
    audit.write_json(args.output / 'review-queue.json', review)
    reference = audit.flat_catalog(json.loads((args.root / 'Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json').read_text(encoding='utf-8')))
    evaluation = audit.metrics(reference, records, [{'text': ' '.join(observations)}])
    audit.write_json(args.output / 'evaluation.json', evaluation)
    print('Selected', len(records), 'all fields exact', evaluation['all_fields_exact'], 'remaining differences', len(evaluation['differences']))
