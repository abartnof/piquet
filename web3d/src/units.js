// Space: units, the table, the camera, the zones -- one source of truth.
//
// Centimetres throughout. y is up and the table top is y = 0; the human sits
// at +z, the opponent at -z, and x runs to the human's right
// (docs/TABLE3D.md section 6).

// A poker-size card, 2.5 x 3.5 in: exactly the 5:7 of the face art.
export const CARD = Object.freeze({
  width: 6.35,
  height: 8.89,
  radius: 0.3175, // 5% of the width, as in the art
  thickness: 0.03,
});

// The implied table: a large pale slab whose edge falls away out of sight.
export const TABLE = Object.freeze({
  width: 140,
  depth: 100,
});

// The human's eyes, looking down the table at a point a little in front of
// its centre.
export const CAMERA = Object.freeze({
  position: Object.freeze([0, 55, 60]),
  target: Object.freeze([0, 0, 0]),
  fov: 40, // vertical, degrees
  // Nothing comes nearer the eye than about 45 cm; a near plane at 20 keeps
  // the depth buffer fine enough to tell a card from the one it lies on.
  near: 20,
  far: 400,
  maxPixelRatio: 2,
});

// Where everything rests (docs/TABLE3D.md section 6), in centimetres on the
// table. Hands are fans floating before their holders; the rest lies flat.
export const ZONES = Object.freeze({
  yourHand: Object.freeze({ centre: Object.freeze([0, 15, 27]), radius: 16, spread: 6.2, groupGap: 3, tilt: 14 }),
  theirHand: Object.freeze({ centre: Object.freeze([0, 13, -24]), facing: Object.freeze([0, 27, -300]), radius: 16, spread: 5.2 }),
  ribbon: Object.freeze({ x: 22.5, z: -2, spacing: 1.45 }), // the pack spread for the cut, top card at the right
  yourCut: Object.freeze({ x: -5, z: 9 }),
  theirCut: Object.freeze({ x: 5, z: -13 }),
  talon: Object.freeze({ x: -18, z: -3 }),
  yourDiscards: Object.freeze({ x: -31, z: 9 }),
  theirDiscards: Object.freeze({ x: -31, z: -14 }),
  yourPlay: Object.freeze({ x: 0.6, z: 3 }), // your card in a trick, nearer you
  theirPlay: Object.freeze({ x: -0.6, z: -7 }), // theirs, turned to face them
  yourTricks: Object.freeze({ x: 15, z: 9, span: 26 }),
  theirTricks: Object.freeze({ x: 15, z: -14, span: 26 }),
});
