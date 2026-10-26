import { describe, expect, it } from "vitest";
import { spell, spellNumbers } from "../src/numbers";

describe("spell", () => {
  it("says numbers the way a narrator does", () => {
    expect(spell(21)).toEqual(["twenty", "one"]);
    expect(spell(15)).toEqual(["fifteen"]);
    expect(spell(380)).toEqual(["three", "hundred", "eighty"]);
    expect(spell(7000)).toEqual(["seven", "thousand"]);
    expect(spell(8_500_000)).toEqual(["eight", "million", "five", "hundred", "thousand"]);
  });
});

describe("spellNumbers", () => {
  it("expands digits into words that share the original word's time", () => {
    const out = spellNumbers([{ text: "21.", start: 1, end: 1.4 }]);
    expect(out.map((w) => w.text)).toEqual(["twenty", "one."]);
    expect(out[0]).toMatchObject({ start: 1, end: 1.2 });
    expect(out[1]!.end).toBeCloseTo(1.4, 9);
  });

  it("handles thousands separators and ordinals", () => {
    expect(spellNumbers([{ text: "7,000", start: 0, end: 1 }]).map((w) => w.text)).toEqual(["seven", "thousand"]);
    expect(spellNumbers([{ text: "19th", start: 0, end: 1 }]).map((w) => w.text)).toEqual(["nineteenth"]);
    expect(spellNumbers([{ text: "21st", start: 0, end: 1 }]).map((w) => w.text)).toEqual(["twenty", "first"]);
  });

  it("leaves years and ordinary words alone", () => {
    const words = [
      { text: "2024,", start: 0, end: 1 },
      { text: "file", start: 1, end: 2 },
    ];
    expect(spellNumbers(words)).toEqual(words);
  });
});
