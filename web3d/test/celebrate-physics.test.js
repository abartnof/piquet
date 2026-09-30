// The celebrations' physics: real gravity, arcs that land where they are
// aimed, cards that fall, bounce and come to rest flat -- never through the
// table.

import test from "node:test";
import assert from "node:assert/strict";
import { Mesh, Object3D, Vector3 } from "three";
import { Flung, G, ballistic, hop, lowestBelow, random, spin } from "../src/celebrate/physics.js";
import { CARD } from "../src/units.js";

test("gravity is the real one, in centimetres", () => {
  assert.equal(G, 981);
});

test("a ballistic throw lands where it was aimed, when it was aimed", () => {
  for (const [p0, p1, T] of [
    [new Vector3(-120, 30, -80), new Vector3(10, 5, 40), 1.1],
    [new Vector3(0, 0, 0), new Vector3(0, 0, 0), 0.6],
    [new Vector3(200, 80, 0), new Vector3(-50, 0, 20), 1.8],
  ]) {
    const v = ballistic(p0, p1, T);
    const p = p0.clone();
    const dt = 1 / 2000;
    for (let t = 0; t < T - 1e-9; t += dt) {
      v.y -= G * dt;
      p.addScaledVector(v, dt);
    }
    assert.ok(p.distanceTo(p1) < 1, `${p.toArray()} vs ${p1.toArray()}`);
  }
});

test("a hop is a parabola: down at its ends, up at its middle", () => {
  assert.equal(hop(0), 0);
  assert.equal(hop(0.5), 1);
  assert.ok(Math.abs(hop(1.25) - hop(0.25)) < 1e-12, "one hop after another");
  assert.ok(Math.abs(hop(0.25) - 0.75) < 1e-12);
});

test("an eased spin starts from rest and reaches full rate without a jump", () => {
  const rate = (t) => (spin(t + 1e-4, 1, 3) - spin(t - 1e-4, 1, 3)) / 2e-4;
  assert.equal(spin(0.5, 1, 3), 0);
  assert.ok(rate(1.001) < 0.01, "from rest");
  assert.ok(Math.abs(rate(3.5) - 1) < 1e-6, "then one radian a second");
  assert.ok(Math.abs(spin(3 - 1e-9, 1, 3) - spin(3 + 1e-9, 1, 3)) < 1e-6, "continuous");
});

test("the generator is the same for the same seed, and stays in range", () => {
  const a = random(42);
  const b = random(42);
  for (let i = 0; i < 100; i++) {
    const x = a.range(-3, 5);
    assert.equal(x, b.range(-3, 5));
    assert.ok(x >= -3 && x < 5);
  }
});

test("a flung card falls, bounces, and comes to rest flat -- never through the table", () => {
  const rng = random(7);
  for (let n = 0; n < 40; n++) {
    const card = new Mesh();
    card.position.set(rng.range(-20, 20), rng.range(10, 60), rng.range(-20, 20));
    card.rotation.set(rng.range(0, 6), rng.range(0, 6), rng.range(0, 6), "YXZ");
    const flung = new Flung();
    let landed = 0;
    flung.add(card, new Vector3(rng.range(-80, 80), rng.range(0, 400), rng.range(-80, 80)), new Vector3(rng.range(-12, 12), rng.range(-12, 12), rng.range(-12, 12)), {
      onLand: () => (landed += 1),
    });
    const dt = 1 / 60;
    for (let t = 0; t < 4; t += dt) {
      flung.update(dt);
      card.updateMatrix();
      assert.ok(card.position.y - lowestBelow(card.quaternion) > -1e-6, `through the table at t=${t.toFixed(2)}`);
    }
    assert.ok(landed >= 1, "it struck the table");
    // Flat: its face normal straight up or down, resting on the table.
    const normal = new Vector3(0, 0, 1).applyQuaternion(card.quaternion);
    assert.ok(Math.abs(Math.abs(normal.y) - 1) < 1e-3, `lies flat (normal ${normal.toArray().map((x) => x.toFixed(3))})`);
    assert.ok(Math.abs(card.position.y - CARD.thickness / 2) < 0.01, "on the table");
  }
});

test("the lowest point of a card is half its thickness lying flat, half its height standing", () => {
  const flat = new Object3D();
  flat.rotation.set(-Math.PI / 2, 0.3, 0, "YXZ");
  assert.ok(Math.abs(lowestBelow(flat.quaternion) - CARD.thickness / 2) < 1e-9);
  const upright = new Object3D();
  assert.ok(Math.abs(lowestBelow(upright.quaternion) - CARD.height / 2) < 1e-9);
});
