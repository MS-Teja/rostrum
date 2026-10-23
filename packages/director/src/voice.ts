import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { parseCues, resolveCues, type BeatAudio, type Cue, type Word } from "@rostrum/primitives";
import type { Script } from "./script";

export interface Narration {
  /** Seconds of narration, including the pause after the last beat. */
  duration: number;
  beats: Array<{ id: string; start: number; end: number }>;
  cues: Cue[];
}

export interface VoiceOptions {
  /** Python with kokoro-onnx and soundfile. */
  python: string;
  /** packages/voice/kokoro_timed.py */
  tool: string;
}

/**
 * Speak every beat with exact word timings, join the clips with the script's
 * pause after each, and resolve the [cues] to times on the joined track.
 * Writes audio/<beat>.wav, audio/<beat>.words.json and audio/narration.wav in `dir`.
 */
export function narrate(dir: string, script: Script, opts: VoiceOptions): Narration {
  mkdirSync(join(dir, "audio"), { recursive: true });

  const clips = script.beats.map((beat) => {
    const file = `audio/${beat.id}.wav`;
    const wordsFile = `audio/${beat.id}.words.json`;
    const out = execFileSync(
      opts.python,
      [opts.tool, "--text", parseCues(beat.say).plain, "--voice", script.voice, "--speed", String(script.speed), "--out", file, "--words", wordsFile],
      { cwd: dir, encoding: "utf8" },
    );
    const { durationSeconds } = JSON.parse(out.trim().split("\n").at(-1)!) as { durationSeconds: number };
    const words = JSON.parse(readFileSync(join(dir, wordsFile), "utf8")) as Word[];
    return { id: beat.id, file, duration: durationSeconds, words };
  });

  const audio: BeatAudio[] = [];
  const beats: Narration["beats"] = [];
  let t = 0;
  for (const clip of clips) {
    audio.push({ id: clip.id, offset: t, words: clip.words });
    beats.push({ id: clip.id, start: t, end: t + clip.duration });
    t += clip.duration + script.pause;
  }

  const inputs = clips.flatMap((c) => ["-i", c.file]);
  const pads = clips.map((_, i) => `[${i}:a]apad=pad_dur=${script.pause}[a${i}]`).join(";");
  const joined = clips.map((_, i) => `[a${i}]`).join("");
  execFileSync(
    "ffmpeg",
    ["-v", "error", "-y", ...inputs, "-filter_complex", `${pads};${joined}concat=n=${clips.length}:v=0:a=1[out]`, "-map", "[out]", "audio/narration.wav"],
    { cwd: dir },
  );

  const cues = resolveCues(
    script.beats.map((b) => ({ id: b.id, text: b.say })),
    audio,
  );
  return { duration: t, beats, cues };
}
