"""Acquire literal image evidence for withheld fields, without reference access."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
import pytesseract
import ge66_ocr_audit as audit
import ge66_script_evidence as se
from ge66_select_candidate import select


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--observations',type=Path,required=True)
    cli.add_argument('--regions',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--model',default='ggml:8ad769cbef404d27260763e014d082877bbd4d4c4361cd47a141a3d0acff5c47')
    args=cli.parse_args()
    out=args.output.resolve(); source=args.observations.resolve()
    if out==source.parent or out in source.parents or args.regions.resolve()==out:
        raise ValueError('Evidence output must be separate from recognition inputs')
    obs=json.loads(source.read_text(encoding='utf-8'))
    _,review=select(obs)
    targets={r['code']:r['unresolved_fields'] for r in review if r.get('unresolved_fields')}
    regions={f'{code}/{field}.png':args.regions/code/(field+'.png')
             for code,fields in targets.items() for field in fields if field in ('name_th','name_en')}
    plan={'scope':'known-page development glyph evidence','model':args.model,
          'reference_used_as_input':False,'database_access':False,'targets':targets,
          'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'region_sha256':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in regions.items()},
          'frozen_sources':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                            for name in ('ge64_completion_evidence.py','ge66_script_evidence.py','ge66_select_candidate.py')}}
    if (out/'plan.json').exists():
        if json.loads((out/'plan.json').read_text(encoding='utf-8')) != plan:
            raise RuntimeError('Evidence plan changed; use a new output directory')
    else:
        audit.write_json(out/'plan.json',plan)
    pytesseract.pytesseract.tesseract_cmd=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    for code,fields in targets.items():
        page=obs[code][0]['page']
        for field in fields:
            if field not in ('name_th','name_en'):
                continue
            with Image.open(regions[f'{code}/{field}.png']) as image:
                directory=out/code/field
                if field=='name_th':
                    text,meta=se.thai_initial_cluster_reading(image,directory/'initial')
                    engine,variant='tesseract','thai_initial_cluster'
                else:
                    text,meta=se.raised_english_text(image)
                    audit.write_json(directory/'raised.json',meta)
                    engine,variant='tesseract','english_raised_parts'
                    if not text:
                        text,meta=se.typhoon_word_text(image,directory/'words',args.model)
                        engine,variant='typhoon','english_literal_word'
                audit.write_json(directory/'evidence.json',meta)
                if text:
                    obs[code].append({'code':code,'page':page,'engine':engine,'variant':variant,field:text,
                                      'image_sha256':plan['region_sha256'][f'{code}/{field}.png']})
                print(code,field,'new literal reading' if text else 'inconclusive',flush=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==plan['input_sha256']
    records,review=select(obs)
    audit.write_json(out/'observations.json',obs)
    audit.write_json(out/'candidate.json',{'records':records,'state':'unapproved_development'})
    audit.write_json(out/'review-queue.json',review)
    audit.write_json(out/'ocr-complete.json',{'completed_before_reference_extraction':True,'records':len(records)})
    audit.write_json(out/'failures.json',[])
    print('Selected',len(records),'withheld',[r['code'] for r in review if r.get('reason')],flush=True)


if __name__=='__main__':
    main()
