"""Font sources: one plain-text file per font.

A source holds what the build takes from an original font: font information,
every glyph (name, advance, Unicode values, outline) in glyph order, and the
OpenType tables reused as they are (layout, metrics headers) in hexadecimal.

    fontviber-source 1
    from texgyrepagella-regular.otf <sha256 of that font>
    info unitsPerEm 1000
    info familyName "TeX Gyre Pagella"

    glyph A
    advance 722
    unicode 0041
    M 10 0
    L 300 680
    C 310 690 320 700 330 700
    Z

    table GPOS
    00010000000a...

Outlines are the build's own M/L/C/Z commands in font units, y up. Info values
are JSON. Glyph order matters: anchor and layout tables refer to glyph ids.
`convert` reads a source back after writing it and checks it is exact, so a font
built from the text file is identical to one built from the original font.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

from .font_io import extract_font, sfnt_tables

MAGIC = 'fontviber-source 1'
TABLES = ('GDEF', 'GPOS', 'GSUB', 'OS/2', 'head', 'hhea', 'maxp', 'post')
ARITY = {'M': 2, 'L': 2, 'C': 6, 'Z': 0}


def tree_digest(path):
    """SHA-256 of a file, or of a directory's relative paths and contents (UFO)."""
    path = Path(path)
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256()
    for item in sorted(p for p in path.rglob('*') if p.is_file() and p.name != '.DS_Store'):
        digest.update(item.relative_to(path).as_posix().encode() + b'\0')
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def number(v):
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def value(text):
    v = float(text)
    return int(v) if v.is_integer() else v


def _names(table):
    _, count, offset = struct.unpack_from('>HHH', table)
    out = {}
    for i in range(count):
        platform, encoding, language, key, length, start = struct.unpack_from('>HHHHHH', table, 6 + i * 12)
        if (platform, encoding, language) == (3, 1, 0x409):
            out[key] = table[offset + start:offset + start + length].decode('utf-16-be')
    return out


def read_otf(path):
    """An OpenType font as a source."""
    path = Path(path)
    data, tables = extract_font(path), sfnt_tables(path)
    names = _names(tables['name'])
    head, hhea, os2, post = tables['head'], tables['hhea'], tables['OS/2'], tables['post']
    revision = struct.unpack_from('>i', head, 4)[0] / 65536
    info = {
        'familyName': names.get(16, names.get(1, data['family'])), 'styleName': names.get(17, names.get(2, 'Regular')),
        'unitsPerEm': data['upem'],
        'ascender': struct.unpack_from('>h', hhea, 4)[0], 'descender': struct.unpack_from('>h', hhea, 6)[0],
        'italicAngle': struct.unpack_from('>i', post, 4)[0] / 65536,
        'versionMajor': int(revision), 'versionMinor': round((revision - int(revision)) * 1000),
        'postscriptFontName': names.get(6, ''),
    }
    if struct.unpack_from('>H', os2, 0)[0] >= 2:
        info['xHeight'], info['capHeight'] = struct.unpack_from('>hh', os2, 86)
    for key, field in ((0, 'copyright'), (7, 'trademark'), (9, 'openTypeNameDesigner'),
                       (13, 'openTypeNameLicense'), (14, 'openTypeNameLicenseURL'), (5, 'openTypeNameVersion')):
        if key in names:
            info[field] = names[key]
    return {'upem': data['upem'], 'family': info['familyName'], 'cmap': data['cmap'], 'glyphs': data['glyphs'],
            'tables': {tag: tables[tag] for tag in TABLES}, 'info': info,
            'origin': {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}


def write_text(source, output):
    """Write a source as one text file."""
    unicodes = {}
    for cp, gid in sorted(source['cmap'].items(), key=lambda item: int(item[0])):
        unicodes.setdefault(gid, []).append(int(cp))
    origin = source['origin']
    lines = [MAGIC, f"from {origin['file']} {origin['sha256']}"]
    lines += [f'info {key} {json.dumps(v, ensure_ascii=False)}' for key, v in sorted(source['info'].items())]
    for gid, glyph in enumerate(source['glyphs']):
        if not glyph['name'] or any(c.isspace() for c in glyph['name']):
            raise ValueError(f'glyph {gid}: name {glyph["name"]!r} cannot be written')
        lines += ['', f"glyph {glyph['name']}", f"advance {glyph['advance']}"]
        lines += [f'unicode {cp:04X}' for cp in unicodes.get(gid, [])]
        lines += [' '.join([cmd[0], *map(number, cmd[1:])]) for cmd in glyph['path']]
    for tag in TABLES:
        hexed = source['tables'][tag].hex()
        lines += ['', f'table {tag}', *(hexed[i:i + 64] for i in range(0, len(hexed), 64))]
    Path(output).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def read_text(path):
    """A source written by write_text."""
    path = Path(path)
    lines = path.read_text(encoding='utf-8').split('\n')
    if lines[0] != MAGIC:
        raise ValueError(f'{path.name}: not a FontViber text source ({MAGIC!r} expected)')
    info, glyphs, cmap, tables, origin = {}, [], {}, {}, None
    glyph = table = None
    for number_, line in enumerate(lines[1:], 2):
        if not line:
            glyph = table = None
            continue
        word, _, rest = line.partition(' ')
        try:
            if table is not None:
                tables[table].append(line)
            elif word == 'from':
                name, sha = rest.rsplit(' ', 1)
                origin = {'file': name, 'sha256': sha}
            elif word == 'info':
                key, _, raw = rest.partition(' ')
                info[key] = json.loads(raw)
            elif word == 'glyph':
                glyph = {'name': rest, 'advance': 0, 'path': []}
                glyphs.append(glyph)
            elif word == 'table':
                table = rest
                tables[table] = []
            elif glyph is None:
                raise ValueError('outside a glyph block')
            elif word == 'advance':
                glyph['advance'] = int(rest)
            elif word == 'unicode':
                cmap[int(rest, 16)] = len(glyphs) - 1
            elif word in ARITY:
                args = rest.split() if rest else []
                if len(args) != ARITY[word]:
                    raise ValueError(f'{word} takes {ARITY[word]} numbers')
                glyph['path'].append([word, *map(value, args)])
            else:
                raise ValueError(f'unknown line {word!r}')
        except ValueError as error:
            raise ValueError(f'{path.name}:{number_}: {error}') from None
    missing = [tag for tag in TABLES if tag not in tables]
    if missing:
        raise ValueError(f'{path.name}: missing tables {", ".join(missing)}')
    return {'upem': info['unitsPerEm'], 'family': info['familyName'],
            'cmap': {str(cp): gid for cp, gid in sorted(cmap.items())}, 'glyphs': glyphs,
            'tables': {tag: bytes.fromhex(''.join(tables[tag])) for tag in TABLES},
            'info': info, 'origin': origin}


def load_source(path):
    """A source font: a text source, a UFO directory or an OpenType file."""
    path = Path(path)
    if path.is_dir():
        from .ufo import load_ufo
        return load_ufo(path)
    with path.open('rb') as handle:
        if handle.read(len(MAGIC)) == MAGIC.encode():
            return read_text(path)
    return read_otf(path)


def same(a, b):
    """Whether two sources give the build identical input."""
    return (a['upem'] == b['upem'] and {str(k): v for k, v in a['cmap'].items()} == {str(k): v for k, v in b['cmap'].items()}
            and len(a['glyphs']) == len(b['glyphs'])
            and all((x['name'], x['advance'], x['path']) == (y['name'], y['advance'], y['path'])
                    for x, y in zip(a['glyphs'], b['glyphs']))
            and all(a['tables'][t] == b['tables'][t] for t in TABLES))


def convert(font, output):
    """Convert an OpenType font, UFO or text source to a text source (.txt) or UFO (.ufo); returns the glyph count."""
    output = Path(output)
    if output.exists():
        raise ValueError(f'{output} already exists')
    source = load_source(font)
    if output.suffix == '.ufo':
        from .ufo import write_ufo
        write_ufo(source, output)
    else:
        write_text(source, output)
    if not same(load_source(output), source):
        raise AssertionError(f'{output} does not read back exactly')
    return len(source['glyphs'])
