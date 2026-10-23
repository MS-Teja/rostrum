"""Render settings, colour and the compositor: the parts of the look that aren't in the scene."""

import sys

import bpy

GPU_BACKENDS = ("METAL",) if sys.platform == "darwin" else ("OPTIX", "CUDA", "HIP", "ONEAPI")


def render(scene, engine="cycles", samples=None, res=(1920, 1080), pct=100, fps=30):
    r = scene.render
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = pct
    r.fps = fps
    r.film_transparent = False
    if engine == "cycles":
        r.engine = "CYCLES"
        c = scene.cycles
        c.device = "GPU" if _use_gpu() else "CPU"
        c.samples = samples or 128
        c.use_adaptive_sampling = True
        c.adaptive_threshold = 0.01
        c.use_denoising = True
        c.denoiser = "OPENIMAGEDENOISE"
        c.denoising_use_gpu = True
        # Product-shot settings: enough bounces for glass inside glass, no caustics,
        # and a clamp so a hot emitter can't throw fireflies across the frame.
        c.max_bounces = 10
        c.transmission_bounces = 10
        c.glossy_bounces = 4
        c.diffuse_bounces = 3
        c.caustics_reflective = False
        c.caustics_refractive = False
        c.sample_clamp_indirect = 8.0
        c.blur_glossy = 0.5
        # Keep the scene on the GPU between frames of an animation instead of rebuilding it.
        scene.render.use_persistent_data = True
    elif engine == "eevee":
        r.engine = "BLENDER_EEVEE"
        e = scene.eevee
        e.taa_render_samples = samples or 64
        e.use_raytracing = True
        e.use_shadows = True
        e.use_fast_gi = True
    else:
        raise ValueError(f"unknown engine {engine!r}")


def _use_gpu():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in GPU_BACKENDS:
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            return True
    return False


def color(scene, look="AgX - Medium High Contrast", exposure=0.0):
    """AgX keeps hot emitters from clipping to flat colour: bright light desaturates like film."""
    vs = scene.view_settings
    vs.view_transform = "AgX"
    vs.look = look
    vs.exposure = exposure
    vs.gamma = 1.0


def motion_blur(scene, on=True, shutter=0.5):
    scene.render.use_motion_blur = on
    scene.render.motion_blur_shutter = shutter


def compositor(scene, bloom=0.25, threshold=1.0, size=0.18, dispersion=0.006):
    """Bloom around emitters, then a touch of lens dispersion at the frame's edges."""
    tree = bpy.data.node_groups.new("rostrum.comp", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    nodes, links = tree.nodes, tree.links

    layers = nodes.new("CompositorNodeRLayers")
    last = layers.outputs["Image"]

    if bloom > 0:
        glare = nodes.new("CompositorNodeGlare")
        glare.inputs["Type"].default_value = "Bloom"
        glare.inputs["Quality"].default_value = "High"
        glare.inputs["Threshold"].default_value = threshold
        glare.inputs["Strength"].default_value = bloom
        glare.inputs["Size"].default_value = size
        links.new(last, glare.inputs["Image"])
        last = glare.outputs["Image"]

    if dispersion > 0:
        lens = nodes.new("CompositorNodeLensdist")
        lens.inputs["Dispersion"].default_value = dispersion
        lens.inputs["Fit"].default_value = True
        links.new(last, lens.inputs["Image"])
        last = lens.outputs["Image"]

    out = nodes.new("NodeGroupOutput")
    links.new(last, out.inputs["Image"])
    scene.compositing_node_group = tree
    scene.render.use_compositing = True
    return tree
