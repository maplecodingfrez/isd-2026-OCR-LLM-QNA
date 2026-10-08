"""Evaluation-only page/row multiset scoring; no recognition or reference fills."""
from collections import defaultdict
import hashlib
import ge66_ocr_audit as audit


def occurrence_metrics(reference,records):
    expected,found=defaultdict(list),defaultdict(list)
    for row in reference:
        expected[(int(row['page']),row['code'])].append(audit.canonical(row))
    for row in records:
        found[(int(row['page']),row['code'])].append(audit.canonical(row))
    exact=0;differences=[];missing=[];extra=[]
    signature=lambda r:tuple(audit.norm(r[f]) for f in audit.FIELDS)
    for page,code in sorted(set(expected)|set(found)):
        want=list(expected[(page,code)]);got=list(found[(page,code)])
        for row in list(want):
            match=next((i for i,r in enumerate(got) if signature(r)==signature(row)),None)
            if match is not None:
                exact+=1;want.remove(row);got.pop(match)
        paired=min(len(want),len(got))
        for i in range(paired):
            differences.append({'page':page,'code':code,'reference':want[i],'observed':got[i],
                                'fields':[f for f in audit.FIELDS if audit.norm(want[i][f])!=audit.norm(got[i][f])]})
        if len(want)>paired:
            missing.append({'page':page,'code':code,'count':len(want)-paired})
        if len(got)>paired:
            extra.append({'page':page,'code':code,'count':len(got)-paired})
    return {'expected':len(reference),'selected':len(records),'all_fields_exact':exact,
            'differences':differences,'missing_occurrences':missing,'extra_occurrences':extra}


def occurrence_gate(score,*,failures):
    return bool(score['expected'] and score['all_fields_exact']==score['expected']
                and not score['missing_occurrences'] and not score['extra_occurrences']
                and not score['differences'] and not failures)


def verify_completion_hashes(directory,marker):
    """Reject recognition artifacts changed after the completion marker."""
    hashes=marker.get('immutable_ocr_sha256',{})
    allowed={'candidate.json','observations.json','occurrence-candidate.json'}
    if not set(hashes)<=allowed:
        raise RuntimeError('Unknown recognition artifact in completion marker')
    for name,expected in hashes.items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Recognition artifact changed after completion: '+name)
    return len(hashes)
