// Where the declarations' rounds begin, for a moment on the screen between
// them (the user: "an on-screen thing pop up for a moment before each part of
// the declarations, after each player is done speaking from the last one.
// they may start again once the on-screen thing is gone").

import test from "node:test";
import assert from "node:assert/strict";
import { breaksBetween } from "../src/breaks.js";
import { partie } from "./partie.js";

const parties = await Promise.all([[3, 7], [2, 23], [1, 5]].map(([l, s]) => partie(l, s)));
const steps = parties.flatMap((states) => states.slice(1).map((next, i) => ({ prev: states[i], next })));
const ROUNDS = ["point", "sequences", "sets"];
const isWord = (e, deal) => e.deal === deal && ["called", "nothing_to_call", "decided", "showed"].includes(e.kind) && ROUNDS.includes(e.category);

test("every deal's three rounds are each introduced once, in order", () => {
  for (const [p, states] of parties.entries()) {
    const byDeal = new Map();
    for (let i = 1; i < states.length; i++) {
      for (const b of breaksBetween(states[i - 1], states[i])) {
        const deal = states[i].deal;
        byDeal.set(deal, [...(byDeal.get(deal) ?? []), b.category]);
      }
    }
    assert.equal(byDeal.size, 6, `partie ${p}: ${[...byDeal.keys()]}`);
    for (const [deal, rounds] of byDeal) assert.deepEqual(rounds, ROUNDS, `partie ${p} deal ${deal}`);
  }
});

test("a round is introduced just before its first word -- or, when you open it, after everything in the move", () => {
  const seen = { before: 0, after: 0 };
  for (const { prev, next } of steps) {
    for (const b of breaksBetween(prev, next)) {
      if (b.at < next.events.length) {
        const e = next.events[b.at];
        assert.ok(b.at >= prev.events.length, "a word already said");
        assert.ok(isWord(e, next.deal) && e.category === b.category, `${e.kind} ${e.category} for ${b.category}`);
        assert.ok(!next.events.slice(0, b.at).some((x) => isWord(x, next.deal) && x.category === b.category), `${b.category} had begun`);
        seen.before++;
      } else {
        assert.equal(b.at, next.events.length);
        assert.equal(next.prompt.kind, "declare");
        assert.equal(next.prompt.category, b.category);
        assert.ok(!next.events.some((x) => isWord(x, next.deal) && x.category === b.category), `${b.category} had begun`);
        seen.after++;
      }
    }
  }
  // Both: your opponent opening a round mid-move, and you opening one.
  assert.ok(seen.before > 10 && seen.after > 10, JSON.stringify(seen));
});

test("in order within a move, and none going back", () => {
  for (const { prev, next } of steps) {
    const at = breaksBetween(prev, next).map((b) => b.at);
    assert.deepEqual(at, [...at].sort((a, b) => a - b));
    assert.deepEqual(breaksBetween(next, prev), [], "an undo");
  }
});

test("declaring for you: every round in one move, each introduced", () => {
  const deal = 1;
  const word = (kind, category, who) => ({ kind, category, who, deal });
  const prev = { deal, events: [{ kind: "deal_begins", deal }], prompt: { kind: "exchange" } };
  const next = {
    deal,
    events: [
      ...prev.events,
      { kind: "exchanged", who: "you", deal },
      word("called", "point", "you"), word("decided", "point"), { kind: "scored", category: "point", deal },
      word("called", "sequences", "you"), word("decided", "sequences"),
      word("nothing_to_call", "sets"), word("decided", "sets"),
      { kind: "played", who: "you", deal },
    ],
    prompt: { kind: "play" },
  };
  assert.deepEqual(breaksBetween(prev, next), [
    { at: 2, category: "point" },
    { at: 5, category: "sequences" },
    { at: 7, category: "sets" },
  ]);
});
