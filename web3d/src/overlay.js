// The overlay: the 2D surfaces floating over the table, in Material Design 3
// (docs/TABLE3D.md section 9). Andrew: "any information display should be on
// the left, or top; any area with buttons that influence gameplay should be
// on the right/bottom. preferably, all the buttons the user will need to play
// the game would be right below the deck". So down the left: the running
// score's log, the live score, what your hand is worth; under your hand: the
// prompt's buttons, the sort, undo and the hint; along the top, the partie
// itself -- the opponent, a new partie, settings.
//
// It draws only what the engine's state says, and reports what the player
// chose through `on` callbacks; it holds no rules. No proper names: the
// machine is "your opponent" everywhere a player reads (Andrew).

import "@material/web/button/filled-button.js";
import "@material/web/chips/assist-chip.js";
import "@material/web/chips/chip-set.js";
import "@material/web/chips/filter-chip.js";
import "@material/web/button/filled-tonal-button.js";
import "@material/web/button/outlined-button.js";
import "@material/web/button/text-button.js";
import "@material/web/dialog/dialog.js";
import "@material/web/divider/divider.js";
import "@material/web/iconbutton/icon-button.js";
import "@material/web/progress/linear-progress.js";
import "@material/web/select/outlined-select.js";
import "@material/web/select/select-option.js";
import "@material/web/switch/switch.js";
import "@material/web/labs/segmentedbutton/outlined-segmented-button.js";
import "@material/web/labs/segmentedbuttonset/outlined-segmented-button-set.js";
import { caption, live, scoredSince } from "./scorebug.js";
import { PATTERNS } from "./surfaces.js";

const THEM = "your opponent";
const Them = "Your opponent";
const SUITS = { S: "♠", H: "♥", D: "♦", C: "♣" };
const CATEGORY = { point: "Point", sequences: "Sequences", sets: "Sets" };

export const LEVELS = [
  [1, "plays their highest card and hopes"],
  [2, "knows what a hand is worth"],
  [3, "remembers what has been played"],
  [4, "watches what you show them"],
  [5, "reads the endgame exactly"],
];

// Law 67's order of reckoning, as the running tab lists a deal's stages.
const STAGES = [
  ["carte_blanche", "Carte blanche", 0],
  ["point", "Point", 1],
  ["sequences", "Sequences", 2],
  ["sets", "Sets", 3],
  ["bonus", "Pique, repique", 3],
  ["play", "The play", 4],
  ["cards", "The cards", 5],
];
const PHASE_STEP = { cut: -1, elder_exchange: 0, younger_exchange: 0, declare_point: 1, declare_sequences: 2, declare_sets: 3, play: 4, complete: 5 };

// Simple stroked icons, drawn for this page.
const ICONS = {
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  settings: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  narration: '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>',
  expand: '<path d="m6 9 6 6 6-6"/>',
  explain: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  hint: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1 2V16h5.2v-.2c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
};

export function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", "icon");
  svg.innerHTML = ICONS[name];
  return svg;
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, "");
    else if (value !== false && value !== null && value !== undefined) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

export const label = (code) => (code[0] === "T" ? "10" : code[0]) + SUITS[code[1]];
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

export function createOverlay(root, on) {
  const $ = (id) => root.querySelector(`#${id}`);
  // The compact overlay (a phone, or a tablet held upright) opens the tab on demand.
  const COMPACT = "(max-width: 700px), (orientation: portrait) and (max-width: 1100px)";
  let tabOpen = { deal: !window.matchMedia(COMPACT).matches, partie: false };
  let lastFigures = new Map();

  // ---- the top bar ---------------------------------------------------------

  // Your opponent's skill is chosen in Settings, once a partie (Andrew: in
  // the top bar it was "unnecessary noise when the game is happening").
  const narrate = el("md-icon-button", { id: "narration-toggle", title: "What has been said", "aria-label": "Narration", toggle: true }, icon("narration"));
  narrate.addEventListener("click", () => {
    $("narration").hidden = !$("narration").hidden;
    narrate.selected = !$("narration").hidden;
  });
  const gear = el("md-icon-button", { id: "settings-open", title: "Settings", "aria-label": "Settings" }, icon("settings"));
  gear.addEventListener("click", () => $("settings").show());
  const fresh = el("md-text-button", { id: "new" }, "New partie");
  fresh.addEventListener("click", () => on.newPartie());
  // On a phone the running score lives in the top bar; a tap opens the tab.
  const scoreChip = el("button", { class: "score-chip", "aria-label": "The running score", "aria-expanded": "false" });
  scoreChip.addEventListener("click", () => {
    const open = $("tab").classList.toggle("open");
    scoreChip.setAttribute("aria-expanded", String(open));
    tabOpen.deal = open || tabOpen.deal;
    dealFold.set(tabOpen.deal);
  });
  $("topbar").replaceChildren(
    el("span", { class: "brand" }, "Piquet"),
    scoreChip,
    fresh,
    narrate,
    gear,
  );

  // ---- folds: Material 3's expanding list item ---------------------------------
  //
  // A head that opens and closes a body: the chevron turns and the body grows
  // on a spring (style.css). Andrew: those arrows are animated in Material 3,
  // "with a lot of motion easing". The elements persist from one render to
  // the next, so the motion has something to run on; only what is inside
  // them is replaced.
  function makeFold(cls, onToggle) {
    const chevron = icon("expand");
    chevron.classList.add("chevron");
    const head = el("button", { class: `fold-head ${cls}`, "aria-expanded": "false" });
    const inner = el("div", { class: "fold-inner" });
    const root = el("div", { class: "fold" }, head, el("div", { class: "fold-body" }, inner));
    head.addEventListener("click", () => onToggle(!root.classList.contains("open")));
    return {
      root,
      inner,
      label(...children) {
        head.replaceChildren(...children, chevron);
      },
      set(open) {
        root.classList.toggle("open", open);
        head.setAttribute("aria-expanded", String(open));
        inner.inert = !open;
      },
    };
  }

  // ---- settings and credits -------------------------------------------------

  const AIDS = [
    ["hints", "Hints", "Suggest the strongest move, under your hand (H)"],
    ["play_forced", "Play forced cards", "Play a card for me when it is the only one I may play"],
    ["play_winners", "Play my winners", "Play out my hand when every trick left is certainly mine"],
    ["declare_for_me", "Declare for me", "Call everything, never ask"],
  ];
  const PREFS = [
    ["explain", "Explanations", "Say what the rules make of each moment, and how to act (E)"],
    ["tab", "The running score", "Show where the deal stands, stage by stage"],
    ["undo", "Undo", "Allow taking back a decision"],
    ["pause", "Pause on tricks", "Leave each finished trick on the table a moment"],
  ];
  const row = (title, words, control) => el("label", { class: "setting" },
    el("span", { class: "setting-text" }, el("span", { class: "setting-title" }, title), el("span", { class: "setting-words" }, words)),
    control);
  const aidSwitches = AIDS.map(([aid, title, words]) => {
    const s = el("md-switch", { "data-aid": aid });
    s.addEventListener("change", () => on.aid(aid));
    return row(title, words, s);
  });
  const prefSwitches = PREFS.map(([pref, title, words]) => {
    const s = el("md-switch", { "data-pref": pref });
    s.addEventListener("change", () => on.pref(pref, s.selected));
    return row(title, words, s);
  });
  const levelInSettings = el("md-outlined-select", { class: "level-setting", label: "Your opponent" },
    LEVELS.map(([n, words]) => el("md-select-option", { value: String(n) }, el("div", { slot: "headline" }, `${n} — ${words}`))));
  levelInSettings.addEventListener("change", () => {
    $("settings").close();
    on.level(Number(levelInSettings.value));
  });
  const speed = el("md-outlined-select", { "data-pref": "speed", label: "Animation" },
    [["0.6", "Leisurely"], ["1", "Natural"], ["1.7", "Brisk"], ["100", "Instant"]].map(([v, words]) =>
      el("md-select-option", { value: v }, el("div", { slot: "headline" }, words))));
  speed.addEventListener("change", () => on.pref("speed", Number(speed.value)));
  const sort = el("md-outlined-select", { "data-pref": "sort", label: "Order your hand" },
    [["auto", "Automatically"], ["suit", "By suit"], ["rank", "By rank"], ["combos", "By combination"]].map(([v, words]) =>
      el("md-select-option", { value: v }, el("div", { slot: "headline" }, words))));
  sort.addEventListener("change", () => on.pref("sort", sort.value));
  // The table top: one chosen at random for each partie, or your own.
  const table = el("md-outlined-select", { "data-pref": "surface", label: "The table" },
    [["random", "A new one each partie"], ...PATTERNS.map((p) => [p.id, p.name])].map(([v, words]) =>
      el("md-select-option", { value: v }, el("div", { slot: "headline" }, words))));
  table.addEventListener("change", () => on.pref("surface", table.value));
  const again = el("md-text-button", {}, "New partie");
  again.addEventListener("click", () => {
    $("settings").close();
    on.newPartie();
  });
  const copy = el("md-text-button", {}, "Copy game record");
  copy.addEventListener("click", () => on.copy(copy));
  const creditsOpen = el("md-text-button", {}, "Credits");
  creditsOpen.addEventListener("click", () => {
    $("settings").close();
    $("credits").show();
  });
  const closeSettings = el("md-filled-tonal-button", {}, "Done");
  closeSettings.addEventListener("click", () => $("settings").close());
  $("settings").replaceChildren(
    el("div", { slot: "headline" }, "Settings"),
    el("div", { slot: "content", class: "settings" },
      el("h3", {}, "Help at the table"), aidSwitches,
      el("h3", {}, "The table"), prefSwitches,
      el("div", { class: "selects" }, levelInSettings, speed, sort, table),
      el("h3", {}, "Keys"),
      el("dl", { class: "keys" },
        [["← →", "move along your hand, or the pack when cutting"],
          ["Space", "play, choose or cut there — or finish a move under way"],
          ["Enter", "the prompt's main action"],
          ["1 2 3", "a declaration"],
          ["U", "undo"],
          ["H", "hints on or off"],
          ["E", "explanations on or off"],
          ["Esc", "let go of everything chosen"]].flatMap(([k, what]) => [el("dt", {}, el("kbd", {}, k)), el("dd", {}, what)]))),
    el("div", { slot: "actions" }, again, copy, creditsOpen, closeSettings),
  );
  const closeCredits = el("md-filled-tonal-button", {}, "Close");
  closeCredits.addEventListener("click", () => $("credits").close());
  $("credits").replaceChildren(
    el("div", { slot: "headline" }, "Credits"),
    el("div", { slot: "content", class: "credits" }, credits()),
    el("div", { slot: "actions" }, closeCredits),
  );

  // ---- the score tab ---------------------------------------------------------

  const dealFold = makeFold("tab-head", (open) => {
    tabOpen.deal = open;
    dealFold.set(open);
  });
  const partieFold = makeFold("tab-head sub", (open) => {
    tabOpen.partie = open;
    partieFold.set(open);
  });
  $("tab").replaceChildren(dealFold.root, partieFold.root);

  function renderTab(s, prefs) {
    const tab = $("tab");
    tab.hidden = !prefs.tab;
    if (!prefs.tab) return;
    const step = PHASE_STEP[s.phase] ?? -1;
    const sums = {};
    for (const e of s.events) {
      if (e.kind !== "scored" || e.deal !== s.deal) continue;
      sums[e.category] ??= { you: 0, them: 0 };
      sums[e.category][e.who] += e.amount;
    }
    const figures = new Map();
    const fig = (key, value, cls = "") => {
      const cell = el("span", { class: `num ${cls}` }, value);
      if (lastFigures.has(key) && lastFigures.get(key) !== value) cell.classList.add("changed");
      figures.set(key, value);
      return cell;
    };

    dealFold.label(
      el("span", { class: "tab-title" }, s.phase === "cut" ? "Cutting for the deal" : `Deal ${s.deal}`),
      el("span", { class: "you" }, fig("head-you", String(s.score.you))),
      el("span", { class: "dot" }, "·"),
      el("span", { class: "them" }, fig("head-them", String(s.score.them))));
    dealFold.set(tabOpen.deal && s.phase !== "cut");

    const body = [];
    if (s.phase !== "cut") {
      const grid = el("div", { class: "tab-grid", role: "table", "aria-label": "This deal, stage by stage" },
        el("span", { class: "h" }, ""), el("span", { class: "h you" }, "you"), el("span", { class: "h run" }, ""),
        el("span", { class: "h them" }, THEM), el("span", { class: "h run" }, ""));
      let runYou = 0;
      let runThem = 0;
      for (const [key, name, at] of STAGES) {
        const got = sums[key];
        if (!got && (key === "carte_blanche" || key === "bonus")) continue;
        const state = at < step || s.phase === "complete" ? "done" : at === step ? "now" : "ahead";
        const done = state === "done" || !!got;
        runYou += got ? got.you : 0;
        runThem += got ? got.them : 0;
        const text = key === "play" && step === 4 ? `Trick ${Math.min(12, s.tricks.you + s.tricks.them + 1)} of 12` : name;
        const cls = `stage ${state}`;
        grid.append(
          el("span", { class: cls }, text),
          el("span", { class: `${cls} you` }, done || got ? fig(`${key}-you`, got && got.you ? `+${got.you}` : "–") : "–"),
          el("span", { class: `${cls} run` }, done || got ? fig(`${key}-run-you`, String(runYou)) : ""),
          el("span", { class: `${cls} them` }, done || got ? fig(`${key}-them`, got && got.them ? `+${got.them}` : "–") : "–"),
          el("span", { class: `${cls} run` }, done || got ? fig(`${key}-run-them`, String(runThem)) : ""),
        );
      }
      grid.append(
        el("span", { class: "stage total" }, "This deal"),
        el("span", { class: "stage total you" }, ""), el("span", { class: "stage total run" }, fig("deal-you", String(s.score.you))),
        el("span", { class: "stage total them" }, ""), el("span", { class: "stage total run" }, fig("deal-them", String(s.score.them))));
      body.push(grid);
    }
    dealFold.inner.replaceChildren(...body);

    // The partie: six deals, their scores, the running totals, the rubicon.
    partieFold.label(
      el("span", { class: "tab-title" }, "The partie"),
      el("span", { class: "you" }, fig("partie-you", String(s.partie.you))),
      el("span", { class: "dot" }, "·"),
      el("span", { class: "them" }, fig("partie-them", String(s.partie.them))));
    partieFold.set(tabOpen.partie);
    const deals = Math.max(6, s.deal, s.deals.length);
    const grid = el("div", { class: "partie-grid" },
      el("span", { class: "h" }, "Deal"), el("span", { class: "h you" }, "you"), el("span", { class: "h them" }, THEM));
    let totYou = 0;
    let totThem = 0;
    for (let n = 1; n <= deals; n++) {
      const done = s.deals.find((d) => d.number === n);
      const now = !done && n === s.deal && s.phase !== "cut";
      if (done) {
        totYou += done.you;
        totThem += done.them;
      }
      const cls = done ? "done" : now ? "now" : "ahead";
      grid.append(
        el("span", { class: `stage ${cls}` }, n > 6 ? `${n} (extra)` : String(n)),
        el("span", { class: `stage ${cls} you` }, done ? String(done.you) : now ? `${s.score.you}…` : "·"),
        el("span", { class: `stage ${cls} them` }, done ? String(done.them) : now ? `${s.score.them}…` : "·"));
    }
    grid.append(el("span", { class: "stage total" }, "Total"),
      el("span", { class: "stage total you" }, String(totYou)), el("span", { class: "stage total them" }, String(totThem)));
    const partie = [grid];
    const standing = s.standing ? s.standing.you : 0;
    if (s.rubicon && standing < 100 && s.prompt.kind !== "over") {
      partie.push(el("p", { class: "rubicon" }, `The rubicon is 100: you need ${100 - standing} more — ${s.rubicon.words}.`));
    } else if (s.phase !== "cut" && s.prompt.kind !== "over") {
      partie.push(el("p", { class: "rubicon" }, "Reach 100 over the six deals, or be rubiconed."));
    }
    partieFold.inner.replaceChildren(...partie);
    lastFigures = figures;
  }

  // ---- the prompt: what is asked of you, and the buttons that answer --------
  //
  // Under your hand, the question over the buttons that answer it.

  // What is asked of you, in two layers (Andrew: of "Your opponent led Q♣.
  // You cannot follow suit: play anything." the first is simply true, the
  // second prescriptive -- and the prescriptive part "should be easy to turn
  // off"). The fact is always shown; the interpretation -- what the rules
  // make of it, and how to act -- only with Explain on.
  function question(s, ui) {
    const p = s.prompt;
    const how = "Click a card to play it, or use ← → and Space.";
    switch (p.kind) {
      case "cut": {
        const again = s.events.length && s.events[s.events.length - 1].kind === "cut_again";
        return [again ? "The cuts were equal — cut again." : "Cut the pack for the deal.",
          "Click the spread to lift the cards above it, or use ← → and Space — or let the button cut for you. The higher card chooses who deals; aces are high."];
      }
      case "choose_dealer":
        return ["You cut higher: you choose who deals first.", "Dealing is a disadvantage, but the first dealer is elder in the sixth and last deal."];
      case "exchange":
        return [`Your exchange. You are ${s.you_are}.`,
          (s.you_are === "elder"
            ? `Throw 1 to ${p.limit} cards and draw as many. `
            : `Throw 1 to ${p.limit} cards — whatever ${THEM} left — and draw as many. `)
          + (ui.selected.length ? "Click a card again to keep it; Enter throws." : "Click cards in your hand to choose them, or use ← → and Space.")];
      case "declare": {
        const name = CATEGORY[p.category] || p.category;
        return [p.answering
          ? `${name}: ${THEM} calls “${p.answering}.”`
          : s.you_are === "elder" ? `${name}: you speak first.` : `${name}: ${THEM} called nothing.`,
        "What do you call? Sinking a holding keeps it from your opponent, at the cost of its points."];
      }
      case "play":
        if (s.trick && s.trick.leader === "them") {
          const narrowed = p.legal.length < s.hand.length;
          return [`${Them} led ${label(s.trick.led)}.`,
            `${narrowed ? "You must follow suit." : "You cannot follow suit: play anything."} ${how}`];
        }
        return ["Your lead.", how];
      // The table has just said how it ended, in the score's caption.
      case "next_deal":
        return [null, "Deal the next hand when you are ready."];
      case "over":
        return [null, null];
    }
    return [null, null];
  }

  let shownLayers = { explain: null, hints: null };
  let lastKind = null;
  const calmMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  function renderPrompt(s, ui, prefs) {
    const box = $("prompt");
    const p = s.prompt;
    const parts = [];
    const actions = (...buttons) => parts.push(el("div", { class: "actions" }, buttons));
    const button = (kind, text, onclick, attrs = {}) => {
      const b = el(`md-${kind}-button`, attrs, text);
      b.addEventListener("click", onclick);
      return b;
    };
    // What is asked of you, over the buttons that answer it: the fact; the
    // interpretation, with Explain on; the hint, with Hints on. A layer
    // just switched on arrives; otherwise nothing moves.
    const [fact, rule] = question(s, ui);
    const explain = prefs.explain !== false;
    const hint = s.aids.hints && s.hint && !["next_deal", "over"].includes(p.kind) ? s.hint : null;
    const arriving = (layer, on) => (on && shownLayers[layer] === false ? " arriving" : "");
    const lines = [];
    if (fact) lines.push(el("p", { class: "ask" }, fact));
    if (rule && explain) lines.push(el("p", { class: `note${arriving("explain", explain)}` }, rule));
    if (hint) {
      const follow = el("md-text-button", { class: "follow", title: "Do what the hint says" }, "Follow");
      follow.addEventListener("click", () => on.act(hint.command));
      lines.push(el("div", { class: `hint-line${arriving("hints", true)}` },
        icon("hint"), el("span", { class: "hint-text" }, hint.text), follow));
    }
    shownLayers = { explain, hints: !!hint };
    if (lines.length) parts.push(el("div", { class: "asked" }, lines));
    // The card the keyboard rests on, named -- the table itself is a picture.
    if (ui.focusText) parts.push(el("p", { class: "keyboard-focus", "aria-live": "polite" }, ui.focusText));
    if (s.error) parts.push(el("div", { class: "error", role: "alert" }, s.error));
    switch (p.kind) {
      // Cutting is the player's own act, if they want it; if not, a button
      // where the pointer rests (Andrew: "it should be optional to actually
      // pick a card").
      case "cut": {
        const lift = p.fewest + Math.floor(Math.random() * (p.most - p.fewest + 1));
        actions(button("filled-tonal", "Cut for me", () => on.act(`cut ${lift}`), { class: "primary" }));
        break;
      }
      case "choose_dealer":
        actions(
          button("filled", "Deal first", () => on.act("dealer you"), { class: "primary" }),
          button("outlined", `Let ${THEM} deal`, () => on.act("dealer them")));
        break;
      case "exchange": {
        const n = ui.selected.length;
        actions(
          button("filled", n ? `Throw ${ui.selected.map(label).join(" ")} and draw ${n}` : "Choose cards to throw",
            () => n && on.act(`exchange ${ui.selected.join(" ")}`), { class: "primary", disabled: !n }),
          n ? button("text", "Clear", () => on.clear()) : null);
        break;
      }
      case "declare": {
        const advised = s.hint && s.aids.hints ? s.hint.command : null;
        const options = el("div", { class: "options" });
        p.options.forEach((option, i) => {
          let text;
          if (prefs.explain === false) text = option.text === "nothing" ? "Nothing" : option.full ? option.text : `Only ${option.text}`;
          else if (option.full) text = `Call ${option.text} — ${option.score} if good`;
          else if (option.text === "nothing") text = "Say nothing (sink it)";
          else text = `Call only ${option.text}, sinking the rest`;
          const kind = i === 0 ? "filled" : "outlined";
          const b = button(kind, `${i + 1}  ${text}`, () => on.act(`declare ${i}`), { class: `${i === 0 ? "primary" : ""} ${advised === `declare ${i}` ? "advised" : ""}` });
          b.addEventListener("pointerenter", () => on.point(option.cards));
          b.addEventListener("pointerleave", () => on.unpoint());
          b.addEventListener("focus", () => on.point(option.cards));
          b.addEventListener("blur", () => on.unpoint());
          options.append(b);
        });
        parts.push(options);
        break;
      }
      case "next_deal":
        actions(button("filled", "Deal the next hand", () => on.act("next"), { class: "primary" }));
        break;
      case "over":
        actions(button("filled", "Play another partie", () => on.newPartie(true), { class: "primary" }));
        break;
    }
    // The buttons spring in when a new question brings them, and the old
    // ones shrink away where they stood rather than vanish.
    const buttons = parts.find((part) => part.matches?.(".actions, .options"));
    const kind = `${p.kind}:${p.category ?? ""}`;
    const before = box.querySelector(".actions, .options");
    if (kind !== lastKind) {
      if (before && !calmMotion.matches) {
        const rect = before.getBoundingClientRect();
        const ghost = before.cloneNode(true);
        Object.assign(ghost.style, { position: "fixed", left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, margin: "0" });
        ghost.classList.add("leaving");
        ghost.inert = true;
        ghost.addEventListener("animationend", () => ghost.remove());
        root.append(ghost);
      }
      if (buttons) buttons.classList.add("popping");
    }
    lastKind = kind;
    box.replaceChildren(...parts);
  }

  // ---- what your hand is worth ---------------------------------------------------
  //
  // Holding by holding: point at one to lift its cards in your hand, click
  // to keep them lifted. Information about the hand, so down the left.

  // An interpretation of your hand, so it goes with Explain.
  function renderWorth(s, ui, prefs) {
    const card = $("worth");
    const show = (s.prompt.kind === "exchange" || s.prompt.kind === "declare") && prefs.explain !== false;
    card.hidden = !show;
    if (!show) return;
    const chips = el("md-chip-set", { class: "worth", "aria-label": "What your hand is worth" });
    if (!s.worth.length) chips.append(el("span", { class: "note" }, "Your hand calls nothing yet."));
    for (const holding of s.worth) {
      const pinned = ui.pinned === holding.text;
      const chip = el("md-assist-chip", { label: holding.text, class: pinned ? "pinned" : "", title: "Point to see its cards; click to keep them lifted" });
      chip.addEventListener("pointerenter", () => on.point(holding.cards));
      chip.addEventListener("pointerleave", () => on.unpoint());
      chip.addEventListener("click", () => on.pin(pinned ? null : holding));
      chips.append(chip);
    }
    card.replaceChildren(el("span", { class: "card-title" }, "Your hand is worth"), chips);
  }

  // ---- the tools under your hand: the sort, undo, the hint ----------------------

  // Andrew: "sorting your hand should always be an option, with a md3 ...
  // Segmented button near the deck".
  const SORTS = [["auto", "Auto"], ["suit", "Suit"], ["rank", "Rank"], ["combos", "Combinations"]];
  const sortSet = el("md-outlined-segmented-button-set", { class: "sort", "aria-label": "Order your hand" },
    SORTS.map(([value, words]) => el("md-outlined-segmented-button", { label: words, "data-sort": value, "no-checkmark": true })));
  sortSet.addEventListener("segmented-button-set-selection", (e) => {
    if (e.detail.selected) on.pref("sort", SORTS[e.detail.index][0]);
  });
  const undo = el("md-outlined-icon-button", { id: "undo", title: "Take back your last decision (U)", "aria-label": "Undo" }, icon("undo"));
  undo.addEventListener("click", () => on.undo());
  // Andrew: "the b. prescriptive part should be easy to turn off (maybe two
  // buttons at the bottom: one button shows you interpretations, another
  // shows straight-up hints? put these where the Hint button currently is)".
  const explainChip = el("md-filter-chip", { label: "Explain", title: "What the rules make of each moment, and how to act (E)" });
  explainChip.append(Object.assign(icon("explain"), { slot: "icon" }));
  explainChip.addEventListener("click", () => on.pref("explain", explainChip.selected));
  const hintChip = el("md-filter-chip", { label: "Hints", title: "The strongest move, with Follow to make it (H)" });
  hintChip.append(Object.assign(icon("hint"), { slot: "icon" }));
  hintChip.addEventListener("click", () => {
    if (hintChip.selected !== !!lastAids.hints) on.aid("hints");
  });
  let lastAids = {};
  $("tools").replaceChildren(sortSet, undo, explainChip, hintChip);

  function renderTools(s, prefs, ui) {
    // Nothing to sort, undo or hint while cutting for the deal.
    $("tools").hidden = s.phase === "cut";
    const playing = s.phase !== "cut" && !!s.hand && s.hand.length > 0;
    sortSet.hidden = !playing;
    for (const b of sortSet.querySelectorAll("md-outlined-segmented-button")) b.selected = b.dataset.sort === prefs.sort;
    undo.hidden = !prefs.undo;
    undo.disabled = ui.busy || !s.can_undo;
    lastAids = s.aids;
    explainChip.selected = prefs.explain !== false;
    hintChip.selected = !!s.aids.hints;
  }

  // ---- the live score --------------------------------------------------------
  //
  // Andrew: "the immediacy of a WNBA on-screen live score display. 2 numbers,
  // one for each team- and when you score, there's a minor animation to
  // update the score- unless you score big, in which case there's a little
  // celebratory animation." The stage table above is the log; this is the
  // score as it stands, with the deal as the period, a bar filling toward
  // the rubicon under each number, and a caption: the latest thing said.

  const side = (who, name) => {
    const n = el("span", { class: "n" }, "0");
    const num = el("span", { class: "side-num" }, n);
    const fill = el("i");
    const root = el("div", { class: `side ${who}` },
      el("span", { class: "side-name" }, name), num,
      el("span", { class: "rubicon-bar", title: "The rubicon: a hundred" }, fill));
    return { who, root, n, num, fill, shown: 0 };
  };
  const bugYou = side("you", "You");
  const bugThem = side("them", Them);
  const period = el("div", { class: "period" });
  const said = el("p", { class: "caption", "aria-live": "polite" });
  $("bug").replaceChildren(bugYou.root, period, bugThem.root, said);
  let seen = null; // { seed, level, events }: what the bug last showed
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)");

  // Restart a CSS animation on an element.
  const replay = (node, cls) => {
    node.classList.remove(cls);
    void node.offsetWidth;
    node.classList.add(cls);
  };

  // An ordinary score: the number counts up, bumps, and a +N floats off it.
  function tick(sd, to) {
    const from = sd.shown;
    sd.shown = to;
    if (calm.matches) {
      sd.n.textContent = String(to);
      return;
    }
    const gain = el("span", { class: "gain" }, `+${to - from}`);
    gain.addEventListener("animationend", () => gain.remove());
    sd.num.append(gain);
    replay(sd.n, "bump");
    const start = performance.now();
    const ease = (t) => 1 - (1 - t) ** 3;
    const step = (now) => {
      const t = Math.min(1, (now - start) / 520);
      sd.n.textContent = String(Math.round(from + (to - from) * ease(t)));
      if (t < 1 && sd.shown === to) requestAnimationFrame(step);
      else if (sd.shown === to) sd.n.textContent = String(to);
    };
    requestAnimationFrame(step);
  }

  // A big one: a banner sweeps across the bug in the scorer's colour, their
  // number pops and a ring goes out from it. Several at once, in turn.
  let queue = Promise.resolve();
  function celebrate(sd, big) {
    root.querySelector(`#tab .tab-head .${sd.who} .num`)?.classList.add("cheer");
    if (calm.matches) return;
    queue = queue.then(() => new Promise((done) => {
      const banner = el("div", { class: `flourish ${sd.who}`, "aria-hidden": "true" },
        el("span", { class: "flourish-what" }, big.flair),
        big.points ? el("span", { class: "flourish-points" }, `+${big.points}`) : null);
      // As the banner leaves, the number it was about pops, so the eye
      // follows it there.
      banner.addEventListener("animationend", (e) => {
        if (e.target !== banner) return;
        banner.remove();
        replay(sd.n, "pop");
        const ring = el("span", { class: "ring" });
        ring.addEventListener("animationend", () => ring.remove());
        sd.num.append(ring);
        done();
      });
      $("bug").append(banner);
    }));
  }

  function renderBug(s) {
    root.querySelector("#bug .side.them")?.classList.remove("thinking");
    const now = live(s);
    const fresh = !seen || seen.seed !== s.seed || seen.level !== s.level || s.events.length < seen.events
      || now.you < bugYou.shown || now.them < bugThem.shown;
    const since = fresh ? s.events.length : seen.events;
    const news = scoredSince(s.events, s.deal, since);
    for (const sd of [bugYou, bugThem]) {
      const to = now[sd.who];
      if (fresh || to === sd.shown) {
        sd.shown = to;
        sd.n.textContent = String(to);
      } else {
        tick(sd, to);
      }
      sd.fill.style.width = `${Math.min(100, to)}%`;
      sd.root.classList.toggle("safe", to >= 100);
      sd.root.querySelector(".rubicon-bar").title = to >= 100 ? "Over the rubicon" : `${100 - to} short of the rubicon`;
      if (!fresh) for (const big of news[sd.who].big) celebrate(sd, big);
    }
    period.replaceChildren(
      el("span", { class: "period-deal" }, s.phase === "cut" ? "Cut" : `Deal ${now.deal}`),
      el("span", { class: "period-of" }, s.phase === "cut" ? "for deal" : now.deal > 6 ? "extra" : `of ${now.of}`));
    const line = caption(s.events, s.deal);
    const text = line ? `${line.who === "you" ? "You" : line.who === "them" ? Them : ""}${line.who ? ": " : ""}${line.text}` : "";
    if (said.dataset.text !== text) {
      said.dataset.text = text;
      said.className = `caption ${line?.who ?? "table"}`;
      said.replaceChildren(text);
      if (!fresh && text) replay(said, "slide");
    }
    seen = { seed: s.seed, level: s.level, events: s.events.length };
  }

  // ---- the narration ------------------------------------------------------------

  const opened = new Set();
  function renderNarration(s) {
    const log = $("log");
    const deals = new Map();
    for (const e of s.events) {
      if (!deals.has(e.deal)) deals.set(e.deal, []);
      deals.get(e.deal).push(e);
    }
    const parts = [];
    for (const [deal, events] of deals) {
      const lines = events.map((e) => el("p", { class: e.who === "you" ? "you" : e.who === "them" ? "them" : "table" }, e.text));
      const ended = events.find((e) => e.kind === "deal_ends");
      if (!ended || deal === s.deal) {
        parts.push(...lines);
        continue;
      }
      const fold = el("details", { class: "fold", open: opened.has(deal) },
        el("summary", {}, `Deal ${deal} — you ${ended.you} · ${THEM} ${ended.them}`), lines);
      fold.addEventListener("toggle", () => (fold.open ? opened.add(deal) : opened.delete(deal)));
      parts.push(fold);
    }
    log.replaceChildren(...parts);
    log.scrollTop = log.scrollHeight;
  }

  return {
    render(s, { prefs, ui }) {
      // A select that has not yet upgraded drops its value; set it again once it has.
      for (const select of [levelInSettings]) {
        select.value = String(s.level);
        select.updateComplete.then(() => {
          if (select.value !== String(s.level)) select.value = String(s.level);
        });
      }
      for (const sw of root.querySelectorAll("[data-aid]")) sw.selected = !!s.aids[sw.dataset.aid];
      for (const sw of root.querySelectorAll("md-switch[data-pref]")) sw.selected = !!prefs[sw.dataset.pref];
      speed.value = String(prefs.speed);
      sort.value = prefs.sort;
      table.value = prefs.surface ?? "random";
      scoreChip.replaceChildren(
        el("span", { class: "you" }, String(s.score.you)),
        el("span", { class: "dot" }, "·"),
        el("span", { class: "them" }, String(s.score.them)));
      renderTab(s, prefs);
      renderBug(s);
      renderWorth(s, ui, prefs);
      renderPrompt(s, ui, prefs);
      renderTools(s, prefs, ui);
      renderNarration(s);
    },
    // While your opponent thinks -- the engine runs on the page's own thread,
    // and at the top level a decision can take a second -- say so, under
    // their number.
    thinking() {
      root.querySelector("#bug .side.them")?.classList.add("thinking");
    },
    primary: () => $("prompt").querySelector(".primary:not([disabled])"),
    option: (i) => $("prompt").querySelectorAll(".options > *")[i],
  };
}

function credits() {
  const item = (title, ...lines) => el("div", { class: "credit" }, el("strong", {}, title), ...lines.map((l) => el("p", {}, l)));
  return [
    item("The card faces", "“Public domain complete playing card deck”, by AustinGabriel64, from Wikimedia Commons. CC0 1.0 — no rights reserved; credited gladly."),
    item("The card back", "Adapted from “Reverso baraja española”, by Germarquezm, from Wikimedia Commons, which includes elements of his “Baraja española.svg”.",
      "Licensed CC BY-SA 3.0 (creativecommons.org/licenses/by-sa/3.0). Changed: re-framed to the faces’ 5:7 and redrawn on flat white without its border. The back shown here is therefore also CC BY-SA 3.0."),
    item("Material Design 3", "The controls follow Google’s Material Design 3 (m3.material.io), through Material Web 2.5.0 — Apache License 2.0, © Google LLC — and Lit 3.3.3 (lit-html, lit-element, @lit/reactive-element) — BSD 3-Clause, © Google LLC — with tslib 2.8.1 (0BSD, © Microsoft). Colours generated with Material Color Utilities (Apache 2.0)."),
    item("three.js", "The table is drawn with three.js 0.186.1 — MIT License, © 2010–2026 three.js authors."),
    item("The rules", "Rubicon piquet, after pagat.com and the Portland Club laws of 1892 (Cavendish)."),
  ];
}
