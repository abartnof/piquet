// The Macarena: the pile builds a person entirely of cards -- torso, head, a
// hat, sunglasses of card backs, arms, legs, feet -- who dances the
// Macarena's arm sequence, swaying and hopping round on the sixteenth beat.
// Each time the eye has gone once round, another deck is thrown in from behind
// you, lands, and builds another dancer, up to ten, all in step.
//
// From the prototype, in Andrew's words: "every time the camera makes a full
// circle around the macarena dancer, another dancing card person should
// appear. they should appear as if someone threw a deck of cards off-screen,
// and when the deck hit the table, the cards formed into a person. limit this
// to 10 extra dancers." The beat is silent here; the dance keeps it.

import { Group, Vector3 } from "three";
import { kit, PALETTE } from "./kit.js";
import { G, ballistic, hop, lerp, smooth } from "./physics.js";
import { U, begin, face, joint, slot, step } from "./body.js";
import { CARD } from "../units.js";

const S = 0.62; // the dancers' cards, smaller
const CW = CARD.width * S;
const CH = CARD.height * S;
const PELVIS = 4 * CH + 0.3; // the feet a few millimetres clear of the table
const BPM = 103;
const DANCE = 3.3; // s: the first dancer starts
const PERIOD = (16 * 60) / BPM; // one lap of the eye, one round of the dance
const MORE = 10;
const THROW = 1.0; // s in the air
const EIO = (t) => {
  const u = Math.min(1, Math.max(0, t));
  return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
};
const EO = (t) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);

// The arms' poses: shoulder x, y, z, elbow x, y.
const POSE = {
  REST: [0, 0, -0.12, 0, 0],
  FD: [-1.45, 0, -0.05, 0, 0],
  FU: [-1.45, 0, -0.05, 0, Math.PI],
  XS: [-1.25, 0.95, 0, -2.3, 0],
  HEAD: [-0.35, 0, -1.5, -2.2, 0],
  XH: [-0.7, 0.75, 0, -1.1, 0],
  SH: [0.25, 0, -0.5, -0.9, 0],
  CL: [-1.3, 0.5, 0, -0.6, 0],
};
const RIGHT = ["FD", "FD", "FU", "FU", "XS", "XS", "HEAD", "HEAD", "XH", "XH", "SH", "SH", "SH", "SH", "SH", "CL"];
const LEFT = ["REST", "FD", "FD", "FU", "FU", "XS", "XS", "HEAD", "HEAD", "XH", "XH", "SH", "SH", "SH", "SH", "CL"];
const pose = (seq, k, f) => POSE[seq[k]].map((v, i) => lerp(POSE[seq[(k + 15) % 16]][i], v, EO(f * 2.5)));
function setArm(arm, p) {
  const mirror = arm.side > 0 ? -1 : 1;
  arm.shoulder.rotation.set(p[0], p[1] * mirror, p[2] * mirror);
  arm.elbow.rotation.set(p[3], p[4], 0);
}

// Where the extra dancers stand: [radius in units, angle in degrees].
const SPOTS = [[5.6, 30], [9.8, 45], [5.6, 150], [9.8, 135], [5.6, 270], [9.8, 225], [5.6, 90], [9.8, 315], [5.6, 210], [5.6, 330]];

export function macarena(ctx) {
  const { toon } = kit(ctx.stage);
  const ink = toon(PALETTE.ink);
  const rng = ctx.random;
  const root = new Group();
  ctx.root.add(root);

  function figure(x, z, next) {
    const fig = joint(root, x, 0, z);
    const torso = joint(fig, 0, PELVIS + 1.5 * CH, 0);
    const head = joint(fig, 0, PELVIS + 3 * CH + 0.04 * U + CH, 0);
    const arm = (sx) => {
      const shoulder = joint(fig, sx * (CW + CW / 2 + 0.03 * U), PELVIS + 3 * CH - 0.25 * U, 0);
      return { shoulder, elbow: joint(shoulder, 0, -2 * CH, 0), side: sx };
    };
    const armR = arm(-1);
    const armL = arm(1);
    const leg = (sx) => {
      const hip = joint(fig, sx * (CW / 2 + 0.01 * U), PELVIS, 0);
      return { hip, knee: joint(hip, 0, -2 * CH, 0) };
    };
    const legR = leg(-1);
    const legL = leg(1);
    const mouth = face(head, [0, -0.1 * U, 0.03 * U], ink);
    const slots = [];
    const add = (part, at, turn = [], scale = [S, S]) => slots.push(slot(next(), part, at, turn, scale, slots.length * 0.05));
    for (const r of [-1, 0, 1]) {
      add(torso, [-CW / 2, r * CH, 0]);
      add(torso, [CW / 2, r * CH, 0]);
    }
    for (const [px, py] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) add(head, [(px * CW) / 2, (py * CH) / 2, 0]);
    add(head, [-0.18 * U, 0.88 * U, 0], [0, 0, -0.4]); // the hat
    add(head, [0.18 * U, 0.88 * U, 0], [0, 0, 0.4]);
    add(head, [-0.19 * U, 0.12 * U, 0.05 * U], [0, Math.PI, 0], [0.3, 0.3]); // sunglasses: two card backs
    add(head, [0.19 * U, 0.12 * U, 0.05 * U], [0, Math.PI, 0], [0.3, 0.3]);
    for (const a of [armR, armL]) {
      for (const k of [0.5, 1.5]) add(a.shoulder, [0, -k * CH, 0]);
      for (const k of [0.5, 1.5]) add(a.elbow, [0, -k * CH, 0]);
    }
    for (const l of [legR, legL]) {
      for (const k of [0.5, 1.5]) add(l.hip, [0, -k * CH, 0]);
      for (const k of [0.5, 1.5]) add(l.knee, [0, -k * CH, 0]);
    }
    add(legR.knee, [0, -2 * CH + 0.2, 0.27 * U], [-Math.PI / 2, 0, 0]); // feet
    add(legL.knee, [0, -2 * CH + 0.2, 0.27 * U], [-Math.PI / 2, 0, 0]);
    return { fig, torso, head, armR, armL, legR, legL, mouth, slots, x0: x };
  }

  function dance(F, on, beat) {
    if (!on) {
      F.armR.shoulder.rotation.set(0, 0, -0.12);
      F.armL.shoulder.rotation.set(0, 0, 0.12);
      return;
    }
    const k = Math.floor(beat) % 16;
    const f = beat - Math.floor(beat);
    const turns = Math.floor(beat / 16);
    setArm(F.armR, pose(RIGHT, k, f));
    setArm(F.armL, pose(LEFT, k, f));
    const swaying = k >= 12 && k <= 14;
    const sway = swaying ? Math.sin(beat * Math.PI) * 0.25 * U : 0;
    F.torso.rotation.z = swaying ? -sway * 0.03 : 0.05 * Math.sin(beat * Math.PI);
    F.head.rotation.z = 0.06 * Math.sin(beat * Math.PI + 1);
    F.legR.hip.rotation.z = -0.04 + sway * 0.011;
    F.legL.hip.rotation.z = 0.04 + sway * 0.011;
    F.fig.position.x = F.x0 + sway;
    // Real hops: a small one every beat, a big one on the sixteenth.
    F.fig.position.y = k === 15 ? hop(f) * 0.9 * U : hop(beat) * 0.06 * U;
    F.legR.knee.rotation.x = k === 15 ? -hop(f) * 0.7 : 0;
    F.legL.knee.rotation.x = F.legR.knee.rotation.x;
    F.fig.rotation.y = (turns * Math.PI) / 2 + (k === 15 ? EIO(f) * (Math.PI / 2) : 0);
  }

  let n = 31;
  const main = figure(0, 0, () => ctx.cards[n--]);
  // Posed before the cards are handed over: a joint turned after a card is
  // attached swings the card with it, from wherever it lies.
  dance(main, false, 0);
  begin(main.slots);

  // A deck thrown in from behind you: it tumbles over twice in the air --
  // turning freely, at a steady rate, to land flat -- bounces once, rests,
  // and becomes another dancer.
  const STACK = (32 * CARD.thickness * 1.15) / 2 + 0.1;
  const others = [];
  function throwDeck(i, t) {
    const [r, deg] = SPOTS[i];
    const a = (deg * Math.PI) / 180;
    const x = Math.cos(a) * r * U;
    const z = Math.sin(a) * r * U;
    const deck = [];
    for (let k = 0; k < 32; k++) deck.push(ctx.extra());
    let m = 0;
    const F = figure(x, z, () => deck[m++]);
    const stack = new Group();
    root.add(stack);
    deck.forEach((c, k) => {
      stack.add(c);
      c.position.set(rng.range(-0.25, 0.25), (k - 15.5) * CARD.thickness * 1.15, rng.range(-0.25, 0.25));
      c.rotation.set(-Math.PI / 2, rng.range(-0.15, 0.15), 0);
    });
    const cp = ctx.camera.position;
    const back = Math.hypot(cp.x, cp.z) || 1;
    const bx = cp.x / back;
    const bz = cp.z / back;
    const side = rng.range(-6, 6) * U;
    const from = new Vector3(cp.x + bx * 9 * U - bz * side, cp.y + 3 * U, cp.z + bz * 9 * U + bx * side);
    others.push({ F, stack, pos: from.clone(), vel: ballistic(from, new Vector3(x, STACK, z), THROW), t0: t, state: "fly", landed: false, tLand: 0, tBuild: 0, yaw: rng.range(0, Math.PI * 2) });
  }
  function update(e, dt, t, beat) {
    if (e.state === "fly" || e.state === "rest") {
      e.vel.y -= G * dt;
      e.pos.addScaledVector(e.vel, dt);
      if (e.pos.y <= STACK && e.vel.y < 0) {
        e.pos.y = STACK;
        if (e.vel.y < -60) {
          e.vel.y *= -0.25;
          e.vel.x *= 0.35;
          e.vel.z *= 0.35;
        } else {
          e.vel.y = 0;
          if (!e.landed) {
            e.landed = true;
            e.tLand = t;
            e.state = "rest";
          }
        }
      }
      if (e.landed) {
        e.vel.x *= Math.exp(-6 * dt);
        e.vel.z *= Math.exp(-6 * dt);
      }
      e.stack.position.copy(e.pos);
      const tau = t - e.t0;
      e.stack.rotation.set(tau < THROW ? -Math.PI * 4 * (tau / THROW) : 0, e.yaw, 0);
      if (e.landed && t > e.tLand + 0.4) {
        dance(e.F, false, 0);
        begin(e.F.slots);
        e.state = "build";
        e.tBuild = t;
      }
    }
    if (e.state === "build") {
      step(e.F.slots, t, e.tBuild, 0.9, 0.8 * U);
      e.F.mouth.visible = t > e.tBuild + 2.6;
      dance(e.F, false, 0);
      if (t > e.tBuild + 2.7) {
        e.state = "dance";
        e.stack.removeFromParent();
      }
    }
    if (e.state === "dance") dance(e.F, true, beat);
  }

  let thrown = 0;
  let widen = 0;
  const eye = new Vector3();
  const at = new Vector3(0, 2.9 * U, 0);
  return {
    update(dt, t) {
      step(main.slots, t, 0.5, 0.9, 0.8 * U);
      main.mouth.visible = t > DANCE - 0.2;
      const bt = t - DANCE;
      const beat = Math.max(0, bt) * (BPM / 60);
      dance(main, bt >= 0, beat);
      const x = t / PERIOD;
      const lap = Math.floor(x);
      const fr = x - lap;
      if (lap > thrown && thrown < MORE) {
        throwDeck(thrown, t);
        thrown += 1;
      }
      for (const e of others) update(e, dt, t, beat);
      // One lap of the eye to one round of the dance, slower at the lap mark;
      // standing further back as the crowd grows.
      const angle = Math.PI * 2 * (lap + lerp(fr, EIO(fr), 0.55));
      widen += (thrown * 1.1 * U - widen) * Math.min(1, dt * 1.5);
      const R = lerp(9, 13, smooth(0, 2.5, t)) * U + widen;
      eye.set(Math.sin(angle) * R, lerp(3.5, 4.6, smooth(0, 2.5, t)) * U + widen * 0.25, Math.cos(angle) * R);
      ctx.look(eye, at, 45);
    },
    dispose() {
      root.removeFromParent();
    },
  };
}
macarena.title = "Macarena";
