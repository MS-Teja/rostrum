"""The camera as a virtual operator. A scene's camera journey is a handful of poses at times
(keys), and the camera travels through them on minimum-jerk curves: the path a skilled hand
takes through via points. Continuous to the fourth derivative between keys, at rest only
where the journey starts, ends, or a key says stop. Smooth by construction, not by repair.

    rig = Rig({"voyager": craft, "thrusters": cluster, "earth": EARTH}, fps=30)
    rig.key(0,   look="voyager",   dist=17, az=200, el=12, lens=40, screen=(-1/6, 0), label="establish")
    rig.key(4.5, look="voyager",   dist=15, az=207,                   label="creep in")
    rig.key(9,   look="thrusters", dist=4,  az=225, el=-8, screen=(0, 0), label="push in to the thrusters")
    rig.key(14,  look="voyager",   dist=7.5, az=300, el=24,           label="round and up to the dish")
    rig.key(20,  look="voyager",   dist=14, az=..., el=..., lens=35, screen=(0.2, 0), label="the beam reaches Earth")
    cam = rig.sample(0, 20)    # {"t", "pos", "aim", "lens", "spans", "channels"}

A key is where the camera IS at that time, relative to what it looks at:
  look     a subject's name, or weights {"voyager": 0.6, "earth": 0.4} (group framing)
  dist     metres from the look point; az, el degrees round it (az 0 = camera on the -Y side
           looking +Y, 90 = on the +X side; el above the horizon). See direction().
  lens     focal length (mm, 36 mm sensor); screen (x, y) where the look point sits, in frames
           from the centre (-1/6 = the left third)
Anything left out carries over from the key before, so the moves of the vocabulary are keys:
  push in / pull back   change dist          orbit        change az
  crane up / down       change el            rack the lens change lens
  hand over the aim     change look (the camera pans to the new subject as it travels)
  hold                  a key a few seconds later with a small drift (a camera never dies)

Every key becomes keyframes on the camera's curves (cam.key.az, .el, .dist, .lens, .sx, .sy
and a weight per subject), stored in the motion file, so the journey is inspectable as curves.
az, el and log(dist) travel on minimum-jerk curves; the lens, the look weights and the screen
offsets on monotone curves, so a zoom never overshoots and the aim never swings past a
subject. No dependencies.
"""

import math

from ..core import kinematics as K
from ..core.curve import Curve

SENSOR_W, ASPECT = 36.0, 16 / 9


def _pt(subject, t):
    return list(subject(t)) if callable(subject) else list(subject)


def direction(az, el):
    """Unit vector from the subject to the camera: az degrees round +Z from -Y (0 = camera on the
    -Y side looking +Y, 90 = on the +X side), el degrees above the horizon."""
    a, e = math.radians(az), math.radians(el)
    return [math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e)]


def bearing(v):
    """(az, el, length) of a vector from a subject to a camera: the inverse of direction()."""
    L = K.norm(v) or 1e-12
    el = math.degrees(math.asin(max(-1.0, min(1.0, v[2] / L))))
    az = math.degrees(math.atan2(v[0], -v[1]))
    return az, el, L


def frame_distance(radius, size, lens):
    """How far away a sphere of `radius` must be to fill `size` of the frame's height."""
    vfov = 2 * math.atan((SENSOR_W / ASPECT) / (2 * lens))
    return radius / (size * math.tan(vfov / 2))


def compose(pos, aim, lens, screen):
    """Turn the camera so the aim point lands exactly `screen` = (x, y) frames from the centre.
    Turning a level camera re-levels its frame, so the first guess is corrected a few times."""
    x, y = screen
    if not x and not y:
        return aim
    d = K.norm(K.sub(aim, pos))
    half_w = d * math.tan(K.hfov(lens) / 2)
    half_h = half_w / ASPECT
    f = K.unit(K.sub(aim, pos))
    up = [0.0, 0.0, 1.0]
    right = K.unit(K.cross(f, up)) if abs(K.dot(f, up)) < 0.999 else [1.0, 0.0, 0.0]
    upv = K.cross(right, f)
    tx, ty = x, y
    look = list(aim)
    for _ in range(6):
        look = [aim[i] - right[i] * 2 * tx * half_w - upv[i] * 2 * ty * half_h for i in range(3)]
        s = K.screen(pos, look, lens, aim)
        if s is None:
            break
        ex, ey = x - s[0], y - s[1]
        if abs(ex) < 1e-9 and abs(ey) < 1e-9:
            break
        tx, ty = tx + ex, ty + ey
    return look


class Rig:
    def __init__(self, subjects, fps=30.0, interp="minjerk"):
        self.subjects = dict(subjects)
        self.fps, self.interp = float(fps), interp
        self.keys = []

    def key(self, t, look=None, dist=None, az=None, el=None, lens=None, screen=None, stop=False, label=None):
        prev = self.keys[-1] if self.keys else {"look": None, "dist": 10.0, "az": 0.0, "el": 10.0, "lens": 35.0, "screen": (0.0, 0.0)}
        look = prev["look"] if look is None else look
        if look is None:
            raise ValueError("the first key needs look=")
        w = {look: 1.0} if isinstance(look, str) else {k: float(v) for k, v in look.items()}
        for name in w:
            if name not in self.subjects:
                raise KeyError(f"unknown subject {name!r}")
        a = prev["az"] if az is None else float(az)
        if self.keys and az is not None:  # take the short way round from the key before
            a = prev["az"] + ((a - prev["az"] + 180) % 360 - 180)
        k = {"t": float(t), "look": look, "w": w, "dist": prev["dist"] if dist is None else float(dist), "az": a,
             "el": prev["el"] if el is None else float(el), "lens": prev["lens"] if lens is None else float(lens),
             "screen": tuple(prev["screen"] if screen is None else screen), "stop": stop, "label": label or ""}
        if self.keys and k["t"] <= prev["t"]:
            raise ValueError("keys must be in time order")
        self.keys.append(k)
        return self

    def curves(self):
        """The journey as keyed curves, named as they're stored in a motion file."""
        ks = self.keys
        stops = [k["t"] for k in ks if k["stop"]]
        mono = "monotone" if len(ks) > 1 else "linear"
        mj = self.interp if len(ks) > 1 else "linear"
        ch = {
            "cam.key.az": Curve(keys=[(k["t"], k["az"]) for k in ks], interp=mj, stops=stops),
            "cam.key.el": Curve(keys=[(k["t"], k["el"]) for k in ks], interp=mj, stops=stops),
            "cam.key.dist": Curve(keys=[(k["t"], math.log(k["dist"])) for k in ks], interp=mj, stops=stops),
            "cam.key.lens": Curve(keys=[(k["t"], math.log(k["lens"])) for k in ks], interp=mono, stops=stops),
            "cam.key.sx": Curve(keys=[(k["t"], k["screen"][0]) for k in ks], interp=mono, stops=stops),
            "cam.key.sy": Curve(keys=[(k["t"], k["screen"][1]) for k in ks], interp=mono, stops=stops),
        }
        used = sorted({n for k in ks for n in k["w"]})
        for n in used:
            ch["cam.key.look." + n] = Curve(keys=[(k["t"], k["w"].get(n, 0.0)) for k in ks], interp=mono, stops=stops)
        return ch

    def state(self, t, ch=None):
        ch = ch or self.curves()
        tot, piv = 0.0, [0.0, 0.0, 0.0]
        for name, c in ch.items():
            if name.startswith("cam.key.look."):
                w = max(0.0, c(t))
                s = _pt(self.subjects[name[13:]], t)
                piv = [piv[i] + w * s[i] for i in range(3)]
                tot += w
        piv = [x / (tot or 1.0) for x in piv]
        d = direction(ch["cam.key.az"](t), ch["cam.key.el"](t))
        r = math.exp(ch["cam.key.dist"](t))
        lens = math.exp(ch["cam.key.lens"](t))
        pos = [piv[i] + d[i] * r for i in range(3)]
        aim = compose(pos, piv, lens, (ch["cam.key.sx"](t), ch["cam.key.sy"](t)))
        return pos, aim, lens

    def sample(self, t0, t1):
        ch = self.curves()
        n = int(round((t1 - t0) * self.fps))
        ts = [t0 + k / self.fps for k in range(n + 1)]
        st = [self.state(t, ch) for t in ts]
        ks = self.keys
        spans = [{"lane": "camera", "t0": a["t"], "t1": b["t"], "label": b["label"]} for a, b in zip(ks, ks[1:])]
        return {"t": ts, "pos": [s[0] for s in st], "aim": [s[1] for s in st], "lens": [s[2] for s in st], "spans": spans, "channels": ch}


def frame_two(a, b, at_a, at_b, dist, lens, near=(0.0, 0.0)):
    """The bearing (az, el) from which subject point `a`, seen from `dist` away, sits at screen
    position `at_a` while point `b` sits at `at_b`: two subjects framed together. Searches round
    `near` (az, el) first. Returns (az, el, error in frames)."""
    def err(az, el):
        pos = [a[i] + x * dist for i, x in enumerate(direction(az, el))]
        aim = compose(pos, a, lens, at_a)
        s = K.screen(pos, aim, lens, b)
        if s is None:
            return 1e9
        return (s[0] - at_b[0]) ** 2 + (s[1] - at_b[1]) ** 2

    best = min(((err(az, el), az, el) for az in range(0, 360, 4) for el in range(-70, 71, 4)),
               key=lambda e: e[0] + 1e-6 * (((e[1] - near[0] + 180) % 360 - 180) ** 2 + (e[2] - near[1]) ** 2))
    _, az, el = best
    step = 2.0
    while step > 1e-3:
        moved = False
        for daz, de in ((step, 0), (-step, 0), (0, step), (0, -step)):
            if err(az + daz, el + de) < err(az, el):
                az, el, moved = az + daz, el + de, True
        if not moved:
            step /= 2
    return az, el, math.sqrt(err(az, el))
