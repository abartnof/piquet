// Disco: the four aces stand up and dance on a floor that pulses to a beat;
// the other cards stand round in two arcs and bob; a mirror ball comes down,
// turning, throwing its glints and its spots of light.
//
// From the prototype, in Andrew's words: "the disco ball should be shinier.
// think about how actual disco balls are made of many small surfaces" -- so
// the ball is some five hundred flat mirror tiles, each lit afresh every frame
// from four lamps (a little diffuse, and a sharp highlight toward the eye
// when a tile catches a lamp), and the spots on the floor are true
// reflections: a lamp's ray, off a tile, down to the floor. Here in the
// table's bright look rather than a dark room -- the floor in the page's pale
// greys, its ripples and the spots in the page's colours -- and silent: the
// beat is one you can only see.

import { BoxGeometry, CircleGeometry, Color, CylinderGeometry, Group, InstancedMesh, Mesh, MeshBasicMaterial, Object3D, PlaneGeometry, SphereGeometry, Vector3 } from "three";
import { toss } from "../kinematics.js";
import { PALETTE, kit } from "./kit.js";
import { clamp, hop, lerp, lowestBelow, smooth, spin, turned } from "./physics.js";

const BPM = 118;
const START = 2.6; // s: the dance begins
const N = 10; // tiles a side
const TILE = 13.8; // cm
const BR = 11.6; // cm: the ball's radius
const ACE = 1.7; // the aces, stood up larger
const EO = (t) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);
const EIO = (t) => {
  const u = clamp(t, 0, 1);
  return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
};

// The four lamps round the room, and their colours.
const LAMPS = [
  { p: new Vector3(0, 142, 89), c: [1, 1, 1] },
  { p: new Vector3(0, 142, -89), c: [1, 0.86, 0.77] },
  { p: new Vector3(107, 116, 0), c: [0.84, 0.89, 1] },
  { p: new Vector3(-107, 116, 0), c: [0.98, 0.84, 0.99] },
];

// The aces' eight-beat routine: a sway, a lean, a spin, a jump, a bow.
function routine(bf) {
  const i = Math.floor(bf);
  const f = bf - i;
  const up = hop(f);
  let dx = 0;
  let y = 0;
  let yaw = 0;
  let lean = 0;
  let squash = 1;
  if (bf < 2) {
    dx = (i === 0 ? -1 : 1) * 3.1 * Math.sin(f * Math.PI);
    lean = (i === 0 ? -1 : 1) * 0.3 * Math.sin(f * Math.PI);
    y = up * 2.2;
  } else if (bf < 4) {
    lean = -0.6 + 0.12 * Math.sin(f * Math.PI * 2);
    y = i === 2 ? up * 4.5 : 1.3;
    yaw = 0.5;
  } else if (bf < 6) {
    yaw = EIO((bf - 4) / 2) * Math.PI * 2;
    y = up * 3.6;
  } else if (bf < 7) {
    y = up * 11.6;
    squash = 1 + 0.12 * Math.cos(f * Math.PI * 2);
  } else {
    lean = -0.35 * Math.sin(f * Math.PI);
    y = up * 1.8;
  }
  return { dx, y, yaw, lean, squash };
}

export function disco(ctx) {
  const { toon } = kit(ctx.stage);
  const root = new Group();
  ctx.root.add(root);

  // The floor: unlit tiles, as the table is, in the page's pale greys.
  const floor = new InstancedMesh(new BoxGeometry(TILE - 0.5, 0.4, TILE - 0.5), new MeshBasicMaterial({ color: 0xffffff }), N * N);
  floor.frustumCulled = false;
  root.add(floor);
  const o = new Object3D();
  const tone = new Color();
  const light = new Color(PALETTE.surface);
  const shade = new Color("#e2e2e9");
  const RIPPLES = ["#d7e2ff", "#fbd7fc", "#ffdcc4", "#b9f2f5"].map((c) => new Color(c));
  const PEAKS = [PALETTE.primary, PALETTE.tertiary, PALETTE.you, PALETTE.them].map((c) => new Color(c));
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      o.position.set((i - (N - 1) / 2) * TILE, 0.2, (j - (N - 1) / 2) * TILE);
      o.updateMatrix();
      floor.setMatrixAt(i * N + j, o.matrix);
      floor.setColorAt(i * N + j, light);
    }
  }

  // The mirror ball: a dark core under rings of small flat tiles, each facing
  // out along the sphere's normal.
  const ball = new Group();
  root.add(ball);
  ball.add(new Mesh(new SphereGeometry(BR - 0.3, 24, 16), toon(PALETTE.ink)));
  const nx = [];
  const ny = [];
  const nz = [];
  const RINGS = 20;
  for (let i = 0; i < RINGS; i++) {
    const lat = -Math.PI / 2 + ((i + 0.5) * Math.PI) / RINGS;
    const cl = Math.cos(lat);
    const count = Math.max(3, Math.round((Math.PI * 2 * BR * cl) / 1.78));
    for (let j = 0; j < count; j++) {
      const lon = ((j + (i % 2) * 0.5) / count) * Math.PI * 2;
      nx.push(cl * Math.cos(lon));
      ny.push(Math.sin(lat));
      nz.push(cl * Math.sin(lon));
    }
  }
  const M = nx.length;
  const mirrors = new InstancedMesh(new PlaneGeometry(1.5, 1.5), new MeshBasicMaterial({ color: 0xffffff, side: 2 }), M);
  mirrors.frustumCulled = false;
  const z = new Vector3(0, 0, 1);
  const n = new Vector3();
  for (let i = 0; i < M; i++) {
    n.set(nx[i], ny[i], nz[i]);
    o.position.copy(n).multiplyScalar(BR + 0.05);
    o.quaternion.setFromUnitVectors(z, n);
    o.updateMatrix();
    mirrors.setMatrixAt(i, o.matrix);
    mirrors.setColorAt(i, tone.set("#9aa0ab"));
  }
  ball.add(mirrors);
  const cord = new Mesh(new CylinderGeometry(0.25, 0.25, 260, 6), toon(PALETTE.outline));
  cord.position.y = BR + 130;
  ball.add(cord);

  // Spots of reflected light on the floor, in the lamps' colours.
  const spotGeometry = new CircleGeometry(2.7, 16);
  const spotMaterials = [PALETTE.primary, PALETTE.you, PALETTE.them, PALETTE.tertiary].map((c) => new MeshBasicMaterial({ color: c, transparent: true, opacity: 0.55, depthWrite: false }));
  const spots = [];
  for (let i = 0; i < 72; i++) {
    const m = new Mesh(spotGeometry, spotMaterials[i % 4]);
    m.rotation.x = -Math.PI / 2;
    m.position.y = 0.45;
    m.visible = false;
    root.add(m);
    spots.push({ m, tile: Math.floor((i * M) / 72), lamp: i % 4 });
  }

  function shine(th, by) {
    const ct = Math.cos(th);
    const st = Math.sin(th);
    const cp = ctx.camera.position;
    for (let i = 0; i < M; i++) {
      const wx = nx[i] * ct + nz[i] * st;
      const wy = ny[i];
      const wz = -nx[i] * st + nz[i] * ct;
      const px = wx * BR;
      const py = by + wy * BR;
      const pz = wz * BR;
      let vx = cp.x - px;
      let vy = cp.y - py;
      let vz = cp.z - pz;
      const vl = Math.hypot(vx, vy, vz) || 1;
      vx /= vl;
      vy /= vl;
      vz /= vl;
      // Silver at rest; a lamp adds a little diffuse, and a sharp glint when
      // the tile sits between the lamp and the eye.
      let r = 0.52;
      let g = 0.54;
      let b = 0.58;
      for (const lamp of LAMPS) {
        let lx = lamp.p.x - px;
        let ly = lamp.p.y - py;
        let lz = lamp.p.z - pz;
        const ll = Math.hypot(lx, ly, lz);
        lx /= ll;
        ly /= ll;
        lz /= ll;
        const nl = wx * lx + wy * ly + wz * lz;
        if (nl <= 0) continue;
        const hx = lx + vx;
        const hy = ly + vy;
        const hz = lz + vz;
        const hl = Math.hypot(hx, hy, hz) || 1;
        const nh = (wx * hx + wy * hy + wz * hz) / hl;
        const k = 0.12 * nl + (nh > 0 ? 3.2 * Math.pow(nh, 45) : 0);
        r += lamp.c[0] * k;
        g += lamp.c[1] * k;
        b += lamp.c[2] * k;
      }
      mirrors.setColorAt(i, tone.setRGB(Math.min(1, r), Math.min(1, g), Math.min(1, b)));
    }
    mirrors.instanceColor.needsUpdate = true;
    for (const s of spots) {
      const i = s.tile;
      const wx = nx[i] * ct + nz[i] * st;
      const wy = ny[i];
      const wz = -nx[i] * st + nz[i] * ct;
      const px = wx * BR;
      const py = by + wy * BR;
      const pz = wz * BR;
      const lamp = LAMPS[s.lamp].p;
      let dx = px - lamp.x;
      let dy = py - lamp.y;
      let dz = pz - lamp.z;
      const dl = Math.hypot(dx, dy, dz);
      dx /= dl;
      dy /= dl;
      dz /= dl;
      const dn = dx * wx + dy * wy + dz * wz;
      if (dn >= 0) {
        s.m.visible = false;
        continue;
      }
      // The lamp's ray, reflected off the tile, to the floor.
      const rx = dx - 2 * dn * wx;
      const ry = dy - 2 * dn * wy;
      const rz = dz - 2 * dn * wz;
      if (ry >= -0.05) {
        s.m.visible = false;
        continue;
      }
      const k = (0.45 - py) / ry;
      const hx = px + k * rx;
      const hz = pz + k * rz;
      if (Math.hypot(hx, hz) > 73) {
        s.m.visible = false;
        continue;
      }
      s.m.visible = true;
      s.m.position.x = hx;
      s.m.position.z = hz;
      s.m.scale.setScalar(0.6 - dn * 0.7);
    }
  }

  // The aces dance in front; the rest stand round in two arcs behind.
  const cards = ctx.cards;
  const aces = cards.filter((c) => c.userData.code?.[0] === "A");
  const others = cards.filter((c) => c.userData.code?.[0] !== "A");
  const ACES_AT = [-32, -11, 11, 32];
  const aceScale = (squash) => new Vector3(ACE, ACE * squash, ACE);
  function acePose(k, beat) {
    const m = routine(beat % 8);
    const q = turned(0, m.yaw, m.lean);
    const s = aceScale(m.squash);
    return { position: new Vector3(ACES_AT[k] + m.dx, lowestBelow(q, s) + 0.4 + m.y, 5), quaternion: q, scale: s };
  }
  function standPose(k, beat, live) {
    const row = k < 14 ? 0 : 1;
    const idx = row ? k - 14 : k;
    const a = lerp(-1, 1, idx / 13) * (row ? 1.05 : 0.9);
    const R = row ? 77 : 64;
    const q = turned(0, -a * 0.6 + 0.25 * Math.sin(beat * Math.PI * 0.5 + idx) * live, 0.15 * Math.sin(beat * Math.PI + idx * 0.6) * live);
    const up = hop(beat + idx * 0.13) * 2.2 * live;
    return { position: new Vector3(Math.sin(a) * R, lowestBelow(q) + 0.4 + up, -Math.cos(a) * R * 0.55 - 11 - row * 11.6), quaternion: q, scale: new Vector3(1, 1, 1) };
  }
  // Each card's way from the pile to its first place.
  const ways = cards.map((card, i) => {
    const target = aces.includes(card) ? acePose(aces.indexOf(card), 0) : standPose(others.indexOf(card), 0, 0);
    return { path: toss({ position: card.position.clone(), quaternion: card.quaternion.clone() }, target, { clearance: 18 }), start: 0.5 + i * 0.03, target };
  });

  const eye = new Vector3();
  const at = new Vector3(0, 30, -9);
  return {
    update(dt, t) {
      const bt = t - START;
      const beat = Math.max(0, bt) * (BPM / 60);
      const pulse = Math.exp(-(beat - Math.floor(beat)) * 4);
      const by = lerp(169, 60, EO((t - 0.6) / 2.2));
      ball.position.set(0, by, 0);
      const th = 1.1 * spin(t, 0.6, 3.5);
      ball.rotation.y = th;
      shine(th, by);

      // The floor: a checker that shifts on the half-beat, and ripples of
      // colour spreading from the middle on the beat.
      const bar = Math.floor(beat / 4) % 4;
      for (let i = 0; i < N; i++) {
        for (let j = 0; j < N; j++) {
          const d = Math.hypot(i - (N - 1) / 2, j - (N - 1) / 2);
          const v = Math.sin(d * 1.2 - beat * Math.PI) * 0.5 + 0.5;
          const checker = (i + j + Math.floor(beat * 2)) % 2 === 0;
          const on = smooth(0.8, 2.2, t - d * 0.05);
          tone.copy(checker ? light : shade);
          if (v > 0.66) tone.lerp(RIPPLES[bar], ((v - 0.66) / 0.34) * on);
          if (v > 0.95 && checker) tone.lerp(PEAKS[bar], 0.45 * on);
          floor.setColorAt(i * N + j, tone);
        }
      }
      floor.instanceColor.needsUpdate = true;

      cards.forEach((card, i) => {
        const w = ways[i];
        const u = (t - w.start) / 0.9;
        if (u < 1) {
          if (u <= 0) return;
          const p = w.path(u);
          card.position.copy(p.position);
          card.quaternion.copy(p.quaternion);
          card.scale.lerpVectors(new Vector3(1, 1, 1), w.target.scale, u);
          return;
        }
        const k = aces.indexOf(card);
        const live = smooth(START - 0.5, START, t);
        const p = k >= 0 ? acePose(k, bt >= 0 ? beat : 0) : standPose(others.indexOf(card), beat, live);
        card.position.copy(p.position);
        card.quaternion.copy(p.quaternion);
        card.scale.copy(p.scale);
      });

      // The eye sways gently round the floor, and nods with the beat.
      const a = Math.sin(t * 0.4) * 0.6;
      const R = lerp(80, 134, smooth(0.2, 2.5, t)) - pulse * 3.5 * smooth(START, START + 1, t);
      const H = lerp(40, 58, smooth(0.2, 2.5, t));
      eye.set(Math.sin(a) * R, H, Math.cos(a) * R);
      ctx.look(eye, at, 45);
    },
    dispose() {
      root.removeFromParent();
    },
  };
}
disco.title = "Disco";
