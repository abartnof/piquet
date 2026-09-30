// As elder, having taken fewer than five of your talon cards: the rest are
// yours to look at (pagat: "If elder exchanges fewer than five cards he can
// look at the remainder of the five"), and you watch your opponent draw them
// first. The engine says so in its "looked" and "they_took" events; this says
// it again where it first matters -- the point's explanation -- in the cards'
// own names. A pure function of the state, so it is tested without a page.

const SUITS = { S: "\u2660", H: "\u2665", D: "\u2666", C: "\u2663" };
const name = (code) => (code[0] === "T" ? "10" : code[0]) + SUITS[code[1]];

export function leftNote(s) {
  const find = (kind) => s.events.find((e) => e.kind === kind && e.deal === s.deal);
  const looked = find("looked");
  if (!looked) return "";
  const took = find("they_took")?.cards ?? [];
  const cards = (list) => list.map(name).join(" ");
  const still = looked.cards.filter((c) => !took.includes(c));
  if (!took.length) return ` You left ${cards(looked.cards)} in the talon; they are still there.`;
  if (!still.length) return ` You left ${cards(looked.cards)}; your opponent drew ${looked.cards.length === 1 ? "it" : "them"}.`;
  return ` You left ${cards(looked.cards)}; your opponent drew ${cards(took)}, and ${cards(still)} ${still.length === 1 ? "is" : "are"} still in the talon.`;
}
