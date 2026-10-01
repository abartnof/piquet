// How the table looks from the chair: the hands held as people hold cards,
// and nothing on the table hidden behind your own hand (the user, playing the
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
// A held card stands highest when it is raised, and that happens only while
// the hand is being judged: chosen to throw in the exchange (when your side
// of the table is still bare), pointed at from the worth card while you
// declare. Once play begins nothing is raised.
const raised = (s) =>
  s.prompt.kind === "exchange" ? { selected: s.hand } : s.prompt.kind === "declare" ? { lifted: s.hand } : {};
const bands = (height, strips = STRIPS) => ({ top: 1 - (2 * strips.top) / height, foot: -1 + (2 * strips.foot) / height });
// The strips as the page measures them, which follow what is on show: the
// score alone and the bare question in play, up to the tallest -- the
// explanation, what your hand is worth, a hint and three calls to choose
// from.
const STRIP_SETS = [STRIPS, { top: 100, foot: 96 }, { top: 214, foot: 230 }];

// The upright eye fits its field to `reach`, so the reach must be the
// table's own: nothing beyond it, and no slack to waste on a small screen.
test("the upright eye's reach is how far the table's cards reach", () => {
  const eye = new Vector3(...CAMERA_PORTRAIT.position);
  const ahead = new Vector3(...CAMERA_PORTRAIT.target).sub(eye).normalize();
  const right = new Vector3().crossVectors(ahead, new Vector3(0, 1, 0)).normalize();
  const up = new Vector3().crossVectors(right, ahead);
  const seen = { up: -Infinity, down: Infinity, across: 0 };
  for (const s of states) {
    for (const x of SORTS.flatMap((sort) => layout(s, { zones: ZONES_PORTRAIT, ...raised(s), eye, sort }))) {
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

  for (const strips of STRIP_SETS) {
    test(`on a ${w} x ${h} phone, the table lies between the information and the controls, ${strips.top} and ${strips.foot} px tall`, () => {
      assert.ok(framing(aspect, 0, h, strips).upright);
      const framed = cameraFor(aspect, 0, h, strips);
      const { fill } = framing(aspect, 0, h, strips);
      const { top, foot } = bands(h, strips);
      for (const s of states) {
        for (const sort of SORTS) {
          const slots = layout(s, { zones: ZONES_PORTRAIT, eye: framed.position, ...raised(s), sort, fill });
          for (const x of slots) {
            for (const [px, py] of onScreen(x.pose, framed)) {
              assert.ok(py < top + 1e-6, `${x.zone} at y ${py.toFixed(3)}, under the information (${top.toFixed(3)}) at ${s.phase}`);
              assert.ok(py > foot - 1e-6, `${x.zone} at y ${py.toFixed(3)}, under the controls (${foot.toFixed(3)}) at ${s.phase}`);
              assert.ok(Math.abs(px) < 0.99, `${x.zone} at x ${px.toFixed(3)}, off the side at ${s.phase} (fill ${fill.toFixed(2)})`);
            }
          }
          // And the fan, drawn out, still hides nothing on the table.
          const hand = slots.filter((x) => x.zone === "your-hand").map((x) => outline(onScreen(x.pose, framed)));
          for (const x of slots) {
            if (x.zone.endsWith("hand")) continue;
            const card = outline(onScreen(x.pose, framed));
            for (const held of hand) assert.ok(!overlap(card, held), `${x.zone} behind your hand at ${s.phase}, fill ${fill.toFixed(2)}`);
          }
        }
      }
    });
  }

  test(`on a ${w} x ${h} phone, nothing on the table hides behind your hand`, () => {
    for (const s of states) {
      for (const sort of SORTS) {
        const slots = place(s, { ...raised(s), sort });
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

// ---- a phone, held sideways --------------------------------------------------
//
// The information runs down the left and the controls down the right, so the
// table is the phone's stacked one, framed in the middle between them at the
// window's full height (the user: "fix horizontal mode ... make use of all
// white space possible"). An iPhone under Safari's bars and without them, an
// old small phone, a large one.
const SIDEWAYS = [[852, 353], [844, 390], [667, 375], [932, 430]];
const SIDES = [{ left: 236, right: 236 }, { left: 200, right: 260 }];
const EDGES = { top: 8, foot: 8 };
for (const [w, h] of SIDEWAYS) {
  for (const sides of SIDES) {
    test(`on a ${w} x ${h} phone held sideways, the table lies between the columns, ${sides.left} and ${sides.right} px`, () => {
      const aspect = w / h;
      assert.ok(framing(aspect, 0, h, EDGES, sides).upright, "the stacked table");
      const camera = cameraFor(aspect, 0, h, EDGES, sides);
      const { fill } = framing(aspect, 0, h, EDGES, sides);
      const { top, foot } = bands(h, EDGES);
      const [left, right] = [-1 + (2 * sides.left) / w, 1 - (2 * sides.right) / w];
      for (const s of states) {
        for (const x of SORTS.flatMap((sort) => layout(s, { zones: ZONES_PORTRAIT, eye: camera.position, ...raised(s), sort, fill }))) {
          for (const [px, py] of onScreen(x.pose, camera)) {
            assert.ok(py < top + 1e-6 && py > foot - 1e-6, `${x.zone} at y ${py.toFixed(3)}, off the top or foot at ${s.phase}`);
            assert.ok(px > left - 1e-6 && px < right + 1e-6, `${x.zone} at x ${px.toFixed(3)}, under a column (${left.toFixed(3)}, ${right.toFixed(3)}) at ${s.phase}`);
          }
        }
      }
    });
  }
}

// The hand's own reach across, and the rate it grows as its fan is drawn
// out, are what framing.js counts on to fill the width without overrunning.
test("the hand's reach across, and how it grows with the fill, are as framing.js assumes", () => {
  const eye = new Vector3(...CAMERA_PORTRAIT.position);
  const ahead = new Vector3(...CAMERA_PORTRAIT.target).sub(eye).normalize();
  const right = new Vector3().crossVectors(ahead, new Vector3(0, 1, 0)).normalize();
  const { hand } = CAMERA_PORTRAIT;
  for (const fill of [1, 1.2, 1.6, 2, 2.4]) {
    let across = 0;
    for (const s of states) {
      for (const x of SORTS.flatMap((sort) => layout(s, { zones: ZONES_PORTRAIT, ...raised(s), eye, sort, fill }))) {
        if (x.zone !== "your-hand") continue;
        for (const c of cardCorners(x.pose).filter((_, i) => i % 2 === 1)) {
          const d = c.clone().sub(eye);
          across = Math.max(across, Math.abs(d.dot(right) / d.dot(ahead)));
        }
      }
    }
    const allowed = hand.across + hand.perFill * (fill - 1);
    assert.ok(across <= allowed + 1e-6, `at fill ${fill} the hand reaches ${across.toFixed(4)}, beyond ${allowed.toFixed(4)}`);
    if (fill === 1) assert.ok(across > hand.across - 0.003, `the hand reaches ${across.toFixed(4)}: hand.across should be its own`);
  }
});

// The user's phone notes: "the hand is small". On the reference phone its
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
