"""Materials. Each function returns the same material for the same name, so parts share them.

Real surfaces are never uniform: most materials get a faint noise in roughness,
which is what makes highlights look like light on an object instead of on a render.
"""

import bpy


def _material(name):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m, False
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, True


def _out(m, shader):
    out = m.node_tree.nodes.new("ShaderNodeOutputMaterial")
    m.node_tree.links.new(shader, out.inputs["Surface"])


def _noise(m, scale, detail=6.0):
    nodes = m.node_tree.nodes
    coord = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = detail
    m.node_tree.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    return noise.outputs["Fac"]


def principled(
    name,
    base=(0.8, 0.8, 0.8),
    metallic=0.0,
    roughness=0.5,
    rough_vary=0.0,
    noise_scale=60.0,
    bump=0.0,
    coat=0.0,
    coat_roughness=0.05,
    transmission=0.0,
    ior=1.5,
    emission=None,
    strength=0.0,
    alpha=1.0,
    specular=0.5,
):
    m, fresh = _material(name)
    if not fresh:
        return m
    nodes, links = m.node_tree.nodes, m.node_tree.links
    b = nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    b.inputs["IOR"].default_value = ior
    b.inputs["Specular IOR Level"].default_value = specular
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = coat_roughness
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["Alpha"].default_value = alpha
    if emission is not None:
        b.inputs["Emission Color"].default_value = (*emission, 1.0)
        b.inputs["Emission Strength"].default_value = strength
    if rough_vary > 0 or bump > 0:
        fac = _noise(m, noise_scale)
        if rough_vary > 0:
            r = nodes.new("ShaderNodeMapRange")
            r.inputs["To Min"].default_value = max(0.0, roughness - rough_vary)
            r.inputs["To Max"].default_value = min(1.0, roughness + rough_vary)
            links.new(fac, r.inputs["Value"])
            links.new(r.outputs["Result"], b.inputs["Roughness"])
        if bump > 0:
            bp = nodes.new("ShaderNodeBump")
            bp.inputs["Strength"].default_value = bump
            bp.inputs["Distance"].default_value = 0.0005
            links.new(fac, bp.inputs["Height"])
            links.new(bp.outputs["Normal"], b.inputs["Normal"])
    if transmission > 0 or alpha < 1:
        m.use_raytrace_refraction = transmission > 0
        m.thickness_mode = "SLAB"
    _out(m, b.outputs["BSDF"])
    return m


def aluminium(name="alu", tone=0.62):
    return principled(name, base=(tone, tone, tone * 1.02), metallic=1.0, roughness=0.3, rough_vary=0.06, noise_scale=180)


def dark_aluminium(name="alu.dark"):
    return principled(name, base=(0.09, 0.095, 0.1), metallic=1.0, roughness=0.34, rough_vary=0.06, noise_scale=180)


def powder(name="powder", tone=0.03, roughness=0.55, specular=0.5):
    return principled(
        name, base=(tone, tone, tone * 1.08), roughness=roughness, rough_vary=0.08, bump=0.08, noise_scale=900, specular=specular
    )


def plastic(name="plastic", tone=0.02, roughness=0.45, specular=0.5):
    return principled(name, base=(tone, tone, tone), roughness=roughness, rough_vary=0.05, specular=specular)


def pcb(name="pcb", color=(0.012, 0.03, 0.022)):
    """Solder mask: a clear lacquer over a satin board. Crisp reflections read as gloss;
    blurry ones read as grey."""
    return principled(name, base=color, roughness=0.38, coat=0.8, coat_roughness=0.08, rough_vary=0.08, noise_scale=300)


def epoxy(name="epoxy"):
    return principled(name, base=(0.014, 0.014, 0.016), roughness=0.5, rough_vary=0.08, bump=0.05, noise_scale=1500)


def gold(name="gold"):
    return principled(name, base=(1.0, 0.77, 0.34), metallic=1.0, roughness=0.18, rough_vary=0.05)


def copper(name="copper"):
    return principled(name, base=(0.96, 0.64, 0.54), metallic=1.0, roughness=0.25, rough_vary=0.06)


def glass(name="glass", roughness=0.0, tint=(1.0, 1.0, 1.0), ior=1.45):
    return principled(name, base=tint, roughness=roughness, transmission=1.0, ior=ior)


def emitter(name, color, strength):
    """Pure light, for data and status LEDs. Only bloom should spread it."""
    m, fresh = _material(name)
    if not fresh:
        return m
    e = m.node_tree.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1.0)
    e.inputs["Strength"].default_value = strength
    _out(m, e.outputs["Emission"])
    return m


def data(name, color, strength=6.0):
    """A glowing glass tile: a lit core seen through a clear, glossy shell."""
    return principled(
        name, base=color, roughness=0.08, coat=1.0, coat_roughness=0.02, emission=color, strength=strength, specular=0.6
    )


def xray(name="xray", edge=(0.75, 0.85, 1.0), edge_strength=1.5, power=3.0):
    """A shell you see through: clear where it faces the camera, catching light at its silhouette."""
    m, fresh = _material(name)
    if not fresh:
        return m
    nodes, links = m.node_tree.nodes, m.node_tree.links
    weight = nodes.new("ShaderNodeLayerWeight")
    weight.inputs["Blend"].default_value = 0.5
    curve = nodes.new("ShaderNodeMath")
    curve.operation = "POWER"
    curve.inputs[1].default_value = power
    links.new(weight.outputs["Facing"], curve.inputs[0])
    clear = nodes.new("ShaderNodeBsdfTransparent")
    glow = nodes.new("ShaderNodeEmission")
    glow.inputs["Color"].default_value = (*edge, 1.0)
    glow.inputs["Strength"].default_value = edge_strength
    gloss = nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = 0.05
    surface = nodes.new("ShaderNodeAddShader")
    links.new(glow.outputs["Emission"], surface.inputs[0])
    links.new(gloss.outputs["BSDF"], surface.inputs[1])
    mix = nodes.new("ShaderNodeMixShader")
    links.new(curve.outputs["Value"], mix.inputs["Fac"])
    links.new(clear.outputs["BSDF"], mix.inputs[1])
    links.new(surface.outputs["Shader"], mix.inputs[2])
    _out(m, mix.outputs["Shader"])
    return m


def frosted(name="frosted", tint=(0.85, 0.9, 1.0), roughness=0.12):
    """Thin glass: you see through it, and its edges catch the light. Roughness frosts it."""
    return principled(name, base=tint, roughness=roughness, transmission=1.0, ior=1.45)


def glass_sheet(name="sheet", tint=(0.85, 0.9, 1.0), glow=(0.6, 0.72, 1.0), strength=0.6):
    """Clear glass that faintly glows where you see it edge-on, the way a sheet of glass
    catches light: invisible head-on, a soft gradient toward the horizon."""
    m, fresh = _material(name)
    if not fresh:
        return m
    nodes, links = m.node_tree.nodes, m.node_tree.links
    b = nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*tint, 1.0)
    b.inputs["Roughness"].default_value = 0.0
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.45
    weight = nodes.new("ShaderNodeLayerWeight")
    weight.inputs["Blend"].default_value = 0.3
    curve = nodes.new("ShaderNodeMath")
    curve.operation = "POWER"
    curve.inputs[1].default_value = 3.0
    links.new(weight.outputs["Facing"], curve.inputs[0])
    e = nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*glow, 1.0)
    scale = nodes.new("ShaderNodeMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = strength
    links.new(curve.outputs["Value"], scale.inputs[0])
    links.new(scale.outputs["Value"], e.inputs["Strength"])
    add = nodes.new("ShaderNodeAddShader")
    links.new(b.outputs["BSDF"], add.inputs[0])
    links.new(e.outputs["Emission"], add.inputs[1])
    m.use_raytrace_refraction = True
    m.thickness_mode = "SLAB"
    _out(m, add.outputs["Shader"])
    return m


def floor(name="floor", tone=0.006, roughness=0.22):
    # Fine-grained variation only: broad patches of roughness read as fog in a dark set.
    return principled(name, base=(tone, tone, tone * 1.1), roughness=roughness, rough_vary=0.03, noise_scale=220)
