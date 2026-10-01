// The director: the engine's states, choreographed, played out on the cards.
//
// It holds the 32 card meshes and where each one is; hands every change of
// state -- or of how the human asks to see it -- to the choreography; runs
// the motions on the timeline, turning faces up and down as they begin and
// land; decorates the cards (a card pointed at rises and takes a heavier ink
// line, a hinted card a cyan one, a card chosen to throw an amber one, a card
// that may not be played is dimmed); and renders only while something moves,
// so a table at rest costs nothing (docs/TABLE3D.md section 5.4).

import { cardCorners } from "./kinematics.js";
import { Raycaster, Vector2, Vector3 } from "three";
import { choreograph, initialPlacement } from "./choreography.js";
import { Timeline } from "./timeline.js";
import { CARD } from "./units.js";

const HOVER_LIFT = 0.9; // cm: a card in the hand pointed at rises this much
const PACKET_LIFT = 0.35; // cm: the packet you would lift when cutting
const EASE_MS = 90; // how quickly a lift follows the pointer

// `settled(prev, next)`, if given, runs after the engine has answered and
// before the change is choreographed: the moment for the app to update what
// the view shows (cards just drawn, say), so the animation lands on it.
// `pace(prev, next, dry)`, if given, runs before the change is choreographed,
// and may hold events back: it returns { waits: { eventIndex: ms from now } }
// (and whatever else it likes, handed on to `timed`), and may first try waits
// out with `dry(waits)` -> { beats, duration }, which animates nothing.
// `timed(prev, next, beats, paced)`, if given, runs once it is choreographed,
// with when each new event will be seen to happen, in ms from now -- for the
// dialogue -- and what `pace` returned.
export function createDirector({ stage, deck, engine, view, settled, pace, timed, testing = false, manual = false, speed = 1 }) {
  const meshes = Array.from({ length: 32 }, () => deck.card(null));
  meshes.forEach((mesh, id) => (mesh.userData.id = id));
  let state = engine.state();
  let placement = [];
  const base = meshes.map(() => null); // each card's pose before decoration
  const lift = new Float32Array(32);
  const liftGoal = new Float32Array(32);
  let hovered = null;

  function show(id) {
    const mesh = meshes[id];
    const pose = base[id];
    mesh.quaternion.copy(pose.quaternion);
    mesh.position.copy(pose.position);
    if (lift[id]) {
      const onTable = placement[id] && placement[id].zone === "pack";
      const up = onTable ? new Vector3(0, 1, 0) : new Vector3(0, 1, 0).applyQuaternion(pose.quaternion);
      mesh.position.addScaledVector(up, lift[id]);
    }
  }
  const timeline = new Timeline({
    apply: (id, pose) => {
      base[id] = pose;
      show(id);
    },
    speed,
  });

  // ---- decoration ---------------------------------------------------------

  function decorate() {
    const kind = state.prompt.kind;
    const v = view();
    const hinted = new Set(state.hint && state.aids.hints ? state.hint.cards : []);
    const chosen = new Set(v.selected);
    const legal = kind === "play" ? new Set(state.prompt.legal) : null;
    const hoveredSlot = hovered === null ? null : placement[hovered];
    for (const m of placement) {
      const mesh = meshes[m.id];
      let line = "plain";
      let dim = false;
      let goal = 0;
      if (m.zone === "your-hand" && !timeline.busy()) {
        if (chosen.has(m.code)) line = "chosen";
        else if (hinted.has(m.code)) line = "hint";
        else if (hovered === m.id && (kind === "exchange" || kind === "play")) line = "hover";
        if (legal && !legal.has(m.code)) dim = true;
        if (hovered === m.id && (kind === "exchange" || kind === "play") && !chosen.has(m.code)) goal = HOVER_LIFT;
      }
      // Your discards, pointed at: a heavier line says you may pick them up.
      if (m.zone === "your-discards" && hoveredSlot && hoveredSlot.zone === "your-discards" && !timeline.busy()) line = "hover";
      if (kind === "cut" && m.zone === "pack" && hoveredSlot && hoveredSlot.zone === "pack" && m.index <= hoveredSlot.index) {
        goal = PACKET_LIFT; // the packet you would lift
      }
      deck.decorate(mesh, { line, dim });
      liftGoal[m.id] = goal;
    }
  }

  // Lifts ease towards their goals; true while any is still on its way.
  let lastFrame = null;
  function easeLifts(now) {
    const dt = lastFrame === null ? 16 : Math.min(64, now - lastFrame);
    lastFrame = now;
    const k = testing ? 1 : 1 - Math.exp(-dt / EASE_MS);
    let moving = false;
    for (let id = 0; id < 32; id++) {
      const gap = liftGoal[id] - lift[id];
      if (Math.abs(gap) < 1e-3) {
        if (lift[id] !== liftGoal[id]) {
          lift[id] = liftGoal[id];
          show(id);
        }
        continue;
      }
      lift[id] += gap * k;
      show(id);
      moving = true;
    }
    return moving;
  }

  // ---- the clock ----------------------------------------------------------

  // The table's clock can stop: at a gate -- a tutorial page at the start of
  // a phase (the user: "the pop ups pop up at the beginning of each of the
  // phases") -- the cards hold still until the gate is released, and then
  // carry on from where they were. Held time is taken off the clock, so
  // everything scheduled on it (the dialogue's boxes too, through `at`)
  // simply waits. Each entry is { at, gate, fn }: at a gate the clock stops
  // and `fn(release)` is called; otherwise `fn()` runs when its time comes.
  let manualNow = 0;
  const wall = () => (manual ? manualNow : performance.now());
  let offset = 0; // ms the clock has been held, in all
  let heldAt = null; // the clock's reading while it is held
  const queue = [];
  const now = () => heldAt ?? wall() - offset;
  let running = false;
  function schedule(entry) {
    queue.push(entry);
    queue.sort((a, b) => a.at - b.at || b.gate - a.gate);
    wake();
  }
  function release() {
    if (heldAt === null) return;
    offset = wall() - heldAt;
    heldAt = null;
    wake();
  }
  // Run what is due by `until`, in order; stop at a gate and hold there.
  function due(until) {
    while (queue.length && queue[0].at <= until && heldAt === null) {
      const entry = queue.shift();
      if (entry.gate) {
        heldAt = entry.at;
        timeline.tick(entry.at);
        stage.render();
        entry.fn(release);
        return true;
      }
      entry.fn();
    }
    return heldAt !== null;
  }
  function frame() {
    if (heldAt === null) {
      const held = due(now());
      if (!held) {
        const t = now();
        const busy = timeline.tick(t);
        const easing = easeLifts(t);
        stage.render();
        if ((busy || easing || queue.length) && !manual) {
          requestAnimationFrame(frame);
          return;
        }
      }
    }
    running = false;
    lastFrame = null;
  }
  function wake() {
    if (manual) return frame();
    if (running) return;
    running = true;
    requestAnimationFrame(frame);
  }

  function settle(s) {
    timeline.skip();
    placement = initialPlacement(s, view());
    for (const m of placement) {
      deck.reveal(meshes[m.id], m.code);
      base[m.id] = m.pose;
      lift[m.id] = 0;
      show(m.id);
    }
    decorate();
    stage.render();
  }

  // The change choreographed from where the cards lie now, its waits given in
  // ms of the table's clock; and each event's moment, as the timeline will
  // play it: at its speed, or at once when nothing is animated.
  function plan(prev, next, waits = {}) {
    const scaled = Object.fromEntries(Object.entries(waits).map(([k, ms]) => [k, ms * timeline.speed]));
    const result = choreograph(prev, next, placement, view(), { pause: view().pause !== false, waits: scaled });
    const beats = {};
    for (const [k, ms] of Object.entries(result.beats)) beats[k] = testing ? 0 : ms / timeline.speed;
    return { result, beats, duration: testing ? 0 : result.duration / timeline.speed };
  }

  function animate(prev, next, waits) {
    timeline.skip(); // anything still moving lands first
    const { result, beats } = plan(prev, next, waits);
    placement = result.placement;
    const start = now();
    for (const m of result.motions) {
      const mesh = meshes[m.id];
      const reveal = m.reveal;
      timeline.add(
        {
          target: m.id,
          path: m.path,
          delay: m.delay,
          duration: m.duration,
          onStart: reveal && !reveal.atEnd ? () => deck.reveal(mesh, reveal.code) : undefined,
          onDone: reveal && reveal.atEnd ? () => deck.reveal(mesh, reveal.code) : undefined,
        },
        start,
      );
    }
    timeline.idle().then(() => {
      decorate();
      wake();
    });
    decorate();
    if (testing) timeline.skip();
    if (testing || manual) frame();
    else wake();
    return beats;
  }

  settle(state);

  // ---- picking ------------------------------------------------------------

  const raycaster = new Raycaster();
  const pointer = new Vector2();
  // The card under a point on the canvas, as its place at the table.
  function pick(clientX, clientY) {
    const rect = stage.renderer.domElement.getBoundingClientRect();
    pointer.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(pointer, stage.camera);
    const [hit] = raycaster.intersectObjects(meshes, false);
    return hit ? placement[hit.object.userData.id] : null;
  }

  // Where on the screen to point at a card so that it is the one hit: near
  // its left edge, which every fan and every row leaves showing. By its
  // code, or by its place: a zone and an index in it.
  function screenPoint(code, zone, index = 0) {
    const m = placement.find((x) => (code ? x.code === code : x.zone === zone && x.index === index));
    if (!m) return null;
    const mesh = meshes[m.id];
    const local = new Vector3(-CARD.width / 2 + 0.55, CARD.height / 2 - 1.6, CARD.thickness / 2);
    const p = local.applyQuaternion(mesh.quaternion).add(mesh.position).project(stage.camera);
    const rect = stage.renderer.domElement.getBoundingClientRect();
    return { x: rect.left + ((p.x + 1) / 2) * rect.width, y: rect.top + ((1 - p.y) / 2) * rect.height };
  }

  // Where to speak from, on the screen: just above your hand's top edge, or
  // just below your opponent's lowest -- near the middle of the table, where
  // the eye already is, never over a card (the user). From the cards as they
  // lie now; before anyone holds any, from where the hand would be.
  function handEdge(who) {
    const zone = who === "you" ? "your-hand" : "their-hand";
    const rect = stage.renderer.domElement.getBoundingClientRect();
    const toScreen = (p) => {
      const q = p.clone().project(stage.camera);
      return { x: rect.left + ((q.x + 1) / 2) * rect.width, y: rect.top + ((1 - q.y) / 2) * rect.height };
    };
    const points = placement
      .filter((m) => m.zone === zone)
      .flatMap((m) => cardCorners({ position: meshes[m.id].position, quaternion: meshes[m.id].quaternion }).map(toScreen));
    if (!points.length) {
      const zones = view().zones;
      const centre = zones[who === "you" ? "yourHand" : "theirHand"].centre;
      const at = toScreen(new Vector3(...centre));
      return { x: at.x, y: at.y, empty: true };
    }
    const x = points.reduce((sum, p) => sum + p.x, 0) / points.length;
    const y = who === "you" ? Math.min(...points.map((p) => p.y)) : Math.max(...points.map((p) => p.y));
    return { x, y };
  }

  return {
    handEdge,
    state: () => state,
    placement: () => placement,
    busy: () => timeline.busy(),
    // Carry out a command, and animate whatever it set in motion.
    // Hold the table at `ms` from now on its clock: the cards stop, and
    // `open(release)` is called; they carry on when it calls release.
    gate(ms, open) {
      schedule({ at: now() + ms, gate: true, fn: open });
    },
    // Run `fn` at `ms` from now on the table's clock, which a gate stops.
    at(ms, fn) {
      schedule({ at: now() + ms, gate: false, fn });
    },
    held: () => heldAt !== null,
    // The table's clock, in ms: it stands still while the table is held.
    clock: () => now(),
    send(command) {
      const prev = state;
      const accepted = engine.send(command);
      state = engine.state();
      if (accepted) {
        settled?.(prev, state);
        const paced = pace?.(prev, state, (waits) => {
          const { beats, duration } = plan(prev, state, waits);
          return { beats, duration };
        }) ?? {};
        const beats = animate(prev, state, paced.waits);
        timed?.(prev, state, beats, paced);
      }
      else {
        decorate();
        wake();
      }
      return accepted;
    },
    // The same state seen differently: a new sort, a card chosen or pointed at.
    rearrange() {
      if (timeline.busy()) return;
      animate(state, state);
    },
    // Point at a card, or at nothing.
    hover(id) {
      if (id === hovered) return;
      hovered = id;
      decorate();
      wake();
    },
    // An undo, a new partie: what was timed to the moves is over.
    cancelTimed() {
      queue.length = 0;
      release();
    },
    // A new partie, or a game restored: straight onto the table.
    restart() {
      state = engine.state();
      settle(state);
    },
    skip() {
      timeline.skip();
      // What was timed to the moves comes now too -- up to a gate, if any.
      due(Infinity);
      decorate();
      wake();
    },
    // For stills: move the hand-driven clock and draw.
    tick(ms) {
      manualNow += ms;
      frame();
    },
    pick,
    screenPoint,
    meshes,
    timeline,
  };
}
