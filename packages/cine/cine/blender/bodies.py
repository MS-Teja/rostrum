"""Planets and moons from real maps, lit as they really were. GPL-3.0-or-later.

    from cine.blender import bodies
    sat = bodies.ringed_planet("saturn", pole, polar_ratio=54364 / 60268,
                               bands="saturn_bands.png", rings="saturn_rings.png",
                               ring_span=(74000 / 60268, 141000 / 60268), ring_gain=3.0)
    jup = bodies.self_lit_sphere("jupiter", pole, "jupiter_PIA07782.jpg", sun_ref)
    bodies.sun_lamp("sunlight", direction_at, frames)   # a sun lamp keyed along a moving direction

Each body is built in units of its equatorial radius, its pole along the given direction (a unit
vector in the scene's frame, e.g. `ephemeris.eq_to_ecliptic(ra, dec)` of the IAU pole). Scale and
place it yourself (on the scale stage: at least a few pixels across, true size when it's bigger).

ringed_planet    an oblate globe whose colour comes from a band strip (colour by latitude: a
                 gas giant's bands read from one column of a real map), and rings from a measured
                 radial profile (colour and opacity by radius). Lit by the scene's lamps.
self_lit_sphere  a sphere wrapped in an equirectangular map that lights itself from the Sun's true
                 direction, read from an empty at the Sun: lit correctly wherever it is, without a
                 lamp per planet. A faint declared fill keeps the night side readable.
"""

import math

import bpy
from mathutils import Vector


def _nodes(m):
    m.use_nodes = True
    return m.node_tree.nodes, m.node_tree.links


def _math(N, L, op, a, b=None, clamp=False):
    x = N.new("ShaderNodeMath")
    x.operation, x.use_clamp = op, clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            x.inputs[i].default_value = v
        else:
            L.new(v, x.inputs[i])
    return x.outputs[0]


def ringed_planet(name, pole, polar_ratio, bands, rings=None, ring_span=(1.23, 2.34), ring_gain=1.0, segments=96):
    """A banded, oblate globe with measured rings, in units of its equatorial radius. `bands`: an
    image whose vertical axis is latitude (south at the bottom). `rings`: an image whose horizontal
    axis runs from the inner to the outer edge of `ring_span` (radii), with colour and alpha.
    `ring_gain` brightens the rings' lit face: ring particles scatter like a thick layer, far
    brighter at a low sun than a matte sheet (an approximation; declare it). Returns the parent."""
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = Vector(pole).to_track_quat("Z", "X")

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=segments, ring_count=segments // 2)
    globe = bpy.context.active_object
    globe.name = name + ".globe"
    for poly in globe.data.polygons:
        poly.use_smooth = True
    globe.scale = (1.0, 1.0, polar_ratio)
    globe.parent = root
    m = bpy.data.materials.new(name + ".globe")
    N, L = _nodes(m)
    bsdf = N["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 1.0
    tc = N.new("ShaderNodeTexCoord")
    nrm = N.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    L.new(tc.outputs["Object"], nrm.inputs[0])
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(nrm.outputs["Vector"], sep.inputs[0])
    v = N.new("ShaderNodeMath")
    v.operation = "MULTIPLY_ADD"
    v.inputs[1].default_value, v.inputs[2].default_value = 1.0 / math.pi, 0.5
    L.new(_math(N, L, "ARCSINE", sep.outputs["Z"]), v.inputs[0])  # latitude, 0 at the south pole to 1 at the north
    uv = N.new("ShaderNodeCombineXYZ")
    uv.inputs[0].default_value = 0.5
    L.new(v.outputs[0], uv.inputs[1])
    img = N.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(bands)
    img.extension = "EXTEND"
    L.new(uv.outputs[0], img.inputs["Vector"])
    L.new(img.outputs["Color"], bsdf.inputs["Base Color"])
    globe.data.materials.append(m)
    if rings:
        _rings(root, name, rings, ring_span, ring_gain)
    return root


def _rings(root, name, image, span, gain, n=512):
    ri, ro = span
    verts = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), 0.0) for r in (ri, ro) for k in range(n)]
    faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    me = bpy.data.meshes.new(name + ".rings")
    me.from_pydata(verts, [], faces)
    rings = bpy.data.objects.new(name + ".rings", me)
    bpy.context.scene.collection.objects.link(rings)
    rings.parent = root
    rm = bpy.data.materials.new(name + ".rings")
    N, L = _nodes(rm)
    bsdf = N["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 1.0
    tc = N.new("ShaderNodeTexCoord")
    ln = N.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    L.new(tc.outputs["Object"], ln.inputs[0])
    u = N.new("ShaderNodeMath")
    u.operation = "MULTIPLY_ADD"  # radius to 0..1 across the span
    u.inputs[1].default_value = 1.0 / (ro - ri)
    u.inputs[2].default_value = -ri / (ro - ri)
    L.new(ln.outputs["Value"], u.inputs[0])
    uv = N.new("ShaderNodeCombineXYZ")
    uv.inputs[1].default_value = 0.5
    L.new(u.outputs[0], uv.inputs[0])
    img = N.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(image)
    img.extension = "CLIP"
    img.interpolation = "Linear"
    L.new(uv.outputs[0], img.inputs["Vector"])
    mix = N.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.inputs["B"].default_value = (gain, gain, gain, 1.0)
    L.new(img.outputs["Color"], mix.inputs["A"])
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    L.new(img.outputs["Alpha"], bsdf.inputs["Alpha"])
    if hasattr(rm, "surface_render_method"):
        rm.surface_render_method = "BLENDED"
    if hasattr(rm, "use_transparent_shadow"):
        rm.use_transparent_shadow = True
    rings.data.materials.append(rm)
    return rings


def self_lit_sphere(name, pole, image, sun_ref, fill=0.12, segments=64):
    """A sphere wrapped in an equirectangular map (longitude across, latitude up), lit by its own
    shader from the direction of `sun_ref` (an empty at the Sun), so it's lit correctly wherever it
    is. `fill`: the declared faint light on its night side. Casts no shadow."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=segments, ring_count=segments // 2)
    o = bpy.context.active_object
    o.name = name
    for p in o.data.polygons:
        p.use_smooth = True
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector(pole).to_track_quat("Z", "X")
    m = bpy.data.materials.new(name)
    N, L = _nodes(m)
    for x in list(N):
        N.remove(x)
    tc = N.new("ShaderNodeTexCoord")
    nrm = N.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    L.new(tc.outputs["Object"], nrm.inputs[0])
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(nrm.outputs["Vector"], sep.inputs[0])
    lon = _math(N, L, "ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
    u = N.new("ShaderNodeMath")
    u.operation = "MULTIPLY_ADD"
    u.inputs[1].default_value, u.inputs[2].default_value = 0.5 / math.pi, 0.5
    L.new(lon, u.inputs[0])
    v = N.new("ShaderNodeMath")
    v.operation = "MULTIPLY_ADD"
    v.inputs[1].default_value, v.inputs[2].default_value = 1.0 / math.pi, 0.5
    L.new(_math(N, L, "ARCSINE", sep.outputs["Z"]), v.inputs[0])
    uv = N.new("ShaderNodeCombineXYZ")
    L.new(u.outputs[0], uv.inputs[0])
    L.new(v.outputs[0], uv.inputs[1])
    img = N.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(image)
    L.new(uv.outputs[0], img.inputs["Vector"])
    sun = N.new("ShaderNodeTexCoord")
    sun.object = sun_ref
    toward = N.new("ShaderNodeVectorMath")
    toward.operation = "SCALE"
    toward.inputs["Scale"].default_value = -1.0
    L.new(sun.outputs["Object"], toward.inputs[0])
    ln = N.new("ShaderNodeVectorMath")
    ln.operation = "NORMALIZE"
    L.new(toward.outputs[0], ln.inputs[0])
    geo = N.new("ShaderNodeNewGeometry")
    dot = N.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L.new(geo.outputs["Normal"], dot.inputs[0])
    L.new(ln.outputs[0], dot.inputs[1])
    lit = _math(N, L, "ADD", _math(N, L, "MAXIMUM", dot.outputs["Value"], 0.0, clamp=True), fill)
    em = N.new("ShaderNodeEmission")
    L.new(img.outputs["Color"], em.inputs["Color"])
    L.new(lit, em.inputs["Strength"])
    out = N.new("ShaderNodeOutputMaterial")
    L.new(em.outputs[0], out.inputs["Surface"])
    o.data.materials.append(m)
    o.visible_shadow = False
    return o


def sun_lamp(name, direction, frames, energy=4.0, angle_deg=0.06):
    """A sun lamp keyed every frame to shine along `direction(t)` (a vector from the Sun toward
    what it lights). `frames`: [(frame, t)]."""
    from . import bake

    lamp = bpy.data.lights.new(name, "SUN")
    lamp.energy, lamp.angle = energy, math.radians(angle_deg)
    o = bpy.data.objects.new(name, lamp)
    bpy.context.scene.collection.objects.link(o)
    for f, t in frames:
        o.rotation_euler = Vector(direction(t)).normalized().to_track_quat("-Z", "Y").to_euler()
        o.keyframe_insert("rotation_euler", frame=f)
    bake._linear(o)
    return o
