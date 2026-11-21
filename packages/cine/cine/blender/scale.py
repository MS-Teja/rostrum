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
  label   text facing the camera at a constant pixel height, offset in pixels from its anchor.
          It holds one place (Teja, 2026-11-21: "Texts are constantly changing, they should be
          at a constant place"): `visible(t)` fades it in and out at a constant size, and with
          `avoid=True` the place round its anchor is chosen once for each appearance (the one
          that crosses the least of the lines, dots, rings and labels drawn so far, over the
          whole appearance) and held until it leaves. `stage.text_flags()` checks every label
          (cine/core/text.py): brief, moving, re-placed, ticking, flash, busy
  ring    a marker ring of constant pixel radius, facing the camera (for things too small to see)
  plane   a faint sheet with a grid whose spacing follows the view (the planets' plane)
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
        self._lines = []   # every line drawn: its points, reveal and moving origin (labels avoid them)
        self._proj = {}
        self._marks = []   # dots and rings: where, size in px, visibility (labels avoid them too)
        self._boxes = {}   # frame -> boxes of the labels already placed (later labels avoid them)
        self._labels = []  # every label as drawn: per-frame screen place, anchor and opacity (text_flags)
        # the view's width at the aim, in true units, each frame
        self.fields = [2 * d * math.tan(K.hfov(L) / 2) for d, L in zip(self.dist, self.lens)]

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
        self._marks.append({"where": where, "px": px, "visible": visible, "glow": True})
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

    def line(self, name, points, px=1.0, colour=(1, 1, 1), strength=2.0, cyclic=False, reveal=None, anchor=None, origin=None):
        """A polyline through `points` (true units), a constant `px` pixels wide on screen at every
        point along it, even where it passes the camera. `reveal(t)` draws it partway (0..1).
        `origin(t)`: the points are relative to a moving point (a path seen from a planet)."""
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
        if origin is not None:  # hang it from an empty that follows the moving origin
            e = bpy.data.objects.new(name + ".origin", None)
            self.scene.collection.objects.link(e)
            e.parent = self.root
            for f, t in self.frames:
                e.location = Vector(origin(t))
                e.keyframe_insert("location", frame=f)
            bake._linear(e)
            o.parent = e
        pts = [tuple(p) for p in points] + ([tuple(points[0])] if cyclic else [])
        cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1] + math.dist(a, b))
        self._lines.append({"points": pts, "cum": cum, "reveal": reveal, "origin": origin})
        self._proj = {}
        ng = self._group()  # (labels placed earlier didn't see this line: draw lines before labels)
        mod = o.modifiers.new("cine.line", "NODES")
        mod.node_group = ng
        ident = {it.name: it.identifier for it in ng.interface.items_tree if getattr(it, "in_out", "") == "INPUT"}
        ins = mod.properties.inputs
        getattr(ins, ident["Camera"]).value = self.cam
        getattr(ins, ident["Material"]).value = self._line_material(name, colour, strength)
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

    def _line_material(self, name, colour, strength, near=(0.08, 0.3)):
        """Emission that fades out where the line passes close to the camera: within `near` of the
        aim's distance (the stage keeps the camera K units from its aim). A line sweeping just past
        the lens is a blurred band that pops in from the frame's edge, never something to read.
        The emission node keeps its default name, "Emission", so its strength can be keyed."""
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        N, L = nt.nodes, nt.links
        em = N.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*colour, 1.0)
        em.inputs["Strength"].default_value = strength
        tc = N.new("ShaderNodeTexCoord")
        d = N.new("ShaderNodeVectorMath")
        d.operation = "LENGTH"
        L.new(tc.outputs["Camera"], d.inputs[0])
        fade = N.new("ShaderNodeMapRange")
        fade.clamp = True
        fade.inputs["From Min"].default_value = near[0] * self.K
        fade.inputs["From Max"].default_value = near[1] * self.K
        L.new(d.outputs["Value"], fade.inputs["Value"])
        tr = N.new("ShaderNodeBsdfTransparent")
        mix = N.new("ShaderNodeMixShader")
        L.new(fade.outputs["Result"], mix.inputs["Fac"])
        L.new(tr.outputs[0], mix.inputs[1])
        L.new(em.outputs[0], mix.inputs[2])
        out = N.new("ShaderNodeOutputMaterial")
        L.new(mix.outputs[0], out.inputs["Surface"])
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
        return m

    def ring(self, name, centre, px=7.0, width_px=1.4, colour=(1, 1, 1), strength=3.0, visible=None):
        """A ring `px` pixels in radius round `centre`, facing the camera, `width_px` thick: a
        marker for something too small to see at this scale (declare it as drawn)."""
        bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.5 * width_px / px, major_segments=48, minor_segments=8, location=(0, 0, 0))
        o = bpy.context.active_object
        o.name = name
        o.data.materials.append(look.emissive(name, colour, strength))
        o.visible_shadow = False
        o.parent = self.root
        o.rotation_mode = "QUATERNION"
        o.location = Vector(centre)
        self._marks.append({"where": tuple(centre), "px": 2 * px + width_px, "visible": visible, "glow": False})
        for i, (f, t) in enumerate(self.frames):
            fw, right, up = self.basis(i)
            r = px * self.per_px(i, o.location)
            v = 1.0 if visible is None else max(0.0, min(1.0, visible(t)))
            o.rotation_quaternion = Matrix((right, up, -fw)).transposed().to_quaternion()
            o.scale = (r * v + 1e-30,) * 3
            o.keyframe_insert("rotation_quaternion", frame=f)
            o.keyframe_insert("scale", frame=f)
        bake._linear(o)
        return o

    def plane(self, name, normal, radius, colour=(0.45, 0.56, 0.78), centre=(0.0, 0.0, 0.0), edge=0.24, near=45.0,
              base=0.03, grid=0.16, gain=1.4, width=0.02):
        """A faint sheet through `centre` with the given `normal` (true units), `radius` across, with a
        grid whose spacing follows the view: lines a tenth and a hundredth of the view's width, the
        finer fading out as the view widens, so it reads as a flat surface at every scale (the
        planets' plane). It fades over its outer `edge` (a fraction of the radius) and with distance
        from the camera (`near`, stage units: the view is about 10 across), so it never shimmers at
        the horizon. `base` and `grid` set the sheet's and the lines' opacity; `width` the lines'
        thickness as a fraction of their spacing. Draw it as declared: a drawn surface."""
        n = 256
        verts = [tuple(centre)] + [(centre[0] + radius * math.cos(2 * math.pi * k / n), centre[1] + radius * math.sin(2 * math.pi * k / n), centre[2])
                                   for k in range(n)]
        faces = [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)]
        me = bpy.data.meshes.new(name)
        me.from_pydata([(v[0] - centre[0], v[1] - centre[1], v[2] - centre[2]) for v in verts], [], faces)
        o = bpy.data.objects.new(name, me)
        self.scene.collection.objects.link(o)
        o.parent = self.root
        o.location = Vector(centre)
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = Vector(normal).to_track_quat("Z", "X")
        o.visible_shadow = False
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        for x in list(nt.nodes):
            nt.nodes.remove(x)
        N, L = nt.nodes, nt.links

        def op(kind, a, b=None, clamp=False):
            x = N.new("ShaderNodeMath")
            x.operation, x.use_clamp = kind, clamp
            for i, v in enumerate((a, b)):
                if v is None:
                    continue
                if isinstance(v, (int, float)):
                    x.inputs[i].default_value = v
                else:
                    L.new(v, x.inputs[i])
            return x.outputs[0]

        tc = N.new("ShaderNodeTexCoord")
        sep = N.new("ShaderNodeSeparateXYZ")
        L.new(tc.outputs["Object"], sep.inputs[0])
        lvl = N.new("ShaderNodeValue")
        lvl.name = "level"
        for (f, _t), fw in zip(self.frames, self.fields):
            lvl.outputs[0].default_value = math.log10(fw)
            lvl.outputs[0].keyframe_insert("default_value", frame=f)
        k = op("SUBTRACT", op("FLOOR", lvl.outputs[0]), 1.0)
        blend = op("SUBTRACT", lvl.outputs[0], op("FLOOR", lvl.outputs[0]))

        def lines(spacing):
            def axis(v):
                g = op("ABSOLUTE", op("SUBTRACT", op("FRACT", op("ADD", op("DIVIDE", v, spacing), 0.5)), 0.5))
                return op("SUBTRACT", 1.0, op("DIVIDE", g, width), clamp=True)
            return op("MAXIMUM", axis(sep.outputs["X"]), axis(sep.outputs["Y"]))

        fine = lines(op("POWER", 10.0, k))
        coarse = lines(op("POWER", 10.0, op("ADD", k, 1.0)))
        lit = op("ADD", op("MULTIPLY", fine, op("SUBTRACT", 1.0, blend)), coarse)
        r = N.new("ShaderNodeVectorMath")
        r.operation = "LENGTH"
        L.new(tc.outputs["Object"], r.inputs[0])
        rim = op("SUBTRACT", 1.0, op("DIVIDE", op("SUBTRACT", r.outputs["Value"], radius * (1 - edge)), radius * edge), clamp=True)
        d = N.new("ShaderNodeVectorMath")
        d.operation = "LENGTH"
        L.new(tc.outputs["Camera"], d.inputs[0])
        close = op("EXPONENT", op("DIVIDE", d.outputs["Value"], -near))
        alpha = op("MULTIPLY", op("MULTIPLY", rim, close), op("ADD", base, op("MULTIPLY", lit, grid)))
        em = N.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*colour, 1.0)
        L.new(op("MULTIPLY", alpha, gain), em.inputs["Strength"])
        tr = N.new("ShaderNodeBsdfTransparent")
        mix = N.new("ShaderNodeMixShader")
        L.new(op("MINIMUM", alpha, 1.0), mix.inputs["Fac"])
        L.new(tr.outputs[0], mix.inputs[1])
        L.new(em.outputs[0], mix.inputs[2])
        out = N.new("ShaderNodeOutputMaterial")
        L.new(mix.outputs[0], out.inputs["Surface"])
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
        o.data.materials.append(m)
        bake._linear(nt)
        return o

    def fade_out(self, t0, t1, stops=8.0):
        """Fade the whole picture to black between t0 and t1 (by exposure)."""
        vs = self.scene.view_settings
        base = vs.exposure
        for f, t in self.frames:
            u = 0.0 if t <= t0 else 1.0 if t >= t1 else (t - t0) / (t1 - t0)
            vs.exposure = base - stops * u * u
            vs.keyframe_insert("exposure", frame=f)

    def label(self, text, anchor, px=16.0, offset=(0.0, 0.0), colour=(0.92, 0.93, 0.95), strength=1.6, visible=None, font=None,
              align="CENTER", avoid=False, gap=26.0):
        """Text facing the camera, `px` pixels tall, offset (x, y) pixels from `anchor` (a point or
        a function of t). `visible(t)` 0..1 is its opacity: it fades at a constant size. Give it
        windows that open once and close once (text_flags checks). `avoid`: for each appearance,
        take the place round the anchor that is clearest of the lines, dots, rings and labels drawn
        so far, and hold it until the label leaves; `gap` is the room kept between the text and
        its anchor. Draw lines and marks before labels."""
        cu = bpy.data.curves.new("label." + text, "FONT")
        cu.body = text
        cu.align_x, cu.align_y = align, "CENTER"
        if font:
            cu.font = font
        o = bpy.data.objects.new("label." + text, cu)
        self.scene.collection.objects.link(o)
        mat = self._label_material("label." + text, colour, strength)
        o.data.materials.append(mat)
        o.visible_shadow = False
        o.parent = self.root
        o.rotation_mode = "QUATERNION"
        n = len(self.frames)
        vis = [1.0 if visible is None else max(0.0, min(1.0, visible(t))) for _, t in self.frames]
        offs = self._hold_place(text, anchor, px, offset, vis, align, gap) if avoid else [tuple(offset)] * n
        w_px = len(text) * 0.58 * px
        dx = {"LEFT": w_px / 2, "RIGHT": -w_px / 2}.get(align, 0.0)
        opacity = mat.node_tree.nodes["opacity"].outputs[0]
        rec = {"name": o.name, "text": text, "at": [], "anchor": [], "opacity": vis}
        for i, (f, t) in enumerate(self.frames):
            w = Vector(anchor(t) if callable(anchor) else anchor)
            fw, right, up = self.basis(i)
            u = self.per_px(i, w)
            o.location = w + right * offs[i][0] * u + up * offs[i][1] * u
            o.rotation_quaternion = Matrix((right, up, -fw)).transposed().to_quaternion()
            sz = px * u * 1.35  # a font's em is about 1.35 x its cap height
            o.scale = (sz, sz, sz)
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_quaternion", frame=f)
            o.keyframe_insert("scale", frame=f)
            opacity.default_value = vis[i]
            opacity.keyframe_insert("default_value", frame=f)
            a = self._to_px(i, w)
            rec["anchor"].append(a)
            rec["at"].append(None if a is None else (a[0] + offs[i][0] + dx, a[1] + offs[i][1]))
        bake._linear(o)
        bake._linear(mat.node_tree)
        self._labels.append(rec)
        if not avoid:  # register its box, so labels placed after it keep clear
            self._register(rec, w_px, 1.15 * px)
        return o

    def _label_material(self, name, colour, strength):
        """Emission mixed with transparency by a keyed value node named "opacity"."""
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        for x in list(nt.nodes):
            nt.nodes.remove(x)
        N, L = nt.nodes, nt.links
        em = N.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*colour, 1.0)
        em.inputs["Strength"].default_value = strength
        op = N.new("ShaderNodeValue")
        op.name = "opacity"
        op.outputs[0].default_value = 1.0
        tr = N.new("ShaderNodeBsdfTransparent")
        mix = N.new("ShaderNodeMixShader")
        L.new(op.outputs[0], mix.inputs["Fac"])
        L.new(tr.outputs[0], mix.inputs[1])
        L.new(em.outputs[0], mix.inputs[2])
        out = N.new("ShaderNodeOutputMaterial")
        L.new(mix.outputs[0], out.inputs["Surface"])
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
        return m

    def text_flags(self, rules=None):
        """Every label drawn, checked against Teja's text rule (cine/core/text.py)."""
        from ..core import text as TX

        return TX.flags(self._labels, self.m.fps, self.width, rules, t0=self.frames[0][1])

    def labels_json(self, path):
        """Save the labels as drawn (per-frame place and opacity), for the text check."""
        import json

        with open(path, "w", encoding="utf-8") as f:
            json.dump({"fps": self.m.fps, "width": self.width, "t0": self.frames[0][1], "labels": self._labels}, f, separators=(",", ":"))
        return path

    def _to_px(self, i, p):
        """A true-unit point to pixels from the frame's centre (x right, y up) in frame i, or None."""
        f, right, up = self.basis(i)
        d = Vector(p) - self.pos[i]
        z = d.dot(f)
        if z <= 1e-12 * max(1.0, d.length):
            return None
        k = self.width / 2 / math.tan(K.hfov(self.lens[i]) / 2) / z
        return d.dot(right) * k, d.dot(up) * k

    def _projected(self, i, cell=48.0, step=5.0):
        """The drawn part of every line, sampled every `step` pixels across the frame (and a margin)
        in frame i, bucketed into `cell`-pixel cells: {(cx, cy): [(x, y), ...]}."""
        if i in self._proj:
            return self._proj[i]
        t = self.frames[i][1]
        W, H = self.width / 2 + 200, self.width * 9 / 32 + 200
        cells = {}
        for ln in self._lines:
            pts, cum = ln["points"], ln["cum"]
            upto = cum[-1] if ln["reveal"] is None else max(0.0, min(1.0, ln["reveal"](t))) * cum[-1]
            org = Vector(ln["origin"](t)) if ln["origin"] else Vector((0, 0, 0))
            prev = None
            for j, p in enumerate(pts):
                if cum[j] > upto:
                    break
                q = self._to_px(i, Vector(p) + org)
                if q is not None and prev is not None:
                    (x0, y0), (x1, y1) = prev, q
                    if not ((x0 < -W and x1 < -W) or (x0 > W and x1 > W) or (y0 < -H and y1 < -H) or (y0 > H and y1 > H)):
                        n = max(1, min(600, int(math.hypot(x1 - x0, y1 - y0) / step)))
                        for k in range(n + 1):
                            x, y = x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n
                            if -W <= x <= W and -H <= y <= H:
                                cells.setdefault((int(x // cell), int(y // cell)), []).append((x, y))
                prev = q
        if len(self._proj) > 64:  # keep the cache small: frames are visited in order
            self._proj = {}
        self._proj[i] = cells
        return cells

    def _crossings(self, cells, x0, y0, x1, y1, cell=48.0):
        n = 0
        for cx in range(int(x0 // cell), int(x1 // cell) + 1):
            for cy in range(int(y0 // cell), int(y1 // cell) + 1):
                for x, y in cells.get((cx, cy), ()):
                    if x0 <= x <= x1 and y0 <= y <= y1:
                        n += 1
        return n

    def clutter(self, i, x0, y0, x1, y1):
        """What a box on screen (pixels from the frame's centre, y up) covers in frame i: line
        samples (every 5 px), plus 6 for each dot or ring."""
        t = self.frames[i][1]
        cost = self._crossings(self._projected(i), x0, y0, x1, y1)
        for mk in self._marks:
            if mk["visible"] is not None and mk["visible"](t) <= 0.0:
                continue
            q = self._to_px(i, mk["where"](t) if callable(mk["where"]) else mk["where"])
            if q is not None:
                r = (1.6 * mk["px"] if mk.get("glow", True) else mk["px"] / 2) + 4
                cost += 6 * (max(x0 - q[0], 0, q[0] - x1) ** 2 + max(y0 - q[1], 0, q[1] - y1) ** 2 < r * r)
        return cost

    def caption_place(self, candidates, every=3):
        """Where captions go (a date, a readout) so they hold one place for the whole scene: of the
        `candidates`, the one whose boxes cover the least of the lines, dots and rings while they
        show. `candidates`: {name: [(t0, t1, x0, y0, x1, y1)]}, each box in pixels from the frame's
        centre (y up) with the times it shows. Returns (best name, {name: cost})."""
        costs = {}
        for name, boxes in candidates.items():
            c = 0.0
            for t0, t1, x0, y0, x1, y1 in boxes:
                for i in range(0, len(self.frames), every):
                    if t0 <= self.frames[i][1] <= t1:
                        c += self.clutter(i, x0, y0, x1, y1)
            costs[name] = c
        return min(costs, key=costs.get), costs

    def _register(self, rec, w, h):
        for i, c in enumerate(rec["at"]):
            if c is not None and rec["opacity"][i] > 0.0:
                self._boxes.setdefault(i, []).append((c[0] - w / 2, c[1] - h / 2, c[0] + w / 2, c[1] + h / 2))

    def _hold_place(self, text, anchor, px, offset, vis, align, gap, every=2):
        """Per-frame offsets for a label that holds one place per appearance. For each run of
        frames where it shows, every candidate place round the anchor is scored over the whole run:
        each line sample (every 5 px) inside the text's box, plus 6 for each dot or ring and 12 for
        each label it would cover, averaged over the run plus half the worst frame, and a little
        for straying from its own offset. The best is held for the whole run: the text never moves
        beside its anchor while it's showing."""
        w, h, m = len(text) * 0.58 * px, 1.15 * px, 6.0
        dx = {"LEFT": w / 2, "RIGHT": -w / 2}.get(align, 0.0)  # the text's centre from its location
        places = [tuple(offset)]
        for s_ in (1.0, 1.9):
            gx, gy = w / 2 + gap * s_, h / 2 + gap * s_
            places += [(0, gy), (0, -gy), (gx, 0), (-gx, 0), (gx * 0.8, gy), (-gx * 0.8, gy), (gx * 0.8, -gy), (-gx * 0.8, -gy)]
        if align != "CENTER":
            places = [tuple(offset)] + [(x - dx, y) for x, y in places[1:]]
        n = len(self.frames)
        runs, start = [], None
        for i in range(n + 1):
            on = i < n and vis[i] > 0.0
            if on and start is None:
                start = i
            if not on and start is not None:
                runs.append((start, i - 1))
                start = None
        out = [tuple(offset)] * n
        for i0, i1 in runs:
            total, worst, wsum = [0.0] * len(places), [0.0] * len(places), 0.0
            for i in list(range(i0, i1 + 1, every)) + [i1]:
                t = self.frames[i][1]
                a = self._to_px(i, anchor(t) if callable(anchor) else anchor)
                if a is None:
                    continue
                cells = self._projected(i)
                marks = []
                for mk in self._marks:
                    if mk["visible"] is not None and mk["visible"](t) <= 0.0:
                        continue
                    q = self._to_px(i, mk["where"](t) if callable(mk["where"]) else mk["where"])
                    if q is not None:
                        # a dot with its glow (bloom reaches well past it); a ring at its drawn size
                        marks.append((q[0], q[1], (1.6 * mk["px"] if mk.get("glow", True) else mk["px"] / 2) + 4))
                boxes = self._boxes.get(i, [])
                wt = max(vis[i], 0.05)
                wsum += wt
                for k, (ox, oy) in enumerate(places):
                    cx, cy = a[0] + ox + dx, a[1] + oy
                    x0, y0, x1, y1 = cx - w / 2 - m, cy - h / 2 - m, cx + w / 2 + m, cy + h / 2 + m
                    cost = self._crossings(cells, x0, y0, x1, y1)
                    cost += 6 * sum(1 for (mx, my, r) in marks
                                    if max(x0 - mx, 0, mx - x1) ** 2 + max(y0 - my, 0, my - y1) ** 2 < r * r)
                    cost += 12 * sum(1 for (bx0, by0, bx1, by1) in boxes if x0 - 10 < bx1 and bx0 < x1 + 10 and y0 - 10 < by1 and by0 < y1 + 10)
                    total[k] += cost * wt
                    worst[k] = max(worst[k], cost)
            if wsum == 0.0:
                continue
            score = [total[k] / wsum + 0.5 * worst[k] + 0.015 * math.hypot(ox - places[0][0], oy - places[0][1])
                     for k, (ox, oy) in enumerate(places)]
            best = places[min(range(len(places)), key=score.__getitem__)]
            for i in range(i0, i1 + 1):
                out[i] = best
            for i in range(i0, i1 + 1):  # register where it went, for the labels placed after it
                t = self.frames[i][1]
                a = self._to_px(i, anchor(t) if callable(anchor) else anchor)
                if a is not None:
                    cx, cy = a[0] + best[0] + dx, a[1] + best[1]
                    self._boxes.setdefault(i, []).append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
        return out

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
