// The dialogue at the table: the phrases speech.js asks for, each given its
// words and its moment, for the declarations' dialogue boxes. The words are
// the phrase bank's (web3d/tools/phrases.py, docs/PHRASES.md), bundled into
// the page by web3d/build.py.
//
// Everything is said in several ways, and each is picked without repeating
// the last (bag.js). Each line waits for its moment -- the animation's beat
// for the event it belongs to -- and for the line before it to have been
// said, so a box never appears before its turn.
//
// createDialogue(bank) -> { say(lines, onLine), estimate(lines), stop() }
//   bank:   { groups: { id: [key] }, texts: { key: words } }
//   lines:  [{ who: "you"|"them", phrase, delay }] from speech(): phrase is a
//           group id; delay the ms from now until its moment (0 if absent)
//   onLine: (line, words, ms) for each line, ms from now until it is said

import { createBags } from "./bag.js";

const GAP = 90; // ms between one speaker's lines
const TURN = 280; // ms when the other speaks
// How long a line takes to say: about as long as a person takes.
const saying = (words) => 250 + 65 * (words || "").length;

export function createDialogue(bank) {
  const pick = createBags();
  let next = 0; // when the last line said will have ended, on the page's clock
  let last = null; // who said it

  return {
    // Each line at its moment, and after the line before it has been said.
    say(lines, onLine) {
      const now = performance.now();
      for (const line of lines) {
        const words = bank.texts?.[pick(line.phrase, bank.groups?.[line.phrase])] ?? "";
        const gap = last === null ? 0 : line.who === last ? GAP : TURN;
        const start = Math.max(now + (line.delay ?? 0), next + gap, now);
        next = start + saying(words);
        last = line.who;
        onLine?.(line, words, start - now);
      }
    },
    // About when these lines, said next, will all have been said -- in ms
    // from now, from the words each is most often said in. For the score,
    // which waits for the dialogue.
    estimate(lines) {
      let t = Math.max(0, next - performance.now());
      let who = last;
      for (const line of lines) {
        const gap = who === null ? 0 : line.who === who ? GAP : TURN;
        t = Math.max(line.delay ?? 0, t + gap);
        t += saying(bank.texts?.[bank.groups?.[line.phrase]?.[0]]);
        who = line.who;
      }
      return t;
    },
    // Undo, or a new partie: nothing still to come holds up what follows.
    stop() {
      next = 0;
      last = null;
    },
  };
}
