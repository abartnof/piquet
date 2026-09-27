// The scene: renderer, camera, light, and the table the cards rest on.
//
// The look (docs/TABLE3D.md section 8): bright and airy. A hemisphere light
// for the base, one key light high to the front-left casting soft shadows,
// and a pale surface with no texture that reads as a table only because
// things rest on it and cast shadows on it. Its far edge fades into the
// background, so there is no edge to see.

import {
  Color,
  DirectionalLight,
  Fog,
  HemisphereLight,
  Mesh,
  MeshToonMaterial,
  PCFShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  Scene,
  SRGBColorSpace,
  VSMShadowMap,
  WebGLRenderer,
} from "three";
import { RAMPS } from "./materials.js";
import { CAMERA, CAMERA_PORTRAIT, PORTRAIT_BELOW } from "./units.js";

// The landscape view is tuned at 16:10 with a 40 degree vertical field; a
// narrower window widens it just enough to keep the table's full width.
const WIDTH_TAN = Math.tan((CAMERA.fov * Math.PI) / 360) * 1.6;

// Candidate surfaces for the table, for Andrew to choose between.
export const SURFACES = {
  paper: { table: "#f3efe7", air: "#f7f4ee" }, // warm paper-white
  sky: { table: "#e3ecf5", air: "#eef3f9" }, // pale sky
  sage: { table: "#e2eadf", air: "#eef2eb" }, // soft sage
};

export function createScene(
  canvas,
  { surface = "sky", shadow = "vsm", shadowMap = 512, blurSamples = 8, eye, at, fov } = {},
) {
  const colours = SURFACES[surface] || SURFACES.sky;
  const renderer = new WebGLRenderer({ canvas, antialias: true });
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = shadow === "vsm" ? VSMShadowMap : PCFShadowMap;

  const scene = new Scene();
  scene.background = new Color(colours.air);
  // The table's far reaches fade into the air: no edge, no horizon.
  scene.fog = new Fog(colours.air, 110, 260);

  const camera = new PerspectiveCamera(CAMERA.fov, 1, CAMERA.near, CAMERA.far);
  let portrait = null;
  const stage = { portrait: false, onReframe: null };
  // Place the eye for this window: upright, or across. Explicit eye, at and
  // fov (from the page's query, for tuning) win.
  function frame(aspect) {
    const upright = aspect < PORTRAIT_BELOW;
    const view = upright ? CAMERA_PORTRAIT : CAMERA;
    camera.position.set(...(eye ?? view.position));
    camera.lookAt(...(at ?? view.target));
    camera.fov = fov ?? (upright ? view.fov : Math.max(view.fov, (360 / Math.PI) * Math.atan(WIDTH_TAN / aspect)));
    camera.aspect = aspect;
    camera.updateProjectionMatrix();
    if (upright !== portrait) {
      const first = portrait === null;
      portrait = upright;
      stage.portrait = upright;
      if (!first && stage.onReframe) stage.onReframe(upright);
    }
  }

  scene.add(new HemisphereLight("#ffffff", "#d8dbe3", 2.3));
  const key = new DirectionalLight("#ffffff", 1.0);
  key.position.set(-30, 80, 40);
  key.castShadow = true;
  // The shadow camera must cover all the table either eye can see. Its
  // default box is ten units across and would clip every shadow but the
  // centre's; and with soft shadows every receiver also casts, so the table
  // faintly shadows itself wherever the box reaches -- a box edge in view
  // shows as a step in the table's brightness (the phone's higher eye found
  // one).
  const REACH = 115;
  Object.assign(key.shadow.camera, { left: -REACH, right: REACH, top: REACH, bottom: -REACH, near: 1, far: 320 });
  // The soft (VSM) shadow blurs its whole map twice every frame, so its cost
  // goes with the map's area times the samples: 2048 px and 16 samples took
  // 4.3 s a frame on the software-rendered VM, where PCF took 0.45 s. The
  // softness is the blur's radius in centimetres, so a smaller map at a
  // proportionally smaller radius in texels looks the same: at 512 and 8
  // samples it could not be told apart by eye, for about an eighth of the
  // work -- which on a phone is battery.
  key.shadow.mapSize.set(shadowMap, shadowMap);
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.02;
  // The blur's radius is set in centimetres of table, so the softness stays
  // the same whatever the map's size or reach.
  const SOFTNESS = 0.8; // cm
  key.shadow.radius = shadow === "vsm" ? (SOFTNESS * shadowMap) / (2 * REACH) : 3;
  key.shadow.blurSamples = blurSamples;
  key.shadow.intensity = 0.75;
  scene.add(key);

  const table = new Mesh(
    new PlaneGeometry(600, 600),
    new MeshToonMaterial({ color: colours.table, gradientMap: RAMPS.table() }),
  );
  table.rotation.x = -Math.PI / 2;
  table.receiveShadow = true;
  scene.add(table);

  // The ink width is given in CSS pixels and drawn in device pixels, so a
  // line keeps its weight on a sharp screen.
  const inks = new Set();
  function fitInk(material) {
    renderer.getDrawingBufferSize(material.uniforms.resolution.value);
    material.uniforms.inkWidth.value = material.userData.cssWidth * renderer.getPixelRatio();
  }
  function registerInk(material) {
    material.userData.cssWidth ??= material.uniforms.inkWidth.value;
    inks.add(material);
    fitInk(material);
  }

  function resize() {
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, CAMERA.maxPixelRatio));
    renderer.setSize(width, height, false);
    frame(width / height);
    for (const ink of inks) fitInk(ink);
  }

  let frames = 0;
  function render() {
    renderer.render(scene, camera);
    frames += 1;
  }

  resize();
  window.addEventListener("resize", () => {
    resize();
    render();
  });

  return Object.assign(stage, { scene, camera, renderer, key, render, registerInk, frames: () => frames });
}
