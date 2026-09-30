// Bodies made of cards, for the dancers and the card people: joints as
// nested groups, each card given a place on the body, and eased there from
// wherever it lies. The prototype's unit was a card's height, and so is ours:
// U = 8.89 cm, so its proportions carry over at the table's real scale.

import { CircleGeometry, Euler, Group, Mesh, Quaternion, TorusGeometry, Vector3 } from "three";
import { CARD } from "../units.js";
import { clamp, lowestCorner } from "./physics.js";

export const U = CARD.height;
const EO = (t) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);

export function joint(parent, x, y, z) {
  const g = new Group();
  g.position.set(x, y, z);
  g.rotation.order = "YXZ";
  parent.add(g);
  return g;
}

// A card's place on a body: its part, position, turn and scale there.
export function slot(card, part, [x, y, z], [rx = 0, ry = 0, rz = 0] = [], [sx = 1, sy = 1] = [], delay = 0) {
  return { card, part, p: new Vector3(x, y, z), q: new Quaternion().setFromEuler(new Euler(rx, ry, rz, "YXZ")), s: new Vector3(sx, sy, 1), delay };
}

// Hand every card to its part, keeping it where it is in the world, and
// remember where it started.
export function begin(slots) {
  slots[0]?.part.updateWorldMatrix(true, true);
  for (const s of slots) {
    s.part.attach(s.card);
    s.sp = s.card.position.clone();
    s.sq = s.card.quaternion.clone();
    s.ss = s.card.scale.clone();
  }
}

// Ease each card to its place: off with a flick, up over an arc, and home.
export function step(slots, t, t0, length, arc) {
  for (const s of slots) {
    const u = (t - t0 - s.delay) / length;
    if (u <= 0) continue;
    const k = clamp(u, 0, 1);
    const e = EO(k);
    s.card.position.lerpVectors(s.sp, s.p, e);
    s.card.position.y += Math.sin(Math.PI * k) * arc;
    s.card.quaternion.copy(s.sq).slerp(s.q, e);
    s.card.scale.lerpVectors(s.ss, s.s, e);
    // Turning as it rises, a card could swing a corner into the table: it
    // never does -- it rides up by just enough.
    const low = lowestCorner(s.card);
    if (low < 0.05) {
      s.card.parent.getWorldQuaternion(TURN);
      s.card.position.add(LIFT.set(0, 0.05 - low, 0).applyQuaternion(TURN.invert()));
    }
  }
}
const TURN = new Quaternion();
const LIFT = new Vector3();

// A little face in the ink: two eyes and a smile.
export function face(parent, [x, y, z], material) {
  const g = joint(parent, x, y, z);
  const eye = new CircleGeometry(0.05 * U, 12);
  for (const side of [-1, 1]) {
    const e = new Mesh(eye, material);
    e.position.set(side * 0.15 * U, 0.14 * U, 0);
    g.add(e);
  }
  const smile = new Mesh(new TorusGeometry(0.16 * U, 0.022 * U, 6, 16, Math.PI), material);
  smile.rotation.z = Math.PI;
  smile.position.set(0, -0.08 * U, 0);
  g.add(smile);
  g.visible = false;
  return g;
}
