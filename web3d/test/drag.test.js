// A panel the player may drag about a phone's screen (the user: "make it
// floating so you can drag it around, since mobile phone real estate is
// sparce"): it can never be lost off the edge, and a tap is still a tap.

import test from "node:test";
import assert from "node:assert/strict";
import { DRAG_FROM, MARGIN, isDrag, keepOnScreen } from "../src/drag.js";

const PHONE = { width: 390, height: 664 };
const CARD = { width: 324, height: 140 };

test("a panel already on the screen stays where it was put", () => {
  assert.deepEqual(keepOnScreen({ x: 30, y: 200 }, CARD, PHONE), { x: 30, y: 200 });
});

test("dragged past an edge, it stops a margin short of it", () => {
  assert.deepEqual(keepOnScreen({ x: 300, y: 600 }, CARD, PHONE), { x: PHONE.width - CARD.width - MARGIN, y: PHONE.height - CARD.height - MARGIN });
  assert.deepEqual(keepOnScreen({ x: -50, y: -20 }, CARD, PHONE), { x: MARGIN, y: MARGIN });
});

test("a panel bigger than the screen keeps its top-left corner in view", () => {
  assert.deepEqual(keepOnScreen({ x: 100, y: 100 }, { width: 500, height: 900 }, PHONE), { x: MARGIN, y: MARGIN });
});

test("a press becomes a drag only once it has travelled a little: a tap still opens the card", () => {
  assert.equal(isDrag({ x: 10, y: 10 }, { x: 12, y: 13 }), false);
  assert.equal(isDrag({ x: 10, y: 10 }, { x: 10, y: 10 + DRAG_FROM }), true);
});
