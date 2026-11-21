"""Does on-screen text hold still? Teja's rule: a label takes one place when it appears, holds it,
and leaves; values aren't left ticking. His note on b07's first render, where labels dodged lines
and readouts ticked every frame: "it's too messy. Texts are constantly changing, they should be at
a constant place, not move all around the place."

    from cine.core import text
    text.flags(labels, fps=30, width=1920)   # [(kind, t, message, t_end)]

Each label is a dict of per-frame values, as the stage drew it:
    name     what to call it in a flag
    text     its text (a string, or one per frame if it changes)
    at       the text's centre on screen, pixels from the frame's centre (None when off screen)
    anchor   the point it labels, the same way (None for a caption with no anchor)
    opacity  0..1

The flags (limits in RULES, set from reading speed and Teja's note, not tuned to a scene):
    brief      on screen for less than its reading time: 0.5 s + 0.06 s a character, at least 1 s
    moving     sliding across the screen (faster than a tenth of the frame's width a second for
               more than 0.3 s): show it while its subject holds still, or leave it out
    re-placed  its place beside its anchor changes while it's showing
    ticking    its text changes again within 1.5 s (a counter): show held values instead
    flash      it leaves and comes back within 1 s
    busy       more than 4 labels appear or change within a second, or more than 6 show at once
"""

import math

RULES = {"read_base": 0.5, "read_char": 0.06, "read_min": 1.0, "max_speed": 0.1, "moving_for": 0.3, "replace_px": 3.0,
         "tick": 1.5, "flash": 1.0, "max_events": 4, "max_on": 6, "shown": 0.5}


def _text_at(lb, i):
    tx = lb.get("text", "")
    return tx if isinstance(tx, str) else tx[i]


def appearances(lb, threshold=0.5):
    """[(i0, i1)] frame ranges where the label shows (opacity at or above the threshold)."""
    out, start = [], None
    op = lb["opacity"]
    for i, v in enumerate(op):
        on = v >= threshold and lb["at"][i] is not None
        if on and start is None:
            start = i
        if not on and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(op) - 1))
    return out


def flags(labels, fps, width, rules=None, t0=0.0):
    r = dict(RULES, **(rules or {}))
    dt = 1.0 / fps
    out, events, counts = [], [], {}
    for lb in labels:
        name = lb["name"]
        apps = appearances(lb, r["shown"])
        for k, (i0, i1) in enumerate(apps):
            ta, tb = t0 + i0 * dt, t0 + (i1 + 1) * dt
            events.append((ta, name))
            for i in range(i0, i1 + 1):
                counts[i] = counts.get(i, 0) + 1
            txt = _text_at(lb, i0)
            need = max(r["read_min"], r["read_base"] + r["read_char"] * len(txt))
            if tb - ta < need:
                out.append(("brief", ta, f'"{txt}" shows for {tb - ta:.2f} s (needs {need:.2f} s to read)', tb))
            if k and (i0 - apps[k - 1][1]) * dt < r["flash"]:
                out.append(("flash", ta, f'"{txt}" leaves and comes back within {(i0 - apps[k - 1][1]) * dt:.2f} s', tb))
            fast, worst, first = 0.0, 0.0, None
            moved, last_change, ticks = 0.0, ta, []
            for i in range(i0 + 1, i1 + 1):
                a, b = lb["at"][i - 1], lb["at"][i]
                if a is None or b is None:
                    continue
                v = math.hypot(b[0] - a[0], b[1] - a[1]) / dt / width
                if v > r["max_speed"]:
                    fast += dt
                    worst = max(worst, v)
                    first = first if first is not None else t0 + i * dt
                anc0, anc1 = (lb.get("anchor") or [None] * len(lb["at"]))[i - 1], (lb.get("anchor") or [None] * len(lb["at"]))[i]
                if anc0 is not None and anc1 is not None:
                    d = math.hypot((b[0] - anc1[0]) - (a[0] - anc0[0]), (b[1] - anc1[1]) - (a[1] - anc0[1]))
                    moved = max(moved, d)
                if _text_at(lb, i) != _text_at(lb, i - 1):
                    t = t0 + i * dt
                    events.append((t, name))
                    if t - last_change < r["tick"]:
                        ticks.append((t, t - last_change))
                    last_change = t
            if ticks:
                out.append(("ticking", ticks[0][0], f'"{name}" changes text {len(ticks)} times within {r["tick"]} s of the last '
                                                    f'(every {min(g for _, g in ticks):.2f} s at the fastest): show held values', ticks[-1][0]))
            if fast > r["moving_for"]:
                out.append(("moving", first, f'"{txt}" slides across the screen for {fast:.2f} s (up to {worst:.2f} of the frame\'s width a second)', tb))
            if moved > r["replace_px"]:
                out.append(("re-placed", ta, f'"{txt}" moves {moved:.0f} px beside its anchor while showing', tb))
    events.sort()
    j = 0
    busy_until = -1.0
    for i, (t, _) in enumerate(events):
        while events[j][0] < t - 1.0:
            j += 1
        names = sorted({n for _, n in events[j:i + 1]})  # distinct labels (one label changing often is "ticking")
        if len(names) > r["max_events"] and t > busy_until:
            out.append(("busy", events[j][0], f"{len(names)} labels appear or change within a second ({', '.join(names)})", t))
            busy_until = t + 1.0
    crowded = [i for i, c in sorted(counts.items()) if c > r["max_on"]]
    if crowded:
        out.append(("busy", t0 + crowded[0] * dt, f"{max(counts.values())} labels show at once (limit {r['max_on']})", t0 + crowded[-1] * dt))
    return sorted(out, key=lambda f: f[1])
