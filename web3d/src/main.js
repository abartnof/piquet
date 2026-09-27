// Piquet at a three-dimensional table.
//
// A client of the table protocol (docs/PROTOCOL.md): it draws the engine's
// state and sends back commands, and holds no rules. The plan is
// docs/TABLE3D.md.

import { loadTextures } from "./art.js";
import { createDeck, place } from "./deck.js";
import { buildDemo } from "./demo.js";
import { decodeBase64, loadEngine } from "./engine.js";
import { layout } from "./layout.js";
import { createScene } from "./scene.js";
import { buildSpike } from "./spike.js";

/* global WASM_BASE64, ART */

const params = new URL(window.location.href).searchParams;
const TESTING = params.has("test");

async function main() {
  if (TESTING) document.body.classList.add("testing");
  const engine = await loadEngine(decodeBase64(WASM_BASE64));
  engine.start(Number(params.get("level") || 3), Number(params.get("seed") || 1));

  const numbers = (name) => (params.get(name) ? params.get(name).split(",").map(Number) : undefined);
  const stage = createScene(document.getElementById("stage"), {
    surface: params.get("surface") || "sky",
    shadow: params.get("shadow") || "vsm",
    eye: numbers("eye"),
    at: numbers("at"),
    fov: numbers("fov") ? numbers("fov")[0] : undefined,
  });
  const textures = await loadTextures(ART, {
    anisotropy: stage.renderer.capabilities.getMaxAnisotropy(),
    pixelRatio: stage.renderer.getPixelRatio(),
  });
  const deck = createDeck(stage, textures, { inkWidth: Number(params.get("ink") || 2.5) });
  const demo = params.has("demo") ? buildDemo(stage, deck, { slow: Number(params.get("slow") || 1) }) : null;
  if (params.has("spike") || params.has("angles")) buildSpike(stage, deck, { angles: params.has("angles") });

  // The table at rest: all 32 cards where the state puts them. (Until the
  // choreography lands, a new state simply appears.)
  const table = params.has("spike") || params.has("angles") || demo ? null : Array.from({ length: 32 }, () => deck.card(null));
  const show = () => {
    if (!table) return;
    layout(engine.state(), { eye: stage.camera.position }).forEach((slot, i) => {
      deck.reveal(table[i], slot.code);
      place(table[i], slot.pose);
    });
    stage.render();
  };
  show();
  stage.render();
  // Ready means the first frame has reached the screen, which is later than
  // render() returning: a browser may defer rasterising an SVG drawn to a
  // canvas until the canvas is uploaded, and the page stalls until it is.
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const readyMs = performance.now();
  document.getElementById("loading").hidden = true;
  if (demo && !TESTING) demo.play();

  // Test hooks: the browser test drives and inspects the table through these.
  window.piquet3d = {
    ready: () => stage.frames() > 0,
    busy: () => false,
    state: () => engine.state(),
    send: (command) => {
      const accepted = engine.send(command);
      show();
      return accepted;
    },
    // The motion demo, frozen at one moment for all its stations.
    demoAt: (t) => demo && demo.at(t),
    art: () => ({
      vector: textures.vector,
      width: textures.width,
      ms: Math.round(textures.ms),
      readyMs: Math.round(readyMs),
    }),
  };
}

main().catch((e) => {
  const note = document.getElementById("loading");
  note.hidden = false;
  note.textContent = `The table failed to load: ${String(e)}`;
  note.classList.add("error");
  throw e;
});
