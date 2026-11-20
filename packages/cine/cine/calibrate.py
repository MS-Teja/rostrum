"""Calibrate "smooth" on real footage: measure how professional films move the picture, shot by
shot, in the same units cine measures its own cameras in, and write a profile of thresholds
and reference ranges for the flags and the motion sheet.

    python -m cine.calibrate film1.mp4 film2.mkv ... --out profile.json --name film
    python -m cine.calibrate --check render.mp4 --profile profile.json   # a render, read the same way
    python -m cine.see scene.motion.json --profile profile.json --png

Needs numpy and ffmpeg (Blender's bundled Python has numpy:
Blender.app/Contents/Resources/<ver>/python/bin/python3.x).

How it reads a film:
  1. ffmpeg streams it as small grey frames (256 px wide, black bars cropped).
  2. Each pair of frames is compared in a 3x3 grid of blocks by phase correlation: each block
     says how far its content moved. A robust fit turns the nine into the picture's motion:
     pan and tilt (frame widths per second), zoom (log-scale per second) and roll.
  3. Cuts (and dissolves, flashes, featureless frames) are where the blocks stop agreeing or
     the picture changes wholesale; the film splits into shots there.
  4. Each shot is smoothed lightly (zero-phase, as a viewer's eye integrates), then measured
     with the same kinematics and flags as a cine scene.
  5. Percentiles over every moving frame become the profile: the flag thresholds (the fast
     end of real motion, the steepest turn-backs, the sharpest lurches) and the shaded
     reference band on the motion sheet.
A profile is only as good as its footage: "film" from the open films, "explainer" from the
clips Teja collects. The per-frame measurements are cached next to each film.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys

import numpy as np

from .core import qa as Q

W = 256  # analysis width, pixels


# ── reading a film ─────────────────────────────────────────────────────────────────────────

def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames:format=duration",
                          "-of", "json", path], capture_output=True, text=True, check=True)
    d = json.loads(out.stdout)
    s = d["streams"][0]
    num, den = (int(x) for x in s["r_frame_rate"].split("/"))
    return {"w": s["width"], "h": s["height"], "fps": num / den, "duration": float(d["format"]["duration"])}


def crop_of(path, duration):
    """The crop that removes black bars, from ffmpeg's cropdetect over a few stretches."""
    found = {}
    for frac in (0.2, 0.45, 0.7):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{duration * frac:.1f}", "-t", "8", "-i", path, "-vf", "cropdetect=24:2:0", "-f", "null", "-"],
                           capture_output=True, text=True)
        for c in re.findall(r"crop=(\d+:\d+:\d+:\d+)", r.stderr)[-20:]:
            found[c] = found.get(c, 0) + 1
    if not found:
        return None
    # the largest area seen often enough (bright scenes reveal the real picture size)
    best = max(found, key=lambda c: (int(c.split(":")[0]) * int(c.split(":")[1]), found[c]))
    return best


def frames(path, info, crop):
    """Yield grey float32 frames, W pixels wide, from the film."""
    cw, ch = (int(x) for x in crop.split(":")[:2]) if crop else (info["w"], info["h"])
    h = int(round(W * ch / cw / 2)) * 2
    vf = (f"crop={crop}," if crop else "") + f"scale={W}:{h}:flags=area,format=gray"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    n = W * h
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, W).astype(np.float32)
    finally:
        p.stdout.close()
        p.wait()


# ── motion between two frames ──────────────────────────────────────────────────────────────

class Grid:
    """A 3x3 grid of overlapping blocks (half the frame each way), Hann-windowed."""

    def __init__(self, h, w):
        self.h, self.w = h, w
        self.bh, self.bw = h // 2, w // 2
        self.win = np.outer(np.hanning(self.bh), np.hanning(self.bw)).astype(np.float32)
        self.origins = [(int(round(r * (h - self.bh) / 2)), int(round(c * (w - self.bw) / 2))) for r in range(3) for c in range(3)]
        self.centres = [(y + self.bh / 2 - h / 2, x + self.bw / 2 - w / 2) for y, x in self.origins]

    def spectra(self, f):
        out = []
        for y, x in self.origins:
            b = f[y:y + self.bh, x:x + self.bw]
            b = (b - b.mean()) * self.win
            out.append(np.fft.rfft2(b))
        return out


def _peak(r):
    """Sub-pixel peak of a correlation surface: (dy, dx, height), shifts wrapped to +-half."""
    h, w = r.shape
    i = int(np.argmax(r))
    py, px = divmod(i, w)
    v = r[py, px]

    def para(a, b, c):
        d = a - 2 * b + c
        return 0.0 if abs(d) < 1e-12 else 0.5 * (a - c) / d

    dy = py + para(r[(py - 1) % h, px], v, r[(py + 1) % h, px])
    dx = px + para(r[py, (px - 1) % w], v, r[py, (px + 1) % w])
    if dy > h / 2:
        dy -= h
    if dx > w / 2:
        dx -= w
    return dy, dx, float(v)


def block_shifts(grid, sa, sb):
    """How far each block's content moved from frame a to frame b (pixels) and how sure it is."""
    out = []
    for fa, fb in zip(sa, sb):
        R = fb * np.conj(fa)
        R /= np.abs(R) + 1e-6
        r = np.fft.irfft2(R, s=(grid.bh, grid.bw))
        out.append(_peak(r))
    return out


def fit(grid, shifts, min_conf=0.06):
    """Robust fit of the nine block shifts to the picture's motion: translation (tx, ty) in
    pixels, scale change s and roll r per frame, about the frame centre:
        dx = tx + s*x - r*y,  dy = ty + s*y + r*x.
    Returns (tx, ty, s, r, confidence) or None when the blocks don't agree."""
    rows, rhs, wts = [], [], []
    for (dy, dx, c), (cy, cx) in zip(shifts, grid.centres):
        if c < min_conf:
            continue
        rows += [[1, 0, cx, -cy], [0, 1, cy, cx]]
        rhs += [dx, dy]
        wts += [c, c]
    if len(rows) < 8:  # fewer than four trustworthy blocks
        return None
    A, b, w0 = np.array(rows, float), np.array(rhs, float), np.array(wts, float)
    w = w0.copy()
    for _ in range(4):  # Huber-weighted least squares: one block on a moving character can't drag the fit
        p, *_ = np.linalg.lstsq(A * w[:, None], b * w, rcond=None)
        res = np.abs(A @ p - b)
        k = 0.5
        w = w0 * np.where(res <= k, 1.0, k / np.maximum(res, 1e-9))
    res = A @ p - b
    agree = float(np.mean(np.abs(res) < 1.0))
    if agree < 0.6:
        return None
    return float(p[0]), float(p[1]), float(p[2]), float(p[3]), float(np.median([s[2] for s in shifts]))


def measure_film(path, cache=None, log=print):
    """Per-frame motion of a film: lists t, pan, tilt (frame widths/s, + = the camera turns
    right / up), zoom (log-scale/s, + = push in), roll (deg/s), conf, change, valid."""
    if cache and os.path.exists(cache):
        with open(cache) as f:
            return json.load(f)
    info = probe(path)
    crop = crop_of(path, info["duration"])
    fps = info["fps"]
    out = {"path": os.path.basename(path), "fps": fps, "crop": crop, "t": [], "pan": [], "tilt": [], "zoom": [], "roll": [], "conf": [], "change": [], "valid": []}
    grid = prev = sprev = small_prev = None
    k = 0
    for f in frames(path, info, crop):
        if grid is None:
            grid = Grid(*f.shape)
        s = grid.spectra(f)
        small = f[::4, ::4]
        if prev is not None:
            m = fit(grid, block_shifts(grid, sprev, s))
            ch = float(np.mean(np.abs(small - small_prev)) / (np.mean(small) + np.mean(small_prev) + 1e-3) * 2)
            out["t"].append(k / fps)
            out["change"].append(ch)
            if m is None:
                for key in ("pan", "tilt", "zoom", "roll"):
                    out[key].append(0.0)
                out["conf"].append(0.0)
                out["valid"].append(False)
            else:
                tx, ty, sc, rr, conf = m
                out["pan"].append(-tx / grid.w * fps)
                out["tilt"].append(ty / grid.w * fps)
                out["zoom"].append(math.log(max(1e-6, 1 + sc)) * fps)
                out["roll"].append(math.degrees(rr) * fps)
                out["conf"].append(conf)
                out["valid"].append(True)
        prev, sprev, small_prev = f, s, small
        k += 1
        if k % 2000 == 0:
            log(f"  {os.path.basename(path)}: {k} frames")
    if cache:
        with open(cache, "w") as f:
            json.dump(out, f)
    return out


# ── shots and statistics ───────────────────────────────────────────────────────────────────

def cuts(m, ratio=4.0, floor=0.08, window=12, conf=0.3):
    """Frame indices where a shot ends: the picture changes far more than usual round it AND the
    two frames stop correlating (the motion fit fails or its blocks barely match). A character
    moving fast changes the picture but still correlates, so it isn't a cut."""
    ch = np.array(m["change"])
    n = len(ch)
    out = []
    for i in range(n):
        a, b = max(0, i - window), min(n, i + window + 1)
        local = np.median(np.concatenate([ch[a:i], ch[i + 1:b]])) if b - a > 1 else 0.0
        lost = (not m["valid"][i]) or m["conf"][i] < conf
        if lost and ch[i] > floor and ch[i] > ratio * max(local, 0.005):
            out.append(i)
    return out


def _smooth(x, sigma):
    if sigma <= 0 or len(x) < 3:
        return np.asarray(x, float)
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    xp = np.pad(np.asarray(x, float), r, mode="edge")
    return np.convolve(xp, k, mode="valid")


def shots(m, min_len=1.0, sigma=2.0):
    """The film's shots: stretches between cuts, with invalid frames trimmed from the ends and
    short ones dropped. Each is a dict of smoothed per-frame signals, like kinematics.measure."""
    fps = m["fps"]
    cs = cuts(m)
    bounds = [0] + [c + 1 for c in cs] + [len(m["t"])]
    out = []
    for a, b in zip(bounds, bounds[1:]):
        # trim a frame each side of the cut, and anything invalid at the ends
        a, b = a + 1, b - 1
        while a < b and not m["valid"][a]:
            a += 1
        while b > a and not m["valid"][b - 1]:
            b -= 1
        if (b - a) / fps < min_len:
            continue
        valid = np.array(m["valid"][a:b])
        if valid.mean() < 0.9:  # a dissolve or an effects shot: the fit can't be trusted
            continue
        sig = {}
        for key in ("pan", "tilt", "zoom"):
            x = np.array(m[key][a:b], float)
            if not valid.all():  # fill the odd failed frame from its neighbours
                idx = np.arange(len(x))
                x = np.interp(idx, idx[valid], x[valid])
            sig[key] = _smooth(x, sigma)
        n = b - a
        dt = 1 / fps
        t = [m["t"][a] + i * dt for i in range(n)]
        sweep = np.hypot(sig["pan"], sig["tilt"])
        energy = np.hypot(sweep, sig["zoom"])
        k = {"t": t, "sweep": sweep.tolist(), "sweep_h": sig["pan"].tolist(), "sweep_v": sig["tilt"].tolist(), "zoom": sig["zoom"].tolist(),
             "energy": energy.tolist(), "segment": [0] * n}
        for key in ("sweep", "zoom", "energy"):
            acc = np.gradient(np.array(k[key]), dt)
            k[key + "_acc"] = acc.tolist()
            k[key + "_jerk"] = np.gradient(acc, dt).tolist()
        k["film"], k["start"], k["end"] = m["path"], t[0], t[-1]
        out.append(k)
    return out


def _pct(x, ps):
    x = np.asarray(x, float)
    if not len(x):
        return {str(p): None for p in ps}
    return {str(p): float(np.percentile(x, p)) for p in ps}


def crossings(k, q=6):
    """Slopes (per s^2) where the signed pan, tilt and zoom rates cross zero, with real motion on
    both sides: how steeply real cameras turn back."""
    out = []
    t = k["t"]
    if len(t) < 2 * q + 2:
        return out
    dt = t[1] - t[0]
    for key in ("sweep_h", "sweep_v", "zoom"):
        s = k[key]
        for i in range(q, len(s) - q - 1):
            if s[i] * s[i + 1] < 0:
                before, after = max(abs(v) for v in s[i - q:i + 1]), max(abs(v) for v in s[i + 1:i + q + 2])
                if min(before, after) > 0.04:
                    out.append(abs((s[i + q + 1] - s[i - q]) / ((2 * q + 1) * dt)))
    return out


def profile(films, name, moving=0.02):
    ss = [s for m in films for s in shots(m)]
    E = lambda key: np.concatenate([np.asarray(s[key], float) for s in ss]) if ss else np.array([])  # noqa: E731
    energy = E("energy")
    mv = energy > moving
    sweep, zoom = E("sweep")[mv], E("zoom")[mv]
    jerk, acc = np.abs(E("energy_jerk")[mv]), np.abs(E("energy_acc")[mv])
    cross = [c for s in ss for c in crossings(s)]
    lengths = [s["end"] - s["start"] for s in ss]
    moving_shots = [s for s in ss if np.mean(np.asarray(s["energy"]) > moving) > 0.5]
    still_runs = []
    for s in ss:
        run = 0.0
        dt = s["t"][1] - s["t"][0]
        for e in s["energy"]:
            if e < moving * 0.25:
                run += dt
            elif run:
                still_runs.append(run)
                run = 0.0
        if run:
            still_runs.append(run)
    ps = (5, 10, 25, 50, 75, 90, 95, 99)
    stats = {
        "shots": len(ss), "seconds": float(sum(lengths)), "moving_fraction": float(mv.mean()) if len(mv) else 0.0,
        "moving_shots": len(moving_shots), "shot_length": _pct(lengths, ps), "sweep": _pct(sweep, ps), "zoom": _pct(zoom, ps),
        "abs_zoom": _pct(np.abs(zoom), ps), "accel": _pct(acc, ps), "jerk": _pct(jerk, ps), "turn_back": _pct(cross, ps),
        "still_run": _pct(still_runs, ps),
    }
    # Calibrated from footage: speeds and turn-backs. Not from footage: jerk and the hiccup
    # shape, whose measured values are dominated by measurement noise (differentiating a
    # measured signal twice amplifies it); they keep cine's defaults until a cleaner method.
    flags = {
        "fast_sweep": stats["sweep"]["99"], "fast_zoom": stats["abs_zoom"]["99"], "jerk": Q.DEFAULT["jerk"],
        "reversal_rate": stats["turn_back"]["95"] if cross else Q.DEFAULT["reversal_rate"],
        "dead": max(Q.DEFAULT["dead"], stats["still_run"]["90"] or 0.0),
    }
    bands = {"sweep": [stats["sweep"]["10"], stats["sweep"]["90"]], "zoom": [stats["zoom"]["10"], stats["zoom"]["90"]]}
    # sanity: how often the footage trips the flags built from it
    tripped = {}
    for s in ss:
        for kind, *_ in Q.flags(s, flags):
            tripped[kind] = tripped.get(kind, 0) + 1
    return {"name": name, "films": [m["path"] for m in films], "flags": flags, "bands": bands, "stats": stats,
            "calibrated": ["fast_sweep", "fast_zoom", "reversal_rate", "dead", "bands"],
            "uncalibrated": {"jerk": "footage jerk is measurement noise; cine default kept", "hiccup": "shape rule, cine default"},
            "read_with": "the curve-based QA (cine.see --profile). Frame-read checks (--check) are for footage; on sparse scenes like a star field they misread zoom.",
            "self_check": {"flags_per_minute": {k: v / max(1e-9, stats["seconds"] / 60) for k, v in tripped.items()}}}


def check(path, prof, cache=None):
    """Read a render exactly as the films were read, and set its motion against the profile.
    Trust it on scenes with texture everywhere (rooms, landscapes); a star field fools the block
    fit's zoom. For a cine scene the curve-based QA, which knows the camera exactly, is the truth.
    percentiles of sweep, zoom and turn-backs, and how often each flag fires per minute (the
    films' own rate is in the profile's self_check)."""
    m = measure_film(path, cache=cache)
    one = profile([m], os.path.basename(path))
    fl = {}
    where = {}
    for s_ in shots(m):
        for kind, t0, msg, _t1 in Q.flags(s_, prof["flags"]):
            fl[kind] = fl.get(kind, 0) + 1
            where.setdefault(kind, []).append(round(t0, 2))
    mins = max(1e-9, one["stats"]["seconds"] / 60)
    return {"video": os.path.basename(path), "shots": one["stats"]["shots"], "minutes": round(mins, 2),
            "moving_fraction": round(one["stats"]["moving_fraction"], 2),
            "sweep_p50_p90_p99": [round(one["stats"]["sweep"][k] or 0, 3) for k in ("50", "90", "99")],
            "abs_zoom_p50_p90_p99": [round(one["stats"]["abs_zoom"][k] or 0, 3) for k in ("50", "90", "99")],
            "turn_back_p50_p95": [round(one["stats"]["turn_back"][k] or 0, 3) for k in ("50", "95")],
            "flags_per_minute": {k: round(v / mins, 2) for k, v in sorted(fl.items())},
            "film_flags_per_minute": {k: round(v, 2) for k, v in sorted(prof["self_check"]["flags_per_minute"].items())},
            "where": where}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("films", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--name", default="film")
    ap.add_argument("--check", nargs="+", help="renders to read against --profile")
    ap.add_argument("--profile")
    a = ap.parse_args(argv)
    if a.check:
        with open(a.profile) as f:
            prof = json.load(f)
        for v in a.check:
            r = check(v, prof)
            where = r.pop("where")
            print(json.dumps(r))
            for k, ts in where.items():
                print(f"  {k}: " + ", ".join(f"{t:g}" for t in ts[:24]) + (" ..." if len(ts) > 24 else ""))
        return 0
    if not a.films or not a.out:
        ap.error("give films and --out, or --check renders --profile")
    ms = []
    for p in a.films:
        print("measuring", p, flush=True)
        ms.append(measure_film(p, cache=os.path.splitext(p)[0] + ".cine-motion.json", log=lambda s: print(s, flush=True)))
    prof = profile(ms, a.name)
    with open(a.out, "w") as f:
        json.dump(prof, f, indent=1)
    st = prof["stats"]
    print(f"{prof['name']}: {st['shots']} shots, {st['seconds'] / 60:.1f} min, moving {st['moving_fraction']:.0%} of the time")
    print("flags:", json.dumps({k: round(v, 3) for k, v in prof["flags"].items()}))
    print("bands:", json.dumps({k: [round(x, 3) for x in v] for k, v in prof["bands"].items()}))
    print("self-check (flags per minute on the footage itself):", json.dumps({k: round(v, 2) for k, v in prof["self_check"]["flags_per_minute"].items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
