"""Remember locally frozen page plans; fresh scope cannot reuse known images."""
import json


def prior_image_pages(root,output,pdf_sha256,*,baseline=()):
    used=set(baseline)
    for path in (root/'outputs').rglob('plan.json'):
        if path.parent.resolve()==output.resolve():continue
        plan=json.loads(path.read_text(encoding='utf-8'))
        if plan.get('pdf_sha256')!=pdf_sha256:continue
        pages=plan.get('pages',[])
        if not isinstance(pages,list) or any(type(p) is not int or p<1 for p in pages):
            raise ValueError('Invalid prior PDF page history: '+str(path))
        used.update(pages)
    return sorted(used)


def require_fresh_sample(output,pages,previous_pages,*,development):
    if development:return
    if set(pages)&set(previous_pages):
        raise ValueError('Previously used pages require a new development output, not fresh scope')
    if (output/'ocr-complete.json').exists() or (output/'reference-evaluation-only.json').exists() or any(output.glob('page-*/reference-text-evaluation-only.txt')):
        raise ValueError('Completed/reference-opened output is immutable; score it or use new untouched pages')
