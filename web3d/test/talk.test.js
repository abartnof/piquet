// What is said at the table, as the dialogue box shows it: your opponent's
// words and points in one half, yours in the other (the user: "we speak a LOT
// in piquet- those things we say during gameplay are a part of the game").

import test from "node:test";
import assert from "node:assert/strict";
import { talk } from "../src/talk.js";
import { partie } from "./partie.js";

const states = await partie(3, 7);
const final = states[states.length - 1];

const ev = (kind, fields) => ({ deal: 1, text: "", ...fields, kind });

test("each side's words go to its own half, in the order they were said", () => {
  const t = talk([
    ev("called", { who: "you", said: "point of 5 (50)", category: "point" }),
    ev("called", { who: "them", said: "tierce", category: "sequences" }),
    ev("called", { who: "you", said: "nothing", category: "sets" }),
  ], 1);
  assert.deepEqual(t.you.map((l) => l.text), ["“Point of 5 (50).”", "“Nothing.”"]);
  assert.deepEqual(t.them.map((l) => l.text), ["“Tierce.”"]);
  assert.ok(t.you.every((l) => l.kind === "said"));
});

test("points scored are summed up where they were won, with what won them", () => {
  const t = talk([
    ev("scored", { who: "them", amount: 3, what: "tierce to the ace", category: "sequences" }),
    ev("scored", { who: "them", amount: 6, what: "trio of aces, trio of queens", category: "sets" }),
    ev("scored", { who: "you", amount: 5, what: "point of 5 (50)", category: "point" }),
  ], 1);
  assert.deepEqual(t.them.map((l) => [l.points, l.text]), [[3, "Tierce to the ace"], [6, "Trio of aces, trio of queens"]]);
  assert.deepEqual(t.you.map((l) => [l.points, l.text]), [[5, "Point of 5 (50)"]]);
  assert.equal(t.total.them, 9);
  assert.equal(t.total.you, 5);
});

test("a card and the point it makes are one line: led, or won with", () => {
  const t = talk([
    ev("played", { who: "you", card: "AS" }),
    ev("scored", { who: "you", amount: 1, what: "leading A♠", category: "play" }),
    ev("played", { who: "them", card: "QS" }),
    ev("took_trick", { who: "you", number: 1 }),
    ev("played", { who: "them", card: "KC" }),
    ev("played", { who: "you", card: "9C" }),
    ev("took_trick", { who: "them", number: 2 }),
    ev("scored", { who: "them", amount: 1, what: "winning with K♣", category: "play" }),
  ], 1);
  assert.deepEqual(t.you.map((l) => [l.text, l.points ?? null]), [
    ["Leads A♠", 1],
    ["Takes trick 1", null],
    ["Plays 9♣", null],
  ]);
  assert.deepEqual(t.them.map((l) => [l.text, l.points ?? null]), [
    ["Plays Q♠", null],
    ["Leads K♣", null],
    ["Takes trick 2", 1],
  ]);
});

// Younger answers elder's call, as the books have it: "good" if elder's is
// better, "not good" if hers is, "equal" if neither's is. Elder who calls
// nothing is answered by nobody: younger simply takes it.
test("younger answers each call: good, not good, or equal", () => {
  const begins = ev("deal_begins", { elder: "you" });
  const t = talk([
    begins,
    ev("called", { who: "you", said: "point of 5 (50)", category: "point" }),
    ev("decided", { category: "point", winner: "you" }),
    ev("called", { who: "you", said: "tierce to the jack", category: "sequences" }),
    ev("decided", { category: "sequences", winner: "them" }),
    ev("called", { who: "you", said: "nothing", category: "sets" }),
    ev("decided", { category: "sets", winner: "them" }),
  ], 1);
  assert.deepEqual(t.them.map((l) => l.text), ["“Good.”", "“Not good.”", "Takes sets"]);
  assert.deepEqual(t.them.filter((l) => l.kind === "answer").map((l) => [l.category, l.winner]),
    [["point", "you"], ["sequences", "them"]], "an answer knows what it answered, and who won");
  assert.deepEqual(t.you.map((l) => l.text), ["“Point of 5 (50).”", "“Tierce to the jack.”", "“Nothing.”"]);

  const equal = talk([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", said: "trio", category: "sets" }),
    ev("decided", { category: "sets", winner: null }),
  ], 1);
  assert.deepEqual(equal.you.map((l) => l.text), ["“Equal.”"]);
  assert.deepEqual(equal.table.map((l) => l.text).slice(-1), ["Sets are equal: neither scores"]);
});

test("only this deal is told, and every line is numbered in the order it happened", () => {
  const t = talk(final.events, 2);
  const lines = [...t.you, ...t.them, ...t.table];
  assert.ok(lines.length > 10);
  const order = lines.map((l) => l.at).sort((a, b) => a - b);
  assert.equal(new Set(order).size, order.length, "no two lines share a place");
  const deal2 = final.events.map((e, i) => [e, i]).filter(([e]) => e.deal === 2).map(([, i]) => i);
  assert.ok(order.every((i) => deal2.includes(i)), "every line is from deal 2");
});

test("the halves' totals are the deal's scores, for every deal of a whole partie", () => {
  for (const s of states) {
    if (s.phase === "cut") continue;
    const t = talk(s.events, s.deal);
    assert.deepEqual(t.total, { you: s.score.you, them: s.score.them }, `deal ${s.deal}, ${s.phase}`);
  }
});

test("every event of a partie is told somewhere, or deliberately left to the table", () => {
  for (let deal = 1; deal <= 6; deal++) {
    const t = talk(final.events, deal);
    for (const l of [...t.you, ...t.them, ...t.table]) {
      assert.ok(typeof l.text === "string" && l.text.length > 0);
      assert.ok(!/undefined|null|\[object/.test(l.text), l.text);
    }
  }
});

// The user: "think about how during WNBA broadcasts, 3-pointers have a little
// on-screen animation in the score box. something like that would be fun
// for special events (not for every event)".
test("the rare big moments carry a flourish, and ordinary points do not", () => {
  const t = talk([
    ev("deal_begins", { elder: "you", you_total: 140, them_total: 20 }), // over already: no rubicon moment
    ev("scored", { who: "you", amount: 10, what: "carte blanche", category: "carte_blanche" }),
    ev("scored", { who: "you", amount: 4, what: "point of 4", category: "point" }),
    ev("scored", { who: "you", amount: 16, what: "sixième to the king", category: "sequences" }),
    ev("scored", { who: "them", amount: 3, what: "tierce to the ace", category: "sequences" }),
    ev("scored", { who: "you", amount: 14, what: "quatorze of aces", category: "sets" }),
    ev("scored", { who: "them", amount: 3, what: "trio of kings", category: "sets" }),
    ev("scored", { who: "you", amount: 60, what: "repique", category: "bonus" }),
    ev("scored", { who: "them", amount: 30, what: "pique", category: "bonus" }),
    ev("scored", { who: "you", amount: 40, what: "capot", category: "cards" }),
    ev("scored", { who: "them", amount: 10, what: "the cards", category: "cards" }),
  ], 1);
  const flair = (half) => t[half].map((l) => l.flair ?? null);
  assert.deepEqual(flair("you"), ["Carte blanche", null, "Sixième", "Quatorze", "Repique", "Capot"]);
  assert.deepEqual(flair("them"), [null, null, "Pique", null]);
});

test("crossing the rubicon is a moment, once, on the point that carries a side over", () => {
  const t = talk([
    ev("deal_begins", { elder: "them", you_total: 90, them_total: 60 }),
    ev("scored", { who: "you", amount: 5, what: "point of 5", category: "point" }),
    ev("scored", { who: "you", amount: 6, what: "trio of aces, trio of queens", category: "sets" }),
    ev("scored", { who: "you", amount: 3, what: "tierce", category: "sequences" }),
    ev("scored", { who: "them", amount: 30, what: "pique", category: "bonus" }),
  ], 1);
  assert.deepEqual(t.you.map((l) => l.flair ?? null), [null, "Over the rubicon", null]);
  assert.deepEqual(t.them.map((l) => l.flair ?? null), ["Pique"], "60 + 30 is still short: the pique is the moment");
});
