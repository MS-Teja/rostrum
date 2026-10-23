import { ease } from "../time/easing";
import { lerp, progress } from "../time/timeline";

/**
 * A system diagram laid out by meaning, not coordinates: the script says which
 * column a component sits in (clients | brokers | consumers) and what connects
 * to what; the layout works out where everything goes for the frame size.
 */

export interface DiagramNode {
  id: string;
  label: string;
  kind?: "service" | "store" | "client";
}

export interface DiagramSpec {
  /** Left to right, the way data flows. */
  columns: Array<{ id: string; nodes: DiagramNode[] }>;
  groups?: Array<{ id: string; label: string; nodes: string[] }>;
  edges?: Array<{ id: string; from: string; to: string }>;
}

export interface Point {
  x: number;
  y: number;
}

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DiagramLayout {
  nodes: Map<string, Box>;
  groups: Map<string, Box>;
  edges: Map<string, Point[]>;
  /** Node box height, the unit everything else scales from. */
  unit: number;
}

export function layoutDiagram(spec: DiagramSpec, size: { width: number; height: number }): DiagramLayout {
  const cols = spec.columns.length;
  const tallest = Math.max(1, ...spec.columns.map((c) => c.nodes.length));
  const w = Math.min((size.width / cols) * 0.6, 340);
  const h = Math.min(w * 0.42, (size.height * 0.8) / (tallest * 1.5));
  const gap = h * 0.5;

  const nodes = new Map<string, Box>();
  spec.columns.forEach((col, i) => {
    const cx = (size.width * (i + 0.5)) / cols;
    const stack = col.nodes.length * h + (col.nodes.length - 1) * gap;
    col.nodes.forEach((node, j) => {
      nodes.set(node.id, { x: cx - w / 2, y: (size.height - stack) / 2 + j * (h + gap), w, h });
    });
  });

  const groups = new Map<string, Box>();
  for (const g of spec.groups ?? []) {
    const boxes = g.nodes.map((id) => nodes.get(id)).filter((b): b is Box => !!b);
    if (boxes.length === 0) continue;
    const pad = h * 0.35;
    const title = h * 0.45;
    const x = Math.min(...boxes.map((b) => b.x)) - pad;
    const y = Math.min(...boxes.map((b) => b.y)) - pad - title;
    const right = Math.max(...boxes.map((b) => b.x + b.w)) + pad;
    const bottom = Math.max(...boxes.map((b) => b.y + b.h)) + pad;
    groups.set(g.id, { x, y, w: right - x, h: bottom - y });
  }

  const edges = new Map<string, Point[]>();
  for (const e of spec.edges ?? []) {
    const a = nodes.get(e.from);
    const b = nodes.get(e.to);
    if (!a || !b) throw new Error(`Edge "${e.id}" connects a node that isn't in the diagram`);
    edges.set(e.id, route(a, b));
  }

  return { nodes, groups, edges, unit: h };
}

/** Right side to left side with one elbow; top to bottom when stacked in a column. */
function route(a: Box, b: Box): Point[] {
  if (Math.abs(a.x - b.x) < 1) {
    const down = b.y > a.y;
    const start = { x: a.x + a.w / 2, y: down ? a.y + a.h : a.y };
    const end = { x: b.x + b.w / 2, y: down ? b.y : b.y + b.h };
    return [start, end];
  }
  const forward = b.x > a.x;
  const start = { x: forward ? a.x + a.w : a.x, y: a.y + a.h / 2 };
  const end = { x: forward ? b.x : b.x + b.w, y: b.y + b.h / 2 };
  if (Math.abs(start.y - end.y) < 1) return [start, end];
  const mid = (start.x + end.x) / 2;
  return [start, { x: mid, y: start.y }, { x: mid, y: end.y }, end];
}

/** The point a fraction `p` of the way along a polyline, by length. */
export function pointAlong(path: readonly Point[], p: number): Point {
  const lengths = path.slice(1).map((pt, i) => Math.hypot(pt.x - path[i]!.x, pt.y - path[i]!.y));
  const total = lengths.reduce((s, l) => s + l, 0);
  let remaining = Math.min(Math.max(p, 0), 1) * total;
  for (let i = 0; i < lengths.length; i++) {
    const len = lengths[i]!;
    if (remaining <= len || i === lengths.length - 1) {
      const f = len === 0 ? 0 : Math.min(remaining / len, 1);
      return { x: lerp(path[i]!.x, path[i + 1]!.x, f), y: lerp(path[i]!.y, path[i + 1]!.y, f) };
    }
    remaining -= len;
  }
  return path[0]!;
}

export type DiagramEvent =
  /** Nodes, groups or edges appear; edges draw themselves from source to target. */
  | { type: "show"; at: number; ids: string[]; duration?: number }
  /** A message travels along an edge. */
  | { type: "send"; at: number; edge: string; label?: string; duration?: number }
  /** Accent these and dim everything else, until the next focus. An empty list clears focus. */
  | { type: "focus"; at: number; ids: string[]; duration?: number }
  /** Components go down. */
  | { type: "fail"; at: number; ids: string[]; duration?: number };

export interface Packet {
  edge: string;
  label?: string;
  /** 0 → 1 along the edge. */
  p: number;
}

export interface DiagramState {
  shown: Map<string, number>;
  accent: Map<string, number>;
  /** How far everything outside the focus is dimmed, 0 → 1. */
  dim: number;
  failed: Map<string, number>;
  packets: Packet[];
}

const DURATION = { show: 0.6, send: 1.1, focus: 0.5, fail: 0.4 } as const;

/** The diagram at time `t`, from its events alone. */
export function diagramStateAt(events: readonly DiagramEvent[], t: number): DiagramState {
  const shown = new Map<string, number>();
  const accent = new Map<string, number>();
  const failed = new Map<string, number>();
  const packets: Packet[] = [];
  let focusSet = new Set<string>();
  let dim = 0;

  for (const e of [...events].sort((a, b) => a.at - b.at)) {
    if (e.at > t) break;
    if (e.type === "show") {
      const p = progress({ start: e.at, duration: e.duration ?? DURATION.show, ease: ease.enter }, t);
      for (const id of e.ids) shown.set(id, Math.max(shown.get(id) ?? 0, p));
    } else if (e.type === "send") {
      const p = progress({ start: e.at, duration: e.duration ?? DURATION.send, ease: ease.move }, t);
      if (p < 1) packets.push({ edge: e.edge, ...(e.label ? { label: e.label } : {}), p });
    } else if (e.type === "focus") {
      const p = progress({ start: e.at, duration: e.duration ?? DURATION.focus, ease: ease.move }, t);
      const next = new Set(e.ids);
      for (const id of new Set([...focusSet, ...next, ...accent.keys()])) {
        accent.set(id, lerp(accent.get(id) ?? 0, next.has(id) ? 1 : 0, p));
      }
      dim = lerp(dim, next.size > 0 ? 1 : 0, p);
      focusSet = next;
    } else {
      const p = progress({ start: e.at, duration: e.duration ?? DURATION.fail, ease: ease.enter }, t);
      for (const id of e.ids) failed.set(id, Math.max(failed.get(id) ?? 0, p));
    }
  }
  return { shown, accent, dim, failed, packets };
}

const SVG = "http://www.w3.org/2000/svg";
const FONT = "var(--rs-font, Inter, sans-serif)";

/** Geometry in attributes; paint and type in styles, where the --rs-* variables resolve. */
function el<K extends keyof SVGElementTagNameMap>(
  name: K,
  attrs: Record<string, string | number>,
  style: Record<string, string> = {},
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  for (const [k, v] of Object.entries(style)) node.style.setProperty(k, v);
  return node;
}

const smoothstep = (a: number, b: number, x: number) => {
  const k = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return k * k * (3 - 2 * k);
};

const pathLength = (pts: readonly Point[]) =>
  pts.slice(1).reduce((s, p, i) => s + Math.hypot(p.x - pts[i]!.x, p.y - pts[i]!.y), 0);

/** Outline for a node: rounded box for services, pill for clients, cylinder for stores. */
function nodeShape(kind: DiagramNode["kind"], b: Box): string {
  const { x, y, w, h } = b;
  if (kind === "store") {
    const ry = h * 0.14;
    return `M ${x} ${y + ry} A ${w / 2} ${ry} 0 0 1 ${x + w} ${y + ry} V ${y + h - ry} A ${w / 2} ${ry} 0 0 1 ${x} ${y + h - ry} Z M ${x} ${y + ry} A ${w / 2} ${ry} 0 0 0 ${x + w} ${y + ry}`;
  }
  const r = kind === "client" ? h / 2 : h * 0.18;
  return `M ${x + r} ${y} H ${x + w - r} A ${r} ${r} 0 0 1 ${x + w} ${y + r} V ${y + h - r} A ${r} ${r} 0 0 1 ${x + w - r} ${y + h} H ${x + r} A ${r} ${r} 0 0 1 ${x} ${y + h - r} V ${y + r} A ${r} ${r} 0 0 1 ${x + r} ${y} Z`;
}

/**
 * Draw a diagram inside `host`, sized to the host's box. Colours and fonts come
 * from CSS custom properties (--rs-*). Returns the renderer to call with each seek time.
 */
export function mountDiagram(host: HTMLElement, spec: DiagramSpec, events: readonly DiagramEvent[]): (t: number) => void {
  const width = host.clientWidth;
  const height = host.clientHeight;
  const layout = layoutDiagram(spec, { width, height });
  const u = layout.unit;

  const svg = el("svg", { width, height, viewBox: `0 0 ${width} ${height}` });
  svg.style.overflow = "visible";
  host.replaceChildren(svg);

  const groupNodes = new Map<string, SVGGElement>();
  for (const g of spec.groups ?? []) {
    const b = layout.groups.get(g.id);
    if (!b) continue;
    const node = el("g", { opacity: 0 });
    node.append(
      el("rect", { x: b.x, y: b.y, width: b.w, height: b.h, rx: u * 0.28, "stroke-width": Math.max(1, u * 0.02) }, {
        fill: "var(--rs-group, rgba(255,255,255,0.02))",
        stroke: "var(--rs-stroke, #2a2c33)",
      }),
    );
    const label = el("text", { x: b.x + u * 0.35, y: b.y + u * 0.45, "font-size": u * 0.23 }, {
      fill: "var(--rs-muted, #8a8f98)",
      "font-family": FONT,
      "font-weight": "600",
      "letter-spacing": "0.08em",
    });
    label.textContent = g.label.toUpperCase();
    node.append(label);
    svg.append(node);
    groupNodes.set(g.id, node);
  }

  const edgeNodes = new Map<string, { path: SVGPathElement; head: SVGPathElement; length: number }>();
  for (const [id, pts] of layout.edges) {
    const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
    const path = el("path", { d, fill: "none", "stroke-width": Math.max(1.5, u * 0.025), "stroke-linejoin": "round" }, {
      stroke: "var(--rs-edge, #4a4d57)",
    });
    const end = pts.at(-1)!;
    const prev = pts.at(-2)!;
    const angle = (Math.atan2(end.y - prev.y, end.x - prev.x) * 180) / Math.PI;
    const s = u * 0.09;
    const head = el("path", { d: `M 0 0 L ${-s * 1.8} ${-s} L ${-s * 1.8} ${s} Z`, transform: `translate(${end.x} ${end.y}) rotate(${angle})` }, {
      fill: "var(--rs-edge, #4a4d57)",
    });
    svg.append(path, head);
    edgeNodes.set(id, { path, head, length: pathLength(pts) });
  }

  const nodeEls = new Map<string, { g: SVGGElement; shape: SVGPathElement }>();
  for (const col of spec.columns) {
    for (const n of col.nodes) {
      const b = layout.nodes.get(n.id)!;
      const g = el("g", { opacity: 0 });
      const shape = el("path", { d: nodeShape(n.kind, b), "stroke-width": Math.max(1.5, u * 0.022) });
      const label = el("text", { x: b.x + b.w / 2, y: b.y + b.h / 2, "text-anchor": "middle", "dominant-baseline": "central", "font-size": u * 0.27 }, {
        fill: "var(--rs-text, #f5f5f7)",
        "font-family": FONT,
        "font-weight": "600",
      });
      label.textContent = n.label;
      g.append(shape, label);
      svg.append(g);
      nodeEls.set(n.id, { g, shape });
    }
  }

  const packetLayer = el("g", {});
  svg.append(packetLayer);

  return (t: number) => {
    const s = diagramStateAt(events, t);
    const visible = (id: string) => s.shown.get(id) ?? 0;
    const presence = (id: string) => 1 - 0.7 * s.dim * (1 - (s.accent.get(id) ?? 0));

    for (const [id, g] of groupNodes) g.setAttribute("opacity", String(visible(id) * presence(id)));

    for (const [id, e] of edgeNodes) {
      const v = visible(id);
      e.path.style.strokeDasharray = `${e.length}`;
      e.path.style.strokeDashoffset = `${e.length * (1 - v)}`;
      const lit = s.accent.get(id) ?? 0;
      const colour = lit > 0.5 ? "var(--rs-accent, #4f8cff)" : "var(--rs-edge, #4a4d57)";
      e.path.style.stroke = colour;
      e.head.style.fill = colour;
      e.path.setAttribute("opacity", String(presence(id)));
      e.head.setAttribute("opacity", String((v >= 0.98 ? 1 : 0) * presence(id)));
    }

    for (const [id, { g, shape }] of nodeEls) {
      const v = visible(id);
      const failed = s.failed.get(id) ?? 0;
      const lit = s.accent.get(id) ?? 0;
      g.setAttribute("opacity", String(v * presence(id) * (1 - 0.45 * failed)));
      g.setAttribute("transform", `translate(0 ${(1 - v) * u * 0.25})`);
      shape.style.fill = lit > 0.5 ? "var(--rs-accent-soft, rgba(79,140,255,0.18))" : "var(--rs-surface, #17181c)";
      shape.style.stroke =
        failed > 0.5 ? "var(--rs-warn, #ff5f57)" : lit > 0.5 ? "var(--rs-accent, #4f8cff)" : "var(--rs-stroke, #2a2c33)";
    }

    packetLayer.replaceChildren();
    for (const pk of s.packets) {
      const path = layout.edges.get(pk.edge);
      if (!path) continue;
      const at = pointAlong(path, pk.p);
      const label = pk.label ?? "";
      const ph = u * 0.42;
      const pw = Math.max(ph, label.length * u * 0.14 + u * 0.4);
      // Ease in on departure and fade into the target on arrival, so the
      // packet never sits on top of the node's label.
      const fade = Math.min(1, pk.p / 0.1) * (1 - smoothstep(0.82, 1, pk.p));
      const g = el("g", { transform: `translate(${at.x} ${at.y}) scale(${0.85 + 0.15 * fade})`, opacity: fade });
      g.append(el("rect", { x: -pw / 2, y: -ph / 2, width: pw, height: ph, rx: ph / 2 }, { fill: "var(--rs-accent, #4f8cff)" }));
      if (label) {
        const text = el("text", { "text-anchor": "middle", "dominant-baseline": "central", "font-size": u * 0.23 }, {
          fill: "var(--rs-on-accent, #ffffff)",
          "font-family": FONT,
          "font-weight": "600",
        });
        text.textContent = label;
        g.append(text);
      }
      packetLayer.append(g);
    }
  };
}
