// Card pong: one card each for the paddles, one for the ball, and the other
// twenty-nine standing along the front of the table, cheering. You against
// your opponent, first to five.
//
// From the prototype, in Andrew's words: "one card per paddle, one card as
// the ball, the other cards cheering at the bottom of the screen. players can
// drag their card with mouse/finger or use the up/down arrow keys" -- one
// player, against the computer. Here at the table's scale: the paddles are
// cards held 1.6 times up, 68 cm either side of the middle; the ball starts
// at two-thirds of a metre a second and quickens with every hit.

import { BoxGeometry, Group, Mesh, Plane, Vector3 } from "three";
import { toss } from "../kinematics.js";
import { CARD } from "../units.js";
import { BRIGHTS, Flakes, Moves, PALETTE, kit } from "./kit.js";
import { clamp, hop, lerp, lowestBelow, smooth, turned } from "./physics.js";

const XL = 68; // cm: each paddle's distance from the middle
const ZH = 39; // cm: the court's half-depth
const SCALE = 1.6; // the paddles, held larger
const HALF = (CARD.height * SCALE) / 2; // a paddle's half-length along the court
const THICK = (CARD.width * SCALE) / 2;
const BALL = 0.62; // the ball: a small card
const BR = (CARD.width * BALL) / 2;
const LIMIT = ZH - 2 - HALF;
const WIN = 5;
const START = 2.6; // s: the cards are in their places

export function pong(ctx) {
  const { toon } = kit(ctx.stage);
  const rng = ctx.random;
  const root = new Group();
  ctx.root.add(root);
  const cards = ctx.cards;
  const [you, them, ball] = [cards[31], cards[30], cards[29]];
  const crowd = cards.slice(0, 29);

  // The court, lightly drawn: its sides and a dashed middle, in the page's
  // outline grey.
  const line = toon(PALETTE.outline);
  const dash = new BoxGeometry(1.2, 0.05, 4.4);
  for (let i = 0; i < 9; i++) {
    const mesh = new Mesh(dash, line);
    mesh.position.set(0, 0.03, -ZH + 4.4 + (i * (2 * ZH - 8.8)) / 8);
    root.add(mesh);
  }
  const edge = new BoxGeometry(2 * XL + 22, 0.1, 1.1);
  for (const s of [-1, 1]) {
    const side = new Mesh(edge, line);
    side.position.set(0, 0.05, s * (ZH + 1.4));
    root.add(side);
  }

  const confetti = new Flakes(root, new BoxGeometry(1.4, 0.02, 0.9), toon("#ffffff"), 700, { floor: 0.03 });

  // To their places: the paddles and the ball flat on the court, the crowd
  // standing in two rows along the front, facing you.
  const moves = new Moves();
  const flat = (x, z, scale = 1) => ({ position: new Vector3(x, (CARD.thickness / 2) * scale, z), quaternion: turned(-Math.PI / 2, 0, 0) });
  const place = (mesh, to, start) => moves.add(mesh, toss({ position: mesh.position.clone(), quaternion: mesh.quaternion.clone() }, to, { clearance: 14 }), start, 0.8);
  place(you, flat(-XL, 0), 0.3);
  place(them, flat(XL, 0), 0.4);
  place(ball, flat(0, 0), 0.6);
  const seat = crowd.map((_, i) => {
    const row = i < 15 ? 0 : 1;
    const n = row ? 14 : 15;
    const index = row ? i - 15 : i;
    return { x: lerp(-76, 76, index / (n - 1)) + row * 5.4, z: 49 + row * 8 };
  });
  // Leaning back to face you, as a held card faces its holder.
  const LEAN = -0.85;
  crowd.forEach((card, i) => {
    const q = turned(LEAN, 0, 0);
    place(card, { position: new Vector3(seat[i].x, lowestBelow(q), seat[i].z), quaternion: q }, 0.8 + i * 0.04);
  });

  const S = { you: 0, them: 0, phase: "intro", bx: 0, bz: 0, vx: 0, vz: 0, speed: 67, aimYou: 0, aimThem: 0, zYou: 0, zThem: 0, serveAt: 0, rally: 0, cheer: 0.15, boost: 0, errAt: 0, err: 0, hitYou: 0, hitThem: 0 };
  const tally = () => ctx.hud.score(`You ${S.you} · ${S.them} Your opponent`);
  tally();

  const table = new Plane(new Vector3(0, 1, 0), 0);
  const under = new Vector3();
  const follow = () => {
    const p = ctx.on(table, under);
    if (p) S.aimYou = clamp(p.z, -LIMIT, LIMIT);
  };
  const canvas = ctx.stage.renderer.domElement;
  ctx.listen(canvas, "pointerdown", follow);
  ctx.listen(canvas, "pointermove", () => ctx.pointer.down && follow());

  function serve(toward) {
    S.bx = 0;
    S.bz = rng.range(-13, 13);
    S.speed = 67;
    S.rally = 0;
    const a = rng.range(-0.5, 0.5);
    S.vx = toward * Math.cos(a) * S.speed;
    S.vz = Math.sin(a) * S.speed;
    S.phase = "play";
  }

  function goal(side) {
    S[side] += 1;
    S.boost = 1;
    S.phase = "wait";
    tally();
    const from = side === "you" ? XL : -XL;
    for (let i = 0; i < 50; i++) {
      confetti.emit(new Vector3(from, 4, rng.range(-26, 26)), new Vector3(rng.range(-40, 40), rng.range(300, 520), rng.range(-40, 40)), {
        colour: rng.pick(BRIGHTS), drag: 3, flutter: 160, rand: rng,
      });
    }
    ctx.hud.burst(new Vector3(from * 0.8, 10, 0), side === "you" ? "PIQUET!" : "Point!", { size: 1.1 });
    if (S.you >= WIN || S.them >= WIN) {
      S.phase = "over";
      S.cheer = 1;
      for (let i = 0; i < 320; i++) {
        confetti.emit(new Vector3(rng.range(-80, 80), rng.range(90, 140), rng.range(-40, 40)), new Vector3(rng.range(-30, 30), 0, rng.range(-30, 30)), {
          colour: rng.pick(BRIGHTS), drag: 6, flutter: 240, rand: rng,
        });
      }
      ctx.hud.message(S.you >= WIN ? "You win" : "Your opponent wins", { label: "Play again", fn: () => ctx.again() });
    } else {
      S.serveAt = clock + 1.3;
    }
  }

  let clock = 0;
  const eye = new Vector3();
  const at = new Vector3();
  return {
    update(dt, t) {
      clock = t;
      moves.update(t);

      // The crowd hops -- real parabolas, higher as the rally grows.
      S.boost *= Math.exp(-1.6 * dt);
      if (S.phase !== "over") S.cheer = 0.15 + Math.min(0.6, S.rally * 0.06) + S.boost * 0.7;
      crowd.forEach((card, i) => {
        if (moves.moving(card)) return;
        const up = hop(t * (1.6 + (i % 5) * 0.2) + i * 0.13) * S.cheer * 8;
        const spin = S.boost > 0.4 ? Math.sin(t * 10 + i) * 0.4 : 0;
        card.quaternion.copy(turned(LEAN, spin + 0.2 * Math.sin(t * 3 + i), 0.12 * Math.sin(t * 6 + i)));
        // Standing on its lowest corner as it leans, never through the table.
        card.position.set(seat[i].x, lowestBelow(card.quaternion) + up, seat[i].z);
      });

      if (S.phase === "intro" && t >= START) {
        S.phase = "wait";
        S.serveAt = t + 0.9;
        ctx.hud.burst(new Vector3(0, 8, 0), "Ready", { size: 1.1 });
      }
      if (S.phase === "wait" && t >= S.serveAt) serve(rng() < 0.5 ? -1 : 1);

      if (t >= START) {
        // You: the pointer, or the up and down arrows.
        if (ctx.keys.has("ArrowUp")) S.aimYou -= 115 * dt;
        if (ctx.keys.has("ArrowDown")) S.aimYou += 115 * dt;
        S.aimYou = clamp(S.aimYou, -LIMIT, LIMIT);
        // Your opponent follows the ball, with an aim that wanders and a
        // limited speed, so it can be beaten.
        if (S.phase === "play" && S.vx > 0) {
          if (t - S.errAt > 0.22) {
            S.errAt = t;
            S.err = rng.range(-1, 1) * (3 + S.speed * 0.05);
          }
          S.aimThem = clamp(S.bz + S.err, -LIMIT, LIMIT);
        } else S.aimThem = lerp(S.aimThem, 0, Math.min(1, dt * 1.5));
        S.zYou += clamp(S.aimYou - S.zYou, -210 * dt, 210 * dt);
        S.zThem += clamp(S.aimThem - S.zThem, -74 * dt, 74 * dt);
        S.hitYou *= Math.exp(-10 * dt);
        S.hitThem *= Math.exp(-10 * dt);
        you.position.set(-XL, (CARD.thickness / 2) * SCALE, S.zYou);
        them.position.set(XL, (CARD.thickness / 2) * SCALE, S.zThem);
        you.quaternion.copy(turned(-Math.PI / 2, 0, 0));
        them.quaternion.copy(turned(-Math.PI / 2, 0, 0));
        you.scale.setScalar(SCALE * (1 + 0.18 * S.hitYou));
        them.scale.setScalar(SCALE * (1 + 0.18 * S.hitThem));
      }

      if (S.phase === "play") {
        S.bx += S.vx * dt;
        S.bz += S.vz * dt;
        if (S.bz > ZH - BR) {
          S.bz = ZH - BR;
          S.vz = -Math.abs(S.vz);
        }
        if (S.bz < -ZH + BR) {
          S.bz = -ZH + BR;
          S.vz = Math.abs(S.vz);
        }
        const strike = (x, z, dir) => {
          const off = clamp((S.bz - z) / (HALF + BR), -1, 1);
          const a = off * 0.85;
          S.speed = Math.min(142, S.speed + 5);
          S.rally += 1;
          S.bx = x - dir * (THICK + BR);
          S.vx = -dir * S.speed * Math.cos(a);
          S.vz = S.speed * Math.sin(a);
        };
        if (S.vx < 0 && S.bx - BR <= -XL + THICK && S.bx + BR >= -XL - THICK && Math.abs(S.bz - S.zYou) <= HALF + BR * 0.8) {
          strike(-XL, S.zYou, -1);
          S.hitYou = 1;
        }
        if (S.vx > 0 && S.bx + BR >= XL - THICK && S.bx - BR <= XL + THICK && Math.abs(S.bz - S.zThem) <= HALF + BR * 0.8) {
          strike(XL, S.zThem, 1);
          S.hitThem = 1;
        }
        if (S.bx < -XL - 21) goal("them");
        else if (S.bx > XL + 21) goal("you");
      }
      if (t >= START) {
        ball.position.set(S.bx, (CARD.thickness / 2) * BALL, S.bz);
        ball.quaternion.copy(turned(-Math.PI / 2, t * 9, 0));
        ball.scale.setScalar(BALL);
      }
      confetti.update(dt, t);

      // The eye: up from the table's view to look down on the court, then
      // still, so the pointer and the court agree.
      const k = smooth(0.2, 2.4, t);
      eye.set(0, lerp(55, 118, k), lerp(60, 122, k));
      at.set(0, 0, lerp(0, 14, k));
      ctx.look(eye, at, 42);
    },
    dispose() {
      confetti.dispose();
      root.removeFromParent();
    },
  };
}
pong.title = "Card pong";
pong.how = "Drag your card, or use ↑ and ↓. First to five";
pong.interactive = true;
