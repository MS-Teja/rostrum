"""A preview that looks like film: EEVEE with motion blur, AgX colour, a lighting rig set from
the real light source, and a dark sky. Fast enough to judge motion on a laptop.

    look.preview(scene, res=(960, 540), samples=16, blur=True)
    look.space_rig(scene, sun_dir=(-0.6, 0.2, 0.3))     # hard key from the Sun, faint fill, rim
    look.glow(scene)                                     # bloom on emissive accents (compositor)
"""

import math

import bpy
from mathutils import Vector


def preview(scene, res=(960, 540), samples=16, blur=True, shutter=0.5, exposure=0.0):
    r = scene.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.film_transparent = False
    r.use_motion_blur = blur
    r.motion_blur_shutter = shutter
    e = scene.eevee
    e.taa_render_samples = samples
    if hasattr(e, "motion_blur_steps"):
        e.motion_blur_steps = 1
    if hasattr(e, "use_shadows"):
        e.use_shadows = True
    vs = scene.view_settings
    vs.view_transform = "AgX"
    vs.look = "AgX - Medium High Contrast"
    vs.exposure = exposure
    r.image_settings.file_format = "PNG"


def glow(scene, threshold=1.0, strength=0.35, size=0.6, kind="Bloom"):
    """Bloom on what's brighter than `threshold` (emissive accents, sunlit metal), through the
    compositor: EEVEE has no bloom of its own since Blender 4.2. Blender 5's compositor is a node
    group set on the scene."""
    ng = bpy.data.node_groups.new("cine.glow", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    g = ng.nodes.new("CompositorNodeGlare")
    out = ng.nodes.new("NodeGroupOutput")
    for name, v in (("Type", kind), ("Threshold", threshold), ("Strength", strength), ("Size", size), ("Quality", "High")):
        if name in g.inputs:
            try:
                g.inputs[name].default_value = v
            except (TypeError, ValueError):
                pass
    ng.links.new(rl.outputs["Image"], g.inputs["Image"])
    ng.links.new(g.outputs[0], out.inputs[0])
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    return ng


def world(scene, colour=(0.0006, 0.0007, 0.001), strength=1.0):
    w = bpy.data.worlds.new("cine.world")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*colour, 1.0)
    bg.inputs["Strength"].default_value = strength
    scene.world = w
    return w


def _sun(name, direction, energy, angle_deg, colour=(1, 1, 1)):
    d = bpy.data.lights.new(name, "SUN")
    d.energy = energy
    d.angle = math.radians(angle_deg)
    d.color = colour
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    v = Vector(direction).normalized()
    o.rotation_euler = (-v).to_track_quat("-Z", "Y").to_euler()  # the light travels against `direction`
    return o


def space_rig(scene, sun_dir=(-0.6, 0.25, 0.35), key=4.5, fill=0.05, rim=1.2):
    """Deep space: one hard key from the Sun (`sun_dir` points from the scene towards the Sun),
    a faint cool fill from the opposite side (light bouncing off nothing is nearly black), and a
    rim from behind-above to separate the silhouette from the dark."""
    s = Vector(sun_dir).normalized()
    _sun("cine.key", s, key, 0.5, (1.0, 0.97, 0.92))
    _sun("cine.fill", -s + Vector((0, 0, 0.3)), fill, 10.0, (0.55, 0.65, 1.0))
    _sun("cine.rim", Vector((-s.x, -s.y, 0.0)).normalized() + Vector((0, 0, 0.8)), rim, 2.0, (0.8, 0.85, 1.0))


def emissive(name, colour, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*colour, 1.0)
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def plume(name, colour, strength=4.0, falloff=1.6, method="BLENDED"):
    """A glowing gas: bright at the object's base (generated z = 0), fading to nothing at its far
    end, see-through everywhere. For thruster puffs, exhaust, jets: put it on a cone whose narrow
    end is the nozzle."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = falloff
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*colour, 1.0)
    em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], inv.inputs[1])
    nt.links.new(inv.outputs[0], pw.inputs[0])
    nt.links.new(pw.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = method
    if hasattr(m, "use_transparency_overlap"):
        m.use_transparency_overlap = True
    return m


def surface(name, colour, roughness=0.5, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*colour, 1.0)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Metallic"].default_value = metallic
    return m
