"""Spacing references stored as parameters rather than fonts.

Vespera takes only these values from a spacing reference such as TeX Gyre
Pagella X: each glyph's name, advance and ink box, the Unicode mapping, and the
pair kerning. `extract_spacing` reads them from a font once; the build loads the
resulting JSON, so the reference font itself is not needed in the repository.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from .font_io import bbox, extract_font, sfnt_tables
from .layout import read_kerning

FORMAT = 1


def extract_spacing(font):
    """Parameters of a spacing reference font, as plain JSON-ready data."""
    font = Path(font)
    data = extract_font(font)
    kerning = []
    for subtables in read_kerning(sfnt_tables(font)['GPOS']):
        lookup = []
        for sub in subtables:
            if sub[0] == 'pairs':
                lookup.append({'type': 'pairs', 'pairs': {
                    str(first): {str(second): value for second, value in sorted(row.items())}
                    for first, row in sorted(sub[1].items())}})
            else:
                _, coverage, class1, class2, (n1, n2), values = sub
                lookup.append({'type': 'classes', 'coverage': coverage,
                               'class1': {str(g): c for g, c in sorted(class1.items())},
                               'class2': {str(g): c for g, c in sorted(class2.items())},
                               'counts': [n1, n2], 'values': values})
        kerning.append(lookup)
    return {
        'format': FORMAT,
        'source': font.name,
        'source_sha256': hashlib.sha256(font.read_bytes()).hexdigest(),
        'family': data['family'],
        'upem': data['upem'],
        'cmap': {cp: gid for cp, gid in sorted(data['cmap'].items(), key=lambda item: int(item[0]))},
        'glyphs': [{'name': g['name'], 'advance': g['advance'],
                    'box': list(bbox(g['path'])) if g['path'] else None} for g in data['glyphs']],
        'kerning': kerning,
    }


def write_spacing(font, output):
    """JSON with one glyph per line; a .gz output is gzip-compressed with a fixed
    timestamp, so the same font always gives the same bytes (gunzip -c to read)."""
    data = extract_spacing(font)
    glyphs = data.pop('glyphs')
    text = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    lines = ',\n'.join(json.dumps(g, separators=(',', ':'), ensure_ascii=False) for g in glyphs)
    raw = (text[:-1] + ',"glyphs":[\n' + lines + '\n]}\n').encode('utf-8')
    output = Path(output)
    output.write_bytes(gzip.compress(raw, 9, mtime=0) if output.suffix == '.gz' else raw)
    return len(glyphs)


def load_spacing(path):
    """The parameters in the shape the build uses (integer glyph ids, parsed kerning)."""
    raw = Path(path).read_bytes()
    data = json.loads(gzip.decompress(raw) if Path(path).suffix == '.gz' else raw)
    if data.get('format') != FORMAT or data.get('upem') != 1000:
        raise ValueError(f'{Path(path).name}: not a 1000-unit Vespera spacing file (format {FORMAT})')
    kerning = []
    for lookup in data['kerning']:
        subs = []
        for sub in lookup:
            if sub['type'] == 'pairs':
                subs.append(('pairs', {int(first): {int(second): value for second, value in row.items()}
                                       for first, row in sub['pairs'].items()}))
            else:
                subs.append(('classes', sub['coverage'],
                             {int(g): c for g, c in sub['class1'].items()},
                             {int(g): c for g, c in sub['class2'].items()},
                             tuple(sub['counts']), sub['values']))
        kerning.append(subs)
    data['kerning'] = kerning
    for g in data['glyphs']:
        g['box'] = tuple(g['box']) if g['box'] else None
    return data
