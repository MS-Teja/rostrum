"""Composition, measured: where each subject's real shape lands in the frame, every frame, and
the cinematographer's rules checked against it (crew/cinematographer.md).

Screen units: x across the frame width and y up the frame height, both -0.5..0.5 (so the
frame is a unit square and areas are fractions of the frame).

Per shape and frame:
  size     the larger of the shape's height and width as fractions of the frame (shot size)
  out      fraction of its bounding box outside the frame (0 = all in)
  margin   distance from its box to the nearest frame edge (negative = crossing it)
  cover    fraction of the frame its silhouette (convex hull) covers
  depth    median distance along the view; cx, cy its box centre; head the room above it
  lead     room ahead of it in the direction it faces (+ = room ahead, - = it faces the edge)
Flags (merged into the sheet's flags). Framing faults count only in frames the viewer gets to
look at (the subject's size changing under 25% a second, at least 90% of the aim on it, and
the aim not changing hands within 0.5 s) and only if they last 0.4 s or more:
  edge      the beat's subject grazes the frame edge: touching or barely cut (cut 0-20%)
  clutter   a context shape nearer than the subject covers more than a quarter of the frame
            (unless it's marked "frame": True, a planned dark foreground frame, like a corridor's walls)
  dominant  another shape takes the frame over from the subject: it covers over 35% of the
            frame and more than twice the subject's share (a "close-up" of a part that is
            really a shot of the whole machine). A part shown medium or closer is exempt from
            the machine that holds it: that's its ground.
  lead      the subject faces the near edge with the open frame behind it
  cramped   a medium or close subject with under 2% headroom
  size      at a key, the subject's size is outside the size its shot plan asked for
  near      the camera is inside a solid shape's extent (its bounding box, grown 5%); drawn,
            hollow shapes (a ring, a region) are marked "solid": False, and a shape the camera
            means to enter (a push-through) carries "enter_after": the time it goes in
  drift     (off by default; rules={"drift": True}) the camera moves for 2 s or more without
            changing the frame. Slow, steady movement under the voice is a good choice; the
            motion checks flag what's actually aimless (qa: wander, fidget)
No dependencies.
"""

from . import kinematics as K
from . import shape as S

SIZES = [  # name, low, high (fraction of frame), from crew/cinematographer.md
    ("extreme wide", 0.0, 0.10), ("wide", 0.10, 0.30), ("medium wide", 0.30, 0.55),
    ("medium", 0.55, 0.80), ("close", 0.80, 1.10), ("extreme close", 1.10, 99.0),
]
RULES = {"graze_margin": 0.05, "decisive_cut": 0.20, "clutter": 0.25, "dominant": 0.35, "dominant_ratio": 2.0, "cramped": 0.02, "lead": 0.04,
         "min_dur": 0.4,  # s: a framing fault must last this long to count (an edge sweeping past during a push doesn't)
         "drift_window": 2.0, "drift_slow": 0.15, "drift_size": 0.12, "drift_place": 0.05, "drift_turn": 15.0,
         "transit": 0.25,  # per s: while the subject's size changes faster than this (a push, a pull) the eye follows
         "handover": 0.5}  # s: the aim has just changed hands; framing is in flux
LASTING = ("edge", "cramped", "clutter", "dominant", "lead")


def size_name(s):
    for name, lo, hi in SIZES:
        if lo <= s < hi:
            return name
    return SIZES[-1][0]


def size_band(name):
    for n, lo, hi in SIZES:
        if n == name:
            return lo, hi
    raise KeyError(f"unknown shot size {name!r}; one of {[s[0] for s in SIZES]}")


def _hull(pts):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _clip(poly, lo=-0.5, hi=0.5):
    """Sutherland-Hodgman clip of a polygon to the frame square."""
    def edge(points, inside, cut):
        out = []
        for i in range(len(points)):
            a, b = points[i - 1], points[i]
            if inside(b):
                if not inside(a):
                    out.append(cut(a, b))
                out.append(b)
            elif inside(a):
                out.append(cut(a, b))
        return out

    def at_x(x):
        return lambda a, b: (x, a[1] + (b[1] - a[1]) * (x - a[0]) / ((b[0] - a[0]) or 1e-12))

    def at_y(y):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (y - a[1]) / ((b[1] - a[1]) or 1e-12), y)

    p = list(poly)
    for inside, cut in ((lambda q: q[0] >= lo, at_x(lo)), (lambda q: q[0] <= hi, at_x(hi)),
                        (lambda q: q[1] >= lo, at_y(lo)), (lambda q: q[1] <= hi, at_y(hi))):
        if not p:
            break
        p = edge(p, inside, cut)
    return p


def _area(poly):
    return abs(sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))) / 2 if len(poly) >= 3 else 0.0


def inside_extent(points, pos, grow=0.05):
    lo = [min(p[k] for p in points) for k in range(3)]
    hi = [max(p[k] for p in points) for k in range(3)]
    pad = [(hi[k] - lo[k]) * grow + 1e-6 for k in range(3)]
    return all(lo[k] - pad[k] <= pos[k] <= hi[k] + pad[k] for k in range(3))


def measure_points(points, pos, aim, lens, face=None):
    """Composition of one shape (world points) from one camera."""
    proj = [K.screen(pos, aim, lens, p) for p in points]
    vis = [q for q in proj if q is not None]
    behind = 1 - len(vis) / max(1, len(points))
    near = behind > 0 and inside_extent(points, pos)
    if not vis or len(vis) < 2:
        return {"visible": False, "behind": behind, "near": near}
    xs, ys = [q[0] for q in vis], [q[1] for q in vis]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = x1 - x0, y1 - y0
    bb = max(w * h, 1e-12)
    inside = max(0.0, min(x1, 0.5) - max(x0, -0.5)) * max(0.0, min(y1, 0.5) - max(y0, -0.5))
    hull = _hull([(q[0], q[1]) for q in vis])
    cover = _area(_clip(hull)) if len(hull) >= 3 else 0.0
    zs = sorted(q[2] for q in vis)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    m = {"visible": True, "behind": behind, "near": near, "size": max(w, h), "w": w, "h": h, "cx": cx, "cy": cy,
         "out": 1 - inside / bb, "margin": min(0.5 - x1, x0 + 0.5, 0.5 - y1, y0 + 0.5), "cover": cover,
         "depth": zs[len(zs) // 2], "head": 0.5 - y1, "lead": None}
    if face is not None:  # which way it faces on screen, from a point a little ahead of its centre
        c, r = S.centre(points)
        ahead = K.screen(pos, aim, lens, [c[k] + face[k] * r for k in range(3)])
        here = K.screen(pos, aim, lens, c)
        if ahead and here:
            fx = ahead[0] - here[0]
            if abs(fx) > 0.25 * max(1e-9, abs(ahead[1] - here[1]) + abs(fx)):
                m["lead"] = -cx if fx > 0 else cx  # facing right: room ahead = how far left of centre it sits
    return m


def _drift(motion, times, meas, subj, r):
    """Frames where the camera moves without changing the frame (see the module notes)."""
    import math

    ch, cam = motion.channels, motion.camera
    pos = [list(ch[cam["pos"]](t)) for t in times]
    aim = [list(ch[cam["aim"]](t)) for t in times]
    lens = [float(ch[cam["lens"]](t)) for t in times]
    k = K.measure(times, pos, aim, lens, getattr(motion, "cuts", ()))
    dt = 1 / motion.fps
    w = int(r["drift_window"] / dt)
    out = []
    for i in range(0, len(times) - w):
        j = i + w
        s = subj[i]
        if s is None or s not in meas or subj[j] != s:
            continue
        e = k["energy"][i:j + 1]
        if not (min(e) > 0.02 and max(e) < r["drift_slow"]):
            continue
        a, b = meas[s][i], meas[s][j]
        if not (a.get("visible") and b.get("visible")):
            continue
        if abs(math.log(max(1e-6, b["size"])) - math.log(max(1e-6, a["size"]))) > r["drift_size"]:
            continue
        if abs(b["cx"] - a["cx"]) > r["drift_place"] or abs(b["cy"] - a["cy"]) > r["drift_place"]:
            continue
        c, _ = S.centre(S.world(motion.shapes[s], motion, times[i]))
        va, vb = K.sub(pos[i], c), K.sub(pos[j], c)
        if math.degrees(K.angle(va, vb)) > r["drift_turn"]:
            continue
        out.append(("drift", times[i], f"the camera moves for {r['drift_window']:.0f} s without changing the frame on {s}: hold still, or move with a purpose"))
    return out


def _contains(motion, outer, inner, t):
    """Whether shape `outer` holds shape `inner` (inner's centre inside outer's bounding box)."""
    po, pi = S.world(motion.shapes[outer], motion, t), S.world(motion.shapes[inner], motion, t)
    c, _ = S.centre(pi)
    return all(min(p[k] for p in po) <= c[k] <= max(p[k] for p in po) for k in range(3))


def _look_weight(motion, name, t):
    """The share of the aim on subject `name` at time t (1.0 when the camera has no look curves)."""
    ws = {n[13:]: max(0.0, c(t)) for n, c in motion.channels.items() if n.startswith("cam.key.look.")}
    tot = sum(ws.values())
    return ws.get(name, 0.0) / tot if tot > 0 else 1.0


def beat_subject(motion, t):
    """The camera's look subject at time t: the heaviest look weight (from camera.rig)."""
    best, wbest = None, 0.0
    for name, c in motion.channels.items():
        if name.startswith("cam.key.look."):
            w = c(t)
            if w > wbest:
                best, wbest = name[13:], w
    return best


def measure(motion, times=None):
    """{shape name: [per-frame measure dicts]} and the per-frame beat subject."""
    times = times or motion.times()
    ch, cam = motion.channels, motion.camera
    out = {name: [] for name in motion.shapes}
    subj = []
    for t in times:
        pos, aim, lens = list(ch[cam["pos"]](t)), list(ch[cam["aim"]](t)), float(ch[cam["lens"]](t))
        for name, sh in motion.shapes.items():
            out[name].append(measure_points(S.world(sh, motion, t), pos, aim, lens, S.facing(sh, motion, t)))
        subj.append(beat_subject(motion, t))
    return out, subj


def flags(motion, meas=None, rules=None):
    """Composition flags: (kind, t0, message, t1), merged like qa.flags."""
    from .qa import merge
    r = dict(RULES)
    r.update(rules or {})
    import math

    times = motion.times()
    meas, subj = meas or measure(motion, times)
    dt = 1 / motion.fps
    held = []  # frames the viewer gets to look at: the subject's size steady, the aim settled
    for i, t in enumerate(times):
        s, a, b = subj[i], max(0, i - 3), min(len(times) - 1, i + 3)
        ok = s in meas and meas[s][a].get("visible") and meas[s][b].get("visible") and subj[a] == s == subj[b]
        rate = abs(math.log(max(1e-6, meas[s][b]["size"])) - math.log(max(1e-6, meas[s][a]["size"]))) / ((b - a) * dt) if ok else 0.0
        w = int(r["handover"] / dt)
        recent = any(subj[j] != s for j in range(max(0, i - w), min(len(times), i + w + 1)))
        mixing = _look_weight(motion, s, t) < 0.9  # the aim is still travelling between subjects
        held.append(not (rate > r["transit"] or recent or mixing))
    out = []
    for i, t in enumerate(times):
        s = subj[i]
        for name, ms in meas.items():
            m = ms[i]
            sh = motion.shapes[name]
            entered = sh.get("enter_after") is not None and t >= sh["enter_after"]  # a planned push-through
            if m.get("near") and sh.get("solid", True) and not entered:
                out.append(("near", t, f"the camera is inside {name}'s extent"))
        if s not in meas or not held[i]:
            continue
        m = meas[s][i]
        if not m.get("visible") or m["behind"] > 0:
            out.append(("edge", t, f"{s} is out of frame or behind the camera"))
            continue
        if (m["out"] == 0 and m["margin"] < r["graze_margin"]) or 0 < m["out"] < r["decisive_cut"]:
            out.append(("edge", t, f"{s} grazes the frame edge (cut {m['out']:.0%}, margin {m['margin']:.3f})"))
        if m["lead"] is not None and m["lead"] < -r["lead"] and m["size"] < 0.8:
            out.append(("lead", t, f"{s} faces the near edge (lead room {m['lead']:.2f})"))
        if 0.55 <= m["size"] < 1.1 and m["out"] == 0 and m["head"] < r["cramped"]:
            out.append(("cramped", t, f"{s} has {m['head']:.0%} headroom"))
        for name, ms in meas.items():
            c = ms[i]
            if name == s or not c.get("visible") or motion.shapes[name].get("role", "subject") != "context":
                continue
            if _contains(motion, s, name, t):
                continue  # a part of the subject itself isn't clutter in front of it
            if c["depth"] < m["depth"] and c["cover"] > r["clutter"] and not motion.shapes[name].get("frame"):
                out.append(("clutter", t, f"{name} (nearer than {s}) covers {c['cover']:.0%} of the frame"))
        for name, ms in meas.items():
            c = ms[i]
            if name == s or not c.get("visible") or c["behind"] > 0:
                continue
            if m["size"] >= 0.55 and _contains(motion, name, s, t):
                continue  # a part shown medium or closer: the machine round it is its ground, not a rival
            if motion.shapes[name].get("frame"):
                continue  # a planned foreground frame (a corridor's walls) frames the subject, it doesn't rival it
            if c["cover"] > r["dominant"] and c["cover"] > r["dominant_ratio"] * m["cover"]:
                out.append(("dominant", t, f"{name} covers {c['cover']:.0%} of the frame; the subject {s} only {m['cover']:.0%}"))
    if r.get("drift"):  # off by default: slow, steady movement under the voice is fine (qa flags wander and fidget)
        out += _drift(motion, times, meas, subj, r)
    for shot in getattr(motion, "shots", []) or []:
        name, want = shot.get("subject"), shot.get("size")
        if not want or name not in meas:
            continue
        i = min(range(len(times)), key=lambda j: abs(times[j] - shot["t"]))
        m = meas[name][i]
        lo, hi = size_band(want) if isinstance(want, str) else (want * 0.9, want * 1.1)
        if m.get("visible") and not (lo <= m["size"] < hi):
            out.append(("size", times[i], f"{name} is {size_name(m['size'])} ({m['size']:.2f}); the plan asked for {want}"))
    return [f for f in merge(out, dt) if f[0] not in LASTING or f[3] - f[1] >= r["min_dur"] - dt / 2]
