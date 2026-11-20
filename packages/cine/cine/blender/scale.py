"""A stage for scenes that span many orders of magnitude (a spacecraft, then the solar system,
then the nearest stars), and drawing that stays readable at every zoom. GPL-3.0-or-later.

    stage = ScaleStage(scene, motion)          # motion's camera is in true units (e.g. AU)
    sun = stage.dot("sun", SUN, px=9, colour=(1, .9, .7), strength=8)
    stage.line("orbit.neptune", points, px=1.2, colour=(.5, .6, .8), cyclic=True)
    stage.label("Sun", anchor=SUN, px=16, offset=(0, -14))
    stage.camera()                             # bake the camera into stage space

**Why a stage.** Blender stores positions in 32-bit floats: a camera 1 AU from a spacecraft
and stars 270,000 AU away can't share one fixed space. So everything lives under one root, in
true units, and each frame the root is moved and scaled so the camera sits K units from its aim
point. Perspective doesn't care about scale, so the picture is exactly the true one.

**Drawing that holds up across scales** (everything baked per frame from the motion's camera):
  dot     an emissive sphere kept at least `px` pixels across (a planet is a dot until it's big)
  line    a curve a constant width on screen at every point (Geometry Nodes: each point's radius
          is its distance to the camera times a width factor); draw it partway with `reveal`
  label   text facing the camera at a constant pixel height, offset in pixels from its anchor
The pixel sizes assume the render's width (render.resolution_x).
"""

import math

import bpy
from mathutils import Matrix, Vector

from ..core import kinematics as K
from . import bake, look


class ScaleStage:
    def __init__(self, scene, motion, K_units=10.0, name="cine.world"):
        self.scene, self.m, self.K = scene, motion, float(K_units)
        bake.setup(scene, motion)
        self.frames = bake.frames(motion)
        ch, cam = motion.channels, motion.camera
        self.pos = [Vector(ch[cam["pos"]](t)) for _, t in self.frames]
        self.aim = [Vector(ch[cam["aim"]](t)) for _, t in self.frames]
        self.lens = [float(ch[cam["lens"]](t)) for _, t in self.frames]
        self.dist = [max(1e-30, (a - p).length) for p, a in zip(self.pos, self.aim)]
        self.s = [self.K / d for d in self.dist]  # stage units per true unit
        self.width = scene.render.resolution_x
        self.root = bpy.data.objects.new(name, None)
        scene.collection.objects.link(self.root)
        for (f, _t), a, s in zip(self.frames, self.aim, self.s):
            self.root.location = -a * s
            self.root.scale = (s, s, s)
            self.root.keyframe_insert("location", frame=f)
            self.root.keyframe_insert("scale", frame=f)
        bake._linear(self.root)
        self.cam = self._camera()
        self._line_group = None

    # ── geometry of the view ──────────────────────────────────────────────────────────────
    def per_px(self, i, point):
        """True units per pixel at `point` in frame i (by its depth along the view)."""
        p, a = self.pos[i], self.aim[i]
        f = (a - p).normalized()
        depth = max(1e-30, (Vector(point) - p).dot(f))
        return depth * 2 * math.tan(K.hfov(self.lens[i]) / 2) / self.width

    def basis(self, i):
        f = (self.aim[i] - self.pos[i]).normalized()
        up = Vector((0, 0, 1))
        right = f.cross(up).normalized() if abs(f.dot(up)) < 0.999 else Vector((1, 0, 0))
        return f, right, right.cross(f)

    # ── drawing ───────────────────────────────────────────────────────────────────────────
    def dot(self, name, where, px=4.0, colour=(1, 1, 1), strength=4.0, min_true=0.0, visible=None):
        """An emissive sphere at `where` (a point, or a function of t), at least `px` pixels across,
        never smaller than `min_true` true units of radius. `visible`: a function of t, 0..1."""
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=16, ring_count=8, location=(0, 0, 0))
        o = bpy.context.active_object
        o.name = name
        o.data.materials.append(look.emissive(name, colour, strength))
        o.visible_shadow = False
        o.parent = self.root
        moving = callable(where)
        if not moving:
            o.location = Vector(where)
        for i, (f, t) in enumerate(self.frames):
            w = Vector(where(t)) if moving else o.location
            r = max(min_true, 0.5 * px * self.per_px(i, w))
            v = 1.0 if visible is None else max(0.0, min(1.0, visible(t)))
            if moving:
                o.location = w
                o.keyframe_insert("location", frame=f)
            o.scale = (r * v + 1e-30,) * 3
            o.keyframe_insert("scale", frame=f)
        bake._linear(o)
        return o

    def _group(self):
        """One Geometry Nodes group for every line: trim the curve to `End`, give each point a
        radius of its distance to the camera times `Width` (true units of radius per unit of
        distance: a constant width on screen), and sweep a tube along it."""
        if self._line_group:
            return self._line_group
        ng = bpy.data.node_groups.new("cine.constant_line", "GeometryNodeTree")
        it = ng.interface
        it.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        it.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        it.new_socket("Width", in_out="INPUT", socket_type="NodeSocketFloat")
        it.new_socket("End", in_out="INPUT", socket_type="NodeSocketFloat")
        it.new_socket("Camera", in_out="INPUT", socket_type="NodeSocketObject")
        it.new_socket("Material", in_out="INPUT", socket_type="NodeSocketMaterial")
        N = ng.nodes
        gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
        trim = N.new("GeometryNodeTrimCurve")
        trim.mode = "FACTOR"
        info = N.new("GeometryNodeObjectInfo")
        info.transform_space = "RELATIVE"
        pos = N.new("GeometryNodeInputPosition")
        dist = N.new("ShaderNodeVectorMath")
        dist.operation = "DISTANCE"
        mul = N.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        rad = N.new("GeometryNodeSetCurveRadius")
        circ = N.new("GeometryNodeCurvePrimitiveCircle")
        circ.inputs["Resolution"].default_value = 8
        circ.inputs["Radius"].default_value = 1.0
        tube = N.new("GeometryNodeCurveToMesh")
        mat = N.new("GeometryNodeSetMaterial")
        L = ng.links
        L.new(gi.outputs["Geometry"], trim.inputs["Curve"])
        L.new(gi.outputs["End"], [i for i in trim.inputs if i.name == "End"][0])
        L.new(gi.outputs["Camera"], info.inputs["Object"])
        L.new(pos.outputs["Position"], dist.inputs[0])
        L.new(info.outputs["Location"], dist.inputs[1])
        L.new(dist.outputs["Value"], mul.inputs[0])
        L.new(gi.outputs["Width"], mul.inputs[1])
        L.new(trim.outputs["Curve"], rad.inputs["Curve"])
        L.new(mul.outputs["Value"], rad.inputs["Radius"])
        L.new(rad.outputs["Curve"], tube.inputs["Curve"])
        if "Scale" in tube.inputs:  # Blender 5: the profile is scaled by this input, not by the curve's radius
            L.new(mul.outputs["Value"], tube.inputs["Scale"])
        L.new(circ.outputs["Curve"], tube.inputs["Profile Curve"])
        L.new(tube.outputs["Mesh"], mat.inputs["Geometry"])
        L.new(gi.outputs["Material"], mat.inputs["Material"])
        L.new(mat.outputs["Geometry"], go.inputs["Geometry"])
        self._line_group = ng
        return ng

    def line(self, name, points, px=1.0, colour=(1, 1, 1), strength=2.0, cyclic=False, reveal=None, anchor=None):
        """A polyline through `points` (true units), a constant `px` pixels wide on screen at every
        point along it, even where it passes the camera. `reveal(t)` draws it partway (0..1)."""
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        sp = cu.splines.new("POLY")
        sp.points.add(len(points) - 1)
        for k, p in enumerate(points):
            sp.points[k].co = (p[0], p[1], p[2], 1.0)
        sp.use_cyclic_u = cyclic
        o = bpy.data.objects.new(name, cu)
        self.scene.collection.objects.link(o)
        o.visible_shadow = False
        o.parent = self.root
        ng = self._group()
        mod = o.modifiers.new("cine.line", "NODES")
        mod.node_group = ng
        ident = {it.name: it.identifier for it in ng.interface.items_tree if getattr(it, "in_out", "") == "INPUT"}
        ins = mod.properties.inputs
        getattr(ins, ident["Camera"]).value = self.cam
        getattr(ins, ident["Material"]).value = look.emissive(name, colour, strength)
        w_in, e_in = getattr(ins, ident["Width"]), getattr(ins, ident["End"])
        e_in.value = 1.0
        for i, (f, t) in enumerate(self.frames):
            w_in.value = 0.5 * px * 2 * math.tan(K.hfov(self.lens[i]) / 2) / self.width
            w_in.keyframe_insert("value", frame=f)
            if reveal is not None:
                e_in.value = max(0.0, min(1.0, reveal(t)))
                e_in.keyframe_insert("value", frame=f)
        bake._linear(o)
        return o

    def label(self, text, anchor, px=16.0, offset=(0.0, 0.0), colour=(0.92, 0.93, 0.95), strength=1.6, visible=None, font=None,
              align="CENTER"):
        """Text facing the camera, `px` pixels tall, offset (x, y) pixels from `anchor` (a point or
        a function of t). `visible(t)` 0..1 fades it (by scale, from the anchor)."""
        cu = bpy.data.curves.new("label." + text, "FONT")
        cu.body = text
        cu.align_x, cu.align_y = align, "CENTER"
        if font:
            cu.font = font
        o = bpy.data.objects.new("label." + text, cu)
        self.scene.collection.objects.link(o)
        o.data.materials.append(look.emissive("label." + text, colour, strength))
        o.visible_shadow = False
        o.parent = self.root
        o.rotation_mode = "QUATERNION"
        for i, (f, t) in enumerate(self.frames):
            w = Vector(anchor(t) if callable(anchor) else anchor)
            fw, right, up = self.basis(i)
            u = self.per_px(i, w)
            v = 1.0 if visible is None else max(0.0, min(1.0, visible(t)))
            o.location = w + right * offset[0] * u + up * offset[1] * u
            o.rotation_quaternion = Matrix((right, up, -fw)).transposed().to_quaternion()
            sz = px * u * 1.35 * v + 1e-30  # a font's em is about 1.35 x its cap height
            o.scale = (sz, sz, sz)
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_quaternion", frame=f)
            o.keyframe_insert("scale", frame=f)
        bake._linear(o)
        return o

    def _camera(self, name="cine.camera", clip=(0.05, 1e8)):
        """The camera in stage space: K units from its aim, every frame (made with the stage, so
        lines can measure their distance to it)."""
        from ..core.curve import Curve, Motion

        m2 = Motion(self.m.name + ".stage", self.m.t0, self.m.t1, self.m.fps)
        pos = [list((p - a) * s) for p, a, s in zip(self.pos, self.aim, self.s)]
        m2.channels = {"cam.pos": Curve(samples=pos, fps=self.m.fps, t0=self.m.t0),
                       "cam.aim": Curve(samples=[[0.0, 0.0, 0.0]] * len(pos), fps=self.m.fps, t0=self.m.t0),
                       "cam.lens": Curve(samples=self.lens, fps=self.m.fps, t0=self.m.t0)}
        return bake.camera(self.scene, m2, name=name, clip=clip)

    def camera(self, clip=(0.05, 1e8)):
        """The stage's camera (already baked)."""
        self.cam.data.clip_start, self.cam.data.clip_end = clip
        return self.cam

def blackbody_rgb(T):
    """An approximate linear RGB for a blackbody at T kelvin (for star dots), normalised to 1."""
    t = T / 100.0
    r = 255.0 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    c = [max(0.0, min(255.0, x)) / 255.0 for x in (r, g, b)]
    c = [x ** 2.2 for x in c]  # sRGB-ish to linear
    k = max(c) or 1.0
    return tuple(x / k for x in c)
