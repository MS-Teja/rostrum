"""Can the viewer see each actor? (crew/build.md, gate 6). GPL-3.0-or-later.

    from cine.core import actors as A
    m.actors["arrive"] = A.actor(P.track(points, t0, t1, fps), size=0.04, word=W["flash"])
    A.flags(m)      # [(kind, t0, message, t1)], like the motion and composition flags

An actor's track is where it is at each frame of its life, [[t, x, y, z], ...], and its size is
its radius in metres. From the camera, over the actor's life:
  unseen   out of frame or behind the camera for more than a fifth of its life (or at its word)
  tiny     smaller than 0.006 of the frame's width across for more than a fifth of its life
Hidden (something solid between it and the camera) needs the scene's geometry: the dailies
ray-test the same track (blender/dailies.hidden). Scene C's first pulse ran on top of a cable
tray, seen only from below, and was hidden for its whole life; nobody saw it for four passes.
No dependencies.
"""

import math

from . import kinematics as K

RULES = {"min_size": 0.006, "max_bad": 0.2}


def actor(track, size, word=None):
    return {"track": [list(map(float, r)) for r in track], "size": float(size), "word": word}


def measure(motion, a):
    """[(t, in_frame, size)] over the actor's life inside the scene: size is its diameter as a
    fraction of the frame's width (0 when behind the camera)."""
    ch, cam = motion.channels, motion.camera
    rows = []
    for t, x, y, z in a["track"]:
        if t < motion.t0 - 1e-9 or t > motion.t1 + 1e-9:
            continue
        pos, aim, lens = list(ch[cam["pos"]](t)), list(ch[cam["aim"]](t)), float(ch[cam["lens"]](t))
        q = K.screen(pos, aim, lens, [x, y, z])
        if q is None:
            rows.append((t, False, 0.0))
            continue
        sx, sy, depth = q
        rows.append((t, abs(sx) <= 0.5 and abs(sy) <= 0.5, a["size"] / (depth * math.tan(K.hfov(lens) / 2))))
    return rows


def flags(motion, rules=None):
    r = dict(RULES, **(rules or {}))
    out = []
    for name, a in sorted((getattr(motion, "actors", None) or {}).items()):
        rows = measure(motion, a)
        if not rows:
            continue
        t0, t1 = rows[0][0], rows[-1][0]
        unseen = [t for t, ok, _ in rows if not ok]
        tiny = [(t, s) for t, ok, s in rows if ok and s < r["min_size"]]
        at_word = None
        if a.get("word") is not None:
            at_word = min(rows, key=lambda row: abs(row[0] - a["word"]))
        if len(unseen) > r["max_bad"] * len(rows) or (at_word is not None and not at_word[1]):
            when = f"; out at its word ({a['word']:.2f} s)" if at_word is not None and not at_word[1] else ""
            out.append(("unseen", unseen[0] if unseen else t0, f"{name} is out of frame for {len(unseen) / len(rows):.0%} of its life{when}", t1))
        if len(tiny) > r["max_bad"] * len(rows):
            smallest = min(s for _, s in tiny)
            out.append(("tiny", tiny[0][0], f"{name} is under {r['min_size']} of the frame wide for {len(tiny) / len(rows):.0%} of its life "
                                            f"(smallest {smallest:.4f})", t1))
    return out
