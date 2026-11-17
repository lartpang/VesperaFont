"""Vertical metrics and the stroke model shared by every Vespera family and style.

Display and Mono use one drawing master, one x-height and one stroke model.
Mono differs only in its 640-unit cell, the width fitting that cell needs, and a
small amount of extra ink for text sizes on screen.
"""
from __future__ import annotations

import math

X_HEIGHT = 469
CAP_HEIGHT = 695
ASCENT, DESCENT = 1000, -300
CELL = 640

# Family-wide optical contrast: verticals gain a little ink; horizontals, serifs
# and hairlines keep the source weight, so contrast rises to about 3.2 : 1.
OPTICS = (6, 0)
# Additional (x, y) stroke gain per weight, relative to the Regular master.
WEIGHT_GAINS = {'Light': (-26, -6), 'Regular': (0, 0), 'Bold': (50, 18)}
# Extra ink that keeps Mono's hairlines visible at 12-16 px.
MONO_INK = (6, 10)

# The true italic source is drawn at 10 degrees; a derived italic uses the same.
ITALIC_ANGLE = 10
ITALIC_SLOPE = math.tan(math.radians(ITALIC_ANGLE))
ITALIC_CONDENSE = .94
# Slant about the middle of the x-height so lowercase bodies keep their spacing.
ITALIC_PIVOT = X_HEIGHT / 2


def stroke_gain(style, monospaced):
    wx, wy = WEIGHT_GAINS[style.weight]
    gx, gy = OPTICS[0] + wx, OPTICS[1] + wy
    if monospaced:
        gx, gy = gx + MONO_INK[0], gy + MONO_INK[1]
    return gx, gy


def compose(g, p, q, r):
    """Follow an outline map x' = p*x + q*y + r with the glyph's anchor transform."""
    a, b, c = g['anchor']
    g['anchor'] = (p * a, p * b + q, p * c + r)
