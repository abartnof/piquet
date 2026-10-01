// When each line is said, for the dialogue boxes (the user: "two dialogue
// boxes to pop up every move" in the declarations): every line in its turn,
// with its words, never before its moment -- and each thing said in a way
// that differs from the last time.

import test from "node:test";
import assert from "node:assert/strict";
import { createDialogue } from "../src/dialogue.js";

const BANK = {
  groups: { "point-5": ["point-5.0"], good: ["good.0", "good.1"], "what-make": ["what-make.0"], "value-48": ["n-48.0"] },
  texts: { "point-5.0": "Five cards.", "good.0": "Good.", "good.1": "Ah, good.", "what-make.0": "What do they make?", "n-48.0": "Forty-eight." },
};

function said(lines, dialogue = createDialogue(BANK)) {
  const out = [];
  dialogue.say(lines, (line, words, ms) => out.push({ who: line.who, phrase: line.phrase, words, ms }));
  return out;
}

test("every line is said in turn, with its words", () => {
  const out = said([
    { who: "you", phrase: "point-5", delay: 0 },
    { who: "them", phrase: "what-make", delay: 0 },
    { who: "you", phrase: "value-48", delay: 0 },
    { who: "them", phrase: "good", delay: 0 },
  ]);
  assert.deepEqual(out.map((l) => l.words), ["Five cards.", "What do they make?", "Forty-eight.", out[3].words]);
  assert.ok(["Good.", "Ah, good."].includes(out[3].words));
  for (let i = 1; i < out.length; i++) assert.ok(out[i].ms > out[i - 1].ms + 200, `line ${i} comes after the one before has been said`);
});

test("no line before its moment", () => {
  const out = said([{ who: "them", phrase: "point-5", delay: 1200 }, { who: "you", phrase: "good", delay: 0 }]);
  assert.ok(out[0].ms >= 1200 - 5);
  assert.ok(out[1].ms > out[0].ms);
});

test("a batch waits for the one before it", () => {
  const dialogue = createDialogue(BANK);
  const first = said([{ who: "you", phrase: "point-5", delay: 0 }], dialogue);
  const second = said([{ who: "them", phrase: "good", delay: 0 }], dialogue);
  assert.ok(second[0].ms > first[0].ms + 200);
});

test("the same thing is not said the same way twice running", () => {
  const dialogue = createDialogue(BANK);
  const words = [];
  for (let i = 0; i < 6; i++) said([{ who: "them", phrase: "good", delay: 0 }], dialogue).forEach((l) => words.push(l.words));
  for (let i = 1; i < words.length; i++) assert.notEqual(words[i], words[i - 1]);
});

test("stop: nothing still waiting holds up what comes next", () => {
  const dialogue = createDialogue(BANK);
  said([{ who: "you", phrase: "point-5", delay: 5000 }], dialogue);
  dialogue.stop();
  const after = said([{ who: "them", phrase: "good", delay: 0 }], dialogue);
  assert.ok(after[0].ms < 100, `said ${after[0].ms} ms from now`);
});

// The score waits for the dialogue (a point is scored after "Good.", not
// before "Five cards."): the dialogue can say, at once, about when a batch of
// lines will have been said.
test("how long a batch of lines will take, told before it is said", () => {
  const dialogue = createDialogue(BANK);
  const lines = [
    { who: "you", phrase: "point-5", delay: 300 },
    { who: "them", phrase: "what-make", delay: 300 },
    { who: "you", phrase: "value-48", delay: 300 },
    { who: "them", phrase: "good", delay: 300 },
  ];
  const until = dialogue.estimate(lines);
  const out = said(lines, dialogue).map((l) => l.ms);
  assert.ok(until >= out[out.length - 1] + 200, `told ${until} ms; the last line begins at ${out[out.length - 1]}`);
  assert.ok(until < out[out.length - 1] + 2000);
});

// The moment between the declarations' rounds (breaks.js): a pause in the
// dialogue, which comes once the line before it has been said, and which
// nothing after it comes before.
test("a pause comes once the line before it has been said, and nothing after it comes sooner", () => {
  const out = said([
    { who: "you", phrase: "point-5", delay: 0 },
    { who: "them", phrase: "good", delay: 0 },
    { pause: true, delay: 0 },
    { who: "them", phrase: "point-5", delay: 0 },
  ]);
  assert.equal(out[2].words, null);
  assert.ok(out[2].ms >= out[1].ms + 250 + 65 * out[1].words.length, `the pause at ${out[2].ms}, "${out[1].words}" at ${out[1].ms}`);
  assert.ok(out[3].ms >= out[2].ms);
  assert.ok(out[3].ms < out[2].ms + 50, "and the next line straight after it");
});

test("a pause waits for its moment, as a line does", () => {
  const out = said([{ who: "you", phrase: "good", delay: 0 }, { pause: true, delay: 3000 }]);
  assert.ok(out[1].ms >= 3000 - 5);
});

// The table is paced before it is played: the words are chosen once, so the
// moments planned are the moments said.
test("what is planned is what is said", () => {
  const dialogue = createDialogue(BANK);
  const lines = dialogue.words([
    { who: "you", phrase: "point-5", delay: 0 },
    { who: "them", phrase: "good", delay: 400 },
    { pause: true, delay: 0 },
    { who: "them", phrase: "good", delay: 0 },
  ]);
  const plan = dialogue.plan(lines);
  const out = said(lines, dialogue);
  assert.deepEqual(out.map((l) => l.words), lines.map((l) => (l.pause ? null : l.words)));
  out.forEach((l, i) => assert.ok(Math.abs(l.ms - plan[i].ms) < 5, `line ${i}: planned ${plan[i].ms}, said ${l.ms}`));
  assert.ok(plan[1].end > plan[1].ms + 250, "and when each will have been said");
});

// On the table's clock, which stops while the table is held still (a page of
// the tutorial, the moment between rounds): the dialogue counts from it.
test("on the clock it is given", () => {
  let t = 0;
  const dialogue = createDialogue(BANK, () => t);
  said([{ who: "you", phrase: "point-5", delay: 0 }], dialogue);
  t = 10_000; // long since said
  const after = said([{ who: "them", phrase: "good", delay: 0 }], dialogue);
  assert.equal(after[0].ms, 0);
});
