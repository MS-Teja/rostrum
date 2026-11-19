import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// cine's core is plain Python with no dependencies, so plain python3 runs it.
const CINE = join(import.meta.dirname, "..");
const py = (code: string) =>
  JSON.parse(
    execFileSync(process.env.ROSTRUM_PYTHON ?? "python3", ["-c", code], {
      cwd: CINE,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }),
  );

describe("easing", () => {
  it("minjerk starts and ends at rest, and every ease goes 0 -> 1", () => {
    const got = py(`
import json
from cine.core import ease as E
names = ["linear", "minjerk", "ease_in", "ease_out", "scurve:0.25", "spring:0.4:1", "bezier:0.65:0:0.35:1"]
out = {}
for n in names:
    e = E.get(n)
    out[n] = [e(0.0), e(1.0), e.speed(0.0), e.speed(1.0), max(e(i / 200) for i in range(201))]
print(json.dumps(out))`);
    for (const [name, [y0, y1, , , ymax]] of Object.entries(got) as [string, number[]][]) {
      expect(y0, name).toBeCloseTo(0, 6);
      expect(y1, name).toBeCloseTo(1, 6);
      expect(ymax, name).toBeLessThan(1.0001);
    }
    expect(got["minjerk"][2]).toBeCloseTo(0, 9);
    expect(got["minjerk"][3]).toBeCloseTo(0, 9);
    expect(got["ease_in"][2]).toBeCloseTo(0, 9);
    expect(got["ease_out"][3]).toBeCloseTo(0, 9);
  });

  it("scurve cruises at constant speed between its ramps", () => {
    const [a, b, c] = py(`
import json
from cine.core import ease as E
e = E.scurve(0.25)
print(json.dumps([e.speed(0.3), e.speed(0.5), e.speed(0.7)]))`);
    expect(a).toBeCloseTo(b, 9);
    expect(b).toBeCloseTo(c, 9);
  });
});

describe("curves", () => {
  it("a spline is continuous in value, speed and acceleration through its keys, and rests at its ends", () => {
    const got = py(`
import json
from cine.core.curve import Curve
c = Curve(keys=[(0, 0.0), (1, 2.0), (2.5, 1.0), (4, 3.0)], interp="spline")
h = 1e-4
def d1(t): return (c(t + h) - c(t - h)) / (2 * h)
def d2(t): return (c(t + h) - 2 * c(t) + c(t - h)) / (h * h)
jumps = []
for k in (1.0, 2.5):
    e = 1e-5  # one-sided speeds at the key itself
    left, right = (c(k) - c(k - e)) / e, (c(k + e) - c(k)) / e
    jumps.append([abs(c(k - 1e-7) - c(k + 1e-7)), abs(left - right), abs(d2(k - 1e-3) - d2(k + 1e-3))])
print(json.dumps({"jumps": jumps, "end_speed": [(c(h) - c(0)) / h, (c(4) - c(4 - h)) / h], "hits": [c(1), c(2.5)]}))`);
    for (const [v, s, a] of got.jumps) {
      expect(v).toBeLessThan(1e-6);
      expect(s).toBeLessThan(1e-2);
      expect(a).toBeLessThan(0.05);
    }
    expect(Math.abs(got.end_speed[0])).toBeLessThan(1e-3);
    expect(Math.abs(got.end_speed[1])).toBeLessThan(1e-3);
    expect(got.hits[0]).toBeCloseTo(2, 9);
    expect(got.hits[1]).toBeCloseTo(1, 9);
  });

  it("vector curves and sampled curves evaluate component-wise, and round-trip through JSON", () => {
    const got = py(`
import json
from cine.core.curve import Curve, Motion
c = Curve(keys=[(0, [0, 0, 0]), (2, [2, 4, 6])], interp="linear")
s = Curve(samples=[0.0, 1.0, 4.0], fps=2, t0=10)
m = Motion("x", 0, 2)
m.channels["a"] = c
m.channels["b"] = s
m.save("/tmp/cine_test.motion.json")
m2 = Motion.load("/tmp/cine_test.motion.json")
print(json.dumps([c(1), s(10.25), m2.channels["a"](1), m2.channels["b"](10.75)]))`);
    expect(got[0]).toEqual([1, 2, 3]);
    expect(got[1]).toBeCloseTo(0.5, 9);
    expect(got[2]).toEqual([1, 2, 3]);
    expect(got[3]).toBeCloseTo(2.5, 9);
  });
});

describe("motion QA", () => {
  const run = (interp: string) =>
    py(`
import json, math
from cine.core.curve import Curve
from cine.core import kinematics as K, qa as Q
keys = []
for k in range(7):
    a = math.radians(-40 + k * 18)
    r = 12 - k * 0.8
    keys.append((k * 2.0, [r * math.cos(a), r * math.sin(a), 2 + 0.4 * k]))
pos = Curve(keys=keys, interp="${interp}")
ts = [i / 30 for i in range(361)]
k = K.measure(ts, [pos(t) for t in ts], [[0, 0, 1]] * len(ts), [35.0] * len(ts))
print(json.dumps(sorted({f[0] for f in Q.flags(k)}) + [len([f for f in Q.flags(k) if f[0] == "hiccup"])]))`);

  it("finds the stop-start in a move that settles at every key", () => {
    const got = run("eased");
    expect(got).toContain("hiccup");
    expect(got[got.length - 1]).toBeGreaterThanOrEqual(4);
  });

  it("stays silent on one continuous move", () => {
    expect(run("spline")).toEqual([0]);
  });

  it("splits measurement at a cut, so a scene change isn't read as a lurch", () => {
    const got = py(`
import json
from cine.core import kinematics as K, qa as Q
ts = [i / 30 for i in range(121)]
pos = [[0.01 * i, -10, 1] if i < 60 else [50 + 0.01 * i, 30, 5] for i in range(121)]
k = K.measure(ts, pos, [[0, 0, 1]] * 121, [35.0] * 121, cuts=[2.0])
print(json.dumps([f[0] for f in Q.flags(k)]))`);
    expect(got).not.toContain("jump");
    expect(got).not.toContain("jerk");
  });
});
