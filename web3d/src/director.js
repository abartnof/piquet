// The director: the engine's states, choreographed, played out on the cards.
//
// It holds the 32 card meshes and where each one is; hands every change of
// state -- or of how the human asks to see it -- to the choreography; runs
// the motions on the timeline, turning faces up and down as they begin and
// land; and renders only while something moves, so a table at rest costs
// nothing (docs/TABLE3D.md section 5.4).

import { choreograph, initialPlacement } from "./choreography.js";
import { place } from "./deck.js";
import { Timeline } from "./timeline.js";

export function createDirector({ stage, deck, engine, view, testing = false, manual = false, speed = 1 }) {
  const meshes = Array.from({ length: 32 }, () => deck.card(null));
  let state = engine.state();
  let placement = [];
  const timeline = new Timeline({ apply: (id, pose) => place(meshes[id], pose), speed });

  function settle(s) {
    timeline.skip();
    placement = initialPlacement(s, view());
    for (const m of placement) {
      deck.reveal(meshes[m.id], m.code);
      place(meshes[m.id], m.pose);
    }
    stage.render();
  }

  // The clock: the browser's, or -- for a strip of stills -- one moved by hand.
  let manualNow = 0;
  const now = () => (manual ? manualNow : performance.now());
  let running = false;
  function frame() {
    const busy = timeline.tick(now());
    stage.render();
    if (busy && !manual) requestAnimationFrame(frame);
    else running = false;
  }
  function wake() {
    if (manual || running) return;
    running = true;
    requestAnimationFrame(frame);
  }

  function animate(prev, next) {
    timeline.skip(); // anything still moving lands first
    const result = choreograph(prev, next, placement, view());
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
    if (testing) timeline.skip();
    if (testing || manual) frame();
    else wake();
  }

  settle(state);

  return {
    state: () => state,
    busy: () => timeline.busy(),
    // Carry out a command, and animate whatever it set in motion.
    send(command) {
      const prev = state;
      const accepted = engine.send(command);
      state = engine.state();
      if (accepted) animate(prev, state);
      return accepted;
    },
    // The same state seen differently: a new sort, a card chosen or pointed at.
    rearrange() {
      animate(state, state);
    },
    // A new partie, or a game restored: straight onto the table.
    restart() {
      state = engine.state();
      settle(state);
    },
    skip() {
      timeline.skip();
      frame();
    },
    // For stills: move the hand-driven clock and draw.
    tick(ms) {
      manualNow += ms;
      frame();
    },
    meshes,
    timeline,
  };
}
