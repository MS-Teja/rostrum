# Why Kafka is fast (in progress)

A ~50 second explainer in cinematic 3D: follow the bytes through a broker's hardware, from the page cache through the usual four copies, then the sendfile shortcut. Built with [`packages/stage3d`](../../packages/stage3d) (Blender) and HyperFrames for the labels.

Status: a 15-second animated test of the zero-copy idea, plus style frames for shots 1 (the broker), 3 (the usual path) and 4 (sendfile), each in two looks, `keynote` and `cutaway`.

## Build the 15-second animation

The narration's word timings drive everything: in Blender, every leg of the data's trip ends on the word that names where it lands; in the overlay, labels and numbered copies appear on the same words and ride the camera move via per-frame anchors.

```sh
node packages/director/dist/cli.mjs check examples/kafka-fast        # script vs facts
ROSTRUM_PYTHON=/path/to/python-with-kokoro-onnx \
  node packages/director/dist/cli.mjs voice examples/kafka-fast      # audio + timing.js
$B -b --factory-startup -P packages/stage3d/render.py -- --scene examples/kafka-fast/scene.py \
  --look keynote --shot anim --timing examples/kafka-fast/timing.js \
  --engine cycles --samples 16 --pct 75 --frames 1-504 --out examples/kafka-fast/renders/plates
node examples/kafka-fast/build.mjs                                   # plate.mp4 + anchors.js
ROSTRUM_TAIL=1.7 node packages/director/dist/cli.mjs compose examples/kafka-fast
npx hyperframes@0.8.185 render examples/kafka-fast -o examples/kafka-fast/renders/zero-copy.mp4
```

The plates take about 35 minutes on an M2 Mac mini (16 samples, denoised, 1440x810, upscaled to 1080p). `timing.js` is committed, so the Blender step works without the voice model.

## Render the style frames

```sh
B=/path/to/Blender.app/Contents/MacOS/Blender
for look in keynote cutaway; do for shot in 1 3 4; do
  $B -b --factory-startup -P packages/stage3d/render.py -- --scene examples/kafka-fast/scene.py \
    --look $look --shot $shot --engine cycles --samples 128 --still 1 \
    --out examples/kafka-fast/stills/plates/$look-$shot.png
done; done
node examples/kafka-fast/stills/build.mjs
npx hyperframes@0.8.185 snapshot examples/kafka-fast/stills --at 0.5,1.5,2.5,3.5,4.5,5.5 --no-end --keep -o examples/kafka-fast/stills/out
```

On an M2 Mac mini each 1080p Cycles plate takes 40–60 s. The studio lighting uses two CC0 HDRIs from Poly Haven (`studio_small_09`, `studio_small_03`), expected in `~/.cache/rostrum/hdri/` (override with `ROSTRUM_HDRI_DIR`).

Facts come from the Kafka design docs: the page cache, "four copies and two system calls", sendfile, and "sendfile is not used when SSL is enabled".
