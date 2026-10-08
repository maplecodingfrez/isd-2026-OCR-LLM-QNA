"""Finish glyphs at crop boundaries using pixels only; retain unsafe-crop evidence."""
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
