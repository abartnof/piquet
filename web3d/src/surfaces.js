// The table top: procedural monochrome patterns, after the user's spec
// (docs/TABLE3D.md, "Table surface patterns"). A single ink drawn over a
// flat light base into a 1024-pixel tile, which repeats across an unlit
// table; no image assets. One pattern is chosen at random when the
// page opens, and kept while it is open unless the player picks another.
//
// plan(pattern) is pure -- where every mark goes, including the twins that
// complete a mark cut by the tile's edge -- so the tests can hold it to
// tiling seamlessly; drawSurface() only strokes that plan onto a canvas.

export const TILE = 1024; // px, one repeat of the pattern
export const BASE = "#edeef0";
const INK = [20, 22, 26];
const DEG = Math.PI / 180;

// A small seeded generator (mulberry32), so a pattern is the same everywhere.
export class Rng {
  constructor(seed) {
    this.state = seed >>> 0;
  }
  next() {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  // Uniform in [-1, 1).
  spread() {
    return this.next() * 2 - 1;
  }
}

const seedOf = (id) => [...id].reduce((h, ch) => Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0, 2166136261);

// The spec's eighteen, in its order. `size` is a mark's whole extent in px.
export const PATTERNS = Object.freeze([
  { id: "plain", name: "Plain", layout: "none" },
  { id: "orthographic", name: "Orthographic grid", layout: "lines", angles: [0, 90], spacing: 64, lineWidth: 1, opacity: 0.09 },
  { id: "dot-grid", name: "Dot grid", layout: "grid", shape: "dot", spacing: 46, size: 4.8, opacity: 0.28 },
  { id: "pip-diamonds", name: "Pip diamonds", layout: "stagger", shape: "diamond", spacing: 113, size: 25, lineWidth: 1.6, opacity: 0.28 },
  { id: "crosshatch", name: "Crosshatch", layout: "lines", angles: [45, -45], spacing: 10, lineWidth: 1, opacity: 0.14 },
  { id: "seat-fleck", name: "Seat fleck", layout: "grid", shape: "tick", spacing: 39, density: 0.45, size: 13, lineWidth: 1.6, rotJitter: Math.PI, opacity: 0.32 },
  { id: "transit-confetti", name: "Transit confetti", layout: "grid", shape: "plus", shape2: "dash", mix: 0.5, spacing: 46, density: 0.55, size: 10, lineWidth: 1.6, rotJitter: 0.15, opacity: 0.3 },
  { id: "pinpoint", name: "Pinpoint grid", layout: "grid", shape: "dot", spacing: 40, size: 4, opacity: 0.32 },
  { id: "staggered-rings", name: "Staggered rings", layout: "stagger", shape: "ring", spacing: 60, size: 18, lineWidth: 1.4, opacity: 0.18 },
  { id: "diamond-grid", name: "Diamond outline grid", layout: "grid", shape: "diamond", spacing: 48, size: 16, lineWidth: 1.4, opacity: 0.18 },
  { id: "diamond-dots", name: "Filled diamond dots", layout: "grid", shape: "diamond", fill: true, spacing: 60, size: 12, opacity: 0.24 },
  { id: "grain", name: "Fine grain scatter", layout: "scatter", shape: "dot", count: 500, size: 2, opacity: 0.35 },
  { id: "weave", name: "Grid weave", layout: "lines", angles: [0, 90], spacing: 20, lineWidth: 1.6, opacity: 0.14 },
  { id: "tick-repeat", name: "Staggered tick repeat", layout: "stagger", shape: "tick", spacing: 44, density: 0.6, posJitter: 10, rotJitter: 69 * DEG, size: 14, lineWidth: 1.6, opacity: 0.24 },
  { id: "asterisks", name: "Asterisk grid repeat", layout: "grid", shape: "asterisk", spacing: 46, density: 0.6, posJitter: 8, rotJitter: 34 * DEG, size: 16, lineWidth: 1.6, opacity: 0.22 },
  { id: "sparkles", name: "Sparse sparkle repeat", layout: "stagger", shape: "sparkle", spacing: 60, density: 0.45, posJitter: 10, rotJitter: 46 * DEG, size: 18, lineWidth: 1.4, opacity: 0.18 },
  { id: "flowers", name: "Sparse flower repeat", layout: "stagger", shape: "flower", fill: true, spacing: 64, density: 0.4, posJitter: 10, rotJitter: Math.PI, size: 18, opacity: 0.18 },
  { id: "hex-dots", name: "Hexagon and dot mix", layout: "stagger", shape: "hex", shape2: "dot", mix: 0.35, spacing: 56, density: 0.5, posJitter: 10, rotJitter: 57 * DEG, size: 28, lineWidth: 1.3, opacity: 0.18 },
]);

// The pattern to lay: the player's own pick if they made one; else `saved`,
// if the caller keeps one; else a new one at random. The page draws one
// at random as it opens and keeps it while it is open (the user: "a single
// table top is chosen- at random- when the user opens the html. but it
// never changes (unless manually it's changed)").
export function chooseSurface({ chosen, saved, random = Math.random }) {
  const known = (id) => PATTERNS.some((p) => p.id === id);
  if (known(chosen)) return chosen;
  if (known(saved)) return saved;
  return PATTERNS[Math.min(PATTERNS.length - 1, Math.floor(random() * PATTERNS.length))].id;
}

// Everything a pattern draws, as lines and marks in tile pixels.
export function plan(pattern) {
  if (pattern.layout === "none") return [];
  if (pattern.layout === "lines") return lineFamilies(pattern);
  const rng = new Rng(seedOf(pattern.id));
  const placed = pattern.layout === "scatter" ? scattered(pattern, rng) : lattice(pattern, rng);
  // A mark cut by an edge is completed by its twin one tile over.
  const out = [];
  for (const m of placed) {
    const reach = m.size + (m.lineWidth ?? 0);
    for (const dx of [-TILE, 0, TILE]) {
      for (const dy of [-TILE, 0, TILE]) {
        const [x, y] = [m.x + dx, m.y + dy];
        if (x > -reach && x < TILE + reach && y > -reach && y < TILE + reach) out.push({ ...m, x, y });
      }
    }
  }
  return out;
}

function ink(pattern) {
  return { opacity: pattern.opacity, lineWidth: pattern.lineWidth ?? 1, fill: !!pattern.fill };
}

// Parallel families of straight lines, spaced so the tile repeats exactly.
function lineFamilies(pattern) {
  const out = [];
  for (const angle of pattern.angles) {
    if (angle === 0 || angle === 90) {
      const gap = TILE / Math.round(TILE / pattern.spacing);
      for (let c = 0; c < TILE; c += gap) {
        out.push(angle === 0
          ? { kind: "line", x1: 0, y1: c, x2: TILE, y2: c, ...ink(pattern) }
          : { kind: "line", x1: c, y1: 0, x2: c, y2: TILE, ...ink(pattern) });
      }
    } else {
      // Diagonals meet the edge every spacing·√2; that must divide the tile.
      const gap = TILE / Math.round(TILE / (pattern.spacing * Math.SQRT2));
      const rising = angle > 0;
      for (let c = -TILE; c <= 2 * TILE; c += gap) {
        out.push(rising
          ? { kind: "line", x1: c, y1: TILE, x2: c + TILE, y2: 0, ...ink(pattern) }
          : { kind: "line", x1: c, y1: 0, x2: c + TILE, y2: TILE, ...ink(pattern) });
      }
    }
  }
  return out;
}

function mark(pattern, rng, x, y) {
  const shape = pattern.shape2 && rng.next() < (pattern.mix ?? 0) ? pattern.shape2 : pattern.shape;
  const angle = (pattern.angle ?? 0) + rng.spread() * (pattern.rotJitter ?? 0);
  const jitter = pattern.posJitter ?? 0;
  return {
    kind: "mark",
    shape,
    x: x + rng.spread() * jitter,
    y: y + rng.spread() * jitter,
    angle,
    size: pattern.size,
    ...ink(pattern),
    // A dot mixed into an outline pattern is solid, and small.
    ...(shape === "dot" && pattern.shape !== "dot" ? { fill: true, size: pattern.size * 0.22 } : {}),
  };
}

// A regular lattice, rows offset by half a cell if staggered, thinned by
// density; its cell fits the tile a whole number of times (an even number
// of rows when staggered, so the offset rows line up across the edge).
function lattice(pattern, rng) {
  const stagger = pattern.layout === "stagger";
  let n = Math.max(1, Math.round(TILE / pattern.spacing));
  if (stagger && n % 2) n += 1;
  const gap = TILE / n;
  const out = [];
  for (let row = 0; row < n; row++) {
    for (let col = 0; col < n; col++) {
      const keep = rng.next() < (pattern.density ?? 1);
      const x = (col + 0.5 + (stagger && row % 2 ? 0.5 : 0)) * gap;
      const m = mark(pattern, rng, x % TILE, (row + 0.5) * gap);
      if (keep) out.push(m);
    }
  }
  return out;
}

function scattered(pattern, rng) {
  return Array.from({ length: pattern.count }, () => mark(pattern, rng, rng.next() * TILE, rng.next() * TILE));
}

// ---- drawing (a browser's canvas) ------------------------------------------

export function drawSurface(canvas, pattern) {
  canvas.width = TILE;
  canvas.height = TILE;
  const g = canvas.getContext("2d");
  g.fillStyle = BASE;
  g.fillRect(0, 0, TILE, TILE);
  g.lineCap = "round";
  g.lineJoin = "round";
  for (const item of plan(pattern)) {
    const colour = `rgba(${INK.join(",")},${item.opacity})`;
    g.strokeStyle = colour;
    g.fillStyle = colour;
    g.lineWidth = item.lineWidth;
    if (item.kind === "line") {
      g.beginPath();
      g.moveTo(item.x1, item.y1);
      g.lineTo(item.x2, item.y2);
      g.stroke();
      continue;
    }
    g.save();
    g.translate(item.x, item.y);
    g.rotate(item.angle);
    drawMark(g, item);
    g.restore();
  }
  return canvas;
}

function drawMark(g, { shape, size, fill }) {
  const r = size / 2;
  const spokes = (n) => {
    g.beginPath();
    for (let i = 0; i < n; i++) {
      const a = (i * Math.PI) / n;
      g.moveTo(-r * Math.cos(a), -r * Math.sin(a));
      g.lineTo(r * Math.cos(a), r * Math.sin(a));
    }
    g.stroke();
  };
  const dot = (x, y, radius) => {
    g.beginPath();
    g.arc(x, y, radius, 0, 2 * Math.PI);
    g.fill();
  };
  switch (shape) {
    case "dot":
      dot(0, 0, r);
      break;
    case "ring":
      g.beginPath();
      g.arc(0, 0, r, 0, 2 * Math.PI);
      g.stroke();
      break;
    case "diamond": // taller than wide, like the suit's pip
      g.beginPath();
      g.moveTo(0, -r);
      g.lineTo(0.7 * r, 0);
      g.lineTo(0, r);
      g.lineTo(-0.7 * r, 0);
      g.closePath();
      if (fill) g.fill();
      else g.stroke();
      break;
    case "tick":
    case "dash":
      spokes(1);
      break;
    case "plus":
      spokes(2);
      break;
    case "asterisk":
      spokes(3);
      break;
    case "sparkle":
      spokes(4);
      break;
    case "flower":
      dot(0, 0, 0.24 * r);
      for (let i = 0; i < 5; i++) {
        const a = (i * 2 * Math.PI) / 5;
        dot(0.64 * r * Math.cos(a), 0.64 * r * Math.sin(a), 0.2 * r);
      }
      break;
    case "hex":
      g.beginPath();
      for (let i = 0; i < 6; i++) {
        const a = (i * Math.PI) / 3;
        g[i ? "lineTo" : "moveTo"](r * Math.cos(a), r * Math.sin(a));
      }
      g.closePath();
      g.stroke();
      break;
  }
}
