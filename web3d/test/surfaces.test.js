// The table top: eighteen procedural monochrome patterns, one chosen at
// random when a partie begins and kept while it is played (the user's spec,
// docs/TABLE3D.md). Everything but the final stroke onto a canvas is pure.

import test from "node:test";
import assert from "node:assert/strict";
import { PATTERNS, TILE, chooseSurface, plan } from "../src/surfaces.js";
import { Rng } from "../src/surfaces.js";

test("all eighteen patterns, plain first, each with a name", () => {
  assert.equal(PATTERNS.length, 18);
  assert.equal(PATTERNS[0].id, "plain");
  const ids = new Set(PATTERNS.map((p) => p.id));
  assert.equal(ids.size, 18, "ids are unique");
  for (const p of PATTERNS) assert.ok(p.name && p.name.length > 2, p.id);
});

test("plain is nothing but the base", () => {
  assert.deepEqual(plan(PATTERNS[0]), []);
});

test("every other pattern marks the tile, in ink, inside it or wrapping across its edge", () => {
  for (const p of PATTERNS.slice(1)) {
    const items = plan(p);
    assert.ok(items.length > 10, `${p.id} draws ${items.length}`);
    for (const item of items) {
      assert.ok(item.opacity > 0 && item.opacity < 1, `${p.id} ink`);
      const [x, y] = item.kind === "line" ? [item.x1, item.y1] : [item.x, item.y];
      assert.ok(Number.isFinite(x) && Number.isFinite(y), p.id);
    }
  }
});

test("the same pattern always draws the same marks", () => {
  for (const p of PATTERNS) assert.deepEqual(plan(p), plan(p), p.id);
});

// Seamless: a tile laid beside itself shows no seam. Every mark within reach
// of an edge has its twin one tile over, so a mark cut by the edge is
// completed on the other side.
test("the tiles meet without a seam", () => {
  for (const p of PATTERNS.slice(1)) {
    const marks = plan(p).filter((m) => m.kind === "mark");
    const key = (m) => `${m.shape}|${Math.round(m.x * 10)}|${Math.round(m.y * 10)}|${Math.round(m.angle * 1000)}`;
    const all = new Set(marks.map(key));
    for (const m of marks) {
      const reach = m.size + (m.lineWidth ?? 0);
      for (const [dx, dy] of [[TILE, 0], [-TILE, 0], [0, TILE], [0, -TILE]]) {
        const twin = { ...m, x: m.x + dx, y: m.y + dy };
        const straddles = twin.x > -reach && twin.x < TILE + reach && twin.y > -reach && twin.y < TILE + reach;
        if (straddles) assert.ok(all.has(key(twin)), `${p.id}: a mark at ${m.x.toFixed(1)}, ${m.y.toFixed(1)} has no twin across the edge`);
      }
    }
  }
});

test("lattices fit the tile a whole number of times", () => {
  for (const p of PATTERNS.filter((q) => q.layout === "grid" || q.layout === "stagger")) {
    const marks = plan(p).filter((m) => m.kind === "mark" && m.x >= 0 && m.x < TILE && m.y >= 0 && m.y < TILE);
    assert.ok(marks.length > 0, p.id);
  }
  // Grid lines: evenly spaced, the last a whole spacing short of the first one over.
  const grid = plan(PATTERNS.find((q) => q.id === "orthographic"));
  const xs = [...new Set(grid.filter((l) => l.x1 === l.x2).map((l) => l.x1))].sort((a, b) => a - b);
  const gap = xs[1] - xs[0];
  assert.ok(Math.abs(TILE / gap - Math.round(TILE / gap)) < 1e-9, `spacing ${gap} does not divide the tile`);
});

test("density thins a lattice, and jitter moves its marks", () => {
  const fleck = PATTERNS.find((q) => q.id === "seat-fleck");
  const inside = plan(fleck).filter((m) => m.x >= 0 && m.x < TILE && m.y >= 0 && m.y < TILE);
  const cells = Math.round(TILE / fleck.spacing) ** 2;
  const kept = inside.length / cells;
  assert.ok(kept > 0.3 && kept < 0.6, `kept ${kept.toFixed(2)} of the cells`);
  const angles = new Set(inside.map((m) => m.angle.toFixed(3)));
  assert.ok(angles.size > inside.length / 2, "ticks at their own angles");
});

test("the surface: the player's own choice; else the game's; else a new one at random", () => {
  const pick = () => 0.5; // a stand-in for Math.random
  assert.equal(chooseSurface({ chosen: "dot-grid", saved: "crosshatch", random: pick }), "dot-grid");
  assert.equal(chooseSurface({ chosen: "random", saved: "crosshatch", random: pick }), "crosshatch");
  assert.equal(chooseSurface({ chosen: "random", saved: null, random: pick }), PATTERNS[9].id);
  assert.equal(chooseSurface({ chosen: "random", saved: "no-such-pattern", random: () => 0 }), PATTERNS[0].id);
  assert.equal(chooseSurface({ chosen: "no-such", saved: null, random: () => 0.999 }), PATTERNS[17].id);
});

test("the generator is seeded, so a pattern is the same on every machine", () => {
  const [a, b] = [new Rng(7), new Rng(7)];
  for (let i = 0; i < 20; i++) assert.equal(a.next(), b.next());
  const c = new Rng(8);
  assert.notEqual(new Rng(7).next(), c.next());
});
