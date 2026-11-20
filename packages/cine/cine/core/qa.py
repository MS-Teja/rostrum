"""Flags: what a viewer would feel as wrong in a camera's motion, found from its kinematics
(kinematics.measure). Thresholds come from a profile (profiles/*.json). The speed limits
(fast, reversal) can follow the voiceover: pass scale = the voice's pace per frame
(core/voice.py), and a fast, excited line allows a brisker camera than a slow, quiet one.

    hiccup     the camera slows almost to a stop between two moves and starts again within
               a second: the stop-start feel. A deliberate hold (still for 1.2 s or more) is not
               a hiccup: it's a choice, and the voiceover is usually why
    reversal   it turns or zooms one way, then snaps back the other way: the rate passes through
               zero steeply, with real motion on both sides (a camera easing from a push into a
               pull passes through zero gently, and that is fine)
    jerk       acceleration that changes abruptly (a lurch)
    fast       sweep or zoom faster than the references' fast end
    dead       nothing moves for longer than the references ever sit still, and no one is
               speaking (a still frame under the voice is a choice, not a dead scene)
    jump       a discontinuity within a stretch that should be continuous (a hidden cut)
    wander     the camera changes direction (pan, tilt or zoom) twice or more within 3 s: it
               meanders instead of going somewhere. A slow, steady move is fine; a wandering one isn't
    fidget     a small, short move between holds (under 1.2 s, never getting going): hold instead,
               or make it a real move
"""

DEFAULT = {
    "moving": 0.02,      # frames/s (or log-units/s): below this the picture is at rest
    "hiccup_ratio": 0.3,  # a dip below this fraction of the motion either side
    "hiccup_window": 1.2,  # s: the dip and its recovery happen within this
    "reversal_window": 1.0,  # s: real motion on both sides of the turn, within this
    "reversal_rate": 0.5,  # frames/s^2 (or log-units/s^2): how steeply the rate passes through zero
    "fast_sweep": 0.6,   # frames/s
    "fast_zoom": 1.2,    # log-units/s
    "jerk": 6.0,         # frames/s^3
    "dead": 4.0,         # s
    "jump": 0.25,        # frames moved in one frame
    "hold": 1.2,         # s: still this long is a deliberate hold, not a stop-start
    "wander_window": 3.0,  # s
    "fidget_len": 1.2,   # s: a move shorter than this between holds...
    "fidget_peak": 0.25,  # ...that never gets faster than this is a fidget
}


def flags(k, profile=None, scale=None, speaking=None, zoom_scale=None):
    """scale: per-frame multiplier for the speed limits (the voice's pace); speaking: per-frame
    True while the voiceover is talking (for the dead check); zoom_scale: a further per-frame
    multiplier for the zoom limit alone (a planned zoom-through across scales)."""
    p = dict(DEFAULT)
    p.update(profile or {})
    t, e, seg = k["t"], k["energy"], k["segment"]
    n = len(t)
    if n < 3:
        return []
    sc = list(scale) if scale is not None else [1.0] * n
    zs = list(zoom_scale) if zoom_scale is not None else [1.0] * n
    dt = (t[-1] - t[0]) / (n - 1)
    out = []
    win = max(2, int(p["hiccup_window"] / dt))
    still = [x < p["moving"] for x in e]
    run = [0] * n  # length (frames) of the still run each frame belongs to
    i = 0
    while i < n:
        j = i
        while j < n and still[j]:
            j += 1
        for q in range(i, j):
            run[q] = j - i
        i = max(j, i + 1)
    # hiccups: a local minimum well below the peaks on both sides, inside one stretch
    for i in range(1, n - 1):
        if not (e[i] <= e[i - 1] and e[i] <= e[i + 1]):
            continue
        if run[i] * dt >= p.get("hold", 1.2):
            continue  # a deliberate hold, not a stumble
        a, b = max(0, i - win), min(n - 1, i + win)
        left = [e[j] for j in range(a, i) if seg[j] == seg[i]]
        right = [e[j] for j in range(i + 1, b + 1) if seg[j] == seg[i]]
        if not left or not right:
            continue
        lo = min(max(left), max(right))
        if lo > p["moving"] * 2 and e[i] < p["hiccup_ratio"] * lo:
            out.append(("hiccup", t[i], f"motion dips to {e[i]:.3f} between moves of {lo:.3f}"))
    # reversals: the signed pan, tilt or zoom rate crosses zero steeply, with motion either side
    rw = max(2, int(p["reversal_window"] / dt))
    q = max(1, int(0.25 / dt))
    for key, label in (("sweep_h", "pan"), ("sweep_v", "tilt"), ("zoom", "zoom")):
        s = k[key]
        for i in range(q, n - q - 1):
            if not (s[i] * s[i + 1] < 0 and seg[i - q] == seg[i + q + 1]):
                continue
            slope = (s[i + q + 1] - s[i - q]) / ((2 * q + 1) * dt)
            before = max(abs(s[j]) for j in range(max(0, i - rw), i + 1))
            after = max(abs(s[j]) for j in range(i + 1, min(n, i + rw + 1)))
            if abs(slope) > p["reversal_rate"] * sc[i] and min(before, after) > p["moving"] * 2:
                out.append(("reversal", t[i], f"{label} turns back at {abs(slope):.2f}/s² ({before:.2f} then {after:.2f})"))
    # jerk, speed, stillness
    for i in range(n):
        if abs(k["energy_jerk"][i]) > p["jerk"] * sc[i] * zs[i]:
            out.append(("jerk", t[i], f"jerk {k['energy_jerk'][i]:.1f} (limit {p['jerk'] * sc[i] * zs[i]:.1f})"))
        if k["sweep"][i] > p["fast_sweep"] * sc[i]:
            out.append(("fast", t[i], f"sweep {k['sweep'][i]:.2f} frames/s (limit {p['fast_sweep'] * sc[i]:.2f} at this pace)"))
        if abs(k["zoom"][i]) > p["fast_zoom"] * sc[i] * zs[i]:
            out.append(("fast", t[i], f"zoom {k['zoom'][i]:.2f}/s (limit {p['fast_zoom'] * sc[i] * zs[i]:.2f} at this pace)"))
    # wander: direction changes (with real motion either side) twice or more within a window
    ww = max(2, int(p["wander_window"] / dt))
    turns = []
    gap = max(1, int(0.5 / dt))  # a stillness this long ends a move: what follows is a new move, not a turn
    for key in ("sweep_h", "sweep_v", "zoom"):
        s_ = k[key]
        last_sign, last_i = 0, -1
        for i in range(n):
            v = s_[i]
            if abs(v) <= p["moving"] * 2:
                continue
            sign = 1 if v > 0 else -1
            held = any(run[j] >= gap for j in range(last_i + 1, i)) if last_i >= 0 else True
            if last_sign and sign != last_sign and seg[i] == seg[last_i] and not held:
                turns.append(i)
            last_sign, last_i = sign, i
    events = []  # pan, tilt and zoom turning together are one change of direction
    for i in sorted(turns):
        if not events or i - events[-1] > int(0.3 / dt):
            events.append(i)
    for a in range(len(events)):
        b = a
        while b + 1 < len(events) and events[b + 1] - events[a] <= ww:
            b += 1
        if b - a + 1 >= 2:
            out.append(("wander", t[events[a]], f"the camera changes direction {b - a + 1} times in {p['wander_window']:.0f} s"))
    # fidget: a short, small move with holds either side
    i = 0
    while i < n:
        if still[i]:
            i += 1
            continue
        j = i
        while j < n and not still[j]:
            j += 1
        before = run[i - 1] * dt if i > 0 else 0.0
        after = run[j] * dt if j < n else 0.0
        if (j - i) * dt < p["fidget_len"] and max(e[i:j]) < p["fidget_peak"] and before >= 0.5 and after >= 0.5:
            out.append(("fidget", t[i], f"a small {(j - i) * dt:.1f} s move between holds: hold instead, or make it a real move"))
        i = j
    # jumps: one frame moving far more than its neighbours (a hidden cut, a teleport)
    fps = 1 / dt
    for i in range(1, n - 1):
        if seg[i - 1] == seg[i] == seg[i + 1] and e[i] > p["jump"] * fps and e[i] > 4 * max(e[i - 1], e[i + 1], p["moving"]):
            out.append(("jump", t[i], f"{e[i] / fps:.2f} frames in one frame"))
    quiet = 0.0
    for i in range(n):
        talking = speaking[i] if speaking is not None else False
        quiet = quiet + dt if (e[i] < p["moving"] * 0.25 and not talking) else 0.0
        still_t = quiet
        if abs(still_t - p["dead"]) < dt / 2:
            out.append(("dead", t[i], f"no motion for {p['dead']:.0f}s"))
    return merge(out, dt)


def _size(msg):
    import re

    m = re.search(r"-?\d+(?:\.\d+)?", msg)
    return abs(float(m.group(0))) if m else 0.0


def merge(fl, dt, gap=0.25):
    """One flag per run: neighbouring frames with the same flag become one, starting at its first
    frame, with the message of its worst frame (the largest number in it)."""
    fl.sort(key=lambda f: (f[0], f[1]))
    out = []
    for f in fl:
        if out and out[-1][0] == f[0] and f[1] - out[-1][3] <= gap:
            out[-1][3] = f[1]
            if _size(f[2]) > _size(out[-1][2]):
                out[-1][2] = f[2]
            continue
        out.append([f[0], f[1], f[2], f[1]])
    return [(a, t0, msg, t1) for a, t0, msg, t1 in sorted(out, key=lambda f: f[1])]


ZOOM_THROUGH = 3.0  # log-scale/s: a planned zoom-through may run about one power of ten per 0.8 s


def voice_args(motion, times, profile=None):
    """(scale, speaking, zoom_scale) for flags() from a motion file: the voice's pace (channel
    "voice.pace"), whether a word is being spoken (channel "voice.speaking"), and the zoom limit's
    lift during planned zoom-throughs (camera spans with "rule": "zoom-through")."""
    scale = speaking = None
    ch = getattr(motion, "channels", {})
    if "voice.pace" in ch:
        scale = [float(ch["voice.pace"](t)) for t in times]
    if "voice.speaking" in ch:
        speaking = [ch["voice.speaking"](t) > 0.5 for t in times]
    zoom_scale = None
    spans = [s for s in getattr(motion, "spans", []) or [] if s.get("rule") == "zoom-through"]
    if spans:
        base = (profile or {}).get("fast_zoom", DEFAULT["fast_zoom"])
        lift = max(1.0, ZOOM_THROUGH / base)
        zoom_scale = [lift if any(s["t0"] <= t <= s["t1"] for s in spans) else 1.0 for t in times]
    return scale, speaking, zoom_scale
