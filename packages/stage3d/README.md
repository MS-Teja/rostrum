# stage3d

Rostrum's 3D stage: a look kit that runs inside Blender (5.2 or later). Scenes are built from code, so an agent can direct them, and the kit carries the taste: lighting rigs, materials, bevelled procedural hardware, data drawn as light, and camera rigs.

**License: GPL-3.0-or-later** (see [LICENSE](LICENSE)), because this code calls Blender's Python API. The rest of Rostrum is Apache-2.0 and only runs Blender as a separate process. Rendered images and videos are yours, under no license from this package.

## Render

```sh
blender -b --factory-startup -P packages/stage3d/render.py -- \
  --scene examples/kafka-fast/scene.py --look keynote --shot 3 \
  --engine cycles --samples 128 --still 1 --out renders/keynote-3.png
```

- `--still N` renders one frame; `--frames a-b` renders a range into a directory.
- Every render also writes **anchors**: named 3D points projected to pixels per frame (`*.anchors.json`). The HTML overlay uses them to pin crisp labels to objects through any camera move.
- `--hide prefix,...` leaves objects out, for look development. `--save scene.blend` keeps the built scene to inspect.

## What's in the kit

| Module | What it does |
|---|---|
| `look.py` | Render presets (EEVEE previews, Cycles finals), AgX colour, bloom and lens dispersion |
| `lights.py` | `keynote` (dark, rim-lit) and `cutaway` (bright studio) rigs, raking strips, and light linking (`exclude`, `only`) to keep lights out of floors and glass |
| `materials.py` | Aluminium, powder coat, circuit board, chip epoxy, gold, glass, a glowing glass sheet, data |
| `parts.py` | Server, rack, RAM stick, M.2 SSD, network card, heatsink, fan: real dimensions, bevelled edges |
| `flow.py` | Filleted paths, tubes, tiles and pulses for data |
| `camera.py`, `anchors.py` | Aimed cameras with focus, and label anchors |
| `easing.py`, `timing.py` | The same easing curves as `packages/primitives`, and narration cues to frames (tested against the TypeScript versions) |

Lessons baked in: light power set so near-black materials stay black; rims kept off flat surfaces; glass that casts no shadow and never shows a light through it.
