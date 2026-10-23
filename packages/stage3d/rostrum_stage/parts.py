"""Procedural hardware. Every part is boxes and cylinders with bevelled edges and real
dimensions in metres: bevels are what catch light, and real sizes keep depth of field honest.

Each builder returns an empty that parents the part, so a part moves as one.
"""

import math

import bmesh
import bpy

from . import materials as M


def collection(name="rostrum"):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def empty(name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None)
    o.empty_display_size = 0.02
    o.location, o.rotation_euler = loc, rot
    o.parent = parent
    collection().objects.link(o)
    return o


def _finish(obj, mat, loc, rot, parent, bevel, segments, smooth=True):
    if smooth:
        obj.data.shade_smooth()
    if bevel > 0:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = segments
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(40)
        mod.harden_normals = True
    if mat is not None:
        obj.data.materials.append(mat)
    obj.location, obj.rotation_euler = loc, rot
    obj.parent = parent
    collection().objects.link(obj)
    return obj


def box(name, size, loc=(0, 0, 0), mat=None, bevel=0.0, segments=3, rot=(0, 0, 0), parent=None):
    """A box of `size` (x, y, z) centred on `loc`."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    return _finish(obj, mat, loc, rot, parent, min(bevel, min(size) * 0.49), segments)


def cylinder(name, radius, depth, loc=(0, 0, 0), mat=None, bevel=0.0, verts=48, rot=(0, 0, 0), parent=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=radius, radius2=radius, depth=depth)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    return _finish(obj, mat, loc, rot, parent, min(bevel, radius * 0.49, depth * 0.49), 3)


def array(obj, count, offset):
    """Repeat `obj` `count` times, each copy shifted by `offset` metres."""
    mod = obj.modifiers.new("array", "ARRAY")
    mod.count = count
    mod.use_relative_offset = False
    mod.use_constant_offset = True
    mod.constant_offset_displace = offset
    # Bevel after the array, so every copy gets its edges.
    if "bevel" in obj.modifiers:
        bpy.context.view_layer.objects.active = obj
        obj.modifiers.move(obj.modifiers.find("array"), 0)
    return obj


# Parts -------------------------------------------------------------------------------------


def dimm(name, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), chip_mat=None):
    """A server RAM stick, standing up: 133 mm long, 31 mm tall, chips on both faces."""
    root = empty(name, loc, rot, parent)
    box(f"{name}.board", (0.1335, 0.0012, 0.031), (0, 0, 0.0155), M.pcb(), 0.0004, parent=root)
    box(f"{name}.pins", (0.124, 0.00125, 0.0032), (0, 0, 0.0016), M.gold(), 0.0002, parent=root)
    chips = chip_mat or M.epoxy()
    for side in (-1, 1):
        c = box(f"{name}.chips{side}", (0.0095, 0.0011, 0.0115), (-0.0548, side * 0.00115, 0.017), chips, 0.0003, parent=root)
        array(c, 9, (0.0137, 0, 0))
    return root


def dimm_slot(name, parent=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    root = empty(name, loc, rot, parent)
    box(f"{name}.body", (0.142, 0.0068, 0.0075), (0, 0, 0.00375), M.plastic("slot", 0.012), 0.0006, parent=root)
    for sx in (-1, 1):
        box(f"{name}.latch{sx}", (0.006, 0.0075, 0.014), (sx * 0.0735, 0, 0.007), M.plastic("latch", 0.06, 0.4), 0.0008, parent=root)
    return root


def m2_ssd(name, parent=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """An M.2 2280 NVMe drive lying flat: 80 x 22 mm."""
    root = empty(name, loc, rot, parent)
    box(f"{name}.board", (0.080, 0.022, 0.0008), (0, 0, 0.0004), M.pcb("pcb.black", (0.006, 0.006, 0.007)), 0.0003, parent=root)
    box(f"{name}.pins", (0.004, 0.019, 0.00085), (-0.0385, 0, 0.0004), M.gold(), 0.0001, parent=root)
    box(f"{name}.controller", (0.012, 0.012, 0.0012), (-0.022, 0, 0.0014), M.epoxy(), 0.0003, parent=root)
    for i, x in enumerate((0.0, 0.021)):
        box(f"{name}.nand{i}", (0.0165, 0.0135, 0.0012), (x, 0, 0.0014), M.epoxy(), 0.0003, parent=root)
    box(f"{name}.label", (0.058, 0.0195, 0.0002), (0.0, 0, 0.00215), M.principled("label", (0.07, 0.07, 0.075), roughness=0.6, metallic=0.3), 0.0001, parent=root)
    return root


def heatsink(name, size=(0.09, 0.09, 0.024), fins=36, parent=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """A low-profile 1U heatsink: copper base, dense aluminium fins."""
    root = empty(name, loc, rot, parent)
    w, d, h = size
    box(f"{name}.base", (w, d, 0.004), (0, 0, 0.002), M.copper(), 0.0006, parent=root)
    pitch = w / fins
    fin = box(f"{name}.fins", (pitch * 0.32, d, h - 0.004), (-w / 2 + pitch / 2, 0, 0.004 + (h - 0.004) / 2), M.aluminium(), 0.0002, parent=root)
    array(fin, fins, (pitch, 0, 0))
    return root


def fan(name, size=0.04, depth=0.028, parent=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """A 40 mm fan seen from above: housing, dark throat, hub and blades."""
    root = empty(name, loc, rot, parent)
    wall = 0.0025
    housing = M.plastic("fan", 0.004, 0.62, 0.3)
    for i, (sx, sy) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
        size_xy = (wall, size, depth) if sx else (size, wall, depth)
        box(f"{name}.wall{i}", size_xy, (sx * (size - wall) / 2, sy * (size - wall) / 2, depth / 2), housing, 0.0008, parent=root)
    cylinder(f"{name}.throat", size * 0.47, 0.001, (0, 0, 0.0005), M.plastic("throat", 0.004, 0.8), parent=root)
    cylinder(f"{name}.hub", size * 0.17, depth * 0.85, (0, 0, depth * 0.45), housing, bevel=0.002, parent=root)
    for i in range(7):
        a = i * 2 * math.pi / 7
        box(
            f"{name}.blade{i}",
            (size * 0.27, size * 0.11, 0.0012),
            (math.cos(a) * size * 0.3, math.sin(a) * size * 0.3, depth * 0.7),
            housing,
            0.0005,
            rot=(math.radians(28), 0, a),
            parent=root,
        )
    return root


def nic(name, parent=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """A dual-port network card lying flat, ports facing +x."""
    root = empty(name, loc, rot, parent)
    box(f"{name}.board", (0.168, 0.069, 0.0016), (0, 0, 0.0008), M.pcb("pcb.nic", (0.006, 0.016, 0.03)), 0.0004, parent=root)
    box(f"{name}.edge", (0.09, 0.0017, 0.009), (-0.02, -0.0353, 0.0), M.gold(), 0.0002, parent=root)
    heatsink(f"{name}.sink", (0.032, 0.032, 0.012), 14, root, (0.0, 0.004, 0.0016))
    box(f"{name}.bracket", (0.0012, 0.12, 0.0185), (0.0846, 0.0, 0.0093), M.aluminium("bracket", 0.5), 0.0003, parent=root)
    for i, y in enumerate((-0.014, 0.012)):
        cage = box(f"{name}.cage{i}", (0.05, 0.019, 0.0088), (0.06, y, 0.0062), M.aluminium("cage", 0.7), 0.0005, parent=root)
        box(f"{name}.mouth{i}", (0.002, 0.016, 0.0062), (0.0855, y, 0.0062), M.plastic("mouth", 0.002, 0.9), parent=root)
        box(f"{name}.led{i}", (0.0012, 0.003, 0.0016), (0.0856, y + 0.0105, 0.0118), M.emitter("led.green", (0.1, 1.0, 0.35), 25.0), parent=root)
        cage.name = f"{name}.cage{i}"
    return root


def drive_bay(name, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), led=True):
    """The front of a 2.5-inch hot-swap caddy, as seen on a server's face."""
    root = empty(name, loc, rot, parent)
    box(f"{name}.face", (0.07, 0.004, 0.0145), (0, 0, 0), M.dark_aluminium(), 0.0006, parent=root)
    box(f"{name}.handle", (0.05, 0.003, 0.004), (0.004, -0.003, -0.002), M.aluminium("handle", 0.55), 0.0012, parent=root)
    if led:
        box(f"{name}.led", (0.0022, 0.002, 0.0022), (-0.03, -0.0021, 0.004), M.emitter("led.blue", (0.25, 0.55, 1.0), 30.0), parent=root)
    return root


def server_1u(name, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), lid_mat=None, inside=True):
    """A 1U server, 440 x 700 x 44.5 mm, front face at -y. Returns (root, parts by role)."""
    root = empty(name, loc, rot, parent)
    W, D, H = 0.44, 0.70, 0.0445
    shell = M.powder()
    box(f"{name}.floor", (W, D, 0.0015), (0, 0, 0.00075), M.powder("tray", 0.008, 0.75, 0.25), 0.0005, parent=root)
    for sx in (-1, 1):
        box(f"{name}.side{sx}", (0.0015, D, H), (sx * (W / 2 - 0.00075), 0, H / 2), shell, 0.0004, parent=root)
    box(f"{name}.back", (W, 0.0015, H), (0, D / 2 - 0.00075, H / 2), shell, 0.0004, parent=root)
    box(f"{name}.bezel", (W + 0.004, 0.012, H), (0, -D / 2 + 0.006, H / 2), M.aluminium("bezel", 0.58), 0.0012, parent=root)
    for i in range(4):
        drive_bay(f"{name}.bay{i}", root, (-0.155 + i * 0.075, -D / 2 - 0.0005, H * 0.52), led=True)
    box(f"{name}.ears", (W + 0.04, 0.003, H * 0.9), (0, -D / 2 + 0.0015, H / 2), M.aluminium("ear", 0.5), 0.001, parent=root)
    parts = {"root": root}
    if inside:
        box(f"{name}.board", (W - 0.02, 0.44, 0.0016), (0, 0.06, 0.0045), M.pcb("pcb.main", (0.006, 0.008, 0.007)), 0.0005, parent=root)
        for i in range(7):
            fan(f"{name}.fan{i}", 0.04, 0.03, root, (-0.18 + i * 0.06, -0.20, 0.0015))
        parts["cpu"] = heatsink(f"{name}.cpu", (0.095, 0.11, 0.026), 38, root, (0.0, 0.02, 0.0053))
        ram = []
        for side in (-1, 1):
            for j in range(6):
                x = side * (0.074 + j * 0.0105)
                dimm_slot(f"{name}.slot{side}{j}", root, (x, 0.02, 0.0053), (0, 0, math.radians(90)))
                ram.append(dimm(f"{name}.dimm{side}{j}", root, (x, 0.02, 0.0083), (0, 0, math.radians(90))))
        parts["ram"] = ram
        parts["ssd"] = m2_ssd(f"{name}.ssd", root, (0.10, 0.16, 0.0053), (0, 0, math.radians(90)))
        parts["nic"] = nic(f"{name}.nic", root, (-0.12, 0.27, 0.016))
        box(f"{name}.psu", (0.085, 0.16, 0.04), (0.17, 0.27, 0.0215), M.aluminium("psu", 0.45), 0.001, parent=root)
    lid = box(f"{name}.lid", (W, D, 0.0012), (0, 0, H - 0.0006), lid_mat or shell, 0.0004, parent=root)
    parts["lid"] = lid
    return root, parts


def rack(name, height, parent=None, loc=(0, 0, 0)):
    """A 19-inch rack cabinet seen from the front: two posts, matte side panels, a back wall.
    The panels hide the servers' flanks, as a real cabinet does."""
    root = empty(name, loc, (0, 0, 0), parent)
    post = M.dark_aluminium("post")
    panel = M.powder("cabinet", 0.012)
    for sx in (-1, 1):
        box(f"{name}.post{sx}", (0.016, 0.04, height), (sx * 0.2365, -0.36, height / 2), post, 0.001, parent=root)
        box(f"{name}.side{sx}", (0.012, 1.0, height), (sx * 0.30, 0.12, height / 2), panel, 0.002, parent=root)
    box(f"{name}.back", (0.62, 0.012, height), (0, 0.62, height / 2), panel, 0.002, parent=root)
    return root
