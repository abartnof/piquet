// Cup and ball: the pile becomes the toy -- a cup (eight cards round, one
// for its base, three for its handle) and a ball (twenty small cards on a
// sphere), joined by a string. You swing the cup with the pointer and try
// to catch the ball in it.
//
// From the prototype, in Andrew's words: "the cards turn into a cup and a
// ball, attached by a string. the user jiggles the cup around and tries to
// swing the ball into the cup. give the ball weight and make it swing around
// somewhat realistically" -- and "can't be played with a keyboard, that's a
// mouse/fingertip one". Here at a real toy's size: a cup 13 cm across, a
// ball 8 cm across, a string of 27 cm, and real gravity, so the ball swings
// about once a second as a real one does.
//
// The physics, as the prototype had it: the string cannot stretch (the ball
// is held to its length, and the snap tugs the cup -- that is its weight);
// the ball strikes the cup's base, wall and rim relative to the cup's own
// motion, so it can be caught, bounced, balanced or tossed; the cup follows
// the pointer on a critically damped spring and tilts with its speed. One
// honest cheat: a gentle pull toward the cup's plane, since a pointer on a
// screen cannot move the cup in depth.

import { BoxGeometry, BufferAttribute, BufferGeometry, DoubleSide, Group, Mesh, MeshBasicMaterial, Plane, Quaternion, Vector3 } from "three";
import { minimumJerk } from "../easing.js";
import { toss } from "../kinematics.js";
import { INK } from "../materials.js";
import { BRIGHTS, Flakes, kit } from "./kit.js";
import { G, clamp, lerp, turned } from "./physics.js";

const RIN = 6.7; // cm: the cup's inner radius
const DEPTH = 7.8; // cm
const RB = 4.0; // cm: the ball's radius
const FLOOR = 4.4; // cm: the ball's lowest card clears the table here
const L = 26.7; // cm: the string
const B0 = new Vector3(0, 41, 0); // where the cup is made
const GRIP = 8; // cm: the pointer holds the cup by its handle, this far below
const PLAY = 3.0; // s: the toy is made
const CAMD = 100; // cm: the eye's distance

export function cupball(ctx) {
  const { toon } = kit(ctx.stage);
  const rng = ctx.random;
  const root = new Group();
  ctx.root.add(root);
  const cupG = new Group();
  cupG.position.copy(B0);
  const ballG = new Group();
  ballG.position.set(0, B0.y - 0.4 - L, 0);
  root.add(cupG, ballG);

  // Where each card goes, in its part's own frame, and how it is scaled.
  const slots = [];
  let next = 31;
  const slot = (group, position, quaternion, scale, delay) => slots.push({ card: ctx.cards[next--], group, position, quaternion, scale, delay });
  for (let i = 0; i < 8; i++) {
    const th = (i / 8) * Math.PI * 2;
    slot(cupG, new Vector3(RIN * Math.cos(th), DEPTH / 2, RIN * Math.sin(th)), turned(0, Math.PI / 2 - th, 0), new Vector3(0.88, 0.88, 1), i * 0.04);
  }
  slot(cupG, new Vector3(0, 0.1, 0), turned(-Math.PI / 2, 0, 0), new Vector3(1.2, 1.2, 1), 0.34);
  for (let k = 0; k < 3; k++) slot(cupG, new Vector3(0, -2.8 - k * 5.3, 0), turned(0, 0, 0), new Vector3(0.36, 0.6, 1), 0.4 + k * 0.04);
  const z = new Vector3(0, 0, 1);
  for (let i = 0; i < 20; i++) {
    const y = 1 - ((i + 0.5) * 2) / 20;
    const r = Math.sqrt(1 - y * y);
    const phase = i * 2.39996;
    const dir = new Vector3(Math.cos(phase) * r, y, Math.sin(phase) * r);
    const q = new Quaternion().setFromUnitVectors(z, dir).premultiply(new Quaternion().setFromAxisAngle(dir, rng.range(0, Math.PI * 2)));
    slot(ballG, dir.multiplyScalar(RB * 0.94), q, new Vector3(0.42, 0.42, 1), 0.5 + i * 0.03);
  }
  // Tossed from the pile to where they belong, shrinking or growing on the
  // way; then made part of the cup or the ball.
  for (const s of slots) {
    const world = { position: s.position.clone().add(s.group.position), quaternion: s.quaternion.clone() };
    s.path = toss({ position: s.card.position.clone(), quaternion: s.card.quaternion.clone() }, world, { clearance: 10 });
    s.start = 0.4 + s.delay;
    s.length = 0.9;
  }
  let built = false;

  const cup = { p: B0.clone(), v: new Vector3(), phi: 0, yank: new Vector3(), yv: new Vector3() };
  const ball = { p: ballG.position.clone(), v: new Vector3() };
  let tx = 0;
  let ty = B0.y - GRIP;
  let catches = 0;
  let armed = true;
  let hold = 0;
  let out = 0;
  const confetti = new Flakes(root, new BoxGeometry(1.4, 0.02, 0.9), toon("#ffffff"), 400, { floor: 0.03 });
  const tally = () => ctx.hud.score(`Catches ${catches}`);
  tally();

  // The string: a light rope pinned to the cup and the ball, drawn as a thin
  // ribbon always turned to the eye, in the ink.
  const RN = 14;
  const P = [];
  const Q = [];
  const ropePos = new Float32Array((RN + 1) * 6);
  const ropeGeo = new BufferGeometry();
  ropeGeo.setAttribute("position", new BufferAttribute(ropePos, 3));
  const index = [];
  for (let k = 0; k < RN; k++) index.push(k * 2, k * 2 + 1, k * 2 + 2, k * 2 + 1, k * 2 + 3, k * 2 + 2);
  ropeGeo.setIndex(index);
  const rope = new Mesh(ropeGeo, new MeshBasicMaterial({ color: INK, side: DoubleSide }));
  rope.frustumCulled = false;
  rope.visible = false;
  root.add(rope);
  const anchor = () => new Vector3(cup.p.x + 0.4 * Math.sin(cup.phi), cup.p.y - 0.4 * Math.cos(cup.phi), cup.p.z);
  {
    const a = anchor();
    for (let i = 0; i <= RN; i++) {
      const p = a.clone().lerp(ball.p, i / RN);
      P.push(p);
      Q.push(p.clone());
    }
  }

  // The pointer only.
  const plane = new Plane(new Vector3(0, 0, 1), 0);
  const under = new Vector3();
  const aim = () => {
    const p = ctx.on(plane, under);
    if (p) {
      tx = p.x;
      ty = p.y;
    }
  };
  const canvas = ctx.stage.renderer.domElement;
  ctx.listen(canvas, "pointermove", aim);
  ctx.listen(canvas, "pointerdown", aim);

  function collide(h) {
    const c = Math.cos(cup.phi);
    const s = Math.sin(cup.phi);
    const d = ball.p.clone().sub(cup.p);
    let lx = c * d.x + s * d.y;
    let ly = -s * d.x + c * d.y;
    let lz = d.z;
    const rv = ball.v.clone().sub(cup.v);
    let vx = c * rv.x + s * rv.y;
    let vy = -s * rv.x + c * rv.y;
    let vz = rv.z;
    const resolve = (nx, ny, nz) => {
      const vn = vx * nx + vy * ny + vz * nz;
      if (vn < 0) {
        const e = 0.3;
        vx -= (1 + e) * vn * nx;
        vy -= (1 + e) * vn * ny;
        vz -= (1 + e) * vn * nz;
        const f = Math.exp(-1.5 * h);
        vx *= f;
        vz *= f;
      }
    };
    let rho = Math.hypot(lx, lz) || 1e-6;
    let ux = lx / rho;
    let uz = lz / rho;
    if (rho < RIN) {
      // The base.
      if (ly >= 0 && ly < RB) {
        ly = RB;
        resolve(0, 1, 0);
      } else if (ly < 0 && ly > -RB) {
        ly = -RB;
        resolve(0, -1, 0);
      }
    }
    if (ly > 0 && ly < DEPTH) {
      // The wall, inside or out.
      if (rho < RIN && rho > RIN - RB) {
        lx = ux * (RIN - RB);
        lz = uz * (RIN - RB);
        resolve(-ux, 0, -uz);
      } else if (rho >= RIN && rho < RIN + RB) {
        lx = ux * (RIN + RB);
        lz = uz * (RIN + RB);
        resolve(ux, 0, uz);
      }
    }
    rho = Math.hypot(lx, lz) || 1e-6;
    ux = lx / rho;
    uz = lz / rho;
    {
      // The rim.
      const dr = rho - RIN;
      const dh = ly - DEPTH;
      const dd = Math.hypot(dr, dh);
      if (ly >= DEPTH && dd < RB && dd > 1e-6) {
        const nr = dr / dd;
        const ny = dh / dd;
        const push = RB - dd;
        lx += ux * nr * push;
        lz += uz * nr * push;
        ly += ny * push;
        resolve(ux * nr, ny, uz * nr);
      }
    }
    ball.p.set(cup.p.x + c * lx - s * ly, cup.p.y + s * lx + c * ly, cup.p.z + lz);
    ball.v.set(cup.v.x + c * vx - s * vy, cup.v.y + s * vx + c * vy, cup.v.z + vz);
  }

  function tether() {
    const a = anchor();
    const d = ball.p.clone().sub(a);
    const dist = d.length() || 1e-6;
    if (dist <= L) return;
    const n = d.divideScalar(dist);
    ball.p.copy(a).addScaledVector(n, L);
    const vr = ball.v.clone().sub(cup.v).dot(n);
    if (vr > 0) {
      ball.v.addScaledVector(n, -vr * 1.1);
      // The snap of the string tugs the cup: the ball's weight in your hand.
      if (vr > 27) cup.yv.addScaledVector(new Vector3(n.x, n.y, 0), vr * 0.3);
    }
  }

  function step(h, reach) {
    const W = 26;
    const gx = clamp(tx, -reach, reach);
    const gy = clamp(ty + GRIP, 17, 71);
    cup.v.x += (W * W * (gx - cup.p.x) - 2 * W * cup.v.x) * h;
    cup.v.y += (W * W * (gy - cup.p.y) - 2 * W * cup.v.y) * h;
    cup.p.x += cup.v.x * h;
    cup.p.y += cup.v.y * h;
    cup.phi += (clamp(-cup.v.x * 0.005, -0.6, 0.6) - cup.phi) * Math.min(1, h * 10);
    ball.v.y -= G * h;
    ball.v.z += (-6 * ball.p.z - 1.5 * ball.v.z) * h;
    ball.v.multiplyScalar(Math.exp(-0.12 * h));
    ball.p.addScaledVector(ball.v, h);
    if (ball.p.y < FLOOR) {
      ball.p.y = FLOOR;
      if (ball.v.y < 0) ball.v.y *= -0.35;
      const f = Math.exp(-3 * h);
      ball.v.x *= f;
      ball.v.z *= f;
    }
    collide(h);
    tether();
    const W2 = 18;
    cup.yv.x += (-W2 * W2 * cup.yank.x - 2 * W2 * cup.yv.x) * h;
    cup.yv.y += (-W2 * W2 * cup.yank.y - 2 * W2 * cup.yv.y) * h;
    cup.yank.x += cup.yv.x * h;
    cup.yank.y += cup.yv.y * h;
  }

  // Where the ball is in the cup's own frame, and how fast relative to it.
  function inCup() {
    const c = Math.cos(cup.phi);
    const s = Math.sin(cup.phi);
    const d = ball.p.clone().sub(cup.p);
    const x = c * d.x + s * d.y;
    const y = -s * d.x + c * d.y;
    const speed = ball.v.clone().sub(cup.v).length();
    const inside = Math.hypot(x, d.z) < RIN - 0.45 && y > 0 && y < DEPTH + RB;
    return { inside, settled: inside && y < RB + 1.3 && speed < 22 };
  }

  function caught() {
    catches += 1;
    tally();
    const mouth = new Vector3(cup.p.x - DEPTH * Math.sin(cup.phi), cup.p.y + DEPTH * Math.cos(cup.phi), 0);
    ctx.hud.burst(mouth.clone().add(new Vector3(0, 14, 0)), "PIQUET!", { size: 1.2 });
    for (let i = 0; i < 40; i++) {
      const a = rng.range(0, Math.PI * 2);
      const speed = rng.range(20, 70);
      confetti.emit(mouth, new Vector3(Math.cos(a) * speed, rng.range(140, 320), Math.sin(a) * speed * 0.4), {
        colour: rng.pick(BRIGHTS), size: rng.range(1.2, 2), drag: 3, flutter: 150, rand: rng,
      });
    }
  }

  const eye = new Vector3();
  const at = new Vector3();
  const spinAxis = new Vector3();
  return {
    update(dt, t) {
      if (!built) {
        for (const s of slots) {
          const u = clamp((t - s.start) / s.length, 0, 1);
          if (t < s.start) continue;
          const p = s.path(u);
          s.card.position.copy(p.position);
          s.card.quaternion.copy(p.quaternion);
          s.card.scale.set(lerp(1, s.scale.x, u), lerp(1, s.scale.y, u), 1);
        }
        if (slots.every((s) => t >= s.start + s.length)) {
          built = true;
          for (const s of slots) s.group.attach(s.card);
        }
      }
      rope.visible = t > 2.4;
      const reach = Math.min(67, Math.tan((22.5 * Math.PI) / 180) * CAMD * ctx.camera.aspect * 0.9);
      if (t >= PLAY && built) {
        const n = Math.min(14, Math.max(4, Math.ceil(dt / 0.004)));
        for (let i = 0; i < n; i++) step(dt / n, reach);
        const where = inCup();
        hold = where.settled ? hold + dt : 0;
        if (armed && hold > 0.35) {
          armed = false;
          caught();
        }
        out = where.inside ? 0 : out + dt;
        if (!armed && out > 0.4) armed = true;
      }
      cupG.position.set(cup.p.x + cup.yank.x, cup.p.y + cup.yank.y, cup.p.z);
      cupG.rotation.z = cup.phi;
      ballG.position.copy(ball.p);
      const sp = Math.hypot(ball.v.x, ball.v.z);
      if (sp > 0.01 && t >= PLAY) ballG.rotateOnWorldAxis(spinAxis.set(ball.v.z / sp, 0, -ball.v.x / sp), (sp / RB) * dt * 0.4);

      // The string: its ends pinned, its middle a rope under gravity.
      P[0].copy(anchor());
      P[RN].copy(ball.p);
      const seg = L / RN;
      const damp = Math.exp(-2 * dt);
      for (let i = 1; i < RN; i++) {
        const v = P[i].clone().sub(Q[i]).multiplyScalar(damp);
        Q[i].copy(P[i]);
        P[i].add(v);
        P[i].y -= G * 0.6 * dt * dt;
      }
      for (let it = 0; it < 6; it++) {
        for (let i = 0; i < RN; i++) {
          const A = P[i];
          const B = P[i + 1];
          const d = B.clone().sub(A);
          const len = d.length() || 1e-6;
          if (len <= seg) continue;
          const wa = i === 0 ? 0 : 0.5;
          const wb = i + 1 === RN ? 0 : 0.5;
          const share = wa + wb || 1;
          const f = (len - seg) / len;
          A.addScaledVector(d, (f * wa) / share);
          B.addScaledVector(d, (-f * wb) / share);
        }
      }
      for (let i = 1; i < RN; i++) if (P[i].y < 0.3) P[i].y = 0.3;
      const cp = ctx.camera.position;
      for (let i = 0; i <= RN; i++) {
        const along = P[Math.min(RN, i + 1)].clone().sub(P[Math.max(0, i - 1)]);
        const side = along.cross(cp.clone().sub(P[i]));
        side.multiplyScalar(0.16 / (side.length() || 1));
        ropePos.set([P[i].x + side.x, P[i].y + side.y, P[i].z + side.z, P[i].x - side.x, P[i].y - side.y, P[i].z - side.z], i * 6);
      }
      ropeGeo.attributes.position.needsUpdate = true;
      confetti.update(dt, t);

      // The eye: from the table's view, round to face the toy.
      const k = minimumJerk(clamp((t - 0.2) / 2, 0, 1));
      eye.set(0, lerp(55, 39, k), lerp(60, CAMD, k));
      at.set(0, lerp(0, 38, k), 0);
      ctx.look(eye, at, lerp(40, 45, k));
    },
    dispose() {
      confetti.dispose();
      root.removeFromParent();
    },
  };
}
cupball.title = "Cup and ball";
cupball.how = "Swing the cup with your mouse or finger, and catch the ball";
cupball.interactive = true;
