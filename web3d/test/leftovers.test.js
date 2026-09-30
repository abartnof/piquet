// As elder, having taken fewer than five: the rest of your five is yours to
// look at (pagat: "If elder exchanges fewer than five cards he can look at
// the remainder of the five"), and you see which of them your opponent then
// draws. The engine says so in two events; the page says it again where it
// first matters, in the point's explanation.

import test from "node:test";
import assert from "node:assert/strict";
import { partie } from "./partie.js";

import { leftNote } from "../src/leftovers.js";

const states = (await Promise.all([[3, 7], [2, 23]].map(([l, s]) => partie(l, s)))).flat();
const atPoint = states.filter((s) => s.prompt.kind === "declare" && s.prompt.category === "point" && s.you_are === "elder");

test("as elder, you are told the cards you left, and which your opponent drew", () => {
  assert.ok(atPoint.length >= 4);
  for (const s of atPoint) {
    const mine = s.events.find((e) => e.kind === "exchanged" && e.deal === s.deal && e.who === "you").count;
    const looked = s.events.find((e) => e.kind === "looked" && e.deal === s.deal);
    const took = s.events.find((e) => e.kind === "they_took" && e.deal === s.deal);
    if (mine === 5) {
      assert.equal(looked, undefined);
      continue;
    }
    assert.equal(looked.cards.length, 5 - mine, "the rest of your five");
    assert.equal(looked.who, "you");
    for (const c of looked.cards) assert.ok(s.talon_seen.includes(c) && !s.hand.includes(c) && !s.discards.includes(c));
    assert.ok(took && took.who === "them" && took.cards.every((c) => looked.cards.includes(c)), "they drew yours first");
  }
});

test("the point's explanation says it in the cards' own names", () => {
  const s = atPoint.find((x) => x.events.some((e) => e.kind === "looked" && e.deal === x.deal));
  const looked = s.events.find((e) => e.kind === "looked" && e.deal === s.deal);
  const note = leftNote(s);
  assert.match(note, /^ You left /);
  // Every card you left is named, by rank and suit.
  for (const c of looked.cards) assert.ok(note.includes((c[0] === "T" ? "10" : c[0]) + { S: "♠", H: "♥", D: "♦", C: "♣" }[c[1]]), `${c} in "${note}"`);
  assert.match(note, /your opponent drew/);
  assert.doesNotMatch(note, /Cori|Norman|Cavendish|Hoyle|Foster/);
  // Younger, or elder who took all five: nothing to say.
  for (const x of states.filter((y) => y.you_are === "younger" && y.prompt.kind === "declare")) assert.equal(leftNote(x), "");
});
