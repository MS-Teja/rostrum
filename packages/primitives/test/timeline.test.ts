import { describe, expect, it } from "vitest";
import { ease } from "../src/time/easing";
import { progress, started } from "../src/time/timeline";

describe("progress", () => {
  const span = { start: 2, duration: 1 };

  it("is 0 before the span and 1 after it", () => {
    expect(progress(span, 1)).toBe(0);
    expect(progress(span, 2)).toBe(0);
    expect(progress(span, 3)).toBe(1);
    expect(progress(span, 10)).toBe(1);
  });

  it("is linear by default and eased when asked", () => {
    expect(progress(span, 2.5)).toBeCloseTo(0.5);
    expect(progress({ ...span, ease: ease.enter }, 2.5)).toBeGreaterThan(0.5);
  });

  it("treats a zero-length span as instant", () => {
    expect(progress({ start: 1, duration: 0 }, 1.0001)).toBe(1);
  });
});

describe("started", () => {
  it("returns only spans that have begun, in start order", () => {
    const spans = [
      { id: "b", start: 2, duration: 1 },
      { id: "a", start: 1, duration: 1 },
      { id: "c", start: 5, duration: 1 },
    ];
    const at = started(spans, 2.5);
    expect(at.map((x) => x.span.id)).toEqual(["a", "b"]);
    expect(at.map((x) => x.p)).toEqual([1, 0.5]);
  });
});
