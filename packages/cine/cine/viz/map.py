"""The director's map: the camera's whole journey through a scene, seen from above and from the
side. The path is coloured by time (blue at the start, orange at the end), with a dot per frame
(close dots = slow, spread dots = fast), a frustum glyph and timestamp every second, and thin
lines to the aim point. Subjects leave grey trails. Cuts break the path.
"""

import html
import math

from ..core import kinematics as K

BG, INK, MUTE, GRID = "#111317", "#e9e7e2", "#8b8f98", "#262a31"


def _col(u):
    # blue -> teal -> orange
    stops = [(0.0, (90, 140, 255)), (0.5, (86, 212, 196)), (1.0, (255, 177, 59))]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if u <= b:
            f = (u - a) / (b - a)
            return "#%02x%02x%02x" % tuple(int(ca[i] + (cb[i] - ca[i]) * f) for i in range(3))
    return "#ffb13b"


def draw(motion, size=860):
    m = motion
    ts = m.times()
    cam = m.camera
    pos = [list(m.channels[cam["pos"]](t)) for t in ts]
    aim = [list(m.channels[cam["aim"]](t)) for t in ts]
    lens = [float(m.channels[cam["lens"]](t)) for t in ts]
    subs = {name: [list(m.channels[ch](t)) for t in ts] for name, ch in m.subjects.items()}
    seg = K.measure(ts, pos, aim, lens, m.cuts)["segment"] if len(ts) > 2 else [0] * len(ts)
    views = [("from above", 0, 1), ("from the side", 0, 2)]
    parts = []
    W, H = size * 2 + 60, size + 100
    data = {"views": []}
    for vi, (title, ax, ay) in enumerate(views):
        ox = 20 + vi * (size + 20)
        oy = 84
        pts = pos + aim + [p for s in subs.values() for p in s]
        lo = [min(p[ax] for p in pts), min(p[ay] for p in pts)]
        hi = [max(p[ax] for p in pts), max(p[ay] for p in pts)]
        span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1.0
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        sc = (size - 40) / span

        def P(p):
            return ox + size / 2 + (p[ax] - cx) * sc, oy + size / 2 - (p[ay] - cy) * sc

        parts.append(f'<rect x="{ox}" y="{oy}" width="{size}" height="{size}" fill="#15181d" stroke="{GRID}"/>')
        parts.append(f'<text x="{ox + 10}" y="{oy - 12}" fill="{INK}" font-size="16" font-weight="600">{title}</text>')
        parts.append(f'<text x="{ox + size - 10}" y="{oy - 12}" fill="{MUTE}" font-size="12" text-anchor="end">grid {span / 10:.3g} units</text>')
        for g in range(1, 10):
            parts.append(f'<line x1="{ox + g * size / 10}" y1="{oy}" x2="{ox + g * size / 10}" y2="{oy + size}" stroke="{GRID}" stroke-width="0.6"/>')
            parts.append(f'<line x1="{ox}" y1="{oy + g * size / 10}" x2="{ox + size}" y2="{oy + g * size / 10}" stroke="{GRID}" stroke-width="0.6"/>')
        for name, trail in subs.items():
            d = " ".join("%.1f,%.1f" % P(p) for p in trail)
            parts.append(f'<polyline points="{d}" fill="none" stroke="#6b707a" stroke-width="2" stroke-dasharray="4 3"/>')
            x, y = P(trail[0])
            parts.append(f'<text x="{x + 6:.1f}" y="{y - 6:.1f}" fill="{MUTE}" font-size="12">{html.escape(name)}</text>')
        n = len(ts)
        for i in range(1, n):
            if seg[i] != seg[i - 1]:
                continue
            (x0, y0), (x1, y1) = P(pos[i - 1]), P(pos[i])
            parts.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{_col(i / max(1, n - 1))}" stroke-width="2.4"/>')
        for i in range(n):
            x, y = P(pos[i])
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.5" fill="{_col(i / max(1, n - 1))}"/>')
        step = max(1, int(round(m.fps)))
        for i in range(0, n, step):
            p, a = pos[i], aim[i]
            x, y = P(p)
            ax_, ay_ = P(a)
            parts.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{ax_:.1f}" y2="{ay_:.1f}" stroke="{_col(i / max(1, n - 1))}" stroke-width="0.6" opacity="0.5"/>')
            # frustum glyph: two rays at +-half the horizontal field of view, in this view's plane
            ang = math.atan2(ay_ - y, ax_ - x)
            half = K.hfov(lens[i]) / 2
            L = 34
            pa = (x + L * math.cos(ang - half), y + L * math.sin(ang - half))
            pb = (x + L * math.cos(ang + half), y + L * math.sin(ang + half))
            parts.append(f'<path d="M{x:.1f},{y:.1f} L{pa[0]:.1f},{pa[1]:.1f} L{pb[0]:.1f},{pb[1]:.1f} Z" fill="{_col(i / max(1, n - 1))}" opacity="0.28" stroke="{_col(i / max(1, n - 1))}" stroke-width="0.8"/>')
            parts.append(f'<text x="{x + 5:.1f}" y="{y + 14:.1f}" fill="{INK}" font-size="10">{ts[i]:.0f}s</text>')
        data["views"].append({"ox": ox, "oy": oy, "pts": [[round(v, 1) for v in P(p)] for p in pos]})
    legend = f'<text x="20" y="28" fill="{INK}" font-size="20" font-weight="700">{html.escape(m.name)}: the camera\'s journey</text>'
    legend += f'<text x="20" y="50" fill="{MUTE}" font-size="12">colour = time (blue → orange) · a dot per frame · a frustum and time every second · grey = subjects</text>'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Inter, Helvetica, Arial, sans-serif">'
           f'<rect width="{W}" height="{H}" fill="{BG}"/>{legend}' + "".join(parts) + '<g id="glyphs"></g></svg>')
    return svg, (W, H), data
