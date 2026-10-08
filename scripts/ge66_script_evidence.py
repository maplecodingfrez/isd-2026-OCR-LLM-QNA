"""Image-only Thai title and raised Latin glyph evidence; no spelling rules."""
import re
import base64
import hashlib
from html import unescape
import json
import urllib.request
from statistics import median
from PIL import Image, ImageOps
import ge66_ocr_audit as audit

LITERAL_PROMPT = ('Transcribe only the visible text exactly. Preserve uppercase and lowercase '
                  'letters, punctuation, and Thai marks. Do not correct spelling or translate. '
                  'Return plain text only, without explanations or formatting.')


def catalog_table_delimiters(text):
    """Remove a column separator immediately after an observed GE code only.

    Keep every title character, including pipes elsewhere. This converts an
    image-recognized table boundary into plain-row formatting, not spelling.
    """
    return re.sub(r'(?m)^(\s*\*{0,2}9064\d{4})[ \t]*\|[ \t]*', r'\1 ', text)


def recognize_region(path, prompt, model):
    """Retain raw Typhoon response and validate every cached request parameter."""
    identity = {'image_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                'model': model, 'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 1024}}
    cache = path.with_suffix('.response.json')
    if cache.exists():
        body = json.loads(cache.read_text(encoding='utf-8'))
        if body.get('region_request') != identity:
            raise RuntimeError('Region cache provenance changed; use a new output directory')
    else:
        payload = {'model': model, 'stream': False, 'options': identity['options'],
                   'messages': [{'role': 'user', 'content': prompt,
                                 'images': [base64.b64encode(path.read_bytes()).decode('ascii')]}]}
        request = urllib.request.Request('http://127.0.0.1:11434/api/chat',
            data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.load(response)
        body['region_request'] = identity
        audit.write_json(cache, body)
    message = body.get('message')
    text = message.get('content') if isinstance(message, dict) else None
    path.with_suffix('.md').write_text(text if isinstance(text, str) else '', encoding='utf-8')
    if not isinstance(text, str) or not text.strip() or body.get('done') is False:
        raise RuntimeError('Region OCR response was empty, malformed or incomplete')
    if body.get('done_reason') == 'length' or body.get('eval_count', 0) >= 1016:
        raise RuntimeError('Region OCR response was truncated')
    return text


def thai_region_text(raw):
    """Accept a title-only reading, rejecting structural/multi-row output."""
    if re.search(r'<(?:table|figure|page_number)\b|```|\|', raw, re.I):
        return None
    clean = ' '.join(re.sub(r'<[^>]+>', ' ', unescape(raw)).split())
    if not re.search(r'[\u0e00-\u0e7f]', clean) or audit.CODE.search(clean) or audit.CREDIT.search(clean):
        return None
    return clean


def title_thai_indices(data):
    """Initial Thai title block, before a separate English title line."""
    indices = [i for i,t in enumerate(data['text']) if re.search(r'[\u0e00-\u0e7f]',t)]
    if not indices:
        return []
    first_top = min(data['top'][i] for i in indices)
    # A recognized separate English line above Thai means the Thai may be
    # a footer after an unread title; it cannot establish the title region.
    if any(re.search(r'[A-Za-z]', t) and not re.search(r'[\u0e00-\u0e7f]', t)
           and data['top'][i]+data['height'][i] <= first_top
           for i,t in enumerate(data['text'])):
        return []
    first_bottom = min(data['top'][i]+data['height'][i] for i in indices)
    english_top = min((data['top'][i] for i,t in enumerate(data['text'])
                       if re.search(r'[A-Za-z]',t) and not re.search(r'[\u0e00-\u0e7f]',t)
                       and data['top'][i] >= first_bottom), default=float('inf'))
    return [i for i in indices if data['top'][i] < english_top]


def thai_title_image(image):
    # Word boxes locate Thai across the full row; fixed column ratios can cut
    # leading vowels when native-resolution crops have different padding.
    names = image
    data = audit.ocr(names, 'tha+eng', 6, data=True)
    if sum(bool(audit.CODE.fullmatch(t.strip().lstrip('*'))) for t in data['text']) > 1:
        return None, {'reason': 'multiple_course_rows', 'reference_used': False}
    indices = title_thai_indices(data)
    thai_word_indices = list(indices)
    if not indices:
        return None, {'reason': 'no_image_recognized_thai_region'}
    if any(audit.CODE.search(data['text'][i]) for i in indices):
        return None, {'reason': 'inseparable_code_and_thai_word'}
    original = data
    thai_left = min(original['left'][i] for i in thai_word_indices)
    thai_right = max(original['left'][i] + original['width'][i] for i in thai_word_indices)
    thai_top = min(original['top'][i] for i in thai_word_indices)
    thai_bottom = max(original['top'][i] + original['height'][i] for i in thai_word_indices)
    # Preserve OCR observations in their original coordinates so same-line
    # title acronyms remain available while unrelated rows stay excluded.
    indices = [i for i, text in enumerate(original['text']) if text.strip()
               and original['left'][i] < thai_right + 4
               and original['left'][i] + original['width'][i] > thai_left - 4
               and original['top'][i] < thai_bottom + 4
               and original['top'][i] + original['height'][i] > thai_top - 4
               and not audit.CODE.fullmatch(text.strip())]
    data = original
    line_keys = ('block_num', 'par_num', 'line_num')
    if all(key in data for key in line_keys):
        line = lambda i: tuple(data[key][i] for key in line_keys)
        thai_lines = {tuple(original[key][i] for key in line_keys)
                      for i in thai_word_indices}
        code_right = max((data['left'][i]+data['width'][i] for i, text in enumerate(data['text'])
                          if audit.CODE.fullmatch(text.strip())), default=0)
        credit_left = names.width
        for i, text in enumerate(data['text']):
            if line(i) not in thai_lines:
                continue
            if audit.CREDIT.fullmatch(text.strip()) or re.fullmatch(r'\(\d+-\d+-\d+\)', text.strip()):
                credit_left = min(credit_left, data['left'][i])
                if i and line(i-1) == line(i) and re.fullmatch(r'\d+', data['text'][i-1].strip()) and (
                        0 <= data['left'][i]-data['left'][i-1]-data['width'][i-1] <= 2*data['height'][i]):
                    credit_left = min(credit_left, data['left'][i-1])
        # Thai titles may contain Latin acronyms/numbers. Keep all words on
        # their lines between the code and credits, regardless of script.
        indices = [i for i, text in enumerate(data['text']) if text.strip() and
                   line(i) in thai_lines and code_right <= data['left'][i] < credit_left]
    box = [max(0, min(data['left'][i] for i in indices)-12),
           max(0, min(data['top'][i] for i in indices)-12),
           min(names.width, max(data['left'][i]+data['width'][i] for i in indices)+12),
           min(names.height, max(data['top'][i]+data['height'][i] for i in indices)+12)]
    # Table cell verticals are image structure, not Thai title strokes. When
    # strong separators enclose the OCR-observed Thai, use the cell interior
    # so code/credits and the full-width English line cannot enter the region.
    gray = names.convert('L')
    column_ink = [sum(gray.getpixel((x, y)) < 180 for y in range(names.height))
                  for x in range(names.width)]
    separators = []
    for x, count in enumerate(column_ink):
        if count < names.height * .4:
            continue
        if not separators or x > separators[-1][-1] + 2:
            separators.append([])
        separators[-1].append(x)
    rules = [(group[0], group[-1]+1) for group in separators if len(group) > 3]
    left_rules = [right for left, right in rules if right <= min(data['left'][i] for i in thai_word_indices)]
    right_rules = [left for left, right in rules if left >= max(
        data['left'][i]+data['width'][i] for i in thai_word_indices)]
    if left_rules and right_rules:
        box[0] = max(box[0], max(left_rules))
        box[2] = min(box[2], min(right_rules))
    return ImageOps.expand(names.crop(box), border=20, fill='white'), {
        'thai_box': box, 'coordinate_space': 'row_image', 'reference_used': False}


def ink_components(image):
    """Connected ink boxes let glyph height be measured without recognizing text."""
    width, height = image.size
    pixels = image.convert('L').tobytes()
    remaining = {i for i, value in enumerate(pixels) if value < 180}
    boxes = []
    while remaining:
        first = remaining.pop()
        stack, component = [first], [first]
        while stack:
            index = stack.pop()
            x, y = index % width, index // width
            for yy in range(max(0, y-1), min(height, y+2)):
                for xx in range(max(0, x-1), min(width, x+2)):
                    neighbor = yy*width+xx
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        stack.append(neighbor)
                        component.append(neighbor)
        if len(component) >= 3:
            xs = [i % width for i in component]
            ys = [i // width for i in component]
            boxes.append((min(xs), min(ys), max(xs)+1, max(ys)+1))
    return boxes


def raised_english_text(image):
    """Re-read mixed-height words in separate image strips, preserving raw case.

    The surrounding line supplies the baseline. Only compact raised components
    are split; no ordinal suffixes, substitutions or course codes are assumed.
    Returns no extra observation if geometry/readings are inconclusive.
    """
    data = audit.ocr(image, 'eng', 6, data=True)
    indices = [i for i, text in enumerate(data['text']) if text.strip()]
    words = {i: data['text'][i] for i in indices}
    readings = []
    for i in indices:
        line = tuple(data[key][i] for key in ('block_num', 'par_num', 'line_num'))
        peers = [j for j in indices if j != i and
                 tuple(data[key][j] for key in ('block_num', 'par_num', 'line_num')) == line
                 and float(data['conf'][j]) >= 80]
        if not peers:
            continue
        if len(peers) == 1:
            # A wrapped line may have one baseline word. Require other title
            # words to independently establish a consistent regular height.
            others = [j for j in indices if j not in (i, peers[0]) and float(data['conf'][j]) >= 80]
            if len(others) < 2:
                continue
            typical = median(data['height'][j] for j in others)
            if any(abs(data['height'][j]-typical) > typical*.15 for j in others+[peers[0]]):
                continue
        regular_height = median(data['height'][j] for j in peers)
        baseline = median(data['top'][j]+data['height'][j] for j in peers)
        left, top = data['left'][i], data['top'][i]
        width, height = data['width'][i], data['height'][i]
        if regular_height < 8 or height < regular_height*1.15:
            continue
        word = image.crop((left, top, left+width, top+height))
        raised = [b for b in ink_components(word)
                  if .3*regular_height <= b[3]-b[1] <= .8*regular_height
                  and top+b[3] <= baseline-.25*regular_height
                  and top+b[1] < baseline-.8*regular_height]
        if not raised:
            continue
        x0, x1 = min(b[0] for b in raised), max(b[2] for b in raised)
        y0, y1 = min(b[1] for b in raised), max(b[3] for b in raised)
        # Refuse overlapping base/raised glyphs rather than silently losing ink.
        components = ink_components(word)
        if any(b not in raised and b[0] < x1 and b[2] > x0 for b in components):
            continue
        parts = []
        for role, box in [('base', (0, 0, x0, height)),
                          ('raised', (x0, y0, x1, y1)),
                          ('base', (x1, 0, width, height))]:
            if box[2] <= box[0] or not ink_components(word.crop(box)):
                continue
            crop = ImageOps.expand(word.crop(box), border=20, fill='white')
            text = audit.ocr(crop, 'eng', 7).strip()
            parts.append({'role': role, 'box': [left+box[0], top+box[1],
                          left+box[2], top+box[3]], 'text': text})
        if not any(p['role'] == 'base' for p in parts) or not all(
                re.fullmatch(r'[A-Za-z0-9]+', p['text']) for p in parts):
            continue
        words[i] = ''.join(p['text'] for p in parts)
        readings.append({'word_index': i, 'token_index': indices.index(i),
                         'word_box': [left, top, left+width, top+height],
                         'original_text': data['text'][i],
                         'text': words[i], 'parts': parts})
    if not readings:
        return None, {'reason': 'no_verified_raised_glyph_readings', 'reference_used': False}
    return ' '.join(words[i] for i in indices), {
        'readings': readings, 'tokens': [data['text'][i] for i in indices],
        'reference_used': False, 'case_normalized': False}


def english_region_text(raw):
    if re.search(r'<[^>]+>|```|\|', raw):
        return None
    text = ' '.join(raw.split())
    return text if text and re.fullmatch(r'[A-Za-z0-9 &"\'(),./:+@%!?=\[\]#\u2019\u2018\u2013\u2014-]+', text) else None


def thai_tesseract_readings(image, directory):
    """Bounded 600-DPI/native and half-size reads, still one engine family."""
    directory.mkdir(parents=True, exist_ok=True)
    data = audit.ocr(image, 'tha+eng', 6, data=True)
    lines = {tuple(data[key][i] for key in ('block_num', 'par_num', 'line_num'))
             for i, text in enumerate(data['text']) if re.search(r'[\u0e00-\u0e7f]', text)}
    psms = (6, 7) if len(lines) == 1 else (6,)
    variants = [('native', image), ('half', image.resize(
        (max(1, image.width//2), max(1, image.height//2)), Image.Resampling.LANCZOS))]
    results = []
    for variant, crop in variants:
        path = directory / f'thai-{variant}.png'
        crop.save(path)
        for psm in psms:
            text = audit.ocr(crop, 'tha+eng', psm).strip()
            path.with_name(f'thai-{variant}-psm{psm}.txt').write_text(text, encoding='utf-8')
            results.append({'variant': f'thai_{variant}_psm{psm}', 'text': text,
                            'image_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    audit.write_json(directory / 'tesseract-readings.json', results)
    return results


def mixed_script_tesseract_reading(image, directory):
    """Re-read isolated non-Thai tokens in a Thai title, with exact anchors.

    Only unanimous PSM6/7 English image reads may replace a uniquely anchored
    token. The resulting title is still one Tesseract-family observation.
    """
    directory.mkdir(parents=True, exist_ok=True)
    raw = audit.ocr(image, 'tha+eng', 6).strip()
    data = audit.ocr(image, 'tha+eng', 6, data=True)
    meta = {'raw_whole_text': raw, 'readings': [], 'reference_used': False,
            'case_normalized': False, 'engine_family': 'tesseract'}
    if not thai_region_text(raw):
        return None, {**meta, 'reason': 'invalid_thai_title'}
    changes = []
    for i, token in enumerate(data['text']):
        if not re.fullmatch(r'[A-Za-z0-9!?.%+-]+', token) or not re.search(r'[A-Za-z0-9]', token):
            continue
        # Refuse repeated tokens and substring matches inside another Latin word.
        matches = list(re.finditer(r'(?<![A-Za-z0-9])'+re.escape(token)+r'(?![A-Za-z0-9])', raw))
        if len(matches) != 1 or data['text'].count(token) != 1:
            continue
        margin = max(10, round(data['height'][i]*.2))
        box = [max(0, data['left'][i]-margin), max(0, data['top'][i]-margin),
               min(image.width, data['left'][i]+data['width'][i]+margin),
               min(image.height, data['top'][i]+data['height'][i]+margin)]
        path = directory / f'latin-{i:03d}.png'
        crop = ImageOps.expand(image.crop(box), border=30, fill='white')
        crop.save(path)
        reads = {str(psm): audit.ocr(crop, 'eng', psm).strip() for psm in (6, 7)}
        reading = {'original_text': token, 'box': box, 'raw_readings': reads,
                   'image_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        meta['readings'].append(reading)
        value = reads['6']
        if value != token and value == reads['7'] and re.fullmatch(r'[A-Za-z0-9]+', value):
            changes.append((matches[0].start(), matches[0].end(), value))
    ordered = sorted(changes)
    if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        meta['reason'] = 'overlapping_text_anchors'
        audit.write_json(directory / 'mixed-script-readings.json', meta)
        return None, meta
    text = raw
    for start, end, value in sorted(changes, reverse=True):
        text = text[:start]+value+text[end:]
    meta['text'] = text
    audit.write_json(directory / 'mixed-script-readings.json', meta)
    return (text if changes else None), meta


def typhoon_raised_text(image, directory, model, meta):
    """Independent whole-title/word readings; Tesseract supplies geometry only.

    Alignment must match on every untouched token. Changed words come entirely
    from Typhoon image reads, never from Tesseract's suggested spelling.
    """
    directory.mkdir(parents=True, exist_ok=True)
    if not meta.get('readings'):
        return None, {'reason': 'no_raised_geometry'}
    path = directory / 'english-literal.png'
    image.save(path)
    whole = english_region_text(recognize_region(path, LITERAL_PROMPT, model))
    if whole is None:
        return None, {'reason': 'invalid_whole_region_reading'}
    tokens = whole.split()
    changed = {r['token_index'] for r in meta['readings']}
    anchors = meta['tokens']
    if len(tokens) != len(anchors) or any(audit.norm(t) != audit.norm(anchors[i])
                                         for i, t in enumerate(tokens) if i not in changed):
        return None, {'reason': 'unaligned_whole_region_reading', 'raw_whole_text': whole}
    word_reads = []
    for reading in meta['readings']:
        index = reading['token_index']
        path = directory / f'word-{index:03d}.png'
        ImageOps.expand(image.crop(reading['word_box']), border=20, fill='white').save(path)
        text = english_region_text(recognize_region(path, LITERAL_PROMPT, model))
        if text is None or not re.fullmatch(r'[A-Za-z0-9]+', text):
            return None, {'reason': 'invalid_word_reading', 'raw_whole_text': whole}
        tokens[index] = text
        word_reads.append({'token_index': index, 'word_box': reading['word_box'], 'text': text})
    return ' '.join(tokens), {'raw_whole_text': whole, 'word_readings': word_reads,
                            'reference_used': False, 'tesseract_text_used_as_fill': False,
                            'case_normalized': False}


def thai_initial_cluster_reading(image, directory):
    """Read an isolated initial Thai base+mark cluster, with literal agreement.

    The base consonant must remain identical. Only unanimous PSM8/13 image
    readings can replace its combining marks; no expected word is supplied.
    This remains one Tesseract-family observation, with raw segment provenance.
    """
    directory.mkdir(parents=True,exist_ok=True)
    raw = audit.ocr(image,'tha+eng',6).strip()
    prefix = re.match(r'^([\u0e01-\u0e2e])([\u0e31\u0e34-\u0e3a\u0e47-\u0e4e]+)',raw)
    meta = {'raw_whole_text':raw,'reference_used':False,'engine_family':'tesseract'}
    if not prefix:
        return None,{**meta,'reason':'no_initial_marked_consonant'}
    components = sorted(ink_components(image),key=lambda b:b[0])
    if not components:
        return None,{**meta,'reason':'no_initial_ink_cluster'}
    cluster = [components[0]]
    edge = components[0][2]
    for box in components[1:]:
        if box[0] >= edge:
            break
        cluster.append(box)
        edge=max(edge,box[2])
    if len(cluster) < 2:
        return None,{**meta,'reason':'inseparable_initial_mark'}
    base_height=max(b[3]-b[1] for b in cluster)
    margin=max(4,round(base_height*.13))
    vertical_margin=max(4,round(base_height/3))
    box=[max(0,min(b[0] for b in cluster)-margin),max(0,min(b[1] for b in cluster)-vertical_margin),
         min(image.width,max(b[2] for b in cluster)+margin),min(image.height,max(b[3] for b in cluster)+vertical_margin)]
    path=directory/'initial-cluster.png'
    crop=ImageOps.expand(image.crop(box),border=35,fill='white');crop.save(path)
    reads={str(psm):audit.ocr(crop,'tha',psm).strip() for psm in (8,13)}
    meta.update(cluster_box=box,raw_cluster_readings=reads,image_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    value=reads['8']
    if value != reads['13'] or not re.fullmatch(r'[\u0e01-\u0e2e][\u0e31\u0e34-\u0e3a\u0e47-\u0e4e]+',value) or value[0] != prefix[1]:
        meta['reason']='inconclusive_initial_cluster'
        audit.write_json(directory/'initial-cluster-readings.json',meta)
        return None,meta
    text=value+raw[prefix.end():]
    meta['text']=text
    audit.write_json(directory/'initial-cluster-readings.json',meta)
    return (text if value != prefix[0] else None),meta


def typhoon_word_text(image, directory, model):
    """Align whole Typhoon text, then re-read disagreeing word pixels literally.

    Tesseract supplies boxes and retry locations only. Untouched words and
    replacement characters all come from Typhoon image responses. A response
    containing another alphabetic word is refused, including title injection.
    """
    directory.mkdir(parents=True,exist_ok=True)
    data=audit.ocr(image,'eng',6,data=True)
    indices=[i for i,t in enumerate(data['text']) if t.strip()]
    path=directory/'whole.png';image.save(path)
    whole=english_region_text(recognize_region(path,LITERAL_PROMPT,model))
    meta={'raw_whole_text':whole,'reference_used':False,'tesseract_text_used_as_fill':False,'word_readings':[]}
    if whole is None or len(whole.split()) != len(indices):
        return None,{**meta,'reason':'unaligned_whole_reading'}
    tokens=whole.split()
    changed=[j for j,i in enumerate(indices) if audit.norm(tokens[j]) != audit.norm(data['text'][i])]
    if not changed or len(changed)>3:
        return None,{**meta,'reason':'no_bounded_word_disagreement'}
    for j in changed:
        i=indices[j]
        box=[max(0,data['left'][i]-15),max(0,data['top'][i]-15),
             min(image.width,data['left'][i]+data['width'][i]+15),
             min(image.height,data['top'][i]+data['height'][i]+15)]
        # Blank margins must not borrow glyphs from adjacent words or lines.
        x0,y0=data['left'][i],data['top'][i]
        x1,y1=x0+data['width'][i],y0+data['height'][i]
        for k in indices:
            if k==i:continue
            ox0,oy0=data['left'][k],data['top'][k]
            ox1,oy1=ox0+data['width'][k],oy0+data['height'][k]
            if max(y0,oy0)<min(y1,oy1):
                if ox1<=x0:box[0]=max(box[0],(ox1+x0)//2)
                elif x1<=ox0:box[2]=min(box[2],(x1+ox0)//2)
                else:return None,{**meta,'reason':'overlapping_word_boxes'}
            if max(x0,ox0)<min(x1,ox1):
                if oy1<=y0:box[1]=max(box[1],(oy1+y0)//2)
                elif y1<=oy0:box[3]=min(box[3],(y1+oy0)//2)
        path=directory/f'word-{j:03d}.png'
        ImageOps.expand(image.crop(box),border=40,fill='white').save(path)
        raw=recognize_region(path,LITERAL_PROMPT,model)
        text=english_region_text(raw)
        if text is None or not re.fullmatch(r'[A-Za-z0-9]+(?:\s*[.,;:!?])*',text):
            return None,{**meta,'reason':'invalid_single_word_reading','rejected_raw':raw}
        split_meta=None
        if audit.norm(text)!=audit.norm(data['text'][i]) and re.fullmatch(r'[A-Za-z0-9]+',text) and re.fullmatch(r'[A-Za-z0-9]+',data['text'][i]):
            split_text,split_meta=typhoon_split_word(image.crop(box),directory/f'split-{j:03d}',model)
            if split_text:text=split_text
        tokens[j]=text
        meta['word_readings'].append({'token_index':j,'box':box,'raw_text':raw,'split_evidence':split_meta,
                                     'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    text=' '.join(tokens);meta['text']=text
    audit.write_json(directory/'word-readings.json',meta)
    return text,meta


def thai_raw_line_probe(image, directory):
    """Supplement a single-line title with unanimous half-size PSM8/13 pixels.

    Preserve every raw reading. A loose segmentation hypothesis with leading
    punctuation is not qualified to vote; no characters are stripped from it.
    Wrapped titles are refused because neither segmentation mode fits them.
    """
    directory.mkdir(parents=True,exist_ok=True)
    data=audit.ocr(image,'tha+eng',6,data=True)
    lines={tuple(data[k][i] for k in ('block_num','par_num','line_num'))
           for i,t in enumerate(data['text']) if re.search(r'[\u0e00-\u0e7f]',t)}
    meta={'reference_used':False,'engine_family':'tesseract'}
    if len(lines)!=1:
        return None,{**meta,'reason':'not_one_thai_line'}
    crop=image.resize((max(1,image.width//2),max(1,image.height//2)),Image.Resampling.LANCZOS)
    path=directory/'thai-half.png';crop.save(path)
    reads={str(psm):audit.ocr(crop,'tha+eng',psm).strip() for psm in (8,13)}
    meta.update(raw_readings=reads,image_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    text=thai_region_text(reads['8'])
    if reads['8']!=reads['13'] or text is None or not re.match(r'[\u0e01-\u0e2e\u0e40-\u0e44A-Za-z0-9]',text):
        meta['reason']='unqualified_raw_line_hypothesis';text=None
    meta['text']=text
    audit.write_json(directory/'raw-line-readings.json',meta)
    return text,meta


def thai_half_literal_probe(image,directory,model):
    """Independent literal half-size image reading; remains Typhoon family."""
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/'thai-half.png'
    image.resize((max(1,image.width//2),max(1,image.height//2)),Image.Resampling.LANCZOS).save(path)
    raw=recognize_region(path,LITERAL_PROMPT,model)
    text=thai_region_text(raw)
    meta={'raw_text':raw,'text':text,'reference_used':False,'engine_family':'typhoon',
          'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    audit.write_json(directory/'literal-readings.json',meta)
    return text,meta


def thai_terminal_literal_probe(image,directory,model):
    """Re-read a terminal consonant cluster; all text comes from Typhoon images.

    This conservative probe fits only a single Thai line ending in Thai.
    Tesseract determines line/language geometry only; its spelling is never
    copied. The replacement must be exactly one base consonant with marks.
    """
    directory.mkdir(parents=True,exist_ok=True)
    data=audit.ocr(image,'tha+eng',6,data=True)
    indices=[i for i,t in enumerate(data['text']) if t.strip()]
    lines={tuple(data[k][i] for k in ('block_num','par_num','line_num')) for i in indices}
    meta={'reference_used':False,'tesseract_text_used_as_fill':False,'engine_family':'typhoon'}
    if not indices or len(lines)!=1 or not re.search(r'[\u0e00-\u0e7f]',data['text'][max(indices,key=lambda i:data['left'][i])]):
        return None,{**meta,'reason':'not_one_terminal_thai_line'}
    path=directory/'whole.png';image.save(path)
    raw=recognize_region(path,LITERAL_PROMPT,model)
    whole=thai_region_text(raw);meta['raw_whole_text']=raw
    terminal=re.search(r'[\u0e01-\u0e2e][\u0e31\u0e34-\u0e3a\u0e47-\u0e4e]*$',whole or '')
    if terminal is None:
        return None,{**meta,'reason':'no_terminal_consonant'}
    boxes=sorted(ink_components(image),key=lambda b:b[2],reverse=True)
    if not boxes:
        return None,{**meta,'reason':'no_terminal_ink'}
    cluster=[boxes[0]];left=boxes[0][0]
    for box in boxes[1:]:
        if box[2]<=left:
            break
        cluster.append(box);left=min(left,box[0])
    height=max(b[3]-b[1] for b in cluster);margin=max(4,round(height*.13))
    box=[max(0,left-margin),max(0,min(b[1] for b in cluster)-margin),
         min(image.width,max(b[2] for b in cluster)+margin),min(image.height,max(b[3] for b in cluster)+margin)]
    path=directory/'terminal.png';ImageOps.expand(image.crop(box),border=40,fill='white').save(path)
    raw_cluster=recognize_region(path,LITERAL_PROMPT,model)
    meta.update(cluster_box=box,raw_cluster_text=raw_cluster,image_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    value=raw_cluster.strip()
    if not re.fullmatch(r'[\u0e01-\u0e2e][\u0e31\u0e34-\u0e3a\u0e47-\u0e4e]*',value):
        text=None;meta['reason']='not_one_consonant_cluster'
    else:
        text=whole[:terminal.start()]+value
    meta['text']=text;audit.write_json(directory/'terminal-readings.json',meta)
    return text,meta


def typhoon_split_word(image,directory,model):
    """Read two literal pixel parts across a central blank column, no lexicon.

    Both parts must be a single alphanumeric token. Refuse inseparable ink,
    punctuation or multiword responses; never strip or copy suggested letters.
    """
    directory.mkdir(parents=True,exist_ok=True)
    pixels=image.convert('L').tobytes();w,h=image.size
    active={x for x in range(w) if any(pixels[y*w+x]<180 for y in range(h))}
    meta={'reference_used':False,'tesseract_text_used_as_fill':False,'raw_parts':[],'image_sha256':[]}
    if not active:return None,{**meta,'reason':'no_word_ink'}
    lo,hi=min(active),max(active)+1
    inset=max(2,(hi-lo)//5)
    gaps=[x for x in range(lo+inset,hi-inset) if x not in active]
    if not gaps:return None,{**meta,'reason':'no_central_blank_column'}
    cut=min(gaps,key=lambda x:abs(x-(lo+hi)/2));meta['split_x']=cut
    for name,box in [('left',(0,0,cut,h)),('right',(cut,0,w,h))]:
        path=directory/f'{name}.png';ImageOps.expand(image.crop(box),border=40,fill='white').save(path)
        raw=recognize_region(path,LITERAL_PROMPT,model)
        meta['raw_parts'].append(raw);meta['image_sha256'].append(hashlib.sha256(path.read_bytes()).hexdigest())
        if not re.fullmatch(r'[A-Za-z0-9]+',raw.strip()):
            meta['reason']='not_one_alphanumeric_part';audit.write_json(directory/'split-readings.json',meta)
            return None,meta
    text=''.join(raw.strip() for raw in meta['raw_parts']);meta['text']=text
    audit.write_json(directory/'split-readings.json',meta)
    return text,meta
