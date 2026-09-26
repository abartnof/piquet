// Piquet -- the page.
//
// It renders the engine's state and sends back commands. It knows nothing
// about the rules: whether a card may be played, what a declaration is worth,
// who won the trick, what Foster would do -- all of that arrives in the state,
// and a move the rules forbid comes back as `state.error` in the engine's own
// words. The protocol is docs/PROTOCOL.md; the engine is crates/piquet-core.
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
const DEFAULT_PREFS = { tab: true, undo: true, pause: true, sort: "suit" };
const DEFAULT_AIDS = { hints: true, play_forced: true, play_winners: true, declare_for_me: false };

// Automated tests pass ?test to drop the pauses that make play feel like play.
const TESTING = new URL(window.location.href).searchParams.has("test");
const PAUSE_MS = TESTING ? 0 : 900;

let engine = null; // the WebAssembly module, wrapped
let game = null; // { level, seed, record } -- enough to rebuild the table
let prefs = { ...DEFAULT_PREFS };
let selected = new Set(); // cards chosen for the discard
let fresh = new Set(); // cards just drawn, marked until the play begins
let lifted = new Set(); // the cards of the declaration under the pointer
let holding = null; // a finished trick left on the table for a moment
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
  holding = null;
  keep();
  render();
}

function resume(saved) {
  // Rebuilding replays the opponent's thinking so far -- a few seconds late
  // in a partie against Foster -- so say so rather than look frozen.
  const note = el("p", { class: "restoring" }, "Restoring your game\u2026");
  $("prompt").replaceChildren(note);
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
    const name = $("level").selectedOptions[0].textContent.replace(/^\d · /, "");
    if (!window.confirm(`Start a new partie against ${name}? This one will be abandoned.`)) {
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

function act(command) {
  if (busy) return;
  const before = engine.state();
  busy = true;
  $("prompt").insertAdjacentHTML("beforeend", '<p class="thinking">…</p>');
  // Let the page paint before the opponent thinks; Foster can take a moment.
  setTimeout(() => {
    const accepted = engine.send(command);
    const after = engine.state();
    if (accepted) {
      selected.clear();
      lifted.clear();
      const drew = after.events.slice(before.events.length).find((e) => e.kind === "drew");
      if (drew) fresh = new Set(drew.drew);
      keep();
      // Leave a finished trick on the table a moment, so the card the
      // opponent put on it is seen rather than inferred.
      if (prefs.pause && PAUSE_MS && tricksTaken(after) > tricksTaken(before) && after.last_trick) {
        holding = after.last_trick;
        render(after);
        setTimeout(() => {
          holding = null;
          busy = false;
          render();
        }, PAUSE_MS);
        return;
      }
    }
    busy = false;
    render(after);
  }, 20);
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

const back = (small = false) => el("div", { class: `card back ${small ? "small" : ""}` });
const slot = (small = false) => el("div", { class: `card slot ${small ? "small" : ""}` });

function sorted(cards) {
  const rank = (c) => RANKS.indexOf(c[0]);
  const suit = (c) => SUIT_ORDER.indexOf(c[1]);
  return [...cards].sort(
    prefs.sort === "rank" ? (a, b) => rank(a) - rank(b) || suit(a) - suit(b) : (a, b) => suit(a) - suit(b) || rank(a) - rank(b),
  );
}

function render(s = engine.state()) {
  const them = s.opponent.name;
  $("who").textContent = `against ${them}, who ${s.opponent.gloss}`;
  $("seed").textContent = `seed ${s.seed}`;
  $("level").value = String(s.level);
  $("their-name").textContent = them;
  $("undo").hidden = !prefs.undo;
  $("undo").disabled = busy || !s.can_undo;
  if (s.phase === "play" && (s.trick || s.last_trick)) fresh.clear();

  renderScores(s);
  renderTab(s);
  renderOpponent(s);
  renderTrick(s);
  renderHand(s);
  renderWorth(s);
  renderPrompt(s);
  renderDiscards(s);
  renderLog(s);
  renderSettings(s);
}

function renderScores(s) {
  const them = s.opponent.name;
  const scores = $("scores");
  scores.replaceChildren(
    el("span", { class: "big" }, "Partie: ", el("span", { class: "you" }, `you ${s.partie.you}`), " · ",
      el("span", { class: "them" }, `${them} ${s.partie.them}`)),
    el("span", {}, `Deal ${s.deal} of six · you are ${s.you_are}${s.you_are === "elder" ? " (you lead)" : " (you dealt)"}`),
    el("span", {}, "This deal: ", el("span", { class: "you" }, `you ${s.score.you}`), " · ",
      el("span", { class: "them" }, `${them} ${s.score.them}`), ` · tricks ${s.tricks.you}–${s.tricks.them}`),
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
  const them = s.opponent.name;

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

  const step = { elder_exchange: 0, younger_exchange: 0, declare_point: 1, declare_sequences: 2, declare_sets: 3, play: 4, complete: 5 }[s.phase];
  const track = el("div", { class: "track" });
  PHASES.forEach((name, i) => {
    const text = i === 4 && step === 4 ? `Trick ${Math.min(12, s.tricks.you + s.tricks.them + 1)} of 12` : name;
    track.append(el("span", { class: i === step ? "now" : i < step ? "past" : "" }, text));
  });

  const sums = {};
  for (const e of s.events) {
    if (e.kind !== "scored" || e.deal !== s.deal) continue;
    sums[e.category] = sums[e.category] || { you: 0, them: 0 };
    sums[e.category][e.who] += e.amount;
  }
  const rows = el("div", { class: "cats" });
  rows.append(el("span", { class: "head" }, ""), el("span", { class: "head you" }, "you"), el("span", { class: "head them" }, them));
  for (const [key, name] of TAB_ROWS) {
    const got = sums[key];
    if (!got && (key === "carte_blanche" || key === "bonus")) continue;
    rows.append(el("span", {}, name),
      el("span", { class: "you" }, got && got.you ? String(got.you) : "–"),
      el("span", { class: "them" }, got && got.them ? String(got.them) : "–"));
  }
  tab.replaceChildren(strip, track, rows);
}

function renderOpponent(s) {
  const completed = s.tricks.you + s.tricks.them;
  const theirs = Math.max(0, 12 - completed - (s.trick && s.trick.leader === "them" ? 1 : 0));
  const row = $("their-hand");
  row.replaceChildren();
  for (let i = 0; i < theirs; i++) row.append(back(true));
  row.append(el("span", { class: "count" }, `${theirs} card${theirs === 1 ? "" : "s"}`));
}

function renderTrick(s) {
  const them = s.opponent.name;
  const area = $("trick");
  area.replaceChildren();
  if (holding) {
    // The trick just finished, left where it was played.
    const mine = holding.leader === "you" ? holding.led : holding.followed;
    const other = holding.leader === "you" ? holding.followed : holding.led;
    area.append(
      el("figure", {}, card(other, { extra: "landed" }), el("figcaption", {}, them)),
      el("figure", {}, card(mine, { extra: "landed" }), el("figcaption", {}, "you")),
      el("p", { class: "taken" }, holding.winner === "you" ? "Your trick." : `${them}'s trick.`),
    );
    return;
  }
  if (s.phase === "play" || s.trick || s.last_trick) {
    const t = s.trick;
    const theirCard = t && (t.leader === "them" ? t.led : t.followed);
    const yourCard = t && (t.leader === "you" ? t.led : t.followed);
    area.append(
      el("figure", {}, theirCard ? card(theirCard, { extra: "landed" }) : slot(), el("figcaption", {}, them)),
      el("figure", {}, yourCard ? card(yourCard) : slot(), el("figcaption", {}, "you")),
    );
    if (s.last_trick) {
      const l = s.last_trick;
      const mine = l.leader === "you" ? l.led : l.followed;
      const other = l.leader === "you" ? l.followed : l.led;
      area.append(el("figure", {},
        el("div", { class: "row" }, card(other, { small: true }), card(mine, { small: true })),
        el("figcaption", {}, "last trick: ", el("span", { class: "won" }, l.winner === "you" ? "yours" : `${them}'s`))));
    }
  } else {
    const talon = el("div", { class: "row" });
    for (let i = 0; i < s.talon_remaining; i++) talon.append(back(true));
    area.append(el("figure", {}, talon,
      el("figcaption", {}, `talon: ${s.talon_remaining} card${s.talon_remaining === 1 ? "" : "s"}`)));
  }
}

function renderHand(s) {
  const prompt = s.prompt;
  const hand = $("hand");
  const hinted = new Set(s.hint && s.aids.hints ? s.hint.cards : []);
  const choosing = !busy && (prompt.kind === "exchange" || prompt.kind === "play");

  // Remember where each card was, so a reordering slides rather than jumps.
  const was = new Map([...hand.children].map((n) => [n.dataset.code, n.getBoundingClientRect()]));

  hand.className = `row hand ${choosing ? "" : "idle"}`;
  hand.replaceChildren();
  for (const code of sorted(s.hand)) {
    const classes = [];
    if (prompt.kind === "exchange" && selected.has(code)) classes.push("selected");
    if (prompt.kind === "play" && !prompt.legal.includes(code)) classes.push("illegal");
    if (hinted.has(code)) classes.push("hinted");
    if (fresh.has(code)) classes.push("fresh");
    if (lifted.has(code)) classes.push("lifted");
    const node = card(code, { extra: classes.join(" ") });
    node.addEventListener("click", () => choose(code));
    hand.append(node);
  }

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

function renderWorth(s) {
  const worth = $("worth");
  worth.textContent = ["exchange", "declare"].includes(s.prompt.kind)
    ? `Worth: ${s.worth.length ? s.worth.join(" · ") : "nothing to call"}`
    : "";
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
    el("span", {}, "★ ", s.hint.text, " "),
    el("button", { class: "follow", onclick: () => act(s.hint.command), title: "Do what the hint says" }, "Follow"));
}

function renderPrompt(s) {
  const them = s.opponent.name;
  const prompt = s.prompt;
  const box = $("prompt");
  box.replaceChildren();
  const ask = (text) => box.append(el("div", { class: "ask" }, text));

  switch (prompt.kind) {
    case "exchange": {
      const n = selected.size;
      ask(s.you_are === "elder"
        ? `You are elder: throw between 1 and ${prompt.limit} cards and draw as many from the talon.`
        : `You are younger: throw between 1 and ${prompt.limit} cards — whatever ${them} left — and draw as many.`);
      box.append(el("p", { class: "muted" }, "Click cards in your hand to choose them."));
      const buttons = el("div", { class: "buttons" },
        el("button", { class: "primary", onclick: () => act(`exchange ${[...selected].join(" ")}`), disabled: n < 1 ? "" : false },
          n ? `Throw ${sorted([...selected]).map(label).join(" ")} and draw ${n}` : "Choose cards to throw"));
      if (n) buttons.append(el("button", { onclick: () => { selected.clear(); render(); } }, "Clear"));
      box.append(buttons);
      break;
    }
    case "declare": {
      const name = CATEGORY[prompt.category] || prompt.category;
      ask(prompt.answering
        ? `${name}: ${them} calls “${prompt.answering}.” What do you call?`
        : s.you_are === "elder" ? `${name}: you speak first.` : `${name}: ${them} called nothing. What do you call?`);
      const options = el("div", { class: "options" });
      const advised = s.hint && s.aids.hints ? s.hint.command : null;
      prompt.options.forEach((option, i) => {
        let text;
        if (option.full) text = `Call ${option.text} — ${option.score} if good`;
        else if (option.text === "nothing") text = "Say nothing (sink it)";
        else text = `Call only ${option.text} — sinking the rest`;
        const button = el("button", {
          class: `${i === 0 ? "primary" : ""} ${advised === `declare ${i}` ? "advised" : ""}`,
          onclick: () => act(`declare ${i}`),
          onmouseenter: () => { lifted = new Set(option.cards); renderHand(s); },
          onmouseleave: () => { lifted.clear(); renderHand(s); },
        }, el("span", { class: "key" }, String(i + 1)), " ", text);
        options.append(button);
      });
      box.append(options);
      break;
    }
    case "play": {
      if (s.trick && s.trick.leader === "them") {
        const narrowed = prompt.legal.length < s.hand.length;
        ask(`${them} led ${label(s.trick.led)}. ${narrowed ? "You must follow suit." : "You cannot follow suit: play anything."}`);
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

function renderDiscards(s) {
  const discards = $("discards");
  discards.replaceChildren(...sorted(s.discards).map((c) => card(c, { small: true })));
  if (!s.discards.length) discards.append(el("span", { class: "muted" }, "none yet"));
}

function renderLog(s) {
  const log = $("log");
  log.replaceChildren();
  for (const e of s.events) {
    const who = e.kind === "deal_begins" ? "deal" : e.who === "you" ? "you" : e.who === "them" ? "them" : "table";
    log.append(el("p", { class: who }, e.text));
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
