# Why Kafka is fast (in progress)

A ~50 second explainer in cinematic 3D: follow the bytes through a broker's hardware, from the page cache through the usual four copies, then the sendfile shortcut. Built with [`packages/stage3d`](../../packages/stage3d) (Blender) and HyperFrames for the labels.

Status: style frames. Shots 1 (the broker), 3 (the usual path) and 4 (sendfile), each in two looks, `keynote` and `cutaway`.

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
