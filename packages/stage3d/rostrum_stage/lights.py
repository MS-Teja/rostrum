"""Lighting rigs. A rig is placed relative to a subject: its centre and its size.

Lights are never visible to the camera: you see what they light and what they
reflect in, never the light itself, as on a real product set.
"""

import math
import os

import bpy
from mathutils import Vector

from . import parts

HDRI_DIR = os.environ.get("ROSTRUM_HDRI_DIR", os.path.expanduser("~/.cache/rostrum/hdri"))


def area(name, loc, target, size, power, color=(1.0, 1.0, 1.0), spread=180.0):
    d = bpy.data.lights.new(name, "AREA")
    d.shape = "RECTANGLE"
    d.size, d.size_y = size
    d.energy = power
    d.color = color
    d.spread = math.radians(spread)
    o = bpy.data.objects.new(name, d)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    # Seen only by what it lights and what reflects it: never directly, never through glass.
    o.visible_camera = False
    o.visible_transmission = False
    parts.collection().objects.link(o)
    return o


def exclude(lights, objects, name="rostrum.unlit"):
    """Keep `lights` off `objects` (light linking). A rim should draw a part's edge, not
    glare off the floor it stands on or the glass in front of it."""
    coll = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    for o in objects:
        if coll.objects.get(o.name) is None:
            coll.objects.link(o)
    for co in coll.collection_objects:
        co.light_linking.link_state = "EXCLUDE"
    for light in lights:
        light.light_linking.receiver_collection = coll


def only(lights, objects, name):
    """Let `lights` reach `objects` and nothing else: a light that exists only as a
    reflection in one pane of glass, say."""
    coll = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    for o in objects:
        if coll.objects.get(o.name) is None:
            coll.objects.link(o)
    for co in coll.collection_objects:
        co.light_linking.link_state = "INCLUDE"
    for light in lights:
        light.light_linking.receiver_collection = coll


def rake(name, loc, target, length, power, color=(1.0, 1.0, 1.0), spread=40.0):
    """A thin strip skimming a surface from the side: vertical edges catch it, flat
    surfaces don't, so detail reads as texture and the surface itself stays dark."""
    return area(name, loc, target, (0.015, length), power, color, spread)


def world(scene, color=(0.0, 0.0, 0.0), hdri=None, hdri_strength=0.3, hdri_rotation=0.0, hdri_visible=False):
    """A world that lights reflections from an HDRI while the camera sees a plain backdrop."""
    w = bpy.data.worlds.new("rostrum.world")
    w.use_nodes = True
    nodes, links = w.node_tree.nodes, w.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputWorld")
    plain = nodes.new("ShaderNodeBackground")
    plain.inputs["Color"].default_value = (*color, 1.0)
    plain.inputs["Strength"].default_value = 1.0
    if hdri is None:
        links.new(plain.outputs["Background"], out.inputs["Surface"])
    else:
        coord = nodes.new("ShaderNodeTexCoord")
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value = (0, 0, math.radians(hdri_rotation))
        env = nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(os.path.join(HDRI_DIR, hdri), check_existing=True)
        lit = nodes.new("ShaderNodeBackground")
        lit.inputs["Strength"].default_value = hdri_strength
        links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], env.inputs["Vector"])
        links.new(env.outputs["Color"], lit.inputs["Color"])
        if hdri_visible:
            links.new(lit.outputs["Background"], out.inputs["Surface"])
        else:
            path = nodes.new("ShaderNodeLightPath")
            mix = nodes.new("ShaderNodeMixShader")
            links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
            links.new(lit.outputs["Background"], mix.inputs[1])
            links.new(plain.outputs["Background"], mix.inputs[2])
            links.new(mix.outputs["Shader"], out.inputs["Surface"])
    scene.world = w
    return w


def keynote(scene, center=(0, 0, 0), scale=1.0, warmth=1.0, key=1.0, hdri=True):
    """Dark stage. A gridded softbox straight overhead lights tops without washing them;
    two low rims behind the subject draw its vertical edges; a faint kicker from the
    front keeps dark parts from merging into the void. Keep the rims off flat surfaces
    with `exclude`."""
    c = Vector(center)
    s = scale
    world(scene, (0.0015, 0.0016, 0.0019), "studio_small_09_2k.hdr" if hdri else None, 0.03, 90)
    # Straight overhead with a tight grid: outside the mirror angle of a camera looking down
    # at 30-40 degrees, so flat surfaces show it only as a crisp edge, never as a grey wash.
    k = area("key", c + Vector((0.0, 0.15, 1.6)) * s, c, (1.2 * s, 0.8 * s), 40 * key * s * s, (1.0, 0.97 * warmth, 0.93 * warmth), 35)
    rims = [
        area("rim.left", c + Vector((-1.3, 0.9, 0.25)) * s, c, (0.06 * s, 1.2 * s), 50 * s * s, (0.78, 0.86, 1.0), 70),
        area("rim.right", c + Vector((1.3, 1.0, 0.3)) * s, c, (0.06 * s, 1.2 * s), 40 * s * s, (1.0, 0.95, 0.9), 70),
    ]
    kicker = area("kicker", c + Vector((0.0, -1.5, 0.35)) * s, c, (1.4 * s, 0.4 * s), 8 * s * s, (0.85, 0.9, 1.0))
    return {"key": k, "rims": rims, "kicker": kicker}


def cutaway(scene, center=(0, 0, 0), scale=1.0):
    """Bright seamless studio, like a product page: a large overhead softbox for soft
    contact shadows, a front fill, a rim from behind. Keep the softboxes out of glass
    with `exclude`, or every pane shows a white rectangle."""
    c = Vector(center)
    s = scale
    world(scene, (0.36, 0.37, 0.39), "studio_small_03_2k.hdr", 0.12, 150)
    key = area("key", c + Vector((0.2, -0.3, 2.0)) * s, c, (2.4 * s, 1.8 * s), 70 * s * s)
    fill = area("fill", c + Vector((0.0, -2.0, 0.6)) * s, c, (2.0 * s, 1.0 * s), 18 * s * s, (0.96, 0.98, 1.0))
    rim = area("rim", c + Vector((0.0, 1.6, 0.8)) * s, c, (2.4 * s, 0.3 * s), 30 * s * s)
    return {"key": key, "rims": [rim], "kicker": fill}
