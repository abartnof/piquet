// The layout: where all 32 cards rest for a state of the protocol, and which
// of them show their faces (docs/TABLE3D.md section 5.2).
//
// layout(state, view) -> 32 slots { zone, index, code, pose }. It is a pure
// function of what the engine says and of how the human has asked to see it
// (the sort, the cards chosen to throw, the cards pointed at); the
// choreography animates from one layout to the next and must end exactly on
// it.
//
// `code` is a card only where the human may know it -- their hand and
// discards, the cards played, the cuts -- and null everywhere else: nothing
// in the opponent's hand, the talon or the opponent's discards ever carries a
// face, whatever the human happens to have deduced.

import { Quaternion, Vector3 } from "three";
import { arrange, sortMode } from "./hand.js";
import { fan, lying } from "./kinematics.js";
import { CAMERA, CARD, ZONES } from "./units.js";

const DEG = Math.PI / 180;
const REST = 0.02; // a card on the table rests a hair above it
const GAP = 0.02; // and a hair above whatever it lies on
const STEP = CARD.thickness + GAP;
const CHOSEN_LIFT = 2.2; // a card chosen to throw stands clear of the hand
const POINTED_LIFT = 1.1; // a card pointed at rises a little
const FRESH_LIFT = 0.55; // a card just drawn stands a little proud until play begins
const PAIR_OFFSET = 0.5; // the card that followed lies a little nearer its winner

// A small fixed turn for each card, so piles look placed by a hand rather than
// stamped by a machine -- and the same every time that card lands there.
export function jitter(key, degrees = 3) {
  let h = 2166136261;
  for (const ch of String(key)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return ((h >>> 0) / 4294967295 - 0.5) * 2 * degrees * DEG;
}

// A squared pile, each card a hair above the last.
function pile(zone, codes, { x, z, faceUp = false, yaw = 0, from = 0, key = zone }) {
  return codes.map((code, i) => ({
    zone,
    index: i,
    code,
    pose: lying({ x, z, height: REST + (from + i) * STEP, faceUp, yaw: yaw + jitter(`${key}${code ?? i}`, 2.5) }),
  }));
}

// A shingled row running to the right: each card rests on the one before it,
// tilted just enough to clear it, as cards spread on a table do -- so every
// card's corner index shows, later cards lie on top, and the row stays on the
// table instead of climbing a card's thickness per card.
function row(entries, { x, z, spacing, faceUp = true, yaw = 0 }) {
  const lean = Math.atan(STEP / spacing);
  const tilt = new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), -lean); // left edge up
  const height = REST + (CARD.width / 2) * Math.sin(lean) + (CARD.thickness / 2) * Math.cos(lean);
  return entries.map(({ zone, code, dz = 0, yaw: own }, i) => {
    const flat = lying({ x: x + i * spacing, z: z + dz, height: 0, faceUp, yaw: own ?? yaw });
    flat.quaternion.premultiply(tilt);
    flat.position.y = height;
    return { zone, index: i, code, pose: flat };
  });
}

// Tricks won, in the winner's row: led card then followed, in play order,
// each still lying the way it was played -- yours upright to you, theirs to
// them, as a gathered trick does at a real table. Cards print their index at
// both ends, so every one still shows a readable corner.
const uprightTo = (who) => (who === "you" ? 0 : Math.PI);

function wonRow(zone, tricks, { x, z, span }, { toward }) {
  const entries = tricks.flatMap((t) => [
    { zone, code: t.led, yaw: uprightTo(t.leader) },
    { zone, code: t.followed, dz: toward * PAIR_OFFSET, yaw: uprightTo(t.leader === "you" ? "them" : "you") },
  ]);
  const spacing = Math.min(1.3, Math.max(1.0, span / Math.max(1, entries.length - 1)));
  return row(entries, { x, z, spacing });
}

function yourHand(state, view, zones) {
  const zone = zones.yourHand;
  const groups = arrange(state, sortMode(state, view.sort));
  const raw = [];
  let angle = 0;
  groups.forEach((group, g) =>
    group.forEach((_, i) => {
      if (g > 0 && i === 0) angle += zone.groupGap * DEG;
      raw.push(angle);
      angle += zone.spread * DEG;
    }),
  );
  const middle = raw.length ? (raw[0] + raw[raw.length - 1]) / 2 : 0;
  const centre = new Vector3(...zone.centre);
  const poses = fan({
    angles: raw.map((a) => a - middle),
    centre,
    facing: toward(centre, 1),
    radius: zone.radius,
    tilt: zone.lean * DEG,
  });
  const codes = groups.flat();
  const chosen = new Set(view.selected);
  const pointed = new Set(view.lifted);
  const fresh = new Set(view.fresh);
  return codes.map((code, i) => {
    const pose = poses[i];
    const lift = chosen.has(code) ? CHOSEN_LIFT : pointed.has(code) ? POINTED_LIFT : fresh.has(code) ? FRESH_LIFT : 0;
    if (lift) pose.position.addScaledVector(new Vector3(0, 1, 0).applyQuaternion(pose.quaternion), lift);
    return { zone: "your-hand", index: i, code, pose };
  });
}

function theirHand(count, zones) {
  const zone = zones.theirHand;
  const centre = new Vector3(...zone.centre);
  return fan({
    count,
    centre,
    facing: toward(centre, -1),
    radius: zone.radius,
    spread: zone.spread * DEG,
    tilt: zone.lean * DEG,
  }).map((pose, i) => ({ zone: "their-hand", index: i, code: null, pose }));
}

// A point level with a held hand, far off toward its holder's side of the
// table (+1 yours, -1 theirs): the fan faces it, then leans back.
function toward(centre, side) {
  return centre.clone().add(new Vector3(0, 0, 300 * side));
}

function theirPlayed(state) {
  const onTable = state.trick && (state.trick.leader === "them" || state.trick.followed) ? 1 : 0;
  return state.tricks_played.length + onTable;
}

function cutLayout(state, zones) {
  const shown = state.prompt.kind === "choose_dealer"
    ? state.events.filter((e) => e.kind === "cut").slice(-2)
    : [];
  const r = zones.ribbon;
  const ribbon = row(
    Array.from({ length: 32 - shown.length }, () => ({ zone: "pack", code: null })),
    { x: r.x - (31 - shown.length) * r.spacing, z: r.z, spacing: r.spacing, faceUp: false },
  ).reverse(); // index 0 is the top of the pack, at the right
  ribbon.forEach((slot, i) => (slot.index = i));
  const cuts = shown.map((e) => {
    const at = e.who === "you" ? zones.yourCut : zones.theirCut;
    const yaw = (e.who === "you" ? 0 : Math.PI) + jitter(e.card);
    return { zone: "cut", index: e.who === "you" ? 0 : 1, code: e.card, pose: lying({ x: at.x, z: at.z, height: REST, yaw }) };
  });
  return [...ribbon, ...cuts];
}

export function layout(
  state,
  {
    sort = "auto",
    selected = [],
    lifted = [],
    fresh = [],
    peek = false,
    eye = new Vector3(...CAMERA.position),
    zones = ZONES,
  } = {},
) {
  if (state.phase === "cut") return cutLayout(state, zones);

  const slots = [];
  slots.push(...yourHand(state, { sort, selected, lifted, fresh, eye }, zones));
  slots.push(...theirHand(12 - theirPlayed(state), zones));

  // The talon: three below and the rest crossed over them (Foster: "the five
  // top cards being laid crosswise on the three at the bottom"). Cards are
  // taken from the top, so the crossed ones go first.
  const t = zones.talon;
  const straight = Math.min(state.talon_remaining, 3);
  const crossed = state.talon_remaining - straight;
  slots.push(...pile("talon", Array(straight).fill(null), { x: t.x, z: t.z }));
  slots.push(
    ...pile("talon", Array(crossed).fill(null), { x: t.x, z: t.z, yaw: 90 * DEG, from: straight }).map((s) => ({
      ...s,
      index: s.index + straight,
    })),
  );

  // Your discards: a pile face down beside you -- or, while you look at them,
  // held up in a small fan (the rules let you consult your own, never theirs).
  const d = zones.yourDiscards;
  if (peek && state.discards.length) {
    fan({
      count: state.discards.length,
      centre: new Vector3(...d.peek.centre),
      facing: eye,
      radius: d.peek.radius,
      spread: d.peek.spread * DEG,
      tilt: 10 * DEG,
    }).forEach((pose, i) => slots.push({ zone: "your-discards", index: i, code: state.discards[i], pose }));
  } else {
    slots.push(...pile("your-discards", state.discards, { x: d.x, z: d.z }));
  }
  const td = zones.theirDiscards;
  slots.push(...pile("their-discards", Array(state.their_discards).fill(null), { x: td.x, z: td.z }));

  // The trick on the table: each card in front of whoever played it, yours
  // upright to you and theirs upright to them -- the one that follows lying
  // a step above the one led, so if their corners meet it is on top (the user:
  // "the cards in the tricks are still clipping each other").
  if (state.trick) {
    const { leader, led, followed } = state.trick;
    const played = [[leader, led], [leader === "you" ? "them" : "you", followed]].filter(([, c]) => c);
    played.forEach(([who, code], i) => {
      const at = who === "you" ? zones.yourPlay : zones.theirPlay;
      const yaw = (who === "you" ? 0 : Math.PI) + jitter(code, 4);
      slots.push({ zone: "trick", index: i, code, pose: lying({ x: at.x, z: at.z, height: REST + i * STEP, yaw }) });
    });
  }

  // Tricks won lie face up in front of their winner, and either player may
  // look at them at any time (Cavendish, Law 60).
  const won = (who) => state.tricks_played.filter((x) => x.winner === who);
  slots.push(...wonRow("your-tricks", won("you"), zones.yourTricks, { toward: 1 }));
  slots.push(...wonRow("their-tricks", won("them"), zones.theirTricks, { toward: -1 }));
  return slots;
}
