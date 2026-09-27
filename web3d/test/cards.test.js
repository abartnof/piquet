// The card's geometry: a thin rounded slab with a face, a back and an edge.

import test from "node:test";
import assert from "node:assert/strict";
import { cardGeometry } from "../src/cards.js";
import { CARD } from "../src/units.js";

// Attributes are Float32: about seven significant figures.
const EPS = 1e-6;
const geometry = cardGeometry();
const pos = geometry.getAttribute("position");
const nrm = geometry.getAttribute("normal");
const uv = geometry.getAttribute("uv");
const ink = geometry.getAttribute("outlineNormal");
const index = geometry.getIndex();

function vertices(group) {
  const seen = new Set();
  for (let i = group.start; i < group.start + group.count; i++) seen.add(index.getX(i));
  return [...seen];
}

const [face, back, edge] = geometry.groups;

test("three groups, in order: face, back, edge", () => {
  assert.equal(geometry.groups.length, 3);
  assert.deepEqual(geometry.groups.map((g) => g.materialIndex), [0, 1, 2]);
});

test("every vertex lies within the card, and the slab is one card thick", () => {
  for (let i = 0; i < pos.count; i++) {
    assert.ok(Math.abs(pos.getX(i)) <= CARD.width / 2 + EPS);
    assert.ok(Math.abs(pos.getY(i)) <= CARD.height / 2 + EPS);
    assert.ok(Math.abs(Math.abs(pos.getZ(i)) - CARD.thickness / 2) < EPS);
  }
});

test("the face looks along +z and the back along -z", () => {
  for (const v of vertices(face)) assert.deepEqual([nrm.getX(v), nrm.getY(v), nrm.getZ(v)], [0, 0, 1]);
  for (const v of vertices(back)) assert.deepEqual([nrm.getX(v), nrm.getY(v), nrm.getZ(v)], [0, 0, -1]);
});

function windingZ(group) {
  // Signed area of every triangle, as seen from +z.
  const areas = [];
  for (let i = group.start; i < group.start + group.count; i += 3) {
    const [a, b, c] = [index.getX(i), index.getX(i + 1), index.getX(i + 2)];
    const ux = pos.getX(b) - pos.getX(a), uy = pos.getY(b) - pos.getY(a);
    const vx = pos.getX(c) - pos.getX(a), vy = pos.getY(c) - pos.getY(a);
    areas.push(ux * vy - uy * vx);
  }
  return areas;
}

test("face triangles wind counter-clockwise seen from the front, back ones from behind", () => {
  assert.ok(windingZ(face).every((a) => a > 0));
  assert.ok(windingZ(back).every((a) => a < 0));
});

test("the face's texture is upright: u runs right and v runs up", () => {
  for (const v of vertices(face)) {
    assert.ok(Math.abs(uv.getX(v) - (pos.getX(v) / CARD.width + 0.5)) < EPS);
    assert.ok(Math.abs(uv.getY(v) - (pos.getY(v) / CARD.height + 0.5)) < EPS);
  }
});

test("the back's texture is not mirrored when the card is seen from behind", () => {
  // From behind, +x is the viewer's left, so u must run the other way.
  for (const v of vertices(back)) {
    assert.ok(Math.abs(uv.getX(v) - (0.5 - pos.getX(v) / CARD.width)) < EPS);
  }
});

test("outline normals lie in the card's plane and point out of it", () => {
  // The ink line is pushed out within the plane of the card, never along its
  // face normal: on a slab this thin, face normals would push the near and
  // far rims in opposite directions and the line would vanish at a grazing
  // angle.
  for (let i = 0; i < ink.count; i++) {
    const [x, y, z] = [ink.getX(i), ink.getY(i), ink.getZ(i)];
    assert.equal(z, 0);
    const length = Math.hypot(x, y);
    const onRim = Math.abs(pos.getX(i)) > EPS || Math.abs(pos.getY(i)) > EPS;
    if (!onRim) {
      assert.equal(length, 0); // the centre of the fan stays put
      continue;
    }
    assert.ok(Math.abs(length - 1) < EPS);
    assert.ok(x * pos.getX(i) + y * pos.getY(i) > 0, "points outward");
  }
});

test("the edge faces outward, all the way round", () => {
  for (let i = edge.start; i < edge.start + edge.count; i += 3) {
    const [a, b, c] = [index.getX(i), index.getX(i + 1), index.getX(i + 2)];
    const p = (k) => [pos.getX(k), pos.getY(k), pos.getZ(k)];
    const [A, B, C] = [p(a), p(b), p(c)];
    const u = B.map((v, j) => v - A[j]);
    const w = C.map((v, j) => v - A[j]);
    const n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const mid = [(A[0] + B[0] + C[0]) / 3, (A[1] + B[1] + C[1]) / 3];
    assert.ok(n[0] * mid[0] + n[1] * mid[1] > 0);
  }
});
