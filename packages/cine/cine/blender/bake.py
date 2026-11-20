"""Bake a motion file into Blender: the scene's curves become keyframes, one per frame, so what
renders is exactly what the motion sheet shows, and motion blur sees true sub-frame motion.

Runs inside Blender (GPL-3.0-or-later, as Blender's API requires).

    from cine.blender import bake
    cam = bake.camera(scene, motion)                  # cam.pos / cam.aim / cam.lens channels
    bake.channel(obj, "location", motion.channels["actor.voyager.loc"], motion)
    bake.channel(obj, "rotation_euler", motion.channels["actor.voyager.rot"], motion)
"""

import math

import bpy
from mathutils import Vector


def frames(motion):
    """(frame number, time) for every frame of the motion, frame 1 at motion.t0."""
    n = int(round((motion.t1 - motion.t0) * motion.fps))
    return [(k + 1, motion.t0 + k / motion.fps) for k in range(n + 1)]


def setup(scene, motion):
    scene.render.fps = int(round(motion.fps))
    scene.render.fps_base = 1.0
    fr = frames(motion)
    scene.frame_start, scene.frame_end = fr[0][0], fr[-1][0]


def _linear(obj):
    """Make every key on `obj` linear. A node socket or other nested struct keeps its keys on the
    datablock that owns it (a material's node tree), so look there too."""
    ad = getattr(obj, "animation_data", None)
    if ad is None:
        owner = getattr(obj, "id_data", None)
        ad = getattr(owner, "animation_data", None) if owner is not None else None
    if not ad or not ad.action:
        return
    for layer in getattr(ad.action, "layers", []) or []:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"
    for fc in getattr(ad.action, "fcurves", []) or []:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def camera(scene, motion, name="cine.camera", sensor=36.0, clip=(0.01, 1e6), dof=False, fstop=4.0):
    """A camera keyed every frame from the motion's camera channels."""
    data = bpy.data.cameras.new(name)
    data.sensor_width, data.sensor_fit = sensor, "HORIZONTAL"
    data.clip_start, data.clip_end = clip
    data.dof.use_dof = dof
    data.dof.aperture_fstop = fstop
    cam = bpy.data.objects.new(name, data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    setup(scene, motion)
    ch = motion.channels
    pos, aim, lens = ch[motion.camera["pos"]], ch[motion.camera["aim"]], ch[motion.camera["lens"]]
    prev = None
    for f, t in frames(motion):
        p, a = Vector(pos(t)), Vector(aim(t))
        cam.location = p
        q = (a - p).to_track_quat("-Z", "Y")
        e = q.to_euler("XYZ", prev) if prev is not None else q.to_euler("XYZ")
        cam.rotation_euler = e
        prev = e
        data.lens = float(lens(t))
        data.dof.focus_distance = (a - p).length
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        data.keyframe_insert("lens", frame=f)
        if dof:
            data.keyframe_insert("dof.focus_distance", frame=f)
    _linear(cam)
    _linear(data)
    return cam


def channel(target, path, curve, motion, index=None, transform=None):
    """Key `target.path` (e.g. "location", "scale", "rotation_euler", or a material input's
    "default_value") from `curve` every frame. `transform(value)` maps curve values first."""
    for f, t in frames(motion):
        v = curve(t)
        if transform:
            v = transform(v)
        if index is None:
            setattr(target, path, v)
            target.keyframe_insert(path, frame=f)
        else:
            getattr(target, path)[index] = v
            target.keyframe_insert(path, index=index, frame=f)
    _linear(target)


def degrees(v):
    return [math.radians(x) for x in v] if isinstance(v, (list, tuple)) else math.radians(v)
