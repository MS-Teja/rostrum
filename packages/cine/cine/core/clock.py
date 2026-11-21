"""A clock that follows the scale: calendar time that runs in proportion to the view.

For scenes across powers of ten, where something real moves at its real pace (a spacecraft, a
planet): the calendar runs at c(t) days per second for each unit of view width, so the subject
crosses the screen at a pace set by its true speed at every zoom. A speed-up reads true, and
diving into a small system slows time with the view.

c(t) steps between plateaus, smoothly (in log). The plateaus are the unknowns: each is solved so
that a pinned moment lands on its word ("the launch on 'So'"). A plateau can also be fixed (a
close shot that runs at a set pace).

    from cine.core.clock import ScaleClock
    clock = ScaleClock(start=jd_launch - 6, t1=T1, fps=30)
    clock.solve(field,                                   # the view's width at t (true units)
                keys=[(0.0, 0), (so - 0.5, 0), (so + 0.3, 1), (close - 0.5, 1), (close, 50.0), (T1, 50.0)],
                pins=[(so, jd_launch), (flung, jd_jupiter)],
                guess=[0.02, 14.0])
    clock(t)        # the Julian date at scene time t
    clock.when(jd)  # the scene time a date is reached
    clock.rate(t)   # days per second at t

Before `solve`, the clock reads `start` at every t.
"""

import math


class ScaleClock:
    def __init__(self, start, t1, fps=30, oversample=4):
        self.start, self.t1, self.fps = start, t1, fps
        self.dt = 1.0 / (fps * oversample)
        self.jd = None
        self.c = None

    def __call__(self, t):
        if self.jd is None:
            return self.start
        J = self.jd
        x = max(0.0, min(len(J) - 1.0001, t / self.dt))
        i = int(x)
        return J[i] + (J[i + 1] - J[i]) * (x - i)

    def rate(self, t, h=0.05):
        """Days per scene second at t."""
        return (self(t + h) - self(t - h)) / (2 * h)

    def when(self, jd):
        """The first scene time the clock reaches `jd` (the clock never runs backwards)."""
        J = self.jd
        if J is None or jd <= J[0]:
            return 0.0
        if jd >= J[-1]:
            return (len(J) - 1) * self.dt
        lo, hi = 0, len(J) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if J[mid] < jd else (lo, mid)
        return (lo + (jd - J[lo]) / (J[hi] - J[lo])) * self.dt

    def solve(self, field, keys, pins, guess, sweeps=5, steps=32):
        """Solve the plateaus so each pin lands. `field(t)`: the view's width (true units) at t.
        `keys`: [(t, v)], v an int (the index of an unknown plateau, one per pin, in pin order) or a
        float (a fixed rate, days per second per unit of width). Returns the solved plateaus."""
        dt = self.dt
        ts = [k * dt for k in range(int(self.t1 / dt) + 2)]
        fv = [field(t) for t in ts]
        nk = len(keys)
        seg = []
        for t in ts:  # which pair of keys, and how far through the step (smoothstep), at each sample
            for i in range(nk - 1):
                if keys[i][0] <= t <= keys[i + 1][0] or i == nk - 2:
                    ta, tb = keys[i][0], keys[i + 1][0]
                    u = max(0.0, min(1.0, (t - ta) / (tb - ta))) if tb > ta else 0.0
                    seg.append((i, u * u * (3 - 2 * u)))
                    break

        def integrate(c):
            lc = [math.log(c[v] if isinstance(v, int) else v) for _, v in keys]
            rate = [math.exp(lc[i] + (lc[i + 1] - lc[i]) * u) * f for (i, u), f in zip(seg, fv)]
            out = [self.start]
            for i in range(1, len(ts)):
                out.append(out[-1] + 0.5 * (rate[i - 1] + rate[i]) * dt)
            return out

        c = list(guess)
        assert len(c) == len(pins), "one unknown plateau per pin"
        for _ in range(sweeps):
            for k, (tp, jp) in enumerate(pins):
                lo, hi = math.log(c[k]) - 7, math.log(c[k]) + 7
                for _ in range(steps):
                    c[k] = math.exp((lo + hi) / 2)
                    J = integrate(c)
                    lo, hi = ((lo + hi) / 2, hi) if J[int(round(tp / dt))] < jp else (lo, (lo + hi) / 2)
        self.jd, self.c = integrate(c), c
        return c

    def misses(self, pins):
        """How far each pin lands from its date, in days (the solve's residuals)."""
        return [self(t) - jd for t, jd in pins]
