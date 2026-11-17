"""A source as a UFO 3 font, for opening it in a font editor, and back.

Each glyph becomes a GLIF file (name, advance, Unicode values and outline
points), font information and glyph order go into the standard plists, and the
OpenType tables the build reuses as they are are kept under data/ in
hexadecimal. `fontviber.source.convert` writes one and checks it reads back.
"""
from __future__ import annotations

from pathlib import Path
import plistlib
import xml.etree.ElementTree as ET

from .source import TABLES, number as _number, value as _value

TABLE_DIR = 'data/org.fontviber.tables'
ILLEGAL = set('"*+/:<>?[\\]|') | {chr(c) for c in range(32)} | {chr(127)}
RESERVED = {'con', 'prn', 'aux', 'clock$', 'nul', 'a:-z:'} | {f'com{i}' for i in range(1, 10)} | {f'lpt{i}' for i in range(1, 10)}


def glyph_file_name(name, taken):
    """The UFO 3 user-name-to-file-name convention."""
    out = ''.join('_' if c in ILLEGAL else c + '_' if c != c.lower() else c for c in name)
    if out.startswith('.'):
        out = '_' + out[1:]
    out = '.'.join('_' + part if part.lower() in RESERVED else part for part in out.split('.'))
    base = out[:250]
    candidate, n = base + '.glif', 1
    while candidate.lower() in taken:
        candidate = f'{base[:230]}{n:015d}.glif'
        n += 1
    taken.add(candidate.lower())
    return candidate


def path_to_points(path):
    """M/L/C/Z contours as cyclic UFO point lists: [(x, y, type or None)]."""
    contours, current = [], None
    for cmd in path:
        if cmd[0] == 'M':
            current = [cmd]
        elif cmd[0] == 'Z':
            contours.append(current)
        else:
            current.append(cmd)
    out = []
    for c in contours:
        start, segments = c[0][1:3], c[1:]
        if not segments:
            out.append([(start[0], start[1], 'move')])
            continue
        last = segments[-1]
        assert list(last[-2:]) == list(start), 'every contour must close explicitly on its start point'
        points = [(start[0], start[1], 'curve' if last[0] == 'C' else 'line')]
        for seg in segments[:-1]:
            if seg[0] == 'C':
                points += [(seg[1], seg[2], None), (seg[3], seg[4], None), (seg[5], seg[6], 'curve')]
            else:
                points.append((seg[1], seg[2], 'line'))
        if last[0] == 'C':
            points += [(last[1], last[2], None), (last[3], last[4], None)]
        out.append(points)
    return out


def points_to_path(contours):
    path = []
    for points in contours:
        x, y, kind = points[0]
        path.append(['M', x, y])
        if kind == 'move':
            path.append(['Z'])
            continue
        pending = []
        for px, py, pkind in points[1:] + [points[0]]:
            if pkind is None:
                pending.append((px, py))
            elif pending:
                (ax, ay), (bx, by) = pending
                path.append(['C', ax, ay, bx, by, px, py])
                pending = []
            else:
                path.append(['L', px, py])
        path.append(['Z'])
    return path


def glif(glyph, unicodes):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<glyph name="{_escape(glyph["name"])}" format="2">',
             f'  <advance width="{glyph["advance"]}"/>']
    lines += [f'  <unicode hex="{cp:04X}"/>' for cp in unicodes]
    contours = path_to_points(glyph['path'])
    if contours:
        lines.append('  <outline>')
        for points in contours:
            lines.append('    <contour>')
            for x, y, kind in points:
                attr = f' type="{kind}"' if kind else ''
                lines.append(f'      <point x="{_number(x)}" y="{_number(y)}"{attr}/>')
            lines.append('    </contour>')
        lines.append('  </outline>')
    lines.append('</glyph>')
    return '\n'.join(lines) + '\n'


def _escape(text):
    return text.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def read_glif(path):
    root = ET.parse(path).getroot()
    advance = root.find('advance')
    unicodes = [int(u.get('hex'), 16) for u in root.findall('unicode')]
    contours = []
    outline = root.find('outline')
    if outline is not None:
        for contour in outline.findall('contour'):
            contours.append([(_value(p.get('x')), _value(p.get('y')), p.get('type'))
                             for p in contour.findall('point')])
    return {'name': root.get('name'), 'advance': int(advance.get('width')) if advance is not None else 0,
            'path': points_to_path(contours)}, unicodes


def _plist(path, value):
    path.write_bytes(plistlib.dumps(value, sort_keys=True))


def write_ufo(source, output):
    """Write a source (see fontviber.source) as a UFO 3 directory at output."""
    output = Path(output)
    if output.exists():
        raise ValueError(f'{output} already exists')
    unicodes = {}
    for cp, gid in sorted(source['cmap'].items(), key=lambda item: int(item[0])):
        unicodes.setdefault(gid, []).append(int(cp))
    (output / 'glyphs').mkdir(parents=True)
    (output / TABLE_DIR).mkdir(parents=True)
    _plist(output / 'metainfo.plist', {'creator': 'org.fontviber', 'formatVersion': 3, 'formatVersionMinor': 0})
    _plist(output / 'fontinfo.plist', source['info'])
    _plist(output / 'layercontents.plist', [['public.default', 'glyphs']])
    _plist(output / 'lib.plist', {
        'public.glyphOrder': [g['name'] for g in source['glyphs']],
        'org.fontviber.source': source['origin'],
        'org.fontviber.tables': f'{TABLE_DIR}: OpenType tables reused as they are, in hexadecimal text',
    })
    contents, taken = {}, set()
    for gid, g in enumerate(source['glyphs']):
        name = glyph_file_name(g['name'], taken)
        contents[g['name']] = name
        (output / 'glyphs' / name).write_text(glif(g, unicodes.get(gid, [])), encoding='utf-8')
    _plist(output / 'glyphs' / 'contents.plist', contents)
    for tag in TABLES:
        hexed = source['tables'][tag].hex()
        text = '\n'.join(hexed[i:i + 64] for i in range(0, len(hexed), 64))
        (output / TABLE_DIR / f"{tag.replace('/', '_')}.hex").write_text(text + '\n', encoding='ascii')


def load_ufo(path):
    """A UFO written by write_ufo, as a source."""
    path = Path(path)
    info = plistlib.loads((path / 'fontinfo.plist').read_bytes())
    lib = plistlib.loads((path / 'lib.plist').read_bytes())
    contents = plistlib.loads((path / 'glyphs' / 'contents.plist').read_bytes())
    glyphs, cmap = [], {}
    for gid, name in enumerate(lib['public.glyphOrder']):
        glyph, unicodes = read_glif(path / 'glyphs' / contents[name])
        glyphs.append(glyph)
        for cp in unicodes:
            cmap[cp] = gid
    tables = {}
    for tag in TABLES:
        text = (path / TABLE_DIR / f"{tag.replace('/', '_')}.hex").read_text(encoding='ascii')
        tables[tag] = bytes.fromhex(''.join(text.split()))
    return {'upem': info['unitsPerEm'], 'family': info['familyName'],
            'cmap': {str(cp): gid for cp, gid in sorted(cmap.items())},
            'glyphs': glyphs, 'tables': tables, 'info': info, 'origin': lib.get('org.fontviber.source')}
