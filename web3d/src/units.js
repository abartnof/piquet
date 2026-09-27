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

// The eye for a phone held upright: higher and nearer overhead, with a
// wider view, over the stacked arrangement of ZONES_PORTRAIT.
export const CAMERA_PORTRAIT = Object.freeze({
  position: Object.freeze([0, 85, 48]),
  target: Object.freeze([0, 0, 8]),
  fov: 56,
});

// Narrower than this, the table is laid out for a phone held upright.
export const PORTRAIT_BELOW = 0.85;

// Where everything rests (docs/TABLE3D.md section 6), in centimetres on the
// table. Hands are fans floating before their holders; the rest lies flat.
export const ZONES = Object.freeze({
  yourHand: Object.freeze({ centre: Object.freeze([0, 15, 27]), radius: 16, spread: 6.2, groupGap: 3, tilt: 14 }),
  theirHand: Object.freeze({ centre: Object.freeze([0, 12, -22]), facing: Object.freeze([0, 26, -300]), radius: 16, spread: 5.2 }),
  ribbon: Object.freeze({ x: 22.5, z: -2, spacing: 1.45 }), // the pack spread for the cut, top card at the right
  yourCut: Object.freeze({ x: -5, z: 9 }),
  theirCut: Object.freeze({ x: 5, z: -13 }),
  talon: Object.freeze({ x: -18, z: -3 }),
  yourDiscards: Object.freeze({ x: -31, z: 9 }),
  theirDiscards: Object.freeze({ x: -31, z: -14 }),
  yourPlay: Object.freeze({ x: 0.6, z: 3 }), // your card in a trick, nearer you
  theirPlay: Object.freeze({ x: -0.6, z: -7 }), // theirs, turned to face them
  // Clear of the floating score tab above and the prompt below.
  yourTricks: Object.freeze({ x: 15, z: 7, span: 24 }),
  theirTricks: Object.freeze({ x: 15, z: -9, span: 24 }),
  // Only in passing, while dealing: the pack squared in front of the dealer,
  // and the pile dealt before each player.
  pack: Object.freeze({ you: Object.freeze({ x: -7, z: 10 }), them: Object.freeze({ x: -7, z: -12 }) }),
  dealt: Object.freeze({ you: Object.freeze({ x: 5, z: 13 }), them: Object.freeze({ x: 5, z: -15 }) }),
});

// The same table for a phone held upright: everything drawn in within about
// 24 cm either side, and stacked down the table instead of spread across it
// -- their hand, their won tricks, the talon and the discards, the trick,
// yours -- so the cards stay big enough to read on a narrow screen.
export const ZONES_PORTRAIT = Object.freeze({
  yourHand: Object.freeze({ centre: Object.freeze([0, 17, 25]), radius: 14, spread: 4.4, groupGap: 2, tilt: 14 }),
  theirHand: Object.freeze({ centre: Object.freeze([0, 12, -27]), facing: Object.freeze([0, 26, -300]), radius: 14, spread: 3.8 }),
  ribbon: Object.freeze({ x: 16.5, z: -2, spacing: 1.05 }),
  yourCut: Object.freeze({ x: -5, z: 9 }),
  theirCut: Object.freeze({ x: 5, z: -13 }),
  talon: Object.freeze({ x: -14, z: -4 }),
  yourDiscards: Object.freeze({ x: -17, z: 8 }),
  theirDiscards: Object.freeze({ x: -17, z: -15 }),
  yourPlay: Object.freeze({ x: 4.5, z: 4 }),
  theirPlay: Object.freeze({ x: 3.3, z: -6 }),
  yourTricks: Object.freeze({ x: -10, z: 17.5, span: 22 }),
  theirTricks: Object.freeze({ x: -10, z: -19.5, span: 22 }),
  pack: Object.freeze({ you: Object.freeze({ x: 9, z: 9 }), them: Object.freeze({ x: 9, z: -12 }) }),
  dealt: Object.freeze({ you: Object.freeze({ x: -2, z: 17.5 }), them: Object.freeze({ x: -2, z: -19.5 }) }),
});
