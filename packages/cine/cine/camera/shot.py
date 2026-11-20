"""Set up a shot the way a cinematographer describes it, and get the camera key that makes it.

    F = Framer(rig, {"voyager": core_points, "thrusters": cluster_points}, facing={"voyager": dish_axis})
    F.shot(0.0, "voyager", size="medium wide", angle="low", side="left third", lens=35,
           view="three-quarter", hand=-1, motive="establish", label="the dish, three-quarters on")
    F.shot(9.0, "thrusters", size="close", angle="eye", side="centre", lens=50, view=30, motive="emphasise")

Each shot solves the camera's distance and screen offset so the subject's real shape (its
points, see core/shape.py) has the asked size and sits on the asked third, from the asked
angle, bearing and lens, then adds the key to the rig with the plan recorded as its intent.
The words are crew/cinematographer.md's:
  size   extreme wide, wide, medium wide, medium, close, extreme close (or a fraction of frame)
  angle  eye (0), low (-20), high (20), overhead (70) degrees of elevation, or a number
  side   left third, centre, right third (or a screen x)
  view   front, three-quarter, side, back three-quarter, back: degrees off the way the subject
         faces (0, 40, 90, 140, 180), turned by `hand` (+1 or -1); or give az directly
  vside  centre, or headroom (top of the subject 10% below the frame top)
  look   normal, low-key or silhouette: the planned exposure the look checks judge it by
         (core/look.py); say why in the label
No dependencies.
"""

import math

from ..core import compose as C
from ..core import shape as S
from . import rig as R

ANGLES = {"eye": 0.0, "low": -20.0, "high": 20.0, "overhead": 70.0}
SIDES = {"left third": -1 / 6, "centre": 0.0, "center": 0.0, "right third": 1 / 6}
VIEWS = {"front": 0.0, "three-quarter": 40.0, "side": 90.0, "back three-quarter": 140.0, "back": 180.0}


TARGETS = {  # where in each band a shot aims: inside the band, and clear of the 5% edge margin
    "extreme wide": 0.06, "wide": 0.2, "medium wide": 0.42, "medium": 0.67, "close": 0.86, "extreme close": 1.45,
}


def _size_target(size):
    if isinstance(size, (int, float)):
        return float(size), None
    C.size_band(size)  # validates the name
    return TARGETS[size], size


def _call(f, t):
    return f(t) if callable(f) else f


class Framer:
    def __init__(self, rig, shapes, facing=None):
        """shapes: {subject name: points in world space, or a function of t returning them}.
        facing: {subject name: its facing direction in world space, or a function of t}."""
        self.rig, self.shapes, self.facing = rig, dict(shapes), dict(facing or {})

    def solve(self, t, subject, size, angle="eye", side="centre", lens=35.0, az=None, view=None, hand=1, vside="centre"):
        """(key values, achieved measures) for a shot, without adding it."""
        pivot = R._pt(self.rig.subjects[subject], t)
        pts = _call(self.shapes[subject], t)
        el = ANGLES[angle] if isinstance(angle, str) else float(angle)
        if az is None:
            f = _call(self.facing.get(subject), t)
            base = R.bearing(f)[0] if f else 0.0
            off = VIEWS[view] if isinstance(view, str) else float(view or 0.0)
            az = base + hand * off
        tx = SIDES[side] if isinstance(side, str) else float(side)
        target, _name = _size_target(size)
        _, rad = S.centre(pts)

        def look(dist, screen):
            pos = [pivot[i] + d * dist for i, d in enumerate(R.direction(az, el))]
            aim = R.compose(pos, pivot, lens, screen)
            return C.measure_points(pts, pos, aim, lens)

        def size_at(dist, screen):
            m = look(dist, screen)
            if not m.get("visible") or m["behind"] > 0:
                return 99.0
            return m["size"]

        screen = [tx, 0.0]
        dist = rad * 4
        for _ in range(8):
            lo, hi = math.log(max(1e-3, rad * 0.3)), math.log(rad * 5000)
            for _ in range(48):  # size shrinks with distance: bisect on log distance
                mid = (lo + hi) / 2
                if size_at(math.exp(mid), screen) > target:
                    lo = mid
                else:
                    hi = mid
            dist = math.exp((lo + hi) / 2)
            m = look(dist, screen)
            if not m.get("visible"):
                break
            ty = (0.4 - m["h"] / 2) if vside == "headroom" else 0.0
            ex, ey = tx - m["cx"], ty - m["cy"]
            screen = [screen[0] + ex, screen[1] + ey]
            if abs(ex) < 1e-4 and abs(ey) < 1e-4:
                break
        m = look(dist, screen)
        return {"dist": dist, "az": az, "el": el, "lens": float(lens), "screen": tuple(screen)}, m

    def shot(self, t, subject, size, angle="eye", side="centre", lens=35.0, az=None, view=None, hand=1, vside="centre",
             motive="", label=None, stop=False, handover=0.5, look="normal"):
        k, m = self.solve(t, subject, size, angle, side, lens, az, view, hand, vside)
        intent = {"subject": subject, "size": size, "angle": angle, "side": side, "lens": lens, "motive": motive, "look": look,
                  "achieved": {"size": round(m.get("size", 0), 3), "cx": round(m.get("cx", 0), 3), "named": C.size_name(m.get("size", 0))}}
        self.rig.key(t, look=subject, dist=k["dist"], az=k["az"], el=k["el"], lens=k["lens"], screen=k["screen"],
                     stop=stop, label=label or motive, intent=intent, handover=handover)
        return k, m
