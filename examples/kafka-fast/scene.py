"""Why Kafka is fast: the 3D set.

Shots:
  1     a broker pulled out of its rack, its lid turned to glass (still)
  3     the usual path: four copies, two trips across the kernel/user boundary (still)
  4     sendfile: page cache straight to the network card, the app dark (still)
  anim  15 s: shots 3 and 4 animated to the narration (needs --timing)

Render one with packages/stage3d/render.py (see the README).
"""

import math

import bpy
from mathutils import Vector

from rostrum_stage import bake, camera, flow, lights, look, parts
from rostrum_stage import materials as M
from rostrum_stage import timing as tm
from rostrum_stage.anchors import anchor
from rostrum_stage.easing import ease, lerp, progress, spring

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
    elif shot == "anim":
        zero_copy(scene, opts["look"], style, opts)
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


def _stage(name, style):
    """The set shared by shots 3, 4 and the animation: hardware on a black mirror floor,
    a glass ceiling between kernel and user space, Kafka floating above it."""
    keynote = name == "keynote"
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
    at = {
        "page_cache": Vector((-0.12, 0.0, top)),
        "socket_buffer": Vector((0.12, 0.0, top)),
        "user_buffer": Vector((0.0, 0.0, USER + 0.04)),
        "ssd": Vector((-0.68, 0.0, 0.026)),
        "nic": Vector((0.66, 0.02, 0.06)),
    }
    lift = Vector((0, 0, 0.012))
    hop = lambda a, b, h: [a, Vector((a.x, a.y, h)), Vector((b.x, b.y, h)), b]  # noqa: E731
    routes = {
        "p1": flow.fillet(hop(at["ssd"] + lift, at["page_cache"] + lift, 0.175), 0.05),
        "p2": flow.fillet([at["page_cache"] + lift, Vector((at["page_cache"].x, 0, at["user_buffer"].z)), at["user_buffer"] - Vector((0.045, 0, 0))], 0.06),
        "p3": flow.fillet([at["user_buffer"] + Vector((0.045, 0, 0)), Vector((at["socket_buffer"].x, 0, at["user_buffer"].z)), at["socket_buffer"] + lift], 0.06),
        "p4": flow.fillet(hop(at["socket_buffer"] + lift, at["nic"] + lift, 0.175), 0.05),
        "direct": flow.fillet(hop(at["page_cache"] + lift, at["nic"] + lift, 0.175), 0.05),
    }
    for role, point in at.items():
        anchor(role, point)
    anchor("kafka", Vector((0.29, 0.0, USER + 0.02)))
    anchor("boundary", Vector((-1.1, 0.0, CEILING)))
    return {"floor": floor, "boundary": boundary, "kafka": kafka, "at": at, "routes": routes}


def _rings(name, xs, mat_for):
    """The two places the usual path crosses the glass: one ring per system call."""
    out = []
    for i, x in enumerate(xs):
        circle = [Vector((x + 0.035 * math.cos(a), 0.035 * math.sin(a), CEILING + 0.0065)) for a in [k * 2 * math.pi / 48 for k in range(49)]]
        out.append(flow.tube(f"syscall{i}", circle, 0.0025, mat_for(i)))
        anchor(f"syscall{i}", Vector((x, 0, CEILING)))
    return out


def _light_and_frame(scene, name, st):
    target = Vector((0.0, 0.05, 0.12))
    if name == "keynote":
        rig = lights.keynote(scene, target, 1.6, hdri=False)
        brackets = [o for o in scene.objects if o.name.startswith("nic.bracket") or o.name.startswith("nic.cage")]
        # A black mirror: the floor shows only what glows or is lit, never a light.
        lights.exclude([rig["key"], rig["kicker"]], [st["floor"], st["boundary"], st["kafka"]])
        lights.exclude(rig["rims"], [st["floor"], st["boundary"], *brackets], "rostrum.unlit.rims")
    else:
        rig = lights.cutaway(scene, target, 1.6)
        lights.exclude([rig["key"], rig["kicker"], *rig["rims"]], [st["boundary"], st["kafka"]])
    return camera.rig(scene, (0.0, -2.35, 0.92), Vector((0.0, 0.05, 0.17)), lens=42, fstop=5.6)


def paths(scene, name, style, sendfile):
    keynote = name == "keynote"
    accent = M.data("tile.accent", style["accent"], style["accent_strength"])
    ghost = M.data("tile.dim", style["dim"], 0.4 if keynote else 0.0)
    glow = flow.path_material("path.accent", style["accent"], style["accent_strength"] * 0.9, solid=not keynote)
    faint = flow.path_material("path.faint", style["dim"], 0.6 if keynote else 0.0, solid=not keynote)
    ring = flow.path_material("ring", (0.85, 0.92, 1.0), 6.0 if keynote else 3.0)

    st = _stage(name, style)
    at, routes = st["at"], st["routes"]
    size = (0.085, 0.085, 0.022)
    flow.tile("on_ssd", size, at["ssd"], ghost if sendfile else accent)
    flow.tile("copy1", size, at["page_cache"], accent)
    flow.tile("copy2", size, at["user_buffer"], ghost if sendfile else accent)
    flow.tile("copy3", size, at["socket_buffer"], ghost if sendfile else accent)
    flow.tile("copy4", size, at["nic"], accent)

    r = 0.006
    if sendfile:
        lift = Vector((0, 0, 0.012))
        flow.tube("p.direct", routes["direct"], r, glow)
        second = at["nic"] + Vector((0, -0.05, 0.0))
        hop = [at["page_cache"] + Vector((0.02, -0.03, 0.012)), Vector((at["page_cache"].x + 0.02, -0.03, 0.16)), Vector((second.x, second.y, 0.16)), second + lift]
        flow.tube("p.direct2", flow.fillet(hop, 0.045), r * 0.7, glow)
        flow.tube("p.unused0", routes["p2"], r * 0.6, faint)
        flow.tube("p.unused1", routes["p3"], r * 0.6, faint)
    else:
        for key in ("p1", "p2", "p3", "p4"):
            flow.tube(key, routes[key], r, glow)
        _rings("syscall", (at["page_cache"].x, at["socket_buffer"].x), lambda i: ring)
    _light_and_frame(scene, name, st)


# The animation ----------------------------------------------------------------------------

LEAD = 0.5  # seconds of picture before the narrator starts; the overlay uses the same


def zero_copy(scene, name, style, opts):
    """15 s: the usual path drawn copy by copy as it's named, then sendfile's shortcut.
    Every event is a function of the narration's cue times."""
    timing, fps = opts["timing"], opts["fps"]
    if timing is None:
        raise ValueError("the animation needs --timing (examples/kafka-fast/timing.js)")
    cue = lambda key: tm.cue_time(timing, key, LEAD)  # noqa: E731
    keynote = name == "keynote"
    st = _stage(name, style)
    at, routes = st["at"], st["routes"]
    size = (0.085, 0.085, 0.022)
    accent, k = style["accent"], style["accent_strength"]

    tiles = {"source": flow.tile("source", size, at["ssd"], M.data("tile.source", accent, k))}
    for i, role in enumerate(("page_cache", "user_buffer", "socket_buffer", "nic"), 1):
        tiles[i] = flow.tile(f"copy{i}", size, at[role], M.data(f"tile.copy{i}", accent, k))
    tubes = {key: flow.tube(key, routes[key], 0.006, flow.path_material(f"path.{key}", accent, k * 0.9)) for key in routes}
    for tube in tubes.values():
        tube.data.bevel_factor_mapping_end = "SPLINE"
    rings = _rings("syscall", (at["page_cache"].x, at["socket_buffer"].x), lambda i: M.emitter(f"ring{i}", (0.85, 0.92, 1.0), 1.5))
    pulse = flow.tile("pulse", (0.05, 0.05, 0.05), Vector(), M.emitter("pulse", (0.75, 0.88, 1.0), 30.0))

    # Each leg ends on its word: the data arrives as the narrator names where it lands.
    legs = [
        ("p1", cue("b1:cache"), 1, None),
        ("p2", cue("b1:user"), 2, 0),
        ("p3", cue("b1:socket"), 3, 1),
        ("p4", cue("b1:nic"), 4, None),
        ("direct", cue("b2:straight") + 0.75, 4, None),
    ]
    travel = 0.6
    sendfile, straight = cue("b2:sendfile"), cue("b2:straight")
    pts = {key: routes[key] for key in routes}

    def leg_progress(t, arrive):
        return ease.move(progress(t, arrive - travel, travel))

    def pulse_at(t):
        for key, arrive, _, _ in legs:
            if arrive - travel <= t <= arrive + 0.05:
                return flow.point_at(pts[key], leg_progress(t, arrive))
        return Vector((0, 0, -5))  # parked out of sight between legs

    def pulse_scale(t):
        live = any(arrive - travel <= t <= arrive + 0.05 for _, arrive, _, _ in legs)
        return (1.0, 1.0, 1.0) if live else (0.0, 0.0, 0.0)

    def drawn(key, arrive):
        return lambda t: leg_progress(t, arrive)

    def copy_scale(arrive, again=None):
        pop = spring(0.35, 0.65)
        def fn(t):
            v = pop.at(t - arrive) if t >= arrive else 0.0
            if again is not None and t >= again:
                v = 1.0 + 0.25 * math.sin(min(1.0, (t - again) / 0.35) * math.pi)
            return (v, v, v)
        return fn

    def dim_after(start, high, low):
        return lambda t: lerp(high, low, ease.move(progress(t, start, 0.6)))

    def crossing(i, arrive):
        # The pulse crosses the glass halfway through its climb or descent.
        when = arrive - travel * (0.55 if i == 0 else 0.45)
        return lambda t: 1.5 + 14.0 * math.exp(-max(0.0, t - when) / 0.25) * (t >= when)

    source_breath = lambda t: k * (1.0 + 1.2 * math.exp(-max(0.0, t - cue("b1:four")) / 0.4) * (t >= cue("b1:four")))  # noqa: E731
    channels = [
        (pulse, "location", pulse_at),
        (pulse, "scale", pulse_scale),
        (bake.strength(tiles["source"].data.materials[0]), "default_value", source_breath),
    ]
    for key, arrive, n, ring in legs:
        channels.append((tubes[key].data, "bevel_factor_end", drawn(key, arrive)))
    for n in (1, 2, 3):
        arrive = legs[n - 1][1]
        channels.append((tiles[n], "scale", copy_scale(arrive)))
    channels.append((tiles[4], "scale", copy_scale(legs[3][1], again=legs[4][1])))
    for i, (key, arrive, _, _) in enumerate(legs[1:3]):
        channels.append((bake.strength(rings[i].data.materials[0]), "default_value",
                         lambda t, c=crossing(i, arrive), d=dim_after(sendfile, 1.0, 0.1): c(t) * d(t)))
    # sendfile: the trip through user space dims, and so does the socket buffer it fed.
    for key in ("p2", "p3", "p4"):
        channels.append((bake.strength(tubes[key].data.materials[0]), "default_value", dim_after(sendfile, k * 0.9, 0.12)))
    for n in (2, 3):
        channels.append((bake.strength(tiles[n].data.materials[0]), "default_value", dim_after(sendfile, k, 0.15)))

    # One slow drift across the set, so the depth reads; a touch closer for sendfile.
    cam = _light_and_frame(scene, name, st)
    end = timing["duration"] + LEAD + TAIL
    frames = list(range(1, int(round(end * fps)) + 1))
    start_loc, end_loc = Vector((-0.36, -2.5, 1.02)), Vector((0.2, -2.25, 0.88))
    look_at = Vector((0.0, 0.05, 0.17))

    def cam_loc(t):
        return start_loc.lerp(end_loc, ease.move(progress(t, 0.0, end)))

    channels.append((cam, "location", cam_loc))
    channels.append((cam, "rotation_euler", lambda t: (look_at - cam_loc(t)).to_track_quat("-Z", "Y").to_euler()))
    channels.append((cam.data.dof, "focus_distance", lambda t: (look_at - cam_loc(t)).length))
    bake.bake(scene, fps, frames, channels)
    look.motion_blur(scene, True, 0.5)


TAIL = 1.2
