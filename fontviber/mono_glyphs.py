"""Terminal glyphs for the 640-unit cell: box drawing, block elements, Powerline."""
from __future__ import annotations

import unicodedata

from .metrics import ASCENT, CELL, DESCENT

MID = (ASCENT + DESCENT) / 2
C = CELL / 2
K = .5523  # cubic approximation of a quarter circle


def polygon(points):
    # Clockwise contours keep overlapping strokes filled in CFF / nonzero fill.
    area = sum(x * yy - xx * y for (x, y), (xx, yy) in zip(points, points[1:] + points[:1]))
    if area > 0:
        points = list(reversed(points))
    return [['M', *points[0]]] + [['L', *p] for p in points[1:]] + [['Z']]


def rect(x0, y0, x1, y1):
    return polygon([(x0, y0), (x0, y1), (x1, y1), (x1, y0)])


def lines(weights):
    """Light and heavy arms, each with its own weight ({'L': 46, 'D': 85, ...}).

    An arm runs on past the centre across the perpendicular arms, so corners and
    tees close cleanly; with no perpendicular arm it runs into the opposite arm
    only when that one is at least as heavy, so a heavy arm never pokes out of a
    light one.
    """
    across = {axis: max((weights[a] for a in axis if a in weights), default=0) for axis in ('LR', 'UD')}
    out = []
    for arm, w in weights.items():
        axis, other = ('LR', 'UD') if arm in 'LR' else ('UD', 'LR')
        opposite = weights.get(axis.replace(arm, ''), 0)
        reach = across[other] / 2 if across[other] else (opposite / 2 if opposite >= w else 0)
        if arm == 'L':
            out += rect(0, MID - w / 2, C + reach, MID + w / 2)
        elif arm == 'R':
            out += rect(C - reach, MID - w / 2, CELL, MID + w / 2)
        elif arm == 'D':
            out += rect(C - w / 2, DESCENT, C + w / 2, MID + reach)
        else:
            out += rect(C - w / 2, MID - reach, C + w / 2, ASCENT)
    return out


def double(arms, weight):
    """Two parallel lines per arm; a line is cut where a perpendicular arm on its side
    passes, and otherwise runs on to meet the far line of the other arm."""
    o, h = weight * 1.4, weight / 2
    out = []
    for horizontal in (True, False):
        before, after = ('L', 'R') if horizontal else ('D', 'U')
        for sign in (1, -1):
            same = ('U' if sign > 0 else 'D') if horizontal else ('R' if sign > 0 else 'L')
            other = ('D' if sign > 0 else 'U') if horizontal else ('L' if sign > 0 else 'R')
            centre, low, high = (C, 0, CELL) if horizontal else (MID, DESCENT, ASCENT)
            spans = []
            if same in arms:
                if before in arms:
                    spans.append((low, centre - o + h))
                if after in arms:
                    spans.append((centre + o - h, high))
            elif before in arms and after in arms:
                spans.append((low, high))
            else:
                reach = o + h if other in arms else 0
                if before in arms:
                    spans.append((low, centre + reach))
                if after in arms:
                    spans.append((centre - reach, high))
            line = (MID if horizontal else C) + sign * o
            for a, b in spans:
                out += rect(a, line - h, b, line + h) if horizontal else rect(line - h, a, line + h, b)
    return out


def single_double(arms, doubled, weight):
    """One axis drawn double, the other single (╒ ╞ ╪ ...). The double lines start at
    the single line; a single arm reaches the far double line at a corner and the
    near one at a tee."""
    o, h = weight * 1.4, weight / 2
    if doubled == 'LR':
        seg = lambda a, b, pos: rect(a, pos - h, b, pos + h)
        double_range, centre, single_range, line = (0, CELL), C, (DESCENT, ASCENT), MID
        single_axis = 'DU'
    else:
        seg = lambda a, b, pos: rect(pos - h, a, pos + h, b)
        double_range, centre, single_range, line = (DESCENT, ASCENT), MID, (0, CELL), C
        single_axis = 'LR'
        doubled = 'DU'
    before, after = (a in arms for a in doubled)
    corner = before != after
    a, b = (double_range[0] if before else centre - h), (double_range[1] if after else centre + h)
    out = seg(a, b, line - o) + seg(a, b, line + o)
    low, high = (a in arms for a in single_axis)
    if low and high:
        span = single_range
    elif low:
        span = (single_range[0], (line + o + h) if corner else (line - o + h))
    else:
        span = ((line - o - h) if corner else (line + o - h), single_range[1])
    pos = centre
    return out + (rect(span[0], pos - h, span[1], pos + h) if doubled == 'DU' else rect(pos - h, span[0], pos + h, span[1]))


def diagonal(rising, weight):
    """Corner to corner of the cell, weight measured across the stroke."""
    height = ASCENT - DESCENT
    dx = weight * (CELL ** 2 + height ** 2) ** .5 / height
    if rising:
        return polygon([(0, DESCENT), (dx, DESCENT), (CELL, ASCENT), (CELL - dx, ASCENT)])
    return polygon([(0, ASCENT), (CELL - dx, DESCENT), (CELL, DESCENT), (dx, ASCENT)])


KINDS = ('LIGHT', 'HEAVY', 'SINGLE', 'DOUBLE')
DIRECTIONS = {'LEFT': 'L', 'RIGHT': 'R', 'UP': 'U', 'DOWN': 'D', 'HORIZONTAL': 'LR', 'VERTICAL': 'UD'}


def line_arms(cp):
    """Arms and their kind from the Unicode name, e.g. 'DOWN LIGHT AND RIGHT HEAVY'
    -> {'D': 'LIGHT', 'R': 'HEAVY'}; None for dashes, arcs and diagonals."""
    name = unicodedata.name(chr(cp)).removeprefix('BOX DRAWINGS ')
    if any(word in name for word in ('DASH', 'ARC', 'DIAGONAL')):
        return None
    parts = []
    for part in name.split(' AND '):
        words = part.split()
        assert all(w in KINDS or w in DIRECTIONS for w in words), name
        kind = next((w for w in words if w in KINDS), None)
        parts.append((kind, ''.join(DIRECTIONS[w] for w in words if w in DIRECTIONS)))
    given = {kind for kind, _ in parts if kind}
    assert len(given) == 1 or all(kind for kind, _ in parts), name
    return {arm: kind or next(iter(given)) for kind, arms in parts for arm in arms}


def rounded(weight, radius=C * .78):
    """A light arc from the right arm down to the lower arm; mirrored for the others."""
    cx, cy = C + radius, MID - radius
    ro, ri = radius + weight / 2, radius - weight / 2
    path = [['M', CELL, MID + weight / 2], ['L', cx, MID + weight / 2],
            ['C', cx - ro * K, cy + ro, cx - ro, cy + ro * K, cx - ro, cy],
            ['L', C - weight / 2, DESCENT], ['L', C + weight / 2, DESCENT], ['L', cx - ri, cy],
            ['C', cx - ri, cy + ri * K, cx - ri * K, cy + ri, cx, cy + ri],
            ['L', CELL, MID - weight / 2], ['Z']]
    return path


def mirror(path, flip_x, flip_y):
    out = [[c[0]] + [v for i in range(1, len(c), 2)
                      for v in ((CELL - c[i] if flip_x else c[i]),
                                (ASCENT + DESCENT - c[i + 1] if flip_y else c[i + 1]))] for c in path]
    if flip_x != flip_y:  # reflection reverses winding
        pts = [c for c in out if c[0] != 'Z']
        rev = [['M', *pts[-1][-2:]]]
        for prev, cmd in zip(reversed(pts[:-1]), reversed(pts[1:])):
            if cmd[0] == 'C':
                rev.append(['C', cmd[3], cmd[4], cmd[1], cmd[2], *prev[-2:]])
            else:
                rev.append(['L', *prev[-2:]])
        out = rev + [['Z']]
    return out


def dashed(horizontal, count, weight):
    out = []
    span = (CELL if horizontal else ASCENT - DESCENT) / count
    gap = span * .3
    for i in range(count):
        a = i * span + gap / 2
        b = a + span - gap
        if horizontal:
            out += rect(a, MID - weight / 2, b, MID + weight / 2)
        else:
            out += rect(C - weight / 2, DESCENT + a, C + weight / 2, DESCENT + b)
    return out


def terminal_drawings(light):
    """All 128 box-drawing characters, all 32 block elements and Powerline separators.

    Line weights follow the font weight so frames sit with the text around them.
    """
    heavy = round(light * 1.85)
    d = {}
    # Every line character of U+2500-257F, read from its Unicode name.
    for cp in range(0x2500, 0x2580):
        arms = line_arms(cp)
        if arms is None:
            continue
        kinds = set(arms.values())
        if 'DOUBLE' not in kinds:
            d[cp] = lines({arm: heavy if kind == 'HEAVY' else light for arm, kind in arms.items()})
        elif kinds == {'DOUBLE'}:
            d[cp] = double(''.join(arms), light)
        else:
            d[cp] = single_double(''.join(arms), 'LR' if arms.get('L', arms.get('R')) == 'DOUBLE' else 'UD', light)
    d[0x2571] = diagonal(True, light)
    d[0x2572] = diagonal(False, light)
    d[0x2573] = diagonal(True, light) + diagonal(False, light)
    arc = rounded(light)
    d[ord('╭')] = arc
    d[ord('╮')] = mirror(arc, True, False)
    d[ord('╯')] = mirror(arc, True, True)
    d[ord('╰')] = mirror(arc, False, True)
    for ch, (horizontal, count, weight) in zip('┄┅┆┇┈┉┊┋╌╍╎╏', [
            (True, 3, light), (True, 3, heavy), (False, 3, light), (False, 3, heavy),
            (True, 4, light), (True, 4, heavy), (False, 4, light), (False, 4, heavy),
            (True, 2, light), (True, 2, heavy), (False, 2, light), (False, 2, heavy)]):
        d[ord(ch)] = dashed(horizontal, count, weight)
    # Continuous underscore; its width exactly matches its advance.
    d[ord('_')] = rect(0, -100 - light / 2, CELL, -100 + light / 2 + 4)
    h = ASCENT - DESCENT
    d[0x2580] = rect(0, MID, CELL, ASCENT)
    for i in range(1, 9):
        d[0x2580 + i] = rect(0, DESCENT, CELL, DESCENT + h * i / 8)
    for i in range(1, 8):
        d[0x2588 + i] = rect(0, DESCENT, CELL * (8 - i) / 8, ASCENT)
    d[0x2590] = rect(C, DESCENT, CELL, ASCENT)
    for cp, modulus in [(0x2591, 4), (0x2592, 2), (0x2593, 4)]:
        p = []
        for row in range(20):
            for col in range(10):
                value = (row + col) % modulus
                if (value != 0 if cp == 0x2593 else value == 0):
                    p += rect(col * 64, DESCENT + row * 65, (col + 1) * 64, DESCENT + (row + 1) * 65)
        d[cp] = p
    d[0x2594] = rect(0, ASCENT - h / 8, CELL, ASCENT)
    d[0x2595] = rect(CELL * 7 / 8, DESCENT, CELL, ASCENT)
    quads = [(0, DESCENT, C, MID), (C, DESCENT, CELL, MID), (0, MID, C, ASCENT), (C, MID, CELL, ASCENT)]
    for cp, which in zip(range(0x2596, 0x25A0), [(0,), (1,), (2,), (0, 1, 2), (1, 2), (0, 2, 3), (1, 2, 3), (3,), (0, 3), (0, 1, 3)]):
        d[cp] = sum((rect(*quads[i]) for i in which), [])
    # Powerline separators (private use): solid and outline arrows filling the cell.
    d[0xE0B0] = polygon([(0, DESCENT), (CELL, MID), (0, ASCENT)])
    run = light * 1.2 * ((CELL ** 2 + (ASCENT - MID) ** 2) ** .5) / (ASCENT - MID)
    d[0xE0B1] = polygon([(0, ASCENT), (CELL, MID), (0, DESCENT), (run, DESCENT),
                         (CELL - run, MID), (run, ASCENT)])
    d[0xE0B2] = mirror(d[0xE0B0], True, False)
    d[0xE0B3] = mirror(d[0xE0B1], True, False)
    return d
