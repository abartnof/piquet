// The cards as scene objects: one mesh per card, its ink line, and which face
// it shows.
//
// A card's face is assigned only when the human may know it (docs/TABLE3D.md
// section 5.1): until then it shows the back on both sides, so nothing in the
// scene can reveal a card the human could not see at a real table.

import { Mesh } from "three";
import { cardGeometry } from "./cards.js";
import { cardMaterials, inkMaterial, RAMPS } from "./materials.js";

export function createDeck(stage, textures, { inkWidth = 2.5 } = {}) {
  const geometry = cardGeometry();
  const ramp = RAMPS.card();
  const ink = inkMaterial({ width: inkWidth });
  stage.registerInk(ink);
  const unknown = cardMaterials({ face: textures.back, back: textures.back, ramp });
  const known = {};
  for (const [code, face] of Object.entries(textures.faces)) {
    known[code] = cardMaterials({ face, back: textures.back, ramp });
  }

  function card(code = null) {
    const mesh = new Mesh(geometry, code ? known[code] : unknown);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.add(new Mesh(geometry, ink));
    mesh.userData.code = code;
    stage.scene.add(mesh);
    return mesh;
  }

  // Show this card's face -- or, with null, hide it again.
  function reveal(mesh, code) {
    mesh.material = code ? known[code] : unknown;
    mesh.userData.code = code;
  }

  return { card, reveal, geometry, ink };
}

export function place(mesh, pose) {
  mesh.position.copy(pose.position);
  mesh.quaternion.copy(pose.quaternion);
}
