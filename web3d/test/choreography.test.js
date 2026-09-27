// The choreography: every change of state animated, every card landing
// exactly where the layout says, nothing teleporting, nothing shown early.

import test from "node:test";
import assert from "node:assert/strict";
import { choreograph, initialPlacement, stagesBetween, cardsNamed } from "../src/choreography.js";
import { cardCorners } from "../src/kinematics.js";
import { layout } from "../src/layout.js";
import { ZONES_PORTRAIT } from "../src/units.js";
import { engine, partie } from "./partie.js";

const parties = await Promise.all([[3, 7], [1, 11], [2, 23], [3, 404], [1, 5]].map(([l, s]) => partie(l, s)));

function mayKnow(s) {
  const known = new Set([...s.hand, ...s.discards]);
  for (const t of s.tricks_played) [t.led, t.followed].forEach((c) => known.add(c));
  if (s.trick) [s.trick.led, s.trick.followed].filter(Boolean).forEach((c) => known.add(c));
  for (const e of s.events) if (e.kind === "cut") known.add(e.card); // shown, then shuffled back
  return known;
}

const key = (slot) => `${slot.zone}#${slot.index}`;
const close = (a, b, eps = 1e-6) => a.position.distanceTo(b.position) <= eps && Math.abs(Math.abs(a.quaternion.dot(b.quaternion)) - 1) <= eps;

// Run a plan the way the timeline would, checking it as it goes.
function run(before, result, next, where, view = {}) {
  const pose = before.map((m) => m.pose);
  const code = before.map((m) => m.code);
  const known = mayKnow(next);
  const byMesh = new Map();
  for (const m of result.motions) {
    assert.ok(m.delay >= 0 && m.duration >= 0, `${where}: negative time`);
    if (!byMesh.has(m.id)) byMesh.set(m.id, []);
    byMesh.get(m.id).push(m);
  }
  for (const [id, motions] of byMesh) {
    motions.sort((a, b) => a.delay - b.delay);
    let free = 0;
    for (const m of motions) {
      assert.ok(m.delay >= free - 1e-6, `${where}: card ${id} is in two motions at once`);
      free = m.delay + m.duration;
      assert.ok(close(m.path(0), pose[id], 1e-5), `${where}: card ${id} jumps at the start of a motion`);
      for (let i = 0; i <= 20; i++) {
        for (const c of cardCorners(m.path(i / 20))) assert.ok(c.y >= -1e-6, `${where}: card ${id} dips below the table`);
      }
      if (m.reveal && m.reveal.code) assert.ok(known.has(m.reveal.code), `${where}: shows ${m.reveal.code} early`);
      if (m.reveal) code[id] = m.reveal.code;
      pose[id] = m.path(1);
    }
  }
  // Every card lands exactly on its place in the layout, showing its face.
  const want = new Map(layout(next, view).map((slot) => [key(slot), slot]));
  const seen = new Set();
  for (const m of result.placement) {
    const slot = want.get(key(m));
    assert.ok(slot, `${where}: card ${m.id} in no slot (${key(m)})`);
    assert.ok(!seen.has(key(m)), `${where}: two cards in ${key(m)}`);
    seen.add(key(m));
    assert.equal(m.code, slot.code, `${where}: wrong face in ${key(m)}`);
    assert.ok(close(pose[m.id], slot.pose), `${where}: card ${m.id} does not land on ${key(m)}`);
    assert.equal(code[m.id], slot.code, `${where}: card ${m.id} shows ${code[m.id]} in ${key(m)}`);
  }
  assert.equal(seen.size, 32);
}

test("the reducer rebuilds every next state from the one before and its events", () => {
  for (const states of parties) {
    for (let i = 1; i < states.length; i++) {
      const stages = stagesBetween(states[i - 1], states[i]);
      assert.ok(stages, `step ${i}: not followed`);
      if (!stages.length) continue;
      const last = stages[stages.length - 1].state;
      const a = layout(last).map((s) => `${s.zone}:${s.code}`).sort();
      const b = layout(states[i]).map((s) => `${s.zone}:${s.code}`).sort();
      assert.deepEqual(a, b, `step ${i} (${states[i - 1].prompt.kind} -> ${states[i].prompt.kind})`);
    }
  }
});

test("whole parties animate end to end, every step landing exactly on its layout", () => {
  for (const [p, states] of parties.entries()) {
    let placement = initialPlacement(states[0]);
    for (let i = 1; i < states.length; i++) {
      const result = choreograph(states[i - 1], states[i], placement);
      run(placement, result, states[i], `partie ${p} step ${i} (${states[i - 1].prompt.kind} -> ${states[i].prompt.kind})`);
      placement = result.placement;
    }
  }
});

test("a whole partie animates on a phone held upright too", () => {
  const states = parties[2];
  const view = { zones: ZONES_PORTRAIT };
  let placement = initialPlacement(states[0], view);
  for (let i = 1; i < states.length; i++) {
    const result = choreograph(states[i - 1], states[i], placement, view);
    run(placement, result, states[i], `portrait step ${i}`, view);
    placement = result.placement;
  }
});

test("picking up your discards to look, and putting them down, never goes through the table", () => {
  const states = parties[0];
  const s = states.find((x) => x.phase === "play" && x.discards.length >= 3);
  const placement = initialPlacement(s);
  const up = choreograph(s, s, placement, { peek: true });
  run(placement, up, s, "picking up the discards", { peek: true });
  const down = choreograph(s, s, up.placement, {});
  run(up.placement, down, s, "putting them down", {});
  assert.ok(up.motions.length >= s.discards.length && down.motions.length >= s.discards.length);
});

test("a card played is laid down after the one it answers, with a pause to think", () => {
  const states = parties[0];
  const i = states.findIndex((s, k) => k > 0 && states[k - 1].prompt.kind === "play" && !states[k - 1].trick);
  let placement = initialPlacement(states[0]);
  for (let k = 1; k < i; k++) placement = choreograph(states[k - 1], states[k], placement).placement;
  const result = choreograph(states[i - 1], states[i], placement);
  const played = states[i].events.slice(states[i - 1].events.length).filter((e) => e.kind === "played");
  assert.ok(played.length >= 2);
  const at = (code) => {
    const mesh = result.placement.find((m) => m.code === code);
    return result.motions.filter((m) => m.id === mesh.id).sort((a, b) => a.delay - b.delay)[0];
  };
  const mine = at(played[0].card);
  const theirs = at(played[1].card);
  assert.ok(theirs.delay >= mine.delay + mine.duration, "they answer after your card is down");
});

test("going back -- an undo -- animates straight to the earlier layout", async () => {
  const states = parties[1];
  const late = states[Math.floor(states.length / 2)];
  const earlier = states[Math.floor(states.length / 2) - 3];
  let placement = initialPlacement(states[0]);
  for (let k = 1; k <= Math.floor(states.length / 2); k++) placement = choreograph(states[k - 1], states[k], placement).placement;
  assert.equal(stagesBetween(late, earlier), null);
  run(placement, choreograph(late, earlier, placement), earlier, "undo");
});

test("asking to see the hand another way just rearranges it", () => {
  const s = parties[0].find((x) => x.prompt.kind === "exchange");
  const placement = initialPlacement(s);
  const result = choreograph(s, s, placement, { sort: "rank" });
  const moved = new Set(result.motions.map((m) => m.id));
  for (const id of moved) assert.equal(placement[id].zone, "your-hand");
  assert.ok(moved.size > 0);
});

test("the cut: both cards turn up where all can see, and are read before the deal", async () => {
  const e = await engine();
  e.start(3, 7);
  const before = e.state();
  e.send("cut 9");
  const after = e.state();
  const placement = initialPlacement(before);
  const result = choreograph(before, after, placement, { cutDepth: 9 });
  run(placement, result, after, "cut");
  const cuts = after.events.filter((x) => x.kind === "cut").map((x) => x.card);
  const shownAt = result.motions.filter((m) => m.reveal && cuts.includes(m.reveal.code)).map((m) => m.delay);
  assert.equal(shownAt.length, 2);
  if (after.prompt.kind === "choose_dealer") return; // you cut higher: nothing dealt until you choose
  const firstDeal = Math.min(...result.motions.filter((m) => m.reveal && after.hand.includes(m.reveal.code)).map((m) => m.delay));
  assert.ok(firstDeal > Math.max(...shownAt) + 1000, "a beat to read the cut before anything is dealt");
});

test("a call names how many cards it holds", () => {
  const cases = [["point of 5", 5], ["point of 6 (56)", 6], ["tierce", 3], ["quart", 4], ["quint to the king", 5],
    ["sixième", 6], ["septième", 7], ["huitième", 8], ["trio", 3], ["quatorze", 4], ["nothing", 0], ["trio of aces", 3]];
  for (const [said, n] of cases) assert.equal(cardsNamed(said), n, said);
});
