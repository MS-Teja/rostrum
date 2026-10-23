"""Narration timing to frame numbers. No bpy here: it runs anywhere."""

import json
import math


def load(path):
    """Read the timing the director's `voice` command writes (timing.js or timing.json)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if path.endswith(".js"):
        text = text[text.index("=") + 1 :].strip().rstrip(";")
    return json.loads(text)


def frame(seconds, fps=30, start=1):
    """The frame showing time `seconds`. Rounds half up, so a cue lands within half a frame."""
    return start + math.floor(seconds * fps + 0.5)


def cue_time(timing, key, lead=0.0):
    """Seconds into the video at which cue `key` (e.g. "b3:sendfile") is spoken."""
    for cue in timing["cues"]:
        if cue["key"] == key:
            return cue["time"] + lead
    known = ", ".join(c["key"] for c in timing["cues"])
    raise KeyError(f"no cue {key!r}; known cues: {known}")


def beat_span(timing, beat_id, lead=0.0):
    """(start, end) in seconds of the narration for one beat."""
    for beat in timing["beats"]:
        if beat["id"] == beat_id:
            return beat["start"] + lead, beat["end"] + lead
    raise KeyError(f"no beat {beat_id!r}")
