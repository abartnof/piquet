// Easing: how a movement is distributed over its time.

import test from "node:test";
import assert from "node:assert/strict";
import { cubicBezier, evenly, friction, gravity, M3, minimumJerk } from "../src/easing.js";

const close = (a, b, eps = 1e-9) => Math.abs(a - b) <= eps;
const slope = (f, t, h = 1e-6) => (f(Math.min(1, t + h)) - f(Math.max(0, t - h))) / (Math.min(1, t + h) - Math.max(0, t - h));
const grid = (n = 200) => Array.from({ length: n + 1 }, (_, i) => i / n);

test("minimum jerk starts and ends at rest, with no jolt either end", () => {
  // Flash & Hogan (1985): the path of a human reaching movement.
  assert.equal(minimumJerk(0), 0);
  assert.equal(minimumJerk(1), 1);
  assert.ok(close(slope(minimumJerk, 0), 0, 1e-5));
  assert.ok(close(slope(minimumJerk, 1), 0, 1e-5));
  // Zero acceleration at both ends: s''(t) = 60t - 180t^2 + 120t^3.
  const accel = (t) => (slope(minimumJerk, t + 1e-4) - slope(minimumJerk, t - 1e-4)) / 2e-4;
  assert.ok(Math.abs(accel(1e-4)) < 0.05);
  assert.ok(Math.abs(accel(1 - 1e-4)) < 0.05);
});

test("minimum jerk is symmetric, and peaks at 1.875 times the mean speed", () => {
  for (const t of grid()) assert.ok(close(minimumJerk(1 - t), 1 - minimumJerk(t), 1e-12));
  assert.ok(close(slope(minimumJerk, 0.5), 1.875, 1e-6));
});

test("friction starts at speed and stops dead at the end, never before", () => {
  // Constant deceleration from an initial speed: s = 1 - (1 - t)^2.
  assert.equal(friction(0), 0);
  assert.equal(friction(1), 1);
  assert.ok(close(slope(friction, 0), 2, 1e-5));
  assert.ok(close(slope(friction, 1), 0, 1e-5));
  for (const t of grid().slice(0, -1)) assert.ok(slope(friction, t) > 0);
});

test("gravity starts from rest and arrives at speed", () => {
  assert.equal(gravity(0), 0);
  assert.equal(gravity(1), 1);
  assert.ok(close(slope(gravity, 0), 0, 1e-5));
  assert.ok(close(slope(gravity, 1), 2, 1e-5));
});

test("every easing is monotonic and clamps outside [0, 1]", () => {
  for (const f of [minimumJerk, friction, gravity, ...Object.values(M3)]) {
    assert.equal(f(-0.5), 0);
    assert.equal(f(1.5), 1);
    let last = -Infinity;
    for (const t of grid()) {
      const v = f(t);
      assert.ok(v >= last - 1e-12, `${f.name} goes backwards at ${t}`);
      last = v;
    }
  }
});

// A reference for a CSS cubic-bezier, independent of the solver: sample the
// parametric curve densely and read y off where x passes t.
function reference(x1, y1, x2, y2, t) {
  const bez = (a, b, u) => 3 * a * u * (1 - u) ** 2 + 3 * b * u * u * (1 - u) + u ** 3;
  const n = 200000;
  let prev = { x: 0, y: 0 };
  for (let i = 1; i <= n; i++) {
    const u = i / n;
    const p = { x: bez(x1, x2, u), y: bez(y1, y2, u) };
    if (p.x >= t) {
      const f = (t - prev.x) / (p.x - prev.x || 1);
      return prev.y + f * (p.y - prev.y);
    }
    prev = p;
  }
  return 1;
}

test("the cubic-bezier solver matches the curve it describes", () => {
  for (const [x1, y1, x2, y2] of [[0.2, 0, 0, 1], [0.05, 0.7, 0.1, 1], [0.3, 0, 0.8, 0.15], [0.25, 0.1, 0.25, 1]]) {
    const ease = cubicBezier(x1, y1, x2, y2);
    for (const t of [0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1]) {
      assert.ok(close(ease(t), reference(x1, y1, x2, y2, t), 2e-5), `(${x1},${y1},${x2},${y2}) at ${t}`);
    }
  }
});

test("Material 3's curves are the tokens @material/web ships", () => {
  // node_modules/@material/web/tokens/versions/latest/sass/_md-sys-motion.scss
  const probe = (f) => [0.1, 0.3, 0.5, 0.7, 0.9].map((t) => f(t));
  assert.deepEqual(probe(M3.standard), probe(cubicBezier(0.2, 0, 0, 1)));
  assert.deepEqual(probe(M3.emphasizedDecelerate), probe(cubicBezier(0.05, 0.7, 0.1, 1)));
  assert.deepEqual(probe(M3.emphasizedAccelerate), probe(cubicBezier(0.3, 0, 0.8, 0.15)));
  assert.deepEqual(probe(M3.standardDecelerate), probe(cubicBezier(0, 0, 0, 1)));
  assert.deepEqual(probe(M3.standardAccelerate), probe(cubicBezier(0.3, 0, 1, 1)));
});

test("evenly accelerated motion, from any starting speed; friction and gravity are its two ends", () => {
  for (const start of [0, 0.18, 1, 1.7, 2]) {
    const f = evenly(start);
    assert.equal(f(0), 0);
    assert.equal(f(1), 1);
    assert.ok(close(slope(f, 0), start, 1e-5));
    assert.ok(close(slope(f, 1), 2 - start, 1e-5));
  }
  for (const t of grid()) {
    assert.ok(close(evenly(2)(t), friction(t), 1e-12));
    assert.ok(close(evenly(0)(t), gravity(t), 1e-12));
  }
});
