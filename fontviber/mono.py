"""Vespera Mono: the Display master refitted to a 640-unit cell.

Letters, punctuation, serifs and dots are the Display drawings. Only widths
change: wide glyphs are condensed and their stems re-thickened to the family
weight, narrow stem letters get longer serifs, and every glyph is centred.
"""
from __future__ import annotations

import copy
import unicodedata

from .font_io import bbox, contours, map_path, spans_at
from .metrics import (CELL, ITALIC_CONDENSE, ITALIC_SLOPE, MONO_INK, OPTICS, X_HEIGHT,
                      compose, stroke_gain)
from .mono_glyphs import terminal_drawings
from .styles import embolden, slant, stroke

# Widest ink before emboldening, relative to the stroke gain still to come.
INK_LIMIT = 580
# Stem thickness lost to condensing (source stems are about 95 units) and the
# share restored: crowded letters such as m and W stay slightly lighter, as in
# most monospaced faces, so their counters stay open.
STEM = 90
RESTORE = .75
# Narrow stem letters: target ink width reached by lengthening their serifs.
SERIF_TARGETS = {**dict.fromkeys('iljIıȷ', 400), **dict.fromkeys('ftr', 430)}
MARGIN = 6
# Dashes reach across the cell so -> and -- read as continuous strokes.
RULE_TARGETS = {'hyphen': 400, 'uni00AD': 400, 'endash': 560}


def stem_span(path, y):
    """The widest dark run crossing height y: the letter's main stem."""
    spans = spans_at(path, y)
    return max(spans, key=lambda s: s[1] - s[0]) if spans else None


def retract_serifs(path, width_wanted):
    """Shorten serifs outside the outer vertical stems before any condensing.

    Only the baseline and top serif zones move, so bowls, arms and diagonals keep
    their drawing; serifs keep at least 45% of their length.
    """
    x0, y0, x1, y1 = bbox(path)
    top = y1
    rows = [spans_at(path, y0 + (y1 - y0) * f) for f in (.3, .5, .7)]
    if not all(rows):
        return path
    left = [r[0][0] for r in rows]
    right = [r[-1][1] for r in rows]
    if max(left) - min(left) > 12 or max(right) - min(right) > 12:
        return path  # outer strokes are not vertical stems
    L, R = max(left), min(right)
    overhang = (L - x0) + (x1 - R)
    if overhang <= 0:
        return path
    f = max(.45, 1 - ((x1 - x0) - width_wanted) / overhang)
    if f >= 1:
        return path

    def pull(x, y):
        if y > y0 + 80 and y < top - 80:
            return x, y
        if x < L:
            return L - (L - x) * f, y
        if x > R:
            return R + (x - R) * f, y
        return x, y
    return map_path(path, pull)


def stretch_rule(path, target):
    """Lengthen a horizontal rule from its middle; thickness and end cuts are kept."""
    x0, _, x1, _ = bbox(path)
    extra = (target - (x1 - x0)) / 2
    if extra <= 0:
        return path
    mid = (x0 + x1) / 2
    return map_path(path, lambda x, y: (x + extra if x > mid else x - extra, y))


def extend_serifs(path, base, target):
    """Lengthen serifs, flags and bars outward from the stem; stems keep their weight."""
    x0, _, x1, _ = bbox(path)
    extra = min(115, (target - (x1 - x0)) / 2)
    span = stem_span(path, 350 if base.isupper() else 250)
    if extra <= 0 or span is None:
        return path
    left, right = span

    def push(x, y):
        if x < left:
            return x - extra * min(1, (left - x) / 30), y
        if x > right:
            return x + extra * min(1, (x - right) / 30), y
        return x, y
    out = []
    for contour in contours(path):
        # Dots and accents above the body stay as drawn.
        out += contour if bbox(contour)[1] > .75 * X_HEIGHT else map_path(contour, push)
    return out


def adapt_monospace(design, config, style, workdir):
    data = copy.deepcopy(design)
    data['family'] = config.family
    gx, gy = stroke_gain(style, True)
    limit = INK_LIMIT - max(0, gx)
    # A true italic master is already slanted; only a derived italic is sheared here.
    shear = style.italic and not design['design'].get('cursive')
    reverse = {}
    for cp, gid in design['cmap'].items():
        reverse.setdefault(gid, []).append(chr(int(cp)))
    strengths, condensed, extended = [], 0, 0
    for gid, g in enumerate(data['glyphs']):
        chars = reverse.get(gid, [])
        base = unicodedata.normalize('NFD', chars[0])[0] if chars else ''
        zero = g['advance'] == 0 or any(unicodedata.category(ch) in ('Mn', 'Me', 'Cf') for ch in chars)
        g['advance'] = 0 if zero else CELL
        compensation, fit = 0, 1
        if base == 'Q':  # keep the long display tail inside the code line
            g['path'] = map_path(g['path'], lambda x, y: (x, y * .55 if y < 0 else y))
        if g['path']:
            # Cursive letters already reach out with entry and exit strokes.
            if base in SERIF_TARGETS and not zero and not design['design'].get('cursive'):
                before = bbox(g['path'])
                g['path'] = extend_serifs(g['path'], base, SERIF_TARGETS[base])
                extended += bbox(g['path']) != before
            if g['name'] in RULE_TARGETS:
                g['path'] = stretch_rule(g['path'], RULE_TARGETS[g['name']])
            x0, y0, x1, y1 = bbox(g['path'])
            allowed = limit
            if shear and not zero:
                # Reserve only the overhang this glyph's slant really adds.
                k, t = ITALIC_CONDENSE, ITALIC_SLOPE
                sx0, _, sx1, _ = bbox(map_path(g['path'], lambda x, y: (k * x + t * y, y)))
                allowed = (limit - ((sx1 - sx0) - k * (x1 - x0))) / k
            if not zero and x1 - x0 > allowed:
                g['path'] = retract_serifs(g['path'], allowed)
                x0, y0, x1, y1 = bbox(g['path'])
            width = x1 - x0
            if zero:
                # Wide accents (double acute, caron) stay inside the cell at every weight.
                s = min(1, (400 - max(0, gx)) / width) if width else 1
                g['path'] = map_path(g['path'], lambda x, y: (round(x * s), y))
                compose(g, s, 0, 0)
            else:
                # Fit upright first so every glyph keeps the full italic angle;
                # italic glyphs reserve the width their slant will add.
                s = 1
                if width > allowed:
                    # Condense, then restore stem weight with horizontal-only emboldening.
                    s = (allowed - STEM) / (width - STEM)
                    compensation = 4 * round((1 - s) * STEM * RESTORE / 4)
                    condensed += 1
                    fit = s
                centre = (x0 + x1) / 2
                dx = CELL / 2 - centre * s
                g['path'] = map_path(g['path'], lambda x, y: (round(x * s + dx), y))
                compose(g, s, 0, dx)
            if shear:
                slant(g, None if zero else CELL / 2)
                if not zero:
                    x0, _, x1, _ = bbox(g['path'])
                    shift = round(CELL / 2 - (x0 + x1) / 2)
                    g['path'] = map_path(g['path'], lambda x, y: (x + shift, y))
                    compose(g, 1, 0, shift)
        # A condensed glyph also takes a proportional share of the weight gain, so
        # three-stem letters (m, M, W, w) keep open counters in Bold.
        strengths.append(stroke(g, round(gx * fit), gy, compensation))
    data = embolden(data, config, style, workdir, strengths)
    # Final guard: slanted or heavy outlines stay inside the cell.
    for g in data['glyphs']:
        if not g['advance'] or not g['path']:
            continue
        x0, _, x1, _ = bbox(g['path'])
        if x0 < MARGIN or x1 > CELL - MARGIN:
            f = min((CELL / 2 - MARGIN) / (CELL / 2 - x0), (CELL / 2 - MARGIN) / (x1 - CELL / 2))
            g['path'] = map_path(g['path'], lambda x, y: (round(CELL / 2 + (x - CELL / 2) * f), y))
            compose(g, f, 0, CELL / 2 * (1 - f))
    light = round(46 + .45 * (gx - OPTICS[0] - MONO_INK[0]))
    terminal = terminal_drawings(light)
    for cp, path in terminal.items():
        key = str(cp)
        if key in data['cmap']:
            g = data['glyphs'][data['cmap'][key]]
        else:
            g = {'name': f'uni{cp:04X}', 'advance': CELL, 'left_shift': 0}
            data['cmap'][key] = len(data['glyphs'])
            data['glyphs'].append(g)
        g['path'] = map_path(path, lambda x, y: (round(x), round(y)))
        g['anchor'] = (1, 0, 0)
    data['design'] = dict(design['design'], family=config.family, version=config.version,
                          style=style.name, cell_advance=CELL, x_height=X_HEIGHT,
                          stroke_gain=(gx, gy), condensed_glyphs=condensed,
                          extended_serifs=extended, terminal_codepoints=sorted(terminal),
                          box_line_weight=light, glyphs=len(data['glyphs']),
                          mapped_codepoints=len(data['cmap']), layout_features=['ccmp', 'mark', 'mkmk'],
                          source_sha256=config.source_sha256)
    return data
