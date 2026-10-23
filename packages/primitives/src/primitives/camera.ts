import { ease } from "../time/easing";
import { lerp, progress } from "../time/timeline";

/** A rectangle in world coordinates (the large canvas the camera looks at). */
export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface CameraEvent {
  at: number;
  /** The region to frame. It's fitted to the frame's aspect ratio with `padding` around it. */
  region: Rect;
  /** Margin on each side, as a fraction of the region's size. Default 0.12. */
  padding?: number;
  duration?: number;
}

const DURATION = 1.2;

/** The view rectangle that shows `region` with padding, at the frame's aspect ratio. */
export function fit(region: Rect, aspect: number, padding = 0.12): Rect {
  const w = Math.max(region.w, region.h * aspect) * (1 + 2 * padding);
  const h = w / aspect;
  return { x: region.x + region.w / 2 - w / 2, y: region.y + region.h / 2 - h / 2, w, h };
}

/**
 * Pan the centre linearly but zoom geometrically: scale is perceived as a
 * ratio, so halfway between 1× and 4× should look like 2×, not 2.5×.
 */
export function between(a: Rect, b: Rect, p: number): Rect {
  const w = a.w * Math.pow(b.w / a.w, p);
  const h = a.h * Math.pow(b.h / a.h, p);
  const cx = lerp(a.x + a.w / 2, b.x + b.w / 2, p);
  const cy = lerp(a.y + a.h / 2, b.y + b.h / 2, p);
  return { x: cx - w / 2, y: cy - h / 2, w, h };
}

/** Where the camera looks at time `t`, starting from `initial`. */
export function cameraAt(events: readonly CameraEvent[], t: number, initial: Rect, aspect: number): Rect {
  let view = initial;
  for (const e of [...events].sort((a, b) => a.at - b.at)) {
    if (e.at > t) break;
    const p = progress({ start: e.at, duration: e.duration ?? DURATION, ease: ease.move }, t);
    view = between(view, fit(e.region, aspect, e.padding), p);
  }
  return view;
}

/**
 * Drive a world element (positioned at 0,0, sized in world units) so the frame
 * shows the camera's view. Returns the renderer to call with each seek time.
 */
export function mountCamera(
  world: HTMLElement,
  frame: { width: number; height: number },
  events: readonly CameraEvent[],
  initial: Rect = { x: 0, y: 0, w: frame.width, h: frame.height },
): (t: number) => void {
  world.style.transformOrigin = "0 0";
  const aspect = frame.width / frame.height;
  return (t: number) => {
    const view = cameraAt(events, t, initial, aspect);
    const scale = frame.width / view.w;
    world.style.transform = `translate(${-view.x * scale}px, ${-view.y * scale}px) scale(${scale})`;
  };
}
