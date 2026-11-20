"""Paths through space, timed by distance travelled, and smoothing that doesn't shift timing.

    Path(points)        a centripetal Catmull-Rom curve through points (no cusps, no loops),
                        evaluated by fraction of its length: Path(...)(0.5) is half-way along
                        it, so speed follows the move's ease, not the spacing of the points
    smooth(values, s)   zero-phase Gaussian smoothing (vectors or numbers), split at cuts:
                        removes kinks without moving anything in time

No dependencies.
"""

import bisect
import math


def _d(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class Path:
    def __init__(self, points, alpha=0.5, samples_per_segment=64):
        pts = [list(map(float, p)) for p in points]
        if len(pts) < 2:
            raise ValueError("a Path needs two points")
        self.pts = pts
        # phantom end points: reflect, so the path starts and ends heading along its first/last leg
        P = [[2 * pts[0][i] - pts[1][i] for i in range(3)]] + pts + [[2 * pts[-1][i] - pts[-2][i] for i in range(3)]]
        self._segs = []
        for k in range(len(P) - 3):
            self._segs.append(self._seg(P[k], P[k + 1], P[k + 2], P[k + 3], alpha))
        # arc-length table
        self._u, self._s = [0.0], [0.0]
        prev = self._eval(0.0)
        n = len(self._segs)
        for j in range(1, n * samples_per_segment + 1):
            u = j / samples_per_segment
            p = self._eval(u)
            self._s.append(self._s[-1] + _d(prev, p))
            self._u.append(u)
            prev = p
        self.length = self._s[-1]

    @staticmethod
    def _seg(p0, p1, p2, p3, alpha):
        def tj(ti, a, b):
            return ti + max(_d(a, b), 1e-9) ** alpha
        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)

        def at(u):  # u in [0, 1] across p1..p2 (Barry-Goldman pyramid)
            t = t1 + (t2 - t1) * u
            def lerp(a, b, ta, tb):
                return [(tb - t) / (tb - ta) * a[i] + (t - ta) / (tb - ta) * b[i] for i in range(3)]
            a1, a2, a3 = lerp(p0, p1, t0, t1), lerp(p1, p2, t1, t2), lerp(p2, p3, t2, t3)
            b1, b2 = lerp(a1, a2, t0, t2), lerp(a2, a3, t1, t3)
            return lerp(b1, b2, t1, t2)
        return at

    def _eval(self, u):
        n = len(self._segs)
        k = min(n - 1, max(0, int(u)))
        return self._segs[k](min(1.0, max(0.0, u - k)))

    def __call__(self, f):
        """The point at fraction f (0..1) of the path's length."""
        s = min(1.0, max(0.0, f)) * self.length
        i = bisect.bisect_left(self._s, s)
        if i <= 0:
            return self._eval(0.0)
        if i >= len(self._s):
            return self._eval(self._u[-1])
        s0, s1 = self._s[i - 1], self._s[i]
        u = self._u[i - 1] + (self._u[i] - self._u[i - 1]) * ((s - s0) / (s1 - s0) if s1 > s0 else 0.0)
        return self._eval(u)


def smooth(values, sigma, cuts=()):
    """Gaussian smoothing with a kernel of `sigma` samples, applied symmetrically (zero phase),
    separately on each stretch between cut indices. Ends are held (reflected), so a camera that
    starts at rest still starts at rest."""
    if sigma <= 0 or len(values) < 3:
        return list(values)
    vec = isinstance(values[0], (list, tuple))
    r = max(1, int(3 * sigma))
    w = [math.exp(-0.5 * (k / sigma) ** 2) for k in range(-r, r + 1)]
    bounds = [0] + sorted(c for c in cuts if 0 < c < len(values)) + [len(values)]
    out = list(values)
    for a, b in zip(bounds, bounds[1:]):
        seg = values[a:b]
        n = len(seg)
        for i in range(n):
            acc, tot = None, 0.0
            for k, wk in zip(range(-r, r + 1), w):
                j = i + k
                if j < 0:
                    j = -j
                if j >= n:
                    j = 2 * (n - 1) - j
                j = min(n - 1, max(0, j))
                v = seg[j]
                if acc is None:
                    acc = [x * wk for x in v] if vec else v * wk
                elif vec:
                    acc = [p + x * wk for p, x in zip(acc, v)]
                else:
                    acc += v * wk
                tot += wk
            out[a + i] = [x / tot for x in acc] if vec else acc / tot
    return out
