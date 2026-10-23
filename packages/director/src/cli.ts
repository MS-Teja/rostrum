import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { checkFacts, parseFactIds, parseScript } from "./script";
import { narrate } from "./voice";

const USAGE = `rostrum <command> <dir>

  check <dir>   Check script.md against facts.md
  voice <dir>   Speak script.md with word timings; write audio/ and timing.js`;

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

const commands: Record<string, () => number> = { check, voice };
const run = commands[command];
if (!run) {
  console.error(USAGE);
  process.exit(1);
}
process.exit(run());
