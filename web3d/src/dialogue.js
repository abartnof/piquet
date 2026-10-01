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
// createDialogue(bank, clock) -> { say(lines, onLine), words(lines), plan(lines), estimate(lines), stop() }
//   bank:   { groups: { id: [key] }, texts: { key: words } }
//   clock:  ms now -- the table's clock, which stops while the table is held
//           still, so time held is not counted as time passed
//   lines:  [{ who: "you"|"them", phrase, delay }] from speech(): phrase is a
//           group id; delay the ms from now until its moment (0 if absent).
//           Or { pause: true, delay }: the moment between the declarations'
//           rounds (breaks.js), which comes once the line before it has been
//           said, and before which nothing after it comes.
//   onLine: (line, words, ms) for each line, ms from now until it is said
//           (words null for a pause)

import { createBags } from "./bag.js";

const GAP = 90; // ms between one speaker's lines
const TURN = 280; // ms when the other speaks
// How long a line takes to say: about as long as a person takes.
const saying = (words) => 250 + 65 * (words || "").length;

export function createDialogue(bank, clock = () => performance.now()) {
  const pick = createBags();
  let next = 0; // when the last line said will have ended, on the clock
  let last = null; // who said it
  const chosen = (line) => (line.pause ? null : line.words ?? bank.texts?.[pick(line.phrase, bank.groups?.[line.phrase])] ?? "");
  // The words a line is most often said in, for a line not yet given its own.
  const usual = (line) => (line.pause ? null : line.words ?? bank.texts?.[bank.groups?.[line.phrase]?.[0]] ?? "");

  // Each line's moment and its end, in ms from now: after the line before it
  // has been said, and not before its own moment. Says nothing.
  function schedule(lines, words) {
    const now = clock();
    let t = next;
    let who = last;
    const out = lines.map((line) => {
      const said = words(line);
      const gap = who === null ? 0 : line.pause || line.who !== who ? TURN : GAP;
      const start = Math.max(now + (line.delay ?? 0), t + gap, now);
      t = line.pause ? start : start + saying(said);
      who = line.pause ? null : line.who;
      return { ...line, words: said, ms: start - now, end: t - now };
    });
    return { out, t, who };
  }

  return {
    // Each line at its moment, and after the line before it has been said.
    say(lines, onLine) {
      const { out, t, who } = schedule(lines, chosen);
      next = t;
      last = who;
      for (const line of out) onLine?.(line, line.words, line.ms);
    },
    // The lines, each with the words it will be said in, chosen now: so that
    // what is planned (below) is what is then said.
    words(lines) {
      return lines.map((line) => (line.pause ? line : { ...line, words: chosen(line) }));
    },
    // When each line would be said and done, in ms from now, if said next.
    plan(lines) {
      return schedule(lines, usual).out;
    },
    // About when these lines, said next, will all have been said -- in ms
    // from now. For the score, which waits for the dialogue.
    estimate(lines) {
      const out = schedule(lines, usual).out;
      return Math.max(0, next - clock(), ...out.map((l) => l.end));
    },
    // Undo, or a new partie: nothing still to come holds up what follows.
    stop() {
      next = 0;
      last = null;
    },
  };
}
