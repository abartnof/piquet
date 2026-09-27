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
import { aim } from "./framing.js";
import { RAMPS } from "./materials.js";
import { CAMERA } from "./units.js";

// Candidate surfaces for the table, for Andrew to choose between.
export const SURFACES = {
  paper: { table: "#f3efe7", air: "#f7f4ee" }, // warm paper-white
  sky: { table: "#e3ecf5", air: "#eef3f9" }, // pale sky
  sage: { table: "#e2eadf", air: "#eef2eb" }, // soft sage
};

export function createScene(
  canvas,
  { surface = "sky", shadow = "vsm", shadowMap = 512, blurSamples = 8, eye, at, fov, lighting = {} } = {},
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
  // The share of the width the information column takes, across the table:
  // the table is framed in the play area beside it (framing.js).
  let inset = 0;
  const stage = { portrait: false, onReframe: null };
  // Place the eye for this window: upright, or across. Explicit eye, at and
  // fov (from the page's query, for tuning) win.
  function frame(aspect) {
    const { upright } = aim(camera, aspect, inset);
    if (eye || at || fov) {
      if (eye) camera.position.set(...eye);
      if (at) camera.lookAt(...at);
      if (fov) camera.fov = fov;
      camera.updateProjectionMatrix();
    }
    if (upright !== portrait) {
      const first = portrait === null;
      portrait = upright;
      stage.portrait = upright;
      if (!first && stage.onReframe) stage.onReframe(upright);
    }
  }

  // The balance between the two sets how deep a shadow is: it takes away
  // only the key light. With the sky at 2.3 against a key of 1.0 a shadow
  // was a fifth darker than the table, and one card's in the air hardly
  // showed (Andrew: the shadows "don't follow the cards to the table at
  // all"). The same brightness, weighted toward the key, makes a shadow
  // about a third darker; and a sun a little lower draws a held card's
  // shadow long enough to show how it is tilted.
  const light = { sky: 1.7, key: 1.6, ...lighting };
  scene.add(new HemisphereLight("#ffffff", "#d8dbe3", light.sky));
  const key = new DirectionalLight("#ffffff", light.key);
  key.position.set(-34, 70, 46);
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
  key.shadow.intensity = 0.8;
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

  // The information column's width in CSS pixels, as laid out: reframe the
  // table beside it.
  function setInset(pixels) {
    const width = canvas.clientWidth || 1;
    const next = Math.max(0, Math.min(0.4, pixels / width));
    if (Math.abs(next - inset) < 1e-3) return false;
    inset = next;
    frame(width / (canvas.clientHeight || 1));
    return true;
  }

  return Object.assign(stage, { scene, camera, renderer, key, render, registerInk, setInset, frames: () => frames });
}
