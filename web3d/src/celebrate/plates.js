// Plate smash: a small game. Plates are thrown in on true arcs; you hold one
// up in front of the pile and move it left and right to deflect them. Every
// plate that lands smashes -- shards on real gravity, a "PIQUET!" where it
// hit -- and when the last has flown, the pile itself bursts.
//
// From the prototype, in the user's words: "fly in on parabolas, using real
// gravity physics. plates should explode ... wherever a plate lands it goes
// 'PIQUET!' ... the user has a plate they can move left or right (same as
// pong, but held perpendicular to the table in front of the camera) to swat
// the other plates away" -- and later, 'deflected' rather than 'swatted'.
// Here at the table's real scale: dinner plates 22 cm across, thrown from a
// couple of metres away, in the air about a second.

import { BufferGeometry, DoubleSide, Float32BufferAttribute, Group, LatheGeometry, Plane, TorusGeometry, Vector2, Vector3 } from "three";
import { minimumJerk } from "../easing.js";
import { Flakes, PALETTE, kit } from "./kit.js";
import { Flung, G, ballistic, clamp, lerp, smooth } from "./physics.js";

const N = 26; // plates thrown
const RADIUS = 11; // cm, a dinner plate
const HELD = 13; // cm, yours a little larger
const PZ = 39; // cm: the plane you hold your plate in, in front of the pile
const PY = 16; // cm: its centre's height
const REACH = 70; // cm: how far to either side you can move it
const TABLE = 140; // cm: plates landing further out fall off the edge of the world

export function plates(ctx) {
  const { toon, inked } = kit(ctx.stage);
  const rng = ctx.random;
  const root = new Group();
  ctx.root.add(root);

  // A plate: a lathe in cream, with a ring of the page's blue round its well.
  const profile = [[0, 0], [6.6, 0.2], [10.5, 1.5], [11, 1.5], [11, 2.0], [10.2, 2.0], [6.6, 0.7], [0, 0.7]].map(([x, y]) => new Vector2(x, y));
  const plateGeometry = new LatheGeometry(profile, 32);
  const ringGeometry = new TorusGeometry(8.4, 0.3, 5, 40).rotateX(Math.PI / 2).translate(0, 1.05, 0);
  const cream = toon(PALETTE.cream, { side: DoubleSide });
  const ring = toon(PALETTE.primary);
  const amber = toon(PALETTE.amber, { side: DoubleSide });
  const plate = (material, scale) => {
    const g = new Group();
    g.add(inked(plateGeometry, material));
    g.add(new Group().add(inked(ringGeometry, ring)));
    g.scale.setScalar(scale);
    return g;
  };

  // Shards: small triangles, mostly cream, some of the ring's blue.
  const shard = new BufferGeometry();
  shard.setAttribute("position", new Float32BufferAttribute([0, 0, 0, 3.2, 0.4, 0, 1.1, 3.4, 0], 3));
  shard.computeVertexNormals();
  const shards = new Flakes(root, shard, toon("#ffffff", { side: DoubleSide }), 1400, { floor: 0.05, bounce: 0.4 });
  const SHARDS = [PALETTE.cream, PALETTE.cream, PALETTE.cream, PALETTE.primaryContainer, PALETTE.primary];

  // Yours: held upright, facing the thrower, rising into place.
  const hold = plate(amber, HELD / RADIUS);
  hold.rotation.x = Math.PI / 2;
  const holder = new Group().add(hold);
  root.add(holder);
  let px = 0;
  let pvx = 0;
  let aim = 0;
  let tilt = 0;

  const thrown = [];
  let deflected = 0;
  let smashed = 0;
  let spawned = 0;
  let nextAt = 2.2;
  let finaleAt = -1;
  let burst = false;
  let over = false;
  let shake = 0;
  let jiggle = 0;
  const flung = new Flung();
  const pileAt = ctx.cards.map((c) => c.position.clone());
  const plane = new Plane(new Vector3(0, 0, 1), -PZ);
  const under = new Vector3();

  const tally = () => ctx.hud.score(`Deflected ${deflected} · Smashed ${smashed}`);
  tally();

  // Drag your plate, or the arrow keys.
  ctx.listen(ctx.stage.renderer.domElement, "pointerdown", () => {
    const p = ctx.on(plane, under);
    if (p) aim = clamp(p.x, -REACH, REACH);
  });
  ctx.listen(ctx.stage.renderer.domElement, "pointermove", () => {
    if (!ctx.pointer.down) return;
    const p = ctx.on(plane, under);
    if (p) aim = clamp(p.x, -REACH, REACH);
  });

  function throwOne() {
    // From off to one side, or from far across the table.
    const side = rng() < 0.5 ? -1 : 1;
    const from = rng() < 0.6
      ? new Vector3(side * rng.range(230, 280), rng.range(20, 50), rng.range(-90, 10))
      : new Vector3(rng.range(-120, 120), rng.range(30, 70), -rng.range(200, 230));
    // Aimed to cross your plane somewhere you can reach.
    const through = new Vector3(rng.range(-REACH, REACH), rng.range(8, 32), PZ);
    const g = plate(cream, 1);
    g.position.copy(from);
    root.add(g);
    thrown.push({ g, p: from.clone(), v: ballistic(from, through, rng.range(0.8, 1.1)), w: new Vector3(rng.range(-9, 9), rng.range(-9, 9), rng.range(-9, 9)), deflected: false, done: false });
    spawned += 1;
  }

  function smash(pl) {
    pl.done = true;
    root.remove(pl.g);
    smashed += 1;
    tally();
    const { x, z } = pl.p;
    for (let i = 0; i < 26; i++) {
      const a = rng.range(0, Math.PI * 2);
      const speed = rng.range(60, 180);
      shards.emit(new Vector3(x, 1.5, z), new Vector3(Math.cos(a) * speed + pl.v.x * 0.2, rng.range(150, 420), Math.sin(a) * speed + pl.v.z * 0.2), {
        colour: rng.pick(SHARDS), size: rng.range(0.6, 1.3), drag: 0.8, rand: rng,
      });
    }
    ctx.hud.burst(new Vector3(x, 6, z), { size: clamp(1.4 - Math.hypot(x, z) / 250, 0.8, 1.3) });
    shake = Math.max(shake, clamp(2.2 - Math.hypot(x, z - PZ) / 90, 0.3, 1.6));
    jiggle = Math.min(1.5, jiggle + 60 / (40 + Math.hypot(x, z)));
  }

  // The finale: the pile bursts toward you -- the cards fan out across the
  // view and fly up past it, over your head, to land behind you. (Settled in
  // a heap on the table, overlapping cards fought each other for the same
  // height; the user: "the cards explode over the screen and then go away".)
  // The camera turns first; the cards go once it is looking.
  let launched = false;
  function finale() {
    burst = true;
    shake = 1.2;
    ctx.hud.burst(new Vector3(0, 12, -6), { size: 1.8, colour: PALETTE.youContainer });
  }
  function launch() {
    launched = true;
    shake = 2.5;
    // Like a firework seen from the side: the eye drops back to look up at
    // the pile (below), and every card arcs out wide across the view to land
    // far off, beyond the fog -- none of them left to settle in a heap.
    for (const card of ctx.cards) {
      const a = rng.range(-Math.PI * 0.9, Math.PI * 0.1); // away from you, mostly
      const far = rng.range(240, 400);
      const land = new Vector3(Math.cos(a) * far, 0, -6 + Math.sin(a) * far * 0.8);
      const v = ballistic(card.position, land, rng.range(1.15, 1.6));
      flung.add(card, v, new Vector3(rng.range(-12, 12), rng.range(-12, 12), rng.range(-12, 12)));
    }
  }

  const eye = new Vector3();
  const at = new Vector3();
  return {
    update(dt, t) {
      // Your plate follows the pointer on a critically damped spring.
      if (ctx.keys.has("ArrowLeft")) aim = clamp(aim - 110 * dt, -REACH, REACH);
      if (ctx.keys.has("ArrowRight")) aim = clamp(aim + 110 * dt, -REACH, REACH);
      const w = 22;
      pvx += (w * w * (aim - px) - 2 * w * pvx) * dt;
      px = clamp(px + pvx * dt, -REACH, REACH);
      tilt *= Math.exp(-7 * dt);
      // Rising into place; and at the finale, down out of the way.
      const down = burst ? minimumJerk(clamp((t - finaleAt) / 0.6, 0, 1)) : 0;
      holder.position.set(px, lerp(lerp(-HELD * 2, PY, minimumJerk(clamp((t - 0.4) / 1.1, 0, 1))), -HELD * 3, down), PZ);
      holder.rotation.set(-0.5 * tilt, 0, -pvx * 0.0025);

      if (!over && spawned < N && t >= nextAt) {
        throwOne();
        nextAt = t + lerp(1.3, 0.55, spawned / N);
      }
      for (const pl of thrown) {
        if (pl.done) continue;
        const was = pl.p.clone();
        pl.v.y -= G * dt;
        pl.p.addScaledVector(pl.v, dt);
        pl.g.position.copy(pl.p);
        pl.g.rotation.x += pl.w.x * dt;
        pl.g.rotation.y += pl.w.y * dt;
        pl.g.rotation.z += pl.w.z * dt;
        // Swept: where it crossed your plane this step, not where it is now.
        if (!pl.deflected && pl.v.z > 0 && was.z < PZ && pl.p.z >= PZ) {
          const f = (PZ - was.z) / (pl.p.z - was.z);
          const cx = lerp(was.x, pl.p.x, f);
          const cy = lerp(was.y, pl.p.y, f);
          if (Math.hypot(cx - px, cy - PY) <= HELD + RADIUS * 0.85) {
            pl.deflected = true;
            deflected += 1;
            tally();
            tilt = 1;
            pl.v.set(pl.v.x * 0.3 + (cx - px) * 3.2 + pvx * 0.8, Math.abs(pl.v.y) * 0.3 + (cy - PY) * 2 + 300, -(Math.abs(pl.v.z) * 0.85 + 30));
            pl.p.z = PZ - 0.5;
            pl.w.multiplyScalar(1.6);
            shake = Math.max(shake, 0.4);
          }
        }
        if (pl.p.y <= RADIUS * 0.2 && pl.v.y < 0 && Math.hypot(pl.p.x, pl.p.z) < TABLE) smash(pl);
        else if (pl.p.y < -60) {
          pl.done = true;
          root.remove(pl.g);
        }
      }

      // The pile jumps a little at every smash near it.
      jiggle *= Math.exp(-9 * dt);
      if (burst && !launched) jiggle = 1.2; // shivering, about to go
      if (!launched) {
        ctx.cards.forEach((c, i) => {
          c.position.y = pileAt[i].y + jiggle * Math.max(0, Math.sin(i * 0.37 + t * 38)) * 0.25;
        });
      }
      if (!over && spawned >= N && finaleAt < 0 && thrown.every((p) => p.done)) finaleAt = t + 1;
      if (finaleAt > 0 && !burst && t >= finaleAt) finale();
      if (burst && !launched && t >= finaleAt + 0.45) launch();
      if (burst && !over && t >= finaleAt + 2.6) {
        over = true;
        ctx.hud.message(`Deflected ${deflected} of ${N}`, { label: "Play again", fn: () => ctx.again() });
      }
      flung.update(dt);
      shards.update(dt, t);

      // The eye: from the table's view, eased up and back behind your plate,
      // high enough to see the pile over it -- a plate held upright, seen
      // from above, is a narrow ellipse.
      const k = minimumJerk(clamp(t / 1.6, 0, 1));
      shake *= Math.exp(-5 * dt);
      eye.set(0, lerp(55, 118, k), lerp(60, 116, k));
      at.set(0, lerp(0, 6, k), lerp(0, 8, k));
      let fov = lerp(40, 46, smooth(0, 1, k));
      // The finale: back and down, looking up at the burst.
      if (burst) {
        const f = minimumJerk(clamp((t - finaleAt) / 0.9, 0, 1));
        eye.lerp(new Vector3(0, 42, 190), f);
        at.lerp(new Vector3(0, 78, -30), f);
        fov = lerp(fov, 58, f);
      }
      if (shake > 0.01) eye.add(new Vector3(rng.range(-1, 1), rng.range(-1, 1), rng.range(-1, 1)).multiplyScalar(shake * 0.8));
      ctx.look(eye, at, fov);
    },
    dispose() {
      shards.dispose();
      root.removeFromParent();
    },
  };
}
plates.title = "Plate smash";
plates.how = "Drag your plate, or use ← and →, to deflect the plates";
plates.touch = "Drag your plate to deflect the plates";
plates.interactive = true;
