"""Frame QA: what the curves can't see, read from the rendered video itself. Apache-2.0.

    python3 -m cine.frameqa scene.mp4 [--skip 0-0.5,24-25]     # skip spans (fades, transitions)
    from cine import frameqa; frameqa.scan("scene.mp4")           # [(kind, t, message)]

Per frame, the mean brightness (ffmpeg's signalstats, luma 0-255). Two flags:
  pop      the picture's mean brightness jumps more than `jump` levels from one frame to the next
           (a light switching on, a bright object popping in, a blank frame)
  flicker  three or more alternating changes of more than `wobble` levels within a third of a
           second (a strobing light, a bright object whipping across the frame under motion blur)
Scene b07's first render had the Sun whip across the frame as the camera passed it; the camera
checks measure against what the camera follows and didn't see it. This scan did. Needs ffmpeg.
"""

import argparse
import re
import subprocess
import sys

RULES = {"jump": 3.0, "wobble": 1.0, "window": 0.34}


def brightness(path):
    """Per-frame mean luma and the frame rate."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                          "-f", "null", "-"], capture_output=True, text=True)
    ys = [float(m.group(1)) for m in re.finditer(r"YAVG=([\d.]+)", out.stdout)]
    m = re.search(r"(\d+(?:\.\d+)?) fps", out.stderr)
    return ys, float(m.group(1)) if m else 30.0


def scan(path, skip=(), rules=None):
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
    return sorted(out, key=lambda f: f[1])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cine.frameqa")
    ap.add_argument("video")
    ap.add_argument("--skip", default="", help="spans to skip, seconds: a-b,c-d")
    a = ap.parse_args(argv)
    skip = [tuple(float(x) for x in s.split("-")) for s in a.skip.split(",") if s]
    fl = scan(a.video, skip)
    for kind, t, msg in fl:
        print(f"  {kind:8s} {t:7.2f}s  {msg}")
    print(f"{len(fl)} frame flags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
