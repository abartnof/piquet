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
// its own eye, and the information sits along the top instead.

import { PerspectiveCamera } from "three";
import { CAMERA, CAMERA_PORTRAIT, PORTRAIT_BELOW } from "./units.js";

export function framing(aspect, inset = 0) {
  const upright = aspect < PORTRAIT_BELOW;
  const view = upright ? CAMERA_PORTRAIT : CAMERA;
  const area = aspect * (1 - (upright ? 0 : inset));
  const fov = upright ? view.fov : Math.max(view.fov, (360 / Math.PI) * Math.atan(CAMERA.widthTan / area));
  // The play area's centre, in normalised device coordinates.
  const shift = upright ? 0 : inset;
  return { upright, position: view.position, target: view.target, fov, shift };
}

// Aim a camera as the page does, for a window of this shape.
export function aim(camera, aspect, inset = 0) {
  const f = framing(aspect, inset);
  camera.position.set(...f.position);
  camera.lookAt(...f.target);
  camera.fov = f.fov;
  camera.aspect = aspect;
  // three moves the frustum's left edge by near * filmOffset / filmWidth;
  // a shift of s in device coordinates is that, over half the frustum's width.
  camera.filmOffset = -f.shift * camera.getFilmWidth() * Math.tan((f.fov * Math.PI) / 360) * aspect;
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  return f;
}

export function cameraFor(aspect, inset = 0) {
  const camera = new PerspectiveCamera(CAMERA.fov, aspect, CAMERA.near, CAMERA.far);
  aim(camera, aspect, inset);
  return camera;
}
