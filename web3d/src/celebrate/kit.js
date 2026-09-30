// What the celebrations build with, in the table's own look: toon shading in
// flat bands, the ink line, and the page's Material colours -- bright and
// clean, never the prototype's dark room (Andrew: "use the normal look").

import { Color, DynamicDrawUsage, InstancedMesh, Mesh, MeshToonMaterial, Object3D } from "three";
import { INK, inkMaterial, toonRamp } from "../materials.js";
import { G } from "./physics.js";

// The page's Material 3 scheme (style.css), and the card edge's cream.
export const PALETTE = Object.freeze({
  primary: "#435e91",
  primaryContainer: "#d7e2ff",
  tertiary: "#715574",
  tertiaryContainer: "#fbd7fc",
  you: "#924c00",
  youContainer: "#ffdcc4",
  them: "#00696e",
  // The page's own amber (the ink of a card chosen to throw): yours, bright.
  amber: "#e8900c",
  themContainer: "#6ff6fe",
  cream: "#f3efe6",
  surface: "#f9f9ff",
  outline: "#c4c6d0",
  ink: INK,
});

// Confetti and the like: the containers bright, the strong tones sparing.
export const BRIGHTS = Object.freeze([
  PALETTE.primaryContainer,
  PALETTE.tertiaryContainer,
  PALETTE.youContainer,
  PALETTE.themContainer,
  PALETTE.primary,
  PALETTE.you,
  PALETTE.them,
  PALETTE.cream,
]);

// One kit per table: its ramp, and one ink line registered with the stage so
// the line keeps its width in pixels.
export function kit(stage) {
  const ramp = toonRamp([0.74, 0.9, 1.0]);
  const ink = inkMaterial({ color: INK, width: 2.5 });
  stage.registerInk?.(ink);
  const toon = (color, options = {}) => new MeshToonMaterial({ color: new Color(color), gradientMap: ramp, ...options });
  // A mesh in toon, with the ink line round it. The line needs smooth
  // normals, which lathes, spheres and tori have.
  function inked(geometry, material) {
    if (!geometry.getAttribute("outlineNormal")) geometry.setAttribute("outlineNormal", geometry.getAttribute("normal"));
    const mesh = new Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.add(new Mesh(geometry, ink));
    return mesh;
  }
  return { ramp, ink, toon, inked };
}

// Light flakes -- confetti, shards -- as one instanced mesh: each falls under
// real gravity against air drag (a paper square's fall settles at about a
// metre a second), flutters if asked, and lies where it lands or bounces
// if it is hard.
export class Flakes {
  constructor(parent, geometry, material, max, { floor = 0.05, bounce = 0 } = {}) {
    this.max = max;
    this.floor = floor;
    this.bounce = bounce;
    this.mesh = new InstancedMesh(geometry, material, max);
    this.mesh.instanceMatrix.setUsage(DynamicDrawUsage);
    this.mesh.frustumCulled = false;
    this.mesh.castShadow = true;
    this.mesh.count = 0;
    this.mesh.setColorAt(0, new Color(1, 1, 1));
    parent.add(this.mesh);
    const f = (n) => new Float32Array(max * n);
    Object.assign(this, { p: f(3), v: f(3), r: f(3), w: f(3), s: f(1), drag: f(1), flutter: f(1), phase: f(1) });
    this.flying = new Uint8Array(max);
    this.head = 0;
    this.n = 0;
    this.o = new Object3D();
    this.colour = new Color();
  }

  emit(p, v, { colour = "#ffffff", size = 1, drag = 1.5, flutter = 0, rand = Math.random } = {}) {
    const i = this.head;
    this.head = (i + 1) % this.max;
    this.n = Math.min(this.max, this.n + 1);
    this.mesh.count = this.n;
    const k = i * 3;
    this.p.set([p.x, p.y, p.z], k);
    this.v.set([v.x, v.y, v.z], k);
    this.r.set([rand() * 6.28, rand() * 6.28, rand() * 6.28], k);
    this.w.set([(rand() - 0.5) * 16, (rand() - 0.5) * 16, (rand() - 0.5) * 16], k);
    this.s[i] = size;
    this.drag[i] = drag;
    this.flutter[i] = flutter;
    this.phase[i] = rand() * 6.28;
    this.flying[i] = 1;
    this.mesh.setColorAt(i, this.colour.set(colour));
    this.mesh.instanceColor.needsUpdate = true;
    this.put(i);
  }

  put(i) {
    const k = i * 3;
    this.o.position.set(this.p[k], this.p[k + 1], this.p[k + 2]);
    this.o.rotation.set(this.r[k], this.r[k + 1], this.r[k + 2]);
    this.o.scale.setScalar(this.s[i]);
    this.o.updateMatrix();
    this.mesh.setMatrixAt(i, this.o.matrix);
  }

  update(dt, t) {
    let moved = false;
    for (let i = 0; i < this.n; i++) {
      if (!this.flying[i]) continue;
      moved = true;
      const k = i * 3;
      const slow = Math.exp(-this.drag[i] * dt);
      this.v[k + 1] -= G * dt;
      this.v[k] *= slow;
      this.v[k + 1] *= slow;
      this.v[k + 2] *= slow;
      const fl = this.flutter[i];
      if (fl) {
        this.v[k] += Math.sin(t * 4 + this.phase[i]) * fl * dt;
        this.v[k + 2] += Math.cos(t * 3.3 + this.phase[i] * 1.7) * fl * dt;
      }
      for (let a = 0; a < 3; a++) {
        this.p[k + a] += this.v[k + a] * dt;
        this.r[k + a] += this.w[k + a] * dt;
      }
      if (this.p[k + 1] <= this.floor) {
        this.p[k + 1] = this.floor;
        if (this.bounce > 0 && this.v[k + 1] < -80) {
          this.v[k + 1] *= -this.bounce;
          this.v[k] *= 0.7;
          this.v[k + 2] *= 0.7;
          for (let a = 0; a < 3; a++) this.w[k + a] *= 0.6;
        } else {
          // Lies where it fell, flat.
          this.flying[i] = 0;
          this.r[k] = -Math.PI / 2;
          this.r[k + 2] = 0;
        }
      }
      this.put(i);
    }
    if (moved) this.mesh.instanceMatrix.needsUpdate = true;
  }

  dispose() {
    this.mesh.removeFromParent();
    this.mesh.dispose();
  }
}
