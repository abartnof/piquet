// Piquet -- the page.
//
// It renders the engine's state and sends back one of four commands. It knows
// nothing about the rules: whether a card may be played, what a declaration is
// worth, who won the trick -- all of that arrives in the state, and a move the
// rules forbid comes back as `state.error` in the engine's own words. The
// protocol is documented in docs/PROTOCOL.md; the engine is crates/piquet-core.

"use strict";

const SUITS = { S: "♠", H: "♥", D: "♦", C: "♣" };
const CATEGORY = { point: "Point", sequences: "Sequences", sets: "Sets" };
const STORE = "piquet.game";

let engine = null; // the WebAssembly module, wrapped
let game = null; // { level, seed, commands } -- everything needed to replay
let selected = new Set(); // cards chosen for the discard
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

// --- keeping the game -------------------------------------------------------
// The engine is deterministic, so a seed and the list of commands *are* the
// game. That is what survives a reload, and what "Copy game record" hands over.

function save() {
  try {
    localStorage.setItem(STORE, JSON.stringify(game));
  } catch (e) {
    /* private window, or storage refused: the game just won't survive a reload */
  }
}

function stored() {
  try {
    return JSON.parse(localStorage.getItem(STORE));
  } catch (e) {
    return null;
  }
}

function start(level, seed) {
  game = { level, seed, commands: [] };
  engine.start(level, seed);
  selected.clear();
  save();
  remember();
  render();
}

function replay(record) {
  engine.start(record.level, record.seed);
  const accepted = [];
  for (const command of record.commands || []) {
    if (!engine.send(command)) break;
    accepted.push(command);
  }
  game = { level: record.level, seed: record.seed, commands: accepted };
  remember();
  render();
}

function remember() {
  const url = new URL(window.location.href);
  url.searchParams.set("level", game.level);
  url.searchParams.set("seed", game.seed);
  try {
    history.replaceState(null, "", url);
  } catch (e) {
    /* some file:// contexts refuse; harmless */
  }
}

function randomSeed() {
  return crypto.getRandomValues(new Uint32Array(1))[0] % 1000000;
}

function act(command) {
  if (busy) return;
  busy = true;
  $("prompt").insertAdjacentHTML("beforeend", '<p class="thinking">…</p>');
  // Let the page paint before the opponent thinks; Foster can take a moment.
  setTimeout(() => {
    if (engine.send(command)) {
      game.commands.push(command);
      selected.clear();
      save();
    }
    busy = false;
    render();
  }, 20);
}

// --- drawing ---------------------------------------------------------------

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "onclick") node.addEventListener("click", value);
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child === null || child === undefined) continue;
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

function label(code) {
  const rank = code[0] === "T" ? "10" : code[0];
  return rank + SUITS[code[1]];
}

function card(code, { small = false, extra = "" } = {}) {
  const red = code[1] === "H" || code[1] === "D";
  const rank = code[0] === "T" ? "10" : code[0];
  return el(
    "div",
    { class: `card ${red ? "red" : ""} ${small ? "small" : ""} ${extra}`, "data-code": code, title: code },
    el("span", { class: "rank" }, rank),
    el("span", { class: "pip" }, SUITS[code[1]]),
    el("span", { class: "centre" }, SUITS[code[1]]),
  );
}

function back(small = false) {
  return el("div", { class: `card back ${small ? "small" : ""}` });
}

function slot(small = false) {
  return el("div", { class: `card slot ${small ? "small" : ""}` });
}

function render() {
  const s = engine.state();
  const them = s.opponent.name;

  $("who").textContent = `against ${them}, who ${s.opponent.gloss}`;
  $("seed").textContent = `seed ${s.seed}`;
  $("level").value = String(s.level);
  $("their-name").textContent = them;

  // Scores.
  const scores = $("scores");
  scores.replaceChildren(
    el("span", { class: "big" }, "Partie: ", el("span", { class: "you" }, `you ${s.partie.you}`), " · ",
      el("span", { class: "them" }, `${them} ${s.partie.them}`)),
    el("span", {}, `Deal ${s.deal} of six · you are ${s.you_are}${s.you_are === "elder" ? " (you lead)" : " (you dealt)"}`),
    el("span", {}, "This deal: ", el("span", { class: "you" }, `you ${s.score.you}`), " · ",
      el("span", { class: "them" }, `${them} ${s.score.them}`),
      ` · tricks ${s.tricks.you}–${s.tricks.them}`),
  );
  if (s.rubicon && s.standing.you < 100 && s.prompt.kind !== "over") {
    scores.append(el("span", { class: "note" },
      `${100 - s.standing.you} more to cross the rubicon — ${s.rubicon.words}.`));
  }

  // The opponent's hand, face down.
  const completed = s.tricks.you + s.tricks.them;
  const theirs = Math.max(0, 12 - completed - (s.trick && s.trick.leader === "them" ? 1 : 0));
  const theirHand = $("their-hand");
  theirHand.replaceChildren();
  for (let i = 0; i < theirs; i++) theirHand.append(back(true));
  theirHand.append(el("span", { class: "count" }, `${theirs} card${theirs === 1 ? "" : "s"}`));

  // The table: the trick in progress, the last one, and the talon.
  const trick = $("trick");
  trick.replaceChildren();
  if (s.phase === "play" || s.trick || s.last_trick) {
    const current = s.trick;
    const theirCard = current && current.leader === "them" ? current.led : current && current.followed && current.leader === "you" ? current.followed : null;
    const yourCard = current && current.leader === "you" ? current.led : null;
    trick.append(
      el("figure", {}, theirCard ? card(theirCard) : slot(), el("figcaption", {}, them)),
      el("figure", {}, yourCard ? card(yourCard) : slot(), el("figcaption", {}, "you")),
    );
    if (s.last_trick) {
      const t = s.last_trick;
      const mine = t.leader === "you" ? t.led : t.followed;
      const other = t.leader === "you" ? t.followed : t.led;
      trick.append(el("figure", {},
        el("div", { class: "row" }, card(other, { small: true }), card(mine, { small: true })),
        el("figcaption", {}, "last trick: ", el("span", { class: "won" }, t.winner === "you" ? "yours" : `${them}'s`))));
    }
  } else {
    const talon = el("div", { class: "row" });
    for (let i = 0; i < s.talon_remaining; i++) talon.append(back(true));
    trick.append(el("figure", {}, talon, el("figcaption", {}, `talon: ${s.talon_remaining} card${s.talon_remaining === 1 ? "" : "s"}`)));
  }

  // Your hand.
  const prompt = s.prompt;
  const hand = $("hand");
  hand.className = `row hand ${prompt.kind === "exchange" || prompt.kind === "play" ? "" : "idle"}`;
  hand.replaceChildren();
  for (const code of s.hand) {
    let extra = "";
    if (prompt.kind === "exchange" && selected.has(code)) extra = "selected";
    if (prompt.kind === "play" && !prompt.legal.includes(code)) extra = "illegal";
    const node = card(code, { extra });
    node.addEventListener("click", () => choose(code, s));
    hand.append(node);
  }

  // What the hand is worth, while that is still the question.
  const worth = $("worth");
  if (["exchange", "declare"].includes(prompt.kind)) {
    worth.textContent = s.worth.length ? `Worth: ${s.worth.join(" \u00b7 ")}` : "Worth: nothing to call";
  } else {
    worth.textContent = "";
  }

  // Your discards.
  const discards = $("discards");
  discards.replaceChildren(...s.discards.map((c) => card(c, { small: true })));
  if (!s.discards.length) discards.append(el("span", { class: "seed" }, "none yet"));

  renderPrompt(s);
  renderLog(s);
}

function choose(code, s) {
  if (busy) return;
  const prompt = s.prompt;
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
      box.append(el("p", { class: "seed" }, "Click cards in your hand to choose them."));
      box.append(el("button", {
        class: "primary",
        onclick: () => act(`exchange ${[...selected].join(" ")}`),
        ...(n < 1 ? { disabled: "" } : {}),
      }, n ? `Throw ${[...selected].map(label).join(" ")} and draw ${n}` : "Choose cards to throw"));
      break;
    }
    case "declare": {
      const name = CATEGORY[prompt.category] || prompt.category;
      ask(prompt.answering
        ? `${name}: ${them} calls “${prompt.answering}.” What do you call?`
        : s.you_are === "elder"
          ? `${name}: you speak first.`
          : `${name}: ${them} called nothing. What do you call?`);
      const options = el("div", { class: "options" });
      prompt.options.forEach((option, i) => {
        let text;
        if (option.full) text = `Call ${option.text} — ${option.score} if good`;
        else if (option.text === "nothing") text = "Say nothing (sink it)";
        else text = `Call only ${option.text} — sinking the rest`;
        options.append(el("button", { class: i === 0 ? "primary" : "", onclick: () => act(`declare ${i}`) }, text));
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
      box.append(el("p", { class: "seed" }, "Click a card to play it."));
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
      box.append(el("button", { class: "primary", onclick: () => start(game.level, randomSeed()) }, "Play another partie"));
      break;
    }
  }
  if (s.error) box.append(el("div", { class: "error" }, s.error));
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

// --- wiring ----------------------------------------------------------------

async function main() {
  engine = await load();

  $("new").addEventListener("click", () => start(Number($("level").value), randomSeed()));
  $("level").addEventListener("change", () => start(Number($("level").value), randomSeed()));
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

  const params = new URL(window.location.href).searchParams;
  const level = Number(params.get("level"));
  const seed = params.get("seed");
  const kept = stored();
  if (seed !== null && level) {
    // A link names a game; resume it if it is the one we were playing.
    if (kept && kept.seed === Number(seed) && kept.level === level) replay(kept);
    else start(level, Number(seed));
  } else if (kept && kept.level) {
    replay(kept);
  } else {
    start(3, randomSeed());
  }
}

main().catch((e) => {
  document.body.insertAdjacentHTML("afterbegin",
    `<p class="error">The engine failed to load: ${String(e)}</p>`);
});
