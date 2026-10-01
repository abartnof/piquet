// The order of the human's hand, as groups set apart from one another.
//
// The same logic as the first, 2D page (since retired), which the user
// asked for: while the hand is still being shaped -- the exchange
// and the declarations -- the automatic order puts the best holdings first,
// each set apart, and the rest after; once the play begins it goes back to
// suits, with the colours alternating.

const RANKS = "AKQJT987";
const SUIT_ORDER = ["S", "H", "C", "D"]; // so the colours alternate

const rankOf = (c) => RANKS.indexOf(c[0]);
const suitOf = (c) => SUIT_ORDER.indexOf(c[1]);
export const bySuit = (a, b) => suitOf(a) - suitOf(b) || rankOf(a) - rankOf(b);
const byRank = (a, b) => rankOf(a) - rankOf(b) || suitOf(a) - suitOf(b);

// "auto", "suit", "rank" or "combos" -> the mode in force now.
export function sortMode(state, preference) {
  if (preference !== "auto") return preference;
  return ["exchange", "declare"].includes(state.prompt.kind) ? "combos" : "suit";
}

// The hand as groups of cards, in the order they are laid out.
export function arrange(state, mode) {
  if (mode === "combos") {
    const held = new Set(state.hand);
    const placed = new Set();
    const groups = [];
    for (const holding of state.worth) {
      if (holding.category === "carte_blanche") continue; // it is the whole hand
      const cards = holding.cards.filter((c) => held.has(c) && !placed.has(c)).sort(bySuit);
      if (!cards.length) continue;
      cards.forEach((c) => placed.add(c));
      groups.push(cards);
    }
    const rest = state.hand.filter((c) => !placed.has(c)).sort(bySuit);
    if (rest.length) groups.push(rest);
    return groups;
  }
  const cards = [...state.hand].sort(mode === "rank" ? byRank : bySuit);
  const key = mode === "rank" ? (c) => c[0] : (c) => c[1];
  const groups = [];
  for (const c of cards) {
    if (!groups.length || key(groups[groups.length - 1][0]) !== key(c)) groups.push([]);
    groups[groups.length - 1].push(c);
  }
  return groups;
}
