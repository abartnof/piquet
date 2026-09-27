// How the table looks from the chair: the hands held as people hold cards,
// and nothing on the table hidden behind your own hand (Andrew, playing the
// first 3D build: "the cards the user holds overlap visually with the cards
// on the table").

import test from "node:test";
import assert from "node:assert/strict";
import { Vector3 } from "three";
import { cardCorners } from "../src/kinematics.js";
import { cameraFor, framing } from "../src/framing.js";
import { layout } from "../src/layout.js";
import { ZONES, ZONES_PORTRAIT } from "../src/units.js";
import { partie } from "./partie.js";

const DEG = Math.PI / 180;
const states = (await Promise.all([[3, 7], [1, 11], [2, 23]].map(([l, s]) => partie(l, s)))).flat();
const normal = (p) => new Vector3(0, 0, 1).applyQuaternion(p.quaternion);
// The angle between a card's face and the table top, in degrees.
const toTable = (p) => 90 - Math.asin(Math.min(1, Math.abs(normal(p).y))) / DEG;

// Window shapes: a laptop, a wide screen, a tablet across; a phone and a
// tablet upright.
const ACROSS = [1.6, 1.78, 1.33];
const UPRIGHT = [0.46, 0.75];
// The information column's share of the width, across the table.
const INSET = 0.25;
const insetFor = (aspect) => (framing(aspect).upright ? 0 : INSET);
const zonesFor = (aspect) => (framing(aspect).upright ? ZONES_PORTRAIT : ZONES);

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

for (const aspect of [...ACROSS, ...UPRIGHT]) {
  test(`nothing on the table hides behind your hand, at ${aspect}:1`, () => {
    const camera = cameraFor(aspect, insetFor(aspect));
    const zones = zonesFor(aspect);
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
    const camera = cameraFor(aspect, insetFor(aspect));
    const zones = zonesFor(aspect);
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
    const inset = insetFor(aspect);
    const camera = cameraFor(aspect, inset);
    const zones = zonesFor(aspect);
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
