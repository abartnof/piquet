// The parade: a little city rises out of the table, and the cards float down
// its street in a conga line, past a cheering crowd, under confetti thrown
// from the windows -- and at the far end of the street they swirl into a
// ring.
//
// From the prototype, and Andrew's notes on it: confetti, not ticker tape
// ("looks too much like sperm now" -- so small squares, nothing long and
// wiggly), and "the parade should never surpass the city limits": the parade
// gathers speed, cruises, and slows to a stop inside the city, where a last
// building closes the street. Here as a toy city on the table, in the page's
// pale colours with the ink line, sized so the cards are the floats: the
// street a metre wide, the buildings up to a metre and a half.

import { BoxGeometry, Color, ConeGeometry, DataTexture, Group, LinearMipmapLinearFilter, InstancedMesh, Object3D, PlaneGeometry, RepeatWrapping, SphereGeometry, SRGBColorSpace, Vector3 } from "three";
import { toss } from "../kinematics.js";
import { BRIGHTS, Flakes, PALETTE, kit } from "./kit.js";
import { clamp, hop, lerp, smooth, spin, turned } from "./physics.js";

const U = 5.5; // cm: the prototype's unit, for the city
const NEAR = 20 * U; // the city's near edge, along z
const FAR = -64 * U; // its far edge
const DRIVE = 40 * U; // how far the parade goes
const T0 = 1.0; // s: it sets off
const TRIP = 13.5; // s: and stops
const EO = (t) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);
const EIO = (t) => {
  const u = clamp(t, 0, 1);
  return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
};

// A facade: pale, with a grid of windows, some lit in the page's blue --
// drawn as plain pixels, so it needs no page to draw on.
function facade(rng) {
  const size = 128;
  const px = new Uint8Array(size * size * 4);
  const paint = (x0, y0, w, h, [r, g, b]) => {
    for (let y = y0; y < y0 + h; y++) for (let x = x0; x < x0 + w; x++) px.set([r, g, b, 255], (y * size + x) * 4);
  };
  paint(0, 0, size, size, [0xe8, 0xe7, 0xee]);
  for (let y = 0; y < 4; y++) {
    for (let x = 0; x < 4; x++) paint(x * 32 + 8, y * 32 + 7, 16, 18, rng() < 0.55 ? [0xd7, 0xe2, 0xff] : [0xc4, 0xc6, 0xd0]);
  }
  const texture = new DataTexture(px, size, size);
  texture.colorSpace = SRGBColorSpace;
  texture.wrapS = texture.wrapT = RepeatWrapping;
  texture.generateMipmaps = true;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.needsUpdate = true;
  return texture;
}

export function parade(ctx) {
  const { toon, inked } = kit(ctx.stage);
  const rng = ctx.random;
  const root = new Group();
  ctx.root.add(root);

  // The street: a pale strip with a dashed middle.
  const street = inked(new BoxGeometry(18 * U, 0.6, NEAR - FAR + 8 * U), toon("#dcdde5"), { box: true });
  street.position.set(0, 0.3, (NEAR + FAR) / 2);
  root.add(street);
  const dash = new BoxGeometry(0.8, 0.2, 8.8);
  const dashMaterial = toon(PALETTE.outline);
  for (let i = 0; i < 26; i++) {
    const d = inked(dash, dashMaterial, { box: true });
    d.position.set(0, 0.7, NEAR - 2 * U - i * 3.3 * U);
    root.add(d);
  }

  // The buildings, rising out of the table.
  const buildings = [];
  const roof = toon("#c4c6d0");
  function building(w, h, d, x, z, delay) {
    const texture = facade(rng);
    texture.repeat.set(w / (3.2 * U), h / (3.2 * U));
    const wall = toon("#ffffff", { map: texture });
    const mesh = inked(new BoxGeometry(w, h, d), [wall, wall, roof, roof, wall, wall], { box: true });
    mesh.position.set(x, -h / 2 - 3, z);
    mesh.userData = { up: h / 2, down: -h / 2 - 3, delay };
    root.add(mesh);
    buildings.push(mesh);
  }
  for (const side of [-1, 1]) {
    for (let k = 0; k < 14; k++) {
      const w = rng.range(4.2, 5.6) * U;
      building(w, rng.range(12, 26) * U, rng.range(5, 6) * U, side * (9.2 * U + w / 2), NEAR - 2 * U - k * 6.4 * U, 0.4 + k * 0.06);
    }
  }
  building(44 * U, 34 * U, 6 * U, 0, FAR - 7.5 * U, 1.2); // the city ends here

  // The crowd along both kerbs: little pawns in the page's colours, hopping.
  const CROWD = 300;
  const heads = new InstancedMesh(new SphereGeometry(0.16 * U, 10, 8), toon("#ffffff"), CROWD);
  const bodies = new InstancedMesh(new ConeGeometry(0.22 * U, 0.6 * U, 10), toon("#ffffff"), CROWD);
  heads.frustumCulled = bodies.frustumCulled = false;
  heads.castShadow = bodies.castShadow = true;
  root.add(heads, bodies);
  const crowd = [];
  const tint = new Color();
  for (let i = 0; i < CROWD; i++) {
    const side = i % 2 ? 1 : -1;
    crowd.push({ x: side * rng.range(6.4, 8.6) * U, z: rng.range(FAR + 2 * U, NEAR), phase: rng(), speed: rng.range(0.9, 1.5) });
    tint.set(rng.pick(BRIGHTS));
    heads.setColorAt(i, tint);
    bodies.setColorAt(i, tint);
  }
  const o = new Object3D();

  // Confetti: small paper squares, falling against the air at about a
  // metre a second, fluttering.
  const confetti = new Flakes(root, new PlaneGeometry(0.9, 0.9), toon("#ffffff", { side: 2 }), 9000, { floor: 0.7 });
  const throwFrom = (at, v) =>
    confetti.emit(at, v, { colour: rng.pick(BRIGHTS), size: rng.range(0.7, 1.6), drag: 12, flutter: 150, rand: rng });

  // The cards: tossed from the pile into the line, then floating along it.
  const cards = ctx.cards;
  const at = new Vector3();
  const slot = (j, t, lead) => at.set(Math.sin(t * 2.4 + j * 0.55) * 1.4 * U, 15 + Math.sin(t * 3.2 - j * 0.6) * 2.8, lead + j * 5.5);
  const joined = cards.map(() => false);
  const ways = cards.map((card, i) => {
    const j = 31 - i;
    return { start: T0 + j * 0.075, from: { position: card.position.clone(), quaternion: card.quaternion.clone() }, path: null };
  });

  // The key light travels with the parade, so its shadows do too.
  const key = ctx.stage.key;
  const keyAt = key ? { position: key.position.clone(), target: key.target.position.clone() } : null;
  let burst = false;
  let owed = 0;
  const eye = new Vector3();
  const look = new Vector3();
  return {
    update(dt, t) {
      for (const b of buildings) b.position.y = lerp(b.userData.down, b.userData.up, EO((t - b.userData.delay) / 1.3));
      // Gathers speed, cruises, and slows to a stop inside the city.
      const lead = -DRIVE * EIO((t - T0) / TRIP);
      if (key) {
        key.position.set(keyAt.position.x, keyAt.position.y, keyAt.position.z + lead);
        key.target.position.set(keyAt.target.x, keyAt.target.y, keyAt.target.z + lead);
        key.target.updateMatrixWorld();
      }
      if (!burst && t >= T0) {
        burst = true;
        for (let i = 0; i < 500; i++) throwFrom(new Vector3(0, 3, -6), new Vector3(rng.range(-60, 60), rng.range(250, 520), rng.range(-60, 60)));
      }
      if (t >= 1.2) {
        owed += dt * 650;
        while (owed >= 1) {
          owed -= 1;
          const side = rng() < 0.5 ? -1 : 1;
          throwFrom(new Vector3(side * 8.9 * U, rng.range(6, 24) * U, clamp(lead + rng.range(-16, 16) * U, FAR + 3 * U, NEAR)), new Vector3(-side * rng.range(3, 19), rng.range(-5, 11), rng.range(-5, 5)));
        }
      }
      const amp = 2.8 * smooth(2, 3, t);
      for (let i = 0; i < CROWD; i++) {
        const c = crowd[i];
        const j = hop(t * c.speed + c.phase) * amp;
        o.position.set(c.x, 0.3 * U + j, c.z);
        o.updateMatrix();
        bodies.setMatrixAt(i, o.matrix);
        o.position.set(c.x, 0.78 * U + j, c.z);
        o.updateMatrix();
        heads.setMatrixAt(i, o.matrix);
      }
      bodies.instanceMatrix.needsUpdate = true;
      heads.instanceMatrix.needsUpdate = true;

      // At the end of the street, the line swirls into a ring.
      const ring = smooth(13.6, 15.6, t);
      cards.forEach((card, i) => {
        const j = 31 - i;
        const w = ways[i];
        if (t < w.start) return;
        const p = slot(j, t, lead);
        if (ring > 0) {
          const a = (j / 32) * Math.PI * 2 + 1.1 * spin(t, 13.6, 18);
          p.set(lerp(p.x, Math.cos(a) * 20, ring), lerp(p.y, 24 + Math.sin(a * 3 + t) * 1.4, ring), lerp(p.z, lead + 11 + Math.sin(a) * 15, ring));
        }
        // Faces turned to the eye as it swings round, as performers play to
        // whoever is watching.
        const q = turned(0.1 * Math.sin(t * 2 + j), Math.PI * smooth(0.8, 5, t) + 0.35 * Math.sin(t * 2 + j), 0.15 * Math.sin(t * 3 + j));
        if (!joined[i]) {
          // Tossed up into the line, catching it up as it moves off.
          const u = (t - w.start) / 0.9;
          if (u < 1) {
            w.path = toss(w.from, { position: p.clone(), quaternion: q }, { clearance: 14 });
            const pose = w.path(Math.max(0, u));
            card.position.copy(pose.position);
            card.quaternion.copy(pose.quaternion);
            return;
          }
          joined[i] = true;
        }
        card.position.copy(p);
        card.quaternion.copy(q);
      });
      confetti.update(dt, t);

      // The eye swings round from behind the parade to walk backwards ahead
      // of it, looking back; and at the end stands back to see the ring.
      const a = Math.PI * smooth(0.8, 5, t);
      const fin = smooth(15, 19, t);
      const h = lerp(22, 38, smooth(1, 5, t)) + 14 * fin;
      const R = lerp(50, 55, smooth(1, 5, t)) + 17 * fin;
      eye.set(Math.sin(a) * 22, h, lead + R * Math.cos(a));
      look.set(0, lerp(11, 19, ring), lead + lerp(16 + (1 - Math.cos(a)) * 2.8, 11, ring));
      ctx.look(eye, look, 50);
    },
    dispose() {
      if (key) {
        key.position.copy(keyAt.position);
        key.target.position.copy(keyAt.target);
        key.target.updateMatrixWorld();
      }
      confetti.dispose();
      root.removeFromParent();
    },
  };
}
parade.title = "The parade";
