// The tutorial (Andrew: "an introduction (concise, bullet points- nothing too
// wordy), and an introduction before each phase of play"): what each card
// says, and when it comes.

import test from "node:test";
import assert from "node:assert/strict";
import { INTRO, PHASES, phaseOf, introDue } from "../src/tutorial.js";
import { partie } from "./partie.js";

const states = (await Promise.all([[3, 7], [2, 23]].map(([l, s]) => partie(l, s)))).flat();

test("every moment of a partie that asks you something has its introduction", () => {
  for (const s of states) {
    const key = phaseOf(s);
    if (s.prompt.kind === "over" || key) {
      assert.ok(key, `no introduction for ${s.prompt.kind}`);
      assert.ok(PHASES[key], `no words for ${key}`);
    }
  }
  const seen = new Set(states.map(phaseOf).filter(Boolean));
  for (const key of ["cut", "exchange", "point", "sequences", "sets", "play", "deal-over", "partie-over"]) assert.ok(seen.has(key), key);
});

test("concise: a title and a few short bullets, nothing too wordy", () => {
  for (const card of [INTRO, ...Object.values(PHASES)]) {
    assert.ok(card.title && card.title.length <= 40, card.title);
    assert.ok(card.bullets.length >= 2 && card.bullets.length <= 5, card.title);
    for (const b of card.bullets) assert.ok(b.length <= 130, `${card.title}: "${b}" is ${b.length} characters`);
  }
});

test("each phase is introduced once, the first time it comes", () => {
  const seen = [];
  const shown = [];
  for (const s of states.slice(0, 200)) {
    const due = introDue(s, seen);
    if (due) {
      shown.push(due);
      seen.push(due);
    }
  }
  assert.equal(new Set(shown).size, shown.length, "never twice");
  assert.equal(shown[0], "cut");
  assert.ok(shown.indexOf("exchange") < shown.indexOf("play"));
});

test("the rules as the engine plays them", () => {
  const all = [INTRO, ...Object.values(PHASES)].flatMap((c) => c.bullets).join(" ");
  assert.match(all, /every card you lead/); // not only tens and higher
  assert.match(all, /last trick scores two/);
  assert.match(all, /quint 15/);
  assert.match(all, /quatorze 14/);
  assert.match(all, /rubicon/i);
  assert.doesNotMatch(all, /Cori|Norman|Cavendish|Hoyle|Foster/); // "your opponent", never a name
});
