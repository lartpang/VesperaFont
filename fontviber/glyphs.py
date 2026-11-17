"""Distinct characters for both families.

Default lining and tabular-oldstyle digits get one true 600-unit advance;
proportional digit alternates remain proportional.
"""
from __future__ import annotations

import copy
from .font_io import contours, map_path

DIGITS = ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine')
CONFUSABLE_TEXT = "(q9gp?){GCu}<iIL1tT7>ck'b6'r[o0O]`nh`\"uvw\"|s5e|zZ2|8B3|,.\\/|=;:|*|~-_+|"
CONFUSABLE_GROUPS = ["(q9gp?)", "{GCu}", "<iIL1tT7>", "ck'b6'r", "[o0O]", '`nh`"uvw"', "s5e", "zZ2", "8B3", ",.\\/", "=;:", "*", "~-_+", "|"]


def distinctive_drawings(source):
    n = {g['name']: g for g in source['glyphs']}
    d = {}

    # A hooked lowercase l has neither I's paired serifs nor 1's diagonal flag.
    d['l'] = [
        ['M', 104, 102], ['C', 104, 25, 149, -12, 206, -12],
        ['C', 249, -12, 287, 8, 314, 39], ['L', 299, 64],
        ['C', 276, 50, 259, 44, 243, 44], ['C', 207, 44, 188, 65, 188, 113],
        ['L', 188, 718], ['L', 179, 726], ['C', 135, 709, 102, 701, 23, 689],
        ['L', 23, 661], ['L', 79, 661], ['C', 97, 661, 104, 650, 104, 620],
        ['L', 104, 102], ['Z'],
    ]
    # q's open, right-facing hook differentiates it from p's foot and g's loop.
    q = copy.deepcopy(n['q']['path'])
    begin = q.index(['L', 393, -176]) + 1
    end = q.index(['L', 477, 318])
    d['q'] = q[:begin] + [
        ['C', 393, -247, 414, -279, 465, -279],
        ['C', 521, -279, 565, -246, 591, -195], ['L', 568, -177],
        ['C', 539, -213, 515, -226, 492, -218],
        ['C', 479, -214, 477, -197, 477, -164],
    ] + q[end:]

    # An extended internal G bar is unmistakable next to an open C.
    fixes = {(479, 271): (433, 282), (479, 241): (433, 235)}
    d['G'] = map_path(n['G']['path'], lambda x, y: fixes.get((x, y), (x, y)))

    # 1 has an emphatic diagonal shoulder and a complete, broad baseline foot.
    fixes = {(60, 598): (49, 596), (67, 555): (71, 538), (77, 555): (85, 538),
             (206, 613): (206, 605), (209, 614): (209, 607),
             (301, 689): (301, 702), (287, 694): (279, 716)}
    d['one'] = map_path(n['one']['path'], lambda x, y: fixes.get((x, y), (x, y)))

    # 7's identifying cross-stroke is the hyphen itself: same weight, same oblique cuts.
    hyphen = contours(n['hyphen']['path'])[0]
    cross = map_path(hyphen, lambda x, y: (139 + (x - 17) * 240 / 295, 321 + (y - 251) * .8))
    d['seven'] = copy.deepcopy(n['seven']['path']) + cross

    # 5 keeps an angular neck; its flag now rises into a fine, calligraphic tip.
    five = copy.deepcopy(n['five']['path'])
    begin = five.index(['L', 127, 605])
    end = five.index(['L', 81, 547]) + 1
    d['five'] = five[:begin] + [
        ['L', 130, 608], ['C', 238, 608, 339, 580, 431, 608],
        ['L', 453, 699], ['C', 347, 672, 225, 683, 82, 689],
        ['L', 81, 547],
    ] + five[end:]

    # Slash is part of the counter topology, so there are no overlapping strokes.
    zero = contours(n['zero']['path'])[0]
    zero += [
        ['M', 113, 360], ['C', 113, 571, 150, 654, 245, 654],
        ['C', 270, 654, 293, 645, 309, 626], ['L', 137, 158],
        ['C', 121, 208, 113, 274, 113, 360], ['Z'],
        ['M', 157, 95], ['L', 334, 564], ['C', 367, 504, 381, 424, 381, 316],
        ['C', 381, 103, 343, 15, 251, 15], ['C', 211, 15, 180, 41, 157, 95], ['Z'],
    ]
    d['zero'] = zero
    # A scaled version supplies marked oldstyle zero forms as well.
    d['zero.oldstyle'] = map_path(zero, lambda x, y: (40 + (x - 29) * 450 / 436, -20 + (y + 20) * 499 / 709))
    return d


def tabularize(glyphs):
    for g in glyphs:
        if g['name'] in DIGITS or g['name'] in [n + '.taboldstyle' for n in DIGITS] or g['name'] == 'zero.slash':
            shift = (600 - g['advance']) / 2
            g['path'] = map_path(g['path'], lambda x, y: (round(x + shift), y))
            g['advance'] = 600
            g['left_shift'] += round(shift)
