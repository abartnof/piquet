// The look spike (docs/TABLE3D.md, P2): a table set by hand, mid-deal, to
// judge the light, the shadows, the ink and the surface by eye. Replaced by
// the real layout once the look is settled.

import { Vector3 } from "three";
import { place } from "./deck.js";
import { fan, lying } from "./kinematics.js";
import { CARD } from "./units.js";

const DEG = Math.PI / 180;
const REST = 0.02; // a card on the table rests a hair above it
const STEP = CARD.thickness + 0.02; // and each card on a pile a hair above the last

export function buildSpike(stage, deck, { angles = false } = {}) {
  if (angles) return buildAngles(deck);

  const flat = (code, x, z, { faceUp = true, yaw = 0, layer = 0 } = {}) =>
    place(deck.card(code), lying({ x, z, height: REST + layer * STEP, faceUp, yaw }));

  // Your hand: a real piquet hand, sorted by suit, colours alternating.
  const yours = ["AS", "KS", "JS", "9S", "AH", "QH", "TH", "8H", "KC", "JC", "7C", "QD"];
  fan({ count: 12, centre: new Vector3(0, 15, 27), facing: stage.camera.position }).forEach((p, i) =>
    place(deck.card(yours[i]), p),
  );
  // Your opponent's: twelve backs, held nearly upright -- the way a person
  // holds a hand, and the way its backs face you rather than the ceiling.
  fan({ count: 12, centre: new Vector3(0, 13, -24), facing: new Vector3(0, 27, -300), spread: 5.2 * DEG, tilt: 0 })
    .forEach((p) => place(deck.card(null), p));

  // The talon, three below and five crossed over them (Foster), to the left.
  for (let i = 0; i < 3; i++) flat(null, -18, -3, { faceUp: false, layer: i });
  for (let i = 0; i < 5; i++) flat(null, -18, -3, { faceUp: false, layer: 3 + i, yaw: 90 * DEG });

  // Discards, face down: yours near, theirs far.
  for (let i = 0; i < 4; i++) flat(null, -31, 9, { faceUp: false, layer: i, yaw: (i % 2 ? 3 : -2) * DEG });
  for (let i = 0; i < 5; i++) flat(null, -31, -14, { faceUp: false, layer: i, yaw: (i % 2 ? -3 : 2) * DEG });

  // A trick in progress: they led the king of diamonds, which lies facing
  // them; your card is not yet down.
  flat("KD", 0, -5, { yaw: 180 * DEG + 4 * DEG });

  // Tricks won, face up and pushed to the right: two of yours, one of theirs.
  const trick = (led, followed, x, z, yaw) => {
    flat(led, x, z, { yaw, layer: 0 });
    flat(followed, x + 1.4, z + 0.3, { yaw: yaw - 7 * DEG, layer: 1 });
  };
  trick("AD", "8D", 19, 9, 0);
  trick("9H", "JH", 23.5, 9, 2 * DEG);
  trick("TC", "9C", 19, -13, 180 * DEG);
}

// Single cards at a range of attitudes -- flat, tipped, on edge, turned, and
// floating -- to check by eye that the ink line is continuous at every angle.
function buildAngles(deck) {
  const codes = ["AS", "KH", "QD", "JC", "TS", "9H", "8D", "7C"];
  const tilts = [0, 20, 45, 70, 85, 90, 110, 150]; // degrees about the card's width
  tilts.forEach((tilt, i) => {
    for (const [row, z, lift, yaw] of [[0, 8, 0, 0], [1, -10, 9, 35]]) {
      const mesh = deck.card(row ? null : codes[i]);
      const x = -35 + i * 10;
      mesh.rotation.set(-90 * DEG + tilt * DEG, yaw * DEG, 0, "YXZ");
      mesh.position.set(x, lift + REST + (CARD.height / 2) * Math.sin(tilt * DEG) + CARD.thickness, z);
    }
  });
}
