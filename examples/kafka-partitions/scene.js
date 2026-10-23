// How Kafka partitions work: the scene. Everything is drawn from the time t alone
// (HyperFrames renders frames out of order), using cue times from timing.js.
(() => {
  const R = window.Rostrum;
  const T = window.ROSTRUM_TIMING;
  const { ease, progress, lerp } = R;
  const pop = R.spring({ response: 0.42, damping: 0.62 });

  /** The narration starts this far into the video (the <audio> data-start). */
  const OFFSET = 0.4;
  const cue = (key) => {
    const t = T.cues[key];
    if (t === undefined) throw new Error(`Missing cue ${key}`);
    return t + OFFSET;
  };
  const TOTAL = Number(document.getElementById("root").dataset.duration);

  const TOPIC = cue("b1:topic");
  const RUSH = cue("b1:rush");
  const SPLIT = cue("b2:partitions");
  const PARALLEL = cue("b2:parallel");
  const KEY = cue("b3:key");
  const C42 = cue("b3:c42");
  const SAME = cue("b3:same");
  const ORDER = cue("b4:order");
  const ACROSS = cue("b4:across");
  const GROUP = cue("b5:consumer group");
  const ONE = cue("b5:one");
  const READ = cue("b5:parallel");
  const RECAP = cue("b6:recap");
  const B5 = T.beats.find((b) => b.id === "b5").start + OFFSET;

  // ---------- Layout (1080p pixels, in world coordinates; the camera frames them)
  const CELL = 84;
  const GAP = 12;
  const STEP = CELL + GAP;
  const LANE_X = 620;
  const CAP = 8;
  const CAP_SINGLE = 10;
  const LANE_Y = [330, 540, 750];
  const PRODUCER = { cx: 220, cy: 540, w: 236, h: 88 };
  const QUEUE_X = 455;
  const PAD = 10;
  const laneRight = (cap) => LANE_X + cap * STEP - GAP;
  const CONSUMER = { x: 1580, w: 290, h: 80 };
  const BOX = { x: 1556, y: LANE_Y[0] - 96, w: 338, h: LANE_Y[2] - LANE_Y[0] + 192 };
  const FLIGHT = 0.55;

  // Waiting events pile up next to the producer, alternating above and below.
  const SLOTS = [0, -1, 1, -2, 2, -3, 3].map((k) => LANE_Y[1] + k * (CELL + 10));
  const slotY = (k) => {
    const i = Math.min(Math.floor(k), SLOTS.length - 1);
    const j = Math.min(i + 1, SLOTS.length - 1);
    return lerp(SLOTS[i], SLOTS[j], k - Math.floor(k));
  };

  // Stand-in for Kafka's partitioner: a fixed key → partition table, so a key
  // always lands in the same lane (F5). The real partitioner hashes with murmur2.
  const PARTITION_OF = { 7: 0, 13: 0, 88: 0, 42: 1, 5: 1, 31: 1, 21: 2, 64: 2, 9: 2 };

  // ---------- Every event the producer sends
  const sends = [];
  {
    // Setup: the producer speeds up, then bursts; the single log takes one write a second.
    const keys = [7, 21, 42, 13, 5, 64, 88, 9, 31, 7, 21, 13, 64, 5, 88];
    const emits = [];
    let t = TOPIC + 0.7;
    for (const gap of [1.0, 0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.45, 0.4]) {
      emits.push(t);
      t += gap;
    }
    for (let i = 0; i < 6; i++) emits.push(RUSH + 0.1 + i * 0.12);

    let free = 0;
    let landed = 0;
    emits.forEach((emit, i) => {
      const s = { key: keys[i], emit, depart: Infinity, land: Infinity, single: null };
      const depart = Math.max(emit, free);
      if (landed < CAP_SINGLE && depart + FLIGHT < SPLIT) {
        Object.assign(s, { depart, land: depart + FLIGHT, single: landed++ });
        free = depart + 1.0;
      }
      sends.push(s);
    });

    // The queue clears into all three partitions at once.
    sends
      .filter((s) => s.depart === Infinity)
      .forEach((s, i) => {
        s.depart = PARALLEL + Math.floor(i / 3) * 0.28 + (i % 3) * 0.05;
        s.land = s.depart + FLIGHT;
      });

    const send = (key, emit) => sends.push({ key, emit, depart: emit, land: emit + FLIGHT, single: null });
    [[21, 2.0], [7, 2.7], [5, 3.3], [64, 3.9], [13, 4.6], [9, 5.2]].forEach(([k, d]) => send(k, PARALLEL + d));
    send(42, SAME);
    send(7, SAME + 0.22);
    send(42, SAME + 0.45);
    send(64, SAME + 0.67);
    send(42, SAME + 0.9);
    [[42, 0.3], [7, 0.8], [21, 1.3], [42, 1.8], [13, 2.6]].forEach(([k, d]) => send(k, RECAP + d));
  }
  for (const s of sends) s.lane = PARTITION_OF[s.key];
  for (const L of [0, 1, 2]) {
    sends
      .filter((s) => s.lane === L)
      .sort((a, b) => a.land - b.land)
      .forEach((s, i) => (s.offset = i));
  }

  // ---------- Drawing helpers
  const SVG = "http://www.w3.org/2000/svg";
  const scene = document.getElementById("scene");
  const el = (name, attrs = {}, style = {}, parent = scene) => {
    const node = document.createElementNS(SVG, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    for (const [k, v] of Object.entries(style)) node.style.setProperty(k, v);
    parent.append(node);
    return node;
  };
  const text = (content, attrs, style, parent) => {
    const node = el("text", attrs, { "font-family": "var(--rs-font)", ...style }, parent);
    node.textContent = content;
    return node;
  };
  const clamp01 = (x) => Math.min(1, Math.max(0, x));
  const span = (start, duration, e = ease.move) => (t) => progress({ start, duration, ease: e }, t);
  const bump = (t, at, rise = 0.15, fall = 0.5) =>
    t < at ? clamp01(1 - (at - t) / rise) : clamp01(1 - (t - at) / fall);
  const popAt = (start) => (t) => progress({ start, duration: pop.settle, ease: pop.ease }, t);

  // ---------- Static pieces (back to front)
  const tracks = [0, 1, 2].map(() => el("rect", { rx: 18 }, { fill: "var(--rs-track)", stroke: "var(--rs-track-stroke)", "stroke-width": "2" }));

  const topicLabel = text("topic · orders", { "font-size": 34, "font-weight": 600, x: LANE_X - 6 }, { fill: "var(--rs-text)" });
  const laneLabels = [0, 1, 2].map((L) =>
    text(`partition ${L} · broker ${L + 1}`, { "font-size": 32, x: LANE_X - 6 }, { fill: "var(--rs-muted)", "font-family": "var(--rs-mono)" }),
  );

  const producer = el("g");
  el(
    "rect",
    { x: PRODUCER.cx - PRODUCER.w / 2, y: PRODUCER.cy - PRODUCER.h / 2, width: PRODUCER.w, height: PRODUCER.h, rx: PRODUCER.h / 2 },
    { fill: "var(--rs-surface)", stroke: "var(--rs-stroke)", "stroke-width": "2" },
    producer,
  );
  text("Producer", { x: PRODUCER.cx, y: PRODUCER.cy, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 34, "font-weight": 600 }, { fill: "var(--rs-text)" }, producer);

  const hashTag = el("g");
  const mono = { fill: "var(--rs-accent-text)", "font-family": "var(--rs-mono)" };
  text("hash(42)", { x: PRODUCER.cx, y: PRODUCER.cy + 98, "text-anchor": "middle", "font-size": 32 }, mono, hashTag);
  text("→ partition 1", { x: PRODUCER.cx, y: PRODUCER.cy + 140, "text-anchor": "middle", "font-size": 32 }, mono, hashTag);

  const waitingLabel = text("waiting", { x: QUEUE_X, "text-anchor": "middle", "font-size": 32 }, { fill: "var(--rs-muted)", "font-family": "var(--rs-mono)" });

  const box = el("g");
  el("rect", { x: BOX.x, y: BOX.y, width: BOX.w, height: BOX.h, rx: 26 }, { fill: "rgba(255,255,255,0.015)", stroke: "var(--rs-stroke)", "stroke-width": "2" }, box);
  text("consumer group", { x: BOX.x + 4, y: BOX.y - 22, "font-size": 32 }, { fill: "var(--rs-muted)", "font-family": "var(--rs-mono)" }, box);

  const edges = LANE_Y.map((y) => {
    const g = el("g");
    const x1 = laneRight(CAP) + PAD + 14;
    const x2 = CONSUMER.x - 16;
    const line = el("line", { x1, y1: y, x2, y2: y }, { stroke: "var(--rs-edge)", "stroke-width": "3" }, g);
    const head = el("path", { d: `M ${x2 + 10} ${y} L ${x2 - 6} ${y - 9} L ${x2 - 6} ${y + 9} Z` }, { fill: "var(--rs-edge)" }, g);
    return { g, line, head, length: x2 - x1 };
  });

  const consumers = LANE_Y.map((y, L) => {
    const g = el("g");
    const rect = el("rect", { x: CONSUMER.x, y: y - CONSUMER.h / 2, width: CONSUMER.w, height: CONSUMER.h, rx: CONSUMER.h / 2 }, { fill: "var(--rs-surface)", stroke: "var(--rs-stroke)", "stroke-width": "2" }, g);
    text(`consumer ${L + 1}`, { x: CONSUMER.x + 30, y, "dominant-baseline": "central", "font-size": 32, "font-weight": 600 }, { fill: "var(--rs-text)" }, g);
    const at = text("", { x: CONSUMER.x + CONSUMER.w - 30, y, "text-anchor": "end", "dominant-baseline": "central", "font-size": 34, "font-weight": 700 }, { fill: "var(--rs-text)", "font-family": "var(--rs-mono)" }, g);
    return { g, rect, at };
  });

  // ---------- Events
  const cells = sends.map((s) => {
    const g = el("g");
    const rect = el("rect", { x: -CELL / 2, y: -CELL / 2, width: CELL, height: CELL, rx: 16 }, { "stroke-width": "2" }, g);
    const dot = el("circle", { r: 7 }, { fill: "var(--rs-muted)" }, g);
    const key = text(String(s.key), { "text-anchor": "middle", "dominant-baseline": "central", "font-size": 34, "font-weight": 600 }, { "font-family": "var(--rs-mono)" }, g);
    const offset = text("", { "text-anchor": "middle", y: CELL / 2 + 38, "font-size": 32 }, { fill: "var(--rs-muted)", "font-family": "var(--rs-mono)" }, g);
    return { s, g, rect, dot, key, offset };
  });

  const readers = LANE_Y.map(() => el("rect", { width: CELL - 12, height: 8, rx: 4 }, { fill: "var(--rs-text)" }));

  // Arrival order for "no order across partitions": the last three events in each
  // lane before that beat, numbered by when they arrived.
  const badged = [0, 1, 2]
    .flatMap((L) => sends.filter((s) => s.lane === L && s.land < ACROSS).sort((a, b) => a.land - b.land).slice(-3))
    .sort((a, b) => a.land - b.land);
  const connectors = [0, 1, 2].map(() => el("polyline", { fill: "none" }, { stroke: "var(--rs-accent)", "stroke-width": "4", "stroke-linejoin": "round" }));
  const badges = badged.map((s, rank) => {
    const g = el("g");
    el("circle", { r: 28 }, { fill: "var(--rs-text)" }, g);
    text(String(rank + 1), { "text-anchor": "middle", "dominant-baseline": "central", "font-size": 32, "font-weight": 700 }, { fill: "var(--rs-bg)", "font-family": "var(--rs-mono)" }, g);
    return { s, g, rank };
  });
  const arrivalKey = el("g");
  el("circle", { cx: laneRight(CAP) - 236, cy: LANE_Y[0] - CELL / 2 - PAD - 103, r: 18 }, { fill: "var(--rs-text)" }, arrivalKey);
  text("1", { x: laneRight(CAP) - 236, y: LANE_Y[0] - CELL / 2 - PAD - 102, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 24, "font-weight": 700 }, { fill: "var(--rs-bg)", "font-family": "var(--rs-mono)" }, arrivalKey);
  text("arrival order", { x: laneRight(CAP) - 206, y: LANE_Y[0] - CELL / 2 - PAD - 92, "font-size": 32 }, { fill: "var(--rs-text)", "font-family": "var(--rs-mono)" }, arrivalKey);

  // ---------- Camera: each shot framed on what matters right now
  const aspect = 1920 / 1080;
  const SETUP = { x: 90, y: 240, w: 1520, h: 600 };
  const LANES = { x: 90, y: 150, w: 1330, h: 720 };
  const WIDE = { x: 80, y: 150, w: 1830, h: 720 };
  const camera = R.mountCamera(
    document.getElementById("world"),
    { width: 1920, height: 1080 },
    [
      { at: SPLIT + 0.1, region: LANES, padding: 0.04, duration: 1.4 },
      { at: ORDER, region: { x: LANE_X - 70, y: LANE_Y[1] - 120, w: CAP * STEP + 140, h: 240 }, duration: 1.3 },
      { at: ACROSS, region: LANES, padding: 0.04, duration: 1.3 },
      { at: GROUP - 0.4, region: WIDE, padding: 0.05, duration: 1.4 },
      { at: RECAP, region: { x: 40, y: 130, w: 1910, h: 760 }, padding: 0.05, duration: 5 },
    ],
    R.fit(SETUP, aspect, 0.04),
  );

  // ---------- Per-frame state
  /** How many events are in lane L at t, rising smoothly as each one lands. */
  const countOf = (L, t) => {
    let n = 0;
    for (const s of sends) {
      if (s.lane !== L) continue;
      n += s.single !== null ? (t >= SPLIT ? 1 : 0) : span(s.land, 0.5)(t);
    }
    return n;
  };
  const scrollOf = (L, t) => Math.max(0, countOf(L, t) - CAP);
  /** Lanes slide apart from the single log's row during the split; cells ride with them. */
  const laneY = (L, t) => lerp(LANE_Y[1], LANE_Y[L], span(SPLIT + 0.2, 0.9)(t));
  const cellPos = (s, t, era) =>
    era === "single"
      ? { x: LANE_X + s.single * STEP + CELL / 2, y: LANE_Y[1] }
      : { x: LANE_X + (s.offset - scrollOf(s.lane, t)) * STEP + CELL / 2, y: laneY(s.lane, t) };
  const queueSlot = (s, t) => {
    let k = 0;
    for (const o of sends) {
      if (o === s) break;
      if (o.emit <= t && t < o.depart + 0.3) k += 1 - span(o.depart, 0.3)(t);
    }
    return k;
  };
  const readerPos = (L, t) => {
    const start = Math.ceil(scrollOf(L, READ));
    return lerp(start, countOf(L, t) - 1, span(READ, 2.2)(t));
  };

  const render = (t) => {
    camera(t);

    // Fade in from black, and out at the end.
    document.getElementById("fade").style.opacity = String(Math.max(1 - clamp01(t / 0.5), clamp01((t - (TOTAL - 0.8)) / 0.8)));

    const split = span(SPLIT + 0.2, 0.9)(t);
    producer.setAttribute("opacity", String(span(0.4, 0.6, ease.enter)(t)));

    // Tracks: one long log, then three partitions sliding apart from it.
    tracks.forEach((r, L) => {
      const cap = L === 1 ? lerp(CAP_SINGLE, CAP, split) : CAP;
      const y = lerp(LANE_Y[1], LANE_Y[L], split);
      r.setAttribute("x", LANE_X - PAD);
      r.setAttribute("y", y - CELL / 2 - PAD);
      r.setAttribute("width", laneRight(cap) - LANE_X + 2 * PAD);
      r.setAttribute("height", CELL + 2 * PAD);
      r.setAttribute("opacity", String(L === 1 ? span(TOPIC, 0.6, ease.enter)(t) : split));
      // "Order lives inside one log": each lane lights up in turn.
      const glow = bump(t, ACROSS + 3.0 + L * 0.35, 0.3, 1.2);
      r.style.stroke = glow > 0.05 ? `rgba(94,160,255,${0.3 + 0.7 * glow})` : "var(--rs-track-stroke)";
    });

    // The topic label sits on the single log, then rises above all three partitions.
    // Fade out, jump, fade back in, rather than drifting through partition 0's cells.
    const moved = t >= SPLIT + 0.55;
    topicLabel.setAttribute("y", moved ? LANE_Y[0] - CELL / 2 - PAD - 92 : LANE_Y[1] - CELL / 2 - PAD - 26);
    const swap = moved ? span(SPLIT + 0.9, 0.5, ease.enter)(t) : 1 - span(SPLIT, 0.4, ease.exit)(t);
    topicLabel.setAttribute("opacity", String(span(TOPIC, 0.5, ease.enter)(t) * swap));
    laneLabels.forEach((label, L) => {
      label.setAttribute("y", LANE_Y[L] - CELL / 2 - PAD - 20);
      label.setAttribute("opacity", String(span(SPLIT + 1.0 + L * 0.25, 0.5, ease.enter)(t)));
    });

    hashTag.setAttribute("opacity", String(span(C42, 0.4, ease.enter)(t) * (1 - span(ORDER - 0.3, 0.4)(t))));

    // Events: pop up in the waiting pile, fly to their log, land, scroll with their lane.
    let waitingTop = Infinity;
    let waitingCount = 0;
    for (const c of cells) {
      const { s } = c;
      if (t < s.emit) {
        c.g.setAttribute("opacity", "0");
        continue;
      }
      let x;
      let y;
      let scale = 1;
      let opacity = 1;

      if (t < s.depart) {
        const k = queueSlot(s, t);
        x = QUEUE_X;
        y = slotY(k);
        scale = popAt(s.emit)(t);
        waitingTop = Math.min(waitingTop, y);
        waitingCount += 1;
      } else if (t < s.land) {
        const era = s.single !== null ? "single" : "partition";
        const from = { x: QUEUE_X, y: SLOTS[0] };
        const to = cellPos(s, t, era);
        const p = ease.move((t - s.depart) / FLIGHT);
        const ctrl = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 - 130 };
        x = (1 - p) ** 2 * from.x + 2 * (1 - p) * p * ctrl.x + p * p * to.x;
        y = (1 - p) ** 2 * from.y + 2 * (1 - p) * p * ctrl.y + p * p * to.y;
      } else if (s.single !== null && t < SPLIT + 0.85) {
        ({ x, y } = cellPos(s, t, "single"));
        opacity = 1 - span(SPLIT, 0.45, ease.exit)(t);
      } else {
        ({ x, y } = cellPos(s, t, "partition"));
        // Appear only once the lanes have mostly slid apart, so nothing stacks mid-split.
        if (s.single !== null) opacity = span(SPLIT + 0.85, 0.5, ease.enter)(t);
        // Fade out by the time half the cell has slid past the start of its track.
        opacity *= clamp01((x - LANE_X) / (CELL / 2));
      }

      // Partition 1 is read in order: a highlight sweeps along it.
      let lift = 0;
      if (s.lane === 1 && t > ORDER && t < ACROSS) lift = bump(t, ORDER + 1.2 + (s.offset - scrollOf(1, t)) * 0.26, 0.12, 0.45);
      // Consumers reading: cells brighten as the reader passes them.
      const read = s.offset !== undefined && t > READ && (s.single === null ? t >= s.land : true) && s.offset <= readerPos(s.lane, t) + 0.01;

      const landed = t >= s.land || (s.single !== null && t >= SPLIT);
      c.g.setAttribute("opacity", String(opacity));
      c.g.setAttribute("transform", `translate(${x} ${y - lift * 10}) scale(${scale})`);

      const keyed = span(KEY + (s.lane * 8 + (s.offset ?? 0)) * 0.025, 0.35, ease.enter)(t);
      c.dot.setAttribute("opacity", String(1 - keyed));
      c.key.setAttribute("opacity", String(keyed));

      const accent = s.key === 42 ? span(C42, 0.4)(t) : 0;
      c.rect.style.fill = accent > 0.5 ? "var(--rs-accent-soft)" : "var(--rs-surface)";
      c.rect.style.stroke = accent > 0.5 || lift > 0.3 ? "var(--rs-accent)" : read ? "#c9ced8" : "var(--rs-stroke)";
      c.key.style.fill = accent > 0.5 ? "var(--rs-accent-text)" : "var(--rs-text)";

      const inSingle = s.single !== null && t < SPLIT + 0.85;
      c.offset.textContent = landed ? String(inSingle ? s.single : s.offset) : "";
      c.offset.style.fill = lift > 0.3 ? "var(--rs-text)" : "var(--rs-muted)";
    }
    waitingLabel.setAttribute("y", (Number.isFinite(waitingTop) ? waitingTop : SLOTS[0]) - CELL / 2 - 22);
    waitingLabel.setAttribute("opacity", String(waitingCount >= 2 ? 1 : 0));

    // Arrival order: numbers rise within each lane but interleave across lanes,
    // then each lane's numbers connect up, in order.
    const across = span(ACROSS + 0.6, 0.4, ease.enter)(t) * (1 - span(B5 - 0.4, 0.4, ease.exit)(t));
    arrivalKey.setAttribute("opacity", String(across));
    for (const b of badges) {
      const p = popAt(ACROSS + 0.9 + b.rank * 0.16)(t);
      const { x, y } = cellPos(b.s, t, "partition");
      b.g.setAttribute("opacity", String(clamp01(p) * across));
      b.g.setAttribute("transform", `translate(${x + CELL / 2 - 6} ${y - CELL / 2 + 6}) scale(${Math.max(0, p)})`);
    }
    connectors.forEach((line, L) => {
      const pts = badges.filter((b) => b.s.lane === L).map((b) => cellPos(b.s, t, "partition"));
      line.setAttribute("points", pts.map((p) => `${p.x + CELL / 2 - 6},${p.y - CELL / 2 + 6}`).join(" "));
      const len = pts.length > 1 ? Math.abs(pts.at(-1).x - pts[0].x) : 0;
      const d = span(ACROSS + 3.0 + L * 0.35, 0.6)(t);
      line.style.strokeDasharray = String(len);
      line.style.strokeDashoffset = String(len * (1 - d));
      line.setAttribute("opacity", String(across));
    });

    // Consumer group, one edge per partition, then readers moving in parallel.
    const boxIn = span(GROUP, 0.6, ease.enter)(t);
    box.setAttribute("opacity", String(boxIn));
    box.setAttribute("transform", `translate(0 ${(1 - boxIn) * 20})`);
    consumers.forEach((c, L) => {
      const shown = span(GROUP + 0.3 + L * 0.15, 0.5, ease.enter)(t);
      c.g.setAttribute("opacity", String(shown));
      c.g.setAttribute("transform", `translate(${(1 - shown) * 24} 0)`);
    });
    edges.forEach((e, L) => {
      const d = span(ONE + L * 0.12, 0.5)(t);
      e.line.style.strokeDasharray = String(e.length);
      e.line.style.strokeDashoffset = String(e.length * (1 - d));
      e.head.setAttribute("opacity", d >= 0.98 ? "1" : "0");
      e.g.setAttribute("opacity", d > 0 ? "1" : "0");
    });
    readers.forEach((r, L) => {
      const pos = readerPos(L, t);
      const { x } = cellPos({ lane: L, offset: pos }, t, "partition");
      r.setAttribute("x", x - (CELL - 12) / 2);
      r.setAttribute("y", LANE_Y[L] + CELL / 2 + 4);
      const shown = span(READ - 0.2, 0.3)(t);
      r.setAttribute("opacity", String(shown));
      const moving = t > READ && span(READ, 2.2)(t) < 1;
      consumers[L].rect.style.stroke = moving ? "var(--rs-accent)" : "var(--rs-stroke)";
      consumers[L].at.textContent = shown > 0 ? String(Math.floor(pos + 0.01)) : "";
    });
  };

  R.onSeek(render);
})();
