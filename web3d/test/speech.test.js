// What the table says aloud, clip by clip, as Cavendish has players say it
// (docs/VOICE.md; Andrew: "maximal speaking (anything a human would say,
// we'll say)").

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { speech } from "../src/speech.js";
import { partie } from "./partie.js";

const ev = (kind, fields) => ({ deal: 1, text: "", ...fields, kind });
const said = (lines) => lines.map((l) => `${l.who}:${l.clip}`);

test("the point: its length called, the value asked for when needed, answered", () => {
  const lines = speech([
    ev("deal_begins", { elder: "you" }),
    ev("called", { who: "you", category: "point", said: "point of 5 (48)" }),
    ev("decided", { category: "point", winner: "you" }),
    ev("scored", { who: "you", amount: 5, category: "point", what: "point of 5 (48)" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["you:point-5", "them:what-make", "you:value-48", "them:good", "you:n-5"]);
});

test("sequences and sets called in full, as Cavendish calls them", () => {
  const lines = speech([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", category: "sequences", said: "quint to the ace, tierce to the jack" }),
    ev("decided", { category: "sequences", winner: "them" }),
    ev("called", { who: "them", category: "sets", said: "quatorze of tens, trio of queens" }),
    ev("decided", { category: "sets", winner: "you" }),
  ], 1, 0);
  assert.deepEqual(said(lines), [
    "them:seq-5-ace", "them:seq-3-knave", "you:good",
    "them:set-4-ten", "them:set-3-queen", "you:not-good",
  ]);
});

// Younger speaks in the dialogue only to answer; what she holds she names as
// she reckons it, each holding with her count (Cavendish p. 77: "Four tens
// fourteen, and three queens seventeen").
test("younger names what she won as she reckons it, each with her count", () => {
  const lines = speech([
    ev("deal_begins", { elder: "you" }),
    ev("called", { who: "them", category: "sets", said: "trio" }),
    ev("showed", { who: "them", what: "trio of aces" }),
    ev("scored", { who: "them", amount: 3, category: "sequences", what: "tierce to the ace" }),
    ev("scored", { who: "them", amount: 6, category: "sets", what: "trio of aces, trio of queens" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["them:seq-3-ace", "them:n-3", "them:set-3-ace", "them:set-3-queen", "them:n-9"]);
});

test("younger never repeats a call she lost", () => {
  const lines = speech([
    ev("deal_begins", { elder: "you" }),
    ev("called", { who: "you", category: "point", said: "point of 5 (50)" }),
    ev("decided", { category: "point", winner: "you" }),
    ev("scored", { who: "you", amount: 5, category: "point", what: "point of 5 (50)" }),
    ev("called", { who: "them", category: "point", said: "point of 5" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["you:point-5", "them:what-make", "you:value-50", "them:good", "you:n-5"]);
});

test("younger's point, when she wins it, is named as she reckons it", () => {
  const lines = speech([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", category: "point", said: "point of 4" }),
    ev("decided", { category: "point", winner: "you" }),
    ev("called", { who: "you", category: "point", said: "point of 5" }),
    ev("scored", { who: "you", amount: 5, category: "point", what: "point of 5 (47)" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["them:point-4", "you:not-good", "you:point-5", "you:n-5"]);
});

test("counting aloud: each side's running total, and the great moments named", () => {
  const lines = speech([
    ev("deal_begins", { elder: "you" }),
    ev("scored", { who: "you", amount: 15, category: "sequences", what: "quint to the ace" }),
    ev("scored", { who: "you", amount: 1, category: "play", what: "leading A♠" }),
    ev("scored", { who: "you", amount: 60, category: "bonus", what: "repique" }),
    ev("scored", { who: "them", amount: 1, category: "play", what: "winning with K♣" }),
    ev("scored", { who: "you", amount: 40, category: "cards", what: "capot" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["you:n-15", "you:n-16", "you:repique", "you:n-76", "them:n-1", "you:capot", "you:n-116"]);
});

test("the exchange announced when elder takes fewer than five, and the dealer chosen", () => {
  const lines = speech([
    ev("first_dealer", { deal: 0, chooser: "them", dealer: "them" }),
    ev("deal_begins", { elder: "you" }),
    ev("exchanged", { who: "you", count: 3 }),
    ev("exchanged", { who: "them", count: 3 }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["you:take-3"]);
  assert.deepEqual(said(speech([ev("first_dealer", { deal: 0, chooser: "them", dealer: "them" })], 0, 0)), ["them:my-deal"]);
});

test("your opponent hands you the choice of deal when you cut higher", () => {
  const lines = speech([ev("choice_of_deal", { deal: 0, who: "you" }), ev("choice_of_deal", { deal: 0, who: "them" })], 0, 0);
  assert.deepEqual(said(lines), ["them:your-choice"]);
});

test("a deal you win handsomely is remarked on, and only such a deal", () => {
  const big = speech([ev("deal_ends", { you: 64, them: 12 })], 1, 0);
  assert.deepEqual(said(big), ["them:well-played"]);
  const close = speech([ev("deal_ends", { you: 30, them: 12 })], 1, 0);
  assert.deepEqual(said(close), []);
  const lost = speech([ev("deal_ends", { you: 5, them: 64 })], 1, 0);
  assert.deepEqual(said(lost), []);
});

test("a nicety at the end: congratulations if you win, good game if not", () => {
  const won = speech([ev("partie_ends", { deal: 6, you: 180, them: 90 })], 6, 0);
  assert.deepEqual(said(won), ["them:congratulations"]);
  const lost = speech([ev("partie_ends", { deal: 6, you: 90, them: 180 })], 6, 0);
  assert.deepEqual(said(lost), ["them:good-game"]);
});

test("only what is new is said", () => {
  const events = [
    ev("deal_begins", { elder: "you" }),
    ev("called", { who: "you", category: "point", said: "point of 4" }),
    ev("decided", { category: "point", winner: "them" }),
  ];
  assert.deepEqual(said(speech(events, 1, 2)), ["them:not-good"]);
});

// Every clip the game asks for must have been recorded, in every voice, and
// said in more than one way.
test("across whole parties, every clip asked for exists in the voices' bank", () => {
  const manifest = JSON.parse(readFileSync(new URL("../audio/cori/manifest.json", import.meta.url)));
  const have = new Set(Object.keys(manifest.groups).filter((id) => manifest.groups[id].length >= 2));
  return Promise.all([[3, 7], [1, 11], [2, 23], [3, 404]].map(([l, s]) => partie(l, s))).then((parties) => {
    let asked = 0;
    for (const states of parties) {
      const end = states[states.length - 1];
      for (let deal = 0; deal <= end.deal; deal++) {
        for (const line of speech(end.events, deal, 0)) {
          asked += 1;
          assert.ok(have.has(line.clip), `no clip ${line.clip}`);
        }
      }
    }
    assert.ok(asked > 400, `only ${asked} clips asked for`);
  });
});
