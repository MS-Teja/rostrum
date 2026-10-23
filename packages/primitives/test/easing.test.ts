import { describe, expect, it } from "vitest";
import { cubicBezier, ease, spring } from "../src/time/easing";

describe("cubicBezier", () => {
  it("matches CSS `ease` at the midpoint", () => {
    expect(cubicBezier(0.25, 0.1, 0.25, 1)(0.5)).toBeCloseTo(0.8024, 4);
  });

  it("is the identity for a straight curve", () => {
    const straight = cubicBezier(0, 0, 1, 1);
    for (const x of [0.1, 0.33, 0.5, 0.9]) expect(straight(x)).toBeCloseTo(x, 6);
  });

  it("clamps outside [0, 1]", () => {
    expect(ease.move(-1)).toBe(0);
    expect(ease.move(2)).toBe(1);
  });

  it("keeps the role curves monotonic", () => {
    for (const curve of [ease.enter, ease.exit, ease.move]) {
      let prev = 0;
      for (let i = 1; i <= 100; i++) {
        const y = curve(i / 100);
        expect(y).toBeGreaterThanOrEqual(prev - 1e-9);
        prev = y;
      }
    }
  });
});

describe("spring", () => {
  const samples = (s: { at(t: number): number }, from: number, to: number) =>
    Array.from({ length: 400 }, (_, i) => s.at(from + ((to - from) * i) / 399));

  it("overshoots when underdamped, then stays within epsilon after settling", () => {
    const s = spring({ response: 0.5, damping: 0.5 });
    expect(s.at(0)).toBe(0);
    expect(Math.max(...samples(s, 0, s.settle))).toBeGreaterThan(1);
    for (const y of samples(s, s.settle, s.settle * 3)) expect(Math.abs(1 - y)).toBeLessThanOrEqual(1e-3 + 1e-9);
  });

  it("never overshoots when critically damped", () => {
    const s = spring({ response: 0.4, damping: 1 });
    const ys = samples(s, 0, s.settle * 2);
    for (let i = 1; i < ys.length; i++) expect(ys[i]!).toBeGreaterThanOrEqual(ys[i - 1]! - 1e-12);
    expect(Math.max(...ys)).toBeLessThanOrEqual(1);
    expect(1 - s.at(s.settle)).toBeCloseTo(1e-3, 6);
  });

  it("works as an easing over its settle time", () => {
    const s = spring({ response: 0.5, damping: 0.8 });
    expect(s.ease(0)).toBe(0);
    expect(s.ease(1)).toBe(1);
  });

  it("rejects impossible settings", () => {
    expect(() => spring({ response: 0, damping: 0.5 })).toThrow(RangeError);
    expect(() => spring({ response: 0.5, damping: 1.5 })).toThrow(RangeError);
  });
});
