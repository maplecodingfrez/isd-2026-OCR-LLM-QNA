"""Locate English below image-recognized Thai; preserve wrapped title lines."""
import re
from PIL import ImageOps
import ge66_ocr_audit as audit
from ge66_crop_quality import table_title_cell

def english_title_image(image):
    names, cell_meta = table_title_cell(image)
    if names is None:
        names = image
    data = audit.ocr(names, 'tha+eng', 6, data=True)
    if sum(bool(audit.CODE.fullmatch(t.strip().lstrip('*'))) for t in data['text']) > 1:
        return None, {'reason': 'multiple_course_rows', 'reference_used': False}
    thai_bottoms = [data['top'][i]+data['height'][i] for i,t in enumerate(data['text'])
                    if re.search(r'[\u0e00-\u0e7f]', t)]
    if not thai_bottoms:
        return None, {'reason': 'no_image_recognized_thai_boundary'}
    top = max(thai_bottoms)+2
    if top >= names.height:
        return None, {'reason': 'no_english_region'}
    tail = names.crop((0, top, names.width, names.height))
    pixels = tail.convert('L').tobytes()
    active = [y for y in range(tail.height) if sum(v<180 for v in
              pixels[y*tail.width:(y+1)*tail.width])>=4]
    if not active:
        return None, {'reason': 'empty_english_region'}
    # Keep every line below Thai, not only the last line of a wrapped title.
    start, stop = max(0,active[0]-8), min(tail.height,active[-1]+9)
    return ImageOps.expand(tail.crop((0,start,tail.width,stop)),border=20,fill='white'), {
        **cell_meta, 'thai_bottom':top-2,'english_box':[0,top+start,names.width,top+stop],
        'reference_used':False}
