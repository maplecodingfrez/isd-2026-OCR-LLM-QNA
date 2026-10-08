"""Finalize frozen OCR artifacts before any reference access."""
import hashlib
import json


def write_trial_artifacts(output,*,observations,records,occurrences,review,raw_pages,failures):
    output.mkdir(parents=True,exist_ok=True)
    payloads={'observations.json':observations,'candidate.json':{'records':records,'state':'unapproved'},
              'occurrence-candidate.json':{'records':occurrences,'state':'unapproved'},
              'review-queue.json':review,'raw-pages.json':raw_pages,'failures.json':failures}
    for name,value in payloads.items():
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    marker={'completed_before_reference_extraction':True,'records':len(records),
            'immutable_ocr_sha256':{name:hashlib.sha256((output/name).read_bytes()).hexdigest()
                                   for name in ('candidate.json','observations.json','occurrence-candidate.json')}}
    (output/'ocr-complete.json').write_text(json.dumps(marker,indent=2),encoding='utf-8')
    return marker
