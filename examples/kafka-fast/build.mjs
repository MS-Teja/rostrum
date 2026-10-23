// Turn Blender's output into overlay inputs: the plate frames into renders/plate.mp4
// at 1920x1080, and the per-frame anchors into anchors.js in the same pixel space.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const here = import.meta.dirname;
const plates = join(here, "renders/plates");
const { fps, width, frames } = JSON.parse(readFileSync(join(plates, "anchors.json"), "utf8"));

execFileSync(
  "ffmpeg",
  ["-v", "error", "-y", "-framerate", String(fps), "-i", join(plates, "f_%04d.png"),
   "-vf", "scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-crf", "12", "-preset", "slow", "-pix_fmt", "yuv420p",
   join(here, "renders/plate.mp4")],
  { stdio: "inherit" },
);

// Anchors were projected at the render's resolution; the overlay works at 1920 wide.
const k = 1920 / width;
const scaled = Object.fromEntries(
  Object.entries(frames).map(([f, anchors]) => [
    f,
    Object.fromEntries(Object.entries(anchors).map(([name, [x, y, v]]) => [name, [+(x * k).toFixed(1), +(y * k).toFixed(1), v]])),
  ]),
);
writeFileSync(join(here, "anchors.js"), `window.ANCHORS = ${JSON.stringify({ fps, frames: scaled })};\n`);
console.log(`plate.mp4 and anchors.js: ${Object.keys(frames).length} frames at ${fps} fps`);
