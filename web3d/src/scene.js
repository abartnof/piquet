// The scene: renderer, camera, light, and the table the cards rest on.

import {
  BoxGeometry,
  Color,
  DirectionalLight,
  HemisphereLight,
  Mesh,
  MeshToonMaterial,
  PCFSoftShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  Scene,
  SRGBColorSpace,
  WebGLRenderer,
} from "three";
import { CAMERA, CARD, TABLE } from "./units.js";

export function createScene(canvas) {
  const renderer = new WebGLRenderer({ canvas, antialias: true });
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = PCFSoftShadowMap;

  const scene = new Scene();
  scene.background = new Color("#eef1f5");

  const camera = new PerspectiveCamera(CAMERA.fov, 1, CAMERA.near, CAMERA.far);
  camera.position.set(...CAMERA.position);
  camera.lookAt(...CAMERA.target);

  scene.add(new HemisphereLight("#ffffff", "#c9ced8", 1.6));
  const key = new DirectionalLight("#ffffff", 1.8);
  key.position.set(-30, 80, 40);
  key.castShadow = true;
  // The shadow camera must cover the table in centimetres; its default box is
  // ten units across and would clip every shadow but the centre's.
  Object.assign(key.shadow.camera, { left: -75, right: 75, top: 60, bottom: -60, near: 1, far: 250 });
  key.shadow.mapSize.set(2048, 2048);
  scene.add(key);

  const table = new Mesh(
    new PlaneGeometry(TABLE.width, TABLE.depth),
    new MeshToonMaterial({ color: "#f7f5f0" }),
  );
  table.rotation.x = -Math.PI / 2;
  table.receiveShadow = true;
  scene.add(table);

  // A placeholder card, floating: its shadow on the table is what makes the
  // table read as a surface at all. Replaced by the real cards.
  const card = new Mesh(
    new BoxGeometry(CARD.width, CARD.thickness, CARD.height),
    new MeshToonMaterial({ color: "#ffffff" }),
  );
  card.position.set(0, 12, 10);
  card.rotation.set(0.9, 0, 0.15);
  card.castShadow = true;
  scene.add(card);

  function resize() {
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, CAMERA.maxPixelRatio));
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
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

  return { scene, camera, renderer, render, frames: () => frames };
}
