// The celebrations, run without a browser: the real scenes on real three.js
// objects, a stand-in for the page's words, the clock driven by hand. What a
// test can hold them to: every card starts in the pile and never passes
// through the table; nothing becomes NaN; a game can be played to its end;
// and when the celebration closes the table is exactly as it was.

import test from "node:test";
import assert from "node:assert/strict";
import { Mesh, MeshBasicMaterial, PerspectiveCamera, Scene, Vector3 } from "three";
import { cardGeometry } from "../src/cards.js";
import { lying } from "../src/kinematics.js";
import { createCelebrations, pilePoses, PILE } from "../src/celebrate/runner.js";
import { SCENES } from "../src/celebrate/scenes.js";
import { CARD } from "../src/units.js";

globalThis.window ??= new EventTarget();

function table() {
  const scene = new Scene();
  const camera = new PerspectiveCamera(40, 1.6, 20, 400);
  camera.position.set(0, 55, 60);
  camera.lookAt(0, 0, 0);
  const canvas = new EventTarget();
  canvas.getBoundingClientRect = () => ({ left: 0, top: 0, width: 1280, height: 800 });
  canvas.setPointerCapture = () => {};
  const stage = { scene, camera, renderer: { domElement: canvas }, registerInk() {}, render() {}, portrait: false };
  const geometry = cardGeometry();
  const deck = {
    card(code = null) {
      const mesh = new Mesh(geometry, new MeshBasicMaterial());
      mesh.userData.code = code;
      scene.add(mesh);
      return mesh;
    },
  };
  // The table as a partie leaves it: tricks face up in rows, the rest down.
  const codes = [];
  for (const s of "SHDC") for (const r of "789TJQKA") codes.push(r + s);
  const meshes = codes.map((code, i) => {
    const mesh = deck.card(i < 24 ? code : null);
    const p = lying({ x: -30 + (i % 12) * 5, z: i < 12 ? -17 : i < 24 ? -5 : 10, height: 0.02, faceUp: i < 24 });
    mesh.position.copy(p.position);
    mesh.quaternion.copy(p.quaternion);
    return mesh;
  });
  const said = { bursts: 0, messages: [], scores: [], titles: [] };
  const hud = {
    open() {},
    close() {},
    clear() {},
    title: (words) => said.titles.push(words),
    how() {},
    score: (words) => words && said.scores.push(words),
    message: (words, action) => words && said.messages.push({ words, action }),
    burst: () => (said.bursts += 1),
  };
  return { stage, deck, meshes, hud, said, camera };
}

// How far a card's lowest corner is above the table, in the world -- a card
// may be part of something (a cup, a dancer) and scaled.
const CORNERS = [];
for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) CORNERS.push(new Vector3((sx * CARD.width) / 2, (sy * CARD.height) / 2, (sz * CARD.thickness) / 2));
function above(mesh) {
  mesh.updateWorldMatrix(true, false);
  return Math.min(...CORNERS.map((c) => c.clone().applyMatrix4(mesh.matrixWorld).y));
}

test("all seven of the user's celebrations are here, each with a name", () => {
  assert.deepEqual(Object.keys(SCENES), ["plates", "pong", "cupball", "disco", "parade", "macarena", "people"]);
  for (const [name, make] of Object.entries(SCENES)) assert.ok(make.title, name);
});

test("the cards gather from the table into the pile, keeping their faces", () => {
  const t = table();
  const run = createCelebrations({ stage: t.stage, deck: t.deck, hud: t.hud, scenes: SCENES, seed: 3 });
  run.manual();
  const shown = new Map(t.meshes.filter((m) => m.userData.code).map((m) => [m.userData.code, m.position.clone()]));
  run.play(run.names[0], { from: t.meshes });
  assert.ok(t.meshes.every((m) => !m.visible), "the table's own cards are put away");
  // At the handover, each face shown on the table is where it was.
  for (const card of run.context.cards) {
    const was = shown.get(card.userData.code);
    if (was) assert.ok(card.position.distanceTo(was) < 1e-6, `${card.userData.code} moved at the handover`);
  }
  for (let ms = 0; ms < 1300; ms += 1000 / 60) {
    run.tick(1000 / 60);
    for (const card of run.context.cards) assert.ok(above(card) > -0.05, "through the table while gathering");
  }
  const pile = pilePoses();
  run.context.cards.forEach((card, k) => {
    assert.ok(card.position.distanceTo(pile[k].position) < 0.5 || card.position.y > 0.5, `card ${k} is in the pile`);
  });
  assert.ok(Math.hypot(PILE.x, PILE.z) < 20, "the pile is in the middle of the table");
  run.stop();
});

for (const name of Object.keys(SCENES)) {
  test(`${name}: plays without a card through the table, and gives the table back`, () => {
    const t = table();
    const eye = t.camera.position.clone();
    const children = t.stage.scene.children.length;
    const run = createCelebrations({ stage: t.stage, deck: t.deck, hud: t.hud, scenes: SCENES, seed: 11 });
    run.manual();
    run.play(name, { from: t.meshes });
    for (let s = 0; s < 40 * 60; s++) {
      run.tick(1000 / 60);
      if (s % 10) continue;
      for (const card of [...run.context.cards]) {
        assert.ok(Number.isFinite(card.position.x + card.position.y + card.position.z), `${name}: NaN at ${s}`);
        assert.ok(card.parent, `${name}: ${card.userData.code} left the scene`);
        assert.ok(above(card) > -0.1, `${name}: ${card.userData.code} through the table at frame ${s}`);
      }
      assert.ok(Number.isFinite(t.camera.position.length()), `${name}: the camera is lost`);
    }
    run.stop();
    assert.equal(t.stage.scene.children.length, children, "everything it added is gone");
    assert.ok(t.meshes.every((m) => m.visible), "the table's cards are back");
    assert.ok(t.camera.position.distanceTo(eye) < 1e-9, "the camera is back");
  });
}

test("plate smash is a game you can finish: plates smash, and the result comes", () => {
  const t = table();
  const run = createCelebrations({ stage: t.stage, deck: t.deck, hud: t.hud, scenes: SCENES, seed: 5 });
  run.manual();
  run.play("plates", { from: t.meshes });
  run.tick(60 * 1000);
  assert.ok(t.said.bursts >= 10, `PIQUET! where plates land (${t.said.bursts})`);
  const result = t.said.messages.at(-1);
  assert.match(result.words, /^Deflected \d+ of 26$/);
  assert.equal(result.action.label, "Play again");
  run.stop();
});

test("pong is a game you can finish: first to five, and the result comes", () => {
  const t = table();
  const run = createCelebrations({ stage: t.stage, deck: t.deck, hud: t.hud, scenes: SCENES, seed: 9 });
  run.manual();
  run.play("pong", { from: t.meshes });
  // Your paddle held still in the middle; your opponent plays on.
  run.tick(180 * 1000);
  const result = t.said.messages.at(-1);
  assert.ok(result, "the game ended");
  assert.match(result.words, /^(You win|Your opponent wins)$/);
  assert.match(t.said.scores.at(-1), /^You [0-5] · [0-5] Your opponent$/);
  run.stop();
});

// A pointer event as a canvas gets one.
function pointer(kind, x, y) {
  const e = new Event(kind);
  Object.assign(e, { clientX: x, clientY: y, pointerId: 1 });
  return e;
}

test("cup and ball, swung hard: the ball flies on its string, and nothing goes through the table", () => {
  const t = table();
  const run = createCelebrations({ stage: t.stage, deck: t.deck, hud: t.hud, scenes: SCENES, seed: 4 });
  run.manual();
  run.play("cupball", { from: t.meshes });
  run.tick(4500);
  const canvas = t.stage.renderer.domElement;
  canvas.dispatchEvent(pointer("pointerdown", 640, 400));
  const ball = run.context.cards[0];
  const seen = { low: Infinity, high: -Infinity };
  for (let s = 0; s < 20 * 60; s++) {
    // A hand swinging the cup side to side, faster and faster, and jerking up.
    const x = 640 + Math.sin(s / (20 - Math.min(14, s / 60))) * 420;
    const y = 400 - (s % 90 < 8 ? 180 : 0);
    canvas.dispatchEvent(pointer("pointermove", x, y));
    run.tick(1000 / 60);
    if (s % 5) continue;
    ball.updateWorldMatrix(true, false);
    const at = new Vector3().setFromMatrixPosition(ball.matrixWorld);
    seen.low = Math.min(seen.low, at.y);
    seen.high = Math.max(seen.high, at.y);
    for (const card of run.context.cards) {
      assert.ok(above(card) > -0.1, `${card.userData.code} through the table at step ${s}`);
      assert.ok(Number.isFinite(card.position.length()), "NaN");
    }
  }
  assert.ok(seen.high - seen.low > 10, `the ball swung (${seen.low.toFixed(1)} to ${seen.high.toFixed(1)} cm)`);
  run.stop();
});
