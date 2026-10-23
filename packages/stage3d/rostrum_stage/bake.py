"""Animation as pure functions of time, baked to a keyframe on every frame.

A scene says what each property is at time t; `bake` samples it once per frame and
keys it with linear interpolation. What renders is exactly what the function says,
motion blur still works, and the cue a function reads is the frame it lands on.
"""

import bpy


def strength(mat):
    """The input that sets how brightly a material glows, whichever kit material it is."""
    nodes = mat.node_tree.nodes
    for node in nodes:
        if node.bl_idname == "ShaderNodeEmission":
            return node.inputs["Strength"]
    for node in nodes:
        if node.bl_idname == "ShaderNodeBsdfPrincipled":
            return node.inputs["Emission Strength"]
    raise ValueError(f"material {mat.name!r} has no emission")


def bake(scene, fps, frames, channels):
    """`channels` is a list of (target, data_path, fn): each frame sets `target.data_path`
    to fn(t) and keys it, t being seconds from the first frame."""
    prefs = bpy.context.preferences.edit
    before = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    try:
        for f in frames:
            t = (f - 1) / fps
            for target, path, fn in channels:
                setattr(target, path, fn(t))
                target.keyframe_insert(path, frame=f)
    finally:
        prefs.keyframe_new_interpolation_type = before
    scene.frame_start, scene.frame_end = frames[0], frames[-1]
