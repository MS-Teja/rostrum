"""Render a Rostrum scene with Blender, and write where its anchors land on screen.

    blender -b --factory-startup -P packages/stage3d/render.py -- \\
        --scene examples/kafka-fast/scene.py --look keynote --shot 3 \\
        --engine cycles --samples 128 --pct 50 --still 1 --out renders/stills/keynote-3.png

A scene file defines build(scene, opts). It builds the set for opts["shot"] in the
opts["look"] style and animates it as a function of the frame. Render settings are
applied before build, so a scene can adjust them.
"""

import argparse
import importlib.util
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from rostrum_stage import anchors, look, timing  # noqa: E402


def parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="render.py")
    p.add_argument("--scene", required=True)
    p.add_argument("--look", default="keynote")
    p.add_argument("--shot")
    p.add_argument("--engine", choices=["eevee", "cycles"], default="eevee")
    p.add_argument("--samples", type=int)
    p.add_argument("--res", default="1920x1080")
    p.add_argument("--pct", type=int, default=100)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--still", type=int, help="render this frame to --out, a .png path")
    p.add_argument("--frames", help="a-b: render this range into --out, a directory")
    p.add_argument("--out", required=True)
    p.add_argument("--timing", help="timing.js or timing.json from `rostrum voice`")
    p.add_argument("--save", help="also save the built scene as a .blend, for inspection")
    p.add_argument("--hide", help="comma-separated object-name prefixes to leave out, for look development")
    a = p.parse_args(argv)
    if (a.still is None) == (a.frames is None):
        p.error("give exactly one of --still or --frames")
    return a


def main():
    a = parse()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    w, h = (int(x) for x in a.res.split("x"))
    look.render(scene, a.engine, a.samples, (w, h), a.pct, a.fps)

    spec = importlib.util.spec_from_file_location("rostrum_scene", os.path.abspath(a.scene))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    opts = {
        "look": a.look,
        "shot": a.shot,
        "engine": a.engine,
        "fps": a.fps,
        "timing": timing.load(a.timing) if a.timing else None,
        # The frames this run renders, so a long scene can bake only what it needs.
        "frames": (a.still, a.still) if a.still is not None else tuple(int(x) for x in a.frames.split("-")),
    }
    t0 = time.time()
    mod.build(scene, opts)
    print(f"rostrum: built in {time.time() - t0:.1f}s")
    for prefix in filter(None, (a.hide or "").split(",")):
        for o in scene.objects:
            if o.name.startswith(prefix):
                o.hide_render = True
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save))

    size = [round(w * a.pct / 100), round(h * a.pct / 100)]
    out = os.path.abspath(a.out)
    scene.render.image_settings.file_format = "PNG"
    if a.still is not None:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        scene.frame_set(a.still)
        anchors.write(os.path.splitext(out)[0] + ".anchors.json", {str(a.still): anchors.project(scene)}, a.fps, size)
        scene.render.filepath = out
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"rostrum: frame {a.still} in {time.time() - t0:.1f}s -> {out}")
    else:
        start, end = (int(x) for x in a.frames.split("-"))
        os.makedirs(out, exist_ok=True)
        frames = {}
        for f in range(start, end + 1):
            scene.frame_set(f)
            frames[str(f)] = anchors.project(scene)
        anchors.write(os.path.join(out, "anchors.json"), frames, a.fps, size)
        scene.frame_start, scene.frame_end = start, end
        scene.render.filepath = os.path.join(out, "f_")
        t0 = time.time()
        bpy.ops.render.render(animation=True)
        n = end - start + 1
        took = time.time() - t0
        print(f"rostrum: {n} frames in {took:.1f}s ({took / n:.2f}s per frame) -> {out}")


main()
