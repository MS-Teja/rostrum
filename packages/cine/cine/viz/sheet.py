"""The motion sheet: a whole scene's animation, start to finish, in one image.

Rows share one time axis, with the narration's words and beats along the top:
  filmstrip (optional), moves (labelled spans),
  camera travel (distance along its path, a dot per frame: the spacing shows speed),
  view direction (yaw and pitch), subject scale on screen (log),
  sweep and zoom speed (reference band shaded, flags marked),
  actors (every other channel), composition (subjects' screen x and y).

A stop-start reads as a pile-up of frame dots in the middle of a move and a dip in the
speed row; a lurch as a kink; a reversal as a speed curve crossing zero.
"""

import base64
import html
import math
import os

from ..core import compose as C
from ..core import kinematics as K
from ..core import qa as Q

W = 1800
GUT = 200  # left gutter for row labels
PAD = 24
BG, INK, MUTE, GRID = "#111317", "#e9e7e2", "#8b8f98", "#262a31"
CAM, AIM, ZOOM, SWEEP, BAND, FLAG = "#ffb13b", "#7fb2ff", "#c792ea", "#56d4c4", "#2b3a34", "#ff5a5a"
COLORS = ["#ffb13b", "#7fb2ff", "#56d4c4", "#c792ea", "#f78c6c", "#c3e88d", "#ffcb6b", "#89ddff"]


class Sheet:
    def __init__(self, motion, title=None):
        self.m = motion
        self.title = title or motion.name
        self.parts, self.y = [], 0
        self.x0, self.x1 = GUT, W - PAD

    def x(self, t):
        return self.x0 + (t - self.m.t0) / max(1e-9, self.m.t1 - self.m.t0) * (self.x1 - self.x0)

    def add(self, s):
        self.parts.append(s)

    def label(self, y, h, text, sub=""):
        self.add(f'<text x="{GUT - 14}" y="{y + h / 2 - (6 if sub else -4):.1f}" fill="{INK}" font-size="14" text-anchor="end" font-weight="600">{html.escape(text)}</text>')
        if sub:
            self.add(f'<text x="{GUT - 14}" y="{y + h / 2 + 12:.1f}" fill="{MUTE}" font-size="11" text-anchor="end">{html.escape(sub)}</text>')

    def frame(self, y, h):
        self.add(f'<rect x="{self.x0}" y="{y}" width="{self.x1 - self.x0}" height="{h}" fill="#15181d" stroke="{GRID}"/>')
        for c in self.m.cuts:
            self.add(f'<line x1="{self.x(c):.1f}" y1="{y}" x2="{self.x(c):.1f}" y2="{y + h}" stroke="#555" stroke-dasharray="3 3"/>')

    def row(self, h):
        y = self.y
        self.y += h + 10
        return y

    # ── rows ─────────────────────────────────────────────────────────────────────────────
    def header(self):
        y = self.row(46)
        dur = self.m.t1 - self.m.t0
        self.add(f'<text x="{PAD}" y="{y + 30}" fill="{INK}" font-size="24" font-weight="700">{html.escape(self.title)}</text>')
        self.add(f'<text x="{W - PAD}" y="{y + 30}" fill="{MUTE}" font-size="14" text-anchor="end">{self.m.t0:.2f}–{self.m.t1:.2f}s · {dur:.1f}s · {self.m.fps:g} fps</text>')

    def timeline(self):
        h = 74
        y = self.row(h)
        self.label(y, h, "narration", "words · beats")
        self.frame(y, h)
        for k, (b0, b1, bid) in enumerate(self.m.beats):
            a, b = max(b0, self.m.t0), min(b1, self.m.t1)
            if b <= a:
                continue
            self.add(f'<rect x="{self.x(a):.1f}" y="{y}" width="{self.x(b) - self.x(a):.1f}" height="{h}" fill="{"#1b2028" if k % 2 else "#171b22"}"/>')
            self.add(f'<text x="{self.x(a) + 4:.1f}" y="{y + 14}" fill="{MUTE}" font-size="11">{html.escape(str(bid))}</text>')
        span = self.m.t1 - self.m.t0
        step = 1 if span <= 40 else 5 if span <= 200 else 10
        t = math.ceil(self.m.t0 / step) * step
        while t <= self.m.t1:
            self.add(f'<line x1="{self.x(t):.1f}" y1="{y + h - 6}" x2="{self.x(t):.1f}" y2="{y + h}" stroke="{MUTE}"/>')
            self.add(f'<text x="{self.x(t):.1f}" y="{y + h + 10}" fill="{MUTE}" font-size="10" text-anchor="middle">{t:g}s</text>')
            t += step
        if span <= 90:
            for tw, word in self.m.words:
                if self.m.t0 <= tw <= self.m.t1:
                    self.add(f'<text transform="translate({self.x(tw):.1f},{y + h - 8}) rotate(-55)" fill="{INK}" font-size="11">{html.escape(word)}</text>')
        self.y += 6

    def filmstrip(self, thumbs, h=96):
        """As many frames as fit side by side, each centred on its own time (a tick marks it)."""
        thumbs = sorted((t, p) for t, p in thumbs if os.path.exists(p))
        if not thumbs:
            return
        y = self.row(h)
        w = h * 16 / 9
        n = max(2, int((self.x1 - self.x0) // (w + 4)))
        span = self.m.t1 - self.m.t0
        picked = []
        for k in range(n):  # the thumb nearest each evenly spaced slot
            slot = self.m.t0 + span * (k + 0.5) / n
            best = min(thumbs, key=lambda tp: abs(tp[0] - slot))
            if best not in picked:
                picked.append(best)
        self.label(y, h, "picture", f"{len(picked)} frames, at their times")
        self.frame(y, h)
        slot_w = (self.x1 - self.x0) / n
        for k, (t, path) in enumerate(picked):
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            mime = "png" if path.endswith(".png") else "jpeg"
            x = self.x0 + k * slot_w + (slot_w - w) / 2
            self.add(f'<image x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" href="data:image/{mime};base64,{data}"/>')
            self.add(f'<line x1="{self.x(t):.1f}" y1="{y + h}" x2="{self.x(t):.1f}" y2="{y + h + 5}" stroke="{INK}"/>')
            self.add(f'<text x="{x + 3:.1f}" y="{y + 11}" fill="{INK}" font-size="9">{t:.1f}s</text>')

    def spans(self):
        sp = [s for s in self.m.spans if s.get("t1", 0) > self.m.t0 and s.get("t0", 0) < self.m.t1]
        if not sp:
            return
        lanes = sorted({s.get("lane", "camera") for s in sp})
        h = 24 * len(lanes) + 6
        y = self.row(h)
        self.label(y, h, "moves")
        self.frame(y, h)
        for s in sp:
            li = lanes.index(s.get("lane", "camera"))
            a, b = self.x(max(s["t0"], self.m.t0)), self.x(min(s["t1"], self.m.t1))
            yy = y + 4 + li * 24
            self.add(f'<rect x="{a:.1f}" y="{yy}" width="{max(2, b - a):.1f}" height="20" rx="4" fill="#2a2f39" stroke="#3a4250"/>')
            self.add(f'<text x="{a + 5:.1f}" y="{yy + 14}" fill="{INK}" font-size="11">{html.escape(s.get("label", ""))}</text>')

    def curve(self, name, sub, series, h=90, dots=False, zero=False, band=None, fmt="{:.2f}", robust=True, keys=()):
        """series: [(values, colour, label)] sampled at self.ts. Each series is drawn in the
        same scale (the row's min..max), with a dot per frame when dots=True."""
        y = self.row(h)
        self.label(y, h, name, sub)
        self.frame(y, h)
        vals = [v for s, _c, _l in series for v in s if v is not None and math.isfinite(v)]
        if not vals:
            return y
        lo, hi = min(vals), max(vals)
        clipped = False
        if robust and len(vals) > 20:  # one spike shouldn't flatten the row: scale to the typical range, mark the rest
            sv = sorted(vals)
            plo, phi = sv[int(0.02 * (len(sv) - 1))], sv[int(0.98 * (len(sv) - 1))]
            r = max(phi - plo, 1e-9)
            if hi > phi + 2 * r or lo < plo - 2 * r:
                lo, hi, clipped = max(lo, plo - 0.6 * r), min(hi, phi + 0.6 * r), True
        if band:
            lo, hi = min(lo, band[0]), max(hi, band[1])
        if zero:
            lo, hi = min(lo, 0.0), max(hi, 0.0)
        if hi - lo < 1e-12:
            hi = lo + 1.0
        vmin, vmax = min(vals), max(vals)  # the labels show the data's true extremes, not the padded axis
        pad = (hi - lo) * 0.08
        lo, hi = lo - pad, hi + pad
        Y = lambda v: y + h - (min(hi, max(lo, v)) - lo) / (hi - lo) * h  # noqa: E731
        if band:
            self.add(f'<rect x="{self.x0}" y="{Y(band[1]):.1f}" width="{self.x1 - self.x0}" height="{Y(band[0]) - Y(band[1]):.1f}" fill="{BAND}" opacity="0.7"/>')
        if zero and lo < 0 < hi:
            self.add(f'<line x1="{self.x0}" y1="{Y(0):.1f}" x2="{self.x1}" y2="{Y(0):.1f}" stroke="#444"/>')
        self.add(f'<text x="{self.x0 + 4}" y="{y + 12}" fill="{MUTE}" font-size="10">max {fmt.format(vmax)}</text>')
        self.add(f'<text x="{self.x0 + 4}" y="{y + h - 3}" fill="{MUTE}" font-size="10">min {fmt.format(vmin)}</text>')
        if clipped:  # outliers: a red tick at the edge where the curve leaves the row
            self.add(f'<text x="{self.x1 - 4}" y="{y + h - 4}" fill="#ff5a5a" font-size="10" text-anchor="end">clipped: spikes beyond the scale marked ▲</text>')
            for vals_, _c, _l in series:
                for t, v in zip(self.ts, vals_):
                    if v is not None and math.isfinite(v) and (v > hi or v < lo):
                        yy = y + 2 if v > hi else y + h - 8
                        self.add(f'<text x="{self.x(t):.1f}" y="{yy + 6:.1f}" fill="#ff5a5a" font-size="8" text-anchor="middle">{"▲" if v > hi else "▼"}</text>')
        for vals_, col, lab in series:
            pts, run = [], []
            for t, v, sgm in zip(self.ts, vals_, self.seg):
                if v is None or not math.isfinite(v):
                    continue
                if run and sgm != run[-1][2]:
                    pts.append(run)
                    run = []
                run.append((self.x(t), Y(v), sgm))
            if run:
                pts.append(run)
            for run in pts:
                d = " ".join(f"{px:.1f},{py:.1f}" for px, py, _ in run)
                self.add(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="1.6"/>')
                if dots:
                    for px, py, _ in run:
                        self.add(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="1.3" fill="{col}"/>')
        for t, v, col in keys:  # keyframes: a diamond where the curve passes through each key
            if self.m.t0 - 1e-6 <= t <= self.m.t1 + 1e-6:
                px, py = self.x(t), Y(v)
                self.add(f'<path d="M{px:.1f},{py - 5:.1f} L{px + 5:.1f},{py:.1f} L{px:.1f},{py + 5:.1f} L{px - 5:.1f},{py:.1f} Z" fill="{BG}" stroke="{col}" stroke-width="1.6"/>')
        if len(series) > 1:
            lx = self.x1 - 8
            for vals_, col, lab in reversed(series):
                self.add(f'<text x="{lx}" y="{y + 13}" fill="{col}" font-size="11" text-anchor="end">{html.escape(lab)}</text>')
                lx -= 8 + 7 * len(lab)
        return y

    def flags_lane(self, fl):
        h = 30
        y = self.row(h)
        self.label(y, h, "flags", f"{len(fl)} found")
        self.frame(y, h)
        for kind, t0, msg, t1 in fl:
            a, b = self.x(t0), self.x(max(t1, t0 + 1 / self.m.fps))
            self.add(f'<rect x="{a:.1f}" y="{y + 4}" width="{max(3, b - a):.1f}" height="{h - 8}" fill="{FLAG}" opacity="0.85"><title>{html.escape(kind)} {t0:.2f}s: {html.escape(msg)}</title></rect>')
            self.add(f'<text x="{a + 2:.1f}" y="{y - 2}" fill="{FLAG}" font-size="9">{html.escape(kind)}</text>')

    def shot_size(self):
        """Shot size and framing of the beat's subject, measured from its real shape: the size row
        is banded extreme wide .. extreme close, with the shot plan's asks as diamonds."""
        meas, subj = self.comp
        size, cx, cy, edge = [], [], [], []
        for i, sname in enumerate(subj):
            mm = meas.get(sname, [None] * len(subj))[i] if sname in meas else None
            ok = mm and mm.get("visible")
            size.append(math.log10(max(1e-3, mm["size"])) if ok else None)
            cx.append(mm["cx"] if ok else None)
            cy.append(mm["cy"] if ok else None)
            edge.append(mm["margin"] if ok else None)
        h = 110
        y = self.row(h)
        self.label(y, h, "shot size", "the beat's subject, from its shape")
        self.frame(y, h)
        lo, hi = math.log10(0.03), math.log10(3.0)
        Y = lambda v: y + h - (min(hi, max(lo, v)) - lo) / (hi - lo) * h  # noqa: E731
        shades = ["#1a1f27", "#1f2530"]
        for j, (name, a, b) in enumerate(C.SIZES):
            ya, yb = Y(math.log10(max(a, 0.03))), Y(math.log10(min(b, 3.0)))
            self.add(f'<rect x="{self.x0}" y="{yb:.1f}" width="{self.x1 - self.x0}" height="{ya - yb:.1f}" fill="{shades[j % 2]}"/>')
            self.add(f'<text x="{self.x0 + 4}" y="{(ya + yb) / 2 + 3:.1f}" fill="{MUTE}" font-size="9">{name}</text>')
        run = []
        for t, v, sname in zip(self.ts, size, subj):
            if v is None:
                if len(run) > 1:
                    self.add(f'<polyline points="{" ".join(run)}" fill="none" stroke="{ZOOM}" stroke-width="1.8"/>')
                run = []
                continue
            run.append(f"{self.x(t):.1f},{Y(v):.1f}")
        if len(run) > 1:
            self.add(f'<polyline points="{" ".join(run)}" fill="none" stroke="{ZOOM}" stroke-width="1.8"/>')
        prev = None
        for t, sname in zip(self.ts, subj):  # who the subject is, written where it changes
            if sname != prev and sname:
                self.add(f'<text x="{self.x(t) + 3:.1f}" y="{y + 12}" fill="{INK}" font-size="10">{html.escape(sname)}</text>')
                prev = sname
        for shot in getattr(self.m, "shots", []) or []:
            want = shot.get("size")
            if isinstance(want, str):
                a, b = C.size_band(want)
                v = math.log10(min(2.0, (a + b) / 2 if b < 50 else a * 1.3) if a > 0 else b * 0.6)
            elif want:
                v = math.log10(want)
            else:
                continue
            px, py = self.x(shot["t"]), Y(v)
            self.add(f'<path d="M{px:.1f},{py - 6:.1f} L{px + 6:.1f},{py:.1f} L{px:.1f},{py + 6:.1f} L{px - 6:.1f},{py:.1f} Z" fill="none" stroke="#ffffff" stroke-width="1.5"><title>plan: {html.escape(str(want))}</title></path>')
        self.curve("framing", "subject centre and nearest-edge margin (frames)",
                   [(cx, CAM, "centre x"), (cy, AIM, "centre y"), (edge, "#ff8a8a", "margin")], h=80, zero=True, band=(-1 / 6, 1 / 6), robust=False)

    def camera_keys(self):
        """The camera's keyed curves (from camera.rig), each key a diamond: the journey as an
        animator's graph editor shows it."""
        ch = self.m.channels
        if "cam.key.az" not in ch:
            return

        def rows(names, conv=lambda v: v):
            series, marks = [], []
            for j, (n, lab, col) in enumerate(names):
                if n not in ch:
                    continue
                c = ch[n]
                series.append(([conv(c(t)) for t in self.ts], col, lab))
                marks += [(t, conv(v), col) for t, v in (c.keys or [])]
            return series, marks

        s, k = rows([("cam.key.az", "azimuth", AIM), ("cam.key.el", "elevation", SWEEP)])
        self.curve("camera bearing", "degrees round the subject", s, h=80, fmt="{:.0f}°", keys=k, robust=False)
        s, k = rows([("cam.key.dist", "distance", ZOOM)], math.exp)
        s2, k2 = rows([("cam.key.lens", "lens", CAM)], math.exp)
        self.curve("camera distance", "metres from the subject (log)", [(list(map(math.log, s[0][0])), ZOOM, "log distance")],
                   h=70, keys=[(t, math.log(v), c) for t, v, c in k], robust=False)
        fov = [f"{v:.0f} mm = {math.degrees(K.hfov(v)):.0f}°" for _, v, _ in k2[:1]]
        self.curve("lens", "mm" + (f" · {fov[0]} wide" if fov else ""), s2, h=50, fmt="{:.0f}", keys=k2, robust=False)
        looks = sorted(n for n in ch if n.startswith("cam.key.look."))
        s, k = rows([(n, n[13:], COLORS[j % len(COLORS)]) for j, n in enumerate(looks)] + [("cam.key.sx", "screen x", "#cccccc"), ("cam.key.sy", "screen y", "#888888")])
        self.curve("aim", "look weights · screen offset", s, h=70, keys=k, robust=False)

    # ── assemble ─────────────────────────────────────────────────────────────────────────
    def build(self, thumbs=(), profile=None, band=None, max_actor_rows=6):
        m = self.m
        self.ts = m.times()
        cam = m.camera
        pos = [list(m.channels[cam["pos"]](t)) for t in self.ts]
        aim = [list(m.channels[cam["aim"]](t)) for t in self.ts]
        lens = [float(m.channels[cam["lens"]](t)) for t in self.ts]
        k = K.measure(self.ts, pos, aim, lens, m.cuts)
        self.k = k
        self.seg = k["segment"]
        self.fl = Q.flags(k, profile)
        self.comp = None
        if getattr(m, "shapes", None):
            self.comp = C.measure(m, self.ts)
            self.fl = sorted(self.fl + C.flags(m, self.comp), key=lambda f: f[1])
        # camera travel: distance along the path, normalised per stretch
        travel, acc = [0.0], 0.0
        for i in range(1, len(pos)):
            if self.seg[i] != self.seg[i - 1]:
                acc = 0.0
            else:
                acc += K.norm(K.sub(pos[i], pos[i - 1])) / max(1e-9, K.norm(K.sub(aim[i], pos[i])))
            travel.append(acc)
        yaw, pitch, scale = [], [], []
        prev = None
        for p, a, L in zip(pos, aim, lens):
            v = K.sub(a, p)
            yw = math.degrees(math.atan2(v[1], v[0]))
            steep = abs(v[2]) > 0.985 * K.norm(v)
            if prev is not None:
                yw = prev if steep else prev + ((yw - prev + 180) % 360 - 180)
            prev = yw
            yaw.append(yw)
            pitch.append(math.degrees(math.atan2(v[2], math.hypot(v[0], v[1]))))
            scale.append(-math.log(max(1e-12, K.norm(v) * math.tan(K.hfov(L) / 2))))
        self.header()
        self.timeline()
        self.filmstrip(list(thumbs))
        self.spans()
        self.camera_keys()
        self.curve("camera travel", "a dot per frame", [(travel, CAM, "travel")], h=100, dots=True)
        self.curve("view direction", "degrees", [(yaw, AIM, "yaw"), (pitch, SWEEP, "pitch")], h=90, fmt="{:.0f}°")
        self.curve("subject scale", "log; up = closer", [(scale, ZOOM, "scale")], h=80, dots=True)
        b = band or {}
        self.curve("sweep", "frame widths per second", [(k["sweep"], SWEEP, "sweep")], h=80, band=b.get("sweep"))
        self.curve("zoom", "log-scale per second", [(k["zoom"], ZOOM, "zoom")], h=80, zero=True, band=b.get("zoom"))
        self.curve("acceleration", "of the overall motion", [(k["energy_acc"], CAM, "accel")], h=70, zero=True)
        self.flags_lane(self.fl)
        actors = [n for n in m.channels if not n.startswith("cam.")][:max_actor_rows]
        for j, name in enumerate(actors):
            c = m.channels[name]
            vals = [c(t) for t in self.ts]
            if vals and isinstance(vals[0], list):
                series = [([v[i] for v in vals], COLORS[(j + i) % len(COLORS)], "xyz"[i] if len(vals[0]) == 3 else str(i)) for i in range(len(vals[0]))]
            else:
                series = [([float(v) for v in vals], COLORS[j % len(COLORS)], name)]
            self.curve(name, "actor", series, h=70, dots=True)
        if self.comp:
            self.shot_size()
        elif m.subjects:
            xs, ys_ = [], []
            for j, (sname, ch) in enumerate(m.subjects.items()):
                c = m.channels[ch]
                sx, sy = [], []
                for i, t in enumerate(self.ts):
                    s = K.screen(pos[i], aim[i], lens[i], list(c(t)))
                    inside = s is not None and abs(s[0]) <= 0.6 and abs(s[1]) <= 0.6  # out of frame: a gap
                    sx.append(s[0] if inside else None)
                    sy.append(s[1] if inside else None)
                xs.append((sx, COLORS[(2 * j) % len(COLORS)], f"{sname} x"))
                ys_.append((sy, COLORS[(2 * j + 1) % len(COLORS)], f"{sname} y"))
            self.curve("composition", "screen position, frames from centre", xs + ys_, h=90, zero=True, band=(-1 / 6, 1 / 6))
        H = self.y + PAD
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Inter, Helvetica, Arial, sans-serif">',
               f'<rect width="{W}" height="{H}" fill="{BG}"/>', '<g transform="translate(0,8)">', *self.parts, "</g></svg>"]
        return "\n".join(svg), H
