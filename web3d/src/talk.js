// What is said at the table, sorted by who said it (the user: "we speak a LOT
// in piquet- those things we say during gameplay are a part of the game.
// they shouldn't be hidden away").
//
// talk(events, deal) -> { them, you, table, total }: the deal's events as
// short lines in the speaker's half of the dialogue box -- what each side
// called, showed and took, and the points it won by -- summed up the way a
// role-playing game sums up a blow and its damage. A card and the point it
// makes become one line ("Leads A♥ +1"). What nobody said, or both did,
// goes to the table. A pure function of the protocol's events, so the page
// only draws it.

const SUITS = { S: "♠", H: "♥", D: "♦", C: "♣" };
const label = (code) => (code[0] === "T" ? "10" : code[0]) + SUITS[code[1]];
const cap = (text) => text.charAt(0).toUpperCase() + text.slice(1);
const TAKES = { point: "the point", sequences: "sequences", sets: "sets" };
const NAME = { point: "Point", sequences: "Sequences", sets: "Sets", carte_blanche: "Carte blanche" };

const RUBICON = 100;

// The rare big moments, which the dialogue box celebrates (the user: like a
// three-pointer's graphic in a basketball broadcast's score box -- "for
// special events (not for every event)"). Everything else is said quietly.
export function flairOf(e) {
  const what = String(e.what ?? "").toLowerCase();
  if (e.category === "bonus") return what.includes("repique") ? "Repique" : "Pique";
  if (e.category === "carte_blanche") return "Carte blanche";
  if (e.category === "cards" && e.amount >= 40) return "Capot";
  if (e.category === "sets" && what.includes("quatorze")) return "Quatorze";
  const long = what.match(/sixième|septième|huitième/);
  if (e.category === "sequences" && long) return cap(long[0]);
  return null;
}

export function talk(events, deal) {
  const halves = { you: [], them: [], table: [] };
  const total = { you: 0, them: 0 };
  let onTable = 0; // cards on the table in the trick being played
  let elder = null;
  const called = {}; // elder's call in each category, as said
  const before = { you: 0, them: 0 }; // the partie's totals as the deal began

  // The latest line in a half of this kind, still without its points.
  const open = (who, kind, card) =>
    [...halves[who]].reverse().find((l) => l.kind === kind && l.points === undefined && (!card || l.card === card));

  events.forEach((e, at) => {
    if (e.deal !== deal) return;
    const who = e.who === "you" || e.who === "them" ? e.who : null;
    const say = (half, text, extra = {}) => halves[half].push({ at, who: half === "table" ? null : half, text, ...extra });

    switch (e.kind) {
      case "deal_begins":
        elder = e.elder;
        before.you = e.you_total ?? 0;
        before.them = e.them_total ?? 0;
        say("table", e.text, { kind: e.kind });
        break;
      case "called":
        if (who === elder) called[e.category] = e.said;
        say(who ?? "table", `“${cap(e.said)}.”`, { kind: "said" });
        break;
      case "decided": {
        // Younger answers elder's call (Cavendish; pagat): "good" if his is
        // better, "not good" if hers is, "equal" if neither's is. A call of
        // nothing gets no answer; younger simply takes the category.
        const younger = elder === "you" ? "them" : elder === "them" ? "you" : null;
        const silent = called[e.category] === undefined || called[e.category] === "nothing";
        if (younger && !silent) {
          const answer = e.winner === elder ? "Good" : e.winner === younger ? "Not good" : "Equal";
          say(younger, `“${answer}.”`, { kind: "answer", category: e.category, winner: e.winner ?? null });
        } else if (e.winner === "you" || e.winner === "them") {
          say(e.winner, `Takes ${TAKES[e.category] ?? e.category}`, { kind: "took" });
        }
        if (e.winner !== "you" && e.winner !== "them") {
          say("table", `${NAME[e.category] ?? cap(e.category)} ${e.category === "point" ? "is" : "are"} equal: neither scores`, { kind: "equal" });
        }
        break;
      }
      case "showed":
        say(who ?? "table", `Shows ${e.what}`, { kind: "showed" });
        break;
      case "played":
        say(who ?? "table", `${onTable === 0 ? "Leads" : "Plays"} ${label(e.card)}`, { kind: "card", card: label(e.card) });
        onTable += 1;
        break;
      case "took_trick":
        say(who ?? "table", e.number === 12 ? "Takes trick 12, the last" : `Takes trick ${e.number}`, { kind: "trick" });
        onTable = 0;
        break;
      case "scored": {
        // Carried over the rubicon by this very score: the partie's moment.
        const standing = who ? before[who] + total[who] : 0;
        const crossed = who && standing < RUBICON && standing + e.amount >= RUBICON;
        if (who) total[who] += e.amount;
        const special = flairOf(e);
        const flair = crossed ? (special ? `${special} — over the rubicon` : "Over the rubicon") : special;
        const what = String(e.what ?? "");
        // A point in the play belongs to the card or the trick that made it.
        const led = what.match(/^leading (.+)$/);
        const home = e.category === "play" && who
          ? led
            ? open(who, "card", led[1])
            : /^winning with|^the last trick/.test(what)
              ? open(who, "trick")
              : null
          : null;
        if (home) {
          home.points = e.amount;
          if (flair) home.flair = flair;
        } else say(who ?? "table", cap(what || "points"), { kind: "scored", points: e.amount, ...(flair ? { flair } : {}) });
        break;
      }
      case "exchanged":
        say(who ?? "table", `Exchanges ${e.count} card${e.count === 1 ? "" : "s"}`, { kind: "exchanged" });
        break;
      case "drew":
        // Only your own draw is ever told, and it is told to you alone.
        say("you", `Threw ${e.discarded.map(label).join(" ")}, drew ${e.drew.map(label).join(" ")}`, { kind: "drew" });
        break;
      case "nothing_to_call":
        say("you", `Nothing to call in ${(NAME[e.category] ?? e.category).toLowerCase()}`, { kind: "nothing" });
        break;
      default:
        say("table", e.text, { kind: e.kind });
    }
  });

  return { ...halves, total };
}
