"""The Vespera drawing master shared by every family and style.

Letters keep the source construction with Vespera's wedge serifs, pen-cut
signature letters and lozenge dots. Punctuation and symbols keep the source
designs, which share the letters' stroke weights, with every round dot turned
into the same lozenge as i and j. The italic master changes letter structure
only (exit strokes, single-storey a); slant and weight are applied per style.
"""
from __future__ import annotations

import copy
import math
import unicodedata

from .font_io import bbox, contours, map_path, spans_at
from .glyphs import distinctive_drawings, tabularize, CONFUSABLE_TEXT
from .layout import remap_kerning
from .metrics import CAP_HEIGHT, X_HEIGHT


# Wedge serifs stay within the source's humanist, bracketed construction: a
# modest outward reach and taper, so spacing and texture remain Pagella's.
WEDGE_REACH = .05
WEDGE_TAPER = .35
WEDGE_BRACKET = 10


def reverse_contour(contour):
    """The same closed contour drawn in the opposite direction."""
    cmds = [c for c in contour if c[0] != 'Z']
    points = [c[-2:] for c in cmds]
    out = [['M', *points[-1]]]
    for k in range(len(cmds) - 1, 0, -1):
        cmd, prev = cmds[k], points[k - 1]
        out.append(['C', cmd[3], cmd[4], cmd[1], cmd[2], *prev] if cmd[0] == 'C' else ['L', *prev])
    return out + [['Z']]


def detect_serifs(path):
    """Flat serif plates, found whichever way the contour runs, so both feet of
    x, k, v... are treated alike."""
    result = []
    for contour in contours(path):
        for found in _serifs_in(contour) + _serifs_in(reverse_contour(contour)):
            if not any(abs(found[0] - r[0]) < 15 and abs(found[1] - r[1]) < 10 for r in result):
                result.append(found)
    return result


def _serifs_in(contour):
    result = []
    if True:
        for i in range(1, len(contour) - 2):
            a, b, nxt = contour[i:i + 3]
            if a[0] != "C" or b[0] != "C" or nxt[0] != "L":
                continue
            start = contour[i - 1][-2:]
            points = [start] + [a[j:j + 2] for j in (1, 3, 5)] + [b[j:j + 2] for j in (1, 3, 5)]
            xs, ys = zip(*points)
            if max(ys) - min(ys) > 8 or not 100 < max(xs) - min(xs) < 430:
                continue
            dy = nxt[2] - b[-1]
            if not 16 <= abs(dy) <= 42:
                continue
            center = a[-2]
            radius = max(abs(min(xs) - center), abs(max(xs) - center))
            result.append((center, a[-1], radius, 1 if dy > 0 else -1))
    return result


def wedge_path(path, serifs=None):
    serifs = detect_serifs(path) if serifs is None else serifs

    def wedge(x, y):
        candidate = None
        for cx, cy, r, direction in serifs:
            dx, dy = x - cx, (y - cy) * direction
            if abs(dx) > r + 5 or not -10 <= dy < 128:
                continue
            strength = max(0, 1 - max(0, dy) / 128) ** 2
            if candidate is None or strength > candidate[0]:
                tip = min(1, abs(dx) / (r * .95))
                x2 = x + dx * WEDGE_REACH * strength
                if dy > 0:
                    d2 = dy - dy * WEDGE_TAPER * tip**1.7 * strength
                    d2 += WEDGE_BRACKET * (1 - tip) * math.sin(math.pi * min(dy / 128, 1))
                else:
                    d2 = dy - 2 * tip**1.5
                candidate = (strength, x2, cy + direction * d2)
        return (candidate[1], candidate[2]) if candidate else (x, y)

    return map_path(path, wedge)


def normalized(contour):
    x, y = contour[0][1:]
    return tuple(tuple(c) for c in map_path(contour, lambda a, b: (a - x, b - y)))


def soften(changes, k):
    """Move each point only part of the way to its signature position."""
    return {src: (src[0] + (dst[0] - src[0]) * k, src[1] + (dst[1] - src[1]) * k) for src, dst in changes.items()}


def signature_drawings(source):
    byname = {g["name"]: g for g in source["glyphs"]}
    drawings = {}
    for name in "AMQaergft":
        drawings[name] = copy.deepcopy(byname[name]["path"])

    # A: an oblique crossbar, cut apex and deep, broad baseline wedges.
    changes = {(223, 229): (223, 207), (511, 229): (511, 235), (240, 269): (240, 249), (493, 269): (493, 275), (408, 700): (415, 717), (376, 700): (375, 692)}
    changes = soften(changes, .5)
    drawings["A"] = map_path(drawings["A"], lambda x, y: changes.get((x, y), (x, y)))

    # M: a low inner vertex, held by quiet upright stems.
    drawings["M"] = map_path(drawings["M"], lambda x, y: (x, -31) if (x, y) in ((436, -13), (456, -13)) else (x, y))

    # Q: the bowl is left open and broad; its tail sweeps beyond the bowl.
    q_inner = contours(drawings["Q"])[1]
    drawings["Q"] = [
        ["M", 22, 343], ["C", 22, 124, 162, -19, 377, -19],
        ["C", 331, -35, 286, -73, 254, -120], ["L", 272, -145],
        ["C", 312, -110, 336, -99, 364, -106],
        ["C", 459, -127, 601, -240, 739, -202],
        ["C", 800, -185, 846, -140, 872, -96], ["L", 851, -80],
        ["C", 808, -130, 746, -139, 684, -116],
        ["C", 566, -73, 478, -24, 401, -19],
        ["C", 480, -12, 517, -2, 569, 28], ["C", 690, 97, 764, 227, 764, 371],
        ["C", 764, 578, 622, 709, 398, 709], ["C", 174, 709, 22, 561, 22, 343], ["Z"],
    ] + q_inner

    # R keeps the source leg: its curl read as a flourish in running text.

    # a: the square source entry is replaced with a diagonal, pen-cut beak.
    a = drawings["a"]
    begin = next(i for i, c in enumerate(a) if c == ["C", 203, 469, 163, 458, 125, 435])
    end = next(i for i, c in enumerate(a) if c == ["C", 282, 416, 321, 379, 324, 288])
    drawings["a"] = a[:begin] + [
        ["C", 193, 469, 145, 451, 104, 418], ["L", 60, 357],
        ["L", 77, 318], ["L", 128, 370],
        ["C", 154, 405, 166, 416, 198, 416],
    ] + a[end:]

    # e: a clearly ascending bar, cut on the same broad-nib diagonal as a/r.
    e = drawings["e"]
    replacements = {
        (119, 230): (119, 222), (265, 230): (265, 242),
        (334, 230): (334, 254), (377, 233): (377, 267), (446, 244): (446, 281),
        (447, 258): (447, 291), (448, 267): (448, 300), (448, 279): (448, 310),
        (359, 267): (359, 302), (247, 264): (247, 280),
        (201, 264): (201, 274), (175, 265): (175, 270), (121, 270): (121, 264),
        (359, 334): (359, 351),
    }
    replacements = soften(replacements, .45)
    drawings["e"] = map_path(e, lambda x, y: replacements.get((x, y), (x, y)))

    # r: a tapering flag terminal instead of the rectangular source shoulder.
    r = drawings["r"]
    begin = next(i for i, c in enumerate(r) if c == ["C", 188, 334, 228, 384, 277, 384])
    end = next(i for i, c in enumerate(r) if c == ["L", 188, 362])
    drawings["r"] = r[:begin] + [
        ["C", 188, 340, 231, 395, 282, 393],
        ["C", 308, 391, 325, 368, 331, 338], ["L", 351, 333],
        ["L", 410, 454], ["C", 392, 476, 365, 485, 337, 479],
        ["C", 294, 472, 265, 443, 244, 418],
    ] + r[end:]

    # g: long, sharply angled ear. Double-storey structure remains legible.
    changes = soften({(519, 378): (537, 378), (544, 419): (591, 455), (540, 431): (579, 475)}, .5)
    drawings["g"] = map_path(drawings["g"], lambda x, y: changes.get((x, y), (x, y)))

    # f/t: longer ascending cross-strokes reinforce the e/g rhythm.
    changes = {(314, 385): (326, 389), (321, 438): (357, 456), (277, 435): (289, 442), (329, 634): (345, 631), (341, 640): (363, 648), (341, 717): (365, 728)}
    changes = soften(changes, .5)
    drawings["f"] = map_path(drawings["f"], lambda x, y: changes.get((x, y), (x, y)))
    changes = {(310, 382): (318, 391), (319, 436): (354, 456), (193, 610): (210, 632), (181, 621): (194, 644)}
    changes = soften(changes, .5)
    drawings["t"] = map_path(drawings["t"], lambda x, y: changes.get((x, y), (x, y)))

    # Rotated lozenge dots for i/j; punctuation uses softer, rounded ink drops.
    # The lozenge keeps the source dot's winding so emboldening grows it like any outer contour.
    for name in ("i", "j"):
        c = contours(byname[name]["path"])
        c[-1] = lozenge(bbox(c[-1]), c[-1])
        drawings[name] = [cmd for cc in c for cmd in cc]
    return drawings


def head_wedge(path):
    """Sharpen the familiar angled entry serif on a lowercase upright."""
    adjustments = []
    for cc in contours(path):
        for i, cmd in enumerate(cc[:-1]):
            if cmd[0] == "C" and cc[i + 1][0] == "L":
                endx, endy = cmd[-2:]
                nextx, nexty = cc[i + 1][-2:]
                if nextx == endx and 24 <= endy - nexty <= 30 and cmd[1] > endx + 70 and cmd[2] > endy + 10:
                    adjustments.append((endx, endy))

    def change(x, y):
        for hx, hy in adjustments:
            if hx - 1 <= x <= hx + 62 and hy - 95 <= y <= hy + 35:
                w = (1 - (x - hx) / 63) * max(0, 1 - abs(y - hy + 8) / 85)
                return x - 12 * w, y + (3 if y < hy - 10 else 8) * w
        return x, y
    return map_path(path, change)



def signed_area(contour):
    points = [c[-2:] for c in contour if c[0] != 'Z']
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1])) / 2


# Carved terminals (刀刻, 方笔): every stroke end -- a short straight face where
# the outline turns back on itself, as at serif tips, arm beaks, entry flags and
# hook ends -- is cut across obliquely, as a knife would. The outer silhouette
# edge keeps its corner; the inner corner slides back along its own edge by the
# face length times CHISEL_CUT (1.0 gives a 45-degree cut).
CHISEL_CUT = 1.0
CHISEL_FACE = (12, 70)
CHISEL_REACH = .6   # never slide further than this share of the adjacent edge


def _segments(contour):
    """(start, command) pairs for a closed contour, with the closing line explicit."""
    cmds = [c for c in contour if c[0] != 'Z']
    start = tuple(cmds[0][1:3])
    out, current = [], start
    for cmd in cmds[1:]:
        out.append((current, cmd))
        current = tuple(cmd[-2:])
    if current != start:
        out.append((current, ['L', *start]))
    return start, out


def _unit(dx, dy):
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n else (0, 0)


CARVED_CATEGORIES = ('L', 'N', 'Po', 'Mn', 'Sk', 'Ps', 'Pe', 'Pi', 'Pf')


def carved(g, chars, mapped_names):
    """Letters, figures, punctuation and accents are carved; operators, dashes and
    geometric shapes keep clean ruled ends."""
    if g['name'] in OPERATORS:
        return False
    probe = chars[0] if chars else None
    if probe is None:
        base = g['name'].split('.')[0].split('_')[0]
        probe = mapped_names.get(base) or (base if len(base) == 1 else None)
    if probe is None:
        return False
    cat = unicodedata.category(probe)
    return cat[0] in 'LN' or cat in CARVED_CATEGORIES


def chisel(path):
    out = []
    for contour in contours(path):
        start, segs = _segments(contour)
        if len(segs) < 3:
            out += contour
            continue
        area = signed_area(contour)
        segs = [[a, list(c)] for a, c in segs]
        n = len(segs)

        def tangent_in(k):
            a, c = segs[k]
            tail = c[-4:-2] if c[0] == 'C' else a
            return _unit(c[-2] - tail[0], c[-1] - tail[1])

        def tangent_out(k):
            a, c = segs[k]
            head = c[1:3] if c[0] == 'C' else c[-2:]
            return _unit(head[0] - a[0], head[1] - a[1])

        def chord(k):
            a, c = segs[k]
            return math.hypot(c[-2] - a[0], c[-1] - a[1])
        for k in range(n):
            a, c = segs[k]
            if c[0] != 'L':
                continue
            length = chord(k)
            if not CHISEL_FACE[0] <= length <= CHISEL_FACE[1]:
                continue
            face = _unit(c[1] - a[0], c[2] - a[1])
            u, v = tangent_in((k - 1) % n), tangent_out((k + 1) % n)
            if u[0] * v[0] + u[1] * v[1] > -.6:
                continue  # not a U-turn: a corner, not a stroke end
            if abs(u[0] * face[0] + u[1] * face[1]) > .8 or abs(v[0] * face[0] + v[1] * face[1]) > .8:
                continue
            turn1 = u[0] * face[1] - u[1] * face[0]
            turn2 = face[0] * v[1] - face[1] * v[0]
            if not (turn1 * turn2 > 0 and turn1 * area > 0):
                continue  # concave: a notch in the ink, not a terminal
            p0, p1 = tuple(a), tuple(c[1:3])
            keep_start = chord((k - 1) % n) >= chord((k + 1) % n)
            if keep_start:  # slide the face's end forward along the next edge
                dist = min(length * CHISEL_CUT, CHISEL_REACH * chord((k + 1) % n))
                target = (p1[0] + v[0] * dist, p1[1] + v[1] * dist)
                dx, dy = target[0] - p1[0], target[1] - p1[1]
                c[1], c[2] = target
                nxt = segs[(k + 1) % n]
                nxt[0] = target
                if nxt[1][0] == 'C':
                    nxt[1][1] += dx
                    nxt[1][2] += dy
            else:  # slide the face's start back along the previous edge
                dist = min(length * CHISEL_CUT, CHISEL_REACH * chord((k - 1) % n))
                target = (p0[0] - u[0] * dist, p0[1] - u[1] * dist)
                dx, dy = target[0] - p0[0], target[1] - p0[1]
                segs[k][0] = target
                prv = segs[(k - 1) % n]
                prv[1][-2], prv[1][-1] = target
                if prv[1][0] == 'C':
                    prv[1][3] += dx
                    prv[1][4] += dy
        first = segs[-1][1][-2:] if tuple(segs[-1][1][-2:]) == start else segs[0][0]
        rebuilt = [['M', *segs[0][0]]] + [c for _, c in segs]
        out += rebuilt + [['Z']]
    return out


def lozenge(box, clockwise_like):
    """The i/j dot: a lozenge on the pen diagonal, fitted to a source dot's box."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hw, hh = (x1 - x0) / 2 * 1.02, (y1 - y0) / 2 * 1.11
    points = [(-1, -.207), (-.157, 1), (1, .207), (.157, -1)]
    points = [(cx + px * hw, cy + py * hh) for px, py in points]
    if (signed_area([['M', *points[0]]] + [['L', *p] for p in points[1:]]) > 0) != (signed_area(clockwise_like) > 0):
        points.reverse()
    # Softened corners echo the source's rounded terminals; the pen diagonal stays.
    cut = .2
    path = []
    for i, (x, y) in enumerate(points):
        (px, py), (nx, ny) = points[i - 1], points[(i + 1) % 4]
        a = (x + (px - x) * cut, y + (py - y) * cut)
        b = (x + (nx - x) * cut, y + (ny - y) * cut)
        path.append(['M' if i == 0 else 'L', round(a[0]), round(a[1])])
        path.append(['C', round(a[0] + (x - a[0]) * .55), round(a[1] + (y - a[1]) * .55),
                     round(b[0] + (x - b[0]) * .55), round(b[1] + (y - b[1]) * .55), round(b[0]), round(b[1])])
    return path + [['L', *path[0][1:]], ['Z']]


def round_dots(path):
    """Replace free-standing round dots (period, colon, ellipsis, middle dot...) with lozenges."""
    cc = contours(path)
    boxes = [bbox(c) for c in cc]
    out = []
    for i, (c, b) in enumerate(zip(cc, boxes)):
        w, h = b[2] - b[0], b[3] - b[1]
        curves = [cmd for cmd in c if cmd[0] == 'C']
        enclosed = any(j != i and o[0] <= b[0] and o[1] <= b[1] and o[2] >= b[2] and o[3] >= b[3]
                       for j, o in enumerate(boxes))
        if len(curves) == 4 and len(c) <= 7 and 60 <= w <= 170 and abs(w - h) <= 12 and not enclosed:
            out += lozenge(b, c)
        else:
            out += c
    return out


OPERATORS = ('plus', 'minus', 'equal', 'less', 'greater', 'plusminus', 'multiply', 'divide',
             'notequal', 'lessequal', 'greaterequal', 'approxequal', 'logicalnot', 'equivalence')
OPERATOR_SCALE = .8
OPERATOR_STROKE = 12
MATH_AXIS = 250

ITALIC_EXIT = set('adhimnu\u0131')


def italic_exit(path, serifs):
    """Italic structure from the roman: the last baseline serif becomes a rising
    exit stroke, earlier ones shrink to small spurs; stems are untouched."""
    feet = sorted(s for s in serifs if abs(s[1]) < 25 and s[3] == 1)
    if not feet:
        return path
    half = 46
    exit_serif = feet[-1]

    def change(x, y):
        for serif in feet:
            cx, cy, r, _ = serif
            d = x - cx
            # Wedge serifs already reach about 40% beyond the detected radius.
            span = r * 1.45 + 8
            if abs(d) > span or not cy - 20 <= y <= cy + 90:
                continue
            weight = 1 if y <= cy + 45 else max(0, 1 - (y - cy - 45) / 45)
            excess = max(0, abs(d) - half)
            if serif is exit_serif and d > 0:
                # The lift starts at the stem axis, so the foot turns up in one curve.
                reach = min(1, d / span)
                return x + excess * .4 * weight, y + weight * 120 * reach ** 2.2
            if abs(d) <= half:
                return x, y
            return cx + math.copysign(half + excess * (1 - .82 * weight), d), y
        return x, y
    return map_path(path, change)


def single_storey_drawings(source):
    """Simplified structures: single-storey a and g.

    a is d with its ascender folded down to the x-height; g is q's bowl and stem
    carried into j's descender hook (both stems are 84 units wide, so the join is
    seamless) in place of q's foot serif.
    """
    byname = {g['name']: g for g in source['glyphs']}
    d = copy.deepcopy(byname['d']['path'])

    # The ascender folds into a clean, pen-cut stem top: the source flag serif is
    # drawn into the stem and the top is cut rising to the right.
    stem_left, stem_right = spans_at(d, 600)[0]

    # d's bowl meets its stem at y=437, below the new stem top; raise that join so
    # the bowl's top hairline runs flush into the stem instead of leaving a notch.
    join = {(412, 437): (412, 460), (356, 461): (372, 469)}

    def fold(x, y):
        x, y = join.get((x, y), (x, y))
        if y > 480:  # the ascender only; the bowl joins the stem lower down
            x = min(max(x, stem_left), stem_right)
            y = 470 + 24 * (x - stem_left) / (stem_right - stem_left)
        return 35 + (x - 35) * .86, y
    q_outer, q_counter = contours(byname['q']['path'])
    j_body = contours(byname['j']['path'])[0]
    begin = q_outer.index(['L', 393, 66]) + 1
    end = q_outer.index(['L', 477, 318])
    assert j_body[0] == ['M', -40, -245] and j_body[10] == ['L', 75, -7]
    dx = 393 - 75
    tail = map_path(j_body[11:13] + [['L', *j_body[1][1:]]] + j_body[2:4], lambda x, y: (x + dx, y))
    g_outer = q_outer[:begin] + [['L', 393, -7]] + tail + q_outer[end:]
    return {'a': map_path(d, fold), 'g': g_outer + q_counter}


def geometric_glyphs(source):
    """Coverage additions drawn in the source's geometric-shape proportions."""
    byname = {g['name']: g for g in source['glyphs']}
    box = byname['filledbox']['path']
    outer = contours(box)[0]
    hollow = contours(byname['H22073']['path'])
    rim = bbox(hollow[1])[0] - bbox(hollow[0])[0]
    x0, y0, x1, y1 = bbox(outer)
    cx, cy, half = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * 1.1

    def diamond(h, like):
        pts = [(cx - h, cy), (cx, cy + h), (cx + h, cy), (cx, cy - h)]
        pts = [(round(x), round(y)) for x, y in pts]
        path = [['M', *pts[0]]] + [['L', *p] for p in pts[1:]] + [['L', *pts[0]], ['Z']]
        return path if (signed_area(path) > 0) == (signed_area(like) > 0) else \
            [['M', *pts[0]]] + [['L', *p] for p in reversed(pts[1:])] + [['L', *pts[0]], ['Z']]
    advance = byname['filledbox']['advance']
    filled = diamond(half, outer)
    open_ = diamond(half, hollow[0]) + diamond(half - rim * math.sqrt(2), hollow[1])
    return {0x25C6: ('uni25C6', filled, advance), 0x25C7: ('uni25C7', open_, advance)}


def metric_mapping(source, metrics):
    """Source glyph id -> metrics-font glyph id, by Unicode first and then by name."""
    names = {g['name']: i for i, g in enumerate(metrics['glyphs'])}
    mapping = {gid: metrics['cmap'][cp] for cp, gid in source['cmap'].items() if cp in metrics['cmap']}
    for gid, g in enumerate(source['glyphs']):
        if gid not in mapping and g['name'] in names:
            mapping[gid] = names[g['name']]
    return mapping


def fit_width(path, width):
    """Bring a redrawn letter back inside a given ink width by shortening what
    reaches beyond its outer strokes (hooks, flags, bars); stems keep their weight."""
    x0, y0, x1, y1 = bbox(path)
    excess = (x1 - x0) - width
    if excess <= 0:
        return path
    spans = spans_at(path, y0 + (y1 - y0) * .45) or [((x0 + x1) / 2, (x0 + x1) / 2)]
    L, R = spans[0][0], spans[-1][1]
    overhang = (L - x0) + (x1 - R)
    f = max(.25, 1 - excess / overhang) if overhang > 0 else 1
    path = map_path(path, lambda x, y: (L - (L - x) * f if x < L else R + (x - R) * f if x > R else x, y))
    x0, _, x1, _ = bbox(path)
    if x1 - x0 > width + 1:  # still too wide: condense the remainder evenly
        k, c = width / (x1 - x0), (x0 + x1) / 2
        path = map_path(path, lambda x, y: (c + (x - c) * k, y))
    return path


# Wei Bei movement (斜画紧结, 纵横欹斜): horizontals rise to the right while
# verticals stay upright and the baseline stays flat; the middle of each letter
# lifts so crossbars sit high and upper counters close up.
WEIBEI_RISE = .075     # slope of horizontals, about 4.3 degrees
WEIBEI_LIFT = .045     # mid-height lift, as a share of the letter's height
WEIBEI_LETTERS = ('L', 'N')


def weibei(path, height):
    x0, _, x1, _ = bbox(path)
    cx = (x0 + x1) / 2

    def move(x, y):
        t = min(1, max(0, y / (.6 * height)))
        rise = WEIBEI_RISE * (x - cx) * t * t * (3 - 2 * t)
        lift = WEIBEI_LIFT * height * math.sin(math.pi * y / height) if 0 < y < height else 0
        return x, y + rise + lift
    return map_path(path, move)


def glyph_kind(g, chars, mapped_names):
    """'upper', 'lower' or None (punctuation, symbols, marks keep their axes)."""
    probe = chars[0] if chars else None
    if probe is None:
        base = g['name'].split('.')[0].split('_')[0]
        probe = mapped_names.get(base)
        if probe is None and len(base) == 1:
            probe = base
    if not probe or unicodedata.category(probe)[0] not in WEIBEI_LETTERS:
        return None
    return 'upper' if unicodedata.category(probe) in ('Lu', 'Lt', 'Nd') else 'lower'


# Flourishes for the true italic: longer entry and exit strokes on the
# lowercase, and a sweeping swash foot on A, M and N.
ENTRY_EXIT = 1.35
SWASH_CAPITALS = 'AMN'
SWASH_REACH = 2.6
SWASH_CURL = 95


def flourish(path, base):
    if not path:
        return path
    x0, y0, x1, y1 = bbox(path)
    if base.islower():
        spans = spans_at(path, X_HEIGHT * .45)
        if not spans:
            return path
        L, R = spans[0][0], spans[-1][1]

        def stretch(x, y):
            if x > R and -30 <= y < .3 * X_HEIGHT:
                return R + (x - R) * ENTRY_EXIT, y
            if x < L and y > .65 * X_HEIGHT:
                return L - (L - x) * ENTRY_EXIT, y
            return x, y
        return map_path(path, stretch)
    if base in SWASH_CAPITALS:
        spans = spans_at(path, 75)
        if not spans:
            return path
        slope = math.tan(math.radians(10))
        # The stem leans: its left edge at height y lies slope * (75 - y) further left.
        edge = lambda y: spans[0][0] - slope * (75 - y)
        points = [(c[i], c[i + 1]) for c in path for i in range(1, len(c), 2)]
        reach = max([1] + [edge(y) - 4 - x for x, y in points if y < 70])

        def swash(x, y):
            L = edge(y) - 4
            if x < L and y < 70:
                t = min(1, (L - x) / reach)
                return L - (L - x) * SWASH_REACH, y + SWASH_CURL * t * t
            return x, y
        return map_path(path, swash)
    return path


# Letters whose signature extends past the source width on purpose.
OVERHANG = {'Q'}


def build_design(source, italic=False, metrics=None, cursive=False):
    """The drawing master. With a metrics font, every glyph it shares takes that
    font's advance, and its ink is placed on that font's ink: spacing and kerning
    are the metrics font's, only the drawing changes."""
    if cursive:
        # A true italic source: its letters are used as drawn; only the generic
        # treatments below (wedges, lozenge dots, Wei Bei, flourishes) apply.
        drawings = {}
    else:
        drawings = signature_drawings(source)
        drawings.update(distinctive_drawings(source))
        drawings.update(single_storey_drawings(source))
    byname = {g["name"]: g for g in source["glyphs"]}
    reverse = {}
    for cp, gid in source['cmap'].items():
        reverse.setdefault(gid, []).append(chr(int(cp)))
    replacements = {}
    full_replacements = {}
    for name, drawn in drawings.items():
        original_contours = contours(byname[name]["path"])
        drawn_contours = contours(drawn)
        if len(original_contours) != len(drawn_contours):
            # Replace the whole contour group wherever it occurs (g, ğ, ĝ, ģ...).
            full_replacements[tuple(sorted(normalized(c) for c in original_contours))] = (
                normalized(original_contours[0]), original_contours[0][0][1:], drawn)
            continue
        for original, replacement in zip(original_contours, drawn_contours):
            if original == replacement:
                continue
            replacements[normalized(original)] = (original[0][1:], replacement)

    mapping = metric_mapping(source, metrics) if metrics else {}
    mapped_names = {source['glyphs'][gid]['name']: chars[0] for gid, chars in reverse.items()}
    if metrics:
        result_kerning = remap_kerning(metrics['kerning'],
                                       {m: s for s, m in mapping.items()})
    result = copy.deepcopy(source)
    signature_count = 0
    total_serifs = 0
    for gid, (g, old) in enumerate(zip(result["glyphs"], source["glyphs"])):
        rebuilt, substituted = [], False
        own = contours(g['path'])
        keys = [normalized(cc) for cc in own]
        group = None
        for wanted, (first_key, origin, replacement) in full_replacements.items():
            remaining = list(keys)
            if all(k in remaining and not remaining.remove(k) for k in wanted):
                group = (wanted, first_key, origin, replacement)
                break
        for cc, key in zip(own, keys):
            if group and key in group[0]:
                continue
            if key in replacements:
                origin, replacement = replacements[key]
                dx, dy = cc[0][1] - origin[0], cc[0][2] - origin[1]
                rebuilt += map_path(replacement, lambda x, y: (x + dx, y + dy))
                substituted = True
            else:
                rebuilt += cc
        if group:
            wanted, first_key, origin, replacement = group
            anchor = own[keys.index(first_key)][0][1:]
            dx, dy = anchor[0] - origin[0], anchor[1] - origin[1]
            rebuilt = map_path(replacement, lambda x, y: (x + dx, y + dy)) + rebuilt
            substituted = True
        if g['name'] == 'zero.slash' and 'zero' in drawings:
            rebuilt = copy.deepcopy(drawings['zero'])
        if cursive and g['name'] == 'zero' and 'zero.slash' in byname:
            rebuilt = copy.deepcopy(byname['zero.slash']['path'])  # slashed by default, as in the roman
        if substituted:
            signature_count += 1
        if g['name'] in OPERATORS:
            # Source operators are sized for mathematics; text, headlines and code
            # want them nearer the lowercase. The embolden pass restores the stroke.
            x0, _, x1, _ = bbox(rebuilt)
            cx = (x0 + x1) / 2
            rebuilt = map_path(rebuilt, lambda x, y: (cx + (x - cx) * OPERATOR_SCALE,
                                                      MATH_AXIS + (y - MATH_AXIS) * OPERATOR_SCALE))
            g['stroke_comp'] = (OPERATOR_STROKE, OPERATOR_STROKE)
        target = metrics['glyphs'][mapping[gid]] if gid in mapping and g['advance'] else None
        target_box = target['box'] if target else None
        if target_box and g['name'] not in OVERHANG:
            rebuilt = fit_width(rebuilt, target_box[2] - target_box[0] + 4)
        drawn_box = bbox(rebuilt) if rebuilt else (0, 0, 0, 0)
        serifs = detect_serifs(rebuilt)
        total_serifs += len(serifs)
        rebuilt = head_wedge(wedge_path(rebuilt, serifs))
        if carved(g, reverse.get(gid, []), mapped_names):
            rebuilt = chisel(rebuilt)
        rebuilt = round_dots(rebuilt)
        chars = reverse.get(gid, [])
        base = unicodedata.normalize('NFD', chars[0])[0] if chars else ''
        if cursive and base:
            rebuilt = flourish(rebuilt, base)
        elif italic and base in ITALIC_EXIT:
            rebuilt = italic_exit(rebuilt, serifs)
        kind = glyph_kind(g, chars, mapped_names) if g['advance'] and rebuilt else None
        if kind:
            rebuilt = weibei(rebuilt, CAP_HEIGHT if kind == 'upper' else X_HEIGHT)

        is_mark = g["advance"] == 0
        if target is not None:
            # The metrics font's advance; the drawing sits where its ink sits.
            if target_box is None:
                shift = 0
            elif g['name'] in OVERHANG:
                shift = target_box[0] - drawn_box[0]
            else:
                shift = (target_box[0] + target_box[2]) / 2 - (drawn_box[0] + drawn_box[2]) / 2
            advance = target['advance']
        else:
            # Without a counterpart, keep the source advance; widen only where a
            # redrawn letter needs room, never for serif tips.
            old_box, new_box = bbox(old["path"]), drawn_box
            left = max(0, old_box[0] - new_box[0])
            right = max(0, new_box[2] - old_box[2])
            shift = 0 if is_mark else left
            advance = g["advance"] + (0 if is_mark else left + right)
        g["path"] = map_path(rebuilt, lambda x, y: (round(x + shift), round(y)))
        g["advance"] = round(advance)
        g["left_shift"] = round(shift)
    if metrics is None:
        tabularize(result['glyphs'])
    for cp, (name, path, advance) in geometric_glyphs(source).items():
        if str(cp) not in result['cmap']:
            result['cmap'][str(cp)] = len(result['glyphs'])
            result['glyphs'].append({'name': name, 'advance': advance, 'path': path, 'left_shift': 0})
    for g in result['glyphs']:
        g['anchor'] = (1, 0, g['left_shift'])
    changes = [g['name'] for g, old in zip(result['glyphs'], source['glyphs']) if g['path'] != old['path'] or g['advance'] != old['advance']]
    if metrics:
        result['kerning'] = result_kerning
    result["design"] = {"source": source.get('family', 'TeX Gyre Pagella'), "italic": italic, "cursive": cursive,
                        "metrics": "TeX Gyre Pagella X (newpx)" if metrics else None,
                        "weibei": {"rise": WEIBEI_RISE, "lift": WEIBEI_LIFT},
                        "modified_glyphs": len(changes), "signature_variants": signature_count,
                        "wedge_serifs": total_serifs, "custom_letters": list(drawings),
                        "confusable_text": CONFUSABLE_TEXT}
    return result
