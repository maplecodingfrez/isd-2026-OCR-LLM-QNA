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
    text = body.get('message', {}).get('content', '')
    path.with_suffix('.md').write_text(text, encoding='utf-8')
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


def thai_title_image(image):
    # Word boxes locate Thai across the full row; fixed column ratios can cut
    # leading vowels when native-resolution crops have different padding.
    names = image
    data = audit.ocr(names, 'tha+eng', 6, data=True)
    indices = [i for i, text in enumerate(data['text']) if re.search(r'[\u0e00-\u0e7f]', text)]
    if not indices:
        return None, {'reason': 'no_image_recognized_thai_region'}
    if any(audit.CODE.search(data['text'][i]) for i in indices):
        return None, {'reason': 'inseparable_code_and_thai_word'}
    line_keys = ('block_num', 'par_num', 'line_num')
    if all(key in data for key in line_keys):
        line = lambda i: tuple(data[key][i] for key in line_keys)
        thai_lines = {line(i) for i in indices}
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
    box = [max(0, min(data['left'][i] for i in indices)-8),
           max(0, min(data['top'][i] for i in indices)-8),
           min(names.width, max(data['left'][i]+data['width'][i] for i in indices)+8),
           min(names.height, max(data['top'][i]+data['height'][i] for i in indices)+8)]
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
        if len(peers) < 2:
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
