// How the table looks from the chair: the hands held as people hold cards,
// and nothing on the table hidden behind your own hand (Andrew, playing the
// first 3D build: "the cards the user holds overlap visually with the cards
// on the table").

import test from "node:test";
import assert from "node:assert/strict";
import { Vector3 } from "three";
import { cardCorners } from "../src/kinematics.js";
import { cameraFor, framing, STRIPS } from "../src/framing.js";
import { layout } from "../src/layout.js";
import { CAMERA_PORTRAIT, ZONES, ZONES_PORTRAIT } from "../src/units.js";
import { partie } from "./partie.js";

const DEG = Math.PI / 180;
const states = (await Promise.all([[3, 7], [1, 11], [2, 23]].map(([l, s]) => partie(l, s)))).flat();
const normal = (p) => new Vector3(0, 0, 1).applyQuaternion(p.quaternion);
// The angle between a card's face and the table top, in degrees.
const toTable = (p) => 90 - Math.asin(Math.min(1, Math.abs(normal(p).y))) / DEG;

// Window shapes: a laptop, a wide screen, a tablet across.
const ACROSS = [1.6, 1.78, 1.33];
// The information column's share of the width, across the table.
const INSET = 0.25;

test("across the table, both hands are held at 75 degrees, leaning back toward their holders", () => {
  for (const s of states) {
    for (const x of layout(s)) {
      if (!x.zone.endsWith("hand")) continue;
      const n = normal(x.pose);
      assert.ok(Math.abs(toTable(x.pose) - 75) < 1, `${x.zone} at ${toTable(x.pose).toFixed(1)} degrees`);
      assert.ok(n.y > 0, `${x.zone}: the face tilts up, toward its holder's eyes`);
      if (x.zone === "your-hand") assert.ok(n.z > 0, "your cards face you");
      else assert.ok(n.z < 0, "theirs face them");
    }
  }
});

// A card's face as the eye sees it: four corners in normalised device
// coordinates, x right and y up, each from -1 to 1 across the window.
function onScreen(pose, camera) {
  return cardCorners(pose)
    .filter((_, i) => i % 2 === 1) // the face's four corners
    .map((c) => c.clone().project(camera))
    .map((p) => [p.x, p.y]);
}

// Two convex outlines overlap unless some edge of one separates them.
function overlap(a, b) {
  for (const poly of [a, b]) {
    for (let i = 0; i < poly.length; i++) {
      const [x1, y1] = poly[i];
      const [x2, y2] = poly[(i + 1) % poly.length];
      const axis = [y1 - y2, x2 - x1];
      const along = (p) => p.map(([x, y]) => x * axis[0] + y * axis[1]);
      const [pa, pb] = [along(a), along(b)];
      if (Math.max(...pa) <= Math.min(...pb) || Math.max(...pb) <= Math.min(...pa)) return false;
    }
  }
  return true;
}

// The corners in order round the face, for the separating-axis test.
const outline = (q) => [q[0], q[1], q[3], q[2]];

for (const aspect of ACROSS) {
  test(`nothing on the table hides behind your hand, at ${aspect}:1`, () => {
    const camera = cameraFor(aspect, INSET);
    const zones = ZONES;
    for (const s of states) {
      // Every card raised as if chosen to throw, the highest a held card
      // stands: whichever one it is, it must not cover the table.
      const slots = layout(s, { zones, selected: s.hand, eye: camera.position });
      const hand = slots.filter((x) => x.zone === "your-hand").map((x) => outline(onScreen(x.pose, camera)));
      for (const x of slots) {
        if (x.zone.endsWith("hand")) continue;
        const card = outline(onScreen(x.pose, camera));
        for (const held of hand) assert.ok(!overlap(card, held), `${x.zone} behind your hand at ${s.phase}`);
      }
    }
  });

  test(`your hand stands clear of the foot of the screen, where its controls go, at ${aspect}:1`, () => {
    const camera = cameraFor(aspect, INSET);
    const zones = ZONES;
    for (const s of states) {
      for (const x of layout(s, { zones, eye: camera.position })) {
        if (x.zone !== "your-hand") continue;
        for (const [, py] of onScreen(x.pose, camera)) {
          assert.ok(py > -0.72, `your hand reaches ${py.toFixed(2)}: the bottom 14% belongs to its controls`);
        }
      }
    }
  });

  test(`everything lies in the play area, clear of the information column, at ${aspect}:1`, () => {
    const inset = INSET;
    const camera = cameraFor(aspect, inset);
    const zones = ZONES;
    for (const s of states) {
      for (const x of layout(s, { zones, eye: camera.position })) {
        for (const [px, py] of onScreen(x.pose, camera)) {
          assert.ok(px > -1 + 2 * inset + 0.02 && px < 0.98, `${x.zone} at x ${px.toFixed(2)}, outside the play area`);
          assert.ok(py < 0.9, `${x.zone} at y ${py.toFixed(2)}, under the top bar`);
        }
      }
    }
  });
}

// ---- a phone, held upright ---------------------------------------------------
//
// The compact overlay's strips are a fixed number of CSS pixels -- the
// information along the top, the controls at the foot -- so the table is
// framed into whatever height they leave, and a shorter window leaves it
// less. Windows as the browser gives them: an iPhone's 390 x 844, and as
// Safari leaves it under its bars; an old small phone; an Android; a tablet.
const PHONES = [[390, 844], [390, 664], [375, 667], [412, 915], [768, 1024]];
// Every order the hand can be sorted in: more groups fan it wider.
const SORTS = ["auto", "suit", "rank", "combos"];
const bands = (height) => ({ top: 1 - (2 * STRIPS.top) / height, foot: -1 + (2 * STRIPS.foot) / height });

// The upright eye fits its field to `reach`, so the reach must be the
// table's own: nothing beyond it, and no slack to waste on a small screen.
test("the upright eye's reach is how far the table's cards reach", () => {
  const eye = new Vector3(...CAMERA_PORTRAIT.position);
  const ahead = new Vector3(...CAMERA_PORTRAIT.target).sub(eye).normalize();
  const right = new Vector3().crossVectors(ahead, new Vector3(0, 1, 0)).normalize();
  const up = new Vector3().crossVectors(right, ahead);
  const seen = { up: -Infinity, down: Infinity, across: 0 };
  for (const s of states) {
    for (const x of SORTS.flatMap((sort) => layout(s, { zones: ZONES_PORTRAIT, selected: s.hand, eye, sort }))) {
      for (const corner of cardCorners(x.pose).filter((_, i) => i % 2 === 1)) {
        const d = corner.clone().sub(eye);
        const [tx, ty] = [d.dot(right) / d.dot(ahead), d.dot(up) / d.dot(ahead)];
        seen.up = Math.max(seen.up, ty);
        seen.down = Math.min(seen.down, ty);
        seen.across = Math.max(seen.across, Math.abs(tx));
      }
    }
  }
  const { reach } = CAMERA_PORTRAIT;
  // What the reach should be: the table's, rounded outward.
  const should = JSON.stringify({ up: Math.ceil(seen.up * 1e3) / 1e3, down: Math.floor(seen.down * 1e3) / 1e3, across: Math.ceil(seen.across * 1e3) / 1e3 });
  for (const k of ["up", "across"]) assert.ok(seen[k] <= reach[k] && seen[k] > reach[k] - 0.01, `reach.${k}: the table's is ${should}`);
  assert.ok(seen.down >= reach.down && seen.down < reach.down + 0.01, `reach.down: the table's is ${should}`);
});

for (const [w, h] of PHONES) {
  const aspect = w / h;
  const camera = cameraFor(aspect, 0, h);
  const place = (s, extra = {}) => layout(s, { zones: ZONES_PORTRAIT, eye: camera.position, ...extra });

  test(`on a ${w} x ${h} phone, the table lies between the information and the controls`, () => {
    assert.ok(framing(aspect, 0, h).upright);
    const { top, foot } = bands(h);
    for (const s of states) {
      for (const x of SORTS.flatMap((sort) => place(s, { selected: s.hand, sort }))) {
        for (const [px, py] of onScreen(x.pose, camera)) {
          assert.ok(py < top + 1e-6, `${x.zone} at y ${py.toFixed(3)}, under the information (${top.toFixed(3)}) at ${s.phase}`);
          assert.ok(py > foot - 1e-6, `${x.zone} at y ${py.toFixed(3)}, under the controls (${foot.toFixed(3)}) at ${s.phase}`);
          assert.ok(Math.abs(px) < 0.98, `${x.zone} at x ${px.toFixed(3)}, off the side at ${s.phase}`);
        }
      }
    }
  });

  test(`on a ${w} x ${h} phone, nothing on the table hides behind your hand`, () => {
    for (const s of states) {
      for (const sort of SORTS) {
        const slots = place(s, { selected: s.hand, sort });
        const hand = slots.filter((x) => x.zone === "your-hand").map((x) => outline(onScreen(x.pose, camera)));
        for (const x of slots) {
          if (x.zone.endsWith("hand")) continue;
          const card = outline(onScreen(x.pose, camera));
          for (const held of hand) assert.ok(!overlap(card, held), `${x.zone} behind your hand at ${s.phase}, sorted by ${sort}`);
        }
      }
    }
  });
}

// Andrew's phone notes: "the hand is small". On the reference phone its
// cards stand well over twice the corner index they carry, and the table's
// cards are big enough to tell apart at a glance.
test("on a phone, your hand and the table's cards are big enough to read", () => {
  const [w, h] = PHONES[0];
  const camera = cameraFor(w / h, 0, h);
  const px = (corners, axis) => ((Math.max(...corners.map((c) => c[axis])) - Math.min(...corners.map((c) => c[axis]))) / 2) * h;
  const held = [];
  const lying = [];
  for (const s of states) {
    for (const x of layout(s, { zones: ZONES_PORTRAIT, eye: camera.position })) {
      const corners = onScreen(x.pose, camera);
      if (x.zone === "your-hand") held.push(px(corners, 1));
      else if (!x.zone.endsWith("hand")) lying.push(px(corners, 0));
    }
  }
  const median = (a) => a.sort((p, q) => p - q)[Math.floor(a.length / 2)];
  assert.ok(median(held) >= 110, `your cards stand ${median(held).toFixed(0)} px tall`);
  assert.ok(median(lying) >= 48, `the table's cards are ${median(lying).toFixed(0)} px wide`);
});
