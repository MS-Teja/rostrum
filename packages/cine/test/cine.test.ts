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

describe("composition", () => {
  it("measures a box's size, centre, cut and cover from a known camera", () => {
    const got = py(`
import json, math
from cine.core import compose as C, shape as S, kinematics as K
pts = S.box([-1, -1, -1], [1, 1, 1])          # a 2 m cube at the origin
lens = 36.0                                    # hfov = 2 atan(18/36) -> half width tan = 0.5
d = 10.0
pos, aim = [0, -d, 0], [0, 0, 0]
m = C.measure_points(pts, pos, aim, lens)
# the near face (y = -1) is 9 m away: half width there = 9 * 0.5 = 4.5 m, so 2 m spans 2/9 of the width
w_expect = 2 / 9
h_expect = 2 / (9 * 0.5 / (16 / 9)) / 2
# shift the aim so the cube sits half out of frame on the right
off = C.measure_points(pts, pos, [-0.5 * 2 * d * 0.5 + 0.0, 0, 0], lens)
print(json.dumps([m["w"], w_expect, m["h"], h_expect, m["cx"], m["out"], m["cover"], m["size"], C.size_name(m["size"]), off["cx"], off["out"]]))`);
    const [w, wExpect, h, hExpect, cx, out, cover, size, name, offCx, offOut] = got;
    expect(w).toBeCloseTo(wExpect, 6);
    expect(h).toBeCloseTo(hExpect, 6);
    expect(cx).toBeCloseTo(0, 9);
    expect(out).toBe(0);
    expect(cover).toBeGreaterThan(0.9 * w * h);
    expect(size).toBeCloseTo(Math.max(w, h), 9);
    expect(name).toBe("medium wide");
    expect(offCx).toBeGreaterThan(0.4);
    expect(offOut).toBeGreaterThan(0.2);
  });

  it("flags a grazing edge, a dominant neighbour and a camera inside a shape; stays quiet on a clean frame", () => {
    const got = py(`
import json
from cine.core.curve import Curve, Motion
from cine.core import compose as C, shape as S
def scene(cam_pos, aim, part_size=0.3):
    m = Motion("t", 0, 1, 30)
    m.channels["cam.pos"] = Curve(keys=[(0, cam_pos), (1, cam_pos)], interp="linear")
    m.channels["cam.aim"] = Curve(keys=[(0, aim), (1, aim)], interp="linear")
    m.channels["cam.lens"] = Curve(keys=[(0, 35.0), (1, 35.0)], interp="linear")
    m.channels["cam.key.look.part"] = Curve(keys=[(0, 1.0), (1, 1.0)], interp="linear")
    m.shapes = {"part": {"points": S.box([-part_size] * 3, [part_size] * 3)},
                "machine": {"points": S.box([-3, 1, -2], [3, 3, 2]), "role": "context"}}
    return sorted({f[0] for f in C.flags(m)})
clean = scene([0, -12, 0], [0, 0, 0], part_size=1.2)
dominant = scene([0, -5, 0], [0, 0, 0])
graze = scene([0, -8, 0], [3.0, 0, 0], part_size=1.2)
inside = scene([0, 2, 0], [0, 0, 0])
print(json.dumps({"clean": clean, "dominant": dominant, "graze": graze, "inside": inside}))`);
    expect(got.clean).toEqual([]);
    expect(got.dominant).toContain("dominant");
    expect(got.graze).toContain("edge");
    expect(got.inside).toContain("near");
  });

  it("sets up a shot from intent: the asked size, third and angle", () => {
    const got = py(`
import json
from cine.camera import rig as R, shot as SH
from cine.core import shape as S, compose as C
pts = S.box([-1, -0.5, -0.5], [1, 0.5, 0.5])
rig = R.Rig({"box": [0, 0, 0]}, fps=30)
F = SH.Framer(rig, {"box": pts}, facing={"box": [1, 0, 0]})
out = []
for size, side, angle in (("medium wide", "left third", "low"), ("close", "centre", "eye"), ("wide", "right third", "high")):
    k, m = F.shot(len(out) * 2.0, "box", size, angle=angle, side=side, lens=35, view="three-quarter")
    lo, hi = C.size_band(size)
    out.append([C.size_name(m["size"]) == size, abs(m["cx"] - SH.SIDES[side]), k["el"] == SH.ANGLES[angle]])
cam = rig.sample(0, 4)
print(json.dumps({"checks": out, "shots": len(cam["shots"]), "intent": cam["shots"][0]["size"]}))`);
    for (const [sizeOk, cxErr, angleOk] of got.checks) {
      expect(sizeOk).toBe(true);
      expect(cxErr).toBeLessThan(1e-3);
      expect(angleOk).toBe(true);
    }
    expect(got.shots).toBe(3);
    expect(got.intent).toBe("medium wide");
  });
});

describe("glide and planned looks", () => {
  it("a rest-to-rest glide peaks at 1/(1-r) of its average speed, below minimum-jerk's 1.875", () => {
    const [mj, gl] = py(`
import json
from cine.core.curve import Curve
def peak(c):
    vs = [(c((i + 1) / 300) - c(i / 300)) * 300 for i in range(300)]
    return max(vs)
print(json.dumps([peak(Curve(keys=[(0, 0), (1, 1)], interp="monotone")), peak(Curve(keys=[(0, 0), (1, 1)], interp="monotone", glide=0.3))]))`);
    expect(mj).toBeCloseTo(1.875, 2);
    expect(gl).toBeCloseTo(1 / 0.7, 2);
  });

  it("judges a still by its planned look: a dark subject passes low-key, fails normal", () => {
    const got = py(`
import json
from cine.core import look as L
m = {"subject_visible": True, "median": 0.06, "p10": 0.01, "p90": 0.25, "spread": 0.24, "clipped": 0.0, "crushed": 0.22, "background": 0.01, "contrast": 3.0}
print(json.dumps({"normal": [k for k, _ in L.flags(m, "normal")], "low": [k for k, _ in L.flags(m, "low-key")],
                  "plan": L.planned([{"t": 9.4, "subject": "thrusters", "look": "low-key"}, {"t": 15, "subject": "dish"}], "thrusters", 10.1)}))`);
    expect(got.normal).toContain("murky");
    expect(got.low).toEqual([]);
    expect(got.plan).toBe("low-key");
  });
});

describe("the voice drives the camera", () => {
  it("finds words and phrases, and reads a faster stretch of speech as a faster pace", () => {
    const got = py(`
import json
from cine.core.voice import Voice
words = []
t = 0.0
for i in range(8):            # slow: a word every 0.6 s
    words.append({"text": f"slow{i}", "start": t, "end": t + 0.4}); t += 0.6
for i in range(16):           # fast: a word every 0.25 s
    words.append({"text": f"fast{i}", "start": t, "end": t + 0.2}); t += 0.25
words.append({"text": "tiny", "start": t, "end": t + 0.2}); words.append({"text": "drift.", "start": t + 0.25, "end": t + 0.5})
v = Voice(words)
times = [i / 30 for i in range(int(t * 30))]
p = v.pace(times)
print(json.dumps({"phrase": v.at("tiny drift"), "end": v.at("drift", edge="end"), "slow": p[int(2.0 * 30)], "fast": p[int(7.0 * 30)]}))`);
    expect(got.phrase).toBeCloseTo(8 * 0.6 + 16 * 0.25, 6);
    expect(got.fast).toBeGreaterThan(got.slow * 1.3);
  });

  it("scales the speed limits by the pace: the same move is too fast under a slow line, fine under a fast one", () => {
    const [slow, fast] = py(`
import json, math
from cine.core import kinematics as K, qa as Q
ts = [i / 30 for i in range(91)]
pos = [[0, -10 * math.exp(-0.3 * t), 1] for t in ts]   # a push at a steady zoom of 0.3/s
k = K.measure(ts, pos, [[0, 0, 1]] * len(ts), [35.0] * len(ts))
prof = {"fast_zoom": 0.3}
kinds = lambda sc: sorted({f[0] for f in Q.flags(k, prof, [sc] * len(ts))})
print(json.dumps([kinds(0.6), kinds(1.5)]))`);
    expect(slow).toContain("fast");
    expect(fast).not.toContain("fast");
  });

  it("a deliberate hold isn't a stop-start; a zigzag wanders; a small short move between holds fidgets", () => {
    const got = py(`
import json, math
from cine.core import kinematics as K, qa as Q
from cine.core.curve import Curve
ts = [i / 30 for i in range(301)]
def run(xs):
    pos = [[x, -10, 1] for x in xs]
    k = K.measure(ts, pos, [[x, 0, 1] for x in xs], [35.0] * len(ts))
    return sorted({f[0] for f in Q.flags(k)})
# move, hold 3 s, move on: the hold is a choice
c = Curve(keys=[(0, 0), (3, 4), (6, 4), (10, 8)], interp="monotone", stops=[3, 6])
hold = run([c(t) for t in ts])
# a zigzag: left, right, left within 3 s
zig = run([0.6 * math.sin(2 * math.pi * t / 1.6) for t in ts])
# a fidget: hold, a tiny 0.6 s nudge, hold
f = Curve(keys=[(0, 0), (4, 0), (4.6, 0.4), (10, 0.4)], interp="monotone", stops=[4, 4.6])
fid = run([f(t) for t in ts])
print(json.dumps({"hold": hold, "zig": zig, "fidget": fid}))`);
    expect(got.hold).not.toContain("hiccup");
    expect(got.zig).toContain("wander");
    expect(got.fidget).toContain("fidget");
  });

  it("a still hold doesn't move at all; a creeping hold moves slowly one way", () => {
    const got = py(`
import json
from cine.camera import rig as R, shot as SH
from cine.core import shape as S, kinematics as K
pts = S.box([-1, -0.5, -0.5], [1, 0.5, 0.5])
def build(**kw):
    rig = R.Rig({"box": [0, 0, 0]}, fps=30)
    F = SH.Framer(rig, {"box": pts})
    F.shot(0.0, "box", "medium wide", az=30, lens=35)
    F.hold(4.0, **kw)
    cam = rig.sample(0, 4)
    k = K.measure(cam["t"], cam["pos"], cam["aim"], cam["lens"])
    return max(k["energy"]), sum(1 for z in k["zoom"][1:-1] if z < -1e-6)
still, creep = build(), build(creep=0.1)
print(json.dumps({"still": still[0], "creep": creep[0], "creep_backwards": creep[1]}))`);
    expect(got.still).toBeLessThan(1e-9);
    expect(got.creep).toBeGreaterThan(0.005);
    expect(got.creep).toBeLessThan(0.1);
    expect(got.creep_backwards).toBe(0);
  });
});

describe("zoom-through", () => {
  it("hands the aim across scales in proportion to the view, so neither subject is flung out", () => {
    const [through, plain, lift] = py(`
import json
from cine.camera import rig as R
from cine.core import kinematics as K, qa as Q
def run(motive):
    rig = R.Rig({"near": [0, 0, 0], "far": [1e5, 0, 0]}, fps=30)
    rig.key(0, look="near", dist=50, az=0, el=10, lens=35, stop=True, intent={"motive": "hold"})
    rig.key(1, stop=True, intent={"motive": "hold"})
    rig.key(5, look="far", dist=3e5, az=0, el=10, stop=True, intent={"motive": motive})
    cam = rig.sample(0, 5)
    k = K.measure(cam["t"], cam["pos"], cam["aim"], cam["lens"])
    return max(k["sweep"]), cam["spans"]
a, spans = run("zoom-through")
b, _ = run("relate")
class M: pass
m = M(); m.spans = spans; m.channels = {}
_, _, zs = Q.voice_args(m, [3.0], {"fast_zoom": 0.6})
print(json.dumps([a, b, zs[0]]))`);
    expect(through).toBeLessThan(1.5);
    expect(plain).toBeGreaterThan(through * 5);
    expect(lift).toBeCloseTo(3.0 / 0.6, 6);
  });
});

describe("following a moving subject", () => {
  it("reads as still when the camera keeps its distance from the subject it follows", () => {
    const got = py(`
import json
from cine.core import kinematics as K
ts = [i / 30 for i in range(61)]
subj = [[3.0 * t, 2.0 * t, 0.0] for t in ts]          # moving along and across the view
pos = [[s[0], s[1] - 10.0, s[2]] for s in subj]        # the camera 10 behind it, keeping station
aim = [list(s) for s in subj]
lens = [35.0] * len(ts)
plain = K.measure(ts, pos, aim, lens)
follow = K.measure(ts, pos, aim, lens, pivot=subj)
mx = lambda k, d: max(abs(x) for x in d[k][2:-2])
print(json.dumps({"zoom_plain": mx("zoom", plain), "sweep_plain": mx("sweep", plain), "zoom_follow": mx("zoom", follow), "sweep_follow": mx("sweep", follow)}))`);
    expect(got.zoom_plain).toBeGreaterThan(0.1);
    expect(got.sweep_plain).toBeGreaterThan(0.1);
    expect(got.zoom_follow).toBeLessThan(1e-9);
    expect(got.sweep_follow).toBeLessThan(1e-9);
  });
});

describe("actor visibility", () => {
  it("flags an actor out of frame, behind the camera, out at its word, or too small; passes a visible one", () => {
    const got = py(`
import json
from cine.core import actors as A
from cine.core import path as P
from cine.core.curve import Curve, Motion
m = Motion("m", 0, 2, 30)
m.channels = {"cam.pos": Curve(keys=[(0, [0, -10, 0]), (2, [0, -10, 0])], interp="linear"),
              "cam.aim": Curve(keys=[(0, [0, 0, 0]), (2, [0, 0, 0])], interp="linear"),
              "cam.lens": Curve(keys=[(0, 35.0), (2, 35.0)], interp="linear")}
m.actors = {
    "seen": A.actor(P.track([(-1, 0, 0), (1, 0, 0)], 0.0, 2.0), size=0.1, word=1.0),
    "leaves": A.actor(P.track([(0, 0, 0), (80, 0, 0)], 0.0, 2.0), size=0.1),
    "enters": A.actor(P.track([(-20, 0, 0), (0, 0, 0)], 0.0, 2.0), size=0.1, word=1.9),
    "behind": A.actor(P.track([(0, -20, 0), (1, -20, 0)], 0.0, 2.0), size=0.1),
    "late": A.actor(P.track([(0, 0, 0), (0.5, 0, 0), (30, 0, 0)], 0.0, 2.0), size=0.1, word=1.9),
    "speck": A.actor(P.track([(0, 0, 0), (0.1, 0, 0)], 0.0, 2.0), size=0.002),
}
print(json.dumps([[f[0], f[2]] for f in A.flags(m)]))`);
    const by = (name: string) => got.filter(([, msg]: string[]) => msg.startsWith(name + " ")).map(([k]: string[]) => k);
    expect(by("seen")).toEqual([]);
    expect(by("leaves")).toEqual(["unseen"]);
    expect(by("enters")).toEqual([]);
    expect(by("behind")).toEqual(["unseen"]);
    expect(by("late")).toEqual(["unseen"]);
    expect(got.find(([, msg]: string[]) => msg.startsWith("late "))[1]).toMatch(/out of frame at its word/);
    expect(by("speck")).toEqual(["tiny"]);
  });
});

describe("transitions", () => {
  it("joins clips overlapping by each transition, video and audio, and checks a match cut", () => {
    const got = py(`
import json, os, subprocess, tempfile
from cine import transition as T
d = tempfile.mkdtemp()
def clip(name, colour, secs, a0=0.7, a1=1.3):  # a tone from a0 to a1 only: silent handles either side
    p = os.path.join(d, name)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color={colour}:s=64x36:d={secs}:r=30",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}", "-af", f"volume='between(t,{a0},{a1})':eval=frame",
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", p], check=True)
    return p
a, b, c = clip("a.mp4", "black", 2), clip("b.mp4", "white", 2), clip("c.mp4", "gray", 2)
out, length = T.join([(a, None), (b, T.dissolve(0.5)), (c, T.light(0.6, centre=(0.3, 0.5)))], os.path.join(d, "out.mp4"))
real = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)
from cine.core.curve import Curve, Motion
from cine.core import shape as S
def scene(cam_y):
    m = Motion("m", 0, 1, 30)
    m.channels = {"cam.pos": Curve(keys=[(0, [0, cam_y, 0]), (1, [0, cam_y, 0])], interp="linear"),
                  "cam.aim": Curve(keys=[(0, [0, 0, 0]), (1, [0, 0, 0])], interp="linear"),
                  "cam.lens": Curve(keys=[(0, 35.0), (1, 35.0)], interp="linear")}
    m.shapes = {"box": {"points": S.box([-1] * 3, [1] * 3)}}
    return m
same, _ = T.match(scene(-10), 1.0, "box", scene(-10.2), 0.0, "box")
off, _ = T.match(scene(-10), 1.0, "box", scene(-16), 0.0, "box")
print(json.dumps({"length": length, "real": real, "same": same, "off": off}))`);
    expect(got.length).toBeCloseTo(2 + 2 - 0.5 + 2 - 0.6, 3);
    expect(Math.abs(got.real - got.length)).toBeLessThan(0.1);
    expect(got.same).toBe(true);
    expect(got.off).toBe(false);
  });

  it("refuses voice under a transition; lays each clip's audio at its start at full level, never crossfaded", () => {
    const got = py(`
import json, os, subprocess, tempfile
from cine import transition as T
d = tempfile.mkdtemp()
def clip(name, a0, a1, secs=2):
    p = os.path.join(d, name)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=gray:s=64x36:d={secs}:r=30",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}", "-af", f"volume='between(t,{a0},{a1})':eval=frame",
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", p], check=True)
    return p
talky = clip("talky.mp4", 0.5, 2.0)      # speaks to its last frame
early = clip("early.mp4", 0.05, 0.35)    # speaks from its first frame
quiet = clip("quiet.mp4", 0.7, 1.3)
try:
    T.join([(talky, None), (quiet, T.dissolve(0.5))], os.path.join(d, "x.mp4"))
    refused = ""
except ValueError as e:
    refused = str(e)
problems = T.check_handles([(quiet, None), (early, T.dissolve(0.5))])
# forced through: the early clip's voice, under the overlap, still plays at full level
out, _ = T.join([(quiet, None), (early, T.dissolve(0.5))], os.path.join(d, "forced.mp4"), force=True)
alone = T.level_db(early, 0.1, 0.2)
joined = T.level_db(out, 1.5 + 0.1, 0.2)
print(json.dumps({"refused": refused, "problems": problems, "alone": alone, "joined": joined}))`);
    expect(got.refused).toMatch(/voice inside the dissolve/);
    expect(got.refused).toMatch(/last 0\.50 s of talky\.mp4/);
    expect(got.problems.length).toBe(1);
    expect(got.problems[0]).toMatch(/first 0\.50 s of early\.mp4/);
    expect(Math.abs(got.joined - got.alone)).toBeLessThan(1.0);
  });

  it("muxes a scene's frames with its take placed at the in-handle", () => {
    const got = py(`
import json, os, subprocess, tempfile
from cine import transition as T
d = tempfile.mkdtemp()
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=gray:s=64x36:d=1.0:r=30", os.path.join(d, "f_%04d.png")], check=True)
take = os.path.join(d, "take.wav")
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.4", take], check=True)
out = T.mux(os.path.join(d, "f_%04d.png"), 30, 1, take, os.path.join(d, "s.mp4"), offset=0.4)
print(json.dumps({"before": T.level_db(out, 0.0, 0.33), "after": T.level_db(out, 0.45, 0.3), "length": T._duration(out)}))`);
    expect(got.before).toBeLessThan(-60);
    expect(got.after).toBeGreaterThan(-30);
    expect(got.length).toBeGreaterThan(0.95);
    expect(got.length).toBeLessThan(1.1);
  });
});
