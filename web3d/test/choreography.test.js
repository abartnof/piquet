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

// The voice says each thing as it is seen to happen (Andrew: the right audio
// "at the right occasion, and not before/after"), so the choreography says
// when each new event happens on its clock: a card's when it lands, a call as
// your opponent's cards stir, anything else once the motion before it is done.
test("every new event has its moment on the animation's clock, in order", () => {
  let checked = { played: 0, called: 0, scored: 0 };
  for (const [p, states] of parties.entries()) {
    let placement = initialPlacement(states[0]);
    for (let i = 1; i < states.length; i++) {
      const prev = states[i - 1];
      const next = states[i];
      const result = choreograph(prev, next, placement);
      placement = result.placement;
      const where = `partie ${p} step ${i}`;
      let last = 0;
      for (let k = prev.events.length; k < next.events.length; k++) {
        const e = next.events[k];
        const t = result.beats[k];
        assert.ok(Number.isFinite(t) && t >= 0 && t <= result.duration + 1e-6, `${where}: event ${k} (${e.kind}) at ${t}`);
        assert.ok(t >= last - 1e-6, `${where}: ${e.kind} is timed before the event ahead of it`);
        last = t;
        if (e.kind === "played") {
          // Not before the card is down on the table.
          const mesh = result.placement.find((m) => m.code === e.card);
          const first = result.motions.filter((m) => m.id === mesh.id).sort((a, b) => a.delay - b.delay)[0];
          if (first) assert.ok(t >= first.delay + first.duration - 1e-6, `${where}: ${e.card} spoken of before it lands`);
          checked.played++;
        }
        if (e.kind === "called" && e.who === "them" && cardsNamed(e.said) > 0) {
          // As their cards stir: once the bob has begun, before it is over.
          const bobs = result.motions.filter((m) => Math.abs(m.delay - t) < 50 * cardsNamed(e.said) + 1);
          assert.ok(bobs.length > 0, `${where}: "${e.said}" said when no card stirs`);
          checked.called++;
        }
        if (e.kind === "scored" && e.category === "play") checked.scored++;
      }
    }
  }
  assert.ok(checked.played > 100 && checked.called > 20 && checked.scored > 100, JSON.stringify(checked));
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

// Andrew: "one card should always be on top if two cards collide, so we
// should always see one card fully cell-shaded above the other. i'm seeing
// the cell shading breaking down during the tricks part." Two cards lying
// over one another on the table, at any moment of any motion, must be a
// card's thickness apart where they overlap -- or the two fight over which
// is drawn, and the ink and the shading break up.
import { Vector3 } from "three";
import { CARD } from "../src/units.js";

const UP = new Vector3(0, 1, 0);
const faceNormal = (p) => new Vector3(0, 0, 1).applyQuaternion(p.quaternion);
function outlineOf(p) {
  const c = cardCorners(p).filter((_, i) => i % 2 === 0);
  const centre = c.reduce((a, q) => a.add(q), new Vector3()).multiplyScalar(0.25);
  // Shrunk by a hair only, so cards that merely touch are apart but a corner
  // a millimetre over another is not.
  return [c[0], c[1], c[3], c[2]].map((q) => q.clone().sub(centre).multiplyScalar(0.997).add(centre)).map((q) => [q.x, q.z]);
}
function apart(a, b) {
  for (const poly of [a, b]) {
    for (let i = 0; i < poly.length; i++) {
      const [x1, z1] = poly[i];
      const [x2, z2] = poly[(i + 1) % poly.length];
      const axis = [z1 - z2, x2 - x1];
      const along = (p) => p.map(([x, z]) => x * axis[0] + z * axis[1]);
      const [pa, pb] = [along(a), along(b)];
      if (Math.max(...pa) <= Math.min(...pb) || Math.max(...pb) <= Math.min(...pa)) return true;
    }
  }
  return false;
}
// The height of a card's mid-plane above a point of the table.
function surfaceAt(p, x, z) {
  const n = faceNormal(p);
  return p.position.y - (n.x * (x - p.position.x) + n.z * (z - p.position.z)) / n.y;
}
// Where two outlines overlap, sample points and take the smallest gap.
function gapBetween(a, b) {
  const [oa, ob] = [outlineOf(a), outlineOf(b)];
  const inside = (poly, [x, z]) => poly.every(([x1, z1], i) => {
    const [x2, z2] = poly[(i + 1) % poly.length];
    return (x2 - x1) * (z - z1) - (z2 - z1) * (x - x1) >= 0;
  }) || poly.every(([x1, z1], i) => {
    const [x2, z2] = poly[(i + 1) % poly.length];
    return (x2 - x1) * (z - z1) - (z2 - z1) * (x - x1) <= 0;
  });
  let least = Infinity;
  const [minX, maxX] = [Math.min(...oa.map((q) => q[0])), Math.max(...oa.map((q) => q[0]))];
  const [minZ, maxZ] = [Math.min(...oa.map((q) => q[1])), Math.max(...oa.map((q) => q[1]))];
  for (let i = 0; i <= 8; i++) {
    for (let j = 0; j <= 8; j++) {
      const pt = [minX + ((maxX - minX) * i) / 8, minZ + ((maxZ - minZ) * j) / 8];
      if (inside(oa, pt) && inside(ob, pt)) least = Math.min(least, Math.abs(surfaceAt(a, ...pt) - surfaceAt(b, ...pt)));
    }
  }
  return least;
}

test("cards lying over one another never share the table, at any moment of any motion", () => {
  const clashes = [];
  for (const states of [parties[0], parties[3]]) {
  let placement = initialPlacement(states[0]);
  for (let i = 1; i < states.length; i++) {
    const result = choreograph(states[i - 1], states[i], placement);
    const byMesh = new Map();
    for (const m of result.motions) {
      if (!byMesh.has(m.id)) byMesh.set(m.id, []);
      byMesh.get(m.id).push(m);
    }
    const end = Math.max(0, ...result.motions.map((m) => m.delay + m.duration));
    const poseAt = (id, t) => {
      const motions = byMesh.get(id);
      if (!motions) return placement[id].pose;
      let pose = placement[id].pose;
      for (const m of motions.sort((a, b) => a.delay - b.delay)) {
        if (t < m.delay) break;
        pose = m.path(Math.min(1, (t - m.delay) / Math.max(1e-9, m.duration)));
      }
      return pose;
    };
    for (let k = 1; k <= 24; k++) {
      const t = (end * k) / 24;
      const poses = placement.map((m) => poseAt(m.id, t));
      // Only cards on or near the table, lying flat enough to be read as
      // lying: a held hand is in the air, and a card mid-toss is above all.
      const lying = poses
        .map((p, id) => ({ p, id }))
        .filter(({ p }) => p.position.y < 1.2 && Math.abs(faceNormal(p).dot(UP)) > 0.9);
      for (let a = 0; a < lying.length; a++) {
        for (let b = a + 1; b < lying.length; b++) {
          const [pa, pb] = [lying[a].p, lying[b].p];
          if (pa.position.distanceTo(pb.position) > 11 || apart(outlineOf(pa), outlineOf(pb))) continue;
          const gap = gapBetween(pa, pb);
          if (gap < CARD.thickness * 0.9) clashes.push(`step ${i} (${states[i - 1].prompt.kind}) t=${Math.round(t)}: cards ${lying[a].id} and ${lying[b].id} ${gap.toFixed(3)} apart`);
        }
      }
    }
    placement = result.placement;
  }
  }
  assert.deepEqual(clashes.slice(0, 8), [], `${clashes.length} clashes`);
});
