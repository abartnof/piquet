// The live score, as a broadcast shows a game's: two numbers, one a side,
// the partie as it stands this instant (Andrew: "the immediacy of a WNBA
// on-screen live score display. 2 numbers, one for each team- and when you
// score, there's a minor animation to update the score- unless you score
// big, in which case there's a little celebratory animation"). The stage
// table above it stays as the game's log.
//
// Pure functions of the protocol's state and events, so the page only
// draws and animates what these say.

import { talk } from "./talk.js";

// The partie as it stands: its total when this deal began, and this deal so
// far. (`partie` counts only finished deals, so mid-deal it lags.)
export function live(s) {
  const standing = s.standing ?? { you: 0, them: 0 };
  const score = s.score ?? { you: 0, them: 0 };
  const deal = Math.max(1, s.deal || 1);
  return { you: standing.you + score.you, them: standing.them + score.them, deal, of: Math.max(6, deal) };
}

// What each side has scored since the event at index `since`, and which of
// it was big enough to celebrate (talk.flairOf, or crossing the rubicon).
export function scoredSince(events, deal, since) {
  const out = { you: { points: 0, big: [] }, them: { points: 0, big: [] } };
  events.forEach((e, at) => {
    if (at >= since && e.deal === deal && e.kind === "scored" && out[e.who]) out[e.who].points += e.amount;
  });
  const lines = talk(events, deal);
  for (const who of ["you", "them"]) {
    for (const line of lines[who]) {
      if (line.at >= since && line.flair) out[who].big.push({ flair: line.flair, points: line.points });
    }
  }
  return out;
}

// What is said, not what is done: cards played and tricks taken are there on
// the table to see, and the points are the numbers' own business.
const UNSAID = new Set(["card", "trick", "scored", "drew"]);

// The latest thing said at the table this deal, and by whom (null: the table).
export function caption(events, deal) {
  const t = talk(events, deal);
  const latest = [...t.you, ...t.them, ...t.table]
    .filter((line) => !UNSAID.has(line.kind))
    .reduce((best, line) => (!best || line.at > best.at ? line : best), null);
  return latest ? { who: latest.who, text: latest.text } : null;
}

// The answers given since the event at index `since` -- "good", "not good",
// "equal" -- with who said them and what each means for you, so the page
// can pop each up as a bubble from the speaker (Andrew: "green or blue if
// good, red if no good"). A call of nothing is answered by nobody.
export function answersSince(events, deal, since) {
  const lines = talk(events, deal);
  return [...lines.you, ...lines.them]
    .filter((line) => line.kind === "answer" && line.at >= since)
    .sort((a, b) => a.at - b.at)
    .map((line) => ({
      who: line.who,
      text: line.text.replace(/[“”]/g, ""),
      outcome: line.winner === "you" ? "won" : line.winner === "them" ? "lost" : "equal",
      category: line.category,
    }));
}
