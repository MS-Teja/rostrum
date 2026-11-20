"""Subject shapes: a subject's real extent, as a cloud of points on its surface in its own frame,
so framing can measure what the viewer sees (how big it is, whether it's cut by the frame,
how much of the frame it covers) instead of guessing from a single point.

A shape in a motion file:
    motion.shapes["voyager"] = {
        "points": [[x, y, z], ...],      # in the subject's frame (from cine.blender.hull, or below)
        "xform": "xf.voyager",          # channel of 12-vectors: rotation rows and translation,
                                        #   local -> world (omit for a shape already in world space)
        "facing": [0, 0, 1],            # optional: the way it faces, in its frame (for lead room)
        "role": "subject" | "context",  # context shapes are checked for clutter, not framing
    }
Helpers make simple shapes (sphere, box, disc) and transforms. No dependencies.
"""

import math


def sphere(centre, radius, n=96):
    """Points spread evenly over a sphere (a Fibonacci lattice)."""
    out = []
    g = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(max(0.0, 1 - z * z))
        a = g * i
        out.append([centre[0] + radius * r * math.cos(a), centre[1] + radius * r * math.sin(a), centre[2] + radius * z])
    return out


def box(lo, hi, n=4):
    """Points on the surface grid of an axis-aligned box."""
    out = []
    for i in range(n + 1):
        for j in range(n + 1):
            for k in range(n + 1):
                if 0 < i < n and 0 < j < n and 0 < k < n:
                    continue
                out.append([lo[0] + (hi[0] - lo[0]) * i / n, lo[1] + (hi[1] - lo[1]) * j / n, lo[2] + (hi[2] - lo[2]) * k / n])
    return out


def disc(centre, normal, radius, n=48):
    """Points on a disc's rim and centre (a dish, a face)."""
    nz = _unit(normal)
    a = _unit(_cross(nz, [0, 0, 1] if abs(nz[2]) < 0.9 else [1, 0, 0]))
    b = _cross(nz, a)
    out = [list(centre)]
    for i in range(n):
        t = 2 * math.pi * i / n
        out.append([centre[k] + radius * (math.cos(t) * a[k] + math.sin(t) * b[k]) for k in range(3)])
    return out


def xform(rot, trans):
    """A 12-vector from a 3x3 rotation (rows) and a translation."""
    return [*rot[0], *rot[1], *rot[2], *trans]


def apply(x, p):
    """Local point -> world by a 12-vector transform."""
    return [x[0] * p[0] + x[1] * p[1] + x[2] * p[2] + x[9],
            x[3] * p[0] + x[4] * p[1] + x[5] * p[2] + x[10],
            x[6] * p[0] + x[7] * p[1] + x[8] * p[2] + x[11]]


def rotate(x, v):
    return [x[0] * v[0] + x[1] * v[1] + x[2] * v[2], x[3] * v[0] + x[4] * v[1] + x[5] * v[2], x[6] * v[0] + x[7] * v[1] + x[8] * v[2]]


def world(shape, motion, t):
    """The shape's points in world space at time t."""
    pts = shape["points"]
    xf = shape.get("xform")
    if not xf:
        return [list(p) for p in pts]
    x = motion.channels[xf](t)
    return [apply(x, p) for p in pts]


def facing(shape, motion, t):
    f = shape.get("facing")
    if not f:
        return None
    xf = shape.get("xform")
    return rotate(motion.channels[xf](t), f) if xf else list(f)


def centre(points):
    lo = [min(p[k] for p in points) for k in range(3)]
    hi = [max(p[k] for p in points) for k in range(3)]
    return [(lo[k] + hi[k]) / 2 for k in range(3)], max(hi[k] - lo[k] for k in range(3)) / 2


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1e-12
    return [x / n for x in v]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
