"""Dailies: a fast look at a scene before the slow render. The key poses and the midpoints between
them are rendered as stills (cine.blender.dailies, inside Blender), then packed here with
every automatic check, for the reviewer agent and for Teja:

    dailies/
      contact.png    every still, with a thirds grid, the safe area and each subject's box drawn
                     over it, and its checks written under it: one image to review
      stills/        the raw stills; masks/ the subject masks
      brief.md       the director's brief and the shot plan
      report.md      every flag (motion, composition, look) and the measures per still
      report.json    the same, for tools
      <name>.sheet.png, <name>.map.png, <name>.html   the motion sheet, the map, the viewer

    times = dailies.times_for(motion, extra=[9.2])          # keys, midpoints, and moments that matter
    shots = blender_dailies.render(scene, motion, times, out, subject=[...])   # in Blender
    dailies.pack(motion, shots, out, profile="profiles/film.json")
"""

import base64
import html
import json
import os

from .core import compose as C
from .core import qa as Q
from .core import kinematics as K
from .core import shape as S


def key_times(motion):
    c = motion.channels.get("cam.key.az")
    return [k[0] for k in (c.keys or [])] if c is not None and c.keys else []


def times_for(motion, extra=(), mids=True):
    ks = key_times(motion)
    ts = set(round(t, 3) for t in ks)
    if mids:
        ts |= {round((a + b) / 2, 3) for a, b in zip(ks, ks[1:])}
    ts |= {round(t, 3) for t in extra}
    return sorted(t for t in ts if motion.t0 <= t <= motion.t1)


def _flags_at(fl, t, tol):
    return [(k, msg) for k, t0, msg, t1 in fl if t0 - tol <= t <= t1 + tol]


def _box(m):
    return (m["cx"] - m["w"] / 2, m["cy"] - m["h"] / 2, m["w"], m["h"])


def contact(motion, shots, comp_at, flags_at, out, cols=3):
    """One image of every still with overlays and captions."""
    cw, ch, cap, gap = 560, 315, 76, 10
    rows = (len(shots) + cols - 1) // cols
    W, H = cols * cw + (cols + 1) * gap, rows * (ch + cap + gap) + gap + 40
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Inter, Helvetica, Arial, sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#111317"/>',
             f'<text x="{gap}" y="26" fill="#e9e7e2" font-size="18" font-weight="600">{html.escape(motion.name)}: dailies</text>']
    keys = [round(k, 3) for k in key_times(motion)]
    for i, s in enumerate(shots):
        x0 = gap + (i % cols) * (cw + gap)
        y0 = 40 + gap + (i // cols) * (ch + cap + gap)
        with open(s["still"], "rb") as f:
            data = base64.b64encode(f.read()).decode()
        parts.append(f'<svg x="{x0}" y="{y0}" width="{cw}" height="{ch}" overflow="hidden">')  # clips the overlays to the cell
        parts.append(f'<image x="0" y="0" width="{cw}" height="{ch}" href="data:image/png;base64,{data}"/>')
        X = lambda u: (u + 0.5) * cw  # noqa: E731
        Y = lambda v: (0.5 - v) * ch  # noqa: E731
        for u in (-1 / 6, 1 / 6):
            parts.append(f'<line x1="{X(u):.1f}" y1="{y0}" x2="{X(u):.1f}" y2="{y0 + ch}" stroke="#ffffff" stroke-opacity="0.25"/>')
            parts.append(f'<line x1="{x0}" y1="{Y(u):.1f}" x2="{x0 + cw}" y2="{Y(u):.1f}" stroke="#ffffff" stroke-opacity="0.25"/>')
        parts.append(f'<rect x="{X(-0.45):.1f}" y="{Y(0.45):.1f}" width="{cw * 0.9:.1f}" height="{ch * 0.9:.1f}" fill="none" stroke="#ffffff" stroke-opacity="0.18" stroke-dasharray="4 4"/>')
        meas = comp_at(s["t"])
        for name, m in meas.items():
            if not m.get("visible") or m.get("behind", 0) > 0:
                continue
            bx, by, bw, bh = _box(m)
            col = "#ff5a5a" if name == s["subject"] else "#7fb2ff"
            parts.append(f'<rect x="{X(bx):.1f}" y="{Y(by + bh):.1f}" width="{bw * cw:.1f}" height="{bh * ch:.1f}" fill="none" stroke="{col}" stroke-width="{1.6 if name == s["subject"] else 1}" stroke-opacity="0.85"/>')
            parts.append(f'<text x="{max(2, X(bx) + 3):.1f}" y="{max(11, Y(by + bh) + 11):.1f}" fill="{col}" font-size="10">{html.escape(name)}</text>')
        parts.append("</svg>")
        sm = meas.get(s["subject"], {})
        tag = "key" if round(s["t"], 3) in keys else "mid"
        size = f'{C.size_name(sm["size"])} {sm["size"]:.2f}' if sm.get("visible") else "out of frame"
        plan = next((p for p in (motion.shots or []) if abs(p["t"] - s["t"]) < 1e-3), None)
        lk = s.get("look", {})
        lk_txt = (f'exposure {lk["median"]:.2f} · contrast {lk["contrast"]:.1f}:1 · spread {lk["spread"]:.2f} · crushed {lk["crushed"]:.0%}'
                  + (f' · look: {s["planned_look"]}' if s.get("planned_look", "normal") != "normal" else "")) if lk.get("subject_visible") else "subject not in frame"
        line1 = f'{s["t"]:.2f} s · {tag} · {s["subject"]} · {size}' + (f' (plan: {plan["size"]})' if plan else "")
        parts.append(f'<text x="{x0}" y="{y0 + ch + 15}" fill="#e9e7e2" font-size="12" font-weight="600">{html.escape(line1)}</text>')
        parts.append(f'<text x="{x0}" y="{y0 + ch + 30}" fill="#b9bcc3" font-size="11">{html.escape(lk_txt)}</text>')
        fl = flags_at(s["t"]) + s.get("look_flags", [])
        words, lines_, cur = (", ".join(sorted({k for k, _ in fl})) + ": " + "; ".join(m for _, m in fl)).split() if fl else ["no", "flags"], [], ""
        for w_ in words:  # wrap to the cell's width, two lines at most
            if len(cur) + len(w_) + 1 > 92:
                lines_.append(cur)
                cur = w_
            else:
                cur = f"{cur} {w_}".strip()
        lines_.append(cur)
        if len(lines_) > 2:
            lines_ = [lines_[0], lines_[1][:88] + " …"]
        for j, ln in enumerate(lines_):
            parts.append(f'<text x="{x0}" y="{y0 + ch + 46 + j * 14}" fill="{"#ff8a8a" if fl else "#8b8f98"}" font-size="11">{html.escape(ln)}</text>')
    parts.append("</svg>")
    from .viz import raster

    raster.png("\n".join(parts), (W, H), out)
    return out


def pack(motion, shots, out_dir, profile=None, motion_path=None):
    """Write the dailies pack. Returns the report dict."""
    os.makedirs(out_dir, exist_ok=True)
    prof = json.load(open(profile)) if profile else None
    times = motion.times()
    ch, cam = motion.channels, motion.camera
    pos = [list(ch[cam["pos"]](t)) for t in times]
    aim = [list(ch[cam["aim"]](t)) for t in times]
    lens = [float(ch[cam["lens"]](t)) for t in times]
    k = K.measure(times, pos, aim, lens, motion.cuts)
    motion_flags = Q.flags(k, (prof or {}).get("flags"))
    comp_flags = C.flags(motion) if motion.shapes else []
    tol = 0.5 / motion.fps

    def comp_at(t):
        p, a, L = list(ch[cam["pos"]](t)), list(ch[cam["aim"]](t)), float(ch[cam["lens"]](t))
        return {n: C.measure_points(S.world(sh, motion, t), p, a, L, S.facing(sh, motion, t)) for n, sh in motion.shapes.items()}

    def flags_at(t):
        return _flags_at(motion_flags + comp_flags, t, tol)

    contact(motion, shots, comp_at, flags_at, os.path.join(out_dir, "contact.png"))
    stills = []
    for s in shots:
        sm = comp_at(s["t"]).get(s["subject"], {})
        stills.append({"t": s["t"], "subject": s["subject"], "still": os.path.relpath(s["still"], out_dir),
                       "composition": {k_: (round(v, 3) if isinstance(v, float) else v) for k_, v in sm.items()},
                       "look": {k_: (round(v, 3) if isinstance(v, float) else v) for k_, v in s.get("look", {}).items()},
                       "occluded": s.get("occluded"), "flags": [list(f) for f in flags_at(s["t"]) + s.get("look_flags", [])]})
    report = {"scene": motion.name, "motion_flags": [list(f) for f in motion_flags], "composition_flags": [list(f) for f in comp_flags],
              "stills": stills, "profile": (prof or {}).get("name")}
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(report, f, indent=1)
    lines = [f"# {motion.name}: dailies report", "",
             f"Motion flags ({report['profile'] or 'default'} profile): {len(motion_flags)}. Composition flags: {len(comp_flags)}. "
             f"Look flags: {sum(len(s.get('look_flags', [])) for s in shots)}.", ""]
    for title, fl in (("Motion", motion_flags), ("Composition", comp_flags)):
        if fl:
            lines.append(f"## {title} flags")
            lines += [f"- {k_} at {t0:.2f}–{t1:.2f} s: {msg}" for k_, t0, msg, t1 in fl]
            lines.append("")
    lines += ["## Stills", "", "| t | subject | size | centre x | margin | covers | exposure | contrast | spread | crushed | blocked | flags |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in stills:
        c, lk = s["composition"], s["look"]
        size = f'{C.size_name(c["size"])} {c["size"]:.2f}' if c.get("visible") else "out"

        def g(d, key, fmt="{:.2f}"):
            return fmt.format(d[key]) if isinstance(d.get(key), (int, float)) else "–"

        lines.append(f'| {s["t"]:.2f} | {s["subject"]} | {size} | {g(c, "cx")} | {g(c, "margin")} | {g(c, "cover", "{:.0%}")} | '
                     f'{g(lk, "median")} | {g(lk, "contrast", "{:.1f}")} | {g(lk, "spread")} | {g(lk, "crushed", "{:.0%}")} | '
                     f'{"–" if s["occluded"] is None else format(s["occluded"], ".0%")} | {"; ".join(f[0] for f in s["flags"]) or "–"} |')
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    brief = [f"# {motion.name}: brief and shot plan", "", motion.brief or "(no brief written)", "", "## Shot plan (keys)", "",
             "| t | subject | size | angle | side | lens | motive | look | achieved |", "|---|---|---|---|---|---|---|---|---|"]
    for p in motion.shots or []:
        a = p.get("achieved", {})
        brief.append(f'| {p["t"]:.2f} | {p.get("subject")} | {p.get("size")} | {p.get("angle")} | {p.get("side")} | {p.get("lens")} | {p.get("motive", "")} | {p.get("look", "normal")} | {a.get("named", "")} {a.get("size", "")} |')
    with open(os.path.join(out_dir, "brief.md"), "w") as f:
        f.write("\n".join(brief) + "\n")
    if motion_path:
        from .see import see

        see(motion_path, out=out_dir, png=True, profile=profile)
    return report
