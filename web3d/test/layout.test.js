// The layout: where all 32 cards rest, for any state of the protocol, and
// which of them may show their faces.

import test from "node:test";
import assert from "node:assert/strict";
import { Vector3 } from "three";
import { cardCorners } from "../src/kinematics.js";
import { layout } from "../src/layout.js";
import { arrange } from "../src/hand.js";
import { CAMERA, CARD, ZONES, ZONES_PORTRAIT } from "../src/units.js";
import { partie } from "./partie.js";

const parties = await Promise.all([[3, 7], [1, 11], [2, 23], [3, 404]].map(([level, seed]) => partie(level, seed)));
const states = parties.flat();
const EYE = new Vector3(...CAMERA.position);
const UP = new Vector3(0, 1, 0);
const normal = (p) => new Vector3(0, 0, 1).applyQuaternion(p.quaternion);

function mayKnow(s) {
  const known = new Set([...s.hand, ...s.discards]);
  for (const t of s.tricks_played) [t.led, t.followed].forEach((c) => known.add(c));
  if (s.trick) [s.trick.led, s.trick.followed].filter(Boolean).forEach((c) => known.add(c));
  if (s.prompt.kind === "choose_dealer") {
    s.events.filter((e) => e.kind === "cut").slice(-2).forEach((e) => known.add(e.card));
  }
  return known;
}

const count = (slots, zone) => slots.filter((x) => x.zone === zone).length;

test(`every state of four parties (${states.length} states) lays out exactly 32 cards`, () => {
  for (const s of states) assert.equal(layout(s).length, 32, `${s.phase}/${s.prompt.kind}`);
});

test("each zone holds what the state says it holds", () => {
  for (const s of states) {
    const slots = layout(s);
    if (s.phase === "cut") {
      const shown = s.prompt.kind === "choose_dealer" ? 2 : 0;
      assert.equal(count(slots, "pack"), 32 - shown);
      assert.equal(count(slots, "cut"), shown);
      continue;
    }
    // One of theirs in every finished trick, and perhaps one on the table now.
    const inPlay = s.trick && (s.trick.leader === "them" || s.trick.followed) ? 1 : 0;
    const theirPlayed = s.tricks_played.length + inPlay;
    assert.equal(count(slots, "your-hand"), s.hand.length);
    assert.equal(count(slots, "their-hand"), 12 - theirPlayed, `their hand at ${s.phase}`);
    assert.equal(count(slots, "talon"), s.talon_remaining);
    assert.equal(count(slots, "your-discards"), s.discards.length);
    assert.equal(count(slots, "their-discards"), s.their_discards);
    const inTrick = s.trick ? [s.trick.led, s.trick.followed].filter(Boolean).length : 0;
    assert.equal(count(slots, "trick"), inTrick);
    const won = (who) => 2 * s.tricks_played.filter((t) => t.winner === who).length;
    assert.equal(count(slots, "your-tricks"), won("you"));
    assert.equal(count(slots, "their-tricks"), won("them"));
  }
});

test("no card shows a face the human could not see at a real table", () => {
  for (const s of states) {
    const slots = layout(s);
    const known = mayKnow(s);
    const codes = slots.map((x) => x.code).filter(Boolean);
    assert.equal(new Set(codes).size, codes.length, "each face once");
    for (const x of slots) {
      if (["their-hand", "talon", "their-discards", "pack"].includes(x.zone)) {
        assert.equal(x.code, null, `a face in ${x.zone} at ${s.phase}`);
      }
      if (x.code) assert.ok(known.has(x.code), `${x.code} in ${x.zone} is not the human's to know`);
    }
    // And everything they may know that is on the table or in hand is shown.
    for (const c of s.hand) assert.ok(codes.includes(c));
  }
});

test("cards face the right way: tricks up, piles down, your hand to you, theirs away", () => {
  for (const s of states) {
    for (const x of layout(s)) {
      const n = normal(x.pose);
      const toEye = EYE.clone().sub(x.pose.position).normalize();
      if (["trick", "your-tricks", "their-tricks", "cut"].includes(x.zone)) assert.ok(n.dot(UP) > 0.99, x.zone);
      if (["talon", "your-discards", "their-discards", "pack"].includes(x.zone)) assert.ok(n.dot(UP) < -0.99, x.zone);
      if (x.zone === "your-hand") assert.ok(n.dot(toEye) > 0.7, "your hand faces you");
      if (x.zone === "their-hand") assert.ok(n.dot(toEye) < -0.5, "you see the backs of theirs");
    }
  }
});

// Two footprints on the table overlap: the separating-axis test on their
// corners, shrunk a hair so cards that merely touch do not count.
function footprint(pose) {
  const c = cardCorners(pose).filter((_, i) => i % 2 === 0); // one face's four corners
  const centre = c.reduce((a, p) => a.add(p), new Vector3()).multiplyScalar(0.25);
  return c.map((p) => p.clone().sub(centre).multiplyScalar(0.99).add(centre)).map((p) => [p.x, p.z]);
}
function separated(a, b) {
  for (const poly of [a, b]) {
    for (let i = 0; i < poly.length; i++) {
      const [x1, z1] = poly[i];
      const [x2, z2] = poly[(i + 1) % poly.length];
      const axis = [z1 - z2, x2 - x1];
      const project = (p) => p.map(([x, z]) => x * axis[0] + z * axis[1]);
      const pa = project(a);
      const pb = project(b);
      if (Math.max(...pa) < Math.min(...pb) || Math.max(...pb) < Math.min(...pa)) return true;
    }
  }
  return false;
}
// Where two cards overlap, one lies wholly above the other there: sample
// the overlap and compare the heights of their surfaces.
function heightAt(pose, x, z) {
  const n = normal(pose);
  const p = pose.position;
  return p.y - (n.x * (x - p.x) + n.z * (z - p.z)) / n.y;
}

for (const [name, zones, reach] of [["across the table", ZONES, 44], ["on a phone held upright", ZONES_PORTRAIT, 24]]) {
test(`resting cards never pass through one another, ${name}: overlapping ones lie a card apart`, () => {
  for (const s of states) {
    const flat = layout(s, { zones }).filter((x) => !["your-hand", "their-hand"].includes(x.zone));
    for (let i = 0; i < flat.length; i++) {
      for (let j = i + 1; j < flat.length; j++) {
        const a = flat[i].pose;
        const b = flat[j].pose;
        if (a.position.distanceTo(b.position) > 11 || separated(footprint(a), footprint(b))) continue;
        // Sample points in both footprints' overlap: the gap there must be a card or more.
        const pts = footprint(a).concat(footprint(b));
        const mid = pts.reduce(([x, z], [px, pz]) => [x + px / 8, z + pz / 8], [0, 0]);
        const gap = Math.abs(heightAt(a, ...mid) - heightAt(b, ...mid));
        assert.ok(gap >= CARD.thickness - 1e-6, `${flat[i].zone}/${flat[j].zone} interpenetrate by ${gap} at ${s.phase}`);
      }
    }
  }
});

test(`nothing rests below the table, and everything on it is within reach of the eye, ${name}`, () => {
  for (const s of states) {
    for (const x of layout(s, { zones })) {
      for (const c of cardCorners(x.pose)) assert.ok(c.y >= -1e-6, `${x.zone} below the table`);
      if (!x.zone.endsWith("hand")) {
        for (const c of cardCorners(x.pose)) {
          assert.ok(Math.abs(c.x) < reach && Math.abs(c.z) < 30, `${x.zone} off the table at ${c.x.toFixed(1)}, ${c.z.toFixed(1)}`);
        }
      }
    }
  }
});

test(`every card is laid out, faces only where known, ${name}`, () => {
  for (const s of states) {
    const slots = layout(s, { zones });
    assert.equal(slots.length, 32);
    for (const x of slots) if (["their-hand", "talon", "their-discards", "pack"].includes(x.zone)) assert.equal(x.code, null);
  }
});
}

test("the hand is fanned in the order chosen, left to right", () => {
  const s = states.find((x) => x.prompt.kind === "exchange");
  for (const sort of ["suit", "rank", "combos"]) {
    const hand = layout(s, { sort }).filter((x) => x.zone === "your-hand");
    const right = new Vector3(1, 0, 0);
    const byX = [...hand].sort((a, b) => a.pose.position.dot(right) - b.pose.position.dot(right));
    assert.deepEqual(byX.map((x) => x.code), arrange(s, sort).flat());
  }
});

test("cards chosen to throw rise out of the hand, and a pointed-at holding rises less", () => {
  const s = states.find((x) => x.prompt.kind === "exchange");
  const [a, b] = s.hand;
  const at = (opts, code) => layout(s, opts).find((x) => x.code === code).pose.position;
  const rest = at({}, a);
  const chosen = at({ selected: [a] }, a);
  const pointed = at({ lifted: [b] }, b);
  const up = (p, q) => p.clone().sub(q).length();
  assert.ok(up(chosen, rest) > 1.5, "a chosen card stands clear of the hand");
  assert.ok(up(pointed, at({}, b)) > 0.5 && up(pointed, at({}, b)) < up(chosen, rest));
});

test("cards just drawn stand a little proud of the hand", () => {
  const s = states.find((x) => x.prompt.kind === "declare");
  const drawn = s.hand[0];
  const at = (fresh) => layout(s, { fresh }).find((x) => x.code === drawn).pose.position;
  const rise = at([drawn]).distanceTo(at([]));
  assert.ok(rise > 0.3 && rise < 1.1, `rises ${rise}`);
});

test("you may pick up your own discards and look at them, and only yours", () => {
  // "Both players keep their own discards beside them and may consult them
  // during play. Neither may look at the other's." (docs/PIQUET.md)
  const s = states.find((x) => x.phase === "play" && x.discards.length >= 2);
  for (const zones of [ZONES, ZONES_PORTRAIT]) {
    const slots = layout(s, { peek: true, zones });
    const mine = slots.filter((x) => x.zone === "your-discards");
    assert.deepEqual(mine.map((x) => x.code).sort(), [...s.discards].sort());
    for (const x of mine) {
      const toEye = EYE.clone().sub(x.pose.position).normalize();
      assert.ok(normal(x.pose).dot(toEye) > 0.5, "held up, facing you");
      assert.ok(Math.min(...cardCorners(x.pose).map((c) => c.y)) > 1, "in the hand, off the table");
    }
    for (const x of slots.filter((y) => y.zone === "their-discards")) assert.equal(x.code, null);
  }
});

test("the same state always lays out the same way", () => {
  for (const s of states.slice(0, 40)) {
    const a = layout(s);
    const b = layout(s);
    a.forEach((x, i) => {
      assert.equal(x.code, b[i].code);
      assert.ok(x.pose.position.equals(b[i].pose.position));
    });
  }
});
