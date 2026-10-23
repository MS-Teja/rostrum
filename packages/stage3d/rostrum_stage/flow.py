"""Data shown as light: tiles for batches, tubes for the paths they travel.

Paths are plain polylines with filleted corners, measured in Python, so a pulse's
position at any moment is a pure function of its progress along the path.
"""

import math

import bpy
from mathutils import Vector

from . import materials as M
from . import parts


def fillet(points, radius, segments=8):
    """Round each interior corner of a polyline with an arc of `radius` (clamped to fit)."""
    pts = [Vector(p) for p in points]
    if len(pts) < 3 or radius <= 0:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u, v = (a - b), (c - b)
        lu, lv = u.length, v.length
        if lu < 1e-9 or lv < 1e-9:
            continue
        u.normalize()
        v.normalize()
        angle = u.angle(v)
        if angle < 1e-3 or abs(angle - math.pi) < 1e-3:
            out.append(b)
            continue
        cut = min(radius / math.tan(angle / 2), lu * 0.5, lv * 0.5)
        p0, p1 = b + u * cut, b + v * cut
        for k in range(segments + 1):
            s = k / segments
            # Quadratic Bezier through the corner: close to a circular arc, and always tangent.
            q = (1 - s) ** 2 * p0 + 2 * (1 - s) * s * b + s * s * p1
            out.append(q)
    out.append(pts[-1])
    return out


def length(points):
    return sum((points[i + 1] - points[i]).length for i in range(len(points) - 1))


def point_at(points, p):
    """Position at fraction `p` of the way along a polyline, by arc length."""
    if p <= 0:
        return points[0].copy()
    total = length(points)
    target = min(p, 1.0) * total
    for i in range(len(points) - 1):
        seg = (points[i + 1] - points[i]).length
        if target <= seg or i == len(points) - 2:
            return points[i].lerp(points[i + 1], 0 if seg == 0 else min(1.0, target / seg))
        target -= seg
    return points[-1].copy()


def tube(name, points, radius, mat, parent=None):
    """A round tube along `points` (already filleted if you want soft corners)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for i, p in enumerate(points):
        sp.points[i].co = (p.x, p.y, p.z, 1.0)
    obj = bpy.data.objects.new(name, cu)
    obj.data.materials.append(mat)
    obj.parent = parent
    parts.collection().objects.link(obj)
    return obj


def tile(name, size, loc, mat, parent=None, rot=(0, 0, 0)):
    """A batch of records: a rounded slab of light."""
    return parts.box(name, size, loc, mat, bevel=min(size) * 0.35, segments=4, rot=rot, parent=parent)


def pulse(name, radius, mat, parent=None):
    """A bright capsule that travels a path; place it with `point_at`."""
    return parts.cylinder(name, radius, radius * 5, (0, 0, 0), mat, bevel=radius * 0.9, verts=24, parent=parent)


def path_material(name, color, strength, solid=False):
    """Light for dark sets. On a bright set glow doesn't read, so `solid` gives a
    saturated, slightly lit surface instead."""
    if solid:
        return M.principled(name, base=color, roughness=0.3, emission=color, strength=strength * 0.4, coat=1.0)
    return M.emitter(name, color, strength)
