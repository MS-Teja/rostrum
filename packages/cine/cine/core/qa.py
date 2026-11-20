"""Flags: what a viewer would feel as wrong in a camera's motion, found from its kinematics
(kinematics.measure). Thresholds come from a profile: the defaults below are provisional
until calibrate.py measures reference footage and writes profile.json.

    hiccup     the camera slows almost to a stop between two moves and starts again within
               a second: the stop-start feel
    reversal   it turns or zooms one way, then snaps back the other way: the rate passes through
               zero steeply, with real motion on both sides (a camera easing from a push into a
               pull passes through zero gently, and that is fine)
    jerk       acceleration that changes abruptly (a lurch)
    fast       sweep or zoom faster than the references' fast end
    dead       nothing moves for longer than the references ever sit still
    jump       a discontinuity within a stretch that should be continuous (a hidden cut)
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
}


def flags(k, profile=None):
    p = dict(DEFAULT)
    p.update(profile or {})
    t, e, seg = k["t"], k["energy"], k["segment"]
    n = len(t)
    if n < 3:
        return []
    dt = (t[-1] - t[0]) / (n - 1)
    out = []
    win = max(2, int(p["hiccup_window"] / dt))
    # hiccups: a local minimum well below the peaks on both sides, inside one stretch
    for i in range(1, n - 1):
        if not (e[i] <= e[i - 1] and e[i] <= e[i + 1]):
            continue
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
            if abs(slope) > p["reversal_rate"] and min(before, after) > p["moving"] * 2:
                out.append(("reversal", t[i], f"{label} turns back at {abs(slope):.2f}/s² ({before:.2f} then {after:.2f})"))
    # jerk, speed, stillness
    for i in range(n):
        if abs(k["energy_jerk"][i]) > p["jerk"]:
            out.append(("jerk", t[i], f"jerk {k['energy_jerk'][i]:.1f}"))
        if k["sweep"][i] > p["fast_sweep"]:
            out.append(("fast", t[i], f"sweep {k['sweep'][i]:.2f} frames/s"))
        if abs(k["zoom"][i]) > p["fast_zoom"]:
            out.append(("fast", t[i], f"zoom {k['zoom'][i]:.2f}/s"))
    # jumps: one frame moving far more than its neighbours (a hidden cut, a teleport)
    fps = 1 / dt
    for i in range(1, n - 1):
        if seg[i - 1] == seg[i] == seg[i + 1] and e[i] > p["jump"] * fps and e[i] > 4 * max(e[i - 1], e[i + 1], p["moving"]):
            out.append(("jump", t[i], f"{e[i] / fps:.2f} frames in one frame"))
    still = 0.0
    for i in range(n):
        still = still + dt if e[i] < p["moving"] * 0.25 else 0.0
        if abs(still - p["dead"]) < dt / 2:
            out.append(("dead", t[i], f"no motion for {p['dead']:.0f}s"))
    return merge(out, dt)


def merge(fl, dt, gap=0.25):
    """One flag per run: neighbouring frames with the same flag become one, at its first frame."""
    fl.sort(key=lambda f: (f[0], f[1]))
    out = []
    for f in fl:
        if out and out[-1][0] == f[0] and f[1] - out[-1][3] <= gap:
            out[-1][3] = f[1]
            continue
        out.append([f[0], f[1], f[2], f[1]])
    return [(a, t0, msg, t1) for a, t0, msg, t1 in sorted(out, key=lambda f: f[1])]
