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
import { CAMERA } from "./units.js";

// Candidate surfaces for the table, for Andrew to choose between.
export const SURFACES = {
  paper: { table: "#f3efe7", air: "#f7f4ee" }, // warm paper-white
  sky: { table: "#e3ecf5", air: "#eef3f9" }, // pale sky
  sage: { table: "#e2eadf", air: "#eef2eb" }, // soft sage
};

export function createScene(
  canvas,
  { surface = "sky", shadow = "vsm", eye = CAMERA.position, at = CAMERA.target, fov = CAMERA.fov } = {},
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

  const camera = new PerspectiveCamera(fov, 1, CAMERA.near, CAMERA.far);
  camera.position.set(...eye);
  camera.lookAt(...at);

  scene.add(new HemisphereLight("#ffffff", "#d8dbe3", 2.3));
  const key = new DirectionalLight("#ffffff", 1.0);
  key.position.set(-30, 80, 40);
  key.castShadow = true;
  // The shadow camera must cover the table in centimetres; its default box is
  // ten units across and would clip every shadow but the centre's.
  Object.assign(key.shadow.camera, { left: -70, right: 70, top: 60, bottom: -60, near: 20, far: 200 });
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.02;
  key.shadow.radius = shadow === "vsm" ? 12 : 3;
  key.shadow.blurSamples = 16;
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
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
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

  return { scene, camera, renderer, key, render, registerInk, frames: () => frames };
}
