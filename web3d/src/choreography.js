// The choreography: how the cards get from one state to the next
// (docs/TABLE3D.md sections 5.3 and 7.3).
//
// The engine reports only the state before a human decision and the state at
// the next one; between them, its events say what happened, in order -- you
// played, they followed, they took the trick, they led. A small reducer
// replays those events into intermediate states, and each is laid out by
// `layout`, so every stage of the animation runs between two true layouts:
// the waypoints are exact, not guessed. A final settle stage lands everything
// on layout(next) whatever happened, and anything the reducer cannot follow --
// an undo, a new partie -- is a single direct transition.
//
// choreograph(prev, next, placement, view) -> { motions, placement, duration }
//
//   placement  where each of the 32 meshes is: [{ id, zone, index, code, pose }]
//   motions    [{ id, path, delay, duration, reveal }]: `reveal` is the face a
//              mesh shows from the start of its motion (a card turned up, or
//              drawn), or -- as { code: null, atEnd: true } -- the face it
//              stops showing when the motion lands (a card turned down).
//
// Faces follow the layout's rule: a mesh shows a face only when the state it
// is moving towards lets the human know that card.

import { Vector3 } from "three";
import {
  beforeFlip,
  chain,
  flip,
  flipPile,
  layDown,
  lying,
  pickUp,
  slide,
  transfer,
} from "./kinematics.js";
import { jitter, layout } from "./layout.js";
import { CARD, ZONES } from "./units.js";

// Starting points, tuned by eye; the speed setting scales them all.
export const TIMING = Object.freeze({
  play: 420,
  think: 320, // your opponent's pause before answering a card
  read: 900, // a finished trick stays a moment before it is taken
  push: 520,
  discard: 380,
  draw: 380,
  stagger: 90, // between cards moved together
  resort: 260,
  cutShow: 700,
  cutRead: 1600,
  flip: 480,
  sweep: 480,
  gather: 480,
  dealCard: 200,
  dealPair: 150, // two at a time (Cavendish): one pair after another
  dealSecond: 45, // and the second card of a pair just behind the first
  dealTalon: 70,
  pickUp: 420,
  direct: 420,
});

const REST = 0.02;
const STEP = CARD.thickness + 0.02;
const TOWARD = { you: new Vector3(0, 0, 1), them: new Vector3(0, 0, -1) };
const FACE_UP = new Set(["trick", "your-tricks", "their-tricks", "cut"]);
const ROWS = new Set(["your-tricks", "their-tricks"]);

const topOf = (pose) => new Vector3(0, 1, 0).applyQuaternion(pose.quaternion).setY(0).normalize();
const acrossOf = (pose) => new Vector3(1, 0, 0).applyQuaternion(pose.quaternion).setY(0).normalize();

// The yaw that keeps a lying card's top pointing the way it points now, face
// up or face down: 0 for upright to the human face up (or, face down, the
// way every face-down card lies), a half turn otherwise.
function yawKeeping(pose, faceUp) {
  const z = topOf(pose).z;
  return (faceUp ? z > 0 : z < 0) ? Math.PI : 0;
}

// Which way to turn a face-up card over, or to turn a face-down one up into
// `faceUpPose`, so that face down it lies the standard way -- top toward the
// human -- and nothing need spin afterwards: about a long edge if that keeps
// its top where it should be, else about a short edge, which reverses it.
// Of the two directions, the one heading towards `goal`.
function turnToward(faceUpPose, goal) {
  const top = topOf(faceUpPose);
  const direction = top.z > 0 ? acrossOf(faceUpPose) : top;
  const toGoal = goal.clone().sub(faceUpPose.position).setY(0);
  return toGoal.dot(direction) >= 0 ? direction : direction.negate();
}

// The meshes placed straight onto a layout, the first time a state is seen.
export function initialPlacement(state, view = {}) {
  return layout(state, view).map((slot, id) => ({ id, ...slot }));
}

// ---- the reducer: events into intermediate states --------------------------

function sameStart(prev, next) {
  if (!prev || prev.seed !== next.seed || prev.level !== next.level) return false;
  if (next.events.length < prev.events.length) return false;
  const last = prev.events.length - 1;
  return last < 0 || (next.events[last].kind === prev.events[last].kind && next.events[last].text === prev.events[last].text);
}

// Only what the layout reads, from `from`, with the hand's sort taken from the
// state being moved towards -- so the hand is ordered once, at the start.
function snapshot(from, next) {
  return {
    phase: from.phase,
    prompt: next.prompt,
    worth: next.worth,
    events: from.events,
    hand: [...from.hand],
    discards: [...from.discards],
    talon_remaining: from.talon_remaining,
    their_discards: from.their_discards,
    trick: from.trick ? { ...from.trick } : null,
    tricks_played: [...from.tricks_played],
  };
}

export function stagesBetween(prev, next) {
  if (!sameStart(prev, next)) return null;
  let s = snapshot(prev, next);
  const stages = [];
  let cuts = [];
  for (const e of next.events.slice(prev.events.length)) {
    switch (e.kind) {
      case "cut":
        cuts.push(e);
        if (cuts.length === 2) {
          s = { ...s, phase: "cut", prompt: { kind: "choose_dealer" }, events: [...s.events, ...cuts] };
          stages.push({ kind: "cut", state: s, cuts });
          cuts = [];
        }
        break;
      case "cut_again":
        s = { ...s, prompt: { kind: "cut" } };
        stages.push({ kind: "uncut", state: s });
        break;
      case "deal_begins":
        s = {
          ...snapshot(next, next),
          phase: "elder_exchange",
          discards: [],
          talon_remaining: 8,
          their_discards: 0,
          trick: null,
          tricks_played: [],
        };
        stages.push({ kind: "deal", state: s, dealer: e.elder === "you" ? "them" : "you" });
        break;
      case "exchanged":
        if (e.who === "them") {
          s = { ...s, their_discards: s.their_discards + e.count, talon_remaining: s.talon_remaining - e.count };
          stages.push({ kind: "their-exchange", state: s });
        }
        break;
      case "drew": {
        const kept = s.hand.filter((c) => !e.discarded.includes(c));
        s = { ...s, hand: kept, discards: [...s.discards, ...e.discarded] };
        stages.push({ kind: "discard", state: s });
        s = { ...s, hand: [...kept, ...e.drew], talon_remaining: s.talon_remaining - e.drew.length };
        stages.push({ kind: "draw", state: s });
        break;
      }
      case "played": {
        const trick = s.trick ? { ...s.trick, followed: e.card } : { leader: e.who, led: e.card, followed: null };
        s = { ...s, phase: "play", hand: e.who === "you" ? s.hand.filter((c) => c !== e.card) : s.hand, trick };
        stages.push({ kind: "play", state: s, who: e.who });
        break;
      }
      case "took_trick":
        s = { ...s, trick: null, tricks_played: [...s.tricks_played, { ...s.trick, winner: e.who }] };
        stages.push({ kind: "trick", state: s, who: e.who });
        break;
      default:
        break; // declarations, scores and the rest move no cards
    }
  }
  return stages;
}

// ---- matching meshes to slots -------------------------------------------------

// Where a zone's newcomers come from, in order of preference; zones claim in
// CLAIM order, so a card leaving a zone is claimed by where it went before
// the zone it left refills itself.
const SOURCES = {
  trick: ["their-hand", "your-hand"],
  "your-tricks": ["trick"],
  "their-tricks": ["trick"],
  "your-discards": ["your-discards", "your-hand"],
  "their-discards": ["their-discards", "their-hand"],
  cut: ["pack"],
  "your-hand": ["your-hand", "talon", "pack"],
  "their-hand": ["their-hand", "talon", "pack"],
  talon: ["talon", "pack"],
  pack: ["pack", "cut"],
};
const CLAIM = ["trick", "your-tricks", "their-tricks", "your-discards", "their-discards", "cut", "your-hand", "their-hand", "talon", "pack"];

// Which of a zone's meshes to take first when some must leave it.
function takeOrder(zone, meshes, destination) {
  const byIndex = [...meshes].sort((a, b) => a.index - b.index);
  if (zone === destination) return byIndex; // staying put: keep the order
  if (zone === "talon" || zone === "pack") return byIndex.reverse(); // off the top
  if (zone === "their-hand") {
    // A card chosen from a hand held up: not always the end one.
    const n = byIndex.length;
    const k = n ? Math.floor(((jitter(`${destination}${n}`, 1) + 1) / 2) * n) % n : 0;
    return [...byIndex.slice(k), ...byIndex.slice(0, k)];
  }
  return byIndex;
}

export function match(current, target) {
  const byCode = new Map(current.filter((m) => m.code).map((m) => [m.code, m]));
  const taken = new Set();
  const owner = new Array(target.length).fill(null);
  target.forEach((slot, k) => {
    const mesh = slot.code && byCode.get(slot.code);
    if (mesh) {
      owner[k] = mesh.id;
      taken.add(mesh.id);
    }
  });
  for (const zone of CLAIM) {
    const open = target.map((slot, k) => k).filter((k) => target[k].zone === zone && owner[k] === null);
    for (const source of SOURCES[zone]) {
      if (!open.length) break;
      const free = takeOrder(source, current.filter((m) => m.zone === source && !taken.has(m.id)), zone);
      while (open.length && free.length) {
        const mesh = free.shift();
        owner[open.shift()] = mesh.id;
        taken.add(mesh.id);
      }
    }
  }
  // Anything left over (a transition the rules above do not describe) pairs
  // up in order; the direct stage animates it plainly.
  const spare = current.filter((m) => !taken.has(m.id));
  owner.forEach((id, k) => {
    if (id === null) owner[k] = spare.shift().id;
  });
  return owner;
}

// ---- the plan: stages into motions ------------------------------------------

class Plan {
  constructor(placement, view, options) {
    this.now = placement.map((m) => ({ ...m }));
    this.view = view;
    this.zones = view.zones ?? ZONES;
    this.pause = options.pause ?? true;
    this.clock = 0;
    this.motions = [];
  }

  add(mesh, path, delay, duration, reveal) {
    this.motions.push({ id: mesh.id, path, delay, duration, reveal });
    return delay + duration;
  }

  // Move every mesh to its slot in `target`, choosing each motion by where it
  // comes from and goes to. Returns when the stage ends.
  stage(target, choose, start = this.clock) {
    const owner = match(this.now, target);
    let end = start;
    const next = [];
    owner.forEach((id, k) => {
      const mesh = this.now[id];
      const slot = target[k];
      const moved = !mesh.pose.position.equals(slot.pose.position) || !mesh.pose.quaternion.equals(slot.pose.quaternion);
      const reveal = mesh.code !== slot.code ? (slot.code ? { code: slot.code } : { code: null, atEnd: true }) : undefined;
      if (moved || reveal) {
        const m = choose(mesh, slot) ?? { path: transfer(mesh.pose, slot.pose), delay: 0, duration: TIMING.direct };
        end = Math.max(end, this.add(mesh, m.path, start + m.delay, m.duration, reveal));
      }
      next[id] = { id, zone: slot.zone, index: slot.index, code: slot.code, pose: slot.pose };
    });
    this.now = next;
    this.clock = end;
    return end;
  }

  // Poses that are not any layout's -- the pack squared for dealing, a pile
  // in front of a player -- as slots of a virtual zone.
  // Each card keeps the way its top points, so none has to spin to get there.
  virtual(zone, meshes, at) {
    return meshes.map((mesh, i) => ({
      id: mesh.id,
      zone,
      index: i,
      code: mesh.code,
      pose: lying({
        x: at.x,
        z: at.z,
        height: REST + i * STEP,
        faceUp: false,
        yaw: yawKeeping(mesh.pose, false) + jitter(`${zone}${i}`, 1.5),
      }),
    }));
  }

  // Move the given meshes to explicit poses, one motion each. A change of
  // face shows from the start of a card's motion, or hides as it lands.
  moveEach(pairs, start = this.clock) {
    let end = start;
    for (const { mesh, pose, path, delay = 0, duration, code = this.now[mesh.id].code } of pairs) {
      const was = this.now[mesh.id].code;
      const reveal = code === was ? undefined : code ? { code } : { code: null, atEnd: true };
      end = Math.max(end, this.add(mesh, path, start + delay, duration, reveal));
      this.now[mesh.id] = { ...this.now[mesh.id], pose, code };
    }
    this.clock = end;
    return end;
  }

  // ---- the stages -------------------------------------------------------------

  direct(state) {
    const target = layout(state, this.view);
    this.stage(target, (mesh, slot) => ({
      path: transfer(mesh.pose, slot.pose, { clearance: mesh.zone === slot.zone ? 1.2 : undefined }),
      delay: 0,
      duration: mesh.zone === slot.zone ? TIMING.resort : TIMING.direct,
    }));
  }

  play({ state, who }) {
    if (who === "them" && this.motions.length) this.clock += TIMING.think;
    this.stage(layout(state, this.view), (mesh, slot) => {
      if (slot.zone === "trick" && mesh.zone !== "trick") {
        return { path: layDown(mesh.pose, slot.pose), delay: 0, duration: TIMING.play };
      }
      return { path: transfer(mesh.pose, slot.pose, { clearance: 1.2 }), delay: 0, duration: TIMING.resort };
    });
  }

  trick({ state }) {
    if (this.pause) this.clock += TIMING.read;
    this.stage(layout(state, this.view), (mesh, slot) => ({
      path: slide(mesh.pose, slot.pose),
      delay: slot.index % 2 ? 40 : 0,
      duration: TIMING.push,
    }));
  }

  discard({ state }) {
    let n = 0;
    this.stage(layout(state, this.view), (mesh, slot) => {
      if (slot.zone.endsWith("discards") && mesh.zone.endsWith("hand")) {
        return { path: layDown(mesh.pose, slot.pose), delay: n++ * TIMING.stagger, duration: TIMING.discard };
      }
      return { path: transfer(mesh.pose, slot.pose, { clearance: 1.2 }), delay: 0, duration: TIMING.resort };
    });
  }

  draw({ state }) {
    this.clock += 120;
    let n = 0;
    this.stage(layout(state, this.view), (mesh, slot) => {
      if (mesh.zone === "talon" && slot.zone.endsWith("hand")) {
        const toward = slot.zone === "your-hand" ? TOWARD.you : TOWARD.them;
        return { path: pickUp(mesh.pose, slot.pose, { toward }), delay: n++ * TIMING.stagger, duration: TIMING.draw };
      }
      return { path: transfer(mesh.pose, slot.pose, { clearance: 1.2 }), delay: 0, duration: TIMING.resort };
    });
  }

  "their-exchange"({ state }) {
    // Their discards go down first; then they draw as many from the talon.
    const target = layout(state, this.view);
    const out = { n: 0 };
    const drawAt = TIMING.discard + TIMING.stagger * 4 + 150;
    const inn = { n: 0 };
    this.stage(target, (mesh, slot) => {
      if (slot.zone === "their-discards" && mesh.zone === "their-hand") {
        return { path: layDown(mesh.pose, slot.pose), delay: out.n++ * TIMING.stagger, duration: TIMING.discard };
      }
      if (slot.zone === "their-hand" && mesh.zone === "talon") {
        return { path: pickUp(mesh.pose, slot.pose, { toward: TOWARD.them }), delay: drawAt + inn.n++ * TIMING.stagger, duration: TIMING.draw };
      }
      return { path: transfer(mesh.pose, slot.pose, { clearance: 1.2 }), delay: 0, duration: TIMING.resort };
    });
  }

  cut({ state, cuts }) {
    const target = layout(state, this.view);
    // The cut cards leave the spread face down and turn over on the table.
    const cutCodes = new Set(cuts.map((c) => c.card));
    const ribbon = this.now.filter((m) => m.zone === "pack").sort((a, b) => a.index - b.index);
    const depth = Math.min(Math.max((this.view.cutDepth ?? 16) - 1, 0), ribbon.length - 1);
    const chosen = { you: ribbon[depth], them: ribbon[(depth + 11) % ribbon.length] };
    for (const e of cuts) {
      const mesh = chosen[e.who];
      this.now[mesh.id] = { ...mesh, zone: "cut-pending", code: e.card };
    }
    const owner = new Map();
    target.forEach((slot) => {
      if (slot.zone === "cut") owner.set(slot.code, slot);
    });
    const start = this.clock;
    let end = start;
    const spreadAt = new Vector3(this.zones.ribbon.x - 15.5 * this.zones.ribbon.spacing, 0, this.zones.ribbon.z);
    for (const e of cuts) {
      const mesh = chosen[e.who];
      const slot = owner.get(e.card);
      // Slid out face down clear of the spread, then turned up towards it.
      const toward = turnToward(slot.pose, spreadAt);
      const down = beforeFlip(slot.pose, toward);
      const path = chain([slide(mesh.pose, down), 1.4], [flip(down, { toward }), 1]);
      end = Math.max(end, this.add(mesh, path, start + (e.who === "them" ? 150 : 0), TIMING.cutShow, { code: e.card }));
      this.now[mesh.id] = { id: mesh.id, zone: "cut", index: slot.index, code: e.card, pose: slot.pose };
    }
    // The rest of the spread closes up.
    const rest = target.filter((slot) => !cutCodes.has(slot.code));
    const spread = this.now.filter((m) => m.zone === "pack").sort((a, b) => a.index - b.index);
    spread.forEach((mesh, i) => {
      const slot = rest[i];
      end = Math.max(end, this.add(mesh, slide(mesh.pose, slot.pose), start + 200, TIMING.resort));
      this.now[mesh.id] = { id: mesh.id, zone: slot.zone, index: slot.index, code: null, pose: slot.pose };
    });
    this.clock = end + (this.pause ? TIMING.cutRead : 0);
  }

  uncut({ state }) {
    this.turnDown(new Vector3(this.zones.ribbon.x - 15.5 * this.zones.ribbon.spacing, 0, this.zones.ribbon.z));
    for (const m of this.now) if (m.zone === "pack-pending") this.now[m.id] = { ...m, zone: "cut" };
    this.stage(layout(state, this.view), (mesh, slot) => ({ path: slide(mesh.pose, slot.pose), delay: 0, duration: TIMING.gather }));
  }

  // Every face-up card on the table turns over where it lies. A row is
  // squared into a pile first -- a shingled card cannot hinge on the
  // neighbour it rests on -- and the pile turns as one block about its long
  // edge, towards `goal`; a lone card turns so that it lies face down the
  // standard way, away from the middle of the table, into clear space.
  turnDown(goal) {
    const middle = new Vector3(0, 0, this.zones.ribbon.z);
    const up = this.now.filter((m) => FACE_UP.has(m.zone));
    if (!up.length) return;
    const groups = {};
    for (const m of up) (groups[ROWS.has(m.zone) ? m.zone : `one${m.id}`] ??= []).push(m);
    const piles = [];
    const sweep = [];
    for (const [key, group] of Object.entries(groups)) {
      const sorted = [...group].sort((a, b) => a.index - b.index);
      if (!ROWS.has(key)) {
        piles.push({ cards: sorted.map((mesh) => ({ mesh, pose: mesh.pose })), row: false });
        continue;
      }
      // Squared exactly -- no jitter -- or corners standing proud of the
      // hinge line would dip below the table as the block stands upright.
      const first = sorted[0].pose.position;
      const cards = sorted.map((mesh, i) => {
        const pose = lying({ x: first.x, z: first.z, height: REST + i * STEP, faceUp: true, yaw: yawKeeping(mesh.pose, true) });
        sweep.push({ mesh, pose, path: slide(mesh.pose, pose), delay: i * 15, duration: TIMING.sweep });
        return { mesh, pose };
      });
      piles.push({ cards, row: true });
    }
    if (sweep.length) this.moveEach(sweep);
    const turns = [];
    piles.forEach(({ cards, row }, g) => {
      const base = cards[0].pose;
      const away = base.position.clone().multiplyScalar(2).sub(middle);
      const toward = row
        ? (goal.x < base.position.x ? new Vector3(-1, 0, 0) : new Vector3(1, 0, 0))
        : turnToward(base, away);
      const paths = flipPile(cards.map((c) => c.pose), { toward });
      cards.forEach(({ mesh }, i) => {
        turns.push({ mesh, pose: paths[i](1), path: paths[i], delay: g * 60, duration: TIMING.flip, code: null });
      });
    });
    this.moveEach(turns);
    for (const { mesh } of turns) this.now[mesh.id] = { ...this.now[mesh.id], zone: "pack-pending" };
  }

  deal({ state, dealer }) {
    const elder = dealer === "you" ? "them" : "you";
    // 1. Everything face up turns over; everything comes together as a pack
    //    in front of the dealer.
    const packAt = this.zones.pack[dealer];
    this.turnDown(new Vector3(packAt.x, 0, packAt.z));
    const order = [...this.now].sort((a, b) => a.pose.position.y - b.pose.position.y || a.id - b.id);
    const pack = this.virtual("pack", order, packAt);
    this.moveEach(
      pack.map((slot, i) => {
        const mesh = this.now[slot.id];
        const onTable = !mesh.zone.endsWith("hand");
        const path = onTable ? slide(mesh.pose, slot.pose) : transfer(mesh.pose, slot.pose);
        return { mesh, pose: slot.pose, path, delay: (i % 8) * 20, duration: TIMING.gather, code: null };
      }),
    );
    pack.forEach((slot) => (this.now[slot.id] = { ...this.now[slot.id], zone: "pack", index: slot.index }));

    // 2. Dealt two at a time, elder first (Cavendish), face down before each
    //    player; then the talon, three and five crossed over them (Foster).
    const target = layout(state, this.view);
    const top = [...pack].reverse().map((slot) => this.now[slot.id]);
    const piles = { you: [], them: [] };
    const dealt = [];
    let pair = 0;
    for (let round = 0; round < 6; round++) {
      for (const who of [elder, dealer]) {
        for (let k = 0; k < 2; k++) {
          const mesh = top.shift();
          const at = this.zones.dealt[who];
          const n = piles[who].length;
          const pose = lying({ x: at.x, z: at.z, height: REST + n * STEP, faceUp: false, yaw: jitter(`deal${who}${n}`, 3) });
          piles[who].push({ mesh, pose });
          const delay = pair * TIMING.dealPair + k * TIMING.dealSecond;
          dealt.push({ mesh, pose, path: transfer(mesh.pose, pose, { clearance: 3 }), delay, duration: TIMING.dealCard, code: null });
        }
        pair++;
      }
    }
    const talonSlots = target.filter((slot) => slot.zone === "talon").sort((a, b) => a.index - b.index);
    talonSlots.forEach((slot, i) => {
      const mesh = top.shift();
      const delay = pair * TIMING.dealPair + i * TIMING.dealTalon;
      dealt.push({ mesh, pose: slot.pose, path: transfer(mesh.pose, slot.pose, { clearance: 3 }), delay, duration: TIMING.dealCard, code: null });
      this.now[mesh.id] = { ...this.now[mesh.id], zone: "talon", index: slot.index };
    });
    this.moveEach(dealt);

    // 3. Each player picks up their twelve: yours turn to face you as they
    //    rise, and show their faces now.
    const pickups = [];
    for (const who of ["you", "them"]) {
      const zone = who === "you" ? "your-hand" : "their-hand";
      const slots = target.filter((slot) => slot.zone === zone).sort((a, b) => a.index - b.index);
      piles[who].forEach(({ mesh }, i) => {
        const slot = slots[i];
        const from = this.now[mesh.id].pose;
        pickups.push({
          mesh,
          pose: slot.pose,
          path: pickUp(from, slot.pose, { toward: TOWARD[who] }),
          delay: i * 35 + (who === "them" ? 60 : 0),
          duration: TIMING.pickUp,
          code: slot.code,
          reveal: slot.code ? { code: slot.code } : undefined,
        });
        this.now[mesh.id] = { ...this.now[mesh.id], zone, index: slot.index };
      });
    }
    this.moveEach(pickups);
    // Hand in hand with the layout from here on.
    this.now = this.now.map((m) => ({ ...m }));
    target.forEach((slot) => {
      const mesh = this.now.find((m) => m.zone === slot.zone && m.index === slot.index);
      if (mesh) this.now[mesh.id] = { ...mesh, code: slot.code, pose: slot.pose };
    });
  }

  result() {
    return { motions: this.motions, placement: this.now, duration: this.clock };
  }
}

export function choreograph(prev, next, placement, view = {}, options = {}) {
  const plan = new Plan(placement, view, options);
  const stages = stagesBetween(prev, next);
  if (stages) for (const stage of stages) plan[stage.kind](stage);
  plan.direct(next); // settle: exactly layout(next), whatever came before
  return plan.result();
}
