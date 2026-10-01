// Where the declarations' rounds begin -- point, then sequences, then sets --
// for a moment on the screen between them (the user: "an on-screen thing pop
// up for a moment before each part of the declarations, after each player is
// done speaking from the last one. they may start again once the on-screen
// thing is gone").
//
// breaksBetween(prev, next) -> [{ at, category }], in order: `at` is the
// index in next.events of a round's first word in this move, or
// next.events.length when the round is yours to open and nothing of it has
// been said yet. A pure function of the protocol's states.

const ROUNDS = ["point", "sequences", "sets"];
const WORDS = new Set(["called", "nothing_to_call", "decided", "showed"]);

export function breaksBetween(prev, next) {
  const since = prev.events.length;
  if (next.events.length < since) return []; // an undo
  // A round put to you was introduced when it was put.
  const begun = new Set(prev.prompt?.kind === "declare" && prev.deal === next.deal ? [prev.prompt.category] : []);
  const out = [];
  next.events.forEach((e, at) => {
    if (e.deal !== next.deal || !WORDS.has(e.kind) || !ROUNDS.includes(e.category) || begun.has(e.category)) return;
    begun.add(e.category);
    if (at >= since) out.push({ at, category: e.category });
  });
  const p = next.prompt;
  if (p.kind === "declare" && ROUNDS.includes(p.category) && !begun.has(p.category)) {
    out.push({ at: next.events.length, category: p.category });
  }
  return out;
}
