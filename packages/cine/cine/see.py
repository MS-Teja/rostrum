"""See a scene's whole animation at once.

    python3 -m cine.see scene.motion.json [--out DIR] [--video preview.mp4] [--thumbs DIR]
                        [--profile profile.json] [--png]

Writes DIR/<name>.sheet.svg, DIR/<name>.map.svg, DIR/<name>.html (the viewer), and with --png
the two images as PNG too (for an agent to read). Prints the flags.
"""

import argparse
import glob
import json
import os
import re
import sys

from .core.curve import Motion
from .viz import map as vmap
from .viz import raster, viewer
from .viz.sheet import Sheet


def thumbs_from(d):
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*.jpg")) + glob.glob(os.path.join(d, "*.png"))):
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)s?\.(?:jpg|png)$", os.path.basename(p))
        if m:
            out.append((float(m.group(1)), p))
    return out


def see(motion_path, out=None, video=None, thumbs=None, profile=None, png=False, video_offset=0.0):
    m = Motion.load(motion_path)
    out = out or os.path.dirname(os.path.abspath(motion_path))
    os.makedirs(out, exist_ok=True)
    prof = json.load(open(profile)) if profile else None
    sh = Sheet(m)
    svg, h = sh.build(thumbs_from(thumbs) if thumbs else (), profile=(prof or {}).get("flags"), band=(prof or {}).get("bands"))
    base = os.path.join(out, m.name)
    with open(base + ".sheet.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    msvg, msize, mdata = vmap.draw(m)
    with open(base + ".map.svg", "w", encoding="utf-8") as f:
        f.write(msvg)
    viewer.write(base + ".html", m.name, svg, h, sh, msvg, mdata, sh.fl, m, video, video_offset)
    if png:
        raster.png(svg, (1800, h + 8), base + ".sheet.png")
        raster.png(msvg, msize, base + ".map.png")
    return sh.fl, base


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cine.see")
    ap.add_argument("motion")
    ap.add_argument("--out")
    ap.add_argument("--video")
    ap.add_argument("--video-offset", type=float, default=0.0)
    ap.add_argument("--thumbs")
    ap.add_argument("--profile")
    ap.add_argument("--png", action="store_true")
    a = ap.parse_args(argv)
    fl, base = see(a.motion, a.out, a.video, a.thumbs, a.profile, a.png, a.video_offset)
    print(f"{base}.html")
    for kind, t0, msg, t1 in fl:
        print(f"  {kind:9s} {t0:8.2f}s  {msg}")
    print(f"{len(fl)} flags")


if __name__ == "__main__":
    sys.exit(main())
