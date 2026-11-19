"""Easing: how a value travels from 0 to 1 over a move. Each is a function of progress
x in [0, 1] returning progress y in [0, 1], with its derivative available, so the motion
sheet can draw both the curve and its speed.

    minjerk     the smoothest point-to-point move: zero speed and zero acceleration at both
                ends (y = 10x^3 - 15x^4 + 6x^5). The default for anything that starts and stops.
    scurve(r)   ease in for fraction r of the move, cruise at constant speed, ease out for r.
                Long moves: they travel mostly at an even speed, like a camera on a dolly.
    ease_in, ease_out   minimum-jerk halves: start from rest and leave at speed, or arrive
                at speed and come to rest. For chaining moves without a stop between them.
    spring(response, damping)   a released spring; damping < 1 overshoots and settles.
    cubic_bezier(x1, y1, x2, y2)   CSS-compatible, to match motion drawn in a browser.
    linear, hold

No dependencies: this runs in plain Python and inside Blender alike.
"""

import math


class Ease:
    """y(x) and dy/dx(x) for x in [0, 1]."""

    def __init__(self, name, y, dy):
        self.name, self.y, self.dy = name, y, dy

    def __call__(self, x):
        return self.y(min(1.0, max(0.0, x)))

    def speed(self, x):
        return self.dy(min(1.0, max(0.0, x)))


linear = Ease("linear", lambda x: x, lambda x: 1.0)
hold = Ease("hold", lambda x: 0.0 if x < 1 else 1.0, lambda x: 0.0)
minjerk = Ease("minjerk", lambda x: x * x * x * (10 - 15 * x + 6 * x * x), lambda x: 30 * x * x * (1 - x) ** 2)


def _half_in():
    # first half of minjerk, rescaled: starts at rest, leaves at speed 1.875 (the minjerk peak, x2)
    return Ease("ease_in", lambda x: 2 * minjerk.y(x / 2), lambda x: minjerk.dy(x / 2))


def _half_out():
    return Ease("ease_out", lambda x: 2 * minjerk.y(0.5 + x / 2) - 1, lambda x: minjerk.dy(0.5 + x / 2))


ease_in = _half_in()
ease_out = _half_out()


def scurve(ramp=0.25):
    """Ease in over `ramp` of the move, constant speed, ease out over `ramp` (0 < ramp <= 0.5).
    The ramps are minimum-jerk in acceleration, so acceleration itself is smooth."""
    r = min(0.5, max(1e-6, ramp))
    # speed profile: rises smoothly 0 -> v over [0, r], holds v, falls over [1 - r, 1]
    v = 1.0 / (1.0 - r)  # area under the profile must be 1

    def ramp_up(u):  # smooth 0 -> 1 with zero slope at both ends (integral of minjerk speed shape)
        return minjerk.y(u)

    def speed(x):
        if x < r:
            return v * ramp_up(x / r)
        if x > 1 - r:
            return v * ramp_up((1 - x) / r)
        return v

    # position = integral of speed; minjerk.y integrates to I(u) = u^4*(2.5 - 3u + u^2)... closed form:
    def integ(u):  # integral_0^u minjerk.y(s) ds
        return u**4 * (2.5 - 3 * u + u * u)

    def y(x):
        if x <= r:
            return v * r * integ(x / r)
        if x >= 1 - r:
            return 1.0 - v * r * integ((1 - x) / r)
        return v * r * integ(1.0) + v * (x - r)

    return Ease(f"scurve({r:g})", y, speed)


def spring(response=0.5, damping=0.8):
    """A spring released at rest towards 1; `response` is the undamped period in units of the
    move, damping in (0, 1]. The move's length should cover its settling time."""
    w0 = 2 * math.pi / response
    z = min(1.0, max(1e-3, damping))
    if z < 1:
        wd = w0 * math.sqrt(1 - z * z)
        k = z * w0 / wd

        def y(x):
            return 1 - math.exp(-z * w0 * x) * (math.cos(wd * x) + k * math.sin(wd * x))

        def dy(x):
            e = math.exp(-z * w0 * x)
            return e * (z * w0 * (math.cos(wd * x) + k * math.sin(wd * x)) - (-wd * math.sin(wd * x) + k * wd * math.cos(wd * x)))
    else:
        def y(x):
            return 1 - math.exp(-w0 * x) * (1 + w0 * x)

        def dy(x):
            return math.exp(-w0 * x) * w0 * w0 * x

    end = y(1.0)
    return Ease(f"spring({response:g},{damping:g})", lambda x: y(x) / end if end else y(x), lambda x: dy(x) / end if end else dy(x))


def cubic_bezier(x1, y1, x2, y2):
    """CSS cubic-bezier(x1, y1, x2, y2)."""
    cx, cy = 3 * x1, 3 * y1
    bx, by = 3 * (x2 - x1) - cx, 3 * (y2 - y1) - cy
    ax, ay = 1 - cx - bx, 1 - cy - by

    def sx(t):
        return ((ax * t + bx) * t + cx) * t

    def sy(t):
        return ((ay * t + by) * t + cy) * t

    def dsx(t):
        return (3 * ax * t + 2 * bx) * t + cx

    def dsy(t):
        return (3 * ay * t + 2 * by) * t + cy

    def solve(x):
        t = x
        for _ in range(10):
            e = sx(t) - x
            d = dsx(t)
            if abs(e) < 1e-9 or abs(d) < 1e-9:
                break
            t -= e / d
        lo, hi = 0.0, 1.0
        if not (0 <= t <= 1) or abs(sx(t) - x) > 1e-6:
            t = x
            for _ in range(60):
                if sx(t) < x:
                    lo = t
                else:
                    hi = t
                t = (lo + hi) / 2
        return t

    def y(x):
        return sy(solve(x))

    def dy(x):
        t = solve(x)
        d = dsx(t)
        return dsy(t) / d if abs(d) > 1e-9 else 0.0

    return Ease(f"cubic_bezier({x1:g},{y1:g},{x2:g},{y2:g})", y, dy)


NAMED = {"linear": linear, "hold": hold, "minjerk": minjerk, "smooth": minjerk, "ease_in": ease_in, "ease_out": ease_out}


def get(spec):
    """An Ease from a name ("minjerk"), "scurve:0.3", "spring:0.5:0.8", "bezier:x1:y1:x2:y2", or an Ease."""
    if isinstance(spec, Ease):
        return spec
    if spec in NAMED:
        return NAMED[spec]
    name, *args = str(spec).split(":")
    vals = [float(a) for a in args]
    if name == "scurve":
        return scurve(*vals)
    if name == "spring":
        return spring(*vals)
    if name == "bezier":
        return cubic_bezier(*vals)
    raise ValueError(f"unknown ease {spec!r}")
