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

// A card played from a held hand. Andrew, watching the first build: "there's
// sort of a sharp tug pulling the card from the deck, and then it's placed on
// the table". So two beats: the fingers snap it out along its own length,
// clear of its neighbours and still at the hand's angle -- fast from the
// first instant, slowing as it comes free -- and then it is tossed onto its
// spot (toss). The toss begins a little before the tug has finished, so the
// card never stops dead between the two.
export function pull(from, to, { tug = 0.6 * CARD.height, tugShare = 0.3, overlap = 0.1 } = {}) {
  const out = new Vector3(0, 1, 0).applyQuaternion(from.quaternion).multiplyScalar(tug);
  const clear = { position: from.position.clone().add(out), quaternion: from.quaternion.clone() };
  const carry = toss(clear, to);
  const carryFrom = tugShare - overlap;
  const snap = (u) => 1 - (1 - u) ** 3; // at full speed at once, easing as it comes clear
  return (t) => {
    const a = snap(Math.min(1, Math.max(0, t / tugShare)));
    const c = carry(Math.min(1, Math.max(0, (t - carryFrom) / (1 - carryFrom))));
    return {
      position: from.position.clone().addScaledVector(out, a).add(c.position).sub(clear.position),
      quaternion: c.quaternion,
    };
  };
}

// A card tossed onto the table. Andrew: "moving cards should start with
// strong jerks, then end with gravity-like acceleration. that means a lot of
// motion-easing." So it is thrown, not guided: it leaves at full speed,
// rises and falls on a parabola -- a cartoon's gravity, strong enough that
// the arc is only `clearance` high -- turning flat on the way, lands with
// the speed of its fall, and slides the last little way to a dead stop
// against friction, its speed along the table unbroken at the touch.
//
// The arc is solved exactly: with the top `clearance` above the higher end,
// in the flight's own time the fall is g = 2(√a + √b)² and the launch
// 2√a(√a + √b), a and b the drops from the top to each end.
export function toss(from, to, { clearance, flight = 0.86, turnBy = 0.8 } = {}) {
  const a = from.position.clone();
  const b = to.position.clone();
  // A card that turns over on the way needs the room to turn in.
  const over = new Vector3(0, 0, 1).applyQuaternion(from.quaternion).dot(new Vector3(0, 0, 1).applyQuaternion(to.quaternion)) < 0;
  const h = Math.max(clearance ?? clearanceFor(a, b), over ? 0.6 * CARD.height : 0);
  const top = Math.max(a.y, b.y) + h;
  const [up, down] = [Math.sqrt(top - a.y), Math.sqrt(top - b.y)];
  const g = 2 * (up + down) ** 2;
  const launch = 2 * up * (up + down);
  // Where it touches down, short of its spot by as far as it then slides: a
  // slide under friction starts at twice its mean speed, so matching the
  // flight's speed along the table fixes the distance.
  const along = new Vector3(b.x - a.x, 0, b.z - a.z);
  const reach = along.length();
  const slid = (reach * (1 - flight)) / (1 + flight);
  if (reach > 0) along.divideScalar(reach);
  const touch = b.clone().addScaledVector(along, -slid);
  // The flight carries the jerk; the turn eases in once the card is on its
  // way and out before it lands, so no edge swings into the table.
  const turn = (u) => minimumJerk((u - 0.05) / (turnBy - 0.05));
  return (t) => {
    if (t < flight) {
      const u = t / flight;
      const position = new Vector3(a.x + (touch.x - a.x) * u, a.y + launch * u - (g * u * u) / 2, a.z + (touch.z - a.z) * u);
      return { position, quaternion: from.quaternion.clone().slerp(to.quaternion, turn(u)) };
    }
    const u = Math.min(1, (t - flight) / (1 - flight));
    return { position: touch.clone().lerp(b, friction(u)), quaternion: to.quaternion.clone() };
  };
}

// A card taken up into a hand: flicked up at full speed and slowing under
// gravity to rest in the grip, as anything thrown upward slows at the top of
// its rise -- the toss's own curve, with the hand at the top of the arc.
export function rise(from, to) {
  const a = from.position.clone();
  const b = to.position.clone();
  const lift = Math.max(0, b.y - a.y);
  // It turns once it is clear of the table, not before.
  const turn = (u) => minimumJerk((u - 0.15) / 0.7);
  return (t) => {
    const u = Math.min(1, Math.max(0, t));
    const across = friction(u); // along the table too: fast away, easing in
    const position = new Vector3(a.x + (b.x - a.x) * across, a.y + lift * (2 * u - u * u), a.z + (b.z - a.z) * across);
    return { position, quaternion: from.quaternion.clone().slerp(to.quaternion, turn(u)) };
  };
}

// A held card bobbed up out of its hand along its own length and back --
// what a player's hand does as they call a holding (Andrew: "the cards
// should rise from the deck a bit"). Flicked up, held a moment, and let
// fall back into place, faster and faster.
export function bob(held, lift, { riseShare = 0.28, holdShare = 0.4 } = {}) {
  const up = new Vector3(0, 1, 0).applyQuaternion(held.quaternion);
  const height = (t) => {
    if (t < riseShare) return 1 - (1 - t / riseShare) ** 3;
    if (t < riseShare + holdShare) return 1;
    const u = (t - riseShare - holdShare) / (1 - riseShare - holdShare);
    return 1 - Math.min(1, u) ** 2;
  };
  return (t) => ({
    position: held.position.clone().addScaledVector(up, lift * height(Math.min(1, Math.max(0, t)))),
    quaternion: held.quaternion.clone(),
  });
}

// From the table to a hand: lift the near edge first, hinged on the far one,
// the way a fingertip gets under a card; then carry it. `toward` points from
// the card to whoever is picking it up.
export function pickUp(from, to, { toward, lift = (20 * Math.PI) / 180, liftShare = 0.25 } = {}) {
  const { side, half } = edgeToward(from, toward.clone().negate()); // the far edge
  const { pivot, axis } = hingeOf(from, side, half);
  const lifted = rotateAbout(from, pivot, axis, lift);
  const carry = rise(lifted, to);
  const snap = (u) => 1 - (1 - u) ** 3; // the fingertip's flick
  return (t) =>
    t < liftShare
      ? rotateAbout(from, pivot, axis, lift * snap(t / liftShare))
      : carry((t - liftShare) / (1 - liftShare));
}

// Turning a card over on the table (Andrew: "one side must be constrained by
// the table"). It turns about its edge lying furthest in `toward` and ends one
// width over, the other side up. A flip is a pile of one; see flipPile.
export function flip(from, options = {}) {
  return flipPile([from], options)[0];
}

// A squared pile turned over on the table as one rigid block, about its
// bottom card's edge lying furthest in `toward`.
//
// A block rolls over its own thickness: it pivots on one bottom corner of the
// edge until it stands upright, then on the other as it falls, so it never
// sinks into the table and lands exactly at its height, its order reversed.
// Rising, a finger's push dies away and it slows, evenly, to `crest` times its
// mean rising speed as it passes upright -- slowest there, but never stopped,
// or it would hang; falling, gravity speeds it evenly from that same speed, so
// there is no jolt at the top. The fall takes `1 - riseShare` of the time.
export function flipPile(poses, { toward, riseShare = 1 / 1.6, crest = 0.3 } = {}) {
  const bottom = poses.reduce((low, p) => (p.position.y < low.position.y ? p : low));
  const { side, half } = edgeToward(bottom, toward);
  const { pivot, axis } = hingeOf(bottom, side, half);
  const top = Math.max(...poses.map((p) => p.position.y)) + CARD.thickness / 2;
  const secondPivot = pivot.clone().addScaledVector(side, top - pivot.y);
  const rise = evenly(2 - crest);
  const fall = evenly((crest * (1 - riseShare)) / riseShare); // the same angular speed at the crest
  return poses.map((from) => {
    const upright = rotateAbout(from, pivot, axis, HALF_PI);
    return (t) => {
      if (t < riseShare) return rotateAbout(from, pivot, axis, HALF_PI * rise(t / riseShare));
      return rotateAbout(upright, secondPivot, axis, HALF_PI * fall((t - riseShare) / (1 - riseShare)));
    };
  });
}

// Pushed across the table and let go: slowing evenly under friction to a
// dead stop. It rides `lift` above the table at the middle of its way and
// settles onto its place, so it passes over whatever it crosses rather than
// through it -- two cards at one height fight over which is drawn, and the
// ink and the shading break up (Andrew: "one card should always be on top").
export function slide(from, to, { ease = friction, lift = 0 } = {}) {
  return (t) => {
    const s = ease(t);
    const u = Math.min(1, Math.max(0, t));
    return {
      position: from.position.clone().lerp(to.position, s).addScaledVector(UP, 4 * lift * u * (1 - u)),
      quaternion: from.quaternion.clone().slerp(to.quaternion, s),
    };
  };
}

// A hand held up and fanned toward `facing` (its holder's eye, or a point in
// front of them): the cards turn about a pivot `radius` below the hand's
// centre, `spread` apart -- or at the given `angles` -- each `step` in front
// of the one before so every corner index shows; the whole hand leans back by
// `tilt`.
export function fan({
  count,
  angles,
  centre,
  facing,
  radius = 16,
  spread = (6.2 * Math.PI) / 180,
  tilt = (14 * Math.PI) / 180,
  step = 0.06,
}) {
  const turns = angles ?? Array.from({ length: count }, (_, i) => (i - (count - 1) / 2) * spread);
  const forward = facing.clone().sub(centre).normalize();
  const right = new Vector3().crossVectors(UP, forward).normalize();
  const up = new Vector3().crossVectors(forward, right);
  const frame = new Quaternion().setFromRotationMatrix(new Matrix4().makeBasis(right, up, forward));
  frame.multiply(new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), -tilt));
  const poses = [];
  for (let i = 0; i < turns.length; i++) {
    const theta = turns[i];
    const local = new Vector3(radius * Math.sin(theta), radius * Math.cos(theta) - radius, i * step);
    poses.push({
      position: local.applyQuaternion(frame).add(centre),
      quaternion: frame.clone().multiply(new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), -theta)),
    });
  }
  return poses;
}

// A pose held: the path of a card that waits its turn.
export function still(p) {
  return () => ({ position: p.position.clone(), quaternion: p.quaternion.clone() });
}

// Paths one after another: chain([path, weight], ...), each running for its
// weight's share of the time.
export function chain(...parts) {
  const total = parts.reduce((sum, [, w]) => sum + w, 0);
  return (t) => {
    let start = 0;
    for (let i = 0; i < parts.length; i++) {
      const [path, w] = parts[i];
      const end = start + w / total;
      if (t <= end || i === parts.length - 1) return path(Math.min(1, Math.max(0, (t - start) / (end - start))));
      start = end;
    }
    return parts[parts.length - 1][0](1);
  };
}

// Where a card must lie, the other side up, for flip(_, { toward }) to land
// it exactly on `target`: one extent plus a thickness back from it, turned
// half over about the hinge's direction. (A half turn is its own inverse.)
export function beforeFlip(target, toward) {
  const { side, half } = edgeToward(target, toward.clone().negate());
  const outward = side.clone().negate(); // the direction the flip will travel
  const axis = new Vector3().crossVectors(outward.clone().negate(), UP).normalize();
  const turn = new Quaternion().setFromAxisAngle(axis, Math.PI);
  return {
    position: target.position.clone().addScaledVector(outward, -(2 * half + CARD.thickness)),
    quaternion: turn.multiply(target.quaternion.clone()),
  };
}
