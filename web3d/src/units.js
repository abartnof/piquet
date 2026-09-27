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
  target: Object.freeze([0, 0, 8]),
  fov: 40, // vertical, degrees
  near: 5,
  far: 600,
  maxPixelRatio: 2,
});
