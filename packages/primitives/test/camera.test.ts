import { describe, expect, it } from "vitest";
import { between, cameraAt, fit, type Rect } from "../src/primitives/camera";

const frame = { x: 0, y: 0, w: 1920, h: 1080 };
const aspect = 1920 / 1080;

describe("fit", () => {
  it("keeps the frame's aspect ratio and centres the region", () => {
    const view = fit({ x: 100, y: 100, w: 200, h: 200 }, aspect, 0);
    expect(view.w / view.h).toBeCloseTo(aspect);
    expect(view.x + view.w / 2).toBeCloseTo(200);
    expect(view.y + view.h / 2).toBeCloseTo(200);
    expect(view.h).toBeCloseTo(200); // a square region is limited by height
  });

  it("adds padding on each side", () => {
    const region = { x: 0, y: 0, w: 1000, h: 100 };
    expect(fit(region, aspect, 0.1).w).toBeCloseTo(1200);
  });
});

describe("between", () => {
  it("zooms geometrically: halfway from 1× to 4× is 2×", () => {
    const wide: Rect = { x: 0, y: 0, w: 1600, h: 900 };
    const close: Rect = { x: 600, y: 337.5, w: 400, h: 225 };
    expect(between(wide, close, 0.5).w).toBeCloseTo(800);
  });

  it("returns the endpoints at 0 and 1", () => {
    const a = { x: 0, y: 0, w: 100, h: 50 };
    const b = { x: 40, y: 10, w: 20, h: 10 };
    expect(between(a, b, 0)).toEqual(a);
    const end = between(a, b, 1);
    for (const k of ["x", "y", "w", "h"] as const) expect(end[k]).toBeCloseTo(b[k]);
  });
});

describe("cameraAt", () => {
  const region = { x: 800, y: 400, w: 320, h: 180 };
  const events = [{ at: 2, region, duration: 1 }];

  it("holds the initial view until the first move", () => {
    expect(cameraAt(events, 1.9, frame, aspect)).toEqual(frame);
  });

  it("frames the region once the move is done", () => {
    const view = cameraAt(events, 5, frame, aspect);
    const target = fit(region, aspect);
    for (const k of ["x", "y", "w", "h"] as const) expect(view[k]).toBeCloseTo(target[k]);
  });

  it("chains moves from wherever the camera is", () => {
    const back = [...events, { at: 4, region: { x: 0, y: 0, w: 1920, h: 1080 }, padding: 0, duration: 1 }];
    const view = cameraAt(back, 10, frame, aspect);
    for (const k of ["x", "y", "w", "h"] as const) expect(view[k]).toBeCloseTo(frame[k]);
  });
});
