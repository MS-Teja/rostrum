import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { checkFacts, parseFactIds, parseScript } from "./script";
import { narrate } from "./voice";

const USAGE = `rostrum <command> <dir>

  check <dir>     Check script.md against facts.md
  voice <dir>     Speak script.md with word timings; write audio/ and timing.js
  compose <dir>   Build index.html from src/index.html and timing.js`;

const [command, target] = process.argv.slice(2);
if (!command || !target) {
  console.error(USAGE);
  process.exit(1);
}
const dir = resolve(target);
const script = parseScript(readFileSync(join(dir, "script.md"), "utf8"));

function check(): number {
  const issues = checkFacts(script, parseFactIds(readFileSync(join(dir, "facts.md"), "utf8")));
  for (const beat of script.beats) if (beat.facts.length === 0 && beat.id !== script.beats.at(-1)?.id) {
    issues.push(`${beat.id} cites no facts`);
  }
  for (const i of issues) console.log(`  ✗ ${i}`);
  console.log(issues.length === 0 ? `✓ ${script.beats.length} beats, every fact cited exists` : `${issues.length} issue(s)`);
  return issues.length === 0 ? 0 : 1;
}

function voice(): number {
  if (script.recorded) {
    console.error(`${script.voice} is a recorded voice: record the script and align it instead of synthesising it.`);
    return 1;
  }
  const here = import.meta.dirname;
  const python = process.env.ROSTRUM_PYTHON ?? process.env.HYPERFRAMES_PYTHON ?? "python3";
  const tool = resolve(here, "../../voice/kokoro_timed.py");
  const n = narrate(dir, script, { python, tool });

  const cues = Object.fromEntries(n.cues.map((c) => [c.key, Number(c.time.toFixed(3))]));
  const timing = { duration: Number(n.duration.toFixed(3)), beats: n.beats, cues };
  writeFileSync(join(dir, "timing.js"), `window.ROSTRUM_TIMING = ${JSON.stringify(timing, null, 1)};\n`);

  const words = script.beats.reduce((s, b) => s + b.say.split(/\s+/).length, 0);
  console.log(`Narration ${n.duration.toFixed(2)} s · ${words} words · ${((words / n.duration) * 60).toFixed(0)} wpm`);
  for (const c of n.cues) console.log(`  ${c.key.padEnd(14)} ${c.time.toFixed(3)} s${c.estimated ? "  (estimated)" : ""}`);
  return n.cues.some((c) => c.estimated) ? 2 : 0;
}

/**
 * Turn an example into a HyperFrames project: src/index.html → index.html with
 * the narration's length filled in, plus the primitives bundle in vendor/.
 */
function compose(): number {
  const here = import.meta.dirname;
  const timingFile = join(dir, "timing.js");
  const timing = JSON.parse(readFileSync(timingFile, "utf8").replace(/^window\.ROSTRUM_TIMING = /, "").replace(/;\s*$/, "")) as {
    duration: number;
    cues: Record<string, number>;
  };
  const tail = Number(process.env.ROSTRUM_TAIL ?? 3.5);
  const duration = Math.ceil((timing.duration + tail) * 100) / 100;
  const template = readFileSync(join(dir, "src/index.html"), "utf8");
  writeFileSync(join(dir, "index.html"), template.replaceAll("{{DURATION}}", String(duration)));
  mkdirSync(join(dir, "vendor"), { recursive: true });
  copyFileSync(resolve(here, "../../primitives/dist/rostrum.js"), join(dir, "vendor/rostrum.js"));

  // Narration levelled for YouTube (−17 LUFS here, so the mix with sound effects lands near YouTube's −14).
  execFileSync("ffmpeg", ["-v", "error", "-y", "-i", "audio/narration.wav", "-af", "loudnorm=I=-17:TP=-1.5:LRA=11", "-ar", "48000", "audio/voice.wav"], { cwd: dir });

  // Sound effects placed on cue words, mixed into one track.
  const sfxFile = join(dir, "sfx.json");
  if (existsSync(sfxFile)) {
    const { sounds } = JSON.parse(readFileSync(sfxFile, "utf8")) as {
      sounds: Array<{ at: string; sound: string; gain?: number; shift?: number; align?: "start" | "end" }>;
    };
    const lead = Number(template.match(/id="narration"[^>]*?data-start="([\d.]+)"/s)?.[1] ?? 0);
    const library = process.env.ROSTRUM_SFX_DIR ?? resolve(dirname(createRequire(import.meta.url).resolve("hyperframes/package.json")), "dist/skills/media-use/audio/assets/sfx");
    const inputs: string[] = [];
    const chains: string[] = [];
    sounds.forEach((s, i) => {
      const file = join(library, `${s.sound}.mp3`);
      const cueTime = timing.cues[s.at];
      if (cueTime === undefined) throw new Error(`sfx.json: no cue "${s.at}"`);
      const length = Number(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], { encoding: "utf8" }));
      const start = Math.max(0, lead + cueTime + (s.shift ?? 0) - (s.align === "end" ? length : 0));
      const ms = Math.round(start * 1000);
      inputs.push("-i", file);
      chains.push(`[${i}:a]aresample=48000,volume=${s.gain ?? 0.3},adelay=${ms}|${ms}[s${i}]`);
    });
    const mix = `${chains.join(";")};${sounds.map((_, i) => `[s${i}]`).join("")}amix=inputs=${sounds.length}:normalize=0:duration=longest[out]`;
    execFileSync("ffmpeg", ["-v", "error", "-y", ...inputs, "-filter_complex", mix, "-map", "[out]", "-ac", "2", "audio/sfx.wav"], { cwd: dir });
    console.log(`sound effects: ${sounds.length} placed from ${library}`);
  }

  console.log(`index.html ready · ${duration} s (narration ${timing.duration} s + ${tail} s tail)`);
  return 0;
}

const commands: Record<string, () => number> = { check, voice, compose };
const run = commands[command];
if (!run) {
  console.error(USAGE);
  process.exit(1);
}
process.exit(run());
