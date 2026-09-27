// What the table says aloud: the protocol's events as a queue of recorded
// phrases, each with its speaker (Andrew: "maximal speaking (anything a human
// would say, we'll say)"). The phrases and their ids are web3d/tools/voice.py's;
// how they are said follows Cavendish, *The Laws of Piquet* (1885) --
// docs/VOICE.md. A pure function, so the page only plays what it returns.
//
// speech(events, deal, since) -> [{ who, clip }], for the events of `deal`
// from index `since`: who is "you" or "them", clip a phrase id.

const RANK = { ace: "ace", king: "king", queen: "queen", jack: "knave", ten: "ten", nine: "nine" };
const LENGTH = { tierce: 3, quart: 4, quint: 5, sixième: 6, septième: 7, huitième: 8 };
const other = (who) => (who === "you" ? "them" : "you");

// A holding named in full -- "quint to the ace", "trio of queens" -- as the
// clip Cavendish's words are recorded under; null for a bare name ("trio").
function holdingClip(text) {
  const run = text.match(/^(tierce|quart|quint|sixième|septième|huitième) to the (\w+)$/);
  if (run) return `seq-${LENGTH[run[1]]}-${RANK[run[2]]}`;
  const set = text.match(/^(trio|quatorze) of (\w+?)s$/);
  if (set) return `set-${set[1] === "trio" ? 3 : 4}-${RANK[set[2]]}`;
  return null;
}

export function speech(events, deal, since = 0) {
  const out = [];
  const say = (who, clip) => clip && out.push({ who, clip });
  let elder = null;
  const count = { you: 0, them: 0 }; // each side's running total, said aloud
  const called = {}; // category -> elder's words
  const bare = {}; // `${who}:${category}` -> called by bare name, to be said when shown

  events.forEach((e, at) => {
    if (e.deal !== deal) return;
    const now = at >= since; // earlier events set the scene but are not said again
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
      case "exchanged":
        // Only elder announces, and only when leaving some (p. 57).
        if (now && who === elder && e.count < 5) say(who, `take-${e.count}`);
        break;
      case "called": {
        if (who === elder) called[e.category] = e.said;
        if (!now) break;
        if (e.said === "nothing") {
          say(who, "nothing");
          break;
        }
        if (e.category === "point") {
          const point = e.said.match(/^point of (\d+)(?: \((\d+)\))?/);
          if (point) {
            say(who, `point-${point[1]}`);
            if (point[2]) {
              say(other(who), "what-make");
              say(who, `n-${point[2]}`);
            }
          }
          break;
        }
        const parts = e.said.split(", ").map(holdingClip);
        if (parts.some((clip) => clip === null)) bare[`${who}:${e.category}`] = true;
        for (const clip of parts) say(who, clip);
        break;
      }
      case "decided": {
        // Younger answers elder's call; a call of nothing gets no answer.
        const younger = elder ? other(elder) : null;
        const silent = called[e.category] === undefined || called[e.category] === "nothing";
        if (now && younger && !silent) {
          say(younger, e.winner === elder ? "good" : e.winner === younger ? "not-good" : "equal");
        }
        break;
      }
      case "showed": {
        // A holding called by its bare name is said in full as it is shown.
        const clip = holdingClip(String(e.what));
        const category = clip && clip.startsWith("seq") ? "sequences" : clip ? "sets" : null;
        if (now && clip && category && bare[`${who}:${category}`]) say(who, clip);
        break;
      }
      case "scored": {
        if (!who) break;
        count[who] += e.amount;
        if (!now) break;
        if (e.category === "bonus") say(who, String(e.what).includes("repique") ? "repique" : "pique");
        if (e.category === "cards") say(who, e.amount >= 40 ? "capot" : "the-cards");
        if (e.category === "carte_blanche") say(who, "carte-blanche-have");
        // Counting aloud: the running total, as each score is made.
        if (count[who] > 0 && count[who] <= 170) say(who, `n-${count[who]}`);
        break;
      }
      case "partie_ends":
        if (now) say("them", e.you > e.them ? "congratulations" : "good-game");
        break;
      default:
        break;
    }
  });
  return out;
}
