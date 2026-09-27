// The director: the engine's states, choreographed, played out on the cards.
//
// It holds the 32 card meshes and where each one is; hands every change of
// state -- or of how the human asks to see it -- to the choreography; runs
// the motions on the timeline, turning faces up and down as they begin and
// land; decorates the cards (a card pointed at rises and takes a heavier ink
// line, a hinted card a cyan one, a card chosen to throw an amber one, a card
// that may not be played is dimmed); and renders only while something moves,
// so a table at rest costs nothing (docs/TABLE3D.md section 5.4).

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
export function createDirector({ stage, deck, engine, view, settled, testing = false, manual = false, speed = 1 }) {
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

  let manualNow = 0;
  const now = () => (manual ? manualNow : performance.now());
  let running = false;
  function frame() {
    const t = now();
    const busy = timeline.tick(t);
    const easing = easeLifts(t);
    stage.render();
    if ((busy || easing) && !manual) requestAnimationFrame(frame);
    else {
      running = false;
      lastFrame = null;
    }
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

  function animate(prev, next) {
    timeline.skip(); // anything still moving lands first
    const result = choreograph(prev, next, placement, view(), { pause: view().pause !== false });
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

  return {
    state: () => state,
    placement: () => placement,
    busy: () => timeline.busy(),
    // Carry out a command, and animate whatever it set in motion.
    send(command) {
      const prev = state;
      const accepted = engine.send(command);
      state = engine.state();
      if (accepted) {
        settled?.(prev, state);
        animate(prev, state);
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
    // A new partie, or a game restored: straight onto the table.
    restart() {
      state = engine.state();
      settle(state);
    },
    skip() {
      timeline.skip();
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
