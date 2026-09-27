// The overlay: the 2D surfaces floating over the table, in Material Design 3
// (docs/TABLE3D.md section 9). Andrew: "any information display should be on
// the left, or top; any area with buttons that influence gameplay should be
// on the right/bottom. preferably, all the buttons the user will need to play
// the game would be right below the deck". So down the left: the running
// score, the dialogue box, what your hand is worth; under your hand: the
// prompt's buttons, the sort, undo and the hint; along the top, the partie
// itself -- the opponent, a new partie, settings.
//
// It draws only what the engine's state says, and reports what the player
// chose through `on` callbacks; it holds no rules. No proper names: the
// machine is "your opponent" everywhere a player reads (Andrew).

import "@material/web/button/filled-button.js";
import "@material/web/chips/assist-chip.js";
import "@material/web/chips/chip-set.js";
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
import { talk } from "./talk.js";

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

  const level = el("md-outlined-select", { id: "level", label: "Your opponent", "aria-label": "Your opponent's skill" },
    LEVELS.map(([n, words]) => el("md-select-option", { value: String(n) }, el("div", { slot: "headline" }, `${n} — ${words}`))));
  level.addEventListener("change", () => on.level(Number(level.value)));
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
    level,
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
    ["hints", "Hints", "Suggest the strongest move, under your hand (H opens it)"],
    ["play_forced", "Play forced cards", "Play a card for me when it is the only one I may play"],
    ["play_winners", "Play my winners", "Play out my hand when every trick left is certainly mine"],
    ["declare_for_me", "Declare for me", "Call everything, never ask"],
  ];
  const PREFS = [
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
      el("div", { class: "selects" }, levelInSettings, speed, sort),
      el("h3", {}, "Keys"),
      el("dl", { class: "keys" },
        [["← →", "move along your hand, or the pack when cutting"],
          ["Space", "play, choose or cut there — or finish a move under way"],
          ["Enter", "the prompt's main action"],
          ["1 2 3", "a declaration"],
          ["U", "undo"],
          ["H", "open or close the hint"],
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
  // The question is said to you, so it is the last line of your half of the
  // dialogue; the buttons that answer it sit under your hand.

  function question(s, ui) {
    const p = s.prompt;
    switch (p.kind) {
      case "cut": {
        const again = s.events.length && s.events[s.events.length - 1].kind === "cut_again";
        return [again ? "The cuts were equal — cut again." : "Cut the pack for the deal.",
          "Click the spread to lift the cards above, or use ← → and Space. The higher card chooses who deals; aces are high."];
      }
      case "choose_dealer":
        return ["You cut higher, so you choose who deals first.", "Dealing is a disadvantage, but the first dealer is elder in the sixth and last deal."];
      case "exchange":
        return [s.you_are === "elder"
          ? `You are elder: throw 1 to ${p.limit} cards and draw as many.`
          : `You are younger: throw 1 to ${p.limit} cards — whatever ${THEM} left — and draw as many.`,
        ui.selected.length ? "Click a card again to keep it; Enter throws." : "Click cards in your hand to choose them, or use ← → and Space."];
      case "declare": {
        const name = CATEGORY[p.category] || p.category;
        return [p.answering
          ? `${name}: ${THEM} calls “${p.answering}.” What do you call?`
          : s.you_are === "elder" ? `${name}: you speak first. What do you call?` : `${name}: ${THEM} called nothing. What do you call?`, null];
      }
      case "play":
        if (s.trick && s.trick.leader === "them") {
          const narrowed = p.legal.length < s.hand.length;
          return [`${Them} led ${label(s.trick.led)}. ${narrowed ? "You must follow suit." : "You cannot follow suit: play anything."}`,
            "Click a card to play it, or use ← → and Space."];
        }
        return ["Your lead.", "Click a card to play it, or use ← → and Space."];
      case "next_deal": {
        const ended = [...s.events].reverse().find((e) => e.kind === "deal_ends");
        return [ended ? ended.text : "The deal is over.", null];
      }
      case "over": {
        const ended = [...s.events].reverse().find((e) => e.kind === "partie_ends");
        return [ended ? ended.text : "The partie is over.", null];
      }
    }
    return [null, null];
  }

  function renderPrompt(s, ui) {
    const box = $("prompt");
    const p = s.prompt;
    const parts = [];
    const actions = (...buttons) => parts.push(el("div", { class: "actions" }, buttons));
    const button = (kind, text, onclick, attrs = {}) => {
      const b = el(`md-${kind}-button`, attrs, text);
      b.addEventListener("click", onclick);
      return b;
    };
    // The card the keyboard rests on, named -- the table itself is a picture.
    if (ui.focusText) parts.push(el("p", { class: "keyboard-focus", "aria-live": "polite" }, ui.focusText));
    if (s.error) parts.push(el("div", { class: "error", role: "alert" }, s.error));
    switch (p.kind) {
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
          if (option.full) text = `Call ${option.text} — ${option.score} if good`;
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
    box.replaceChildren(...parts);
  }

  // ---- what your hand is worth ---------------------------------------------------
  //
  // Holding by holding: point at one to lift its cards in your hand, click
  // to keep them lifted. Information about the hand, so down the left.

  function renderWorth(s, ui) {
    const card = $("worth");
    const show = s.prompt.kind === "exchange" || s.prompt.kind === "declare";
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
  // Andrew: hints "should work like lists in MD3- with a toggle that lets it
  // be seen/hidden". Open, it floats up over the hand from the button.
  const hintFold = makeFold("hint-head", (open) => on.pref("hintOpen", open));
  hintFold.root.classList.add("hint-fold");
  hintFold.label(icon("hint"), el("span", {}, "Hint"));
  $("tools").replaceChildren(sortSet, undo, hintFold.root);

  function renderTools(s, prefs, ui) {
    // Nothing to sort, undo or hint while cutting for the deal.
    $("tools").hidden = s.phase === "cut";
    const playing = s.phase !== "cut" && !!s.hand && s.hand.length > 0;
    sortSet.hidden = !playing;
    for (const b of sortSet.querySelectorAll("md-outlined-segmented-button")) b.selected = b.dataset.sort === prefs.sort;
    undo.hidden = !prefs.undo;
    undo.disabled = ui.busy || !s.can_undo;
    const hint = s.aids.hints ? s.hint : null;
    hintFold.root.hidden = !s.aids.hints || s.phase === "cut";
    hintFold.set(!!prefs.hintOpen && !!hint);
    hintFold.inner.replaceChildren(hint
      ? el("div", { class: "hint" },
        el("span", { class: "hint-text" }, hint.text),
        (() => {
          const follow = el("md-filled-tonal-button", { title: "Do what the hint says" }, "Follow");
          follow.addEventListener("click", () => on.act(hint.command));
          return follow;
        })())
      : el("div", { class: "hint" }, el("span", { class: "hint-text" }, "Nothing to suggest just now.")));
  }

  // ---- the dialogue box --------------------------------------------------------
  //
  // Andrew: "we speak a LOT in piquet- those things we say during gameplay
  // are a part of the game. they shouldn't be hidden away here. think how in
  // RPGs, damage/healing is summed up with a sort of text box ... split into
  // two vertically-stacked halves- if the opponent does something, what they
  // 'say', what they gain in points, etc- is in the top of the box, in red-
  // if the user says/wins, it's on the bottom half in black."

  const half = (who, name) => {
    const total = el("span", { class: "half-total" });
    const lines = el("ol", { class: "lines" });
    const head = el("header", { class: "half-head" }, el("span", { class: "half-name" }, name), total);
    return { who, root: el("div", { class: `half ${who}` }, head, lines), total, lines, head };
  };
  const themHalf = half("them", Them);
  const youHalf = half("you", "You");
  const between = el("p", { class: "between" });
  const asked = el("div", { class: "asked", "aria-live": "polite" });
  youHalf.root.append(asked);
  $("talk").replaceChildren(themHalf.root, between, youHalf.root);
  let heard = { deal: null, at: -1 };

  // A rare big moment, celebrated like a three-pointer in a broadcast's score
  // box: a slab in the scorer's colour sweeps into their half, a sheen runs
  // across it, and it gives way to the line; their figure in the tab pops.
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)");
  function celebrate(h, line) {
    root.querySelector(`#tab .tab-head .${h.who} .num`)?.classList.add("cheer");
    if (calm.matches) return;
    const slab = el("div", { class: "flourish", "aria-hidden": "true" },
      el("span", { class: "flourish-what" }, line.flair),
      line.points ? el("span", { class: "flourish-points" }, `+${line.points}`) : null);
    slab.addEventListener("animationend", (e) => e.target === slab && slab.remove());
    h.root.append(slab);
  }

  function renderTalk(s, ui) {
    themHalf.head.querySelector(".thinking")?.remove();
    const t = talk(s.events, s.deal);
    // What was there when the page opened was not just said: nothing replays.
    const fresh = heard.deal === null ? Infinity : heard.deal === s.deal ? heard.at : -1;
    let latest = heard.deal === s.deal ? heard.at : -1;
    for (const h of [themHalf, youHalf]) {
      h.total.replaceChildren(s.phase === "cut" ? "" : `${t.total[h.who]} this deal`);
      h.lines.replaceChildren(...t[h.who].map((line) => {
        latest = Math.max(latest, line.at);
        const isNew = line.at > fresh;
        if (isNew && line.flair) celebrate(h, line);
        return el("li", { class: `line ${line.kind}${isNew ? " fresh" : ""}${line.flair ? " flair" : ""}` },
          el("span", { class: "words" }, line.text),
          line.points ? el("span", { class: "points" }, `+${line.points}`) : null);
      }));
    }
    const table = t.table[t.table.length - 1];
    between.replaceChildren(table ? table.text : s.phase === "cut" ? "Cutting for the first deal." : "");
    const [ask, note] = question(s, ui);
    asked.replaceChildren(...(ask ? [el("p", { class: "ask" }, ask)] : []), ...(note ? [el("p", { class: "note" }, note)] : []));
    heard = { deal: s.deal, at: latest };
    // The newest words in view: the end of each half.
    for (const h of [themHalf, youHalf]) {
      h.lines.scrollTop = h.lines.scrollHeight;
      h.lines.classList.toggle("over", h.lines.scrollHeight > h.lines.clientHeight + 1);
    }
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
      for (const select of [level, levelInSettings]) {
        select.value = String(s.level);
        select.updateComplete.then(() => {
          if (select.value !== String(s.level)) select.value = String(s.level);
        });
      }
      for (const sw of root.querySelectorAll("[data-aid]")) sw.selected = !!s.aids[sw.dataset.aid];
      for (const sw of root.querySelectorAll("md-switch[data-pref]")) sw.selected = !!prefs[sw.dataset.pref];
      speed.value = String(prefs.speed);
      sort.value = prefs.sort;
      scoreChip.replaceChildren(
        el("span", { class: "you" }, String(s.score.you)),
        el("span", { class: "dot" }, "·"),
        el("span", { class: "them" }, String(s.score.them)));
      renderTab(s, prefs);
      renderTalk(s, ui);
      renderWorth(s, ui);
      renderPrompt(s, ui);
      renderTools(s, prefs, ui);
      renderNarration(s);
    },
    // While your opponent thinks -- the engine runs on the page's own thread,
    // and at the top level a decision can take a second -- say so, in their
    // half of the dialogue.
    thinking() {
      themHalf.head.append(el("md-linear-progress", { indeterminate: true, class: "thinking", "aria-label": "Your opponent is thinking" }));
    },
    // The hint opened or closed from the keyboard.
    toggleHint: () => on.pref("hintOpen", !hintFold.root.classList.contains("open")),
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
