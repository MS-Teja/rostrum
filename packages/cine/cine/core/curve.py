"""Curves: the one model of animation in cine. Every animated quantity in a scene (camera
position, aim point, lens, an actor's position, rotation, scale, glow) is a named Curve of
time. The scene's motion file holds its curves; Blender is baked from them, the motion
sheet draws them, QA measures them.

A Curve is either
  keyed:   keys [(t, value)] joined by one interpolation:
             "minjerk" the minimum-jerk path through every key (a quintic spline, continuous to
                       the fourth derivative): how a skilled hand moves through via points. At
                       rest at the first and last key and at any key listed in `stops`. It may
                       swing past a key when neighbouring keys demand it. Camera journeys.
             "monotone" quintic segments that never overshoot: a key that is a peak, a valley
                       or one of two equal keys is reached at rest; elsewhere speed carries
                       through. Continuous to the second derivative. Weights, screen offsets.
                       With glide=r, a segment from rest to rest eases in over r of it, cruises,
                       and eases out (a dolly grip's move): its peak speed is 1/(1-r) of its
                       average instead of minimum-jerk's 1.875.
             "spline"  a clamped cubic spline through every key: continuous in value, speed
                       and acceleration (C2), at rest at the first and last key.
             "eased"   each segment its own ease (default minjerk): the value settles at every
                       key. Actor moves that should land and stop.
             "linear", "hold"
  sampled: one value per frame (from a simulation, a recorded camera, data).

Values are numbers or equal-length lists (vectors). No dependencies.
"""

import bisect
import json

from . import ease as E


def _add(a, b):
    return [x + y for x, y in zip(a, b)] if isinstance(a, list) else a + b


def _sub(a, b):
    return [x - y for x, y in zip(a, b)] if isinstance(a, list) else a - b


def _mul(a, k):
    return [x * k for x in a] if isinstance(a, list) else a * k


def _lerp(a, b, u):
    return _add(a, _mul(_sub(b, a), u))


class Curve:
    def __init__(self, keys=None, interp="spline", samples=None, fps=30.0, t0=0.0, ease="minjerk", eases=None, stops=(), glide=0.0):
        if (keys is None) == (samples is None):
            raise ValueError("a Curve has keys or samples, not both")
        self.fps, self.t0 = float(fps), float(t0)
        if keys is not None:
            ks = sorted(((float(t), list(v) if isinstance(v, (list, tuple)) else float(v)) for t, v in keys), key=lambda k: k[0])
            self.keys = ks
            self.interp = interp
            self.ease = E.get(ease)
            self.eases = [E.get(e) for e in eases] if eases else None  # per segment, for "eased"
            self.samples = None
            self.stops = sorted(float(x) for x in stops)
            self.glide = float(glide)
            self._glides = {}
            if interp == "spline" and len(ks) > 1:
                self._spline()
            if interp in ("minjerk", "monotone") and len(ks) > 1:
                self._quintic()
        else:
            self.keys = None
            self.interp = "sampled"
            self.samples = [list(v) if isinstance(v, (list, tuple)) else float(v) for v in samples]

    # ── spline coefficients: clamped (zero end slopes) cubic spline, per component ──────────
    def _spline(self):
        ts = [k[0] for k in self.keys]
        vec = isinstance(self.keys[0][1], list)
        comps = len(self.keys[0][1]) if vec else 1
        self._m = []  # second derivatives per component
        for c in range(comps):
            ys = [k[1][c] if vec else k[1] for k in self.keys]
            self._m.append(_clamped_second_derivs(ts, ys))

    # ── quintic coefficients, per component and segment, in local progress u in [0, 1] ──────
    def _quintic(self):
        ts = [k[0] for k in self.keys]
        vec = isinstance(self.keys[0][1], list)
        comps = len(self.keys[0][1]) if vec else 1
        cols = [[k[1][c] if vec else k[1] for k in self.keys] for c in range(comps)]
        stop = [any(abs(t - x) < 1e-6 for x in self.stops) for t in ts]
        if self.interp == "minjerk":
            self._c = _minjerk_spline(ts, cols, stop)
        else:
            self._c = [_monotone_quintic(ts, ys, stop) for ys in cols]
            if self.glide > 0 and comps == 1:  # rest-to-rest segments glide: ease in, cruise, ease out
                for i, c in enumerate(self._c[0]):
                    if abs(c[1]) < 1e-12 and abs(c[1] + 2 * c[2] + 3 * c[3] + 4 * c[4] + 5 * c[5]) < 1e-12 and cols[0][i] != cols[0][i + 1]:
                        self._glides[i] = (cols[0][i], cols[0][i + 1], E.scurve(self.glide))

    # ── evaluation ───────────────────────────────────────────────────────────────────────
    @property
    def span(self):
        if self.keys is not None:
            return self.keys[0][0], self.keys[-1][0]
        return self.t0, self.t0 + (len(self.samples) - 1) / self.fps

    def __call__(self, t):
        if self.samples is not None:
            x = (t - self.t0) * self.fps
            if x <= 0:
                return self.samples[0]
            if x >= len(self.samples) - 1:
                return self.samples[-1]
            i = int(x)
            return _lerp(self.samples[i], self.samples[i + 1], x - i)
        ks = self.keys
        if len(ks) == 1 or t <= ks[0][0]:
            return ks[0][1]
        if t >= ks[-1][0]:
            return ks[-1][1]
        i = bisect.bisect_right([k[0] for k in ks], t) - 1
        (ta, va), (tb, vb) = ks[i], ks[i + 1]
        u = (t - ta) / (tb - ta)
        if self.interp == "linear":
            return _lerp(va, vb, u)
        if self.interp == "hold":
            return va
        if self.interp == "eased":
            e = self.eases[i] if self.eases else self.ease
            return _lerp(va, vb, e(u))
        if self.interp == "monotone" and i in self._glides:
            a, b, e = self._glides[i]
            return a + (b - a) * e(u)
        if self.interp in ("minjerk", "monotone"):
            def poly(c):
                return c[0] + u * (c[1] + u * (c[2] + u * (c[3] + u * (c[4] + u * c[5]))))
            if isinstance(va, list):
                return [poly(self._c[c][i]) for c in range(len(va))]
            return poly(self._c[0][i])
        # spline
        h = tb - ta
        def one(ya, yb, ma, mb):
            a, b = (tb - t) / h, (t - ta) / h
            return a * ya + b * yb + ((a**3 - a) * ma + (b**3 - b) * mb) * h * h / 6.0
        if isinstance(va, list):
            return [one(va[c], vb[c], self._m[c][i], self._m[c][i + 1]) for c in range(len(va))]
        return one(va, vb, self._m[0][i], self._m[0][i + 1])

    def sample(self, t0, t1, fps=None):
        fps = fps or self.fps
        n = int(round((t1 - t0) * fps))
        return [self(t0 + k / fps) for k in range(n + 1)]

    # ── storage ──────────────────────────────────────────────────────────────────────────
    def to_json(self):
        if self.samples is not None:
            return {"samples": self.samples, "fps": self.fps, "t0": self.t0}
        d = {"keys": self.keys, "interp": self.interp}
        if self.interp == "eased":
            d["ease"] = self.ease.name
        if self.stops:
            d["stops"] = self.stops
        if getattr(self, "glide", 0):
            d["glide"] = self.glide
        return d

    @classmethod
    def from_json(cls, d):
        if "samples" in d:
            return cls(samples=d["samples"], fps=d.get("fps", 30), t0=d.get("t0", 0.0))
        return cls(keys=d["keys"], interp=d.get("interp", "spline"), ease=d.get("ease", "minjerk"), stops=d.get("stops", ()), glide=d.get("glide", 0.0))


def _clamped_second_derivs(ts, ys):
    """Second derivatives at the knots of the cubic spline through (ts, ys) with zero slope at
    both ends (so a camera path starts and ends at rest). Thomas algorithm."""
    n = len(ts)
    if n < 2:
        return [0.0] * n
    h = [ts[i + 1] - ts[i] for i in range(n - 1)]
    a = [0.0] * n
    b = [0.0] * n
    c = [0.0] * n
    d = [0.0] * n
    # clamped ends: slope 0
    b[0], c[0], d[0] = 2 * h[0], h[0], 6 * ((ys[1] - ys[0]) / h[0] - 0.0)
    for i in range(1, n - 1):
        a[i], b[i], c[i] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
        d[i] = 6 * ((ys[i + 1] - ys[i]) / h[i] - (ys[i] - ys[i - 1]) / h[i - 1])
    a[n - 1], b[n - 1], d[n - 1] = h[n - 2], 2 * h[n - 2], 6 * (0.0 - (ys[n - 1] - ys[n - 2]) / h[n - 2])
    for i in range(1, n):
        w = a[i] / b[i - 1]
        b[i] -= w * c[i - 1]
        d[i] -= w * d[i - 1]
    m = [0.0] * n
    m[n - 1] = d[n - 1] / b[n - 1]
    for i in range(n - 2, -1, -1):
        m[i] = (d[i] - c[i] * m[i + 1]) / b[i]
    return m


def _deriv_row(k, at_end):
    """Coefficients that give the k-th derivative (in u) of c0 + c1 u + ... + c5 u^5 at u = 0
    or u = 1."""
    row = [0.0] * 6
    for j in range(k, 6):
        f = 1.0
        for q in range(j - k + 1, j + 1):
            f *= q
        row[j] = f if at_end else (f if j == k else 0.0)
    return row


def _solve(A, B):
    """Gaussian elimination with partial pivoting: A x = B for several right-hand sides."""
    n = len(A)
    A = [row[:] for row in A]
    B = [row[:] for row in B]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(A[r][col]))
        A[col], A[piv] = A[piv], A[col]
        B[col], B[piv] = B[piv], B[col]
        p = A[col][col]
        if abs(p) < 1e-14:
            raise ValueError("singular system: two keys at the same time?")
        for r in range(col + 1, n):
            f = A[r][col] / p
            if f:
                Ar, Ac = A[r], A[col]
                for c in range(col, n):
                    Ar[c] -= f * Ac[c]
                B[r] = [x - f * y for x, y in zip(B[r], B[col])]
    X = [[0.0] * len(B[0]) for _ in range(n)]
    for r in range(n - 1, -1, -1):
        acc = B[r][:]
        for c in range(r + 1, n):
            if A[r][c]:
                acc = [a - A[r][c] * x for a, x in zip(acc, X[c])]
        X[r] = [a / A[r][r] for a in acc]
    return X


def _minjerk_spline(ts, cols, stop):
    """The quintic spline through (ts, ys) for each column of ys: through every key, continuous
    to the fourth derivative between keys, with speed and acceleration zero at both ends and at
    stop keys. This minimises the integral of squared jerk (Flash & Hogan's via-point model of
    smooth human movement). Returns per column, per segment, six coefficients in local u."""
    m = len(ts) - 1
    h = [ts[i + 1] - ts[i] for i in range(m)]
    N = 6 * m
    A, B = [], []

    def eq(entries, rhs):
        row = [0.0] * N
        for (seg, coef) in entries:
            for j in range(6):
                row[6 * seg + j] += coef[j]
        A.append(row)
        B.append(rhs)

    zero = [0.0] * len(cols)
    for i in range(m):
        eq([(i, _deriv_row(0, False))], [ys[i] for ys in cols])
        eq([(i, _deriv_row(0, True))], [ys[i + 1] for ys in cols])
    for j in range(1, m):
        if stop[j]:
            for k in (1, 2):
                eq([(j - 1, _deriv_row(k, True))], zero)
                eq([(j, _deriv_row(k, False))], zero)
        else:
            for k in (1, 2, 3, 4):
                a = [x / h[j - 1] ** k for x in _deriv_row(k, True)]
                b = [-x / h[j] ** k for x in _deriv_row(k, False)]
                eq([(j - 1, a), (j, b)], zero)
    for k in (1, 2):
        eq([(0, _deriv_row(k, False))], zero)
        eq([(m - 1, _deriv_row(k, True))], zero)
    X = _solve(A, B)
    return [[[X[6 * i + j][c] for j in range(6)] for i in range(m)] for c in range(len(cols))]


def _hermite5(p0, p1, v0, v1, h):
    """Quintic Hermite coefficients (in u) with end speeds v0, v1 (per second) and zero end
    accelerations, over a segment h seconds long."""
    a, b = h * v0, h * v1
    return [p0, a, 0.0, -10 * p0 - 6 * a - 4 * b + 10 * p1, 15 * p0 + 8 * a + 7 * b - 15 * p1, -6 * p0 - 3 * a - 3 * b + 6 * p1]


def _monotone_quintic(ts, ys, stop):
    n = len(ts)
    h = [ts[i + 1] - ts[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    v = [0.0] * n
    for k in range(1, n - 1):
        if stop[k] or d[k - 1] * d[k] <= 0:
            continue
        h0, h1 = h[k - 1], h[k]
        v[k] = 3 * (h0 + h1) / ((2 * h1 + h0) / d[k - 1] + (h1 + 2 * h0) / d[k])  # Fritsch-Butland
    out = []
    for i in range(n - 1):
        v0, v1 = v[i], v[i + 1]
        for _ in range(40):  # back the speeds off until the segment never runs backwards
            c = _hermite5(ys[i], ys[i + 1], v0, v1, h[i])
            sgn = ys[i + 1] - ys[i]
            ok = all((c[1] + u * (2 * c[2] + u * (3 * c[3] + u * (4 * c[4] + u * 5 * c[5])))) * sgn >= -1e-12 for u in [q / 32 for q in range(33)])
            if ok or sgn == 0:
                break
            v0, v1 = v0 * 0.85, v1 * 0.85
        out.append(_hermite5(ys[i], ys[i + 1], v0, v1, h[i]))
    return out


class Motion:
    """A scene's motion file: its curves and the timing they belong to.

    fields: name, fps, t0, t1 (seconds in the video), words [(t, word)], beats [(t0, t1, id)],
    cuts [t] (scene changes inside the span), spans [{lane, t0, t1, label}] (labelled moves),
    camera {"pos": channel, "aim": channel, "lens": channel}, subjects {name: channel},
    shapes {name: {points, xform, facing, role}} (see core/shape.py), shots [{t, subject, size,
    angle, side, lens, motive}] (the shot plan, from camera.shot), brief (the director's brief,
    text), channels {name: Curve}, notes (free text).
    """

    def __init__(self, name, t0, t1, fps=30.0):
        self.name, self.t0, self.t1, self.fps = name, float(t0), float(t1), float(fps)
        self.words, self.beats, self.cuts, self.spans = [], [], [], []
        self.camera = {"pos": "cam.pos", "aim": "cam.aim", "lens": "cam.lens"}
        self.subjects = {}
        self.shapes = {}
        self.shots = []
        self.brief = ""
        self.channels = {}
        self.notes = ""

    def times(self):
        n = int(round((self.t1 - self.t0) * self.fps))
        return [self.t0 + k / self.fps for k in range(n + 1)]

    def save(self, path):
        d = {k: getattr(self, k) for k in ("name", "t0", "t1", "fps", "words", "beats", "cuts", "spans", "camera", "subjects", "shapes", "shots", "brief", "notes")}
        d["channels"] = {k: c.to_json() for k, c in self.channels.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, separators=(",", ":"))

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        m = cls(d["name"], d["t0"], d["t1"], d.get("fps", 30))
        for k in ("words", "beats", "cuts", "spans", "camera", "subjects", "shapes", "shots", "brief", "notes"):
            if k in d:
                setattr(m, k, d[k])
        m.channels = {k: Curve.from_json(c) for k, c in d["channels"].items()}
        return m
