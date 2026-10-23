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


def project(scene):
    """{name: [x, y, visible]} in output pixels for the current frame."""
    r = scene.render
    w = r.resolution_x * r.resolution_percentage / 100
    h = r.resolution_y * r.resolution_percentage / 100
    cam = scene.camera
    out = {}
    for o in scene.objects:
        if not o.name.startswith(PREFIX):
            continue
        v = world_to_camera_view(scene, cam, o.matrix_world.translation)
        visible = v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1
        out[o.name[len(PREFIX) :]] = [round(v.x * w, 2), round((1 - v.y) * h, 2), visible]
    return out


def write(path, frames, fps, size):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"fps": fps, "width": size[0], "height": size[1], "frames": frames}, f, separators=(",", ":"))
