// The cards as scene objects: one mesh per card, its ink line, and which face
// it shows.
//
// A card's face is assigned only when the human may know it (docs/TABLE3D.md
// section 5.1): until then it shows the back on both sides, so nothing in the
// scene can reveal a card the human could not see at a real table.

import { Mesh } from "three";
import { cardGeometry } from "./cards.js";
import { cardMaterials, INK, inkMaterial, RAMPS } from "./materials.js";

// The ink line is also the selection language (docs/TABLE3D.md section
// 8.2), which keeps the table free of glows and badges: a card pointed at
// takes a heavier line, a hinted one a cyan line, one chosen to throw an
// amber one.
export const INKS = {
  plain: { color: INK },
  hover: { color: INK, heavier: 1.5 },
  hint: { color: "#009fb7", heavier: 1.6 },
  chosen: { color: "#e8900c", heavier: 1.6 },
};

export function createDeck(stage, textures, { inkWidth = 2.5 } = {}) {
  const geometry = cardGeometry();
  const ramp = RAMPS.card();
  const inks = {};
  for (const [name, { color, heavier = 1 }] of Object.entries(INKS)) {
    inks[name] = inkMaterial({ color, width: inkWidth * heavier });
    stage.registerInk(inks[name]);
  }
  const ink = inks.plain;
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

  // Change every face's art -- to the Jumbo Index faces, or back to the
  // classic ones (faces.js) -- on the cards where they lie.
  function setFaces(faces) {
    for (const [code, face] of Object.entries(faces)) {
      known[code][0].map = face;
      known[code][0].needsUpdate = true;
    }
  }

  // Which line a card is drawn with, and whether its face is dimmed (a card
  // that may not be played). Faces are one material per card, so dimming
  // one dims only that card.
  function decorate(mesh, { line = "plain", dim = false } = {}) {
    mesh.children[0].material = inks[line];
    const code = mesh.userData.code;
    if (code) known[code][0].color.setScalar(dim ? 0.72 : 1);
  }

  return { card, reveal, decorate, setFaces, geometry, ink };
}

export function place(mesh, pose) {
  mesh.position.copy(pose.position);
  mesh.quaternion.copy(pose.quaternion);
}
