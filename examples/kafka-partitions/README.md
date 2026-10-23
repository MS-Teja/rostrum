# How Kafka partitions work (60 s)

The first segment made with Rostrum's process. Each stage leaves a file you can read and edit:

| Stage | File |
|---|---|
| 1. Facts, each with its source in the Kafka docs | [`facts.md`](facts.md) |
| 2. Teaching plan: the question, the reveals, the visual vocabulary | [`outline.md`](outline.md) |
| 3. Script: narration with `[cue]` words, visual intent and fact references | [`script.md`](script.md) |
| 4. Voice: per-beat narration with exact word timings | `audio/`, `timing.js` (generated) |
| 5–7. Art direction and scene, drawn as a pure function of time | [`src/index.html`](src/index.html), [`scene.js`](scene.js) |
| Sound: effects placed on cue words | [`sfx.json`](sfx.json) |

## Build and render

From the repo root, with the voice setup from [`examples/log-demo`](../log-demo/README.md):

```bash
pnpm build
pnpm rostrum check examples/kafka-partitions     # every cited fact exists
ROSTRUM_PYTHON=/path/to/python pnpm rostrum voice examples/kafka-partitions
pnpm rostrum compose examples/kafka-partitions   # index.html, levelled voice, sound effects
cd examples/kafka-partitions
npx hyperframes@0.8.185 lint
npx hyperframes@0.8.185 render -o renders/kafka-partitions.mp4
```

The sound effects come from the library bundled with HyperFrames (Pixabay Content License). `compose` finds them in `node_modules/hyperframes`, so they're never copied into this repo.
