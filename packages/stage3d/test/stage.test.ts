import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { ease, spring } from "../../primitives/src/time/easing";

// The Python half of the stage runs inside Blender, but easing and timing use no bpy,
// so plain python3 can check them against the TypeScript originals.
const STAGE = join(import.meta.dirname, "..");
const python = (code: string) =>
  JSON.parse(
    execFileSync(process.env.ROSTRUM_PYTHON ?? "python3", ["-c", code], {
      cwd: STAGE,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }),
  );

const XS = Array.from({ length: 41 }, (_, i) => i / 40);

describe("Python easing", () => {
  it("matches the TypeScript curves at 41 points each", () => {
    const got = python(`
import json
from rostrum_stage.easing import ease, spring
xs = [i / 40 for i in range(41)]
s = spring(0.5, 0.7)
c = spring(0.4, 1.0)
print(json.dumps({
  "enter": [ease.enter(x) for x in xs],
  "exit": [ease.exit(x) for x in xs],
  "move": [ease.move(x) for x in xs],
  "spring": [s.ease(x) for x in xs],
  "critical": [c.ease(x) for x in xs],
  "settle": [s.settle, c.settle],
}))`);
    const s = spring({ response: 0.5, damping: 0.7 });
    const c = spring({ response: 0.4, damping: 1 });
    const want = {
      enter: XS.map(ease.enter),
      exit: XS.map(ease.exit),
      move: XS.map(ease.move),
      spring: XS.map(s.ease),
      critical: XS.map(c.ease),
    };
    for (const [name, values] of Object.entries(want)) {
      values.forEach((v, i) => expect(got[name][i], `${name} at ${XS[i]}`).toBeCloseTo(v, 9));
    }
    expect(got.settle[0]).toBeCloseTo(s.settle, 9);
    expect(got.settle[1]).toBeCloseTo(c.settle, 9);
  });
});

describe("Python timing", () => {
  it("puts a cue on the frame that shows it, rounding half up", () => {
    const got = python(`
import json
from rostrum_stage.timing import frame, cue_time
t = {"cues": [{"key": "b3:sendfile", "time": 12.34}], "beats": []}
print(json.dumps([frame(0), frame(1 / 30), frame(0.5 / 30), frame(0.49 / 30), frame(10, 24), cue_time(t, "b3:sendfile", 0.4)]))`);
    expect(got.slice(0, 5)).toEqual([1, 2, 2, 1, 241]);
    expect(got[5]).toBeCloseTo(12.74, 9);
  });

  it("names the known cues when one is missing", () => {
    expect(() =>
      python(`
from rostrum_stage.timing import cue_time
cue_time({"cues": [{"key": "b1:topic", "time": 1.0}], "beats": []}, "b9:nope")`),
    ).toThrow(/b1:topic/);
  });
});
