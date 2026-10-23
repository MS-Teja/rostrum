"""Narration with exact word timings, straight from the voice model.

Kokoro's timestamped export reports how long it spends on every phoneme, so
word times come from the synthesis itself instead of transcribing the audio
afterwards (speech recognition was ~0.25 s early on phrase starts in tests).

  python kokoro_timed.py --text "A log is a list." --voice am_michael \
      --out b1.wav --words b1.words.json

Needs: kokoro-onnx, soundfile, and the timestamped model:
  https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX-timestamped
"""

import argparse
import json
import os
import re
import sys

import soundfile as sf
from kokoro_onnx import Kokoro

DEFAULT_MODEL = os.path.expanduser("~/.cache/rostrum/models/kokoro-v1.0-timestamped.onnx")
DEFAULT_VOICES = os.path.expanduser("~/.cache/hyperframes/tts/voices/voices-v1.0.bin")

# Spaces, punctuation and stress/length marks carry no word identity.
SKIP = set(" ,.:;!?—…\"'()ˈˌː")


def word_timings(kokoro: Kokoro, text: str, spoken, lang: str) -> list[dict]:
    """Give each word of `text` the time span of the phonemes it produced."""
    words = text.split()

    # Phonemize each word alone, remembering which word every phoneme came from.
    ref, owner = [], []
    for i, word in enumerate(words):
        core = re.sub(r"[^\w'-]", "", word)
        if not core:
            continue
        for ch in kokoro.tokenizer.phonemize(core, lang):
            if ch not in SKIP:
                ref.append(ch)
                owner.append(i)

    # The phonemes actually spoken (whole-sentence phonemization differs a little:
    # "on the" becomes one group, function words reduce), with their times.
    heard = [(t.phoneme, t.start, t.end) for t in spoken if t.phoneme not in SKIP]

    # Needleman–Wunsch alignment of word phonemes to spoken phonemes.
    n, m = len(ref), len(heard)
    gap = -1
    score = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = i * gap
    for j in range(1, m + 1):
        score[0][j] = j * gap
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match = 2 if ref[i - 1] == heard[j - 1][0] else -1
            score[i][j] = max(score[i - 1][j - 1] + match, score[i - 1][j] + gap, score[i][j - 1] + gap)

    label = [None] * m
    i, j = n, m
    while i > 0 and j > 0:
        match = 2 if ref[i - 1] == heard[j - 1][0] else -1
        if score[i][j] == score[i - 1][j - 1] + match:
            label[j - 1] = owner[i - 1]
            i, j = i - 1, j - 1
        elif score[i][j] == score[i][j - 1] + gap:
            j -= 1
        else:
            i -= 1

    # A spoken phoneme left unlabelled belongs to the word before it.
    last = None
    for k in range(m):
        if label[k] is None:
            label[k] = last
        last = label[k]

    spans: dict[int, list[float]] = {}
    for (_, start, end), w in zip(heard, label):
        if w is None:
            continue
        span = spans.setdefault(w, [start, end])
        span[0] = min(span[0], start)
        span[1] = max(span[1], end)

    out = []
    for i, word in enumerate(words):
        if i in spans:
            out.append({"text": word, "start": round(spans[i][0], 3), "end": round(spans[i][1], 3)})
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--text", required=True)
    p.add_argument("--voice", default="am_michael")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--lang", default="en-us")
    p.add_argument("--out", required=True, help="WAV file to write")
    p.add_argument("--words", required=True, help="JSON file for word timings")
    p.add_argument("--model", default=os.environ.get("ROSTRUM_KOKORO_MODEL", DEFAULT_MODEL))
    p.add_argument("--voices", default=os.environ.get("ROSTRUM_KOKORO_VOICES", DEFAULT_VOICES))
    a = p.parse_args()

    for path in (a.model, a.voices):
        if not os.path.exists(path):
            sys.exit(f"Missing {path}. See the setup notes at the top of this file.")

    kokoro = Kokoro(a.model, a.voices)
    # The timestamped export names its output "durations"; kokoro-onnx 0.6.1 looks
    # for "duration". Inference reads the output by position, so turn it on.
    if len(kokoro.sess.get_outputs()) > 1:
        kokoro.has_timings = True
    if not kokoro.has_timings:
        sys.exit("This model doesn't report phoneme durations; use the timestamped export.")

    audio, rate, spoken = kokoro.create_timed(a.text, a.voice, speed=a.speed, lang=a.lang)
    words = word_timings(kokoro, a.text, spoken, a.lang)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sf.write(a.out, audio, rate)
    with open(a.words, "w") as f:
        json.dump(words, f, indent=1)
    print(json.dumps({"ok": True, "out": a.out, "words": a.words, "durationSeconds": round(len(audio) / rate, 3), "wordCount": len(words)}))


if __name__ == "__main__":
    main()
