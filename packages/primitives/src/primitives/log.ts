import { ease } from "../time/easing";
import { lerp, progress } from "../time/timeline";

/**
 * An append-only log: Kafka partitions, queues, write-ahead logs, event streams.
 * Records get offsets in the order they're appended; readers point at the next
 * offset they'll read; retention expires old records without renumbering the rest.
 */

export interface LogRecord {
  id: string;
  label: string;
  /** Accent marks the record the narration is about; everything else stays neutral. */
  accent?: boolean;
}

export type LogEvent =
  | { type: "append"; at: number; record: LogRecord; duration?: number }
  | { type: "read"; at: number; reader: string; offset: number; duration?: number }
  | { type: "expire"; at: number; before: number; duration?: number };

export interface CellState {
  offset: number;
  record: LogRecord;
  /** 0 → 1 as the record arrives. */
  shown: number;
  /** 0 → 1 as retention removes it. */
  gone: number;
}

export interface ReaderState {
  name: string;
  /** Fractional while moving, so the pointer glides between offsets. */
  position: number;
  shown: number;
}

export interface LogState {
  cells: CellState[];
  readers: ReaderState[];
}

const DURATION = { append: 0.6, read: 0.7, expire: 0.5 } as const;

/** The log at time `t`, from its events alone. */
export function logStateAt(events: readonly LogEvent[], t: number): LogState {
  const ordered = [...events].sort((a, b) => a.at - b.at);
  const cells: CellState[] = [];
  const readers = new Map<string, ReaderState>();
  let nextOffset = 0;

  for (const e of ordered) {
    if (e.type === "append") {
      // Offsets are fixed by append order, whether or not the append has happened yet.
      const offset = nextOffset++;
      if (e.at > t) continue;
      const shown = progress({ start: e.at, duration: e.duration ?? DURATION.append, ease: ease.enter }, t);
      cells.push({ offset, record: e.record, shown, gone: 0 });
    } else if (e.at > t) {
      continue;
    } else if (e.type === "read") {
      const p = progress({ start: e.at, duration: e.duration ?? DURATION.read, ease: ease.move }, t);
      const reader = readers.get(e.reader);
      if (reader) reader.position = lerp(reader.position, e.offset, p);
      else readers.set(e.reader, { name: e.reader, position: e.offset, shown: p });
    } else {
      const p = progress({ start: e.at, duration: e.duration ?? DURATION.expire, ease: ease.exit }, t);
      for (const cell of cells) if (cell.offset < e.before) cell.gone = Math.max(cell.gone, p);
    }
  }
  return { cells, readers: [...readers.values()] };
}

export interface LogSpec {
  events: LogEvent[];
  /** Name shown beside the log, e.g. "partition 0". */
  label?: string;
  /** Cells to leave room for. Default: the number of appends. */
  capacity?: number;
}

const SVG = "http://www.w3.org/2000/svg";

/**
 * Geometry goes in attributes; paint and type go in inline styles, because CSS
 * variables (the --rs-* art direction) resolve in styles but not in SVG attributes.
 */
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

const FONT = "var(--rs-font, Inter, sans-serif)";
const MONO = "var(--rs-mono, 'JetBrains Mono', monospace)";

/**
 * Draw a log inside `host`, sized to the host's box. Colours and fonts come from
 * CSS custom properties (--rs-*), so the art direction lives in the stylesheet.
 * Returns the renderer to call with each seek time.
 */
export function mountLog(host: HTMLElement, spec: LogSpec): (t: number) => void {
  const width = host.clientWidth;
  const height = host.clientHeight;
  const appends = spec.events.filter((e) => e.type === "append");
  const capacity = spec.capacity ?? Math.max(1, appends.length);

  const gap = Math.round(width * 0.012);
  const labelWidth = spec.label ? width * 0.16 : 0;
  const cell = Math.min(height * 0.42, (width - labelWidth - gap * (capacity - 1)) / capacity);
  const rowY = (height - cell) / 2;
  const cellX = (offset: number) => labelWidth + offset * (cell + gap);

  const svg = el("svg", { width, height, viewBox: `0 0 ${width} ${height}` });
  svg.style.overflow = "visible";
  host.replaceChildren(svg);

  if (spec.label) {
    const label = el("text", {
      x: labelWidth - gap * 2,
      y: rowY + cell / 2,
      "text-anchor": "end",
      "dominant-baseline": "central",
      "font-size": cell * 0.26,
    }, { fill: "var(--rs-muted, #8a8f98)", "font-family": FONT });
    label.textContent = spec.label;
    svg.append(label);
  }

  const cellNodes = new Map<number, SVGGElement>();
  appends.forEach((_, offset) => {
    const g = el("g", { opacity: 0 });
    g.append(
      el("rect", {
        width: cell,
        height: cell,
        rx: cell * 0.16,
        "stroke-width": Math.max(1.5, cell * 0.02),
      }),
    );
    const text = el("text", {
      x: cell / 2,
      y: cell / 2,
      "text-anchor": "middle",
      "dominant-baseline": "central",
      "font-size": cell * 0.24,
    }, { "font-family": FONT, "font-weight": "600" });
    const offsetLabel = el("text", {
      x: cell / 2,
      y: cell + cell * 0.3,
      "text-anchor": "middle",
      "font-size": cell * 0.2,
    }, { fill: "var(--rs-muted, #8a8f98)", "font-family": MONO });
    offsetLabel.textContent = String(offset);
    g.append(text, offsetLabel);
    svg.append(g);
    cellNodes.set(offset, g);
  });

  const readerNodes = new Map<string, SVGGElement>();
  const readerFor = (name: string) => {
    let g = readerNodes.get(name);
    if (!g) {
      g = el("g", { opacity: 0 });
      const s = cell * 0.16;
      g.append(el("path", { d: `M ${-s} ${-s * 1.6} L ${s} ${-s * 1.6} L 0 0 Z` }, { fill: "var(--rs-accent, #4f8cff)" }));
      const name_ = el("text", {
        y: -s * 2.2,
        "text-anchor": "middle",
        "font-size": cell * 0.2,
      }, { fill: "var(--rs-accent, #4f8cff)", "font-family": FONT, "font-weight": "600" });
      name_.textContent = name;
      g.append(name_);
      svg.append(g);
      readerNodes.set(name, g);
    }
    return g;
  };

  return (t: number) => {
    const state = logStateAt(spec.events, t);
    for (const g of cellNodes.values()) g.setAttribute("opacity", "0");
    for (const c of state.cells) {
      const g = cellNodes.get(c.offset);
      if (!g) continue;
      const slide = (1 - c.shown) * cell * 0.5;
      g.setAttribute("opacity", String(c.shown * (1 - c.gone)));
      g.setAttribute("transform", `translate(${cellX(c.offset) + slide} ${rowY})`);
      const [rect, text] = [g.children[0]!, g.children[1]!];
      (rect as SVGElement).style.fill = c.record.accent ? "var(--rs-accent-soft, rgba(79,140,255,0.18))" : "var(--rs-surface, #17181c)";
      (rect as SVGElement).style.stroke = c.record.accent ? "var(--rs-accent, #4f8cff)" : "var(--rs-stroke, #2a2c33)";
      (text as SVGElement).style.fill = "var(--rs-text, #f5f5f7)";
      text.textContent = c.record.label;
    }
    for (const r of state.readers) {
      const g = readerFor(r.name);
      g.setAttribute("opacity", String(r.shown));
      g.setAttribute("transform", `translate(${cellX(r.position) + cell / 2} ${rowY - cell * 0.12})`);
    }
  };
}
