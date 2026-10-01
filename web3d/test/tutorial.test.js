// The tutorial: the user's four pages (web3d/tutorial.md) -- an introduction,
// then one before each phase of play -- what they say, and when they come.
// The user: "make sure the rules that they specify are identical to how this
// videogame works", so the rules they state are checked against the engine's
// own events, not only against their wording.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PAGE_KEYS, parseTutorial, pageFor, pageDue } from "../src/tutorial.js";
import { partie } from "./partie.js";

const MD = readFileSync(new URL("../tutorial.md", import.meta.url), "utf8");
const pages = parseTutorial(MD);
const states = (await Promise.all([[3, 7], [2, 23]].map(([l, s]) => partie(l, s)))).flat();

// Every piece of text on a page, flattened.
const words = (page) =>
  [page.title, ...page.blocks.flatMap((b) => (b.items ? b.items : [b.spans]).map((spans) => spans.map((s) => s.text).join("")))].join("\n");

test("four pages, in order: the introduction, then one before each phase", () => {
  assert.deepEqual(PAGE_KEYS, ["intro", "exchange", "declarations", "tricks"]);
  assert.deepEqual(pages.map((p) => p.key), PAGE_KEYS);
  assert.deepEqual(pages.map((p) => p.title), ["Introduction", "The Exchange", "The Declarations", "The Tricks"]);
  for (const page of pages) assert.ok(page.blocks.length >= 3, `${page.title} is empty`);
});

test("the markdown the pages are written in: headings, paragraphs, lists, bold and italic", () => {
  const [page] = parseTutorial(
    "# Title\n\nA *partie* and **the talon**, then more.\n\n## Part\n\n1. **One:** first\n2. Two\n\n- a\n- **b** c\n",
  );
  assert.equal(page.title, "Title");
  assert.deepEqual(page.blocks.map((b) => b.type), ["p", "h", "ol", "ul"]);
  assert.deepEqual(page.blocks[0].spans, [
    { text: "A " },
    { text: "partie", italic: true },
    { text: " and " },
    { text: "the talon", bold: true },
    { text: ", then more." },
  ]);
  assert.equal(page.blocks[1].spans[0].text, "Part");
  assert.deepEqual(page.blocks[2].items[0], [{ text: "One:", bold: true }, { text: " first" }]);
  assert.equal(page.blocks[3].items.length, 2);
  // A paragraph may wrap over several lines of the source.
  const [wrapped] = parseTutorial("# T\n\nOne line\nand the next.\n");
  assert.equal(wrapped.blocks[0].spans[0].text, "One line and the next.");
});

test("the page for the moment you are in: its phase, or the introduction", () => {
  const expected = { exchange: "exchange", declare: "declarations", play: "tricks" };
  for (const s of states) assert.equal(pageFor(s), expected[s.prompt.kind] ?? "intro", s.prompt.kind);
  assert.deepEqual(new Set(states.map(pageFor)), new Set(PAGE_KEYS));
});

test("in the tutorial, each phase's page comes once, the first time you act in it", () => {
  const seen = ["intro"]; // the tutorial opens on it
  const shown = [];
  for (const s of states.slice(0, 400)) {
    const due = pageDue(s, seen);
    if (due) {
      shown.push(due);
      seen.push(due);
    }
  }
  assert.deepEqual(shown, ["exchange", "declarations", "tricks"]);
  // Once it has popped up, a page does not come again.
  const early = states.find((s) => s.prompt.kind === "exchange");
  assert.equal(pageDue(early, ["intro", "exchange"]), null);
});

// ---- the rules, as the engine plays them (and as pagat has them) ----------

const all = pages.map(words).join("\n");
// Both parties, played to the end: every event of each.
const ends = states.filter((s) => s.prompt.kind === "over");
const events = ends.flatMap((s) => s.events);
const scored = events.filter((e) => e.kind === "scored");

test("leading scores a point, whatever the card -- not only tens and higher", () => {
  assert.match(all, /1 point each time you lead a card, whatever it is/);
  assert.doesNotMatch(all, /lead a 10/);
  const low = scored.filter((e) => e.category === "play" && /^leading [789]/.test(e.what));
  assert.ok(low.length > 0 && low.every((e) => e.amount === 1), "the engine scores a low lead");
});

test("winning a trick your opponent led scores one, and the last trick one more", () => {
  assert.match(all, /1 point each time you win a trick your opponent led/);
  assert.match(all, /Last trick:\s*1 extra point/);
  assert.ok(scored.some((e) => e.what.startsWith("winning with") && e.amount === 1));
  assert.ok(scored.some((e) => e.what === "the last trick" && e.amount === 1));
});

test("the cards: 10 for seven tricks or more, nobody at six each, 40 for capot", () => {
  assert.match(all, /10 points for winning 7 or more of the 12\. If you split 6-6, nobody gets it/);
  assert.match(all, /score 40 instead of the 10/);
  assert.ok(scored.some((e) => e.category === "cards" && e.amount === 10));
});

test("younger must exchange at least one card, up to what elder left", () => {
  assert.match(all, /Elder hand:\s*Discards 1 to 5 cards/);
  assert.match(all, /Younger hand:\s*Discards 1 to 3 cards, or more if the elder hand left some untaken/);
  assert.doesNotMatch(all, /not to exchange at all/);
  // Elder exchanges first, 1 to 5; younger at least 1 and up to 3 plus
  // whatever elder left -- 7, when elder took only 1.
  const pairs = ends.flatMap((s) => {
    const byDeal = new Map();
    for (const e of s.events.filter((x) => x.kind === "exchanged")) byDeal.set(e.deal, [...(byDeal.get(e.deal) ?? []), e]);
    return [...byDeal.values()];
  });
  assert.ok(ends.length === 2 && pairs.length >= 12);
  for (const [elder, younger] of pairs) {
    assert.ok(elder.count >= 1 && elder.count <= 5, `elder took ${elder.count}`);
    assert.ok(younger.count >= 1 && younger.count <= 3 + (5 - elder.count), `younger took ${younger.count} after ${elder.count}`);
  }
});

test("elder may look at the talon cards they leave; younger has no such peek", () => {
  assert.match(all, /If the elder hand takes fewer than 5 cards, they may look at the ones they left/);
  assert.doesNotMatch(all, /A player may look at the/);
  // The engine tells elder all five of theirs once they have exchanged.
  const afterElder = states.find((s) => s.you_are === "elder" && s.phase !== "elder_exchange" && s.talon_seen.length);
  assert.ok(afterElder && afterElder.talon_seen.length === 5, "elder is shown all five");
});

test("the declarations: what each scores, and what beats what", () => {
  assert.match(all, /1 point per card in that suit/);
  assert.match(all, /aces count 11, face cards 10, and all other cards their number/);
  assert.match(all, /3 cards score 3, 4 cards score 4, 5 cards score 15, 6 cards score 16, 7 cards score 17, and 8 cards score 18/);
  assert.match(all, /Three of a kind scores 3, and four of a kind scores 14/);
  assert.match(all, /if they are exactly equal, neither scores/);
  for (const e of scored.filter((x) => x.category === "point")) assert.ok(e.amount >= 1 && e.amount <= 8);
});

// The user: "a newcomer has no idea what jargon like 'tierce' means". Every
// name the table gives a sequence or a set is said on the page.
test("the names the table calls sequences and sets by, and what they are", () => {
  assert.match(all, /3 cards are a tierce, 4 a quart, 5 a quint, 6 a sixième, 7 a septième, and 8 a huitième/);
  assert.match(all, /"Quart to the king" is four in a row with the king on top/);
  assert.match(all, /Three of a kind is a trio, and four of a kind a quatorze/);
  const named = scored
    .filter((e) => e.category === "sequences" || e.category === "sets")
    .flatMap((e) => e.what.split(", ").map((holding) => holding.split(" ")[0]));
  assert.ok(new Set(named).size >= 3, `only ${[...new Set(named)]} in the test parties`);
  for (const name of new Set(named)) assert.ok(all.includes(` a ${name}`), `"${name}" is never explained`);
});

test("lying: one card fewer than you hold, or nothing -- what the table offers", () => {
  assert.match(all, /claim one card fewer than you're holding, or nothing at all, but never more/);
  const declare = states.find((s) => s.prompt.kind === "declare" && s.prompt.options.length === 3);
  assert.ok(declare, "a declaration with a full call, a sink and one short");
});

test("pique, repique and the rubicon, as the partie is settled", () => {
  assert.match(all, /Reaching 30 points from declarations alone, before the opponent scores anything, earns 60 extra points/);
  assert.match(all, /If the elder hand reaches 30 points before the opponent scores anything, they get 30 extra points/);
  // The engine reckons both in Law 67's order, not the order things are said.
  assert.match(all, /points count in round order — point, sequences, sets, then tricks — even though the younger hand announces their declarations after the first lead/);
  assert.match(all, /wins the difference plus 100\. If the loser didn't reach 100 points \(the rubicon\), the winner takes both totals plus 100/);
  assert.doesNotMatch(all, /big margin/);
  for (const s of states.filter((x) => x.prompt.kind === "over" && x.settlement?.winner)) {
    const [hi, lo] = [Math.max(s.partie.you, s.partie.them), Math.min(s.partie.you, s.partie.them)];
    assert.equal(s.settlement.points, lo < 100 ? hi + lo + 100 : hi - lo + 100);
  }
});

test("no names for your opponent, and no stray typos", () => {
  assert.doesNotMatch(all, /Cori|Norman|Cavendish|Hoyle|Foster/);
  assert.doesNotMatch(all, /phaes|In each game/);
});
