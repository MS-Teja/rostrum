export type Renderer = (t: number) => void;

/**
 * Redraw on every HyperFrames seek. HyperFrames renders each frame on its own,
 * so `render` must derive everything from `t` and nothing from the previous frame.
 */
export function onSeek(render: Renderer, target: EventTarget = window): () => void {
  const handler = (e: Event) => render((e as CustomEvent<{ time: number }>).detail.time);
  target.addEventListener("hf-seek", handler);
  render(0);
  return () => target.removeEventListener("hf-seek", handler);
}
