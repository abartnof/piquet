// The physics of the celebrations: real gravity, in the table's units.
//
// The user's prototype (in git at 272ff15, web3d/reference/celebrations-prototype.html) set the
// rule these keep: "AUTHENTIC PHYSICS WHERE POSSIBLE. Things that fly must
// follow real ballistic arcs under gravity ... do not fake with sine bounces
// or straight-line tweens when a real trajectory is available." The table is
// in centimetres and seconds, and the cards are real cards, so gravity is
// the real 981 cm/s^2 -- nothing is slowed to a toy scale.

import { Euler, Quaternion, Vector3 } from "three";
import { CARD } from "../units.js";

export const G = 981; // cm/s^2
// A card lies this far above the table, as on the table in play: flush with
// it, a card fights the table and its shadow for the same pixels.
export const REST = 0.02; // cm

// The launch velocity that carries a body from p0 to p1 in T seconds under
// gravity alone.
export function ballistic(p0, p1, T) {
  return new Vector3((p1.x - p0.x) / T, (p1.y - p0.y) / T + 0.5 * G * T, (p1.z - p0.z) / T);
}

// The height of a real hop, as a share of its top, at phase f (0 to 1 is one
// hop): a parabola, not a bouncing sine.
export function hop(f) {
  const u = f - Math.floor(f);
  return 4 * u * (1 - u);
}

// An angle that eases into motion: the integral of a smooth speed ramp from
// rest at `a` to full rate (1 per second) at `b` -- an orbit that gathers
// speed rather than starting at full tilt.
export function spin(t, a, b) {
  if (t <= a) return 0;
  const span = b - a;
  if (t >= b) return span * 0.5 + (t - b);
  const u = (t - a) / span;
  return span * (u * u * u - (u * u * u * u) / 2);
}

export const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (a, b, x) => {
  const t = clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};

// A seeded generator, so a scene can be replayed exactly (tests, stills).
export function random(seed = 1) {
  let s = seed >>> 0 || 1;
  const next = () => {
    s ^= s << 13;
    s >>>= 0;
    s ^= s >>> 17;
    s ^= s << 5;
    s >>>= 0;
    return s / 4294967296;
  };
  next.range = (a, b) => a + next() * (b - a);
  next.pick = (list) => list[Math.floor(next() * list.length)];
  return next;
}

// How far a card's lowest point lies below its centre, as it is turned (and,
// if given, scaled).
const HALF = new Vector3();
const ONE = new Vector3(1, 1, 1);
export function lowestBelow(quaternion, scale = ONE) {
  let low = 0;
  for (const sx of [-1, 1]) {
    for (const sy of [-1, 1]) {
      for (const sz of [-1, 1]) {
        HALF.set((sx * CARD.width * scale.x) / 2, (sy * CARD.height * scale.y) / 2, (sz * CARD.thickness * scale.z) / 2).applyQuaternion(quaternion);
        low = Math.min(low, HALF.y);
      }
    }
  }
  return -low;
}

// Cards flung into the air: they fly under gravity, spin freely (no torque in
// the air -- the one honest constant rate), strike the table and bounce with
// some restitution and friction, and settle flat. Each body is
// { mesh, v: Vector3 (cm/s), w: Vector3 (rad/s, about x, y, z), e, grip }.
export class Flung {
  constructor() {
    this.bodies = [];
  }

  add(mesh, v, w = new Vector3(), { e = 0.35, grip = 0.8, onLand = null } = {}) {
    mesh.rotation.order = "YXZ";
    const body = { mesh, v: v.clone(), w: w.clone(), e, grip, onLand, resting: false };
    this.bodies.push(body);
    return body;
  }

  update(dt) {
    for (const b of this.bodies) {
      const m = b.mesh;
      if (b.resting) {
        // Settling: slide to a stop, turn to lie flat, face up or down.
        b.v.multiplyScalar(Math.max(0, 1 - 8 * dt));
        m.position.x += b.v.x * dt;
        m.position.z += b.v.z * dt;
        const k = Math.min(1, dt * 10);
        const flat = Math.round((m.rotation.x + Math.PI / 2) / Math.PI) * Math.PI - Math.PI / 2;
        m.rotation.x += (flat - m.rotation.x) * k;
        m.rotation.z += (Math.round(m.rotation.z / (2 * Math.PI)) * 2 * Math.PI - m.rotation.z) * k;
        // Lowered as it turns flat -- never so fast a corner dips below.
        const eased = m.position.y + (REST + CARD.thickness / 2 - m.position.y) * k;
        m.position.y = Math.max(eased, lowestBelow(m.quaternion) + REST);
        continue;
      }
      b.v.y -= G * dt;
      m.position.addScaledVector(b.v, dt);
      m.rotation.x += b.w.x * dt;
      m.rotation.y += b.w.y * dt;
      m.rotation.z += b.w.z * dt;
      m.updateMatrix();
      const low = lowestBelow(m.quaternion) + REST;
      if (m.position.y < low && b.v.y >= 0) {
        // Rising, but turning a corner into the table: the table holds it.
        m.position.y = low;
      } else if (m.position.y < low) {
        m.position.y = low;
        // Too slow to bounce: it settles where it fell.
        if (b.v.y > -60) {
          b.resting = true;
          b.v.y = 0;
        } else {
          b.v.y *= -b.e;
          b.v.x *= b.grip;
          b.v.z *= b.grip;
          b.w.multiplyScalar(0.6);
        }
        b.onLand?.(b);
      }
    }
  }
}

// How high a card's lowest corner stands above the table, wherever it is in
// the scene and however it is scaled.
const CORNERS = [];
for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) CORNERS.push(new Vector3((sx * CARD.width) / 2, (sy * CARD.height) / 2, (sz * CARD.thickness) / 2));
const CORNER = new Vector3();
export function lowestCorner(mesh) {
  mesh.updateWorldMatrix(true, false);
  let low = Infinity;
  for (const c of CORNERS) low = Math.min(low, CORNER.copy(c).applyMatrix4(mesh.matrixWorld).y);
  return low;
}

// A rotation from Euler angles in the cards' order, for scenes that pose.
export function turned(x, y, z) {
  return new Quaternion().setFromEuler(new Euler(x, y, z, "YXZ"));
}
