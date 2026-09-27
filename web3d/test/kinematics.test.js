// The motion primitives: every path a card can take, and the physical promises
// each one keeps (docs/TABLE3D.md section 7.2).

import test from "node:test";
import assert from "node:assert/strict";
import { Quaternion, Vector3 } from "three";
import {
  beforeFlip,
  cardCorners,
  chain,
  fan,
  flip,
  flipPile,
  layDown,
  lying,
  pickUp,
  pose,
  slide,
  still,
  transfer,
} from "../src/kinematics.js";
import { CARD } from "../src/units.js";

const DEG = Math.PI / 180;
const T = Array.from({ length: 401 }, (_, i) => i / 400);
const EPS = 1e-6;

const lowest = (p) => Math.min(...cardCorners(p).map((c) => c.y));
const near = (a, b, eps = 1e-6) => a.distanceTo(b) <= eps;
const sameTurn = (a, b, eps = 1e-6) => Math.abs(Math.abs(a.dot(b)) - 1) <= eps;
const normal = (p) => new Vector3(0, 0, 1).applyQuaternion(p.quaternion);
const top = (p) => new Vector3(0, 1, 0).applyQuaternion(p.quaternion);

test("a card lying on the table has its lowest point exactly at its stack height", () => {
  const p = lying({ x: 3, z: -4, height: 0.5, faceUp: true, yaw: 30 * DEG });
  assert.ok(Math.abs(lowest(p) - 0.5) < EPS);
  assert.ok(normal(p).y > 0.999);
  const down = lying({ x: 0, z: 0, height: 0, faceUp: false });
  assert.ok(normal(down).y < -0.999);
});

test("a face-up card lies upright to the human; yawed half a turn, upright to the opponent", () => {
  const mine = lying({ x: 0, z: 0, height: 0, faceUp: true });
  assert.ok(top(mine).z < -0.999); // its top points away from the human
  const theirs = lying({ x: 0, z: 0, height: 0, faceUp: true, yaw: Math.PI });
  assert.ok(top(theirs).z > 0.999);
});

test("a transfer starts and ends where it is told, at rest", () => {
  const a = pose([0, 15, 27], new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), -40 * DEG));
  const b = lying({ x: 0, z: 0, height: 0 });
  const path = transfer(a, b);
  assert.ok(near(path(0).position, a.position));
  assert.ok(near(path(1).position, b.position));
  assert.ok(sameTurn(path(1).quaternion, b.quaternion));
  const speed = (t) => path(t + 1e-4).position.distanceTo(path(t).position) / 1e-4;
  assert.ok(speed(0) < 0.01 && speed(1 - 1e-4) < 0.01);
});

test("a transfer arcs over whatever lies between, by at least three centimetres", () => {
  const a = lying({ x: -20, z: 0, height: 0 });
  const b = lying({ x: 20, z: 0, height: 0 });
  const path = transfer(a, b);
  const mid = path(0.5).position;
  assert.ok(mid.y >= 0.25 * 40 - EPS, `apex ${mid.y}`); // a quarter of the distance
  const short = transfer(lying({ x: 0, z: 0, height: 0 }), lying({ x: 4, z: 0, height: 0 }));
  assert.ok(short(0.5).position.y >= 3 - EPS); // never less than 3 cm
});

test("a transfer has finished turning before it arrives, so the card is set down level", () => {
  const a = pose([0, 15, 27], new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), -40 * DEG));
  const b = lying({ x: 0, z: 0, height: 0 });
  const path = transfer(a, b);
  for (const t of T.filter((t) => t >= 0.86)) assert.ok(sameTurn(path(t).quaternion, b.quaternion, 1e-9));
});

test("laying a card down ends flat at its stack height, meeting the table face-parallel", () => {
  const a = pose([6, 16, 28], new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), -35 * DEG));
  const b = lying({ x: 0, z: -3, height: 0.1, faceUp: true });
  const path = layDown(a, b);
  assert.ok(near(path(1).position, b.position));
  assert.ok(Math.abs(lowest(path(1)) - 0.1) < EPS);
  // The last stretch is a vertical approach: it drops, it does not skid.
  const p90 = path(0.9).position;
  const p100 = path(1).position;
  const horizontal = Math.hypot(p90.x - p100.x, p90.z - p100.z);
  assert.ok(horizontal < 0.2 * (p90.y - p100.y), `skids ${horizontal} while dropping ${p90.y - p100.y}`);
});

test("nothing ever passes through the table", () => {
  const held = pose([0, 15, 27], new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), -40 * DEG));
  const paths = [
    transfer(held, lying({ x: 0, z: 0, height: 0 })),
    layDown(held, lying({ x: -5, z: 2, height: 0, yaw: 20 * DEG })),
    transfer(lying({ x: -20, z: -3, height: 0.2, faceUp: false }), lying({ x: 10, z: 8, height: 0 })),
    pickUp(lying({ x: -18, z: -3, height: 0.2, faceUp: false }), held, { toward: new Vector3(0, 0, 1) }),
    flip(lying({ x: 0, z: 0, height: 0, faceUp: false }), { toward: new Vector3(1, 0, 0) }),
    flip(lying({ x: 0, z: 0, height: 0.3, faceUp: false, yaw: 90 * DEG }), { toward: new Vector3(0, 0, -1) }),
    slide(lying({ x: 0, z: 0, height: 0 }), lying({ x: 30, z: 10, height: 0, yaw: 3 * DEG })),
  ];
  paths.forEach((path, i) => {
    for (const t of T) assert.ok(lowest(path(t)) >= -EPS, `path ${i} dips to ${lowest(path(t))} at t=${t}`);
  });
});

test("a flip turns the card over along an edge that stays on the table", () => {
  const start = lying({ x: 0, z: 0, height: 0.2, faceUp: false });
  const path = flip(start, { toward: new Vector3(1, 0, 0) });
  // The edge it turns on is the one toward the right; its bottom corners stay
  // put, on the table, until the card stands on that edge.
  const before = cardCorners(start);
  const hinge = before.map((c, i) => i).filter((i) => before[i].x > 0 && before[i].y < 0.2 + EPS);
  assert.equal(hinge.length, 2);
  for (const t of T) {
    const p = path(t);
    assert.ok(lowest(p) >= 0.2 - EPS, `below its stack at t=${t}`);
    if (t <= 1 / 1.6) {
      const now = cardCorners(p);
      for (const i of hinge) assert.ok(near(now[i], before[i], 1e-6), `the hinge moved at t=${t}`);
    }
  }
  const end = path(1);
  assert.ok(normal(end).y > 0.999, "ends face up");
  assert.ok(Math.abs(lowest(end) - 0.2) < EPS, "lying at its stack height");
  const moved = end.position.x - start.position.x;
  assert.ok(Math.abs(moved - (CARD.width + CARD.thickness)) < EPS, `moved ${moved}: one width over`);
  assert.ok(Math.abs(end.position.z - start.position.z) < EPS);
});

test("a flip rises under a finger, crests without stopping, and falls under gravity", () => {
  const path = flip(lying({ x: 0, z: 0, height: 0, faceUp: false }), { toward: new Vector3(1, 0, 0) });
  const tilt = (t) => Math.acos(Math.max(-1, Math.min(1, -normal(path(t)).y))); // 0 face down, pi face up
  const rate = (t) => (tilt(Math.min(1, t + 1e-5)) - tilt(Math.max(0, t - 1e-5))) / (Math.min(1, t + 1e-5) - Math.max(0, t - 1e-5));
  const crest = 1 / 1.6;
  assert.ok(Math.abs(tilt(crest) - Math.PI / 2) < 1e-6, "upright at the crest");
  // Slowing as it rises, slowest at the crest -- but never stopped there: a
  // finger pushing a card over keeps it moving through the top.
  assert.ok(rate(0.1) > rate(0.3) && rate(0.3) > rate(0.5));
  const top = rate(crest);
  assert.ok(top > 0.15 * rate(0) && top < 0.5 * rate(0), `crest speed ${top} against ${rate(0)}`);
  for (const t of T) assert.ok(rate(t) >= top - 1e-3, `slower than the crest at t=${t}`);
  // The same speed either side of the crest: no jolt as gravity takes over.
  assert.ok(Math.abs(rate(crest - 1e-3) - rate(crest + 1e-3)) < 0.02 * top);
  // Then accelerating all the way down.
  assert.ok(rate(0.99) > rate(0.85) && rate(0.85) > rate(0.7));
});

test("picking up lifts the near edge first, hinged on the far one", () => {
  const start = lying({ x: -18, z: -3, height: 0.2, faceUp: false });
  const held = pose([0, 15, 27], new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), -40 * DEG));
  const path = pickUp(start, held, { toward: new Vector3(0, 0, 1) });
  const early = cardCorners(path(0.15));
  const far = early.filter((c) => c.z < -3).map((c) => c.y);
  const nearEdge = early.filter((c) => c.z > -3).map((c) => c.y);
  assert.ok(Math.max(...far) < 0.2 + CARD.thickness + 0.05, "the far edge stays down");
  assert.ok(Math.min(...nearEdge) > 0.5, "the near edge has lifted");
  assert.ok(near(path(1).position, held.position));
  assert.ok(sameTurn(path(1).quaternion, held.quaternion));
});

test("a slide stays flat on the table and stops dead at the end", () => {
  const a = lying({ x: 20, z: 12, height: 0 });
  const b = lying({ x: 34, z: 12, height: 0, yaw: -3 * DEG });
  const path = slide(a, b);
  for (const t of T) {
    assert.ok(Math.abs(lowest(path(t))) < 1e-6);
    assert.ok(normal(path(t)).y > 0.999);
  }
  const speed = (t) => path(Math.min(1, t + 1e-4)).position.distanceTo(path(t).position) / 1e-4;
  assert.ok(speed(0) > 20, "it starts at speed, having been pushed");
  assert.ok(speed(1 - 1e-4) < 0.05, "and friction stops it");
});

test("a fan faces its holder, each card a little in front of the last", () => {
  const eye = new Vector3(0, 55, 60);
  const cards = fan({ count: 12, centre: new Vector3(0, 15, 27), facing: eye, tilt: 14 * DEG });
  assert.equal(cards.length, 12);
  for (const c of cards) {
    const toEye = eye.clone().sub(c.position).normalize();
    assert.ok(normal(c).dot(toEye) > Math.cos(22 * DEG), "the face turns toward the holder");
  }
  for (let i = 1; i < cards.length; i++) {
    const gap = cards[i].position.clone().sub(cards[i - 1].position).dot(normal(cards[i]));
    assert.ok(gap > CARD.thickness, "in front of the one before it, never through it");
    const turn = top(cards[i - 1]).angleTo(top(cards[i]));
    assert.ok(turn > 0 && turn < 10 * DEG);
  }
  // Spread left to right as the holder sees them.
  const right = new Vector3(1, 0, 0);
  assert.ok(cards[11].position.dot(right) > cards[0].position.dot(right));
});

test("a fan of one card is the card at the centre, upright", () => {
  const [only] = fan({ count: 1, centre: new Vector3(0, 15, 27), facing: new Vector3(0, 55, 60), tilt: 0 });
  assert.ok(near(only.position, new Vector3(0, 15, 27)));
  assert.ok(top(only).y > 0.5);
});

test("a flip can be aimed: beforeFlip gives the pose it must start from to land on a target", () => {
  for (const [target, toward] of [
    [lying({ x: -5, z: 9, height: 0.02, faceUp: true, yaw: 0.07 }), new Vector3(1, 0, 0)],
    [lying({ x: 5, z: -13, height: 0.02, faceUp: true, yaw: Math.PI - 0.05 }), new Vector3(-1, 0, 0)],
    [lying({ x: 0, z: 0, height: 0.3, faceUp: false, yaw: 0.4 }), new Vector3(0, 0, 1)],
  ]) {
    const start = beforeFlip(target, toward);
    assert.ok(normal(start).y * normal(target).y < 0, "it starts the other side up");
    const end = flip(start, { toward })(1);
    assert.ok(near(end.position, target.position, 1e-6));
    assert.ok(sameTurn(end.quaternion, target.quaternion, 1e-9));
  }
});

test("chained paths run one after another, each for its share of the time", () => {
  const a = lying({ x: 0, z: 0 });
  const b = lying({ x: 10, z: 0 });
  const c = lying({ x: 10, z: 10 });
  const path = chain([slide(a, b), 1], [still(b), 1], [slide(b, c), 2]);
  assert.ok(near(path(0).position, a.position));
  assert.ok(near(path(0.25).position, b.position));
  assert.ok(near(path(0.4).position, b.position), "holding still");
  assert.ok(near(path(1).position, c.position));
  assert.ok(path(0.75).position.z > 0 && path(0.75).position.z < 10);
});

test("a squared pile turns over as one block, rolling over its own height", () => {
  const pile = Array.from({ length: 6 }, (_, i) => lying({ x: 12, z: 9, height: 0.02 + i * 0.05, faceUp: true, yaw: i % 2 ? Math.PI : 0 }));
  const paths = flipPile(pile, { toward: new Vector3(-1, 0, 0) });
  const gap = (t, a, b) => paths[a](t).position.distanceTo(paths[b](t).position);
  for (const t of T) {
    for (const path of paths) assert.ok(lowest(path(t)) >= 0.02 - EPS, `below the pile's base at t=${t}`);
    // Rigid: the cards keep their distances from one another all the way over.
    assert.ok(Math.abs(gap(t, 0, 5) - gap(0, 0, 5)) < 1e-6 && Math.abs(gap(t, 1, 4) - gap(0, 1, 4)) < 1e-6);
  }
  const end = paths.map((path) => path(1));
  for (const p of end) assert.ok(normal(p).y < -0.999, "face down");
  // The order reverses: what was on top is now at the bottom.
  assert.ok(end[5].position.y < end[0].position.y);
  assert.ok(Math.abs(Math.min(...end.map(lowest)) - 0.02) < 1e-6, "resting on the table where the pile did");
  const height = 5 * 0.05 + CARD.thickness;
  assert.ok(Math.abs(end[0].position.x - (12 - CARD.width - height)) < 1e-6, "one width and one pile-height over");
});

test("a flip is a pile of one", () => {
  const card = lying({ x: 0, z: 0, height: 0.2, faceUp: false, yaw: 0.3 });
  const toward = new Vector3(0, 0, 1);
  const [single] = flipPile([card], { toward });
  for (const t of T) {
    assert.ok(single(t).position.distanceTo(flip(card, { toward })(t).position) < 1e-9);
  }
});
