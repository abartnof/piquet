// The scene: renderer, camera, light, and the table the cards rest on.
//
// The look (docs/TABLE3D.md section 8): bright and airy. A hemisphere light
// for the base and one key light high to the front-left casting soft
// shadows, on the cards; the table is unlit, a pale procedural pattern
// (surfaces.js) whose far reaches fade into the air, so there is no edge.

import {
  CanvasTexture,
  Color,
  DirectionalLight,
  Fog,
  HemisphereLight,
  Mesh,
  MeshBasicMaterial,
  PCFShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  RepeatWrapping,
  Scene,
  ShadowMaterial,
  SRGBColorSpace,
  VSMShadowMap,
  WebGLRenderer,
} from "three";
import { M3, M3_MS } from "./easing.js";
import { aim, STRIPS } from "./framing.js";
import { BASE, PATTERNS, drawSurface } from "./surfaces.js";
import { CAMERA } from "./units.js";

export function createScene(
  canvas,
  { table: pattern = "plain", shadow = "vsm", shadowMap = 512, blurSamples = 8, eye, at, fov, lighting = {} } = {},
) {
  const renderer = new WebGLRenderer({ canvas, antialias: true });
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = shadow === "vsm" ? VSMShadowMap : PCFShadowMap;

  const scene = new Scene();
  scene.background = new Color(BASE);
  // The table's far reaches fade into the air: no edge, no horizon.
  scene.fog = new Fog(BASE, 110, 260);

  const camera = new PerspectiveCamera(CAMERA.fov, 1, CAMERA.near, CAMERA.far);
  let portrait = null;
  // The share of the width the information column takes, across the table:
  // the table is framed in the play area beside it (framing.js).
  let inset = 0;
  // Upright, the strips the table is framed between (framing.js) -- and on
  // a phone held sideways the columns, `left` and `right`: as they stand on
  // the way to `target`, which they ease toward.
  let strips = { ...STRIPS };
  let target = { ...STRIPS };
  const stage = { portrait: false, onReframe: null };
  // Place the eye for this window: upright, or across. Explicit eye, at and
  // fov (from the page's query, for tuning) win.
  function frame(aspect) {
    const sides = strips.left === undefined ? null : { left: strips.left, right: strips.right };
    const { upright } = aim(camera, aspect, inset, canvas.clientHeight || undefined, strips, sides);
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
  // showed (the user: the shadows "don't follow the cards to the table at
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

  // The table (the user's spec): unlit, a procedural pattern in one ink over a
  // light base (surfaces.js) -- the cards, not the table, take the light.
  // The shadows are laid over it by a sheet that draws nothing else, so a
  // card still says where it is by the shadow it casts on the pattern.
  const surface = new CanvasTexture(document.createElement("canvas"));
  surface.wrapS = RepeatWrapping;
  surface.wrapT = RepeatWrapping;
  surface.colorSpace = SRGBColorSpace;
  surface.anisotropy = renderer.capabilities.getMaxAnisotropy();
  const TABLE_CM = 600;
  const TILE_CM = 48; // one 1024-pixel tile: a dot grid's 46 px is 2.2 cm
  surface.repeat.set(TABLE_CM / TILE_CM, TABLE_CM / TILE_CM);
  const table = new Mesh(new PlaneGeometry(TABLE_CM, TABLE_CM), new MeshBasicMaterial({ map: surface }));
  table.rotation.x = -Math.PI / 2;
  scene.add(table);
  const shade = new Mesh(new PlaneGeometry(TABLE_CM, TABLE_CM), new ShadowMaterial({ color: "#14161a", opacity: 0.3 }));
  shade.rotation.x = -Math.PI / 2;
  shade.position.y = 0.005; // above the table, below the lowest card
  shade.receiveShadow = true;
  scene.add(shade);
  function setSurface(id) {
    const chosen = PATTERNS.find((p) => p.id === id) ?? PATTERNS[0];
    drawSurface(surface.image, chosen);
    surface.needsUpdate = true;
    stage.surface = chosen.id;
  }
  setSurface(pattern);

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

  // The strips the overlay leaves on a phone, in CSS pixels, as measured:
  // the table eases to its new framing as a Material 3 element changes size
  // -- emphasized decelerate, a long duration -- or, `instant`, is simply
  // there. The tween is the scene's own, so it runs whether or not the cards
  // are moving.
  let easing = null;
  const KEYS = ["top", "foot", "left", "right"];
  function setStrips(next, { instant = false } = {}) {
    const same = (a, b) => KEYS.every((k) => (a[k] === undefined) === (b[k] === undefined) && (a[k] === undefined || Math.abs(a[k] - b[k]) < 1));
    if (same(next, target)) return false;
    // Columns come and go with the phone's turning: at once, not eased.
    const turned = (next.left === undefined) !== (strips.left === undefined);
    target = Object.fromEntries(KEYS.filter((k) => next[k] !== undefined).map((k) => [k, next[k]]));
    const aspect = () => (canvas.clientWidth || 1) / (canvas.clientHeight || 1);
    if (instant || turned || !portrait) {
      easing = null;
      strips = { ...target };
      frame(aspect());
      render();
      return true;
    }
    const restart = !easing;
    easing = { from: { ...strips }, start: performance.now() };
    const step = (now) => {
      if (!easing) return;
      const u = M3.emphasizedDecelerate((now - easing.start) / M3_MS.long2);
      strips = Object.fromEntries(Object.keys(target).map((k) => [k, (easing.from[k] ?? target[k]) + (target[k] - (easing.from[k] ?? target[k])) * u]));
      frame(aspect());
      render();
      if (u < 1) requestAnimationFrame(step);
      else easing = null;
    };
    if (restart) requestAnimationFrame(step);
    return true;
  }

  return Object.assign(stage, {
    scene, camera, renderer, key, render, registerInk, setInset, setStrips, setSurface,
    strips: () => ({ ...target }),
    frames: () => frames,
  });
}
