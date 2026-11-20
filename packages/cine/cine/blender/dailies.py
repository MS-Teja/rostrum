"""Dailies inside Blender: render a scene's key poses as stills, with a mask per still that
separates the subject from everything else, and measure what the look role checks
(crew/look.md): exposure, contrast, clipping, crush, flatness, judged by each shot's
planned look (core/look.py). Also ray-tests whether
anything blocks the camera's view of the subject. GPL-3.0-or-later.

    from cine.blender import dailies
    looks = dailies.render(scene, motion, times, out_dir, subject=[voyager parts],
                           other=[earth, beam, plumes], hide=[stars])

Masks are flat Workbench renders: subject red, other objects green, background black.
Measures use display values (the PNG after AgX), luminance by Rec. 709 weights.
"""

import os

import bpy
import numpy as np
from mathutils import Vector

from ..core import compose as C
from ..core import look as LK
from ..core import shape as S


def frame_of(motion, t):
    return int(round((t - motion.t0) * motion.fps)) + 1


def _pixels(path):
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = "Non-Color"
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(img.size[1], img.size[0], 4)[::-1]  # rows top-down
    bpy.data.images.remove(img)
    return a


def measure_look(still, mask):
    """Look measures of one still, inside the subject mask (red) against the background."""
    px, mk = _pixels(still), _pixels(mask)
    L = 0.2126 * px[..., 0] + 0.7152 * px[..., 1] + 0.0722 * px[..., 2]
    subj = (mk[..., 0] > 0.5) & (mk[..., 1] < 0.5)
    other = mk[..., 1] > 0.5
    bg = ~subj & ~other
    out = {"subject_cover": float(subj.mean()), "other_cover": float(other.mean())}
    if subj.sum() < 50:
        out["subject_visible"] = False
        return out
    s = L[subj]
    b = L[bg] if bg.sum() > 50 else np.array([0.0])
    med, bmed = float(np.median(s)), float(np.median(b))
    out.update({
        "subject_visible": True, "median": med, "p10": float(np.percentile(s, 10)), "p90": float(np.percentile(s, 90)),
        "spread": float(np.percentile(s, 90) - np.percentile(s, 10)), "clipped": float((s >= 0.98).mean()),
        "crushed": float((s <= 0.02).mean()), "background": bmed, "contrast": med / max(bmed, 0.02),
    })
    return out


def occlusion(scene, motion, t, subject, ignore=()):
    """Fraction of the subject's shape points that something outside the subject blocks from the
    camera (a boom across the lens, a part in front of the part we're looking at)."""
    sh = motion.shapes.get(subject)
    if not sh:
        return None
    pts = S.world(sh, motion, t)
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    pad = [0.1 * (hi[k] - lo[k]) + 0.02 for k in range(3)]
    cam = list(motion.channels[motion.camera["pos"]](t))
    dg = bpy.context.evaluated_depsgraph_get()
    blocked = 0
    for p in pts:
        o, d = Vector(cam), Vector(p) - Vector(cam)
        dist = d.length
        d.normalize()
        travelled = 0.0
        for _ in range(6):
            hit, loc, _n, _i, obj, _m = scene.ray_cast(dg, o, d, distance=dist - travelled - 0.02)
            if not hit:
                break
            if obj and any(obj.name.startswith(x) for x in ignore):
                step = (loc - o).length + 1e-3
                o, travelled = loc + d * 1e-3, travelled + step
                continue
            if not all(lo[k] - pad[k] <= loc[k] <= hi[k] + pad[k] for k in range(3)):
                blocked += 1
            break
    return blocked / max(1, len(pts))


def render(scene, motion, times, out_dir, subject, other=(), hide=(), res=(640, 360), samples=8, ignore=()):
    """Render stills and masks at `times`; return [{t, frame, still, mask, look, flags, occluded}]."""
    os.makedirs(os.path.join(out_dir, "stills"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "masks"), exist_ok=True)
    r = scene.render
    keep = {"x": r.resolution_x, "y": r.resolution_y, "samples": scene.eevee.taa_render_samples, "path": r.filepath}
    r.resolution_x, r.resolution_y = res
    scene.eevee.taa_render_samples = samples
    shots = []
    for t in times:
        f = frame_of(motion, t)
        scene.frame_set(f)
        path = os.path.join(out_dir, "stills", f"t_{t:06.2f}.png")
        r.filepath = path
        bpy.ops.render.render(write_still=True)
        subj = C.beat_subject(motion, t)
        shots.append({"t": round(t, 3), "frame": f, "still": path, "subject": subj,
                      "occluded": occlusion(scene, motion, t, subj, ignore=ignore) if subj else None})
    # masks: flat colours, no blur, no bloom, no stars
    state = {"engine": r.engine, "blur": r.use_motion_blur, "comp": r.use_compositing, "view": scene.view_settings.view_transform,
             "look": scene.view_settings.look, "world": tuple(scene.world.color) if scene.world else None}
    colours = {o.name: tuple(o.color) for o in bpy.data.objects}
    hidden = {o.name: o.hide_render for o in bpy.data.objects}
    r.engine = "BLENDER_WORKBENCH"
    r.use_motion_blur = False
    r.use_compositing = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    sh = scene.display.shading
    sh.light, sh.color_type = "FLAT", "OBJECT"
    scene.display.render_aa = "OFF"
    if scene.world:
        scene.world.color = (0, 0, 0)
    subject_names = {o.name for o in subject}
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVE", "FONT", "SURFACE", "META"):
            o.color = (1, 0, 0, 1) if o.name in subject_names else (0, 1, 0, 1)
    for o in hide:
        o.hide_render = True
    for s in shots:
        scene.frame_set(s["frame"])
        s["mask"] = os.path.join(out_dir, "masks", f"t_{s['t']:06.2f}.png")
        r.filepath = s["mask"]
        bpy.ops.render.render(write_still=True)
    # restore
    r.engine, r.use_motion_blur, r.use_compositing = state["engine"], state["blur"], state["comp"]
    scene.view_settings.view_transform, scene.view_settings.look = state["view"], state["look"]
    if state["world"] is not None:
        scene.world.color = state["world"]
    for o in bpy.data.objects:
        if o.name in colours:
            o.color = colours[o.name]
        if o.name in hidden:
            o.hide_render = hidden[o.name]
    r.resolution_x, r.resolution_y, scene.eevee.taa_render_samples, r.filepath = keep["x"], keep["y"], keep["samples"], keep["path"]
    for s in shots:
        s["look"] = measure_look(s["still"], s["mask"])
        s["planned_look"] = LK.planned(motion.shots, s["subject"], s["t"])
        if all(p_.get("look") == "diagram" for p_ in (motion.shots or [])) and motion.shots:
            s["planned_look"] = "diagram"
        s["look_flags"] = LK.flags(s["look"], s["planned_look"])
        transit = any(sp.get("rule") in ("push-through", "zoom-through") and sp["t0"] <= s["t"] <= sp["t1"] for sp in (motion.spans or []))
        if s["occluded"] is not None and s["occluded"] > 0.15 and not transit:  # passing through something hides things by design
            s["look_flags"].append(("occluded", f"{s['occluded']:.0%} of {s['subject']} blocked by something in front"))
    return shots
