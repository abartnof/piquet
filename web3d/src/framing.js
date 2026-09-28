// Where the eye is, for a window of a given shape -- a pure function, so the
// tests can look through exactly the camera the page uses.
//
// Information lives down the left of the window and the controls under your
// hand (Andrew: "any information display should be on the left, or top; any
// area with buttons that influence gameplay should be on the right/bottom").
// So the table is framed in the play area to the right of the information
// column: `inset` is the share of the window's width the column takes. The
// picture is moved over by shifting the lens, not by turning the eye, so the
// table keeps the same perspective whatever the column's width; and the
// field widens only as far as the play area needs to keep the table's width.
//
// Below PORTRAIT_BELOW the table is laid out for a phone held upright, under
// its own eye, and the information sits along the top instead. There the
// overlay's strips are fixed heights in CSS pixels, so a short window has
// less room for the table than a tall one: the field is fitted to the band
// between them, and the picture lifted into it.

import { PerspectiveCamera } from "three";
import { CAMERA, CAMERA_PORTRAIT, PORTRAIT_BELOW } from "./units.js";

// The compact overlay's strips at their tallest, in CSS pixels: along the
// top the score, and while you exchange and declare the folded line of what
// your hand is worth; at the foot the prompt, its choices and the tools.
// The browser test holds the page to them.
export const STRIPS = Object.freeze({ top: 142, foot: 194 });

// A phone as the tests and the page assume one, when no height is given.
const PHONE_HEIGHT = 844;

export function framing(aspect, inset = 0, height = PHONE_HEIGHT) {
  const upright = aspect < PORTRAIT_BELOW;
  if (!upright) {
    const area = aspect * (1 - inset);
    const fov = Math.max(CAMERA.fov, (360 / Math.PI) * Math.atan(CAMERA.widthTan / area));
    // The play area's centre, in normalised device coordinates.
    return { upright, position: CAMERA.position, target: CAMERA.target, fov, shift: inset, lift: 0 };
  }
  // The band between the strips, in device coordinates; the field just tall
  // enough for the table's reach to fill it -- or, on a squat window, wide
  // enough for its width -- and the lift that centres the table in it.
  const { up, down, across } = CAMERA_PORTRAIT.reach;
  const top = 1 - (2 * STRIPS.top) / height;
  const foot = -1 + (2 * STRIPS.foot) / height;
  const tan = Math.max((up - down) / (top - foot), across / (0.96 * aspect));
  const lift = (top + foot) / 2 - (up + down) / (2 * tan);
  const fov = (360 / Math.PI) * Math.atan(tan);
  return { upright, position: CAMERA_PORTRAIT.position, target: CAMERA_PORTRAIT.target, fov, shift: 0, lift };
}

// Aim a camera as the page does, for a window of this shape (and, upright,
// this height in CSS pixels).
export function aim(camera, aspect, inset = 0, height = PHONE_HEIGHT) {
  const f = framing(aspect, inset, height);
  camera.position.set(...f.position);
  camera.lookAt(...f.target);
  camera.fov = f.fov;
  camera.aspect = aspect;
  // three moves the frustum's left edge by near * filmOffset / filmWidth;
  // a shift of s in device coordinates is that, over half the frustum's width.
  camera.filmOffset = -f.shift * camera.getFilmWidth() * Math.tan((f.fov * Math.PI) / 360) * aspect;
  // Upright, the lift: three moves the frustum's window down by the view
  // offset's share of the full height, and device coordinates span two, so
  // lifting the picture by l is an offset of l / 2 in a full height of one.
  if (f.lift) camera.setViewOffset(aspect, 1, 0, f.lift / 2, aspect, 1);
  else camera.clearViewOffset();
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  return f;
}

export function cameraFor(aspect, inset = 0, height = PHONE_HEIGHT) {
  const camera = new PerspectiveCamera(CAMERA.fov, aspect, CAMERA.near, CAMERA.far);
  aim(camera, aspect, inset, height);
  return camera;
}
