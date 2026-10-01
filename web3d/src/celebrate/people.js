// Card people: the pile builds six people in a queue -- legs, a body, a head
// with a little face, arms -- and the eye glides at knee height through the
// gap between every pair of legs. At the end of the queue it turns round;
// the people spin to face it, hop, wave and lean out of the queue to peek at
// it, thrilled; and the eye goes back through their legs the other way, and
// round again, for as long as you watch.
//
// From the prototype, in the user's words: "cards form people (legs, torso,
// arms, head) in a line and the camera slides between their legs" -- then
// "when you're done going through the card people's legs, the camera should
// turn around to see them peeking at you and being very excited - you go
// through their legs again, ad infinitum." Six people of six cards is
// thirty-six, so four more are dealt in from the pile as it goes.

import { Group, Vector3 } from "three";
import { PALETTE, kit } from "./kit.js";
import { hop, lerp, smooth } from "./physics.js";
import { U, begin, face, joint, slot, step } from "./body.js";

const T0 = 3.6; // s: the eye sets off
const ZS = 8 * U; // it travels between these
const ZE = -16 * U;
const TRAVEL = 8.0; // s each way
const TURN = 1.8; // s to turn round
const CYCLE = 2 * (TRAVEL + TURN);
const HIP = 1.35 * U + 0.3; // the feet a few millimetres clear of the table
const EIO = (t) => {
  const u = Math.min(1, Math.max(0, t));
  return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
};

// Where the eye is in its round: travelling, or turning, and which way.
function eyeAt(t) {
  const s = t - T0;
  if (s < 0) return null;
  const cycle = Math.floor(s / CYCLE);
  const w = s - cycle * CYCLE;
  if (w < TRAVEL) return { cycle, w, z: lerp(ZS, ZE, EIO(w / TRAVEL)), th: 0, turn: 0 };
  if (w < TRAVEL + TURN) {
    const turn = (w - TRAVEL) / TURN;
    return { cycle, w, z: ZE, th: Math.PI * EIO(turn), turn };
  }
  if (w < 2 * TRAVEL + TURN) return { cycle, w, z: lerp(ZE, ZS, EIO((w - TRAVEL - TURN) / TRAVEL)), th: Math.PI, turn: 0 };
  const turn = (w - 2 * TRAVEL - TURN) / TURN;
  return { cycle, w, z: ZS, th: Math.PI + Math.PI * EIO(turn), turn };
}

export function people(ctx) {
  const { toon } = kit(ctx.stage);
  const ink = toon(PALETTE.ink);
  const rng = ctx.random;
  const root = new Group();
  ctx.root.add(root);

  // Thirty-two from the pile; the rest dealt from its top.
  let n = 31;
  const top = ctx.cards[31].position.clone().add(new Vector3(0, 0.1, 0));
  const next = () => {
    if (n >= 0) return ctx.cards[n--];
    const card = ctx.extra();
    card.position.copy(top);
    card.quaternion.copy(ctx.cards[31].quaternion);
    return card;
  };

  const folk = [];
  const slots = [];
  for (let k = 0; k < 6; k++) {
    const person = joint(root, 0, 0, -2.2 * U - k * 2.4 * U);
    const P = { root: person, k, jitter: rng.range(0, Math.PI * 2) };
    P.hipL = joint(person, -0.42 * U, HIP, 0);
    P.hipR = joint(person, 0.42 * U, HIP, 0);
    P.upper = joint(person, 0, HIP, 0);
    P.torso = joint(P.upper, 0, 0.625 * U, 0);
    P.head = joint(P.upper, 0, 1.75 * U, 0);
    P.armL = joint(P.upper, -0.62 * U, 1.15 * U, 0);
    P.armR = joint(P.upper, 0.62 * U, 1.15 * U, 0);
    const d = k * 0.12;
    const add = (part, y, scale, delay) => slots.push(slot(next(), part, [0, y, 0], [], scale, d + delay));
    add(P.hipL, -0.675 * U, [0.5, 1.35], 0);
    add(P.hipR, -0.675 * U, [0.5, 1.35], 0.02);
    add(P.torso, 0, [1.3, 1.25], 0.04);
    add(P.head, 0, [1.0, 0.9], 0.06);
    add(P.armL, -0.575 * U, [0.42, 1.15], 0.08);
    add(P.armR, -0.575 * U, [0.42, 1.15], 0.1);
    P.face = face(P.head, [0, 0.02 * U, 0.03 * U], ink);
    folk.push(P);
  }
  // Every person's pose at time t.
  function pose(t, at, thrill, built) {
    for (const P of folk) {
      const k = P.k;
      P.face.visible = t > 1.3 + k * 0.12 + 0.9;
      const idle = Math.sin(t * 3 + P.jitter);
      P.hipL.rotation.z = -0.06 - 0.03 * idle;
      P.hipR.rotation.z = 0.06 - 0.03 * idle;
      const up = 0.5 + 0.5 * Math.sin(t * 5 + k);
      const up2 = 0.5 + 0.5 * Math.sin(t * 5 + k + Math.PI);
      P.armR.rotation.z = lerp(0.15 + 0.1 * idle, lerp(0.3, 2.6, up), thrill);
      P.armL.rotation.z = -lerp(0.15 - 0.1 * idle, lerp(0.3, 2.6, up2), thrill);
      // Leaning out of the queue to peek at the eye.
      const peek = Math.sin(t * 2.2 + k * 1.3);
      P.upper.rotation.z = 0.28 * thrill * peek;
      P.head.rotation.z = 0.06 * Math.sin(t * 2 + P.jitter) - 0.3 * thrill * peek;
      // Spinning round to face the eye at each end, one after another, with
      // a real hop.
      let yaw = 0;
      let jump = 0;
      if (at) {
        const fB = (at.w - TRAVEL - (5 - k) * 0.18) / 0.9;
        const fD = (at.w - (2 * TRAVEL + TURN) - k * 0.18) / 0.9;
        yaw = at.cycle * Math.PI * 2 + Math.PI * EIO(fB) + Math.PI * EIO(fD);
        if (fB > 0 && fB < 1) jump = hop(fB / 2) * 0.8 * U;
        if (fD > 0 && fD < 1) jump = hop(fD / 2) * 0.8 * U;
      }
      P.root.rotation.y = yaw;
      P.root.position.y = built ? hop(t * 1.4 + k * 0.37) * 0.3 * U * thrill + jump : 0;
      P.root.scale.y = 1 + 0.03 * Math.sin(t * 3 + P.jitter) * (built ? 1 : 0);
    }
  }
  // Posed before the cards are handed over, so no joint swings a card on
  // the turn.
  pose(0, null, 0, false);
  begin(slots);

  const eye = new Vector3();
  const look = new Vector3();
  return {
    update(dt, t) {
      step(slots, t, 0.5, 0.85, 0.7 * U);
      const built = t > 2.6;
      const at = eyeAt(t);
      // Thrilled, once the eye has been through them once.
      const thrill = smooth(T0 + TRAVEL - 1, T0 + TRAVEL + 1, t);
      pose(t, at, thrill, built);

      // The eye: round from the table's view down to knee height, then
      // through their legs and back, turning round at each end.
      const into = smooth(T0 - 1.3, T0, t);
      let px = 0;
      let py = 0.72 * U;
      let pz = ZS;
      let lx = 0;
      let ly = 1.5 * U;
      let lz = ZS - 4 * U;
      if (at) {
        pz = at.z;
        py = 0.72 * U + 0.45 * U * Math.sin(Math.PI * at.turn);
        lx = Math.sin(at.th) * 4 * U;
        lz = at.z - Math.cos(at.th) * 4 * U;
      }
      if (t < T0) {
        const a = 0.4 * smooth(0, T0 - 0.6, t);
        eye.set(lerp(Math.sin(a) * 9 * U, px, into), lerp(2.8 * U, py, into), lerp(Math.cos(a) * 9 * U, pz, into));
        look.set(lerp(0, lx, into), lerp(1.5 * U, ly, into), lerp(-3 * U, lz, into));
      } else {
        eye.set(px, py, pz);
        look.set(lx, ly, lz);
      }
      ctx.look(eye, look, 55);
    },
    dispose() {
      root.removeFromParent();
    },
  };
}
people.title = "Card people";
