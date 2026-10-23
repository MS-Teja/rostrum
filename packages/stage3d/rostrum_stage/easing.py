"""Easing curves, ported from packages/primitives/src/time/easing.ts.

test/easing.test.ts checks both at the same sample points, so motion rendered
in Blender matches motion drawn in the browser. No bpy here: it runs anywhere.
"""

import math
from types import SimpleNamespace


def linear(x):
    return x


def cubic_bezier(x1, y1, x2, y2):
    """CSS-compatible cubic-bezier: Newton-Raphson for x(t), bisection where the slope is flat."""
    cx = 3 * x1
    bx = 3 * (x2 - x1) - cx
    ax = 1 - cx - bx
    cy = 3 * y1
    by = 3 * (y2 - y1) - cy
    ay = 1 - cy - by

    def sample_x(t):
        return ((ax * t + bx) * t + cx) * t

    def sample_y(t):
        return ((ay * t + by) * t + cy) * t

    def slope_x(t):
        return (3 * ax * t + 2 * bx) * t + cx

    def solve_t(x):
        t = x
        for _ in range(8):
            err = sample_x(t) - x
            if abs(err) < 1e-7:
                return t
            d = slope_x(t)
            if abs(d) < 1e-6:
                break
            t -= err / d
        lo, hi = 0.0, 1.0
        t = x
        while lo < hi:
            sx = sample_x(t)
            if abs(sx - x) < 1e-7:
                return t
            if x > sx:
                lo = t
            else:
                hi = t
            if hi - lo < 1e-9:
                break
            t = (lo + hi) / 2
        return t

    def curve(x):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        return sample_y(solve_t(x))

    return curve


# Easing by role, so every scene moves the same way.
ease = SimpleNamespace(
    enter=cubic_bezier(0.16, 1, 0.3, 1),
    exit=cubic_bezier(0.7, 0, 0.84, 0),
    move=cubic_bezier(0.65, 0, 0.35, 1),
    linear=linear,
)


def spring(response, damping, epsilon=1e-3):
    """A spring released at rest, parameterised like SwiftUI's spring(response:dampingFraction:)."""
    if not response > 0:
        raise ValueError("spring response must be > 0")
    if not 0 < damping <= 1:
        raise ValueError("spring damping must be in (0, 1]")

    w0 = 2 * math.pi / response
    if damping < 1:
        wd = w0 * math.sqrt(1 - damping * damping)
        k = damping * w0 / wd

        def at(s):
            if s <= 0:
                return 0.0
            return 1 - math.exp(-damping * w0 * s) * (math.cos(wd * s) + k * math.sin(wd * s))

        settle = math.log(1 / (epsilon * math.sqrt(1 - damping * damping))) / (damping * w0)
    else:

        def at(s):
            if s <= 0:
                return 0.0
            return 1 - math.exp(-w0 * s) * (1 + w0 * s)

        lo, hi = 0.0, 1.0
        while 1 - at(hi) > epsilon:
            hi *= 2
        for _ in range(60):
            mid = (lo + hi) / 2
            if 1 - at(mid) > epsilon:
                lo = mid
            else:
                hi = mid
        settle = hi

    return SimpleNamespace(at=at, settle=settle, ease=lambda x: 1.0 if x >= 1 else at(x * settle))


def progress(t, start, duration):
    """0 before `start`, 1 after `start + duration`, linear in between."""
    if duration <= 0:
        return 1.0 if t >= start else 0.0
    return min(1.0, max(0.0, (t - start) / duration))


def lerp(a, b, p):
    return a + (b - a) * p
