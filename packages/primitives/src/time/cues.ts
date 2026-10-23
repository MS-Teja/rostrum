/**
 * Cues tie animation to narration. In the script, a cue is a bracketed word or
 * phrase: "Producers write records to a [topic]." or "[the log|log]" to name it.
 * Each cue resolves to the moment its first word is spoken.
 */

/** A spoken word with times in seconds, as produced by transcription. */
export interface Word {
  text: string;
  start: number;
  end: number;
}

/** One beat of the script: 1–3 sentences, possibly containing [cues]. */
export interface Beat {
  id: string;
  text: string;
}

/** The narration audio for one beat: where it starts in the track, and its words (times local to the beat). */
export interface BeatAudio {
  id: string;
  offset: number;
  words: Word[];
}

export interface Cue {
  /** `${beatId}:${name}` — unique even when the same word is cued in several beats. */
  key: string;
  name: string;
  beatId: string;
  /** Seconds from the start of the narration track. */
  time: number;
  /** True when the cue word wasn't found in the audio and its time was interpolated. */
  estimated: boolean;
}

interface ParsedCue {
  name: string;
  tokenIndex: number;
}

const CUE = /\[([^\]|]+)(?:\|([^\]]+))?\]/g;

/** Lowercase letters and digits only, so "Topic," and "topic" match. */
export const normalize = (token: string): string => token.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");

/** Split text into normalized word tokens; hyphens split words, as speech engines usually do. */
export const tokenize = (text: string): string[] =>
  text
    .split(/[\s\-–—/]+/)
    .map(normalize)
    .filter((t) => t.length > 0);

/** Strip cue brackets, returning the spoken text and each cue's position among its tokens. */
export function parseCues(text: string): { plain: string; tokens: string[]; cues: ParsedCue[] } {
  const cues: ParsedCue[] = [];
  let plain = "";
  let last = 0;
  for (const m of text.matchAll(CUE)) {
    const before = text.slice(last, m.index);
    plain += before;
    const spoken = m[1]!;
    cues.push({ name: (m[2] ?? spoken).trim(), tokenIndex: tokenize(plain).length });
    plain += spoken;
    last = m.index + m[0].length;
  }
  plain += text.slice(last);
  return { plain, tokens: tokenize(plain), cues };
}

/**
 * Global alignment (Needleman–Wunsch) of script tokens to transcript tokens.
 * Returns, for each script token, the index of the transcript word it lines up with, or -1.
 */
export function align(script: readonly string[], heard: readonly string[]): number[] {
  const n = script.length;
  const m = heard.length;
  const GAP = -1;
  const score = (a: string, b: string) => {
    if (a === b) return 2;
    if (a.length >= 3 && b.length >= 3 && (a.startsWith(b) || b.startsWith(a))) return 1;
    return -1;
  };

  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = 1; i <= n; i++) dp[i]![0] = i * GAP;
  for (let j = 1; j <= m; j++) dp[0]![j] = j * GAP;
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      dp[i]![j] = Math.max(
        dp[i - 1]![j - 1]! + score(script[i - 1]!, heard[j - 1]!),
        dp[i - 1]![j]! + GAP,
        dp[i]![j - 1]! + GAP,
      );
    }
  }

  const pairs = new Array<number>(n).fill(-1);
  let i = n;
  let j = m;
  while (i > 0 && j > 0) {
    const here = dp[i]![j]!;
    const s = score(script[i - 1]!, heard[j - 1]!);
    const diagonal = here === dp[i - 1]![j - 1]! + s;
    const skipHeard = here === dp[i]![j - 1]! + GAP;
    // A substitution ("42" heard as "forty two") still pins the time, but when
    // tied with skipping a heard word, skip first: the cue belongs on the first
    // word the number was spoken as.
    if (diagonal && (s > 0 || !skipHeard)) {
      pairs[i - 1] = j - 1;
      i--;
      j--;
    } else if (skipHeard) {
      j--;
    } else {
      i--;
    }
  }
  return pairs;
}

/** Resolve every cue in the script to a time on the narration track. */
export function resolveCues(beats: readonly Beat[], audio: readonly BeatAudio[]): Cue[] {
  const audioById = new Map(audio.map((a) => [a.id, a]));
  const out: Cue[] = [];

  for (const beat of beats) {
    const { tokens, cues } = parseCues(beat.text);
    if (cues.length === 0) continue;
    const clip = audioById.get(beat.id);
    if (!clip) throw new Error(`No narration audio for beat "${beat.id}"`);

    const heard = clip.words.map((w) => normalize(w.text));
    const pairs = align(tokens, heard);

    for (const cue of cues) {
      const j = pairs[cue.tokenIndex] ?? -1;
      const word = j >= 0 ? clip.words[j] : undefined;
      const time = word ? word.start : interpolate(cue.tokenIndex, pairs, clip.words);
      out.push({
        key: `${beat.id}:${cue.name}`,
        name: cue.name,
        beatId: beat.id,
        time: clip.offset + time,
        estimated: !word,
      });
    }
  }
  return out;
}

/** Estimate a time for an unmatched token from its nearest matched neighbours. */
function interpolate(index: number, pairs: readonly number[], words: readonly Word[]): number {
  let prev = index - 1;
  while (prev >= 0 && (pairs[prev] ?? -1) < 0) prev--;
  let next = index + 1;
  while (next < pairs.length && (pairs[next] ?? -1) < 0) next++;

  const prevWord = prev >= 0 ? words[pairs[prev]!] : undefined;
  const nextWord = next < pairs.length ? words[pairs[next]!] : undefined;
  const from = prevWord ? prevWord.end : 0;
  const to = nextWord ? nextWord.start : (words.at(-1)?.end ?? from);
  const lo = prevWord ? prev : -1;
  const hi = nextWord ? next : pairs.length;
  return from + ((to - from) * (index - lo)) / (hi - lo);
}
