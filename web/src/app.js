// Piquet -- the page.
//
// It renders the engine's state and sends back commands. It knows nothing
// about the rules: whether a card may be played, what a declaration is worth,
// who won the trick, what the strongest play is -- all of that arrives in the
// state, and a move the rules forbid comes back as `state.error` in the
// engine's own words. The protocol is docs/PROTOCOL.md; the engine is
// crates/piquet-core.
//
// What the page does own is how the game *feels*: the order of the hand, what
// lifts and glows, how long a finished trick stays on the table, which aids
// are on, and the keyboard. Andrew's brief: "less persnickety, less needless
// clicking -- rather, effortless and fun", every aid something that can be
// turned off.

"use strict";

const SUITS = { S: "♠", H: "♥", D: "♦", C: "♣" };
const RANKS = "AKQJT987";
const SUIT_ORDER = ["S", "H", "C", "D"]; // so the colours alternate
const CATEGORY = { point: "Point", sequences: "Sequences", sets: "Sets" };
const TAB_ROWS = [
  ["carte_blanche", "Carte blanche"],
  ["point", "Point"],
  ["sequences", "Sequences"],
  ["sets", "Sets"],
  ["play", "Tricks"],
  ["cards", "The cards"],
  ["bonus", "Pique, repique"],
];
const PHASES = ["Exchange", "Point", "Sequences", "Sets", "Tricks", "Count"];

const GAME_STORE = "piquet.game";
const PREF_STORE = "piquet.prefs";
const AID_STORE = "piquet.aids";
const DEFAULT_PREFS = { tab: true, undo: true, pause: true, sort: "auto" };
const DEFAULT_AIDS = { hints: true, play_forced: true, play_winners: true, declare_for_me: false };

// Automated tests pass ?test to drop the pauses that make play feel like play.
const TESTING = new URL(window.location.href).searchParams.has("test");
const PAUSE_MS = TESTING ? 0 : 900;
const CUT_PAUSE_MS = TESTING ? 0 : 1800;

// No proper names at the table (Andrew: "just call them your opponent").
const THEM = "your opponent";
const Them = "Your opponent";

let engine = null; // the WebAssembly module, wrapped
let game = null; // { level, seed, record } -- enough to rebuild the table
let prefs = { ...DEFAULT_PREFS };
let selected = new Set(); // cards chosen for the discard
let fresh = new Set(); // cards just drawn, marked until the play begins
let lifted = new Set(); // cards lifted by pointing at a declaration or a holding
let pinned = null; // a holding the player clicked, whose cards stay lifted
let holding = null; // something left on the table a moment: a trick, or the cut
let opened = new Set(); // earlier deals the player has unfolded in the narration
let busy = false;

const $ = (id) => document.getElementById(id);

async function load() {
  const bytes = Uint8Array.from(atob(WASM_BASE64), (c) => c.charCodeAt(0));
  const { instance } = await WebAssembly.instantiate(bytes, {});
  const ex = instance.exports;
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  return {
    start(level, seed) {
      ex.piquet_new(level, seed);
    },
    state() {
      const view = new Uint8Array(ex.memory.buffer, ex.piquet_state(), ex.piquet_state_len());
      return JSON.parse(dec.decode(view));
    },
    send(command) {
      const bytes = enc.encode(command);
      const at = ex.piquet_alloc(bytes.length);
      new Uint8Array(ex.memory.buffer, at, bytes.length).set(bytes);
      return ex.piquet_send(bytes.length) === 1;
    },
  };
}

// --- remembering ------------------------------------------------------------
// The engine is deterministic, so a level, a seed and the engine's own record
// of what was done from your seat *are* the game. That is what survives a
// reload, and what "Copy game record" hands over. Preferences and aids are
// kept separately: they belong to the player, not to one game.

function recall(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value === null ? fallback : { ...fallback, ...value };
  } catch (e) {
    return fallback;
  }
}

function store(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    /* private window, or storage refused: it just won't be remembered */
  }
}

function keep() {
  const s = engine.state();
  game = { level: s.level, seed: s.seed, record: s.record };
  store(GAME_STORE, game);
  const url = new URL(window.location.href);
  url.searchParams.set("level", s.level);
  url.searchParams.set("seed", s.seed);
  try {
    history.replaceState(null, "", url);
  } catch (e) {
    /* some file:// contexts refuse; harmless */
  }
}

function applyAids(aids) {
  for (const [aid, on] of Object.entries(aids)) engine.send(`set ${aid} ${on ? "on" : "off"}`);
}

function start(level, seed) {
  engine.start(level, seed);
  applyAids(recall(AID_STORE, DEFAULT_AIDS));
  selected.clear();
  fresh.clear();
  lifted.clear();
  pinned = null;
  holding = null;
  keep();
  render();
}

function resume(saved) {
  // Rebuilding replays the opponent's thinking so far -- a few seconds late
  // in a partie at level 5 -- so say so rather than look frozen.
  $("prompt").replaceChildren(el("p", { class: "restoring" }, "Restoring your game…"));
  setTimeout(() => restore(saved), TESTING ? 0 : 30);
}

function restore(saved) {
  engine.start(saved.level, saved.seed);
  const payload = [`replay ${saved.level} ${saved.seed}`, ...(saved.record || [])].join("\n");
  if (!engine.send(payload)) {
    start(saved.level, saved.seed); // a record from an older engine: begin it again
    return;
  }
  applyAids(recall(AID_STORE, DEFAULT_AIDS));
  keep();
  render();
}

function randomSeed() {
  return crypto.getRandomValues(new Uint32Array(1))[0] % 1000000;
}

function inProgress() {
  const s = engine.state();
  return s.prompt.kind !== "over" && s.record.some((r) => !r.startsWith("*"));
}

function newPartie(level) {
  if (inProgress() && !TESTING) {
    if (!window.confirm(`Start a new partie at level ${level}? This one will be abandoned.`)) {
      $("level").value = String(engine.state().level);
      return;
    }
  }
  start(level, randomSeed());
}

// --- acting -----------------------------------------------------------------

function tricksTaken(s) {
  return s.events.filter((e) => e.kind === "took_trick").length;
}

function lastCut(s) {
  const cuts = s.events.filter((e) => e.kind === "cut");
  if (cuts.length < 2) return null;
  const [a, b] = cuts.slice(-2);
  return { you: a.who === "you" ? a.card : b.card, them: a.who === "you" ? b.card : a.card };
}

function act(command) {
  if (busy) return;
  const before = engine.state();
  busy = true;
  $("prompt").insertAdjacentHTML("beforeend", '<p class="thinking">…</p>');
  // Let the page paint before the opponent thinks; level 5 can take a moment.
  setTimeout(() => {
    const accepted = engine.send(command);
    const after = engine.state();
    if (accepted) {
      selected.clear();
      lifted.clear();
      pinned = null;
      const drew = after.events.slice(before.events.length).find((e) => e.kind === "drew");
      if (drew) fresh = new Set(drew.drew);
      keep();
      // When the opponent wins the cut the deal begins at once; leave the two
      // cards on the table a moment so the player sees why.
      if (before.phase === "cut" && after.phase !== "cut" && CUT_PAUSE_MS) {
        const chose = after.events.find((e) => e.kind === "first_dealer");
        return hold({ kind: "cut", cut: lastCut(after), text: chose ? chose.text : "" }, after, CUT_PAUSE_MS);
      }
      // Leave a finished trick on the table a moment, so the card the
      // opponent put on it is seen rather than inferred.
      if (prefs.pause && PAUSE_MS && tricksTaken(after) > tricksTaken(before) && after.last_trick) {
        return hold({ kind: "trick", trick: after.last_trick }, after, PAUSE_MS);
      }
    }
    busy = false;
    render(after);
  }, 20);
}

function hold(what, state, ms) {
  holding = what;
  render(state);
  setTimeout(() => {
    holding = null;
    busy = false;
    render();
  }, ms);
}

function toggleAid(aid) {
  const aids = { ...engine.state().aids };
  aids[aid] = !aids[aid];
  store(AID_STORE, aids);
  act(`set ${aid} ${aids[aid] ? "on" : "off"}`);
}

// --- drawing ----------------------------------------------------------------

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== false && value !== null && value !== undefined) node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

function label(code) {
  return (code[0] === "T" ? "10" : code[0]) + SUITS[code[1]];
}

function card(code, { small = false, extra = "" } = {}) {
  const red = code[1] === "H" || code[1] === "D";
  const rank = code[0] === "T" ? "10" : code[0];
  return el(
    "div",
    { class: `card ${red ? "red" : ""} ${small ? "small" : ""} ${extra}`, "data-code": code, title: label(code) },
    el("span", { class: "rank" }, rank),
    el("span", { class: "pip" }, SUITS[code[1]]),
    el("span", { class: "centre" }, SUITS[code[1]]),
  );
}

const back = (small = false, extra = "") => el("div", { class: `card back ${small ? "small" : ""} ${extra}` });
const slot = (small = false) => el("div", { class: `card slot ${small ? "small" : ""}` });
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// --- the order of the hand ---------------------------------------------------
// Andrew: "i want the hand to be easily sorted in the first segment, so you
// can see the best hands you currently have for set, point, etc." So while
// the hand is still being shaped -- the exchange and the declarations -- the
// automatic order puts the best holdings first, each set apart, and the rest
// after; once the play begins it goes back to suits.

const rankOf = (c) => RANKS.indexOf(c[0]);
const suitOf = (c) => SUIT_ORDER.indexOf(c[1]);
const bySuit = (a, b) => suitOf(a) - suitOf(b) || rankOf(a) - rankOf(b);
const byRank = (a, b) => rankOf(a) - rankOf(b) || suitOf(a) - suitOf(b);

function sortMode(s) {
  if (prefs.sort !== "auto") return prefs.sort;
  return ["exchange", "declare"].includes(s.prompt.kind) ? "combos" : "suit";
}

// Groups of cards, in the order they are laid out; each group is set apart.
function arrange(s) {
  const mode = sortMode(s);
  if (mode === "combos") {
    const placed = new Set();
    const groups = [];
    for (const holding of s.worth) {
      if (holding.category === "carte_blanche") continue; // it is the whole hand
      const cards = holding.cards.filter((c) => !placed.has(c)).sort(bySuit);
      if (!cards.length) continue;
      cards.forEach((c) => placed.add(c));
      groups.push(cards);
    }
    const rest = s.hand.filter((c) => !placed.has(c)).sort(bySuit);
    if (rest.length) groups.push(rest);
    return groups;
  }
  const cards = [...s.hand].sort(mode === "rank" ? byRank : bySuit);
  const key = mode === "rank" ? (c) => c[0] : (c) => c[1];
  const groups = [];
  for (const c of cards) {
    if (!groups.length || key(groups[groups.length - 1][0]) !== key(c)) groups.push([]);
    groups[groups.length - 1].push(c);
  }
  return groups;
}

// --- rendering ---------------------------------------------------------------

function render(s = engine.state()) {
  $("who").textContent = `${Them} ${s.opponent.skill}.`;
  $("seed").textContent = `seed ${s.seed}`;
  $("level").value = String(s.level);
  $("undo").hidden = !prefs.undo;
  $("undo").disabled = busy || !s.can_undo;
  const hints = $("hints-switch");
  hints.textContent = s.aids.hints ? "Hints on" : "Hints off";
  hints.setAttribute("aria-pressed", String(s.aids.hints));
  hints.classList.toggle("on", s.aids.hints);
  if (s.phase === "play" && (s.trick || s.tricks_played.length)) fresh.clear();

  renderScores(s);
  renderTab(s);
  renderTheirSide(s);
  renderMiddle(s);
  renderYourSide(s);
  renderSortbar(s);
  renderHand(s);
  renderWorth(s);
  renderPrompt(s);
  renderLog(s);
  renderSettings(s);
}

function renderScores(s) {
  const scores = $("scores");
  const seat = s.you_are === null
    ? "cutting for the deal"
    : `you are ${s.you_are}${s.you_are === "elder" ? " (you lead)" : " (you dealt)"}`;
  scores.replaceChildren(
    el("span", { class: "big" }, "Partie: ", el("span", { class: "you" }, `you ${s.partie.you}`), " · ",
      el("span", { class: "them" }, `${THEM} ${s.partie.them}`)),
    el("span", {}, `Deal ${s.deal} of six · ${seat}`),
    el("span", {}, "This deal: ", el("span", { class: "you" }, `you ${s.score.you}`), " · ",
      el("span", { class: "them" }, `${THEM} ${s.score.them}`), ` · tricks ${s.tricks.you}–${s.tricks.them}`),
  );
  if (s.rubicon && s.standing.you < 100 && s.prompt.kind !== "over") {
    scores.append(el("span", { class: "note" },
      `${100 - s.standing.you} more to cross the rubicon — ${s.rubicon.words}.`));
  }
}

// Where we are: the six deals, the phase of this one, and a running tab.
function renderTab(s) {
  const tab = $("tab");
  tab.hidden = !prefs.tab;
  if (!prefs.tab) return;

  const strip = el("div", { class: "strip" });
  const deals = Math.max(6, s.deal, s.deals.length);
  for (let n = 1; n <= deals; n++) {
    const done = s.deals.find((d) => d.number === n);
    const now = n === s.deal && s.prompt.kind !== "over" && !done;
    strip.append(el("div", { class: `deal-cell ${now ? "now" : ""} ${done ? "done" : ""}` },
      el("span", { class: "n" }, String(n)),
      done ? el("span", { class: "you" }, String(done.you)) : el("span", { class: "muted" }, "·"),
      done ? el("span", { class: "them" }, String(done.them)) : el("span", { class: "muted" }, "·")));
  }
  strip.append(el("div", { class: "deal-cell total" },
    el("span", { class: "n" }, "total"),
    el("span", { class: "you" }, String(s.partie.you)),
    el("span", { class: "them" }, String(s.partie.them))));

  const track = el("div", { class: "track" });
  if (s.phase === "cut") {
    track.append(el("span", { class: "now" }, "Cut for deal"));
    PHASES.forEach((name) => track.append(el("span", {}, name)));
  } else {
    const step = { elder_exchange: 0, younger_exchange: 0, declare_point: 1, declare_sequences: 2, declare_sets: 3, play: 4, complete: 5 }[s.phase];
    PHASES.forEach((name, i) => {
      const text = i === 4 && step === 4 ? `Trick ${Math.min(12, s.tricks.you + s.tricks.them + 1)} of 12` : name;
      track.append(el("span", { class: i === step ? "now" : i < step ? "past" : "" }, text));
    });
  }

  const sums = {};
  for (const e of s.events) {
    if (e.kind !== "scored" || e.deal !== s.deal) continue;
    sums[e.category] = sums[e.category] || { you: 0, them: 0 };
    sums[e.category][e.who] += e.amount;
  }
  const rows = el("div", { class: "cats" });
  rows.append(el("span", { class: "head" }, ""), el("span", { class: "head you" }, "you"), el("span", { class: "head them" }, THEM));
  for (const [key, name] of TAB_ROWS) {
    const got = sums[key];
    if (!got && (key === "carte_blanche" || key === "bonus")) continue;
    rows.append(el("span", {}, name),
      el("span", { class: "you" }, got && got.you ? String(got.you) : "–"),
      el("span", { class: "them" }, got && got.them ? String(got.them) : "–"));
  }
  tab.replaceChildren(strip, track, rows);
}

function pile(count, caption) {
  const stack = el("div", { class: "stack" });
  for (let i = 0; i < Math.min(count, 6); i++) stack.append(back(true));
  return el("div", { class: "pile-wrap" }, count ? stack : slot(true), el("span", { class: "count" }, caption));
}

function tricksOf(s, who) {
  const row = $(who === "you" ? "your-tricks" : "their-tricks");
  row.replaceChildren();
  const won = s.tricks_played.filter((t) => t.winner === who);
  for (const t of won) {
    const [top, under] = t.leader === "you" ? [t.led, t.followed] : [t.followed, t.led];
    // Face up, in front of whoever won them: either player may look at any
    // time (Cavendish, Law 60).
    row.append(el("div", { class: "pair", title: `${label(t.led)} led, ${label(t.followed)} followed` },
      card(under, { small: true }), card(top, { small: true, extra: "over" })));
  }
  if (!won.length) row.append(el("span", { class: "muted" }, s.phase === "cut" ? "" : "none yet"));
}

function renderTheirSide(s) {
  const completed = s.tricks.you + s.tricks.them;
  const theirs = s.phase === "cut" ? 0 : Math.max(0, 12 - completed - (s.trick && s.trick.leader === "them" ? 1 : 0));
  const hand = $("their-hand");
  hand.replaceChildren();
  for (let i = 0; i < theirs; i++) hand.append(back(true));
  hand.append(el("span", { class: "count" }, s.phase === "cut" ? "not yet dealt" : plural(theirs, "card")));
  // Their discards: how many, never which (the pile is face down).
  $("their-discards").replaceChildren(pile(s.their_discards, s.their_discards ? plural(s.their_discards, "card") : "none yet"));
  tricksOf(s, "them");
}

function renderYourSide(s) {
  tricksOf(s, "you");
  const discards = $("discards");
  discards.replaceChildren(...[...s.discards].sort(bySuit).map((c) => card(c, { small: true })));
  if (!s.discards.length) discards.append(el("span", { class: "muted" }, s.phase === "cut" ? "" : "none yet"));
}

function renderMiddle(s) {
  $("talon").replaceChildren(s.phase === "cut"
    ? el("span", { class: "muted" }, "—")
    : pile(s.talon_remaining, plural(s.talon_remaining, "card")));
  const area = $("trick");
  area.replaceChildren();
  $("middle-title").textContent = s.phase === "cut" ? "The cut for deal" : "On the table";

  if (holding && holding.kind === "cut") return drawCut(area, holding.cut, holding.text);
  if (holding && holding.kind === "trick") {
    const t = holding.trick;
    const mine = t.leader === "you" ? t.led : t.followed;
    const other = t.leader === "you" ? t.followed : t.led;
    area.append(
      el("figure", {}, card(other, { extra: "landed" }), el("figcaption", {}, THEM)),
      el("figure", {}, card(mine, { extra: "landed" }), el("figcaption", {}, "you")),
      el("p", { class: "taken" }, t.winner === "you" ? "Your trick." : `${Them}'s trick.`),
    );
    return;
  }
  if (s.prompt.kind === "cut") return drawFan(area, s);
  if (s.prompt.kind === "choose_dealer") return drawCut(area, lastCut(s), "You cut higher: the choice of deal is yours.");

  const t = s.trick;
  const theirCard = t && (t.leader === "them" ? t.led : t.followed);
  const yourCard = t && (t.leader === "you" ? t.led : t.followed);
  area.append(
    el("figure", {}, theirCard ? card(theirCard, { extra: "landed" }) : slot(), el("figcaption", {}, THEM)),
    el("figure", {}, yourCard ? card(yourCard) : slot(), el("figcaption", {}, "you")),
  );
}

function drawCut(area, cut, text) {
  if (!cut) return;
  area.append(
    el("figure", {}, card(cut.them, { extra: "landed" }), el("figcaption", {}, `${THEM} cut`)),
    el("figure", {}, card(cut.you, { extra: "landed" }), el("figcaption", {}, "you cut")),
    text ? el("p", { class: "taken" }, text) : null,
  );
}

// The pack fanned face down: point at a card to lift everything above it,
// click to cut there. A cut lifts two to thirty cards (Cavendish, Law 3).
function drawFan(area, s) {
  const again = s.events.length && s.events[s.events.length - 1].kind === "cut_again";
  const fan = el("div", { class: "cutfan" });
  const cards = [];
  for (let i = 0; i < 32; i++) {
    const depth = i + 1;
    const allowed = depth >= s.prompt.fewest && depth <= s.prompt.most;
    const node = back(true, allowed ? "cuttable" : "fixed");
    if (allowed) {
      node.title = `Cut here: lift ${depth} cards`;
      node.addEventListener("mouseenter", () => cards.forEach((c, j) => c.classList.toggle("lifting", j <= i)));
      node.addEventListener("mouseleave", () => cards.forEach((c) => c.classList.remove("lifting")));
      node.addEventListener("click", () => act(`cut ${depth}`));
    }
    cards.push(node);
    fan.append(node);
  }
  area.append(el("div", { class: "cutbox" },
    again ? el("p", { class: "taken" }, "The cuts were equal — cut again.") : null,
    fan,
    el("p", { class: "muted" }, "Click anywhere in the pack to cut. The higher card chooses who deals; aces are high.")));
}

function renderSortbar(s) {
  const mode = sortMode(s);
  for (const button of document.querySelectorAll("#sortbar button")) {
    const chosen = button.dataset.sort === prefs.sort;
    button.classList.toggle("chosen", chosen);
    button.classList.toggle("showing", prefs.sort === "auto" && button.dataset.sort === mode);
  }
  $("sortbar").hidden = s.phase === "cut";
}

function renderHand(s) {
  const prompt = s.prompt;
  const hand = $("hand");
  const hinted = new Set(s.hint && s.aids.hints ? s.hint.cards : []);
  const choosing = !busy && (prompt.kind === "exchange" || prompt.kind === "play");

  // Remember where each card was, so a reordering slides rather than jumps.
  const was = new Map([...hand.querySelectorAll(".card")].map((n) => [n.dataset.code, n.getBoundingClientRect()]));

  hand.className = `row hand ${choosing ? "" : "idle"}`;
  hand.replaceChildren();
  arrange(s).forEach((group, g) => {
    group.forEach((code, i) => {
      const classes = [];
      if (g > 0 && i === 0) classes.push("group-start");
      if (prompt.kind === "exchange" && selected.has(code)) classes.push("selected");
      if (prompt.kind === "play" && !prompt.legal.includes(code)) classes.push("illegal");
      if (hinted.has(code)) classes.push("hinted");
      if (fresh.has(code)) classes.push("fresh");
      if (lifted.has(code)) classes.push("lifted");
      const node = card(code, { extra: classes.join(" ") });
      node.addEventListener("click", () => choose(code));
      hand.append(node);
    });
  });

  for (const node of hand.children) {
    const old = was.get(node.dataset.code);
    if (!old || !node.animate) continue;
    const now = node.getBoundingClientRect();
    const dx = old.left - now.left;
    const dy = old.top - now.top;
    if (dx || dy) {
      node.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
        { duration: TESTING ? 0 : 260, easing: "ease-out" });
    }
  }
}

// What the hand could call, one chip per holding: point at one to lift its
// cards, click to keep them lifted.
function renderWorth(s) {
  const worth = $("worth");
  worth.replaceChildren();
  if (!["exchange", "declare"].includes(s.prompt.kind)) return;
  worth.append(el("span", { class: "muted" }, "Worth: "));
  if (!s.worth.length) {
    worth.append(el("span", { class: "muted" }, "nothing to call"));
    return;
  }
  for (const holding of s.worth) {
    const on = pinned === holding.text;
    worth.append(el("button", {
      class: `chip ${holding.category} ${on ? "on" : ""}`,
      title: "Point to see its cards; click to keep them lifted",
      onmouseenter: () => { lifted = new Set(holding.cards); renderHand(s); },
      onmouseleave: () => {
        const kept = pinned && s.worth.find((w) => w.text === pinned);
        lifted = kept ? new Set(kept.cards) : new Set();
        renderHand(s);
      },
      onclick: () => {
        pinned = on ? null : holding.text;
        lifted = pinned ? new Set(holding.cards) : new Set();
        render(s);
      },
    }, holding.text));
  }
}

function choose(code) {
  if (busy) return;
  const prompt = engine.state().prompt;
  if (prompt.kind === "exchange") {
    if (selected.has(code)) selected.delete(code);
    else if (selected.size < prompt.limit) selected.add(code);
    render();
  } else if (prompt.kind === "play") {
    // Illegal cards are sent too: the engine refuses them and says why, which
    // is the whole of what a beginner needs to hear.
    act(`play ${code}`);
  }
}

function hintLine(s) {
  if (!s.hint || !s.aids.hints) return null;
  return el("div", { class: "hint" },
    el("span", {}, "★ Hint: ", s.hint.text, " "),
    el("button", { class: "follow", onclick: () => act(s.hint.command), title: "Do what the hint says" }, "Follow"),
    el("button", { class: "follow quiet", onclick: () => toggleAid("hints"), title: "Turn hints off (H)" }, "Hide hints"));
}

function renderPrompt(s) {
  const prompt = s.prompt;
  const box = $("prompt");
  box.replaceChildren();
  const ask = (text) => box.append(el("div", { class: "ask" }, text));

  switch (prompt.kind) {
    case "cut": {
      ask("Cut the pack for the deal: click anywhere in it.");
      box.append(el("p", { class: "muted" },
        "Whoever cuts the higher card chooses who deals first. Dealing is a disadvantage, "
        + "but the first dealer is elder in the sixth and last deal."));
      break;
    }
    case "choose_dealer": {
      ask("You cut higher, so you choose who deals first.");
      box.append(el("div", { class: "buttons" },
        el("button", { class: "primary", onclick: () => act("dealer you") }, "Deal first — and be elder in the sixth deal"),
        el("button", { onclick: () => act("dealer them") }, `Let ${THEM} deal — and lead now`)));
      break;
    }
    case "exchange": {
      const n = selected.size;
      ask(s.you_are === "elder"
        ? `You are elder: throw between 1 and ${prompt.limit} cards and draw as many from the talon.`
        : `You are younger: throw between 1 and ${prompt.limit} cards — whatever ${THEM} left — and draw as many.`);
      box.append(el("p", { class: "muted" }, "Click cards in your hand to choose them."));
      const buttons = el("div", { class: "buttons" },
        el("button", { class: "primary", onclick: () => act(`exchange ${[...selected].join(" ")}`), disabled: n < 1 ? "" : false },
          n ? `Throw ${[...selected].sort(bySuit).map(label).join(" ")} and draw ${n}` : "Choose cards to throw"));
      if (n) buttons.append(el("button", { onclick: () => { selected.clear(); render(); } }, "Clear"));
      box.append(buttons);
      break;
    }
    case "declare": {
      const name = CATEGORY[prompt.category] || prompt.category;
      ask(prompt.answering
        ? `${name}: ${THEM} calls “${prompt.answering}.” What do you call?`
        : s.you_are === "elder" ? `${name}: you speak first.` : `${name}: ${THEM} called nothing. What do you call?`);
      const options = el("div", { class: "options" });
      const advised = s.hint && s.aids.hints ? s.hint.command : null;
      prompt.options.forEach((option, i) => {
        let text;
        if (option.full) text = `Call ${option.text} — ${option.score} if good`;
        else if (option.text === "nothing") text = "Say nothing (sink it)";
        else text = `Call only ${option.text} — sinking the rest`;
        options.append(el("button", {
          class: `${i === 0 ? "primary" : ""} ${advised === `declare ${i}` ? "advised" : ""}`,
          onclick: () => act(`declare ${i}`),
          onmouseenter: () => { lifted = new Set(option.cards); renderHand(s); },
          onmouseleave: () => { lifted.clear(); renderHand(s); },
        }, el("span", { class: "key" }, String(i + 1)), " ", text));
      });
      box.append(options);
      break;
    }
    case "play": {
      if (s.trick && s.trick.leader === "them") {
        const narrowed = prompt.legal.length < s.hand.length;
        ask(`${Them} led ${label(s.trick.led)}. ${narrowed ? "You must follow suit." : "You cannot follow suit: play anything."}`);
      } else {
        ask("Your lead.");
      }
      box.append(el("p", { class: "muted" }, "Click a card to play it."));
      break;
    }
    case "next_deal": {
      const ended = [...s.events].reverse().find((e) => e.kind === "deal_ends");
      ask(ended ? ended.text : "The deal is over.");
      box.append(el("button", { class: "primary", onclick: () => act("next") }, "Deal the next hand"));
      break;
    }
    case "over": {
      const ended = [...s.events].reverse().find((e) => e.kind === "partie_ends");
      ask(ended ? ended.text : "The partie is over.");
      box.append(el("button", { class: "primary", onclick: () => start(s.level, randomSeed()) }, "Play another partie"));
      break;
    }
  }
  const hint = hintLine(s);
  if (hint) box.append(hint);
  if (s.error) box.append(el("div", { class: "error" }, s.error));
}

// The narration, one fold per deal: earlier deals shut to a line each, this
// one open, so the log reads as a partie rather than a scroll.
function renderLog(s) {
  const log = $("log");
  log.replaceChildren();
  const deals = new Map();
  for (const e of s.events) {
    if (!deals.has(e.deal)) deals.set(e.deal, []);
    deals.get(e.deal).push(e);
  }
  for (const [deal, events] of deals) {
    const lines = events.map((e) => {
      const who = e.kind === "deal_begins" ? "deal" : e.who === "you" ? "you" : e.who === "them" ? "them" : "table";
      return el("p", { class: who }, e.text);
    });
    const ended = events.find((e) => e.kind === "deal_ends");
    if (!ended || deal === s.deal) {
      log.append(...lines);
      continue;
    }
    const fold = el("details", { class: "fold", open: opened.has(deal) ? "" : false },
      el("summary", {}, `Deal ${deal} — you ${ended.you} · ${THEM} ${ended.them}`), ...lines);
    fold.addEventListener("toggle", () => (fold.open ? opened.add(deal) : opened.delete(deal)));
    log.append(fold);
  }
  log.scrollTop = log.scrollHeight;
}

function renderSettings(s) {
  for (const box of document.querySelectorAll("[data-aid]")) box.checked = !!s.aids[box.dataset.aid];
  for (const input of document.querySelectorAll("[data-pref]")) {
    if (input.type === "checkbox") input.checked = !!prefs[input.dataset.pref];
    else input.value = prefs[input.dataset.pref];
  }
}

// --- wiring -----------------------------------------------------------------

function wire() {
  $("new").addEventListener("click", () => newPartie(Number($("level").value)));
  $("level").addEventListener("change", () => newPartie(Number($("level").value)));
  $("undo").addEventListener("click", () => act("undo"));
  $("hints-switch").addEventListener("click", () => toggleAid("hints"));
  $("settings-toggle").addEventListener("click", () => {
    const panel = $("settings");
    panel.hidden = !panel.hidden;
    $("settings-toggle").setAttribute("aria-expanded", String(!panel.hidden));
  });
  for (const box of document.querySelectorAll("[data-aid]")) {
    box.addEventListener("change", () => toggleAid(box.dataset.aid));
  }
  for (const input of document.querySelectorAll("[data-pref]")) {
    input.addEventListener("change", () => {
      prefs[input.dataset.pref] = input.type === "checkbox" ? input.checked : input.value;
      store(PREF_STORE, prefs);
      render();
    });
  }
  for (const button of document.querySelectorAll("#sortbar button")) {
    button.addEventListener("click", () => {
      prefs.sort = button.dataset.sort;
      store(PREF_STORE, prefs);
      render();
    });
  }
  $("copy").addEventListener("click", async () => {
    const record = JSON.stringify(game);
    try {
      await navigator.clipboard.writeText(record);
      $("copied").textContent = "copied";
    } catch (e) {
      window.prompt("Copy this game record:", record);
    }
    setTimeout(() => ($("copied").textContent = ""), 2000);
  });

  document.addEventListener("keydown", (e) => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName) || e.altKey) return;
    if (e.key === "Enter") {
      const primary = $("prompt").querySelector("button.primary:not([disabled])");
      if (primary) {
        e.preventDefault();
        primary.click();
      }
    } else if (/^[1-9]$/.test(e.key) && !e.ctrlKey && !e.metaKey) {
      const option = $("prompt").querySelectorAll(".options button")[Number(e.key) - 1];
      if (option) option.click();
    } else if ((e.key === "u" || e.key === "U" || (e.key === "z" && (e.ctrlKey || e.metaKey))) && !$("undo").hidden) {
      if (!$("undo").disabled) {
        e.preventDefault();
        act("undo");
      }
    } else if ((e.key === "h" || e.key === "H") && !e.ctrlKey && !e.metaKey) {
      toggleAid("hints");
    } else if (e.key === "Escape") {
      selected.clear();
      pinned = null;
      lifted.clear();
      render();
    }
  });
}

async function main() {
  if (TESTING) document.body.classList.add("testing");
  engine = await load();
  prefs = recall(PREF_STORE, DEFAULT_PREFS);
  wire();

  const params = new URL(window.location.href).searchParams;
  const level = Number(params.get("level"));
  const seed = params.get("seed");
  const kept = recall(GAME_STORE, null);
  if (seed !== null && level) {
    // A link names a game; resume it if it is the one we were playing.
    if (kept && kept.seed === Number(seed) && kept.level === level) resume(kept);
    else start(level, Number(seed));
  } else if (kept && kept.level) {
    resume(kept);
  } else {
    start(3, randomSeed());
  }
}

main().catch((e) => {
  document.body.insertAdjacentHTML("afterbegin", `<p class="error">The engine failed to load: ${String(e)}</p>`);
});
