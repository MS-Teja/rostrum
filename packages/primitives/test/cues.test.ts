import { describe, expect, it } from "vitest";
import { parseCues, resolveCues, type Word } from "../src/time/cues";

/** Words spoken back to back, 0.3 s each, starting at `from`. */
const speak = (text: string, from = 0): Word[] =>
  text.split(" ").map((w, i) => ({ text: w, start: from + i * 0.3, end: from + i * 0.3 + 0.25 }));

describe("parseCues", () => {
  it("strips brackets and records where each cue starts", () => {
    const { plain, cues } = parseCues("Producers write records to a [topic].");
    expect(plain).toBe("Producers write records to a topic.");
    expect(cues).toEqual([{ name: "topic", tokenIndex: 5 }]);
  });

  it("names a phrase cue and anchors it on the phrase's first word", () => {
    const { tokens, cues } = parseCues("Each partition is [an append-only log|log].");
    expect(tokens).toEqual(["each", "partition", "is", "an", "append", "only", "log"]);
    expect(cues).toEqual([{ name: "log", tokenIndex: 3 }]);
  });
});

describe("resolveCues", () => {
  it("returns the time the cue word is spoken, offset by the beat's start", () => {
    const beats = [{ id: "b1", text: "Producers write records to a [topic]." }];
    const audio = [{ id: "b1", offset: 10, words: speak("Producers write records to a topic.") }];
    const [cue] = resolveCues(beats, audio);
    expect(cue).toMatchObject({ key: "b1:topic", estimated: false });
    expect(cue!.time).toBeCloseTo(10 + 5 * 0.3);
  });

  it("matches numbers read out as words", () => {
    const beats = [{ id: "b1", text: "Record [42] lands in partition one." }];
    const audio = [{ id: "b1", offset: 0, words: speak("record forty two lands in partition one") }];
    const [cue] = resolveCues(beats, audio);
    expect(cue!.estimated).toBe(false);
    expect(cue!.time).toBeCloseTo(0.3); // "forty"
  });

  it("estimates a cue the speech engine dropped, between its neighbours", () => {
    const beats = [{ id: "b1", text: "Then the [consumer] reads it." }];
    const audio = [{ id: "b1", offset: 0, words: speak("then the reads it") }];
    const [cue] = resolveCues(beats, audio);
    expect(cue!.estimated).toBe(true);
    // Between the end of "the" (0.55 s) and the start of "reads" (0.6 s).
    expect(cue!.time).toBeGreaterThanOrEqual(0.55);
    expect(cue!.time).toBeLessThanOrEqual(0.6);
  });

  it("keeps the same cue word in different beats apart", () => {
    const beats = [
      { id: "b1", text: "A [partition] is a log." },
      { id: "b2", text: "Another [partition] grows too." },
    ];
    const audio = [
      { id: "b1", offset: 0, words: speak("A partition is a log.") },
      { id: "b2", offset: 5, words: speak("Another partition grows too.") },
    ];
    const cues = resolveCues(beats, audio);
    expect(cues.map((c) => c.key)).toEqual(["b1:partition", "b2:partition"]);
    expect(cues[1]!.time).toBeCloseTo(5.3);
  });

  it("ignores case and punctuation differences in the transcript", () => {
    const beats = [{ id: "b1", text: "It's an [append-only] log." }];
    const audio = [{ id: "b1", offset: 0, words: speak("Its an Append only log") }];
    const [cue] = resolveCues(beats, audio);
    expect(cue).toMatchObject({ estimated: false });
    expect(cue!.time).toBeCloseTo(0.6);
  });

  it("fails loudly when a beat with cues has no audio", () => {
    expect(() => resolveCues([{ id: "b9", text: "A [cue]." }], [])).toThrow(/b9/);
  });
});
