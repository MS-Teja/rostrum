// Builds the log demo: script → narration with word timings (Kokoro, timestamped
// export) → cue times → log events → a HyperFrames project ready to render.
//
//   ROSTRUM_PYTHON=/path/to/venv/bin/python node build.mjs
//   npx hyperframes@0.8.185 render -o renders/log-demo.mp4

import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { parseCues, resolveCues } from "../../packages/primitives/dist/index.mjs";

const here = import.meta.dirname;
const script = JSON.parse(readFileSync(join(here, "script.json"), "utf8"));
const python = process.env.ROSTRUM_PYTHON ?? process.env.HYPERFRAMES_PYTHON ?? "python3";
const voiceTool = join(here, "../../packages/voice/kokoro_timed.py");

mkdirSync(join(here, "audio"), { recursive: true });
mkdirSync(join(here, "vendor"), { recursive: true });

// 1. One clip per beat, each with exact word timings from the voice model.
const clips = script.beats.map((beat) => {
  const file = `audio/${beat.id}.wav`;
  const wordsFile = `audio/${beat.id}.words.json`;
  const { plain } = parseCues(beat.text);
  const out = execFileSync(
    python,
    [voiceTool, "--text", plain, "--voice", script.voice, "--speed", String(script.speed), "--out", file, "--words", wordsFile],
    { cwd: here, encoding: "utf8" },
  );
  const { durationSeconds } = JSON.parse(out.trim().split("\n").at(-1));
  return { id: beat.id, file, duration: durationSeconds, words: JSON.parse(readFileSync(join(here, wordsFile), "utf8")) };
});

// 2. Join the clips with a pause after each beat; each beat's offset is exact.
const offsets = [];
let total = 0;
for (const clip of clips) {
  offsets.push(total);
  total += clip.duration + script.pause;
}
const inputs = clips.flatMap((c) => ["-i", c.file]);
const pads = clips.map((_, i) => `[${i}:a]apad=pad_dur=${script.pause}[a${i}]`).join(";");
const joined = clips.map((_, i) => `[a${i}]`).join("");
execFileSync(
  "ffmpeg",
  ["-v", "error", "-y", ...inputs, "-filter_complex", `${pads};${joined}concat=n=${clips.length}:v=0:a=1[out]`, "-map", "[out]", "audio/narration.wav"],
  { cwd: here },
);

// 3. Word times are already local to each beat's clip.
const audio = clips.map((clip, i) => ({ id: clip.id, offset: offsets[i], words: clip.words }));

// 4. Cues → events. This mapping is the storyboard; the director will write it later.
const cues = resolveCues(script.beats, audio);
const at = (key) => {
  const cue = cues.find((c) => c.key === key);
  if (!cue) throw new Error(`Missing cue ${key}`);
  return cue.time;
};
const events = [
  { type: "append", at: at("b2:r0"), record: { id: "a", label: "A" } },
  { type: "append", at: at("b2:r1"), record: { id: "b", label: "B" } },
  { type: "append", at: at("b2:r2"), record: { id: "c", label: "C" } },
  { type: "append", at: at("b2:r3"), record: { id: "d", label: "D" } },
  { type: "read", at: at("b3:reader"), reader: "reader", offset: 0 },
  { type: "read", at: at("b3:advance"), reader: "reader", offset: 3, duration: 1.4 },
  { type: "expire", at: at("b4:expire"), before: 2 },
];

// 5. Write the HyperFrames project.
const duration = Math.ceil((total + 0.6) * 100) / 100;
writeFileSync(join(here, "scene.js"), `window.ROSTRUM_SCENE = ${JSON.stringify({ duration, events })};\n`);
writeFileSync(
  join(here, "index.html"),
  readFileSync(join(here, "composition.html"), "utf8").replace("{{DURATION}}", String(duration)),
);
copyFileSync(join(here, "../../packages/primitives/dist/rostrum.js"), join(here, "vendor/rostrum.js"));

console.log(`Narration ${total.toFixed(2)} s, video ${duration} s`);
for (const c of cues) console.log(`  ${c.key.padEnd(12)} ${c.time.toFixed(3)} s${c.estimated ? "  (estimated)" : ""}`);
