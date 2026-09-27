// The live score: two numbers, one a side, as a broadcast shows a game's
// (Andrew: "the immediacy of a WNBA on-screen live score display. 2
// numbers, one for each team- and when you score, there's a minor animation
// to update the score- unless you score big, in which case there's a little
// celebratory animation").

import test from "node:test";
import assert from "node:assert/strict";
import { answersSince, caption, live, scoredSince } from "../src/scorebug.js";
import { partie } from "./partie.js";

const parties = await Promise.all([[3, 7], [1, 11], [2, 23]].map(([l, s]) => partie(l, s)));
const ev = (kind, fields) => ({ deal: 1, text: "", ...fields, kind });

test("the live numbers are the partie as it stands this instant", () => {
  for (const states of parties) {
    for (const s of states) {
      const now = live(s);
      assert.equal(now.you, s.standing.you + s.score.you);
      assert.equal(now.them, s.standing.them + s.score.them);
    }
    const end = states[states.length - 1];
    assert.deepEqual([live(end).you, live(end).them], [end.partie.you, end.partie.them], "and the partie's totals at its end");
  }
});

test("within a partie the numbers only ever go up", () => {
  for (const states of parties) {
    for (let i = 1; i < states.length; i++) {
      const [a, b] = [live(states[i - 1]), live(states[i])];
      assert.ok(b.you >= a.you && b.them >= a.them, `went down at state ${i}`);
    }
  }
});

test("the period is the deal, of six -- or an extra one on a tie", () => {
  const s = parties[0].find((x) => x.deal === 3);
  assert.deepEqual([live(s).deal, live(s).of], [3, 6]);
  assert.deepEqual([live({ ...s, deal: 7 }).deal, live({ ...s, deal: 7 }).of], [7, 7]);
});

test("what was scored since a moment: by side, and the big ones named", () => {
  const events = [
    ev("deal_begins", { elder: "you", you_total: 20, them_total: 10 }),
    ev("scored", { who: "you", amount: 5, what: "point of 5", category: "point" }),
    ev("scored", { who: "you", amount: 60, what: "repique", category: "bonus" }),
    ev("scored", { who: "them", amount: 3, what: "tierce", category: "sequences" }),
  ];
  assert.deepEqual(scoredSince(events, 1, 0), {
    you: { points: 65, big: [{ flair: "Repique", points: 60 }] },
    them: { points: 3, big: [] },
  });
  // Only what is new counts: from the third event on.
  assert.deepEqual(scoredSince(events, 1, 3), {
    you: { points: 0, big: [] },
    them: { points: 3, big: [] },
  });
});

test("the caption is the latest thing said, and who said it", () => {
  const events = [
    ev("deal_begins", { elder: "you", text: "Deal 1 of six. You are elder, and lead." }),
    ev("called", { who: "you", said: "point of 5 (49)", category: "point" }),
    ev("decided", { category: "point", winner: "them" }),
  ];
  assert.deepEqual(caption(events, 1), { who: "them", text: "“Not good.”" });
  assert.deepEqual(caption(events.slice(0, 2), 1), { who: "you", text: "“Point of 5 (49).”" });
  assert.deepEqual(caption(events.slice(0, 1), 1), { who: null, text: "Deal 1 of six. You are elder, and lead." });
});

test("a card played is shown on the table, not captioned", () => {
  const events = [
    ev("called", { who: "them", said: "quart", category: "sequences" }),
    ev("played", { who: "you", card: "AS" }),
    ev("played", { who: "them", card: "7S" }),
    ev("took_trick", { who: "you", number: 1 }),
  ];
  assert.deepEqual(caption(events, 1), { who: "them", text: "“Quart.”" });
});

// Andrew: "during the declarations, there's only an implicit notification
// that you didn't succeed ... a bubble that pops up on-screen with that?
// green or blue if good, red if no good".
test("the answers given since a moment: who said it, and what it means for you", () => {
  const events = [
    ev("deal_begins", { elder: "you" }),
    ev("called", { who: "you", said: "point of 5 (49)", category: "point" }),
    ev("decided", { category: "point", winner: "you" }),
    ev("called", { who: "you", said: "tierce", category: "sequences" }),
    ev("decided", { category: "sequences", winner: "them" }),
    ev("called", { who: "you", said: "trio", category: "sets" }),
    ev("decided", { category: "sets", winner: null }),
  ];
  assert.deepEqual(answersSince(events, 1, 0), [
    { who: "them", text: "Good.", outcome: "won", category: "point" },
    { who: "them", text: "Not good.", outcome: "lost", category: "sequences" },
    { who: "them", text: "Equal.", outcome: "equal", category: "sets" },
  ]);
  assert.deepEqual(answersSince(events, 1, 5).map((a) => a.text), ["Equal."], "only what is new");

  // Younger, you answer their calls: "good" concedes, and is bad news.
  const younger = [
    ev("deal_begins", { elder: "them" }),
    ev("called", { who: "them", said: "quart", category: "sequences" }),
    ev("decided", { category: "sequences", winner: "them" }),
  ];
  assert.deepEqual(answersSince(younger, 1, 0), [{ who: "you", text: "Good.", outcome: "lost", category: "sequences" }]);
});

test("a call of nothing is answered by nobody, so no bubble", () => {
  const events = [
    ev("deal_begins", { elder: "you" }),
    ev("called", { who: "you", said: "nothing", category: "sets" }),
    ev("decided", { category: "sets", winner: "them" }),
  ];
  assert.deepEqual(answersSince(events, 1, 0), []);
});
