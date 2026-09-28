// When each line is said, for the dialogue boxes (Andrew: "two dialogue
// boxes to pop up every move" in the declarations). The voice reports every
// line's moment and words -- the lines it plays and the ones it keeps silent
// alike, so a box appears in turn even with the sound off.

import test from "node:test";
import assert from "node:assert/strict";
import { createVoice } from "../src/voice.js";

const VOICES = {
  cori: {
    gender: "female",
    groups: { "point-5": ["point-5.0"], good: ["good.0", "good.1"], "what-make": ["what-make.0"], "value-48": ["n-48.0"] },
    texts: { "point-5.0": "Five cards.", "good.0": "Good.", "good.1": "Ah, good.", "what-make.0": "What do they make?", "n-48.0": "Forty-eight." },
  },
};
VOICES.norman = { ...VOICES.cori, gender: "male" };

async function heard(lines, prefs) {
  const voice = createVoice(VOICES);
  const out = [];
  await voice.say(lines, prefs, (line, words, ms) => out.push({ who: line.who, clip: line.clip, words, ms }));
  return out;
}

test("with the sound off, every line is still said in turn, with its words", async () => {
  const out = await heard([
    { who: "you", clip: "point-5", delay: 0 },
    { who: "them", clip: "what-make", delay: 0 },
    { who: "you", clip: "value-48", delay: 0 },
    { who: "them", clip: "good", delay: 0 },
  ], { voice: false });
  assert.deepEqual(out.map((l) => l.words), ["Five cards.", "What do they make?", "Forty-eight.", out[3].words]);
  assert.ok(["Good.", "Ah, good."].includes(out[3].words));
  for (let i = 1; i < out.length; i++) assert.ok(out[i].ms > out[i - 1].ms + 200, `line ${i} comes after the one before has been said`);
});

test("no line before its moment", async () => {
  const out = await heard([{ who: "them", clip: "point-5", delay: 1200 }, { who: "you", clip: "good", delay: 0 }], { voice: false });
  assert.ok(out[0].ms >= 1200 - 5);
  assert.ok(out[1].ms > out[0].ms);
});

test("your own lines keep their turn when your voice is off", async () => {
  const out = await heard([{ who: "you", clip: "point-5", delay: 0 }, { who: "them", clip: "good", delay: 0 }], { voice: true, sayMine: false });
  assert.equal(out.length, 2);
  assert.ok(out[1].ms > out[0].ms + 200, "the answer waits for the call");
});

// The score waits for the dialogue (a point is scored after "Good.", not
// before "Five cards."): the voice can say, at once, about when a batch of
// lines will have been said.
test("how long a batch of lines will take, told before it is said", async () => {
  const voice = createVoice(VOICES);
  const lines = [
    { who: "you", clip: "point-5", delay: 300 },
    { who: "them", clip: "what-make", delay: 300 },
    { who: "you", clip: "value-48", delay: 300 },
    { who: "them", clip: "good", delay: 300 },
  ];
  const until = voice.estimate(lines);
  const out = [];
  await voice.say(lines, { voice: false }, (line, words, ms) => out.push(ms));
  assert.ok(until >= out[out.length - 1] + 200, `told ${until} ms; the last line begins at ${out[out.length - 1]}`);
  assert.ok(until < out[out.length - 1] + 2000);
});
