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

describe("minimum-jerk and monotone curves", () => {
  it("two keys give exactly the minimum-jerk ease; more keys stay continuous to the 4th derivative", () => {
    const got = py(`
import json
from cine.core.curve import Curve
from cine.core import ease as E
two = Curve(keys=[(0, 0), (2, 1)], interp="minjerk")
err2 = max(abs(two(t / 50) - E.minjerk(t / 100)) for t in range(101))
c = Curve(keys=[(0, 0), (1.5, 2), (4, 3), (5, 6), (8, 6.5)], interp="minjerk")
ts = [k[0] for k in c.keys]
def deriv(seg, n, u):  # n-th time derivative of segment seg at local u, from its coefficients
    co, h = c._c[0][seg], ts[seg + 1] - ts[seg]
    tot = 0.0
    for j in range(n, 6):
        f = 1.0
        for q in range(j - n + 1, j + 1):
            f *= q
        tot += co[j] * f * u ** (j - n)
    return tot / h ** n
jumps = [abs(deriv(i - 1, n, 1.0) - deriv(i, n, 0.0)) for i in (1, 2, 3) for n in (1, 2, 3, 4)]
ends = [abs(deriv(0, 1, 0.0)), abs(deriv(0, 2, 0.0)), abs(deriv(3, 1, 1.0)), abs(deriv(3, 2, 1.0))]
keys = [abs(c(t) - v) for t, v in c.keys]
print(json.dumps([err2, max(jumps), max(ends), max(keys)]))`);
    const [err2, jump, ends, keys] = got;
    expect(err2).toBeLessThan(1e-9);
    expect(jump).toBeLessThan(1e-8);
    expect(ends).toBeLessThan(1e-9);
    expect(keys).toBeLessThan(1e-9);
  });

  it("a stop key brings the curve to rest; a monotone curve never overshoots its keys", () => {
    const [stopSpeed, lo, hi, mjLo] = py(`
import json
from cine.core.curve import Curve
s = Curve(keys=[(0, 0), (1, 1), (2, 3)], interp="minjerk", stops=[1])
keys = [(0, 0), (4.5, 0), (9, 1), (14, 0), (20, 0)]
m = Curve(keys=keys, interp="monotone")
mj = Curve(keys=keys, interp="minjerk")
v = [m(t / 30) for t in range(601)]
print(json.dumps([abs(s(1.0005) - s(0.9995)) / 1e-3, min(v), max(v), min(mj(t / 30) for t in range(601))]))`);
    expect(stopSpeed).toBeLessThan(1e-3);
    expect(lo).toBeGreaterThanOrEqual(-1e-12);
    expect(hi).toBeLessThanOrEqual(1 + 1e-12);
    expect(mjLo).toBeLessThan(-0.01); // why weights and screen offsets use monotone
  });

  it("round-trips keys, interpolation and stops through JSON", () => {
    const same = py(`
import json
from cine.core.curve import Curve
c = Curve(keys=[(0, [0, 0]), (1, [1, 2]), (3, [0, 5])], interp="minjerk", stops=[1])
d = Curve.from_json(json.loads(json.dumps(c.to_json())))
print(json.dumps(all(abs(a - b) < 1e-12 for t in range(31) for a, b in zip(c(t / 10), d(t / 10)))))`);
    expect(same).toBe(true);
  });
});

describe("camera rig", () => {
  const journey = `
import json, math
from cine.camera import rig as R
from cine.core import kinematics as K, qa as Q
spin = lambda t: [0.3 * math.cos(t), 0.3 * math.sin(t), 0.0]
rig = R.Rig({"craft": [0, 0, 0], "part": spin, "far": [0, 40, 5]}, fps=30)
rig.key(0, look="craft", dist=30, az=140, el=6, lens=40, screen=(-1/6, 0))
rig.key(4.5, dist=24, az=128, el=9)
rig.key(9, look="part", dist=4, az=80, el=28, screen=(0, 0))
rig.key(14, look="craft", dist=8, az=45, el=22)
rig.key(20, dist=14, az=20, el=-5, lens=35, screen=(-0.2, 0))
cam = rig.sample(0, 20)
k = K.measure(cam["t"], cam["pos"], cam["aim"], cam["lens"])
`;

  it("passes through every key: position relative to what it looks at, lens and screen place", () => {
    const err = py(journey + `
worst = 0.0
for key in rig.keys:
    i = int(round(key["t"] * 30))
    piv = R._pt(rig.subjects[key["look"]], key["t"])
    want = [piv[j] + R.direction(key["az"], key["el"])[j] * key["dist"] for j in range(3)]
    worst = max(worst, K.norm(K.sub(cam["pos"][i], want)), abs(cam["lens"][i] - key["lens"]))
    s = K.screen(cam["pos"][i], cam["aim"][i], cam["lens"][i], piv)
    worst = max(worst, abs(s[0] - key["screen"][0]), abs(s[1] - key["screen"][1]))
print(json.dumps(worst))`);
    expect(err).toBeLessThan(1e-6);
  });

  it("a chained journey through five keys raises no flags and starts and ends at rest", () => {
    const [flags, e0, e1, peak] = py(journey + `
print(json.dumps([[f[0] for f in Q.flags(k)], k["energy"][1], k["energy"][-2], max(k["energy"])]))`);
    expect(flags).toEqual([]);
    expect(e0).toBeLessThan(0.02 * peak);
    expect(e1).toBeLessThan(0.05 * peak);
  });

  it("frames two subjects at the screen places asked for", () => {
    const err = py(`
import json
from cine.camera import rig as R
az, el, err = R.frame_two([0, 0, 0.6], [11, 44, 8], (-0.2, -0.04), (0.25, 0.1), dist=14, lens=35)
print(json.dumps(err))`);
    expect(err).toBeLessThan(1e-3);
  });
});
