import { describe, expect, it } from "vitest";
import { checkFacts, parseFactIds, parseScript } from "../src/script";

const md = `# Script: test

Voice: af_heart · Speed: 1.05 · Pause between beats: 0.3 s

## b1 · set up
Say: Think of a Kafka [topic] as a log.
Show: one long log.
Facts: F2, F8

## b2 · reveal
Say: Kafka splits a topic into [partitions].
Show: three lanes.
Facts: F3

## b3 · recap
Say: One topic, many logs.
Show: everything moving.
Facts: —
`;

describe("parseScript", () => {
  const s = parseScript(md);

  it("reads the voice settings", () => {
    expect(s).toMatchObject({ voice: "af_heart", recorded: false, speed: 1.05, pause: 0.3 });
  });

  it("reads a recorded voice, which has no speed", () => {
    const rec = parseScript(md.replace("Voice: af_heart · Speed: 1.05 · Pause between beats: 0.3 s", "Voice: Teja (recorded) · Pause between beats: 0.4 s"));
    expect(rec).toMatchObject({ voice: "Teja (recorded)", recorded: true, pause: 0.4 });
    expect(() => parseScript(md.replace("Speed: 1.05 · ", ""))).toThrow(/Speed/);
  });

  it("reads each beat's lines and fact references", () => {
    expect(s.beats.map((b) => b.id)).toEqual(["b1", "b2", "b3"]);
    expect(s.beats[0]).toEqual({
      id: "b1",
      title: "set up",
      say: "Think of a Kafka [topic] as a log.",
      show: "one long log.",
      facts: ["F2", "F8"],
    });
    expect(s.beats[2]!.facts).toEqual([]);
  });

  it("rejects a script without the voice line", () => {
    expect(() => parseScript("## b1 · x\nSay: hi")).toThrow(/Voice:/);
  });

  it("rejects duplicate beat ids", () => {
    expect(() => parseScript(md.replace("## b2", "## b1"))).toThrow(/twice/);
  });
});

describe("facts", () => {
  const facts = "| ID | Fact |\n|---|---|\n| F2 | a |\n| F3 | b |\n";

  it("finds fact ids in the table", () => {
    expect([...parseFactIds(facts)]).toEqual(["F2", "F3"]);
  });

  it("flags citations that don't exist", () => {
    expect(checkFacts(parseScript(md), parseFactIds(facts))).toEqual(["b1 cites F8, which isn't in facts.md"]);
  });
});
