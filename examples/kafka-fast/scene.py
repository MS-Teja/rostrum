"""Why Kafka is fast: the 3D set.

Shots (style frames for now; animation comes after Gate S):
  1  a broker pulled out of its rack, its lid turned to glass
  3  the usual path: four copies, two trips across the kernel/user boundary
  4  sendfile: page cache straight to the network card, the app dark

Render one with packages/stage3d/render.py (see the README).
"""

import math

import bpy
from mathutils import Vector

from rostrum_stage import camera, flow, lights, look, parts
from rostrum_stage import materials as M
from rostrum_stage.anchors import anchor

LOOKS = {
    "keynote": {
        "accent": (0.22, 0.56, 1.0),
        "accent_strength": 3.0,
        "dim": (0.05, 0.08, 0.14),
        "agx": "AgX - Medium High Contrast",
        "exposure": 0.0,
        "floor": dict(tone=0.004, roughness=0.12),
        "bloom": 0.45,
    },
    "cutaway": {
        "accent": (0.0, 0.3, 1.0),
        "accent_strength": 1.6,
        "dim": (0.55, 0.6, 0.68),
        "agx": "AgX - Medium High Contrast",
        "exposure": 0.1,
        "floor": dict(tone=0.42, roughness=0.45),
        "bloom": 0.2,
    },
}


def build(scene, opts):
    style = LOOKS[opts["look"]]
    look.color(scene, style["agx"], style["exposure"])
    look.compositor(scene, bloom=style["bloom"])
    shot = str(opts["shot"] or "3")
    if shot == "1":
        hero(scene, opts["look"], style)
    elif shot in ("3", "4"):
        paths(scene, opts["look"], style, sendfile=shot == "4")
    else:
        raise ValueError(f"unknown shot {shot!r}")


# Shot 1 ------------------------------------------------------------------------------------


def hero(scene, name, style):
    lid = M.frosted("lid.glass", (0.88, 0.93, 1.0), 0.0)
    pull = 0.74
    z0 = 0.20
    server, p = parts.server_1u("broker", loc=(0, -pull, z0), lid_mat=lid)
    p["lid"].visible_shadow = False
    for k in list(range(-4, 0)) + list(range(1, 6)):
        parts.server_1u(f"neighbour{k}", loc=(0, 0, z0 + k * 0.0445), inside=False)
    cabinet = parts.rack("rack", 0.62, loc=(0, 0, -0.02))

    floor = parts.box("floor", (8, 8, 0.01), (0, 0, -0.03), M.floor("floor", **style["floor"]))
    floor.visible_shadow = name != "keynote"

    # Data on the board: network card to memory to drive, as lit traces.
    trace = flow.path_material("trace", style["accent"], style["accent_strength"] * 1.2, solid=name != "keynote")
    top = 0.0045 + 0.0008 + 0.0009
    routes = [
        [(-0.14, 0.235), (-0.14, 0.15), (-0.10, 0.11), (-0.10, 0.092)],
        [(-0.10, 0.092), (-0.04, 0.092), (0.04, 0.092), (0.10, 0.092)],
        [(0.10, 0.092), (0.10, 0.118)],
    ]
    for i, route in enumerate(routes):
        pts = flow.fillet([Vector((x, y, top)) for x, y in route], 0.012)
        flow.tube(f"trace{i}", pts, 0.0011, trace, parent=server)

    bpy.context.view_layer.update()
    for role, obj in (("ssd", p["ssd"]), ("cpu", p["cpu"]), ("nic", p["nic"]), ("ram", p["ram"][3])):
        anchor(role, obj.matrix_world.translation.copy())

    target = Vector((0.0, -pull + 0.06, z0 + 0.01))
    focus = Vector((-0.10, -pull + 0.02, z0 + 0.02))  # the left memory bank: the page cache
    if name == "keynote":
        rig = lights.keynote(scene, target, 0.75, key=0.35)
        flats = [o for o in scene.objects if o.name in ("broker.floor", "broker.board")]
        sides = [o for o in cabinet.children if ".side" in o.name]
        lights.exclude([rig["key"], rig["kicker"]], [floor, p["lid"]])
        lights.exclude(rig["rims"], [floor, p["lid"], *flats, *sides], "rostrum.unlit.rims")
        board_z = z0 + 0.03
        rakes = [
            lights.rake("rake.left", (-0.36, -pull + 0.02, board_z), (0.3, -pull + 0.02, z0), 0.75, 14, (0.8, 0.88, 1.0)),
            lights.rake("rake.right", (0.36, -pull + 0.12, board_z), (-0.3, -pull + 0.12, z0), 0.6, 6, (1.0, 0.93, 0.86)),
        ]
        lights.exclude(rakes, [floor, p["lid"], *sides], "rostrum.unlit.rakes")
        # A soft panel behind, seen only as a gradient in the glass lid: proof the lid is there.
        glint = lights.area("glint", target + Vector((0.25, 1.1, 1.0)), target, (1.6, 0.12), 5, (0.9, 0.94, 1.0), 180)
        lights.only([glint], [p["lid"]], "rostrum.lid")
    else:
        rig = lights.cutaway(scene, target, 0.75)
        lights.exclude([rig["key"], rig["kicker"], *rig["rims"]], [p["lid"]])
    cam = camera.rig(scene, (-0.42, -pull - 0.78, z0 + 0.92), target, lens=50, fstop=2.8)
    cam.data.dof.focus_distance = (focus - cam.location).length


# Shots 3 and 4 -----------------------------------------------------------------------------

S = 4.0  # the diagram is the real hardware at 4x, so it reads at a glance
CEILING = 0.22
USER = 0.36


def paths(scene, name, style, sendfile):
    keynote = name == "keynote"
    accent = M.data("tile.accent", style["accent"], style["accent_strength"])
    ghost = M.data("tile.dim", style["dim"], 0.4 if keynote else 0.0)
    glow = flow.path_material("path.accent", style["accent"], style["accent_strength"] * 0.9, solid=not keynote)
    faint = flow.path_material("path.faint", style["dim"], 0.6 if keynote else 0.0, solid=not keynote)
    ring = flow.path_material("ring", (0.85, 0.92, 1.0), 6.0 if keynote else 3.0)

    floor = parts.box("floor", (12, 12, 0.01), (0, 0, -0.005), M.floor("floor", **style["floor"]))
    floor.visible_shadow = not keynote

    # Kernel space, on the floor: the drive, the memory standing up, the network card.
    ssd = parts.m2_ssd("ssd", loc=(-0.68, 0.0, 0.0))
    ssd.scale = (S, S, S)
    ram = parts.dimm("ram", loc=(0.0, 0.03, 0.0))
    ram.scale = (3.2, 3.2, 3.2)
    nic = parts.nic("nic", loc=(0.80, 0.02, 0.0))
    nic.scale = (S * 0.8, S * 0.8, S * 0.8)

    # The kernel/user boundary: a pane of clear glass with the app floating above it.
    pane = M.glass_sheet("pane", strength=0.22) if keynote else M.frosted("pane", (0.9, 0.93, 1.0), 0.0)
    boundary = parts.box("boundary", (6.0, 0.9, 0.012), (0.0, 0.0, CEILING), pane, 0.004)
    # Glass casts a solid shadow in a path tracer without caustics; this pane should only be seen.
    boundary.visible_shadow = False
    # Clear glass is nearly invisible head-on; lit edges give the boundary a presence.
    edge = flow.path_material("pane.edge", (0.7, 0.8, 1.0), 1.2 if keynote else 0.0)
    flow.tube("boundary.edge", [Vector((-3.0, 0.45, CEILING + 0.006)), Vector((3.0, 0.45, CEILING + 0.006))], 0.0018, edge)
    # Software is glass; hardware is solid. The app is a slab of smoked glass.
    if keynote:
        app = M.principled("app", (0.03, 0.035, 0.05), roughness=0.12, transmission=1.0, ior=1.45)
    else:
        app = M.principled("app", (0.92, 0.93, 0.95), roughness=0.4, coat=1.0, coat_roughness=0.2)
    kafka = parts.box("kafka", (0.62, 0.34, 0.05), (0.0, 0.0, USER), app, 0.012)
    kafka.visible_shadow = False

    top = 0.031 * 3.2 + 0.021  # just above the memory stick's top edge
    page_cache = Vector((-0.12, 0.0, top))
    socket_buf = Vector((0.12, 0.0, top))
    user_buf = Vector((0.0, 0.0, USER + 0.04))
    on_ssd = Vector((-0.68, 0.0, 0.026))
    at_nic = Vector((0.66, 0.02, 0.06))
    size = (0.085, 0.085, 0.022)

    flow.tile("on_ssd", size, on_ssd, ghost if sendfile else accent)
    flow.tile("copy1", size, page_cache, accent)
    flow.tile("copy2", size, user_buf, ghost if sendfile else accent)
    flow.tile("copy3", size, socket_buf, ghost if sendfile else accent)
    flow.tile("copy4", size, at_nic, accent)

    r = 0.006
    lift = Vector((0, 0, 0.012))
    hop = lambda a, b, h: [a, Vector((a.x, a.y, h)), Vector((b.x, b.y, h)), b]  # noqa: E731
    if sendfile:
        flow.tube("p.direct", flow.fillet(hop(page_cache + lift, at_nic + lift, 0.175), 0.05), r, glow)
        second = at_nic + Vector((0, -0.05, 0.0))
        flow.tube("p.direct2", flow.fillet(hop(page_cache + Vector((0.02, -0.03, 0.012)), second, 0.16), 0.045), r * 0.7, glow)
        for i, (a, b) in enumerate(((page_cache, user_buf), (user_buf, socket_buf))):
            flow.tube(f"p.unused{i}", flow.fillet(hop(a + lift, b - lift, USER + 0.04), 0.05), r * 0.6, faint)
    else:
        flow.tube("p1", flow.fillet(hop(on_ssd + lift, page_cache + lift, 0.175), 0.05), r, glow)
        up = [page_cache + lift, Vector((page_cache.x, 0, user_buf.z)), user_buf - Vector((0.045, 0, 0))]
        flow.tube("p2", flow.fillet(up, 0.06), r, glow)
        down = [user_buf + Vector((0.045, 0, 0)), Vector((socket_buf.x, 0, user_buf.z)), socket_buf + lift]
        flow.tube("p3", flow.fillet(down, 0.06), r, glow)
        flow.tube("p4", flow.fillet(hop(socket_buf + lift, at_nic + lift, 0.175), 0.05), r, glow)
        for i, x in enumerate((page_cache.x, socket_buf.x)):
            circle = [Vector((x + 0.035 * math.cos(a), 0.035 * math.sin(a), CEILING + 0.0065)) for a in [k * 2 * math.pi / 48 for k in range(49)]]
            flow.tube(f"syscall{i}", circle, 0.0025, ring)
            anchor(f"syscall{i}", Vector((x, 0, CEILING)))

    anchor("ssd", on_ssd)
    anchor("page_cache", page_cache)
    anchor("socket_buffer", socket_buf)
    anchor("user_buffer", user_buf)
    anchor("nic", at_nic)
    anchor("kafka", Vector((0.29, 0.0, USER + 0.02)))
    anchor("boundary", Vector((-1.1, 0.0, CEILING)))

    target = Vector((0.0, 0.05, 0.12))
    if keynote:
        rig = lights.keynote(scene, target, 1.6, hdri=False)
        brackets = [o for o in scene.objects if o.name.startswith("nic.bracket") or o.name.startswith("nic.cage")]
        # A black mirror: the floor shows only what glows or is lit, never a light.
        lights.exclude([rig["key"], rig["kicker"]], [floor, boundary, kafka])
        lights.exclude(rig["rims"], [floor, boundary, *brackets], "rostrum.unlit.rims")
    else:
        rig = lights.cutaway(scene, target, 1.6)
        lights.exclude([rig["key"], rig["kicker"], *rig["rims"]], [boundary, kafka])
    camera.rig(scene, (0.0, -2.35, 0.92), Vector((0.0, 0.05, 0.17)), lens=42, fstop=5.6)
