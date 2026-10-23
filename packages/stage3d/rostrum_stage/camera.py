"""A camera aimed by position and target, with focus on the target.

Aiming is computed directly instead of with a Track To constraint, so a camera
move baked frame by frame is exactly the function that produced it.
"""

import bpy
from mathutils import Vector

from . import parts


def rig(scene, loc, target, lens=70.0, fstop=5.6, sensor=36.0, name="camera"):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.sensor_width = sensor
    data.clip_start = 0.01
    data.clip_end = 100.0
    data.dof.use_dof = fstop > 0
    data.dof.aperture_fstop = max(fstop, 0.5)
    data.dof.aperture_blades = 7
    obj = bpy.data.objects.new(name, data)
    parts.collection().objects.link(obj)
    scene.camera = obj
    aim(obj, loc, target)
    return obj


def aim(cam, loc, target, roll=0.0):
    loc, target = Vector(loc), Vector(target)
    cam.location = loc
    q = (target - loc).to_track_quat("-Z", "Y")
    cam.rotation_euler = q.to_euler()
    cam.rotation_euler.rotate_axis("Z", roll)
    cam.data.dof.focus_distance = (target - loc).length
