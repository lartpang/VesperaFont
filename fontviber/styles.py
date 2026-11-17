"""Weights and slopes, applied identically to both families from one master.

Order of operations for each style: slant the master (italic only), fit the
family's widths, then embolden every outline with the family-wide stroke model.
Each outline map is mirrored into the glyph's anchor transform so combining
marks follow the letters they attach to.
"""
from __future__ import annotations

import copy

from .export import export_font
from .font_io import bbox, extract_font, map_path
from .layout import remap_kerning
from .glyphs import DIGITS
from .metrics import ITALIC_CONDENSE, ITALIC_PIVOT, ITALIC_SLOPE, WEIGHT_GAINS, compose, stroke_gain

TABULAR = set(DIGITS) | {n + '.taboldstyle' for n in DIGITS} | {'zero.slash'}


def slant(g, centre=None):
    """Condense about centre (or the origin) and shear about the x-height middle."""
    k, t = ITALIC_CONDENSE, ITALIC_SLOPE
    c = 0 if centre is None else centre * (1 - k)
    g['path'] = map_path(g['path'], lambda x, y: (round(k * x + c + t * (y - ITALIC_PIVOT)), y))
    compose(g, k, t, c - t * ITALIC_PIVOT)


def stroke(g, gx, gy, extra_x=0):
    """Per-glyph (x, y) embolden strength: the style's gain plus any compensation."""
    cx, cy = g.get('stroke_comp', (0, 0))
    return gx + cx + extra_x, gy + cy


def embolden(data, config, style, workdir, strengths):
    """Native FreeType emboldening; strengths holds one (x, y) pair per glyph.

    Returned outlines are recentred, so a stroke gain grows equally on both sides.
    """
    raw = workdir / f'{config.postscript(style)}-master.otf'
    export_font(data, raw, config, style)
    decoded = {key: extract_font(raw, embolden=key)['glyphs'] for key in set(strengths)}
    raw.unlink()
    for gid, (g, (sx, sy)) in enumerate(zip(data['glyphs'], strengths)):
        path = decoded[(sx, sy)][gid]['path']
        g['path'] = map_path(path, lambda x, y: (round(x - sx / 2), round(y - sy / 2)))
    return data


# A heavier drawing may be at most this much narrower than its emboldened outline.
NARROWEST = .75


def fit_to_weight(data, design, reference, target):
    """Draw a weight inside its reference font's spacing.

    Emboldening grows strokes outward; a drawn bold grows them inward. Each
    glyph is brought back to the width the reference bold adds over the
    reference regular (so the extra ink goes into the counters), placed where the
    reference bold places its ink, and given that font's advance and kerning.
    Returns the glyph ids fitted this way.
    """
    from .design import metric_mapping
    to_target = metric_mapping(design, target)
    to_reference = metric_mapping(design, reference)
    fitted = set()
    for gid, g in enumerate(data['glyphs']):
        if not g['advance'] or gid not in to_target:
            continue
        aim = target['glyphs'][to_target[gid]]
        g['advance'] = aim['advance']
        fitted.add(gid)
        master = design['glyphs'][gid]['path']
        if not g['path'] or not aim['box'] or not master:
            continue
        tb, b, mb = aim['box'], bbox(g['path']), bbox(master)
        rb = reference['glyphs'][to_reference[gid]]['box'] if gid in to_reference else None
        growth = (tb[2] - tb[0]) - ((rb[2] - rb[0]) if rb else (mb[2] - mb[0]))
        wanted = (mb[2] - mb[0]) + growth
        k = min(1, max(NARROWEST, wanted / max(1, b[2] - b[0])))
        offset = ((mb[0] + mb[2]) / 2 - (rb[0] + rb[2]) / 2) if rb else 0
        centre, aim_centre = (b[0] + b[2]) / 2, (tb[0] + tb[2]) / 2 + offset
        g['path'] = map_path(g['path'], lambda x, y: (round(aim_centre + (x - centre) * k), y))
        compose(g, k, 0, aim_centre - centre * k)
    data['kerning'] = remap_kerning(target['kerning'], {m: s for s, m in to_target.items()})
    return fitted


def display_style(design, config, style, workdir, weight_metrics=None):
    """weight_metrics: optional (reference regular, reference of this weight) fonts."""
    data = copy.deepcopy(design)
    data['family'] = config.family
    derived = style.italic and not design['design'].get('cursive')
    if derived:
        for g in data['glyphs']:
            if g['name'] in TABULAR:
                slant(g, g['advance'] / 2)
            else:
                slant(g)
                g['advance'] = round(g['advance'] * ITALIC_CONDENSE)
    gx, gy = stroke_gain(style, False)
    data = embolden(data, config, style, workdir, [stroke(g, gx, gy) for g in data['glyphs']])
    fitted = fit_to_weight(data, design, *weight_metrics) if weight_metrics else set()
    # Without a reference for this weight, the stem gain widens advances and the
    # optical gain tightens the fit.
    wx = WEIGHT_GAINS[style.weight][0]
    for gid, g in enumerate(data['glyphs']):
        if gid in fitted:
            continue
        if g['advance'] and g['name'] not in TABULAR:
            g['path'] = map_path(g['path'], lambda x, y: (x + wx // 2, y))
            g['advance'] += wx
            compose(g, 1, 0, wx // 2)
    # Word spaces keep the master's width (Pagella X's), widened with the weight.
    for cp in ('32', '160'):
        if cp in data['cmap'] and data['cmap'][cp] not in fitted:
            gid = data['cmap'][cp]
            space = round((design['glyphs'][gid]['advance'] + wx / 2) * (ITALIC_CONDENSE if derived else 1))
            data['glyphs'][gid]['advance'] = space
    data['design'] = dict(design['design'], family=config.family, style=style.name,
                          stroke_gain=(gx, gy))
    return data
