/**
 * script.md, the narration stage file. A header line sets the voice; each
 * `## <id> · <title>` section is a beat with Say / Show / Facts lines:
 *
 *   Voice: af_heart · Speed: 1.0 · Pause between beats: 0.3 s
 *
 * A person's voice is marked "(recorded)" and has no speed:
 *
 *   Voice: Teja (recorded) · Pause between beats: 0.4 s
 *
 *   ## b1 · set up the problem
 *   Say: Think of a Kafka [topic] as a log.
 *   Show: one long log labelled with its topic.
 *   Facts: F2, F8
 */

export interface ScriptBeat {
  id: string;
  title: string;
  /** Spoken text, with [cue] markers. */
  say: string;
  show: string;
  facts: string[];
}

export interface Script {
  voice: string;
  /** True when a person records the narration instead of a TTS voice. */
  recorded: boolean;
  speed: number;
  /** Silence after each beat, in seconds. */
  pause: number;
  beats: ScriptBeat[];
}

export function parseScript(markdown: string): Script {
  const header = markdown.match(/^Voice:\s*(.+?)\s*·\s*(?:Speed:\s*([\d.]+)\s*·\s*)?Pause between beats:\s*([\d.]+)\s*s/m);
  if (!header) throw new Error('script.md needs a line like "Voice: af_heart · Speed: 1.0 · Pause between beats: 0.3 s"');
  const recorded = /\(recorded\)\s*$/.test(header[1]!);
  if (!recorded && header[2] === undefined) throw new Error("a TTS voice needs a Speed:, e.g. \"Speed: 1.0\"");

  const beats: ScriptBeat[] = [];
  for (const section of markdown.split(/^## /m).slice(1)) {
    const [heading = "", ...lines] = section.split("\n");
    const [id = "", title = ""] = heading.split("·").map((s) => s.trim());
    const field = (name: string) => lines.find((l) => l.startsWith(`${name}:`))?.slice(name.length + 1).trim() ?? "";
    const say = field("Say");
    if (!id || !say) throw new Error(`Beat "${heading.trim()}" needs an id and a Say: line`);
    const facts = field("Facts")
      .split(",")
      .map((f) => f.trim())
      .filter((f) => /^F\d+$/.test(f));
    beats.push({ id, title, say, show: field("Show"), facts });
  }

  const ids = new Set<string>();
  for (const b of beats) {
    if (ids.has(b.id)) throw new Error(`Beat id "${b.id}" is used twice`);
    ids.add(b.id);
  }
  return { voice: header[1]!, recorded, speed: Number(header[2] ?? 1), pause: Number(header[3]), beats };
}

/** Fact IDs defined in facts.md: the first cell of each table row, e.g. "| F3 | …". */
export function parseFactIds(markdown: string): Set<string> {
  return new Set([...markdown.matchAll(/^\|\s*(F\d+)\s*\|/gm)].map((m) => m[1]!));
}

/** Every fact a beat cites must exist in facts.md. */
export function checkFacts(script: Script, factIds: Set<string>): string[] {
  const issues: string[] = [];
  for (const beat of script.beats) {
    for (const f of beat.facts) if (!factIds.has(f)) issues.push(`${beat.id} cites ${f}, which isn't in facts.md`);
  }
  return issues;
}
