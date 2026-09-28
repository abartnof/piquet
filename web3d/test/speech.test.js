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

// The declarations, as Cavendish has them spoken (pp. 60-67): elder calls
// the shape; only when younger holds the same shape does she ask for the
// tie-break -- the point's value, the sequence's top card, the set's rank --
// and elder gives it; then she answers. Your opponent's calls reach the page
// as the shape first and the tie-break after the decision; yours in full.

test("your opponent calls a point, and you answer at once when the length decides it", () => {
  const lines = speech([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", category: "point", said: "point of 5" }),
    ev("called", { who: "you", category: "point", said: "point of 4 (38)" }),
    ev("decided", { category: "point", winner: "them", asked: false }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["them:point-5", "you:good"]);
});

test("your opponent's point of equal length: you ask what it makes, they tell you, then you answer", () => {
  const lines = speech([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", category: "point", said: "point of 4" }),
    ev("called", { who: "you", category: "point", said: "point of 4 (40)" }),
    ev("decided", { category: "point", winner: "them", asked: true }),
    ev("called", { who: "them", category: "point", said: "point of 4, making 41" }),
    ev("showed", { who: "them", what: "point of 4 (41)" }),
    ev("scored", { who: "them", amount: 4, category: "point", what: "point of 4 (41)" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["them:point-4", "you:what-make", "them:value-41", "you:good", "them:n-4"]);
});

test("your opponent's sequence and set: the shape, and the top or the rank only when asked", () => {
  const lines = speech([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", category: "sequences", said: "quart" }),
    ev("decided", { category: "sequences", winner: "you", asked: false }),
    ev("called", { who: "them", category: "sets", said: "trio" }),
    ev("decided", { category: "sets", winner: "them", asked: true }),
    ev("called", { who: "them", category: "sets", said: "trio of kings" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["them:seq-4", "you:not-good", "them:set-3", "you:what-set", "them:set-3-king", "you:good"]);
});

test("a sequence of equal length: how high?", () => {
  const lines = speech([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", category: "sequences", said: "tierce" }),
    ev("decided", { category: "sequences", winner: null, asked: true }),
    ev("called", { who: "them", category: "sequences", said: "tierce to the queen" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["them:seq-3", "you:how-high", "them:seq-3-queen", "you:equal"]);
});

test("your own point: its length, and what it makes only when you are asked", () => {
  const plain = speech([
    ev("deal_begins", { elder: "you" }),
    ev("called", { who: "you", category: "point", said: "point of 5 (48)" }),
    ev("decided", { category: "point", winner: "you", asked: false }),
    ev("scored", { who: "you", amount: 5, category: "point", what: "point of 5 (48)" }),
  ], 1, 0);
  assert.deepEqual(said(plain), ["you:point-5", "them:good", "you:n-5"]);
  const asked = speech([
    ev("deal_begins", { elder: "you" }),
    ev("called", { who: "you", category: "point", said: "point of 5 (48)" }),
    ev("decided", { category: "point", winner: "you", asked: true }),
  ], 1, 0);
  assert.deepEqual(said(asked), ["you:point-5", "them:what-make", "you:value-48", "them:good"]);
});

test("your own sequences: the best one's shape, and its top when asked", () => {
  const lines = speech([
    ev("deal_begins", { elder: "you" }),
    ev("called", { who: "you", category: "sequences", said: "quart to the king, tierce to the ten" }),
    ev("decided", { category: "sequences", winner: "them", asked: true }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["you:seq-4", "them:how-high", "you:seq-4-king", "them:not-good"]);
});

test("nothing to call, as elder: said so", () => {
  const lines = speech([
    ev("deal_begins", { elder: "you" }),
    ev("nothing_to_call", { category: "sets" }),
    ev("decided", { category: "sets", winner: "them", asked: false }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["you:nothing"]);
  const younger = speech([ev("deal_begins", { elder: "them" }), ev("nothing_to_call", { category: "sets" })], 1, 0);
  assert.deepEqual(said(younger), []);
});

test("elder names what was never said aloud as he reckons it", () => {
  const lines = speech([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", category: "sets", said: "trio" }),
    ev("decided", { category: "sets", winner: "them", asked: false }),
    ev("scored", { who: "them", amount: 6, category: "sets", what: "trio of aces, trio of kings" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["them:set-3", "you:good", "them:set-3-ace", "them:set-3-king", "them:n-6"]);
});

test("sequences and sets called in full, as Cavendish calls them, when the tie-break is asked", () => {
  const lines = speech([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", category: "sequences", said: "quint" }),
    ev("decided", { category: "sequences", winner: "them", asked: true }),
    ev("called", { who: "them", category: "sequences", said: "quint to the ace" }),
    ev("called", { who: "them", category: "sets", said: "quatorze" }),
    ev("decided", { category: "sets", winner: "you", asked: false }),
  ], 1, 0);
  assert.deepEqual(said(lines), [
    "them:seq-5", "you:how-high", "them:seq-5-ace", "you:good",
    "them:set-4", "you:not-good",
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

test("younger's point, when she wins it, is named as she reckons it", () => {
  const lines = speech([
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", category: "point", said: "point of 4" }),
    ev("decided", { category: "point", winner: "you", asked: false }),
    ev("called", { who: "you", category: "point", said: "point of 5" }),
    ev("scored", { who: "you", amount: 5, category: "point", what: "point of 5 (47)" }),
  ], 1, 0);
  assert.deepEqual(said(lines), ["them:point-4", "you:not-good", "you:point-5", "you:n-5"]);
});

// The dialogue boxes show the declarations' lines (Andrew: "two dialogue
// boxes to pop up every move"): each line says which kind of event it
// belongs to.
test("each line knows the kind of event it belongs to", () => {
  const lines = speech([
    ev("deal_begins", { elder: "you" }),
    ev("exchanged", { who: "you", count: 4 }),
    ev("called", { who: "you", category: "point", said: "point of 5 (48)" }),
    ev("decided", { category: "point", winner: "you", asked: true }),
    ev("scored", { who: "you", amount: 5, category: "point", what: "point of 5 (48)" }),
  ], 1, 0);
  assert.deepEqual(lines.map((l) => `${l.clip}@${l.kind}`), [
    "take-4@exchanged", "point-5@called", "what-make@decided", "value-48@decided", "good@decided", "n-5@scored",
  ]);
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
  // (No call was heard, so the quint is named as it is reckoned.)
  assert.deepEqual(said(lines), ["you:seq-5-ace", "you:n-15", "you:n-16", "you:repique", "you:n-76", "them:n-1", "you:capot", "you:n-116"]);
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
    ev("called", { who: "you", category: "point", said: "point of 4 (33)" }),
    ev("decided", { category: "point", winner: "them", asked: false }),
  ];
  assert.deepEqual(said(speech(events, 1, 2)), ["them:not-good"]);
});

// Every clip the game asks for must have been recorded, in every voice, and
// said in more than one way.
test("across whole parties, every clip asked for exists in the phrase bank", () => {
  const bank = JSON.parse(readFileSync(new URL("../words.json", import.meta.url)));
  const have = new Set(Object.keys(bank.groups).filter((id) => bank.groups[id].length >= 2));
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

// ---- QC over simulated parties ---------------------------------------------
//
// Andrew: "simulate a few games to make sure the audio passes your QC". The
// page speaks each move's new events as it happens; spoken so, whole parties
// must say exactly what each deal says spoken at once, and every declaration
// must run as Cavendish has it.
const SHAPE = /^(point-\d|seq-\d$|set-\d$|nothing$)/;
const ASK = { point: "what-make", sequences: "how-high", sets: "what-set" };
const TIE = { point: /^value-\d+$/, sequences: /^seq-\d-\w+$/, sets: /^set-\d-\w+$/ };
const ANSWER = new Set(["good", "not-good", "equal"]);

test("QC: simulated parties are spoken whole, once, in Cavendish's order, counting true", async () => {
  const parties = await Promise.all([[1, 5], [2, 17], [3, 7], [3, 404], [4, 29], [4, 61], [2, 88], [3, 1674]].map(([l, s]) => partie(l, s)));
  const tally = { calls: 0, asked: 0, answered: 0, counts: 0 };
  for (const [p, states] of parties.entries()) {
    const end = states[states.length - 1];
    for (let d = 0; d <= end.deal; d++) {
      const where = `partie ${p} deal ${d}`;
      const whole = speech(end.events, d, 0);
      // 1. Move by move, as the page speaks it: the same lines, in order.
      const pieces = [];
      for (let i = 1; i < states.length; i++) {
        const [prev, next] = [states[i - 1], states[i]];
        if (!next.events.slice(prev.events.length).some((e) => e.deal === d)) continue;
        pieces.push(...speech(next.events, d, prev.events.length));
      }
      assert.deepEqual(said(pieces), said(whole), `${where}: spoken move by move`);
      const at = (k) => whole.filter((l) => l.at === k);
      let elder = null;
      const first = {};
      const running = { you: 0, them: 0 };
      end.events.forEach((e, k) => {
        if (e.deal !== d) return;
        // 2. Every line belongs to an event of this deal.
        if (e.kind === "deal_begins") elder = e.elder;
        // 3. Elder's first call in each category is voiced, as its shape.
        if (e.kind === "called" && e.who === elder && first[e.category] === undefined) {
          first[e.category] = e.said;
          const lines = at(k);
          assert.equal(lines.length, 1, `${where}: "${e.said}" said as ${JSON.stringify(said(lines))}`);
          assert.ok(lines[0].who === elder && SHAPE.test(lines[0].clip), `${where}: "${e.said}" said as ${lines[0].clip}`);
          tally.calls++;
        }
        // 4. The answer, after the question and the tie-break when asked.
        if (e.kind === "decided" && first[e.category] && first[e.category] !== "nothing") {
          const lines = said(at(k));
          const younger = elder === "you" ? "them" : "you";
          const expect = e.asked
            ? [`${younger}:${ASK[e.category]}`, `${elder}:TIE`, `${younger}:ANSWER`]
            : [`${younger}:ANSWER`];
          const shaped = lines.map((l, j) => {
            const [who, clip] = l.split(":");
            if (e.asked && j === 1 && TIE[e.category].test(clip)) return `${who}:TIE`;
            if (ANSWER.has(clip)) return `${who}:ANSWER`;
            return l;
          });
          assert.deepEqual(shaped, expect, `${where}: ${e.category} decided (asked ${e.asked}) said as ${JSON.stringify(lines)}`);
          tally.answered++;
          if (e.asked) tally.asked++;
        }
        // 5. Each score's count is the running total.
        if (e.kind === "scored" && (e.who === "you" || e.who === "them")) {
          running[e.who] += e.amount;
          const counts = at(k).filter((l) => l.clip.startsWith("n-"));
          if (running[e.who] <= 170) {
            assert.deepEqual(said(counts), [`${e.who}:n-${running[e.who]}`], `${where}: a score of ${e.amount} counted`);
            tally.counts++;
          }
        }
      });
      for (const line of whole) assert.equal(end.events[line.at].deal, d, `${where}: a line from another deal`);
    }
  }
  assert.ok(tally.calls > 80 && tally.asked > 10 && tally.answered > 60 && tally.counts > 400, JSON.stringify(tally));
});
