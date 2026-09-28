// Piquet at a three-dimensional table.
//
// A client of the table protocol (docs/PROTOCOL.md): it draws the engine's
// state and sends back commands, and holds no rules. The plan is
// docs/TABLE3D.md. This file is the app: it boots the engine, the scene and
// the overlay; keeps the player's preferences, aids and game; and turns
// clicks and keys into commands.

import { loadTextures } from "./art.js";
import { createDeck } from "./deck.js";
import { buildDemo } from "./demo.js";
import { createDirector } from "./director.js";
import { decodeBase64, loadEngine } from "./engine.js";
import { STRIPS } from "./framing.js";
import { createOverlay, label as labelOf } from "./overlay.js";
import { speech } from "./speech.js";
import { chooseSurface } from "./surfaces.js";
import { createVoice } from "./voice.js";
import { createScene } from "./scene.js";
import { buildSpike } from "./spike.js";
import { ZONES, ZONES_PORTRAIT } from "./units.js";

/* global WASM_BASE64, ART, VOICES */

const params = new URL(window.location.href).searchParams;
const TESTING = params.has("test");

const GAME_STORE = "piquet3d.game";
// Versioned: your own calls became opt-in (Andrew: "by default, the
// opponent's voice should be on, and the user's voice should be off"). A
// stored set from before keeps every other choice, but not that one.
const PREF_STORE = "piquet3d.prefs.2";
const OLD_PREF_STORE = "piquet3d.prefs";
// Versioned: "play my winners" became opt-in, and a stored set from before
// would keep it on without the player ever having chosen it.
const AID_STORE = "piquet3d.aids.2";
const DEFAULT_PREFS = {
  tab: true, undo: true, pause: true, sort: "auto", speed: 1, explain: true, surface: "random",
  // The voice (docs/VOICE.md): your opponent's on, in a woman's voice;
  // yours off until you want it, and then in the other.
  voice: true, opponentVoice: "cori", sayMine: false,
};
// Playing out your winners is opt-in: Andrew, finding his cards played for
// him mid-trick, "i didn't intend for that to happen".
const DEFAULT_AIDS = { hints: true, play_forced: true, play_winners: false, declare_for_me: false };

function recall(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value === null ? fallback : { ...fallback, ...value };
  } catch (e) {
    return fallback;
  }
}

// The settings as stored, or as they were stored before the store was
// versioned, less your own calls.
function recallPrefs(defaults) {
  if (recall(PREF_STORE, null)) return recall(PREF_STORE, defaults);
  const older = recall(OLD_PREF_STORE, null);
  if (!older) return defaults;
  const { sayMine, ...kept } = older;
  return { ...defaults, ...kept };
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
    // the page opens -- kept while it is open, new parties and all (Andrew:
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
  const textures = await loadTextures(ART, {
    anisotropy: Number(params.get("aniso")) || stage.renderer.capabilities.getMaxAnisotropy(),
    pixelRatio: stage.renderer.getPixelRatio(),
  });
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
    art: () => ({ vector: textures.vector, width: textures.width, ms: Math.round(textures.ms), readyMs: Math.round(readyMs) }),
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
  const ui = { selected: [], lifted: [], pinned: null, pinnedCards: [], fresh: [], peek: false, focus: null };
  let cutDepth = 16;
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
  });

  // ---- the game: started, kept, restored -------------------------------------

  const applyAids = (aids) => {
    for (const [aid, on] of Object.entries(aids)) engine.send(`set ${aid} ${on ? "on" : "off"}`);
  };
  function begin(level, seed) {
    engine.start(level, seed);
    applyAids(recall(AID_STORE, DEFAULT_AIDS));
  }
  function restore(saved) {
    engine.start(saved.level, saved.seed);
    const payload = [`replay ${saved.level} ${saved.seed}`, ...(saved.record || [])].join("\n");
    if (!engine.send(payload)) begin(saved.level, saved.seed); // a record from an older engine
    applyAids(recall(AID_STORE, DEFAULT_AIDS));
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

  // After every accepted move, before it is animated: choices clear, and what
  // the talon gave you stands proud until the play begins.
  function settled(prev, next) {
    ui.selected = [];
    ui.lifted = [];
    ui.pinned = null;
    ui.pinnedCards = [];
    ui.peek = false; // any move puts your discards back down
    const drew = next.events.slice(prev.events.length).find((e) => e.kind === "drew");
    if (drew) ui.fresh = drew.drew;
    if (["play", "complete", "cut"].includes(next.phase) || next.events.length < prev.events.length) ui.fresh = [];
    // What was said, said aloud -- only what is new; an undo falls silent.
    if (next.events.length < prev.events.length) voice.stop();
    else if (!TESTING || params.has("voice")) {
      const deals = new Set(next.events.slice(prev.events.length).map((e) => e.deal));
      const lines = [...deals].flatMap((deal) => speech(next.events, deal, prev.events.length));
      voice.say(lines, prefs);
    }
  }

  const voices = typeof VOICES === "object" ? VOICES : {};
  const voice = createVoice(voices);
  const director = createDirector({
    stage,
    deck,
    engine,
    view,
    settled,
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

  function render() {
    const f = focused();
    const s = engine.state();
    const focus = f
      ? f.zone === "pack"
        ? `Cut here: lift ${Math.min(Math.max(f.index + 1, s.prompt.fewest), s.prompt.most)} cards (Space)`
        : `${labelOf(f.code)}${s.prompt.kind === "play" && !s.prompt.legal.includes(f.code) ? ", which you may not play" : ""} (Space to ${s.prompt.kind === "play" ? "play" : ui.selected.includes(f.code) ? "keep" : "throw"})`
      : null;
    overlay.render(s, { prefs, ui: { ...ui, busy: director.busy(), focusText: focus } });
    reframe();
  }

  // The table is framed beside the information column, across the table;
  // on a phone the column runs along the top instead, and the table has the
  // whole width (framing.js).
  const info = document.getElementById("info");
  function reframe() {
    const beside = getComputedStyle(info).getPropertyValue("--beside").trim() === "1";
    if (stage.setInset(beside ? info.getBoundingClientRect().right + 8 : 0)) stage.render();
  }
  window.addEventListener("resize", reframe);

  // Carry out a command. The engine answers for your opponent on this
  // thread, so outside the tests the page first shows that they are thinking
  // and gives itself a frame to paint it.
  let pending = false;
  function act(command) {
    if (TESTING || command === "undo" || command.startsWith("set ")) return carryOut(command);
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
    if (name === "voice" && !value) voice.stop();
    if (name === "surface") {
      // Picking one lays it now, and for good; choosing Random keeps the
      // table in front of you until the page is next opened.
      if (value !== "random") stage.setSurface(value);
      stage.render();
    }
    render();
  }

  function newPartie(n, force = false) {
    const s = engine.state();
    const inProgress = s.prompt.kind !== "over" && s.record.some((r) => !r.startsWith("*"));
    if (inProgress && !force && !TESTING && !window.confirm(`Start a new partie against a level ${n} opponent? This one will be abandoned.`)) {
      render();
      return;
    }
    begin(n, randomSeed());
    voice.stop();
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
    if (director.busy()) return;
    const hit = director.pick(e.clientX, e.clientY);
    const t = target(hit);
    ui.focus = null;
    director.hover(t ? hit.id : null);
    canvas.style.cursor = t ? "pointer" : "";
  });
  canvas.addEventListener("pointerleave", () => director.hover(null));
  canvas.addEventListener("click", (e) => {
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
    // With ?voice (speech is off in tests otherwise): what the voice did.
    voice: () => voice.stats(),
    // The heights the phone's table is framed between (framing.js).
    strips: () => STRIPS,
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
