"""Restore visually verified IT term headings without changing course data.

The correction applies only when every group membership matches the source.
Other plans and unverified structures retain their existing output.
"""
import json
from pathlib import Path


def verified_groups(year, semester, slot, members):
    path = Path(__file__).resolve().parents[3] / 'data/reference/it-year3-semester1.json'
    if (year, semester, slot.get('kind'), slot.get('credits')) != (3, 1, 'choose_group', 9):
        return None
    try:
        source = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    actual = {}
    for member in members:
        actual.setdefault(member['group_no'], set()).add(member['code'])
    expected = {i: set(group['codes']) for i, group in enumerate(source['groups'], 1)}
    if actual != expected:
        return None
    by_group_code = {(member['group_no'], member['code']): member for member in members}
    ordered = []
    for number, group in enumerate(source['groups'], 1):
        for code in group['codes']:
            ordered.append({**by_group_code[number, code], 'group_name': group['name']})
    return ordered, source
