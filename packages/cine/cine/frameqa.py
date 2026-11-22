"""Frame QA: what the curves can't see, read from the rendered video itself. Apache-2.0.

    python3 -m cine.frameqa scene.mp4 [--skip 0-0.5,24-25]     # skip spans (fades, transitions)
    from cine import frameqa; frameqa.scan("scene.mp4")           # [(kind, t, message)]

Per frame, the mean brightness (ffmpeg's signalstats, luma 0-255). Two flags:
  pop      the picture's mean brightness jumps more than `jump` levels from one frame to the next
           (a light switching on, a bright object popping in, a blank frame)
  flicker  three or more alternating changes of more than `wobble` levels within a third of a
           second (a strobing light, a bright object whipping across the frame under motion blur)
Scene b07's first render had the Sun whip across the frame as the camera passed it; the camera
checks measure against what the camera follows and didn't see it. This scan did.

Two more, on the look and the pace (from frames sampled at 4 a second, 64 x 36, grey), with limits
measured from the bar (research/refs/notes.md: Cleo Abram's space sequences run at a mean brightness
of 0.21-0.25 with 26-43% of the frame near black, and a new image every 3-4 s; the rejected overnight
Voyager film ran at 0.04 and 88%, holding one subject for 15-60 s):
  dim      a stretch longer than `max_dim` seconds where, over 3 s, the picture's mean brightness is
           under `min_mean` or more than `max_black` of it is near black (darker than 16/255); or dark
           stretches that add up to more than `max_dim_share` of the video. Her space shots go dark
           too, briefly: 23-41% of the time, never longer than 15 s. Ours: 96%, one stretch of 96 s
  stale    nothing new for more than `max_stale` seconds: no moment where the picture differs from
           the one a second earlier by more than `new_image` (mean change, 0-1). A slow creep or
           orbit on one subject reads as stale; so does a held frame under a long explanation
Turn them off with --no-style (a deliberate dark or still sequence). Needs ffmpeg.
"""

import argparse
import re
import subprocess
import sys

RULES = {"jump": 3.0, "wobble": 1.0, "window": 0.34, "min_mean": 0.12, "max_black": 0.55, "max_stale": 8.0, "max_dim": 15.0, "max_dim_share": 0.45, "new_image": 0.035,
         "sample_fps": 4.0}


def brightness(path):
    """Per-frame mean luma and the frame rate."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                          "-f", "null", "-"], capture_output=True, text=True)
    ys = [float(m.group(1)) for m in re.finditer(r"YAVG=([\d.]+)", out.stdout)]
    m = re.search(r"(\d+(?:\.\d+)?) fps", out.stderr)
    return ys, float(m.group(1)) if m else 30.0


def samples(path, fps=4.0, w=64, h=36):
    """Grey frames, downsampled: a list of bytes objects, w x h each."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    n = w * h
    return [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]


def style(path, skip=(), rules=None):
    """The dim and stale flags: [(kind, t, message)]."""
    r = dict(RULES, **(rules or {}))
    fps = r["sample_fps"]
    fr = samples(path, fps)
    if not fr:
        return []
    n = len(fr[0])
    mean = [sum(f) / n / 255 for f in fr]
    black = [sum(1 for v in f if v < 16) / n for f in fr]

    def skipped(t):
        return any(a <= t <= b for a, b in skip)

    out = []
    win = int(3 * fps)
    bad = []
    for i in range(len(fr)):
        a, b = max(0, i - win // 2), min(len(fr), i + win // 2 + 1)
        m, k = sum(mean[a:b]) / (b - a), sum(black[a:b]) / (b - a)
        bad.append((m < r["min_mean"] or k > r["max_black"]) and not skipped(i / fps))
    i = 0
    while i < len(bad):
        if bad[i]:
            j = i
            while j < len(bad) and bad[j]:
                j += 1
            a, b = i, j
            m, k = sum(mean[a:b]) / (b - a), sum(black[a:b]) / (b - a)
            if (j - i) / fps > r["max_dim"]:
                out.append(("dim", i / fps, f"{(j - i) / fps:.1f} s dark: mean brightness {m:.2f}, {k:.0%} near black "
                                            f"(the bar: dark stretches under {r['max_dim']:.0f} s)"))
            i = j
        else:
            i += 1
    share = sum(bad) / len(bad)
    if share > r["max_dim_share"]:
        out.append(("dim", 0.0, f"dark for {share:.0%} of the video (the bar: under {r['max_dim_share']:.0%}; mean brightness "
                                f"{sum(mean) / len(mean):.2f}, {sum(black) / len(black):.0%} near black)"))
    lag = int(fps)
    last_new = 0.0
    for i in range(lag, len(fr)):
        t = i / fps
        diff = sum(abs(x - y) for x, y in zip(fr[i], fr[i - lag])) / n / 255
        if diff > r["new_image"] or skipped(t):
            if t - last_new > r["max_stale"]:
                out.append(("stale", last_new, f"nothing new for {t - last_new:.1f} s (the bar: a new image every 3-4 s, at most {r['max_stale']:.0f} s)"))
            last_new = t
    t_end = len(fr) / fps
    if t_end - last_new > r["max_stale"]:
        out.append(("stale", last_new, f"nothing new for {t_end - last_new:.1f} s, to the end"))
    return out


def scan(path, skip=(), rules=None, look=True):
    r = dict(RULES, **(rules or {}))
    ys, fps = brightness(path)
    d = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]

    def skipped(t):
        return any(a <= t <= b for a, b in skip)

    out = []
    for i, x in enumerate(d):
        t = (i + 1) / fps
        if abs(x) > r["jump"] and not skipped(t):
            out.append(("pop", t, f"mean brightness jumps {x:+.1f} levels in one frame"))
    w = max(3, int(round(r["window"] * fps)))
    i = 1
    while i < len(d):
        flips = [j for j in range(i, min(len(d), i + w)) if abs(d[j]) > r["wobble"] and abs(d[j - 1]) > r["wobble"] and d[j] * d[j - 1] < 0]
        t = i / fps
        if len(flips) >= 3 and not skipped(t):
            out.append(("flicker", t, f"{len(flips)} alternating brightness changes in {w / fps:.2f} s"))
            i += w
        else:
            i += 1
    if look:
        out += style(path, skip, rules)
    return sorted(out, key=lambda f: f[1])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cine.frameqa")
    ap.add_argument("video")
    ap.add_argument("--skip", default="", help="spans to skip, seconds: a-b,c-d")
    ap.add_argument("--no-style", action="store_true", help="skip the dim and stale checks")
    a = ap.parse_args(argv)
    skip = [tuple(float(x) for x in s.split("-")) for s in a.skip.split(",") if s]
    fl = scan(a.video, skip, look=not a.no_style)
    for kind, t, msg in fl:
        print(f"  {kind:8s} {t:7.2f}s  {msg}")
    print(f"{len(fl)} frame flags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
