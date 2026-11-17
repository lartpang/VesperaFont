"""One OpenType exporter; spacing and style metadata come from the configuration."""
from __future__ import annotations

import struct

from .font_io import bbox, make_cff, make_sfnt, name_table, sfnt_tables
from .layout import cmap_table, layout_features, transform_anchors, with_kerning
from .metrics import ASCENT, CAP_HEIGHT, CELL, DESCENT, ITALIC_ANGLE, ITALIC_SLOPE, X_HEIGHT

P = struct.pack
U = struct.unpack_from


def naming(config, style):
    return {
        'family': config.family, 'style': style.name,
        'legacy_family': config.legacy_family(style), 'legacy_style': style.ribbi,
        'full': f'{config.family} {style.name}', 'postscript': config.postscript(style),
        'weight': style.weight, 'release': config.version,
    }


def export_font(data, output, config, style):
    glyphs = data['glyphs']
    boxes = [bbox(g['path']) for g in glyphs]
    bounds = (min(b[0] for b in boxes), min(b[1] for b in boxes),
              max(b[2] for b in boxes), max(b[3] for b in boxes))
    names = naming(config, style)
    angle = -ITALIC_ANGLE if style.italic else 0
    # Start from the source's reused tables (layout and metric headers); the rest is rebuilt below.
    tables = dict(data['base_tables']) if 'base_tables' in data else sfnt_tables(config.source)
    for tag in ('DSIG', 'FFTM'):
        tables.pop(tag, None)
    tables['CFF '] = make_cff(glyphs, bounds, names, config.font_version, config.monospaced, angle)
    tables['name'] = name_table(names, config.font_version, config.description)
    if data.get('kerning') and not config.monospaced:
        tables['GPOS'] = with_kerning(tables['GPOS'], data['kerning'])
    tables['GPOS'] = transform_anchors(tables['GPOS'], glyphs)
    if config.monospaced:
        tables.pop('kern', None)
        tables['GPOS'] = layout_features(tables['GPOS'], {'mark', 'mkmk'})
        # No ligatures or kerning in the cell; locl keeps Romanian comma-below s and t.
        tables['GSUB'] = layout_features(tables['GSUB'], {'ccmp', 'locl'})
    tables['cmap'] = cmap_table(data['cmap'])
    head = bytearray(tables['head'])
    head[4:8] = P('>I', round(float(config.font_version) * 65536))
    head[36:44] = P('>hhhh', *bounds)
    head[44:46] = P('>H', (1 if style.bold else 0) | (2 if style.italic else 0))
    tables['head'] = bytes(head)
    tables['hmtx'] = b''.join(P('>Hh', g['advance'], b[0]) for g, b in zip(glyphs, boxes))
    hhea = bytearray(tables['hhea'])
    hhea[4:10] = P('>hhh', ASCENT, DESCENT, 0)
    hhea[10:18] = P('>Hhhh', max(g['advance'] for g in glyphs), min(b[0] for b in boxes),
                    min(g['advance']-b[2] for g, b in zip(glyphs, boxes)), max(b[2] for b in boxes))
    hhea[18:22] = P('>hh', *((1000, round(1000 * ITALIC_SLOPE)) if style.italic else (1, 0)))
    hhea[34:36] = P('>H', len(glyphs))
    tables['hhea'] = bytes(hhea)
    maxp = bytearray(tables['maxp'])
    maxp[4:6] = P('>H', len(glyphs))
    tables['maxp'] = bytes(maxp)
    os2 = bytearray(tables['OS/2'])
    spacing = [g['advance'] for g in glyphs if g['advance']]
    os2[2:4] = P('>h', CELL if config.monospaced else round(sum(spacing) / len(spacing)))
    os2[4:6] = P('>H', style.weight_class)
    os2[8:10] = P('>H', 0)
    os2[58:62] = b'FVB '
    selection = U('>H', os2, 62)[0] & ~0b1100001
    selection |= (1 if style.italic else 0) | (32 if style.bold else 0)
    selection |= 64 if style.ribbi == 'Regular' else 0
    os2[62:64] = P('>H', selection)
    os2[68:78] = P('>hhhHH', ASCENT, DESCENT, 0, max(ASCENT, bounds[3]), max(-DESCENT, -bounds[1]))
    os2[86:90] = P('>hh', X_HEIGHT, CAP_HEIGHT)
    post = bytearray(tables['post'])
    post[4:8] = P('>i', angle * 65536)
    if config.monospaced:
        os2[35] = 9
        os2[46:50] = P('>I', U('>I', os2, 46)[0] | (1 << 11) | (1 << 12))
        post[8:12] = P('>hh', -100, 50)
        post[12:16] = P('>I', 1)
    tables['post'] = bytes(post)
    tables['OS/2'] = bytes(os2)
    output.write_bytes(make_sfnt(tables))
