import { describe, expect, it } from "vitest";
import { diagramStateAt, layoutDiagram, pointAlong, type DiagramEvent, type DiagramSpec } from "../src/primitives/diagram";

const size = { width: 1920, height: 1080 };
const spec: DiagramSpec = {
  columns: [
    { id: "clients", nodes: [{ id: "producer", label: "Producer", kind: "client" }] },
    {
      id: "cluster",
      nodes: [
        { id: "b1", label: "Broker 1" },
        { id: "b2", label: "Broker 2" },
        { id: "b3", label: "Broker 3" },
      ],
    },
    { id: "readers", nodes: [{ id: "consumer", label: "Consumer", kind: "client" }] },
  ],
  groups: [{ id: "kafka", label: "Kafka cluster", nodes: ["b1", "b2", "b3"] }],
  edges: [
    { id: "p-b1", from: "producer", to: "b1" },
    { id: "p-b2", from: "producer", to: "b2" },
    { id: "b2-c", from: "b2", to: "consumer" },
  ],
};

describe("layoutDiagram", () => {
  const layout = layoutDiagram(spec, size);

  it("puts columns left to right and stacks nodes without overlap", () => {
    const [p, b1, b2, b3, c] = ["producer", "b1", "b2", "b3", "consumer"].map((id) => layout.nodes.get(id)!);
    expect(p!.x).toBeLessThan(b1!.x);
    expect(b1!.x).toBeLessThan(c!.x);
    expect(b1!.y + b1!.h).toBeLessThan(b2!.y);
    expect(b2!.y + b2!.h).toBeLessThan(b3!.y);
  });

  it("keeps everything inside the frame", () => {
    for (const box of [...layout.nodes.values(), ...layout.groups.values()]) {
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.y).toBeGreaterThanOrEqual(0);
      expect(box.x + box.w).toBeLessThanOrEqual(size.width);
      expect(box.y + box.h).toBeLessThanOrEqual(size.height);
    }
  });

  it("wraps a group around its members", () => {
    const g = layout.groups.get("kafka")!;
    for (const id of ["b1", "b2", "b3"]) {
      const n = layout.nodes.get(id)!;
      expect(n.x).toBeGreaterThan(g.x);
      expect(n.y).toBeGreaterThan(g.y);
      expect(n.x + n.w).toBeLessThan(g.x + g.w);
      expect(n.y + n.h).toBeLessThan(g.y + g.h);
    }
  });

  it("routes edges from the source's right side to the target's left side", () => {
    const path = layout.edges.get("p-b1")!;
    const p = layout.nodes.get("producer")!;
    const b1 = layout.nodes.get("b1")!;
    expect(path[0]).toEqual({ x: p.x + p.w, y: p.y + p.h / 2 });
    expect(path.at(-1)).toEqual({ x: b1.x, y: b1.y + b1.h / 2 });
  });

  it("draws a straight edge between nodes at the same height", () => {
    expect(layout.edges.get("p-b2")).toHaveLength(2);
  });

  it("rejects edges to missing nodes", () => {
    expect(() => layoutDiagram({ ...spec, edges: [{ id: "x", from: "producer", to: "nope" }] }, size)).toThrow(/"x"/);
  });
});

describe("pointAlong", () => {
  const path = [
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 10, y: 10 },
  ];

  it("measures by length across segments", () => {
    expect(pointAlong(path, 0)).toEqual({ x: 0, y: 0 });
    expect(pointAlong(path, 0.5)).toEqual({ x: 10, y: 0 });
    expect(pointAlong(path, 0.75)).toEqual({ x: 10, y: 5 });
    expect(pointAlong(path, 1)).toEqual({ x: 10, y: 10 });
  });
});

describe("diagramStateAt", () => {
  const events: DiagramEvent[] = [
    { type: "show", at: 0, ids: ["producer", "b1"] },
    { type: "send", at: 1, edge: "p-b1", label: "order#42", duration: 1 },
    { type: "focus", at: 3, ids: ["b1"], duration: 0.5 },
    { type: "focus", at: 5, ids: [], duration: 0.5 },
    { type: "fail", at: 6, ids: ["b1"] },
  ];

  it("shows a packet only while it's in flight", () => {
    expect(diagramStateAt(events, 0.9).packets).toEqual([]);
    const mid = diagramStateAt(events, 1.5).packets;
    expect(mid).toHaveLength(1);
    expect(mid[0]).toMatchObject({ edge: "p-b1", label: "order#42" });
    expect(diagramStateAt(events, 2.1).packets).toEqual([]);
  });

  it("accents the focus and dims the rest, then clears", () => {
    const focused = diagramStateAt(events, 4);
    expect(focused.accent.get("b1")).toBe(1);
    expect(focused.dim).toBe(1);
    const cleared = diagramStateAt(events, 5.6);
    expect(cleared.accent.get("b1")).toBe(0);
    expect(cleared.dim).toBe(0);
  });

  it("marks failures and keeps earlier state", () => {
    const s = diagramStateAt(events, 7);
    expect(s.failed.get("b1")).toBe(1);
    expect(s.shown.get("producer")).toBe(1);
  });
});
