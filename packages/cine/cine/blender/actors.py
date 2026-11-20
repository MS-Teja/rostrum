"""Actor presets (crew/animator.md): motion with the principles built in, keyed every frame so
what renders is what the sheet shows. GPL-3.0-or-later.

    from cine.blender import actors
    actors.puff(scene, motion, parent, nozzle=(x, y, z), direction=(0, 0, -1), events=[(10.2, 1.0)])
    actors.glow_pulse(obj, motion, events=[(3.0, 1.0)], base=0.2)     # a light that flashes and decays
    actors.appear(obj, motion, t=4.0, overshoot=0.08, settle=0.4)      # scale in with a small overshoot

**puff**: gas from a nozzle, as a burst of soft glowing blobs (not a solid cone). Each event (time,
size) spawns blobs that leave the nozzle inside a narrow cone, slow down (gas loses speed fast in
vacuum's expansion), swell and fade over about half a second: a 2-3 frame bloom, then decay.
Blobs share one material; each blob's fade is its object colour, keyed per frame.
**glow_pulse**: an emissive object's brightness rises in 2 frames and decays (a status light,
a filament), via its object colour.
**appear**: scale from nothing to full with a small overshoot that settles (anticipation-free:
a pop with follow-through).
"""

import math
import random

import bpy
from mathutils import Vector

from . import bake


def _fade_material(name, colour, strength, softness=2.0, opacity=1.0):
    """Emission whose strength is the object's colour (red channel), soft at the silhouette, and at
    most `opacity` opaque (gas is see-through, and many blobs overlap)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    info = nt.nodes.new("ShaderNodeObjectInfo")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = strength
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = softness
    alpha = nt.nodes.new("ShaderNodeMath")
    alpha.operation = "MULTIPLY"
    op = nt.nodes.new("ShaderNodeMath")
    op.operation = "MULTIPLY"
    op.inputs[1].default_value = opacity
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*colour, 1.0)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    L = nt.links
    L.new(info.outputs["Color"], sep.inputs[0])
    L.new(sep.outputs[0], mul.inputs[0])
    L.new(mul.outputs[0], em.inputs["Strength"])
    L.new(lw.outputs["Facing"], inv.inputs[1])
    L.new(inv.outputs[0], pw.inputs[0])
    L.new(pw.outputs[0], alpha.inputs[0])
    L.new(sep.outputs[0], alpha.inputs[1])
    L.new(alpha.outputs[0], op.inputs[0])
    L.new(op.outputs[0], mix.inputs["Fac"])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    return m


def puff(scene, motion, parent, nozzle, direction, events, blobs=26, spread_deg=11.0, speed=3.2, life=0.6,
         r0=0.012, growth=0.10, colour=(0.82, 0.9, 1.0), strength=1.6, opacity=0.4, seed=7, name="puff"):
    """Gas puffs from `nozzle` along `direction` (both in `parent`'s frame), one burst per event
    (time, size 0..1). Returns the blob objects."""
    rng = random.Random(seed)
    mat = _fade_material(name + ".gas", colour, strength, opacity=opacity)
    d = Vector(direction).normalized()
    a = d.orthogonal().normalized()
    b = d.cross(a)
    frames = bake.frames(motion)
    objs = []
    for e, (te, size) in enumerate(events):
        for k in range(blobs):
            th = math.radians(spread_deg) * math.sqrt(rng.random())
            ph = 2 * math.pi * rng.random()
            v_dir = (d * math.cos(th) + (a * math.cos(ph) + b * math.sin(ph)) * math.sin(th)).normalized()
            v = speed * size * (0.55 + 0.9 * rng.random())
            delay = 0.05 * rng.random()  # not all at once: the burst has a front
            r_end = (r0 + growth * size) * (0.6 + 0.8 * rng.random())
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=12, location=(0, 0, 0))
            o = bpy.context.active_object
            for poly in o.data.polygons:
                poly.use_smooth = True
            o.name = f"{name}.{e}.{k:02d}"
            o.data.materials.append(mat)
            o.visible_shadow = False
            o.parent = parent
            first, last = frames[0][0], frames[-1][0]
            live = [(f, t) for f, t in frames if -2 / motion.fps <= t - te - delay <= life + 3 / motion.fps]
            keyed = ([(first, frames[0][1])] if live and live[0][0] > first else []) + live + ([(last, frames[-1][1])] if live and live[-1][0] < last else [])
            for f, t in keyed:  # only its life needs keys: before and after, it's invisible and still
                age = t - te - delay
                if age < -1 / motion.fps or age > life + 2 / motion.fps:
                    vis, rr, pos = 0.0, 1e-4, Vector(nozzle)
                else:
                    age = max(0.0, age)
                    u = age / life
                    bloom = min(1.0, age / 0.07)  # 2 frames up
                    vis = size * bloom * math.exp(-3.2 * u) * (1 - u * u)
                    rr = r0 + (r_end - r0) * (1 - math.exp(-4.0 * u))
                    travel = v * life * (1 - math.exp(-3.0 * u)) / 3.0  # decelerating
                    pos = Vector(nozzle) + v_dir * travel
                o.location = pos
                o.scale = (max(1e-4, rr),) * 3
                o.color = (max(0.0, vis), 0.0, 0.0, 1.0)
                o.keyframe_insert("location", frame=f)
                o.keyframe_insert("scale", frame=f)
                o.keyframe_insert("color", frame=f)
            bake._linear(o)
            objs.append(o)
    return objs


def glow_pulse(obj, motion, events, base=0.15, rise=0.07, decay=0.5):
    """Key `obj.color` (red = brightness, for materials that read it) as flashes on a base level."""
    for f, t in bake.frames(motion):
        v = base
        for te, size in events:
            age = t - te
            if 0 <= age < rise:
                v = max(v, base + (size - base) * age / rise)
            elif age >= rise:
                v = max(v, base + (size - base) * math.exp(-(age - rise) / decay))
        obj.color = (v, 0.0, 0.0, 1.0)
        obj.keyframe_insert("color", frame=f)
    bake._linear(obj)


def appear(obj, motion, t, overshoot=0.08, settle=0.4, grow=0.18):
    """Scale `obj` in at time t: up to 1 + overshoot in `grow` seconds, settling to 1 over `settle`."""
    full = Vector(obj.scale)
    for f, tt in bake.frames(motion):
        age = tt - t
        if age <= 0:
            k = 0.0
        elif age < grow:
            x = age / grow
            k = (1 + overshoot) * (3 * x * x - 2 * x * x * x)
        else:
            k = 1 + overshoot * math.exp(-5 * (age - grow) / settle) * math.cos(math.pi * (age - grow) / settle)
        obj.scale = full * max(1e-4, k)
        obj.keyframe_insert("scale", frame=f)
    bake._linear(obj)


def fade_material(name, colour, strength, softness=2.0, opacity=1.0):
    """The material puff() and glow_pulse() use: emission scaled by the object's colour (red)."""
    return _fade_material(name, colour, strength, softness, opacity)
