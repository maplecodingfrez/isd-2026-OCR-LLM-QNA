"""Finish glyphs at crop boundaries using pixels only; retain unsafe-crop evidence."""
def table_row_crop(image, anchor_y, left, right, *, horizontal_start=0.05,
                   horizontal_end=0.95, rule_coverage=0.72):
    """Crop the complete table row containing an image-recognized code anchor.

    Long horizontal rules define row cells; use them when both adjacent rules
    are clear and the anchor falls between them. If not, let the caller use its
    bounded fallback crop and preserve the review flag.
    """
    width, height = image.size
    x0, x1 = int(width*horizontal_start), int(width*horizontal_end)
    band = image.convert('L').crop((x0, 0, x1, height))
    pixels, band_width = band.tobytes(), band.width
    active = [sum(value < 180 for value in pixels[y*band_width:(y+1)*band_width])
              >= band_width*rule_coverage for y in range(height)]
    groups = []
    for y, is_rule in enumerate(active):
        if not is_rule:
            continue
        if not groups or y > groups[-1][-1]+2:
            groups.append([])
        groups[-1].append(y)
    center = int(anchor_y)
    upper = [group for group in groups if group[-1] < center]
    lower = [group for group in groups if group[0] > center]
    if not upper or not lower:
        return None, {'clipped': True, 'reason': 'missing_adjacent_table_rules'}
    top, bottom = upper[-1][-1]+1, lower[0][0]
    if bottom-top < 12:
        return None, {'clipped': True, 'reason': 'invalid_table_row_bounds'}
    box = [int(left), top, int(right), bottom]
    crop = image.crop(box)
    return crop, {'clipped': False, 'original_box': box, 'box': box,
                  'boundary_adjusted': False, 'crop_method': 'adjacent_horizontal_rules',
                  'rule_band': [x0, x1], 'rule_coverage': rule_coverage,
                  'horizontal_rules': [[upper[-1][0], upper[-1][-1]],
                                       [lower[0][0], lower[0][-1]]]}


def safe_row_crop(image, box, max_expand=80):
    left, top, right, bottom = map(int, box)
    lo, hi = max(0, top-max_expand), min(image.height, bottom+max_expand)
    # Names occupy the area after the code column. Include credits/long titles.
    strip = image.crop((max(left, int(image.width*.235)), lo, right, hi)).convert('L')
    data = strip.tobytes()
    width = strip.width
    # Narrow rules spanning the entire inspection band are table borders,
    # not cut glyphs. Ignore them for boundary detection only; retain every
    # pixel in the returned image. Short strokes never qualify as rules.
    rules = set()
    if strip.height >= 160:
        columns = [x for x in range(width) if sum(data[y*width+x] < 180
                   for y in range(strip.height)) >= strip.height*.98]
        groups = []
        for x in columns:
            if not groups or x != groups[-1][-1]+1:
                groups.append([])
            groups[-1].append(x)
        for group in groups:
            if len(group) <= 6:
                rules.update(group)
    ink = [sum(data[y*width+x] < 180 for x in range(width) if x not in rules) >= 4
           for y in range(strip.height)]
    original = [left, top, right, bottom]
    while top > lo and ink[top-lo]:
        top -= 1
    while bottom < hi and ink[bottom-1-lo]:
        bottom += 1
    clipped = ink[top-lo] or ink[bottom-1-lo]
    # Keep a few blank rows around complete glyphs, without adding another line.
    for _ in range(4):
        if top > lo and not ink[top-1-lo]:
            top -= 1
        if bottom < hi and not ink[bottom-lo]:
            bottom += 1
    adjusted = [left, top, right, bottom]
    return image.crop(adjusted), {'clipped': bool(clipped), 'original_box': original,
                                 'box': adjusted, 'boundary_adjusted': adjusted != original}


def table_title_cell(image):
    """Use strong vertical rules to bound a wide central title cell, or refuse.

    This document-specific geometry excludes code/credit cells without editing
    glyph pixels or recognized text. Narrow/tall letter strokes and ambiguous
    multiple wide cells do not supply a table-cell boundary.
    """
    gray = image.convert('L')
    width, height = gray.size
    pixels = gray.tobytes()
    groups = []
    for x in range(width):
        if sum(pixels[y*width+x] < 180 for y in range(height)) < height*.7:
            continue
        if not groups or x != groups[-1][-1]+1:
            groups.append([])
        groups[-1].append(x)
    rules = [(g[0], g[-1]+1) for g in groups if len(g) <= max(3, width*.02)]
    boxes = [[left[1], 0, right[0], height] for left, right in zip(rules, rules[1:])
             if right[0]-left[1] >= width*.4
             and width*.3 <= (left[1]+right[0])/2 <= width*.7]
    if len(boxes) != 1:
        return None, {'reason': 'no_unique_wide_title_cell', 'reference_used': False}
    box = boxes[0]
    return image.crop(box), {'table_cell_box': box, 'coordinate_space': 'row_image',
                             'cell_method': 'vertical_pixel_rules', 'reference_used': False}


def code_anchor_left(anchors):
    """Include observed code glyphs and a height-derived blank left margin."""
    return max(0, min(int(a['left'])-max(12, round(a['height']*.8)) for a in anchors))


def code_anchor_occurrences(readings):
    """Merge duplicate detections at one position, preserving printed repeats."""
    anchors = []
    for row in sorted(readings, key=lambda a: (a['top'], a['left'], a['code'])):
        duplicate = next((a for a in anchors if a['code'] == row['code']
                          and max(a['top'], row['top']) < min(a['top']+a['height'], row['top']+row['height'])
                          and abs(a['left']-row['left']) <= max(a['height'], row['height'])), None)
        if duplicate is None:
            anchors.append(dict(row))
        else:
            bottom = max(duplicate['top']+duplicate['height'], row['top']+row['height'])
            duplicate['top'] = min(duplicate['top'],row['top'])
            duplicate['height'] = bottom-duplicate['top']
            duplicate['left'] = min(duplicate['left'],row['left'])
    return anchors
