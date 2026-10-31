"""Named 3D points, projected to pixels for each frame.

Labels live in the HTML overlay, where type stays crisp. Anchors tell the
overlay where each labelled thing is on screen, so a label follows its object
through any camera move.
"""

import json

import bpy
from bpy_extras.object_utils import world_to_camera_view

from . import parts

PREFIX = "anchor."


def anchor(name, loc, parent=None):
    o = parts.empty(PREFIX + name, loc, (0, 0, 0), parent)
    o.empty_display_size = 0.01
    return o


def polyline(name, points, parent=None):
    """A line through 3D points, for the overlay to draw as 2D ink registered to the scene:
    each point is an anchor named "<name>#<i>", projected every frame like any other."""
    return [anchor(f"{name}#{i}", p, parent) for i, p in enumerate(points)]


def project(scene):
    """{name: [x, y, visible]} in output pixels for the current frame. A polyline's points
    are gathered under its name, in order: {name: [[x, y, visible], ...]}."""
    r = scene.render
    w = r.resolution_x * r.resolution_percentage / 100
    h = r.resolution_y * r.resolution_percentage / 100
    cam = scene.camera
    out, lines = {}, {}
    for o in scene.objects:
        if not o.name.startswith(PREFIX):
            continue
        v = world_to_camera_view(scene, cam, o.matrix_world.translation)
        visible = v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1
        point = [round(v.x * w, 2), round((1 - v.y) * h, 2), visible]
        name = o.name[len(PREFIX) :]
        if "#" in name:
            line, i = name.rsplit("#", 1)
            lines.setdefault(line, []).append((int(i), point))
        else:
            out[name] = point
    for line, points in lines.items():
        out[line] = [p for _, p in sorted(points)]
    return out


def write(path, frames, fps, size):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"fps": fps, "width": size[0], "height": size[1], "frames": frames}, f, separators=(",", ":"))
