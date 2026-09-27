// The order of the human's hand: the 2D page's grouping, for the 3D fan.

import test from "node:test";
import assert from "node:assert/strict";
import { arrange, sortMode } from "../src/hand.js";

const state = (over) => ({
  hand: ["AS", "KS", "9H", "AD", "KD", "QD", "JD", "7C", "AC", "8S", "9S", "TS"],
  worth: [
    { text: "point of 4 (40)", category: "point", cards: ["AD", "KD", "QD", "JD"] },
    { text: "quart to the ace", category: "sequences", cards: ["AD", "KD", "QD", "JD"] },
    { text: "trio of aces", category: "sets", cards: ["AS", "AD", "AC"] },
  ],
  prompt: { kind: "exchange", limit: 5 },
  ...over,
});

test("auto sorts by combination while the hand is being shaped, by suit in play", () => {
  assert.equal(sortMode(state(), "auto"), "combos");
  assert.equal(sortMode(state({ prompt: { kind: "declare" } }), "auto"), "combos");
  assert.equal(sortMode(state({ prompt: { kind: "play", legal: [] } }), "auto"), "suit");
  assert.equal(sortMode(state(), "rank"), "rank");
});

test("by suit: spades, hearts, clubs, diamonds -- so the colours alternate -- high first", () => {
  const groups = arrange(state(), "suit");
  assert.deepEqual(groups, [["AS", "KS", "TS", "9S", "8S"], ["9H"], ["AC", "7C"], ["AD", "KD", "QD", "JD"]]);
});

test("by rank: aces together, then kings, and so on", () => {
  const groups = arrange(state(), "rank");
  assert.deepEqual(groups[0], ["AS", "AC", "AD"]);
  assert.deepEqual(groups[1], ["KS", "KD"]);
});

test("by combination: the best holdings first, each card once, then the rest", () => {
  const groups = arrange(state(), "combos");
  assert.deepEqual(groups[0], ["AD", "KD", "QD", "JD"]);
  assert.deepEqual(groups[1], ["AS", "AC"]); // the ace of diamonds is already placed
  assert.deepEqual(groups.flat().sort(), [...state().hand].sort());
});

test("every mode keeps every card exactly once", () => {
  for (const mode of ["suit", "rank", "combos"]) {
    assert.deepEqual(arrange(state(), mode).flat().sort(), [...state().hand].sort());
  }
});
