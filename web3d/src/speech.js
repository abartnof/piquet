// What the table says aloud: the protocol's events as a queue of recorded
// phrases, each with its speaker (Andrew: "maximal speaking (anything a human
// would say, we'll say)"). The phrases and their ids are web3d/tools/voice.py's;
// how they are said follows Cavendish, *The Laws of Piquet* (1885) --
// docs/VOICE.md. A pure function, so the page only plays what it returns.
//
// speech(events, deal, since) -> [{ who, clip, at }], for the events of `deal`
// from index `since`: who is "you" or "them", clip a group of the bank --
// something said in several ways, which the voice picks among (voice.js) --
// and `at` the index of the event it belongs to, so it can be said when that
// event is seen to happen.
//
// The declarations follow Cavendish (pp. 60-67). Elder calls the shape -- "Five
// cards.", "A quart.", "A trio." Only when younger holds the same shape does she
// ask for the tie-break -- "What do they make?", "How high?", "Of what?" -- and
// elder gives it: the point's value, the sequence's top, the set's rank. Then
// she answers: "Good.", "Not good.", "Equal." Whether she asked is the
// decision's `asked`. Your opponent's calls reach the page as the shape, and
// the tie-break only after the decision; yours come whole. Younger says nothing
// else in the dialogue: what she holds she names as she reckons it, once elder
// has led.

const RANK = { ace: "ace", king: "king", queen: "queen", jack: "knave", ten: "ten", nine: "nine", eight: "eight", seven: "seven" };
const LENGTH = { tierce: 3, quart: 4, quint: 5, sixième: 6, septième: 7, huitième: 8 };
const QUESTION = { point: "what-make", sequences: "how-high", sets: "what-set" };
const other = (who) => (who === "you" ? "them" : "you");
// How far ahead a deal must leave you for your opponent to say so.
const WELL_PLAYED = 30;

const RUN = /^(tierce|quart|quint|sixième|septième|huitième)(?: to the (\w+))?$/;
const SET = /^(trio|quatorze)(?: of (\w+?)s)?$/;

// A holding named in full -- "quint to the ace", "trio of queens" -- as the
// group Cavendish's words are recorded under; null for a bare shape.
function holdingClip(text) {
  const run = text.match(RUN);
  if (run && run[2]) return `seq-${LENGTH[run[1]]}-${RANK[run[2]]}`;
  const set = text.match(SET);
  if (set && set[2]) return `set-${set[1] === "trio" ? 3 : 4}-${RANK[set[2]]}`;
  return null;
}

// Its shape, whether named in full or not: "A quart.", "A trio.", "Five cards."
function shapeClip(text) {
  const point = text.match(/^point of (\d+)/);
  if (point) return `point-${point[1]}`;
  const run = text.match(RUN);
  if (run) return `seq-${LENGTH[run[1]]}`;
  const set = text.match(SET);
  if (set) return `set-${set[1] === "trio" ? 3 : 4}`;
  return null;
}

// The tie-break a call gives: the point's value -- "point of 5 (48)" as you
// call it, "point of 4, making 41" as your opponent does -- or the best
// holding named in full.
function tiebreakClip(category, text) {
  if (category === "point") {
    const value = text.match(/\((\d+)\)|making (\d+)/);
    return value ? `value-${value[1] ?? value[2]}` : null;
  }
  return holdingClip(text.split(", ")[0]);
}

const holdings = (text) => String(text).split(", ");

export function speech(events, deal, since = 0) {
  const out = [];
  let at = 0;
  const say = (who, clip) => clip && out.push({ who, clip, at });
  let elder = null;
  const count = { you: 0, them: 0 }; // each side's running total, said aloud
  const called = {}; // category -> elder's first words
  const named = new Set(); // the holdings said aloud in full this deal

  events.forEach((e, i) => {
    if (e.deal !== deal) return;
    at = i;
    const now = i >= since; // earlier events set the scene but are not said again
    const who = e.who === "you" || e.who === "them" ? e.who : null;
    switch (e.kind) {
      case "deal_begins":
        elder = e.elder;
        break;
      case "first_dealer":
        if (now) say(e.chooser, e.dealer === e.chooser ? "my-deal" : "your-deal");
        break;
      case "cut_again":
        if (now) say("them", "cut-again");
        break;
      case "choice_of_deal":
        if (now && e.who === "you") say("them", "your-choice");
        break;
      case "exchanged":
        // Only elder announces, and only when leaving some (p. 57).
        if (now && who === elder && e.count < 5) say(who, `take-${e.count}`);
        break;
      case "nothing_to_call":
        // Only ever yours: as elder you say so, as younger you just answer.
        if (called[e.category] === undefined && elder === "you") {
          called[e.category] = "nothing";
          if (now) say("you", "nothing");
        }
        break;
      case "called": {
        // Elder's first words in a category; a later call of his is the
        // tie-break, said with the decision it belongs to (below).
        if (who !== elder || called[e.category] !== undefined) break;
        called[e.category] = e.said;
        if (!now) break;
        say(who, e.said === "nothing" ? "nothing" : shapeClip(holdings(e.said)[0]));
        break;
      }
      case "decided": {
        const call = called[e.category];
        if (!elder || call === undefined || call === "nothing") break;
        const younger = other(elder);
        // The tie-break: from your own call, or from your opponent's next.
        let source = call;
        if (elder === "them") {
          const next = events.slice(i + 1).find((x) => x.deal === deal && x.kind === "called" && x.who === "them" && x.category === e.category);
          source = next ? next.said : null;
        }
        const tiebreak = e.asked && source ? tiebreakClip(e.category, source) : null;
        if (tiebreak && e.category !== "point") named.add(tiebreak);
        if (!now) break;
        if (tiebreak) {
          say(younger, QUESTION[e.category]);
          say(elder, tiebreak);
        }
        say(younger, e.winner === elder ? "good" : e.winner === younger ? "not-good" : "equal");
        break;
      }
      case "scored": {
        if (!who) break;
        count[who] += e.amount;
        if (!now) break;
        // Each holding named as it is reckoned, unless it was said in full
        // already: all of younger's ("Four tens fourteen, and three queens
        // seventeen", p. 77), and whatever elder won on the shape alone.
        if (["point", "sequences", "sets"].includes(e.category)) {
          const point = String(e.what).match(/^point of (\d+)/);
          if (point) {
            if (who !== elder) say(who, `point-${point[1]}`);
          } else {
            for (const clip of holdings(e.what).map(holdingClip)) {
              if (clip && !named.has(clip)) say(who, clip);
              named.add(clip);
            }
          }
        }
        if (e.category === "bonus") say(who, String(e.what).includes("repique") ? "repique" : "pique");
        if (e.category === "cards") say(who, e.amount >= 40 ? "capot" : "the-cards");
        if (e.category === "carte_blanche") say(who, "carte-blanche-have");
        // Counting aloud: the running total, as each score is made.
        if (count[who] > 0 && count[who] <= 170) say(who, `n-${count[who]}`);
        break;
      }
      case "deal_ends":
        // A deal won handsomely is remarked on -- and only such a deal, or
        // the remark would be as tiresome as silence.
        if (now && e.you - e.them >= WELL_PLAYED) say("them", "well-played");
        break;
      case "partie_ends":
        if (now) say("them", e.you > e.them ? "congratulations" : "good-game");
        break;
      default:
        break;
    }
  });
  return out;
}
