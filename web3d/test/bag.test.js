// Saying a thing several ways without repeating yourself (the user: "i don't
// want *any* sounds to be repetitive"): every way once before any again,
// and never the same way twice running.

import test from "node:test";
import assert from "node:assert/strict";
import { createBags } from "../src/bag.js";

// A seeded generator, so a failure can be replayed.
function seeded(seed) {
  let x = seed >>> 0;
  return () => ((x = (x * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}

const WAYS = ["good.0", "good.1", "good.2", "good.3", "good.4"];

test("every way is heard once before any is heard again", () => {
  const pick = createBags(seeded(7));
  for (let round = 0; round < 40; round++) {
    const heard = WAYS.map(() => pick("them/good", WAYS));
    assert.deepEqual([...heard].sort(), [...WAYS].sort(), `round ${round}`);
  }
});

test("never the same way twice running, even as the bag is refilled", () => {
  for (const seed of [1, 2, 3, 4, 5]) {
    const pick = createBags(seeded(seed));
    let last = null;
    for (let i = 0; i < 2000; i++) {
      const way = pick("them/good", WAYS.slice(0, 2));
      assert.notEqual(way, last, `seed ${seed}, pick ${i}`);
      last = way;
    }
  }
});

test("each thing has its own bag, and each speaker theirs", () => {
  const pick = createBags(seeded(3));
  const a = [pick("them/good", WAYS), pick("them/good", WAYS)];
  const b = WAYS.map(() => pick("you/good", WAYS));
  assert.deepEqual([...b].sort(), [...WAYS].sort());
  assert.notEqual(a[0], a[1]);
});

test("one way is always that way; none is nothing", () => {
  const pick = createBags(seeded(9));
  assert.equal(pick("x", ["only.0"]), "only.0");
  assert.equal(pick("x", ["only.0"]), "only.0");
  assert.equal(pick("y", []), null);
  assert.equal(pick("z", undefined), null);
});
