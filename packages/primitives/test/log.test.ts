import { describe, expect, it } from "vitest";
import { logStateAt, type LogEvent } from "../src/primitives/log";

const rec = (id: string) => ({ id, label: id });

describe("logStateAt", () => {
  const events: LogEvent[] = [
    { type: "append", at: 1, record: rec("a") },
    { type: "append", at: 2, record: rec("b") },
    { type: "append", at: 3, record: rec("c") },
  ];

  it("assigns offsets in append order and shows only what has arrived", () => {
    const s = logStateAt(events, 2.1);
    expect(s.cells.map((c) => [c.record.id, c.offset])).toEqual([
      ["a", 0],
      ["b", 1],
    ]);
    expect(s.cells[0]!.shown).toBe(1);
    expect(s.cells[1]!.shown).toBeGreaterThan(0);
    expect(s.cells[1]!.shown).toBeLessThan(1);
  });

  it("keeps offsets fixed even when events are listed out of order", () => {
    const shuffled = [events[2]!, events[0]!, events[1]!];
    expect(logStateAt(shuffled, 10).cells.map((c) => c.offset)).toEqual([0, 1, 2]);
  });

  it("introduces a reader where it starts, then glides it to new offsets", () => {
    const withReader: LogEvent[] = [
      ...events,
      { type: "read", at: 4, reader: "billing", offset: 0 },
      { type: "read", at: 6, reader: "billing", offset: 2, duration: 1 },
    ];
    expect(logStateAt(withReader, 5).readers).toEqual([{ name: "billing", position: 0, shown: 1 }]);
    const mid = logStateAt(withReader, 6.5).readers[0]!;
    expect(mid.position).toBeGreaterThan(0);
    expect(mid.position).toBeLessThan(2);
    expect(logStateAt(withReader, 8).readers[0]!.position).toBe(2);
  });

  it("expires old records without renumbering the rest", () => {
    const expiring: LogEvent[] = [...events, { type: "expire", at: 5, before: 2 }];
    const s = logStateAt(expiring, 9);
    expect(s.cells.map((c) => [c.offset, c.gone])).toEqual([
      [0, 1],
      [1, 1],
      [2, 0],
    ]);
  });

  it("is a pure function of time", () => {
    expect(logStateAt(events, 2.5)).toEqual(logStateAt(events, 2.5));
  });
});
