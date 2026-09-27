// Piquet at a three-dimensional table.
//
// A client of the table protocol (docs/PROTOCOL.md): it draws the engine's
// state and sends back commands, and holds no rules. The plan is
// docs/TABLE3D.md.

import { decodeBase64, loadEngine } from "./engine.js";
import { createScene } from "./scene.js";

/* global WASM_BASE64 */

const TESTING = new URL(window.location.href).searchParams.has("test");

async function main() {
  if (TESTING) document.body.classList.add("testing");
  const engine = await loadEngine(decodeBase64(WASM_BASE64));
  engine.start(3, 1);

  const stage = createScene(document.getElementById("stage"));
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
