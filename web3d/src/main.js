// Piquet at a three-dimensional table.
//
// A client of the table protocol (docs/PROTOCOL.md): it draws the engine's
// state and sends back commands, and holds no rules. The plan is
// docs/TABLE3D.md.

import { loadTextures } from "./art.js";
import { decodeBase64, loadEngine } from "./engine.js";
import { createScene } from "./scene.js";
import { buildSpike } from "./spike.js";

/* global WASM_BASE64, ART */

const params = new URL(window.location.href).searchParams;
const TESTING = params.has("test");

async function main() {
  if (TESTING) document.body.classList.add("testing");
  const engine = await loadEngine(decodeBase64(WASM_BASE64));
  engine.start(3, 1);

  const numbers = (name) => (params.get(name) ? params.get(name).split(",").map(Number) : undefined);
  const stage = createScene(document.getElementById("stage"), {
    surface: params.get("surface") || "sky",
    shadow: params.get("shadow") || "vsm",
    eye: numbers("eye"),
    at: numbers("at"),
    fov: numbers("fov") ? numbers("fov")[0] : undefined,
  });
  const textures = await loadTextures(ART, stage.renderer.capabilities.getMaxAnisotropy());
  buildSpike(stage, textures, { inkWidth: Number(params.get("ink") || 2.5), angles: params.has("angles") });
  stage.render();
  document.getElementById("loading").hidden = true;

  // Test hooks: the browser test drives and inspects the table through these.
  window.piquet3d = {
    ready: () => stage.frames() > 0,
    busy: () => false,
    state: () => engine.state(),
  };
}

main().catch((e) => {
  const note = document.getElementById("loading");
  note.hidden = false;
  note.textContent = `The table failed to load: ${String(e)}`;
  note.classList.add("error");
  throw e;
});
