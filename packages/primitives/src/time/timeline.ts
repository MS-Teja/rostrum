import { linear, type Easing } from "./easing";

/** Something that happens over time, in seconds of the composition. */
export interface Span {
  start: number;
  duration: number;
  ease?: Easing;
}

/** Eased progress of `span` at time `t`: 0 before it starts, 1 once it's done. */
export function progress(span: Span, t: number): number {
  if (t <= span.start) return 0;
  if (span.duration <= 0 || t >= span.start + span.duration) return 1;
  return (span.ease ?? linear)((t - span.start) / span.duration);
}

export const lerp = (a: number, b: number, p: number): number => a + (b - a) * p;

/** Spans that have started by time `t`, in start order, each with its eased progress. */
export function started<T extends Span>(spans: readonly T[], t: number): Array<{ span: T; p: number }> {
  return spans
    .filter((s) => s.start <= t)
    .sort((a, b) => a.start - b.start)
    .map((span) => ({ span, p: progress(span, t) }));
}
