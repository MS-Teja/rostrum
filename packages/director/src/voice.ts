import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
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

  return assemble(dir, script, clips);
}

interface Clip {
  id: string;
  /** Path relative to `dir`. */
  file: string;
  duration: number;
  words: Word[];
}

/** Join beat clips with the script's pause after each, and resolve the [cues] on the joined track. */
function assemble(dir: string, script: Script, clips: Clip[]): Narration {
  const audio: BeatAudio[] = [];
  const beats: Narration["beats"] = [];
  let t = 0;
  for (const clip of clips) {
    audio.push({ id: clip.id, offset: t, words: clip.words });
    beats.push({ id: clip.id, start: t, end: t + clip.duration });
    t += clip.duration + script.pause;
  }

  const inputs = clips.flatMap((c) => ["-i", c.file]);
  const pads = clips.map((_, i) => `[${i}:a]aresample=48000,apad=pad_dur=${script.pause}[a${i}]`).join(";");
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

const TAKE_EXTENSIONS = ["m4a", "mp3", "wav", "aac", "flac", "ogg"];

export interface AlignOptions {
  /** Path to the HyperFrames CLI (bin/hyperframes.mjs), for its Parakeet transcriber. */
  hyperframes: string;
}

/**
 * Time a person's recording of the script: audio/<beat>.<ext> for every beat.
 * Each take is trimmed of leading and trailing silence, transcribed for word
 * times, then joined and matched to the cues like synthesised narration.
 * Measured against known word times, the transcriber's onsets land a median
 * 1.5 frames from the truth with no constant bias, so they're used as they are.
 * Writes audio/<beat>.take.wav, audio/<beat>.words.json and audio/narration.wav.
 */
export function align(dir: string, script: Script, opts: AlignOptions): Narration & { missing: string[] } {
  const takeOf = (id: string) => TAKE_EXTENSIONS.map((ext) => `audio/${id}.${ext}`).find((f) => existsSync(join(dir, f)));
  // A recording session can be partial: time what's recorded, and say what isn't.
  const missing = script.beats.filter((b) => !takeOf(b.id)).map((b) => b.id);
  const recorded = { ...script, beats: script.beats.filter((b) => takeOf(b.id)) };
  if (recorded.beats.length === 0) throw new Error(`no recordings yet: expected audio/<beat>.m4a, .mp3 or .wav, e.g. audio/${script.beats[0]?.id}.m4a`);
  const clips = recorded.beats.map((beat) => {
    const source = takeOf(beat.id)!;
    const file = `audio/${beat.id}.take.wav`;
    // Keep a breath of room tone at each end, so cuts between beats sound natural.
    const trim = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse";
    execFileSync("ffmpeg", ["-v", "error", "-y", "-i", source, "-af", trim, "-ar", "48000", "-ac", "1", file], { cwd: dir });

    const scratch = mkdtempSync(join(tmpdir(), `rostrum-align-${beat.id}-`));
    try {
      const copy = join(scratch, "take.wav");
      copyFileSync(join(dir, file), copy);
      const out = execFileSync(process.execPath, [opts.hyperframes, "transcribe", copy, "--json"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
      const { transcriptPath } = JSON.parse(out.trim().split("\n").at(-1)!) as { transcriptPath: string };
      const raw = JSON.parse(readFileSync(transcriptPath, "utf8")) as Array<{ text: string; start: number; end: number }>;
      const words: Word[] = raw.map(({ text, start, end }) => ({ text, start, end }));
      writeFileSync(join(dir, `audio/${beat.id}.words.json`), JSON.stringify(words, null, 1));
      const duration = Number(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], { cwd: dir, encoding: "utf8" }));
      return { id: beat.id, file, duration, words };
    } finally {
      rmSync(scratch, { recursive: true, force: true });
    }
  });
  return { ...assemble(dir, recorded, clips), missing };
}
