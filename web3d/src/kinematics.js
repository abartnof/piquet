// The motion primitives: every path a card takes, as a function of t in [0, 1]
// returning a pose { position, quaternion } (docs/TABLE3D.md section 7.2).
//
// Cards are rigid, thin and light, and almost always moved by a hand, so most
// motion is the smooth start and stop of a guided movement rather than flight.
// Nothing passes through the table: every path here keeps every corner of the
// card at or above it, and the tests hold each one to that.

import { Euler, Matrix4, Quaternion, Vector3 } from "three";
import { evenly, friction, minimumJerk } from "./easing.js";
import { CARD } from "./units.js";

const UP = new Vector3(0, 1, 0);
const HALF_PI = Math.PI / 2;

export function pose(position, quaternion = new Quaternion()) {
  return {
    position: position instanceof Vector3 ? position.clone() : new Vector3(...position),
    quaternion: quaternion.clone(),
  };
}

// A card lying flat on the table, its lowest face at `height` (the top of
// whatever it lies on). Face up it reads upright to the human -- its top
// points away from them -- and `yaw` turns it about the vertical.
export function lying({ x = 0, z = 0, height = 0, faceUp = true, yaw = 0 } = {}) {
  const quaternion = new Quaternion().setFromEuler(new Euler(faceUp ? -HALF_PI : HALF_PI, yaw, 0, "YXZ"));
  return { position: new Vector3(x, height + CARD.thickness / 2, z), quaternion };
}

// The eight corners of the card's slab, in a fixed order. The real card's
// corners are rounded inside these, so a test on them is conservative.
const CORNERS = [];
for (const sx of [-1, 1]) {
  for (const sy of [-1, 1]) {
    for (const sz of [-1, 1]) {
      CORNERS.push(new Vector3((sx * CARD.width) / 2, (sy * CARD.height) / 2, (sz * CARD.thickness) / 2));
    }
  }
}

export function cardCorners(p) {
  return CORNERS.map((c) => c.clone().applyQuaternion(p.quaternion).add(p.position));
}

function rotateAbout(p, pivot, axis, angle) {
  const turn = new Quaternion().setFromAxisAngle(axis, angle);
  return {
    position: p.position.clone().sub(pivot).applyQuaternion(turn).add(pivot),
    quaternion: turn.multiply(p.quaternion),
  };
}

// Of a flat card's four edges, the one lying furthest in `toward` (a
// horizontal direction): its outward direction, and its distance from the
// centre.
function edgeToward(p, toward) {
  const want = new Vector3(toward.x, 0, toward.z).normalize();
  const across = new Vector3(1, 0, 0).applyQuaternion(p.quaternion).setY(0).normalize();
  const along = new Vector3(0, 1, 0).applyQuaternion(p.quaternion).setY(0).normalize();
  const edges = [
    [across, CARD.width / 2],
    [across.clone().negate(), CARD.width / 2],
    [along, CARD.height / 2],
    [along.clone().negate(), CARD.height / 2],
  ];
  const [side, half] = edges.reduce((best, e) => (e[0].dot(want) > best[0].dot(want) ? e : best));
  return { side, half };
}

// Turning about a card's edge as it lies on the table: the hinge line, and the
// axis whose positive turn lifts the rest of the card off the table.
function hingeOf(p, side, half) {
  const pivot = p.position.clone().addScaledVector(side, half);
  pivot.y = p.position.y - CARD.thickness / 2;
  const axis = new Vector3().crossVectors(side.clone().negate(), UP).normalize();
  return { pivot, axis };
}

function quadratic(a, c, b, s) {
  const u = 1 - s;
  return a.clone().multiplyScalar(u * u).addScaledVector(c, 2 * u * s).addScaledVector(b, s * s);
}

function cubic(a, c1, c2, b, s) {
  const u = 1 - s;
  return a
    .clone()
    .multiplyScalar(u * u * u)
    .addScaledVector(c1, 3 * u * u * s)
    .addScaledVector(c2, 3 * u * s * s)
    .addScaledVector(b, s * s * s);
}

// How high a carried card arcs over the chord between its two ends: enough to
// clear whatever lies between, never less than three centimetres.
const clearanceFor = (a, b) => Math.max(3, 0.25 * a.distanceTo(b));

// Hand-guided, from one pose to another, along an arc. Both the travel and the
// turn follow minimum jerk, and the turn is finished by `turnBy` of the time,
// so the card arrives already at its final attitude and is set down rather
// than rotated into place.
export function transfer(from, to, { clearance, ease = minimumJerk, turnBy = 0.85 } = {}) {
  const a = from.position.clone();
  const b = to.position.clone();
  const h = clearance ?? clearanceFor(a, b);
  const control = a.clone().add(b).multiplyScalar(0.5).addScaledVector(UP, 2 * h); // apex h above the chord
  return (t) => ({
    position: quadratic(a, control, b, ease(t)),
    quaternion: from.quaternion.clone().slerp(to.quaternion, ease(Math.min(1, t / turnBy))),
  });
}

// From the hand to the table: a transfer that leaves up and out of the hand
// and finishes with a vertical drop, so the card meets the table
// face-parallel. Paper does not bounce.
export function layDown(from, to, { clearance, ease = minimumJerk, turnBy = 0.85 } = {}) {
  const a = from.position.clone();
  const b = to.position.clone();
  const h = clearance ?? clearanceFor(a, b);
  const outward = b.clone().sub(a).setY(0).multiplyScalar(0.35);
  const c1 = a.clone().add(outward).addScaledVector(UP, 0.6 * h);
  const c2 = b.clone().addScaledVector(UP, h);
  return (t) => ({
    position: cubic(a, c1, c2, b, ease(t)),
    quaternion: from.quaternion.clone().slerp(to.quaternion, ease(Math.min(1, t / turnBy))),
  });
}

// From the table to a hand: lift the near edge first, hinged on the far one,
// the way a fingertip gets under a card; then carry it. `toward` points from
// the card to whoever is picking it up.
export function pickUp(from, to, { toward, lift = (20 * Math.PI) / 180, liftShare = 0.25 } = {}) {
  const { side, half } = edgeToward(from, toward.clone().negate()); // the far edge
  const { pivot, axis } = hingeOf(from, side, half);
  const lifted = rotateAbout(from, pivot, axis, lift);
  const carry = transfer(lifted, to);
  return (t) =>
    t < liftShare
      ? rotateAbout(from, pivot, axis, lift * minimumJerk(t / liftShare))
      : carry((t - liftShare) / (1 - liftShare));
}

// Turning a card over on the table (Andrew: "one side must be constrained by
// the table"). It turns about its edge lying furthest in `toward` and ends one
// width over, the other side up.
//
// A card rolls over its own thickness: it pivots on one bottom corner of the
// edge until it stands upright, then on the other as it falls, so it never
// sinks into the table and lands exactly at its height. Rising, a finger's
// push dies away and it slows, evenly, to `crest` times its mean rising speed
// as it passes upright -- slowest there, but never stopped, or it would hang;
// falling, gravity speeds it evenly from that same speed, so there is no jolt
// at the top. The fall takes `1 - riseShare` of the time.
export function flip(from, { toward, riseShare = 1 / 1.6, crest = 0.3 } = {}) {
  const { side, half } = edgeToward(from, toward);
  const { pivot, axis } = hingeOf(from, side, half);
  const upright = rotateAbout(from, pivot, axis, HALF_PI);
  const secondPivot = pivot.clone().addScaledVector(side, CARD.thickness);
  const rise = evenly(2 - crest);
  const fall = evenly((crest * (1 - riseShare)) / riseShare); // the same angular speed at the crest
  return (t) => {
    if (t < riseShare) return rotateAbout(from, pivot, axis, HALF_PI * rise(t / riseShare));
    return rotateAbout(upright, secondPivot, axis, HALF_PI * fall((t - riseShare) / (1 - riseShare)));
  };
}

// Pushed across the table and let go: flat all the way, slowing evenly under
// friction to a dead stop.
export function slide(from, to, { ease = friction } = {}) {
  return (t) => {
    const s = ease(t);
    return {
      position: from.position.clone().lerp(to.position, s),
      quaternion: from.quaternion.clone().slerp(to.quaternion, s),
    };
  };
}

// A hand held up and fanned toward `facing` (its holder's eye, or a point in
// front of them): the cards turn about a pivot `radius` below the hand's
// centre, `spread` apart, each `step` in front of the one before so every
// corner index shows; the whole hand leans back by `tilt`.
export function fan({
  count,
  centre,
  facing,
  radius = 16,
  spread = (6.2 * Math.PI) / 180,
  tilt = (14 * Math.PI) / 180,
  step = 0.06,
}) {
  const forward = facing.clone().sub(centre).normalize();
  const right = new Vector3().crossVectors(UP, forward).normalize();
  const up = new Vector3().crossVectors(forward, right);
  const frame = new Quaternion().setFromRotationMatrix(new Matrix4().makeBasis(right, up, forward));
  frame.multiply(new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), -tilt));
  const poses = [];
  for (let i = 0; i < count; i++) {
    const theta = (i - (count - 1) / 2) * spread;
    const local = new Vector3(radius * Math.sin(theta), radius * Math.cos(theta) - radius, i * step);
    poses.push({
      position: local.applyQuaternion(frame).add(centre),
      quaternion: frame.clone().multiply(new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), -theta)),
    });
  }
  return poses;
}
