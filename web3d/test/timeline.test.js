// The timeline: motions run against the clock.

import test from "node:test";
import assert from "node:assert/strict";
import { Timeline } from "../src/timeline.js";

// A path that just reports its t, so what was applied is what was asked for.
const trace = (t) => ({ t });

function recorder() {
  const applied = new Map();
  const apply = (target, pose) => applied.set(target, pose.t);
  return { applied, apply };
}

test("a motion is applied at its fraction of its duration", () => {
  const { applied, apply } = recorder();
  const timeline = new Timeline({ apply });
  timeline.add({ target: "a", path: trace, delay: 100, duration: 400 }, 1000);
  timeline.tick(1100);
  assert.equal(applied.get("a"), 0);
  timeline.tick(1300);
  assert.equal(applied.get("a"), 0.5);
});

test("nothing moves before it starts", () => {
  const { applied, apply } = recorder();
  const timeline = new Timeline({ apply });
  timeline.add({ target: "a", path: trace, delay: 500, duration: 100 }, 0);
  timeline.tick(200);
  assert.equal(applied.has("a"), false);
  assert.equal(timeline.busy(), true, "a motion waiting to start keeps the timeline busy");
});

test("a frame that skips past the end still lands exactly on it", () => {
  const { applied, apply } = recorder();
  const timeline = new Timeline({ apply });
  timeline.add({ target: "a", path: trace, duration: 100 }, 0);
  timeline.tick(5000);
  assert.equal(applied.get("a"), 1);
  assert.equal(timeline.busy(), false);
});

test("the speed setting scales every delay and duration", () => {
  const { applied, apply } = recorder();
  const timeline = new Timeline({ apply, speed: 2 });
  timeline.add({ target: "a", path: trace, delay: 200, duration: 400 }, 0);
  timeline.tick(100);
  assert.equal(applied.get("a"), 0);
  timeline.tick(200);
  assert.equal(applied.get("a"), 0.5);
});

test("a zero duration lands at once: the test mode, and reduced motion", () => {
  const { applied, apply } = recorder();
  const timeline = new Timeline({ apply });
  timeline.add({ target: "a", path: trace, duration: 0 }, 0);
  timeline.tick(0);
  assert.equal(applied.get("a"), 1);
});

test("skip lands everything on its end at once", () => {
  const { applied, apply } = recorder();
  const timeline = new Timeline({ apply });
  timeline.add({ target: "a", path: trace, duration: 400 }, 0);
  timeline.add({ target: "b", path: trace, delay: 900, duration: 400 }, 0);
  timeline.tick(100);
  timeline.skip();
  assert.equal(applied.get("a"), 1);
  assert.equal(applied.get("b"), 1);
  assert.equal(timeline.busy(), false);
});

test("motions on one card apply in the order they start, so the later one wins", () => {
  const { applied, apply } = recorder();
  const timeline = new Timeline({ apply });
  timeline.add({ target: "a", path: () => ({ t: "second" }), delay: 100, duration: 100 }, 0);
  timeline.add({ target: "a", path: () => ({ t: "first" }), delay: 0, duration: 300 }, 0);
  timeline.tick(150);
  assert.equal(applied.get("a"), "second");
});

test("idle resolves when the last motion lands, and at once when there is none", async () => {
  const { apply } = recorder();
  const timeline = new Timeline({ apply });
  await timeline.idle();
  timeline.add({ target: "a", path: trace, duration: 100 }, 0);
  let done = false;
  const waiting = timeline.idle().then(() => (done = true));
  timeline.tick(50);
  await Promise.resolve();
  assert.equal(done, false);
  timeline.tick(100);
  await waiting;
  assert.equal(done, true);
});

test("a motion can say when it has landed", () => {
  const { apply } = recorder();
  const timeline = new Timeline({ apply });
  const landed = [];
  timeline.add({ target: "a", path: trace, duration: 100, onDone: () => landed.push("a") }, 0);
  timeline.tick(50);
  assert.deepEqual(landed, []);
  timeline.tick(100);
  timeline.tick(200);
  assert.deepEqual(landed, ["a"], "exactly once");
});

test("a motion can say when it has begun, once, before its first pose", () => {
  const order = [];
  const timeline = new Timeline({ apply: (target, pose) => order.push(`pose ${pose.t}`) });
  timeline.add({ target: "a", path: trace, delay: 100, duration: 100, onStart: () => order.push("start") }, 0);
  timeline.tick(50);
  timeline.tick(150);
  timeline.tick(160);
  assert.deepEqual(order, ["start", "pose 0.5", "pose 0.6"]);
});

test("skipping still says a motion began", () => {
  const order = [];
  const timeline = new Timeline({ apply: () => {} });
  timeline.add({ target: "a", path: trace, delay: 100, duration: 100, onStart: () => order.push("start"), onDone: () => order.push("done") }, 0);
  timeline.skip();
  assert.deepEqual(order, ["start", "done"]);
});

test("one card's motions finish in order: hidden as one lands, then shown as the next begins", () => {
  for (const drive of [(tl) => tl.skip(), (tl) => tl.tick(1000)]) {
    let face = "AS";
    const timeline = new Timeline({ apply: () => {} });
    timeline.add({ target: "a", path: trace, delay: 0, duration: 100, onDone: () => (face = null) }, 0);
    timeline.add({ target: "a", path: trace, delay: 100, duration: 100, onStart: () => (face = "KD") }, 0);
    drive(timeline);
    assert.equal(face, "KD");
  }
});
