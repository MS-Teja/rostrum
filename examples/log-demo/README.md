# Log demo

A 17-second narrated explainer of an append-only log. It's the first end-to-end test of Rostrum's timing. Every animation starts on a word in the narration:
- records arrive on "zero", "one", "two" and "three"
- the reader appears on "reader" and glides on "moves forward"
- old records fade on "expire"

```
script.json ──▶ Kokoro, timestamped export ──▶ beat clips + exact word times
     │                                                    │
     └── [cue] words ──────────────▶ resolveCues ◀────────┘
                                          │
                              log events at cue times ──▶ HyperFrames render
```

The word times come from the voice model itself, which reports how long it spends on every sound, so they're exact. Transcribing the audio afterwards was about 0.25 s early on the first word after a pause, and it merged "zero, one, two, three" into "0123".

## Run it

You need:
- Node 22+ and ffmpeg
- a Python with `kokoro-onnx` and `soundfile` installed
- the timestamped Kokoro model and its voices file:

```bash
mkdir -p ~/.cache/rostrum/models
curl -L -o ~/.cache/rostrum/models/kokoro-v1.0-timestamped.onnx \
  https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX-timestamped/resolve/main/onnx/model.onnx
curl -L -o ~/.cache/rostrum/models/voices-v1.0.bin \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
export ROSTRUM_KOKORO_VOICES=~/.cache/rostrum/models/voices-v1.0.bin
```

Then:

```bash
pnpm build                                   # from the repo root: bundles the primitives
cd examples/log-demo
ROSTRUM_PYTHON=/path/to/python node build.mjs
npx hyperframes@0.8.185 render -o renders/log-demo.mp4
```

The build prints every cue with its time in the narration. Any cue whose word couldn't be matched in the voice model's word timings is marked "estimated".
