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
  // The table's half-width the view must keep, as the tangent of half the
  // horizontal field: what 40 degrees shows at 16:10 across the whole window.
  widthTan: 0.44,
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
  // 5.6 degrees a card leaves 1.6 cm of each showing at this radius -- twice
  // the corner index -- and keeps a full hand in suits clear of the prompt.
  //
  // Both hands are held as people hold cards: at 75 degrees to the table,
  // leaning back 15 from upright toward their holder (Andrew: "the hands are
  // sort of tilted away from the player at ~75 degrees").
  yourHand: Object.freeze({ centre: Object.freeze([0, 16, 26]), radius: 16, spread: 5.6, groupGap: 2.6, lean: 15 }),
  theirHand: Object.freeze({ centre: Object.freeze([0, 12, -22]), radius: 16, spread: 5.2, lean: 15 }),
  ribbon: Object.freeze({ x: 20, z: -6, spacing: 1.3 }), // the pack spread for the cut, top card at the right
  yourCut: Object.freeze({ x: -5, z: 4 }),
  theirCut: Object.freeze({ x: 5, z: -16 }),
  talon: Object.freeze({ x: -15, z: -9 }),
  // Your discards, and where you hold them up when you look at them.
  yourDiscards: Object.freeze({ x: -25, z: -1, peek: Object.freeze({ centre: Object.freeze([-21, 12, 14]), radius: 10, spread: 9 }) }),
  theirDiscards: Object.freeze({ x: -25, z: -18 }),
  yourPlay: Object.freeze({ x: 0.6, z: -4 }), // your card in a trick, nearer you
  theirPlay: Object.freeze({ x: -0.6, z: -13 }), // theirs, turned to face them
  // Won tricks shingled to the right, clear of your hand.
  yourTricks: Object.freeze({ x: 10, z: -5, span: 18 }),
  theirTricks: Object.freeze({ x: 10, z: -17, span: 18 }),
  // Only in passing, while dealing: the pack squared in front of the dealer,
  // and the pile dealt before each player.
  pack: Object.freeze({ you: Object.freeze({ x: -7, z: 0 }), them: Object.freeze({ x: -7, z: -16 }) }),
  dealt: Object.freeze({ you: Object.freeze({ x: 5, z: 0 }), them: Object.freeze({ x: 5, z: -17 }) }),
});

// The same table for a phone held upright: everything drawn in within about
// 24 cm either side, and stacked down the table instead of spread across it
// -- their hand, their won tricks, the talon and the discards, the trick,
// yours -- so the cards stay big enough to read on a narrow screen.
export const ZONES_PORTRAIT = Object.freeze({
  // A phone's eye is nearly overhead, and a hand at 75 degrees would be seen
  // almost edge on; held up at 50 degrees it still reads.
  yourHand: Object.freeze({ centre: Object.freeze([0, 12, 33]), radius: 14, spread: 4.4, groupGap: 2, lean: 40 }),
  theirHand: Object.freeze({ centre: Object.freeze([0, 12, -27]), radius: 14, spread: 3.8, lean: 15 }),
  ribbon: Object.freeze({ x: 16.5, z: -2, spacing: 1.05 }),
  yourCut: Object.freeze({ x: -5, z: 9 }),
  theirCut: Object.freeze({ x: 5, z: -13 }),
  talon: Object.freeze({ x: -14, z: -4 }),
  yourDiscards: Object.freeze({ x: -17, z: 8, peek: Object.freeze({ centre: Object.freeze([-7, 13, 12]), radius: 9, spread: 9 }) }),
  theirDiscards: Object.freeze({ x: -17, z: -15 }),
  yourPlay: Object.freeze({ x: 4.5, z: 4 }),
  theirPlay: Object.freeze({ x: 3.3, z: -6 }),
  yourTricks: Object.freeze({ x: -10, z: 17.5, span: 22 }),
  theirTricks: Object.freeze({ x: -10, z: -19.5, span: 22 }),
  pack: Object.freeze({ you: Object.freeze({ x: 9, z: 9 }), them: Object.freeze({ x: 9, z: -12 }) }),
  dealt: Object.freeze({ you: Object.freeze({ x: -2, z: 17.5 }), them: Object.freeze({ x: -2, z: -19.5 }) }),
});
