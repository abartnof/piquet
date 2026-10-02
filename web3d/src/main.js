// Piquet at a three-dimensional table.
//
// A client of the table protocol (docs/PROTOCOL.md): it draws the engine's
// state and sends back commands, and holds no rules. The plan is
// docs/TABLE3D.md. This file is the app: it boots the engine, the scene and
// the overlay; keeps the player's preferences, aids and game; and turns
// clicks and keys into commands.

import { loadTextures, vectorWidth } from "./art.js";
import { facesFor, jumboTextures, phoneHere } from "./faces.js";
import { createDeck } from "./deck.js";
import { buildDemo } from "./demo.js";
import { createDirector } from "./director.js";
import { decodeBase64, loadEngine } from "./engine.js";
import { STRIPS } from "./framing.js";
import { SORTS } from "./hand.js";
import { createOverlay, label as labelOf } from "./overlay.js";
import { breaksBetween } from "./breaks.js";
import { speech } from "./speech.js";
import { chooseSurface } from "./surfaces.js";
import { createDialogue } from "./dialogue.js";
import { PAGE_KEYS, pageDue, pageFor, parseTutorial } from "./tutorial.js";
import { createCelebrations } from "./celebrate/runner.js";
import { createHud } from "./celebrate/hud.js";
import { SCENES } from "./celebrate/scenes.js";
// The user's words, as written: esbuild inlines the file as text.
import TUTORIAL_TEXT from "../tutorial.md";
import { createScene } from "./scene.js";
import { buildSpike } from "./spike.js";
import { ZONES, ZONES_PORTRAIT } from "./units.js";

/* global WASM_BASE64, ART, WORDS */

const params = new URL(window.location.href).searchParams;
const TESTING = params.has("test");
// The tests play without the moment between the declarations' rounds, unless
// one asks for it.
const PACED = !TESTING || params.has("breaks");
// How long the name of a declarations' round is up between rounds (the user:
// "it shouldn't last long, maybe a second").
const BREAK = 1000;

const GAME_STORE = "piquet3d.game";
// Versioned once, when a setting since removed changed its default; a set
// stored before that is still read.
const PREF_STORE = "piquet3d.prefs.2";
const OLD_PREF_STORE = "piquet3d.prefs";
// Versioned: "play my winners" became opt-in, and then hints did (the user:
// "when tutorial mode is on, both explanations and hints are on by default;
// else, only explanations are on"). A stored set from before keeps every
// other choice, but not hints, which it would hold only by the old default.
const AID_STORE = "piquet3d.aids.3";
const OLD_AID_STORE = "piquet3d.aids.2";
// The tutorial, if this partie is one: which partie, and what it has
// introduced so far.
const TUTORIAL_STORE = "piquet3d.tutorial";
const DEFAULT_PREFS = {
  tab: true, undo: true, pause: true, sort: "auto", speed: 1, explain: true, surface: "random",
  faces: "auto",
};
// Playing out your winners is opt-in: the user, finding their cards played
// for them mid-trick, "i didn't intend for that to happen".
const DEFAULT_AIDS = { hints: false, play_forced: true, play_winners: false, declare_for_me: false };

function recall(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value === null ? fallback : { ...fallback, ...value };
  } catch (e) {
    return fallback;
  }
}

// The aids as stored, or as they were before hints became opt-in, less hints.
function recallAids() {
  if (recall(AID_STORE, null)) return recall(AID_STORE, DEFAULT_AIDS);
  const older = recall(OLD_AID_STORE, null);
  if (!older) return DEFAULT_AIDS;
  const { hints, ...kept } = older;
  return { ...DEFAULT_AIDS, ...kept };
}

// The settings as stored, or as they were stored before the store was
// versioned.
function recallPrefs(defaults) {
  return recall(PREF_STORE, null) ? recall(PREF_STORE, defaults) : recall(OLD_PREF_STORE, defaults);
}

function store(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    /* a private window, or storage refused: it just won't be remembered */
  }
}

async function main() {
  if (TESTING) document.body.classList.add("testing");
  const engine = await loadEngine(decodeBase64(WASM_BASE64));
  const numbers = (name) => (params.get(name) ? params.get(name).split(",").map(Number) : undefined);
  const stage = createScene(document.getElementById("stage"), {
    // The table top: your own pick if you made one, else one at random as
    // the page opens -- kept while it is open, new parties and all (the user:
    // "a single table top is chosen- at random- when the user opens the
    // html. but it never changes (unless manually it's changed)").
    // ?table= to try one.
    table: chooseSurface({ chosen: params.get("table") ?? recallPrefs(DEFAULT_PREFS).surface, saved: null }),
    shadow: params.get("shadow") || "vsm",
    shadowMap: Number(params.get("shadowmap")) || undefined,
    blurSamples: Number(params.get("blur")) || undefined,
    // ?light=sky,key to try another balance.
    lighting: numbers("light") ? { sky: numbers("light")[0], key: numbers("light")[1] } : {},
    eye: numbers("eye"),
    at: numbers("at"),
    fov: numbers("fov") ? numbers("fov")[0] : undefined,
  });
  const anisotropy = Number(params.get("aniso")) || stage.renderer.capabilities.getMaxAnisotropy();
  const textures = await loadTextures(ART, { anisotropy, pixelRatio: stage.renderer.getPixelRatio() });
  let facesShown = "classic"; // which faces the cards wear (showFaces, below)
  const deck = createDeck(stage, textures, { inkWidth: Number(params.get("ink") || 2.5) });
  let readyMs = 0;
  const hooks = {
    ready: () => stage.frames() > 0 && readyMs > 0,
    // How long one frame takes to draw, waited out to the end (readPixels).
    renderMs: () => {
      const gl = stage.renderer.getContext();
      const t0 = performance.now();
      stage.render();
      gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
      return performance.now() - t0;
    },
    art: () => ({ faces: facesShown, vector: textures.vector, width: textures.width, ms: Math.round(textures.ms), readyMs: Math.round(readyMs) }),
  };

  // The look spike, the angles and the motion demo are pages of their own.
  if (params.has("demo") || params.has("spike") || params.has("angles")) {
    const demo = params.has("demo") ? buildDemo(stage, deck, { slow: Number(params.get("slow") || 1) }) : null;
    if (!demo) buildSpike(stage, deck, { angles: params.has("angles") });
    stage.render();
    await firstFrame();
    readyMs = performance.now();
    document.getElementById("loading").hidden = true;
    document.getElementById("overlay").hidden = true;
    if (demo && !TESTING) demo.play();
    window.piquet3d = { ...hooks, busy: () => false, state: () => engine.state(), demoAt: (t) => demo && demo.at(t) };
    return;
  }

  // Asked by the system for less motion, the cards simply arrive -- unless the
  // player has chosen a speed for themselves.
  const calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let prefs = recallPrefs({ ...DEFAULT_PREFS, speed: calm ? 100 : DEFAULT_PREFS.speed });
  if (!SORTS.includes(prefs.sort)) prefs = { ...prefs, sort: "auto" }; // a sort since retired

  // The card faces: Jumbo Index on a phone, held either way, and the classic
  // faces on an iPad or a computer -- or whichever you choose in Settings,
  // changed where the cards lie (faces.js). ?faces=jumbo or classic to try.
  const phone = phoneHere();
  const faceSets = { classic: textures.faces };
  function showFaces(choice) {
    const want = facesFor(choice, phone);
    if (want === facesShown) return;
    faceSets[want] ??= jumboTextures(Object.keys(textures.faces), {
      width: textures.width ?? vectorWidth(stage.renderer.getPixelRatio()),
      anisotropy,
    });
    deck.setFaces(faceSets[want]);
    // The set put away gives back its GPU memory; its images stay, to be
    // uploaded again if it is chosen again.
    for (const texture of Object.values(faceSets[facesShown])) texture.dispose();
    facesShown = want;
    stage.render();
  }
  showFaces(params.get("faces") ?? prefs.faces);
  // `withheld`: the moments between rounds still to come in this move, until
  // which your buttons wait.
  const ui = { selected: [], lifted: [], pinned: null, pinnedCards: [], fresh: [], peek: false, focus: null, withheld: 0 };
  let cutDepth = 16;
  let fill = 1; // how far your hand's fan is drawn out (refill, below)
  const view = () => ({
    sort: prefs.sort,
    selected: ui.selected,
    lifted: ui.lifted,
    fresh: ui.fresh,
    peek: ui.peek,
    cutDepth,
    pause: prefs.pause,
    eye: stage.camera.position,
    zones: stage.portrait ? ZONES_PORTRAIT : ZONES,
    fill: stage.portrait ? fill : 1,
  });

  // ---- the game: started, kept, restored -------------------------------------

  const applyAids = (aids) => {
    for (const [aid, on] of Object.entries(aids)) engine.send(`set ${aid} ${on ? "on" : "off"}`);
  };
  function begin(level, seed) {
    engine.start(level, seed);
    applyAids(recallAids());
  }
  function restore(saved) {
    engine.start(saved.level, saved.seed);
    const payload = [`replay ${saved.level} ${saved.seed}`, ...(saved.record || [])].join("\n");
    if (!engine.send(payload)) begin(saved.level, saved.seed); // a record from an older engine
    applyAids(recallAids());
  }
  const randomSeed = () => crypto.getRandomValues(new Uint32Array(1))[0] % 1000000;

  const level = Number(params.get("level"));
  const seed = params.get("seed");
  const kept = recall(GAME_STORE, null);
  if (seed !== null && level) {
    if (kept && kept.seed === Number(seed) && kept.level === level) restore(kept);
    else begin(level, Number(seed));
  } else if (kept && kept.level) {
    restore(kept);
  } else {
    begin(3, randomSeed());
  }

  // ?ending -- the celebrations' staging (the user: "the dummy ending where
  // the game is basically over, and i get to scroll through the different
  // endings"): a partie played by a dull script into its last deal, until
  // you hold two cards. Play one; the last trick plays itself; the partie
  // ends, and the celebration comes, with arrows to step through them all.
  // Nothing of it is kept: your own partie is left as it was.
  const STAGING = params.has("ending");
  if (STAGING) {
    begin(level || 3, Number(seed ?? 31));
    engine.send("set play_forced on");
    const dull = (s) => {
      const p = s.prompt;
      if (p.kind === "cut") return "cut 16";
      if (p.kind === "choose_dealer") return "dealer you";
      if (p.kind === "exchange") return `exchange ${s.hand.slice(-Math.min(p.limit, 3)).join(" ")}`;
      if (p.kind === "declare") return "declare 0";
      if (p.kind === "play") return `play ${p.legal[0]}`;
      return "next";
    };
    for (let n = 0; n < 5000; n++) {
      const s = engine.state();
      if (s.prompt.kind === "over" || (s.prompt.kind === "play" && s.deal >= 6 && s.hand.length <= 2)) break;
      engine.send(dull(s));
    }
  }

  // After every accepted move, before it is animated: choices clear, and what
  // the talon gave you stands proud until the play begins.
  function settled(prev, next) {
    if (next.prompt.kind === "over" && prev.prompt.kind !== "over" && (!TESTING || STAGING)) partieEnded();
    ui.selected = [];
    ui.lifted = [];
    ui.pinned = null;
    ui.pinnedCards = [];
    ui.peek = false; // any move puts your discards back down
    const drew = next.events.slice(prev.events.length).find((e) => e.kind === "drew");
    if (drew) ui.fresh = drew.drew;
    if (["play", "complete", "cut"].includes(next.phase) || next.events.length < prev.events.length) ui.fresh = [];
    // An undo falls silent at once.
    if (next.events.length < prev.events.length) hush();
  }

  // An undo, a new partie: nothing still to be said, or held for.
  let hushes = 0;
  function hush() {
    hushes += 1;
    ui.withheld = 0;
    dialogue.stop();
    overlay.clearDialogue();
    director.cancelTimed();
  }

  // What is said in a move: only what is new.
  function spoken(prev, next) {
    const deals = new Set(next.events.slice(prev.events.length).map((e) => e.deal));
    return [...deals].flatMap((deal) => speech(next.events, deal, prev.events.length));
  }

  // The lines in the order they are said, each at its moment, with the moment
  // between rounds before the first line of each round. `pauseAt(b)` is when
  // that moment may come.
  function sequence(lines, breaks, beats, pauseAt) {
    const out = [];
    let i = 0;
    const until = (at) => {
      for (; i < lines.length && lines[i].at < at; i++) out.push({ ...lines[i], delay: beats[lines[i].at] ?? 0 });
    };
    for (const b of breaks) {
      until(b.at);
      out.push({ pause: true, at: b.at, category: b.category, delay: pauseAt(b) });
    }
    until(Infinity);
    return out;
  }

  // The moment between the declarations' rounds (the user: "an on-screen
  // thing pop up for a moment before each part of the declarations, after
  // each player is done speaking from the last one. they may start again
  // once the on-screen thing is gone"). It comes once the round before has
  // been said, and the table is held back until then -- your opponent's
  // cards stir for their next call only after it -- so each round's moment
  // is found in turn, trying the move's timing out with that round's wait.
  function pace(prev, next, dry) {
    const breaks = PACED ? breaksBetween(prev, next) : [];
    if (!breaks.length) return {};
    const lines = dialogue.words(spoken(prev, next));
    const waits = {};
    breaks.forEach((b, n) => {
      const { beats, duration } = dry(waits);
      const items = sequence(lines, breaks.slice(0, n + 1), beats, (x) => waits[x.at] ?? beats[x.at] ?? duration);
      const planned = dialogue.plan(items.slice(0, items.findIndex((x) => x.pause && x.at === b.at) + 1));
      waits[b.at] = planned[planned.length - 1].ms;
    });
    return { waits, lines, breaks };
  }

  // The declarations as a dialogue (the user: "two dialogue boxes to pop up
  // every move"): only what is new, each line in a box by its speaker's
  // hand when its event is seen to happen on the table.
  const DIALOGUE = new Set(["called", "decided", "nothing_to_call"]);
  function timed(prev, next, beats, paced = {}) {
    if (next.events.length < prev.events.length) return;
    const breaks = paced.breaks ?? [];
    const items = sequence(paced.lines ?? spoken(prev, next), breaks, beats, (b) => paced.waits[b.at]);
    // The score waits until the last line of the dialogue has been said.
    const last = items.map((line) => DIALOGUE.has(line.kind)).lastIndexOf(true);
    if (last >= 0 && !TESTING) overlay.hold(dialogue.estimate(items.slice(0, last + 1)));
    phasePages(prev, next, beats);
    // Your buttons wait for the last moment between rounds in this move.
    ui.withheld += breaks.length;
    // On the table's clock, so a tutorial page at the start of a phase holds
    // the boxes still along with the cards.
    dialogue.say(items, (line, words, ms) => {
      if (line.pause) director.gate(ms, (release) => between(line.category, release));
      else if (DIALOGUE.has(line.kind)) director.at(ms, () => overlay.dialogue(line.who, words, 0, line.kind !== "decided"));
    });
  }

  // The round's name, up a moment while the table is held still; then the
  // table carries on, and your buttons come once the last has gone.
  function between(category, release) {
    const hushed = hushes;
    overlay.pauseScore();
    const gone = overlay.interlude(category, BREAK);
    setTimeout(() => {
      gone(); // faded by now; and gone before your buttons come
      if (hushed !== hushes) return; // an undo, a new partie: already let go
      overlay.resumeScore(BREAK);
      release();
      ui.withheld = Math.max(0, ui.withheld - 1);
      if (!ui.withheld) render();
    }, BREAK);
  }

  // In the tutorial, each phase's page at the phase's very start (the user:
  // "the pop ups pop up at the beginning of each of the phases"): when your
  // opponent moves first in it, the table stops just before their first move
  // and holds still until the page is closed; when you move first, the page
  // comes once the table is still (introduce).
  const PHASE_OF = {
    exchanged: "exchange", drew: "exchange", looked: "exchange", they_took: "exchange",
    called: "declarations", decided: "declarations", nothing_to_call: "declarations", showed: "declarations",
    played: "tricks", took_trick: "tricks",
  };
  function phasePages(prev, next, beats) {
    if (!inTutorial()) return;
    next.events.slice(prev.events.length).forEach((e, i) => {
      const key = PHASE_OF[e.kind];
      if (!key || tutorial.seen.includes(key)) return;
      tutorial = { ...tutorial, seen: [...tutorial.seen, key] };
      store(TUTORIAL_STORE, tutorial);
      if (e.who === "you") return; // yours: its page came before you moved
      director.gate(beats[prev.events.length + i] ?? 0, (release) => {
        overlay.pauseScore();
        const opened = performance.now();
        read(key, () => {
          overlay.resumeScore(performance.now() - opened);
          release();
        });
      });
    });
  }

  // On the table's clock, which stands still while the table is held.
  const dialogue = createDialogue(typeof WORDS === "object" ? WORDS : {}, () => director.clock());
  const director = createDirector({
    stage,
    deck,
    engine,
    view,
    settled,
    pace,
    timed,
    testing: TESTING && !params.has("manual"),
    manual: params.has("manual"),
    speed: prefs.speed,
  });

  // Turning a phone lays the table out the other way.
  stage.onReframe = () => {
    director.restart();
    render();
  };

  function keep() {
    if (STAGING) return; // the staging's partie is not yours
    const s = engine.state();
    store(GAME_STORE, { level: s.level, seed: s.seed, record: s.record });
    const url = new URL(window.location.href);
    url.searchParams.set("level", s.level);
    url.searchParams.set("seed", s.seed);
    try {
      history.replaceState(null, "", url);
    } catch (e) {
      /* some file:// contexts refuse; harmless */
    }
  }

  // ---- acting ----------------------------------------------------------------

  const overlay = createOverlay(document.getElementById("overlay"), {
    act,
    // Where the table speaks from: the edge of a hand, on the screen.
    anchor: (who) => director.handEdge(who),
    undo: () => act("undo"),
    tutorial: () => showTutorial(),
    tutorialMode: (on) => tutorialMode(on),
    aid: toggleAid,
    pref: setPref,
    level: (n) => newPartie(n),
    newPartie: (force) => newPartie(engine.state().level, force),
    clear: () => {
      ui.selected = [];
      director.rearrange();
      render();
    },
    point: (cards) => {
      ui.lifted = cards;
      director.rearrange();
    },
    // Letting go of a pointed-at holding falls back to the pinned one, if any.
    unpoint: () => {
      ui.lifted = ui.pinnedCards;
      director.rearrange();
    },
    pin: (holding) => {
      ui.pinned = holding ? holding.text : null;
      ui.pinnedCards = holding ? holding.cards : [];
      ui.lifted = ui.pinnedCards;
      director.rearrange();
      render();
    },
    copy: async (button) => {
      const s = engine.state();
      const record = JSON.stringify({ level: s.level, seed: s.seed, record: s.record });
      try {
        await navigator.clipboard.writeText(record);
        button.textContent = "Copied";
      } catch (e) {
        window.prompt("Copy this game record:", record);
      }
      setTimeout(() => (button.textContent = "Copy game record"), 2000);
    },
  });

  // ---- the celebrations -------------------------------------------------------
  //
  // At the end of a partie, one of them at random (the user: "in the real
  // game, when the game ends, the user will just see one of the ending
  // games/animations, randomly chosen"); when staging, all of them in turn.
  const hud = createHud(document.getElementById("overlay"), stage.camera, {
    staging: STAGING,
    onStep: (d) => {
      const names = celebrations.names;
      const i = names.indexOf(celebrations.playing());
      celebrations.play(names[(i + d + names.length) % names.length]);
    },
    onClose: () => celebrations.stop(),
  });
  const celebrations = createCelebrations({ stage, deck, hud, scenes: SCENES });
  function celebrate(name = STAGING ? celebrations.names[0] : celebrations.random()) {
    if (celebrations.playing()) return;
    celebrations.play(name, { from: director.meshes });
  }
  // Once the partie's last cards have landed and its result has been seen.
  // (Whoever won: it celebrates the partie, not the winner.) Only if the
  // partie is still over by then -- a new one may have begun meanwhile.
  function partieEnded() {
    const seed = engine.state().seed;
    director.timeline.idle().then(() =>
      setTimeout(() => {
        const s = engine.state();
        if (s.prompt.kind === "over" && s.seed === seed) celebrate();
      }, STAGING ? 900 : 2200));
  }

  function render() {
    const f = focused();
    const s = engine.state();
    const focus = f
      ? f.zone === "pack"
        ? `Cut here: lift ${Math.min(Math.max(f.index + 1, s.prompt.fewest), s.prompt.most)} cards (Space)`
        : `${labelOf(f.code)}${s.prompt.kind === "play" && !s.prompt.legal.includes(f.code) ? ", which you may not play" : ""} (Space to ${s.prompt.kind === "play" ? "play" : ui.selected.includes(f.code) ? "keep" : "throw"})`
      : null;
    overlay.render(s, { prefs, ui: { ...ui, busy: director.busy(), focusText: focus, tutorial: inTutorial(), faces: facesShown } });
    reframe();
    // In the tutorial, a phase you begin is introduced once the table is
    // still.
    if (inTutorial()) director.timeline.idle().then(introduce);
  }

  // The table is framed beside the information column, across the table;
  // on a phone the column runs along the top instead, and the table has the
  // whole width (framing.js).
  const info = document.getElementById("info");
  function reframe() {
    const beside = getComputedStyle(info).getPropertyValue("--beside").trim() === "1";
    if (stage.setInset(beside ? info.getBoundingClientRect().right + 8 : 0)) stage.render();
    measureStrips();
  }
  window.addEventListener("resize", reframe);

  // On a phone, the strips the overlay takes along the top and at the foot,
  // measured, and the table framed between them -- so it has all the room
  // the aids you have on leave it, and none of theirs (framing.js). What
  // each moment needs is remembered at its tallest, by the kind of question,
  // the aids on and the width: the table settles once into the room a phase
  // needs, rather than breathing with every line of the prompt.
  const tallest = new Map();
  let lastAids = null; // Explain and Hints as last measured
  const GAP = 6; // between a strip and the cards
  let measured = false;
  let measuring = 0;
  function measureStrips() {
    if (measuring) return;
    // After the overlay's buttons have drawn themselves.
    measuring = requestAnimationFrame(() => {
      measuring = 0;
      // A phone held sideways has the information down the left and the
      // controls down the right (style.css); the table goes between them.
      const sideways = getComputedStyle(info).getPropertyValue("--sideways").trim() === "1";
      if (!stage.portrait && !sideways) return;
      const s = engine.state();
      // The moment between rounds asks nothing: the foot then is the empty
      // prompt's, and counts for nothing -- but the top is measured, so an
      // aid switched then is answered then.
      const pausing = ui.withheld > 0;
      const box = (id) => {
        const n = document.getElementById(id);
        return n && !n.hidden && n.offsetParent && !n.classList.contains("floating") ? n.getBoundingClientRect() : null;
      };
      if (sideways) {
        const controls = box("controls");
        const right = controls && controls.width ? window.innerWidth - controls.left + GAP : 0;
        const key = `sideways|${s.prompt.kind}|${window.innerWidth}x${window.innerHeight}`;
        const was = tallest.get(key) ?? { top: GAP, foot: GAP, left: 0, right: 0 };
        const now = { top: GAP, foot: GAP, left: Math.max(was.left, info.getBoundingClientRect().right + GAP), right: Math.max(was.right, right), raised: raisable(s) };
        tallest.set(key, now);
        reframeTo(now);
        return;
      }
      // The explanation takes no room from the table: it lies over the
      // cards, and the table is framed as if it were not there -- nor what
      // it pushes down (the user: the explanation "smashes down the cards and
      // makes them too hard to read ... show me what it looks like if the
      // explanation popup is allowed to collide with the cards").
      const rule = box("rule");
      const under = rule ? rule.height + (parseFloat(getComputedStyle(info).rowGap) || 0) : 0;
      const worth = box("worth");
      const bottoms = [box("bug")?.bottom, worth && worth.bottom - under].filter((b) => typeof b === "number");
      const top = Math.max(0, ...bottoms) + GAP;
      const controls = box("controls");
      const foot = pausing ? 0 : controls && controls.height ? window.innerHeight - controls.top + GAP : STRIPS.foot;
      const aids = `${prefs.explain !== false}|${!!s.aids.hints}`;
      const key = `${s.prompt.kind}|${aids}|${window.innerWidth}`;
      const was = tallest.get(key) ?? { top: 0, foot: 0 };
      const now = { top: Math.max(was.top, top), foot: Math.max(was.foot, foot) || stage.strips().foot, raised: raisable(s) };
      tallest.set(key, now);
      // An aid you switched yourself is answered at once; what the game's
      // moves change waits for the table to be still (reframeTo).
      const asked = lastAids !== null && aids !== lastAids;
      lastAids = aids;
      reframeTo(now, { asked });
    });
  }
  // Room taken is given at once, so nothing is ever drawn under the
  // overlay; room given back waits until the table is still and has
  // finished speaking. The engine is in the play the moment your last
  // declaration is made, while the table is still saying the declarations,
  // and the eye moving then looked like a zoom in the middle of them (the
  // user: "at some point, the camera zoomed in during the declarations").
  let settling = null;
  // Whether your cards may be raised now -- chosen to throw, pointed at
  // while declaring -- for which the framing keeps room at the sides.
  const raisable = (s) => s.prompt.kind === "exchange" || s.prompt.kind === "declare";
  // Your hand's fan takes the width the framing leaves (framing.js): when
  // that changes, the hand spreads or gathers -- once the cards in motion
  // have landed, if any are moving.
  let refilling = false;
  function refill() {
    const next = stage.portrait ? stage.fill() : 1;
    if (Math.abs(next - fill) < 0.01) return;
    fill = next;
    if (refilling) return;
    refilling = true;
    const spread = () => {
      if (director.busy()) return void director.timeline.idle().then(() => setTimeout(spread, 0));
      refilling = false;
      director.rearrange();
    };
    spread();
  }
  function reframeTo(next, { asked = false } = {}) {
    clearTimeout(settling);
    const was = stage.strips();
    // Switched by you (the user: "when i turn off the explanations they
    // don't decompress" -- they did, once the table was still, which could
    // be eight seconds): the eye moves now.
    if (asked && measured && !TESTING) {
      stage.setStrips(next);
      refill();
      return;
    }
    if (TESTING || !measured) {
      measured = true;
      stage.setStrips(next, { instant: true });
      refill();
      return;
    }
    // Turned, the columns come or go at once.
    if ((was.left === undefined) !== (next.left === undefined)) {
      stage.setStrips(next, { instant: true });
      refill();
      return;
    }
    // Room for raised cards is room too: given back, in play, only once
    // the table is still.
    const sizes = Object.keys(next).filter((k) => k !== "raised");
    const taken = Object.fromEntries(sizes.map((k) => [k, Math.max(was[k] ?? 0, next[k])]));
    taken.raised = next.raised || (was.raised ?? 1) > 0;
    stage.setStrips(taken);
    refill();
    if (sizes.every((k) => taken[k] === next[k]) && taken.raised === next.raised) return;
    const settle = () => {
      if (director.busy() || overlay.talking()) settling = setTimeout(settle, 250);
      else {
        stage.setStrips(next);
        refill();
      }
    };
    settling = setTimeout(settle, 250);
  }
  // The overlay's buttons draw themselves a moment after it renders, and an
  // explanation opens and folds: measured again whenever the strips change.
  if (window.ResizeObserver) {
    const watch = new ResizeObserver(() => measureStrips());
    for (const id of ["bug", "rule", "worth", "controls", "info"]) watch.observe(document.getElementById(id));
  }

  // Carry out a command. The engine answers for your opponent on this
  // thread, so outside the tests the page first shows that they are thinking
  // and gives itself a frame to paint it.
  let pending = false;
  function act(command) {
    const move = !(command === "undo" || command.startsWith("set "));
    if (move && ui.withheld) return false; // not until the moment between rounds is over
    if (TESTING || !move) return carryOut(command);
    if (pending) return false;
    pending = true;
    if (director.busy()) director.skip();
    overlay.thinking();
    requestAnimationFrame(() =>
      setTimeout(() => {
        pending = false;
        carryOut(command);
      }, 0),
    );
    return true;
  }

  function carryOut(command) {
    if (director.busy()) director.skip();
    const cut = /^cut (\d+)$/.exec(command);
    if (cut) cutDepth = Number(cut[1]);
    const accepted = director.send(command);
    if (accepted) keep();
    render();
    return accepted;
  }

  function toggleAid(aid) {
    const aids = { ...engine.state().aids };
    aids[aid] = !aids[aid];
    store(AID_STORE, aids);
    act(`set ${aid} ${aids[aid] ? "on" : "off"}`);
  }

  function setPref(name, value) {
    prefs = { ...prefs, [name]: value };
    store(PREF_STORE, prefs);
    if (name === "speed") director.timeline.speed = value;
    if (name === "sort") director.rearrange();
    if (name === "faces") showFaces(value);
    if (name === "surface") {
      // Picking one lays it now, and for good; choosing Random keeps the
      // table in front of you until the page is next opened.
      if (value !== "random") stage.setSurface(value);
      stage.render();
    }
    render();
  }

  // ---- the tutorial ------------------------------------------------------------
  //
  // The user's four pages (web3d/tutorial.md): the introduction when the
  // tutorial begins, then each phase's page when it comes -- the exchange's
  // once the deal is decided (the user: "the second tutorial page should pop up
  // after the player decides if they are younger/elder"), the declarations'
  // and the tricks' before those phases. The ? brings them up at any time.
  // Each pops up once, at its moment, whether or not it was paged to before
  // (the user paged through them all, and then the exchange's never came).
  const PAGES = parseTutorial(TUTORIAL_TEXT);
  let tutorial = recall(TUTORIAL_STORE, { on: false, seed: null, seen: [] });
  let reading = false;
  const inTutorial = () => tutorial.on && tutorial.seed === engine.state().seed;
  function read(key, then) {
    reading = true;
    overlay.tutorial(PAGES, PAGE_KEYS.indexOf(key), {
      // In the tutorial the pages come by themselves; the introduction says so.
      popups: inTutorial(),
      done: () => {
        reading = false;
        (then ?? introduce)();
      },
    });
  }
  // In the tutorial, the phase's page the first time you act in it -- once
  // no other dialog is open (Settings, say, where it was just turned on).
  function introduce() {
    if (!inTutorial() || reading || ui.withheld || director.held() || director.busy() || document.querySelector("md-dialog[open]")) return;
    const key = pageDue(engine.state(), tutorial.seen);
    if (!key) return;
    // Popped up: done. Paging to a page does not count.
    tutorial = { ...tutorial, seen: [...tutorial.seen, key] };
    store(TUTORIAL_STORE, tutorial);
    read(key);
  }
  // A page held back by another dialog comes when that dialog closes.
  document.addEventListener("closed", (e) => e.target.id !== "tutorial" && setTimeout(introduce, 0), true);
  // The ? in the top bar, or the key: the page for this moment.
  function showTutorial() {
    if (!reading) read(pageFor(engine.state()));
  }
  // With the tutorial come hints and explanations; when it ends, the hints
  // go again if it was the tutorial that brought them.
  function tutorialOn(seen) {
    const seed = engine.state().seed;
    const brought = !engine.state().aids.hints;
    tutorial = { on: true, seed, seen, hints: brought || (tutorial.seed === seed && !!tutorial.hints) };
    store(TUTORIAL_STORE, tutorial);
    if (brought) toggleAid("hints");
    if (prefs.explain === false) setPref("explain", true);
  }
  function tutorialOff() {
    const brought = tutorial.on && tutorial.hints;
    tutorial = { ...tutorial, on: false, hints: false };
    store(TUTORIAL_STORE, tutorial);
    if (brought && engine.state().aids.hints) toggleAid("hints");
  }
  // The switch in Settings: this partie's pages on or off. Pages already
  // read stay read.
  function tutorialMode(on) {
    if (on) tutorialOn(tutorial.seed === engine.state().seed ? tutorial.seen : []);
    else tutorialOff();
    render();
  }
  function startTutorial() {
    newPartie(engine.state().level, true);
    tutorialOn(["intro"]);
    read("intro");
  }

  function newPartie(n, force = false) {
    const s = engine.state();
    const inProgress = s.prompt.kind !== "over" && s.record.some((r) => !r.startsWith("*"));
    if (inProgress && !force && !TESTING && !window.confirm(`Start a new partie against a level ${n} opponent? This one will be abandoned.`)) {
      render();
      return;
    }
    // A new partie ends any celebration of the last.
    if (celebrations.playing()) celebrations.stop();
    // A second partie has no tutorial (the user: "2nd partie has no more
    // tutorial popups").
    if (tutorial.on) tutorialOff();
    begin(n, randomSeed());
    hush();
    ui.selected = [];
    ui.lifted = [];
    director.restart();
    keep();
    render();
  }

  // ---- the table: pointing and clicking -----------------------------------------

  const canvas = stage.renderer.domElement;
  function target(hit, s = engine.state()) {
    if (!hit) return null;
    const kind = s.prompt.kind;
    if (kind === "cut" && hit.zone === "pack") return { kind: "cut", depth: Math.min(Math.max(hit.index + 1, s.prompt.fewest), s.prompt.most) };
    if ((kind === "exchange" || kind === "play") && hit.zone === "your-hand") return { kind, code: hit.code };
    // Your own discards, which the rules let you consult: pick them up to look.
    if (hit.zone === "your-discards") return { kind: "peek" };
    return null;
  }
  canvas.addEventListener("pointermove", (e) => {
    if (celebrations.playing()) return;
    if (director.busy()) return;
    const hit = director.pick(e.clientX, e.clientY);
    const t = target(hit);
    ui.focus = null;
    director.hover(t ? hit.id : null);
    canvas.style.cursor = t ? "pointer" : "";
  });
  canvas.addEventListener("pointerleave", () => director.hover(null));
  canvas.addEventListener("click", (e) => {
    if (celebrations.playing()) return;
    if (director.busy()) {
      director.skip(); // a click while the cards move: finish the move
      render();
      return;
    }
    use(target(director.pick(e.clientX, e.clientY)));
  });

  // What a card at the table does when clicked, or chosen from the keyboard.
  function use(t) {
    if (!t) return;
    if (t.kind === "cut") act(`cut ${t.depth}`);
    else if (t.kind === "play") act(`play ${t.code}`); // refused ones too: the engine says why
    else if (t.kind === "peek") {
      ui.peek = !ui.peek;
      director.rearrange();
    } else choose(t.code);
  }

  // The keyboard's own pointer: the arrows move it along whatever may be
  // chosen now -- your hand, or the spread when cutting -- in the order the
  // cards lie on the screen, and it looks exactly like pointing.
  function candidates() {
    const s = engine.state();
    return director
      .placement()
      .filter((m) => target(m, s))
      .filter((m) => m.zone !== "your-discards")
      .map((m) => ({ m, x: director.screenPoint(m.code, m.zone, m.index)?.x ?? 0 }))
      .sort((a, b) => a.x - b.x)
      .map(({ m }) => m);
  }
  function moveFocus(step) {
    const list = candidates();
    if (!list.length) return;
    const at = ui.focus !== null ? list.findIndex((m) => m.id === ui.focus) : -1; // card 0 is a card
    const next = at < 0 ? (step > 0 ? 0 : list.length - 1) : Math.min(list.length - 1, Math.max(0, at + step));
    ui.focus = list[next].id;
    director.hover(ui.focus);
    render();
  }
  function focused() {
    if (ui.focus === null) return null;
    const m = director.placement().find((x) => x.id === ui.focus);
    return m && target(m) ? m : null;
  }

  function choose(code) {
    const limit = engine.state().prompt.limit;
    if (ui.selected.includes(code)) ui.selected = ui.selected.filter((c) => c !== code);
    else if (ui.selected.length < limit) ui.selected = [...ui.selected, code];
    director.rearrange();
    render();
  }

  document.addEventListener("keydown", (e) => {
    // A celebration has the keys, all but Esc, which ends it.
    if (celebrations.playing()) {
      if (e.key === "Escape" && !document.querySelector("md-dialog[open]")) celebrations.stop();
      return;
    }
    if (["INPUT", "SELECT", "TEXTAREA", "MD-OUTLINED-SELECT"].includes(e.target.tagName) || e.altKey) return;
    if (document.querySelector("md-dialog[open]")) return;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      moveFocus(e.key === "ArrowRight" ? 1 : -1);
    } else if (e.key === " " && !director.busy() && focused()) {
      e.preventDefault();
      use(target(focused()));
    } else if (e.key === "Enter") {
      const primary = overlay.primary();
      if (primary) {
        e.preventDefault();
        primary.click();
      } else if (focused()) {
        e.preventDefault();
        use(target(focused()));
      }
    } else if (/^[1-9]$/.test(e.key) && !e.ctrlKey && !e.metaKey) {
      overlay.option(Number(e.key) - 1)?.click();
    } else if ((e.key === "u" || e.key === "U" || (e.key === "z" && (e.ctrlKey || e.metaKey))) && prefs.undo) {
      if (engine.state().can_undo) {
        e.preventDefault();
        act("undo");
      }
    } else if (e.key === "?") {
      e.preventDefault();
      showTutorial();
    } else if ((e.key === "h" || e.key === "H") && !e.ctrlKey && !e.metaKey) {
      toggleAid("hints");
    } else if ((e.key === "e" || e.key === "E") && !e.ctrlKey && !e.metaKey) {
      setPref("explain", prefs.explain === false);
    } else if (e.key === "Escape") {
      ui.selected = [];
      ui.lifted = [];
      ui.peek = false;
      ui.focus = null;
      director.hover(null);
      director.rearrange();
      render();
    } else if (e.key === " " && director.busy()) {
      e.preventDefault();
      director.skip();
      render();
    }
  });

  keep();
  render();
  await firstFrame();
  readyMs = performance.now();
  document.getElementById("loading").hidden = true;

  // On opening: the tutorial, a new game, or the partie under way.
  if ((!TESTING || params.has("welcome")) && !STAGING) {
    const s = engine.state();
    const underWay = s.prompt.kind !== "over" && s.record.some((r) => !r.startsWith("*"));
    overlay.welcome(underWay, (choice) => {
      if (choice === "tutorial") startTutorial();
      else if (choice === "new") newPartie(s.level, true);
      else introduce();
    });
  }

  // Test hooks: the browser test drives and inspects the table through these.
  window.piquet3d = {
    ...hooks,
    busy: () => director.busy(),
    state: () => engine.state(),
    send: (command) => act(command),
    // Where to click to hit a card: by its code, or the first of a zone.
    screenPoint: (code, zone, index) => director.screenPoint(code, zone, index),
    placement: () => director.placement().map(({ id, zone, index, code }) => ({ id, zone, index, code })),
    // With ?manual: move the animation clock by hand, for stills.
    tick: (ms) => director.tick(ms),
    // Whether the table is held still at a gate (a tutorial page at the
    // start of a phase).
    held: () => director.held(),
    // The celebrations: start one, which is playing, their names, and a
    // hand-driven clock for stills.
    celebrate: (name) => celebrate(name),
    celebration: () => celebrations.playing(),
    celebrations: () => celebrations.names,
    celebrationTick: (ms) => {
      celebrations.manual(true);
      celebrations.tick(ms);
    },
    // The tutorial, if this partie is one.
    tutorial: () => ({ ...tutorial, on: inTutorial() }),
    // What the cards' shadows add to the frame as it stands: drawn with them
    // and without, read straight from the drawing buffer, the pixels that
    // differ counted.
    shadowPixels: () => {
      const gl = stage.renderer.getContext();
      const { drawingBufferWidth: w, drawingBufferHeight: h } = gl;
      const read = (on) => {
        // Soft (VSM) shadows are cast by every receiver too, so both go.
        for (const mesh of director.meshes) mesh.castShadow = mesh.receiveShadow = on;
        stage.render();
        const px = new Uint8Array(w * h * 4);
        gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
        return px;
      };
      const lit = read(true);
      const bare = read(false);
      read(true);
      let n = 0;
      for (let i = 0; i < lit.length; i += 4) if (Math.abs(lit[i] - bare[i]) + Math.abs(lit[i + 1] - bare[i + 1]) + Math.abs(lit[i + 2] - bare[i + 2]) > 12) n += 1;
      return n;
    },
    // The heights the phone's table is framed between, as last measured
    // (framing.js).
    strips: () => stage.strips(),
  };
}

// Ready means the first frame has reached the screen, which is later than
// render() returning: a browser may defer rasterising an SVG drawn to a
// canvas until the canvas is uploaded, and the page stalls until it is.
const firstFrame = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

main().catch((e) => {
  const note = document.getElementById("loading");
  note.hidden = false;
  note.textContent = `The table failed to load: ${String(e)}`;
  note.classList.add("error");
  throw e;
});
