import type { Word } from "@rostrum/primitives";

const ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"];
const TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];
const SCALES: Array<[number, string]> = [
  [1_000_000_000, "billion"],
  [1_000_000, "million"],
  [1_000, "thousand"],
];

/** An integer in words, as a narrator says it: 21 → "twenty one", 7000 → "seven thousand". */
export function spell(n: number): string[] {
  if (n < 20) return [ONES[n]!];
  if (n < 100) return [TENS[Math.floor(n / 10)]!, ...(n % 10 ? [ONES[n % 10]!] : [])];
  if (n < 1000) return [ONES[Math.floor(n / 100)]!, "hundred", ...(n % 100 ? spell(n % 100) : [])];
  for (const [size, name] of SCALES) {
    if (n >= size) return [...spell(Math.floor(n / size)), name, ...(n % size ? spell(n % size) : [])];
  }
  return [String(n)];
}

const ORDINAL: Record<string, string> = { one: "first", two: "second", three: "third", five: "fifth", eight: "eighth", nine: "ninth", twelve: "twelfth" };

function ordinal(words: string[]): string[] {
  const last = words.at(-1)!;
  const said = ORDINAL[last] ?? (last.endsWith("y") ? `${last.slice(0, -1)}ieth` : `${last}th`);
  return [...words.slice(0, -1), said];
}

/**
 * Transcribers write numbers as digits ("21", "7,000", "19th"); scripts spell them
 * out. Spell each one into words sharing the original word's time, so cues on
 * spoken numbers match. Years and other four-digit runs stay as they are.
 */
export function spellNumbers(words: Word[]): Word[] {
  return words.flatMap((w) => {
    const m = w.text.match(/^(\d{1,3}(?:,\d{3})+|\d+)(st|nd|rd|th)?([^\p{L}\p{N}]*)$/u);
    if (!m) return [w];
    const n = Number(m[1]!.replaceAll(",", ""));
    if (!Number.isSafeInteger(n) || (/^\d{4}$/.test(m[1]!) && n >= 1900 && n < 2100 && !m[2])) return [w];
    const said = m[2] ? ordinal(spell(n)) : spell(n);
    const step = (w.end - w.start) / said.length;
    return said.map((text, i) => ({
      text: i === said.length - 1 ? text + m[3]! : text,
      start: w.start + i * step,
      end: w.start + (i + 1) * step,
    }));
  });
}
