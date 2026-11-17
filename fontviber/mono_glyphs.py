"""Terminal glyphs for the 640-unit cell: box drawing, block elements, Powerline."""
from __future__ import annotations

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


ARMS = {'L': (0, MID, C, MID), 'R': (C, MID, CELL, MID), 'U': (C, MID, C, ASCENT), 'D': (C, DESCENT, C, MID)}


def single(directions, weight, fraction=None):
    """Arms meet in one union square; fraction draws an arm partially (half lines)."""
    out = []
    for arm in directions:
        x0, y0, x1, y1 = ARMS[arm]
        if x0 == x1:
            out += rect(x0 - weight / 2, y0, x1 + weight / 2, y1)
        else:
            out += rect(x0, y0 - weight / 2, x1, y1 + weight / 2)
    return out + rect(C - weight / 2, MID - weight / 2, C + weight / 2, MID + weight / 2)


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
    """Box drawing, all 32 block elements and Powerline separators.

    Line weights follow the font weight so frames sit with the text around them.
    """
    heavy = round(light * 1.85)
    d = {}
    dirs = ['LR', 'UD', 'RD', 'LD', 'RU', 'LU', 'URD', 'ULD', 'LRD', 'LRU', 'LURD']
    for chars, weight in [('─│┌┐└┘├┤┬┴┼', light), ('━┃┏┓┗┛┣┫┳┻╋', heavy)]:
        for ch, arms in zip(chars, dirs):
            d[ord(ch)] = single(arms, weight)
    for ch, arms in zip('═║╔╗╚╝╠╣╦╩╬', dirs):
        d[ord(ch)] = double(arms, light)
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
    for ch, arm, weight in zip('╴╵╶╷╸╹╺╻', 'LURDLURD', [light] * 4 + [heavy] * 4):
        x0, y0, x1, y1 = ARMS[arm]
        if x0 == x1:
            d[ord(ch)] = rect(x0 - weight / 2, y0, x1 + weight / 2, y1)
        else:
            d[ord(ch)] = rect(x0, y0 - weight / 2, x1, y1 + weight / 2)
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
