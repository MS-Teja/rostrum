"""TEMPLATE: copy beside your scene's notes (crew/build.md, gate 1), rename, and fill every TODO.
GPL-3.0-or-later.

Scene <name>: <one line on what it shows>, cut to <the line of narration it carries>:

    "<the narration, verbatim>"

    python3 scene.py                                        # motion file only (gates 1, 5)
    blender -b --factory-startup -P scene.py -- --proof     # the hero alone, lit (gate 3)
    blender -b --factory-startup -P scene.py -- --dailies   # key stills + every check (gates 4, 6, 7)
    blender -b --factory-startup -P scene.py -- --render    # the preview, with the voice (gate 8)
"""

import math  # noqa: F401  (most scenes need it)
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CINE = os.environ.get("CINE", os.path.join(HERE, "..", ".."))  # TODO: the path to rostrum/packages/cine
sys.path[:0] = [CINE]

from cine.camera import rig as R  # noqa: E402
from cine.camera import shot as SHOT  # noqa: E402, F401
from cine.core import shape as SH  # noqa: E402
from cine.core.curve import Curve, Motion  # noqa: E402
from cine.core.voice import Voice  # noqa: E402

NAME = "TODO-scene-name"
OUT = os.path.join(HERE, "out", NAME)
TAKE, WORDS = os.path.join(HERE, "TODO.take.wav"), os.path.join(HERE, "TODO.words.json")
PROFILE = "explainer"
FPS, T0 = 30, 0.0
# handles: silent picture before the first word and after the last, each at least the transition on
# that side plus 0.25 s (director §4). The voice is never under a transition.
HANDLE_IN, HANDLE_OUT = 0.8, 0.8  # TODO: from the transitions in and out
V = Voice.load(WORDS, audio=TAKE, offset=HANDLE_IN)
T1 = round((V.end + max(0.7, HANDLE_OUT)) * FPS) / FPS
W = {"first": V.at("TODO")}  # the words the picture rides: key by these, never by raw seconds

SUBJECTS = {"hero": (0.0, 0.0, 0.0)}  # TODO: aim points by name
SHAPES = {"hero": {"points": SH.box([-1, -1, -1], [1, 1, 1]), "role": "subject"}}  # TODO: real extents
HERO = ("hero",)  # TODO: name prefixes of the hero object's parts (the --proof render shows only these)

BRIEF = f"""scene      {NAME}
purpose    TODO: what this scene does in the video, in one sentence
remember   TODO: the one thing the viewer must take away
last image TODO: the "remember" as a picture: what's in frame, the subject's size, what moves, held >= 2 s (the longest hold)
journey    TODO: the camera's path in one sentence
feeling    TODO
beats      TODO: time range (by words), the words, what happens, the one dominant motion, the beat's subject
seen at word
  word        what must be visible        size      lit by
  TODO
in         TODO: the transition in
out        TODO: the transition out
handles    in {HANDLE_IN:.2f} s, out {HANDLE_OUT:.2f} s
light      TODO: every source, motivated and declared; the planned look (normal, low-key, silhouette, diagram)
cheats     TODO: every cheat, uniform and declared
references TODO: for each hero object, its real references and its 3-5 readable features at its closest shot
"""


def journey():
    rig = R.Rig(SUBJECTS, fps=FPS)
    # TODO: keys by words (crew/cinematographer.md §9), e.g.
    rig.place(0.0, "hero", at=(0.0, -6.0, 1.0), lens=35, label="TODO", intent={"subject": "hero", "motive": "establish", "look": "normal"})
    rig.place(T1, "hero", at=(0.0, -5.0, 1.0), label="TODO", intent={"subject": "hero", "motive": "creep", "look": "normal"})
    return rig


def plan():
    rig = journey()
    cam = rig.sample(T0, T1)
    times = cam["t"]
    m = Motion(NAME, T0, T1, FPS)
    for k in ("pos", "aim", "lens"):
        m.channels["cam." + k] = Curve(samples=cam[k], fps=FPS, t0=T0)
    m.channels.update(cam["channels"])
    m.words = V.lane()
    m.channels["voice.pace"] = Curve(samples=V.pace(times), fps=FPS, t0=T0)
    m.channels["voice.speaking"] = Curve(samples=[1.0 if V.speaking(t) else 0.0 for t in times], fps=FPS, t0=T0)
    m.spans = cam["spans"]
    m.shapes = {k: dict(v) for k, v in SHAPES.items()}
    m.brief = BRIEF
    m.shots = cam.get("shots", [])
    os.makedirs(OUT, exist_ok=True)
    m.save(os.path.join(OUT, NAME + ".motion.json"))
    return m


def build(m):
    """The set, the light and the actors (gates 3, 4, 6)."""
    global bpy
    import bpy

    from cine.blender import bake, look

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    look.preview(scene, res=(960, 540), samples=16, blur=True)
    look.glow(scene, threshold=1.0, strength=0.4)
    # TODO: the hero (named with a HERO prefix), the set, the lights, the actors
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    bpy.context.active_object.name = "hero"
    cam = bake.camera(scene, m)
    return scene, cam


def render(scene):
    import bpy

    from cine import transition as T

    d = os.path.join(OUT, "frames")
    os.makedirs(d, exist_ok=True)
    scene.render.filepath = os.path.join(d, "f_")
    bpy.ops.render.render(animation=True)
    return T.mux(os.path.join(d, "f_%04d.png"), FPS, scene.frame_start, TAKE, os.path.join(OUT, NAME + ".mp4"), offset=HANDLE_IN)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    m = plan()
    print("planned", m.name, f"{T1:.2f} s")
    if "--proof" in argv or "--dailies" in argv:
        from cine import dailies as D
        from cine.blender import dailies as BD

        scene, cam = build(m)
        hero = [o for o in bpy.data.objects if o.name.startswith(HERO)]
        others = [o for o in bpy.data.objects if o.type in ("MESH", "CURVE") and o not in hero]
        if "--proof" in argv:  # gate 3: the hero alone under its light, at the shots where it's closest and widest
            for o in others:
                o.hide_render = True
            sizes = sorted(m.shots, key=lambda s: s["t"])  # TODO: pick the closest and widest shots of the hero
            shots = BD.render(scene, m, [s["t"] for s in sizes], os.path.join(OUT, "proof"), subject=hero)
            for s in shots:
                print(f"{s['t']:6.2f}s  {s.get('look_flags') or 'no look flags'}")
        else:
            out = os.path.join(OUT, "dailies")
            shots = BD.render(scene, m, D.times_for(m), out, subject=hero, other=others)
            D.pack(m, shots, out, profile=os.path.join(CINE, "profiles", PROFILE + ".json"), motion_path=os.path.join(OUT, NAME + ".motion.json"))
            print("dailies ->", out)
    if "--render" in argv:
        scene, cam = build(m)
        print(render(scene))
