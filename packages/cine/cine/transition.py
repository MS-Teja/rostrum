"""Transitions between scenes (crew/director.md), and the joining of rendered scenes into one film.

    from cine import transition as T
    T.join([("a.mp4", None), ("b.mp4", T.light(0.8, centre=(0.3, 0.5)))], "reel.mp4")
    T.mux("frames/f_%04d.png", 30, 1, "take.wav", "scene.mp4", offset=1.2)   # frames + voice, handle in
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

**The voice is never under a transition.** A transition overlaps the end of one scene with the
start of the next, so each scene keeps handles: silent picture before its first word and after its
last, at least as long as the transition on that side (`Voice.load(..., offset=handle_in)` and
`T1 = voice end + handle_out`; `mux` places the take at the offset). `join` lays each scene's audio
at its own start time, never crossfades it, and refuses to join when the overlap isn't silent on
both sides. Needs ffmpeg.
"""

import json
import math
import os
import re
import subprocess

SILENT_DB = -45.0  # an overlap's mean level must stay under this on both sides


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


def level_db(path, start, dur):
    """The mean audio level (dB) of `path` from `start` for `dur` seconds; -inf for digital silence."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{max(0.0, start):.3f}", "-t", f"{dur:.3f}", "-i", path,
                          "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+|-inf) dB", out.stderr)
    return float(m.group(1)) if m else float("-inf")


def check_handles(clips):
    """Every transition's overlap must be silent on both sides: the last d seconds of the clip
    before and the first d seconds of the clip after. Returns the problems, [] when clean."""
    problems = []
    for i in range(1, len(clips)):
        tr = clips[i][1] or cut()
        if tr.duration <= 0:
            continue
        a, b = clips[i - 1][0], clips[i][0]
        tail = level_db(a, _duration(a) - tr.duration, tr.duration)
        head = level_db(b, 0.0, tr.duration)
        for side, name, db in (("last", a, tail), ("first", b, head)):
            if db > SILENT_DB:
                problems.append(f"voice inside the {tr.kind} into {os.path.basename(b)}: {db:.0f} dB in the {side} "
                                f"{tr.duration:.2f} s of {os.path.basename(name)} (give it a handle at least that long)")
    return problems


def mux(frames, fps, start, take, out, offset=0.0, crf=18):
    """A scene's frames (an ffmpeg image pattern, numbered from `start`) and its voice take, the take
    placed `offset` seconds in (the scene's in-handle), into one mp4 as long as the picture."""
    ms = int(round(offset * 1000))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(fps), "-start_number", str(start), "-i", frames, "-i", take,
                    "-filter_complex", f"[1:a]adelay=delays={ms}:all=1,apad[a]", "-map", "0:v", "-map", "[a]", "-shortest",
                    "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out], check=True)
    return out


def join(clips, out, fps=30, crf=18, force=False):
    """clips: [(path, transition into this clip or None for the first)]. Writes `out`: the pictures
    overlap by each transition, and each clip's audio is laid at its own start time and summed,
    never crossfaded. Refuses (ValueError) if any overlap holds voice, unless `force`."""
    problems = check_handles(clips)
    if problems and not force:
        raise ValueError("; ".join(problems))
    paths = [c[0] for c in clips]
    durs = [_duration(p) for p in paths]
    inputs = []
    for p in paths:
        inputs += ["-i", p]
    v_prev = "[0:v]"
    graph = []
    starts, t_end = [0.0], durs[0]
    for i in range(1, len(paths)):
        tr = clips[i][1] or cut()
        offset = t_end - tr.duration
        vlab = f"[v{i}]"
        vf = tr.video(offset)
        graph.append(f"{v_prev}[{i}:v]{vf}{vlab}" if vf else f"{v_prev}[{i}:v]concat=n=2:v=1:a=0{vlab}")
        v_prev = vlab
        starts.append(offset)
        t_end = offset + durs[i]
    for i, s in enumerate(starts):
        graph.append(f"[{i}:a]adelay=delays={int(round(s * 1000))}:all=1[d{i}]")
    graph.append("".join(f"[d{i}]" for i in range(len(paths))) + f"amix=inputs={len(paths)}:normalize=0:dropout_transition=0[aout]")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", v_prev, "-map", "[aout]",
           "-t", f"{t_end:.3f}", "-r", str(fps), "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out]
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
