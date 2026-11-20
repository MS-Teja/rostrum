"""Transitions between scenes (crew/director.md), and the joining of rendered scenes into one film.

    from cine import transition as T
    T.join([("a.mp4", None), ("b.mp4", T.light(0.8, travel="left", centre_y=0.0))], "reel.mp4")
    T.match(motion_a, t_a, "voyager", motion_b, t_b, "voyager")   # a match cut's alignment

Within a scene the camera never cuts. Between scenes, each boundary has a designed transition:
  cut        only when the director says so
  dissolve   a matched dissolve (0.5 s by default): time passes at the same place
  light      a bloom of light from a point (where the light is: a signal, the Sun), the next scene
             opening outward from it behind a soft bright rim; best where the next scene's subject
             appears at that same point
  whip       a fast directional slide with motion blur, matched in direction on both sides
A zoom-through or push-through is one continuous camera move across both scenes, so it's
planned in the scenes themselves (a key with motive "zoom-through"), not composited here.
The audio crossfades under every transition. Needs ffmpeg.
"""

import json
import math
import os
import subprocess


class Transition:
    def __init__(self, kind, duration, **params):
        self.kind, self.duration, self.params = kind, float(duration), params

    def video(self, offset):
        d, p = self.duration, self.params
        if self.kind == "dissolve":
            return f"xfade=transition=fade:duration={d:.3f}:offset={offset:.3f}"
        if self.kind == "whip":
            direction = {"left": "slideleft", "right": "slideright", "up": "slideup", "down": "slidedown"}[p.get("travel", "left")]
            return f"xfade=transition={direction}:duration={d:.3f}:offset={offset:.3f}"
        if self.kind == "light":
            # A bloom of light from a screen point (cx, cy in 0..1, y down): the frame brightens round
            # it, and the next scene opens outward from it behind a soft bright rim. q = 1 - P.
            cx, cy = p.get("centre", (0.5, 0.5))
            soft, width, glow, veil = p.get("soft", 0.10), p.get("width", 0.07), p.get("glow", 110), p.get("veil", 22)
            r = f"hypot((X/W-{cx})*1.778,(Y/H-{cy}))"  # distance in frame heights
            R = "(2.2*pow(1-P,1.5))"                  # the opening radius grows fast, then eases
            s_ = f"clip(0.5+({R}-{r})/{soft},0,1)"
            g = f"({glow}*exp(-pow(({r}-{R})/{width},2))+{veil}*exp(-pow({r}/0.9,2)))*sin(PI*(1-P))"
            expr = f"if(eq(PLANE,0),clip(A*(1-{s_})+B*{s_}+{g},0,255),A*(1-{s_})+B*{s_})"
            return f"xfade=transition=custom:duration={d:.3f}:offset={offset:.3f}:expr='{expr}'"
        if self.kind == "cut":
            return None
        raise ValueError(f"unknown transition {self.kind!r}")


def cut():
    return Transition("cut", 0.0)


def dissolve(duration=0.5):
    return Transition("dissolve", duration)


def light(duration=0.8, centre=(0.5, 0.5), **kw):
    """A bloom of light from `centre` (x, y in 0..1 of the frame, y down): put it where the light
    is (a signal, the Sun) and, ideally, where the next scene's subject appears."""
    return Transition("light", duration, centre=centre, **kw)


def whip(duration=0.35, travel="left"):
    return Transition("whip", duration, travel=travel)


def _duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path], capture_output=True, text=True, check=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def join(clips, out, fps=30, crf=18):
    """clips: [(path, transition into this clip or None for the first)]. Writes `out` with the
    video and audio of every clip, overlapping by each transition's duration."""
    paths = [c[0] for c in clips]
    durs = [_duration(p) for p in paths]
    inputs = []
    for p in paths:
        inputs += ["-i", p]
    v_prev, a_prev = "[0:v]", "[0:a]"
    graph = []
    t_end = durs[0]
    for i in range(1, len(paths)):
        tr = clips[i][1] or cut()
        d = tr.duration
        offset = t_end - d
        vlab, alab = f"[v{i}]", f"[a{i}]"
        vf = tr.video(offset)
        if vf:
            graph.append(f"{v_prev}[{i}:v]{vf}{vlab}")
            graph.append(f"{a_prev}[{i}:a]acrossfade=d={max(0.05, d):.3f}:c1=tri:c2=tri{alab}")
        else:
            graph.append(f"{v_prev}[{i}:v]concat=n=2:v=1:a=0{vlab}")
            graph.append(f"{a_prev}[{i}:a]concat=n=2:v=0:a=1{alab}")
        v_prev, a_prev = vlab, alab
        t_end = offset + durs[i]
    cmd = ["ffmpeg", "-loglevel", "error", "-y", *inputs]
    if graph:
        cmd += ["-filter_complex", ";".join(graph), "-map", v_prev, "-map", a_prev]
    cmd += ["-r", str(fps), "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out]
    subprocess.run(cmd, check=True)
    return out, t_end


def match(motion_a, t_a, subject_a, motion_b, t_b, subject_b, tol=0.05):
    """How well a shared subject lines up across a match cut: its screen centre and size at the
    end of A and the start of B (crew/director.md: within 5% of the frame). Returns (ok, report)."""
    from .core import compose as C
    from .core import shape as S

    def at(m, t, s):
        ch, cam = m.channels, m.camera
        return C.measure_points(S.world(m.shapes[s], m, t), list(ch[cam["pos"]](t)), list(ch[cam["aim"]](t)), float(ch[cam["lens"]](t)))

    a, b = at(motion_a, t_a, subject_a), at(motion_b, t_b, subject_b)
    if not (a.get("visible") and b.get("visible")):
        return False, {"a": a.get("visible"), "b": b.get("visible")}
    dx, dy = b["cx"] - a["cx"], b["cy"] - a["cy"]
    ds = abs(math.log(max(1e-9, b["size"]) / max(1e-9, a["size"])))
    ok = abs(dx) <= tol and abs(dy) <= tol and ds <= math.log(1 + tol * 4)
    return ok, {"dx": round(dx, 3), "dy": round(dy, 3), "size_a": round(a["size"], 3), "size_b": round(b["size"], 3)}
