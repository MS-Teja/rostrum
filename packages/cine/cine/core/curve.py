"""Curves: the one model of animation in cine. Every animated quantity in a scene (camera
position, aim point, lens, an actor's position, rotation, scale, glow) is a named Curve of
time. The scene's motion file holds its curves; Blender is baked from them, the motion
sheet draws them, QA measures them.

A Curve is either
  keyed:   keys [(t, value)] joined by one interpolation:
             "spline"  a clamped cubic spline through every key: continuous in value, speed
                       and acceleration (C2), at rest at the first and last key. Camera paths.
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
    def __init__(self, keys=None, interp="spline", samples=None, fps=30.0, t0=0.0, ease="minjerk", eases=None):
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
            if interp == "spline" and len(ks) > 1:
                self._spline()
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
        return d

    @classmethod
    def from_json(cls, d):
        if "samples" in d:
            return cls(samples=d["samples"], fps=d.get("fps", 30), t0=d.get("t0", 0.0))
        return cls(keys=d["keys"], interp=d.get("interp", "spline"), ease=d.get("ease", "minjerk"))


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


class Motion:
    """A scene's motion file: its curves and the timing they belong to.

    fields: name, fps, t0, t1 (seconds in the video), words [(t, word)], beats [(t0, t1, id)],
    cuts [t] (scene changes inside the span), spans [{lane, t0, t1, label}] (labelled moves),
    camera {"pos": channel, "aim": channel, "lens": channel}, subjects {name: channel},
    channels {name: Curve}, notes (free text).
    """

    def __init__(self, name, t0, t1, fps=30.0):
        self.name, self.t0, self.t1, self.fps = name, float(t0), float(t1), float(fps)
        self.words, self.beats, self.cuts, self.spans = [], [], [], []
        self.camera = {"pos": "cam.pos", "aim": "cam.aim", "lens": "cam.lens"}
        self.subjects = {}
        self.channels = {}
        self.notes = ""

    def times(self):
        n = int(round((self.t1 - self.t0) * self.fps))
        return [self.t0 + k / self.fps for k in range(n + 1)]

    def save(self, path):
        d = {k: getattr(self, k) for k in ("name", "t0", "t1", "fps", "words", "beats", "cuts", "spans", "camera", "subjects", "notes")}
        d["channels"] = {k: c.to_json() for k, c in self.channels.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, separators=(",", ":"))

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        m = cls(d["name"], d["t0"], d["t1"], d.get("fps", 30))
        for k in ("words", "beats", "cuts", "spans", "camera", "subjects", "notes"):
            if k in d:
                setattr(m, k, d[k])
        m.channels = {k: Curve.from_json(c) for k, c in d["channels"].items()}
        return m
