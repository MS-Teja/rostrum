"""The voiceover drives the picture: where the words fall, and how fast the voice is going.

    v = Voice.load("b15.words.json", audio="b15.take.wav")
    v.at("fire")                  # when "fire" starts (s); v.at("again", n=2), v.at("tiny drift")
    v.at("Earth", edge="end")     # when it ends
    pace = v.pace(times)          # per frame: ~0.6 (slow, quiet, pausing) .. ~1.5 (fast, loud)
    motion.words = v.lane()       # the words on the sheet's timeline

**Pace** sets how fast the camera may move at each moment. The motion flags scale their speed
limits by it (qa.flags(scale=...)), so the camera can be brisk under a fast, excited line and
must be calm under a slow, quiet one. It combines:
  rate     words per second over a 3 s window, against the take's own median
  energy   loudness (RMS) over a 1 s window, against the take's median, when the audio is given
  pauses   between phrases the pace eases towards 1: the picture may speak, at the base pace
pace = rate^0.6 x energy^0.4, smoothed over half a second and kept to 0.6-1.5. No dependencies.
"""

import array
import json
import math
import re
import wave


def _norm(w):
    return re.sub(r"[^\w']", "", w.lower())


class Voice:
    def __init__(self, words, rms=None, offset=0.0):
        """words: [{"text", "start", "end"}] (s, in the take); rms: [(t, level)] or None; offset:
        where the take starts in the scene (s)."""
        self.words = [{"text": w["text"], "start": w["start"] + offset, "end": w["end"] + offset} for w in words]
        self.rms = [(t + offset, v) for t, v in rms] if rms else None
        self.offset = offset

    @classmethod
    def load(cls, words_path, audio=None, offset=0.0):
        with open(words_path) as f:
            words = json.load(f)
        return cls(words, rms(audio) if audio else None, offset)

    # ── when ────────────────────────────────────────────────────────────────────────────
    def at(self, phrase, n=1, edge="start"):
        """When the n-th occurrence of `phrase` (one or more words) starts, or ends."""
        want = [_norm(p) for p in phrase.split()]
        found = 0
        for i in range(len(self.words) - len(want) + 1):
            if all(_norm(self.words[i + j]["text"]) == want[j] for j in range(len(want))):
                found += 1
                if found == n:
                    return self.words[i + len(want) - 1]["end"] if edge == "end" else self.words[i]["start"]
        raise KeyError(f"{phrase!r} (occurrence {n}) isn't in the voiceover")

    @property
    def end(self):
        return self.words[-1]["end"] if self.words else self.offset

    def speaking(self, t, pad=0.35):
        return any(w["start"] - pad <= t <= w["end"] + pad for w in self.words)

    def lane(self):
        return [[round(w["start"], 3), w["text"]] for w in self.words]

    # ── how fast ────────────────────────────────────────────────────────────────────────
    def pace(self, times, window=3.0, lo=0.6, hi=1.5):
        mids = [(w["start"] + w["end"]) / 2 for w in self.words]
        if not mids:
            return [1.0] * len(times)

        def rate(t):
            return sum(1 for m in mids if abs(m - t) <= window / 2) / window

        spoken = [rate(m) for m in mids]
        med_rate = sorted(spoken)[len(spoken) // 2] or 1.0
        med_rms = None
        if self.rms:
            lv = sorted(v for t, v in self.rms if self.speaking(t))
            med_rms = lv[len(lv) // 2] if lv else None
        raw = []
        for t in times:
            if self.speaking(t):
                r = max(0.2, rate(t) / med_rate) ** 0.6
                if med_rms:
                    e = [v for tt, v in self.rms if abs(tt - t) <= 0.5]
                    r *= max(0.2, (sum(e) / len(e)) / med_rms) ** 0.4 if e else 1.0
            else:
                r = 1.0  # a pause, or before and after the voice: the base pace
            raw.append(min(hi, max(lo, r)))
        return _smooth(raw, times, 0.5)


def rms(path, step=0.02):
    """[(t, RMS level)] of a 16-bit PCM WAV every `step` seconds (mono, or the first channel)."""
    with wave.open(path) as w:
        n, ch, sr, width = w.getnframes(), w.getnchannels(), w.getframerate(), w.getsampwidth()
        if width != 2:
            raise ValueError("rms() reads 16-bit PCM WAV")
        a = array.array("h", w.readframes(n))
    if ch > 1:
        a = a[::ch]
    hop = max(1, int(sr * step))
    out = []
    for i in range(0, len(a) - hop, hop):
        seg = a[i:i + hop]
        out.append(((i + hop / 2) / sr, math.sqrt(sum(x * x for x in seg) / len(seg)) / 32768.0))
    return out


def _smooth(vals, times, sigma):
    if len(times) < 2:
        return vals
    dt = (times[-1] - times[0]) / (len(times) - 1)
    r = max(1, int(3 * sigma / dt))
    k = [math.exp(-0.5 * (j * dt / sigma) ** 2) for j in range(-r, r + 1)]
    out = []
    for i in range(len(vals)):
        acc = wsum = 0.0
        for j, kw in zip(range(i - r, i + r + 1), k):
            if 0 <= j < len(vals):
                acc += vals[j] * kw
                wsum += kw
        out.append(acc / wsum)
    return out
