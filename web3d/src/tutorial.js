// The tutorial: a short introduction, and a card before each phase the first
// time it comes (Andrew: "an introduction (concise, bullet points- nothing too
// wordy), and an introduction before each phase of play. when this 'tutorial'
// mode is on, hints+explanations are on by default"). The rules as the engine
// plays them -- docs/PIQUET.md, after pagat.

export const INTRO = {
  title: "Piquet in a minute",
  bullets: [
    "Two players and 32 cards: seven to ace in each suit. Aces are high.",
    "A partie is six deals. The deal alternates; the other player, elder, has the advantage.",
    "Each deal: exchange cards, declare what you hold, then play twelve tricks. All three score.",
    "The higher score after six deals wins. Reach 100 (the rubicon) or you pay far more.",
    "Hints suggest the strongest move, and explanations say what each moment means. Both are on.",
  ],
};

export const PHASES = {
  cut: {
    title: "The cut",
    bullets: [
      "Lift part of the pack to show a card; your opponent does the same.",
      "The higher card chooses who deals first. Equal cards cut again.",
      "Or just press Cut for me.",
    ],
  },
  "choose-dealer": {
    title: "Choosing the deal",
    bullets: [
      "You cut higher, so you choose who deals first.",
      "Dealing first makes you elder in the sixth and last deal, when it matters most.",
    ],
  },
  exchange: {
    title: "The exchange",
    bullets: [
      "You each hold 12 cards. The other 8 lie face down: the talon.",
      "Elder throws away 1 to 5 cards and draws as many. Younger then throws up to what elder left.",
      "Keep what scores: a long suit, cards in a row, and three or four tens or higher.",
      "A hand with no king, queen or jack is carte blanche: 10 points.",
    ],
  },
  point: {
    title: "Declaring: the point",
    bullets: [
      "Your point is your longest suit. Elder says how many cards; younger answers good, not good or equal.",
      "Equal length? Add the pips (ace 11, court cards 10, the rest their number); the higher wins.",
      "The better point scores one a card. You may call less than you hold, to keep it hidden.",
    ],
  },
  sequences: {
    title: "Declaring: sequences",
    bullets: [
      "Three or more in a row in one suit: a tierce, quart, quint, up to a huitième of eight.",
      "The longest wins; if equal, the higher top card.",
      "The winner scores all of theirs: tierce 3, quart 4, quint 15, sixième 16, and so on.",
    ],
  },
  sets: {
    title: "Declaring: sets",
    bullets: [
      "Three or four of a kind, tens or higher: a trio scores 3, a quatorze 14.",
      "Any quatorze beats any trio; otherwise the higher rank wins. The winner scores all of theirs.",
      "Reach 30 by declaring alone before your opponent scores: repique, 60 more.",
    ],
  },
  play: {
    title: "The play",
    bullets: [
      "Twelve tricks, no trumps. Follow suit if you can; the higher card of the suit led wins.",
      "Score one for every card you lead and every trick you win second; the last trick scores two.",
      "Win more than six tricks: 10 for the cards. All twelve: capot, 40.",
      "Elder reaching 30 before younger scores anything: pique, 30 more.",
    ],
  },
  "deal-over": {
    title: "The end of a deal",
    bullets: [
      "The deal's points join the running score, and the deal passes to the other player.",
      "Six deals in all. Keep an eye on 100: the rubicon.",
    ],
  },
  "partie-over": {
    title: "The end of the partie",
    bullets: [
      "The higher score wins the difference, plus 100.",
      "If the loser never reached 100 they are rubiconed: the winner takes both scores, plus 100.",
    ],
  },
};

// Which phase a state is in, for the tutorial: the question put to you.
export function phaseOf(s) {
  const p = s.prompt;
  switch (p.kind) {
    case "cut":
      return "cut";
    case "choose_dealer":
      return "choose-dealer";
    case "exchange":
      return "exchange";
    case "declare":
      return p.category === "point" ? "point" : p.category === "sequences" ? "sequences" : "sets";
    case "play":
      return "play";
    case "next_deal":
      return "deal-over";
    case "over":
      return "partie-over";
    default:
      return null;
  }
}

// The phase to introduce now, if it has not been introduced yet.
export function introDue(s, seen) {
  const key = phaseOf(s);
  return key && !seen.includes(key) ? key : null;
}
