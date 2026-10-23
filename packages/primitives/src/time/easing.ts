export type Easing = (x: number) => number;

export const linear: Easing = (x) => x;

/**
 * CSS-compatible cubic-bezier easing. Solves x(t) for t with Newton–Raphson,
 * falling back to bisection where the slope is too flat, then returns y(t).
 */
export function cubicBezier(x1: number, y1: number, x2: number, y2: number): Easing {
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;

  const sampleX = (t: number) => ((ax * t + bx) * t + cx) * t;
  const sampleY = (t: number) => ((ay * t + by) * t + cy) * t;
  const slopeX = (t: number) => (3 * ax * t + 2 * bx) * t + cx;

  const solveT = (x: number) => {
    let t = x;
    for (let i = 0; i < 8; i++) {
      const err = sampleX(t) - x;
      if (Math.abs(err) < 1e-7) return t;
      const d = slopeX(t);
      if (Math.abs(d) < 1e-6) break;
      t -= err / d;
    }
    let lo = 0;
    let hi = 1;
    t = x;
    while (lo < hi) {
      const sx = sampleX(t);
      if (Math.abs(sx - x) < 1e-7) return t;
      if (x > sx) lo = t;
      else hi = t;
      if (hi - lo < 1e-9) break;
      t = (lo + hi) / 2;
    }
    return t;
  };

  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    return sampleY(solveT(x));
  };
}

/** Easing by role, so scenes stay consistent. */
export const ease = {
  /** Things arriving: fast start, long gentle settle (expo-out). */
  enter: cubicBezier(0.16, 1, 0.3, 1),
  /** Things leaving: slow start, quick finish (expo-in). */
  exit: cubicBezier(0.7, 0, 0.84, 0),
  /** Things moving between two places (cubic in-out). */
  move: cubicBezier(0.65, 0, 0.35, 1),
  /** Steady flows such as data streams. */
  linear,
} as const;

export interface SpringOptions {
  /** Period of the undamped oscillation in seconds; smaller is snappier. */
  response: number;
  /** Damping fraction in (0, 1]: 1 settles without overshoot, lower values bounce. */
  damping: number;
  /** Distance from the target that counts as settled. Default 0.001. */
  epsilon?: number;
}

export interface Spring {
  /** Position at `seconds` after release, moving from 0 towards 1 (may overshoot). */
  at(seconds: number): number;
  /** Seconds until the motion stays within `epsilon` of the target. */
  settle: number;
  /** The spring as an easing over its settle time, for use in a Span. */
  ease: Easing;
}

/** A spring released at rest, parameterised like SwiftUI's `.spring(response:dampingFraction:)`. */
export function spring({ response, damping, epsilon = 1e-3 }: SpringOptions): Spring {
  if (!(response > 0)) throw new RangeError("spring response must be > 0");
  if (!(damping > 0 && damping <= 1)) throw new RangeError("spring damping must be in (0, 1]");

  const w0 = (2 * Math.PI) / response;
  let at: (s: number) => number;
  let settle: number;

  if (damping < 1) {
    const wd = w0 * Math.sqrt(1 - damping * damping);
    const k = (damping * w0) / wd;
    at = (s) => (s <= 0 ? 0 : 1 - Math.exp(-damping * w0 * s) * (Math.cos(wd * s) + k * Math.sin(wd * s)));
    // The oscillation's envelope is e^(-ζω₀t)/√(1-ζ²); settle when it drops below epsilon.
    settle = Math.log(1 / (epsilon * Math.sqrt(1 - damping * damping))) / (damping * w0);
  } else {
    at = (s) => (s <= 0 ? 0 : 1 - Math.exp(-w0 * s) * (1 + w0 * s));
    // Critically damped: monotonic, so find where the remaining distance hits epsilon.
    let lo = 0;
    let hi = 1;
    while (1 - at(hi) > epsilon) hi *= 2;
    for (let i = 0; i < 60; i++) {
      const mid = (lo + hi) / 2;
      if (1 - at(mid) > epsilon) lo = mid;
      else hi = mid;
    }
    settle = hi;
  }

  return { at, settle, ease: (x) => (x >= 1 ? 1 : at(x * settle)) };
}
