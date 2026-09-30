// The celebrations: at the end of a partie, the cards celebrate.
//
// Andrew designed seven with Claude on the web (web3d/reference/
// celebrations-prototype.html) and asked for them translated into the game:
// "just use these as ideas, and translate the ideas into the game. use all
// of our norms we've established- no sound, use the normal look, use our
// normal card art, use normal 3js settings ... in the real game, when the
// game ends, the user will just see one of the ending games/animations,
// randomly chosen."
//
// Every celebration starts as the prototype's did, from the 32 cards in a
// pile -- here, gathered from wherever the partie left them, tossed in with
// the table's own motion (a flick, then gravity). The runner owns its own
// card meshes while it plays, so the director's are left exactly as they
// were, and the table comes back as it was when the celebration ends.
//
// A scene is a function of a context (below) returning { update(dt, t),
// dispose() }, with a `title`, and `interactive` and `how` if it is a game.

import { Group, Vector3 } from "three";
import { lying, toss } from "../kinematics.js";
import { CARD } from "../units.js";
import { random } from "./physics.js";

const CODES = [];
for (const s of "SHDC") for (const r of "789TJQKA") CODES.push(r + s);

export const PILE = Object.freeze({ x: 0, z: -6 });
const STEP = CARD.thickness + 0.012;

// The pile: all 32 squared face down in the middle of the table, each a hair
// turned, as a hand squares a pack.
export function pilePoses(at = PILE) {
  return CODES.map((_, i) =>
    lying({ x: at.x + Math.sin(i * 12.9) * 0.08, z: at.z + Math.cos(i * 7.7) * 0.08, height: i * STEP, faceUp: false, yaw: Math.sin(i * 5.1) * 0.02 }),
  );
}

// `stage` and `deck` as the table's; `hud`, the page's words over the scene
// (hud.js); `scenes`, the celebrations by name, in their order.
export function createCelebrations({ stage, deck, hud, scenes, seed }) {
  const names = Object.keys(scenes);
  const rng = random(seed ?? ((Math.random() * 2 ** 32) >>> 0));
  let root = null;
  let cards = [];
  let extras = [];
  let scene = null;
  let current = null;
  let saved = null;
  let hidden = [];
  let gathering = null; // { paths, start, length }
  let clock = 0; // the scene's time, s
  let last = null;
  let raf = null;
  let manual = false;
  const listeners = [];
  const pointer = { x: 0, y: 0, down: false, id: null };
  const keys = new Set();

  // ---- the camera, handed to the scene and given back -----------------------

  function keepCamera() {
    const c = stage.camera;
    const fog = stage.scene.fog;
    saved = {
      position: c.position.clone(), quaternion: c.quaternion.clone(), fov: c.fov, near: c.near,
      film: c.filmOffset, view: c.view ? { ...c.view } : null, fog: fog && [fog.near, fog.far],
    };
    // The table is framed beside the information column; a celebration has
    // the whole window, the column stepped aside.
    c.filmOffset = 0;
    c.clearViewOffset();
    // The table's far reaches still fade into the air, but further off: a
    // celebration's eye stands back further than a player's.
    if (fog) [fog.near, fog.far] = [230, 460];
    // The scenes come close: a near plane for a camera between card legs.
    c.near = 2;
    c.updateProjectionMatrix();
  }
  function restoreCamera() {
    if (!saved) return;
    const c = stage.camera;
    c.position.copy(saved.position);
    c.quaternion.copy(saved.quaternion);
    c.fov = saved.fov;
    c.near = saved.near;
    c.filmOffset = saved.film;
    if (saved.view) c.setViewOffset(saved.view.fullWidth, saved.view.fullHeight, saved.view.offsetX, saved.view.offsetY, saved.view.width, saved.view.height);
    c.updateProjectionMatrix();
    if (saved.fog) [stage.scene.fog.near, stage.scene.fog.far] = saved.fog;
    saved = null;
  }

  // ---- the context a scene is given ----------------------------------------

  function extra(code = rng.pick(CODES)) {
    const mesh = deck.card(code);
    stage.scene.remove(mesh);
    root.add(mesh);
    extras.push(mesh);
    return mesh;
  }
  const ctx = {
    get root() {
      return root;
    },
    get cards() {
      return cards;
    },
    stage,
    camera: stage.camera,
    random: rng,
    hud,
    pointer,
    keys,
    pile: () => pilePoses(),
    extra,
    // Look from `from` at `at`, with a field of view if given.
    look(from, at, fov) {
      const c = stage.camera;
      c.position.copy(from);
      c.lookAt(at);
      if (fov && fov !== c.fov) {
        c.fov = fov;
        c.updateProjectionMatrix();
      }
    },
    // Where the pointer is, on a plane: a ray from the eye through it.
    on(plane, target = new Vector3()) {
      stage.camera.updateMatrixWorld();
      const origin = stage.camera.position.clone();
      const through = new Vector3(pointer.x, pointer.y, 0.5).unproject(stage.camera).sub(origin).normalize();
      const denom = plane.normal.dot(through);
      if (Math.abs(denom) < 1e-6) return null;
      const t = -(plane.normal.dot(origin) + plane.constant) / denom;
      return t > 0 ? target.copy(origin).addScaledVector(through, t) : null;
    },
    // A pointer or key handler, removed with the scene.
    listen(target, kind, fn) {
      target.addEventListener(kind, fn);
      listeners.push([target, kind, fn]);
    },
    // This celebration again, from the pile.
    again: () => api.play(current),
  };

  // Where the pointer is (in the view's -1..1), whether it is pressed, and
  // which keys are held -- for the scenes that are games.
  const canvas = stage.renderer.domElement;
  const track = (e) => {
    const r = canvas.getBoundingClientRect();
    pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  };
  const always = [
    [canvas, "pointermove", track],
    [canvas, "pointerdown", (e) => {
      track(e);
      pointer.down = true;
      try {
        canvas.setPointerCapture(e.pointerId);
      } catch (_) {
        /* a synthetic pointer */
      }
    }],
    [canvas, "pointerup", () => (pointer.down = false)],
    [canvas, "pointercancel", () => (pointer.down = false)],
    [window, "keydown", (e) => {
      keys.add(e.key);
      if (e.key.startsWith("Arrow")) e.preventDefault();
    }],
    [window, "keyup", (e) => keys.delete(e.key)],
  ];

  // ---- running ---------------------------------------------------------------

  function frame(now) {
    raf = null;
    const dt = last === null ? 1 / 60 : Math.min(0.05, (now - last) / 1000);
    last = now;
    step(dt);
    if (current && !manual) raf = requestAnimationFrame(frame);
  }
  function step(dt, draw = true) {
    if (gathering) {
      const u = Math.min(1, (clock += dt) / gathering.length);
      gathering.paths.forEach(({ mesh, path, delay, share }, i) => {
        const t = Math.max(0, Math.min(1, (u - delay) / share));
        const p = path(t);
        mesh.position.copy(p.position);
        mesh.quaternion.copy(p.quaternion);
      });
      if (u >= 1) {
        gathering = null;
        clock = 0;
        begin(current);
      }
    } else if (scene) {
      clock += dt;
      scene.update(dt, clock);
    }
    if (draw) stage.render();
  }

  function dropScene() {
    if (scene) scene.dispose?.();
    scene = null;
    for (const [target, kind, fn] of listeners.splice(0)) target.removeEventListener(kind, fn);
    for (const mesh of extras.splice(0)) root.remove(mesh);
    for (const child of [...root.children]) if (!cards.includes(child)) root.remove(child);
    hud.clear();
    keys.clear();
    pointer.down = false;
    for (const card of cards) card.scale.setScalar(1);
  }

  function begin(name) {
    const make = scenes[name];
    if (make.how) hud.how(make.how);
    scene = make(ctx);
  }

  // Toss every card from where it is into the pile, the last on top. Each
  // of ours takes over the table's card with the same face, so nothing seen
  // changes; the table's face-down cards, whatever they were, take the rest.
  function gather(from) {
    const to = pilePoses();
    const order = [...from.keys()].sort((a, b) => from[a].position.y - from[b].position.y);
    const byCode = new Map(cards.map((m) => [m.userData.code, m]));
    const known = new Set(from.map((f) => f.code).filter(Boolean));
    const spare = cards.filter((m) => !known.has(m.userData.code));
    const next = order.map((i) => (from[i].code && byCode.get(from[i].code)) || spare.shift());
    const paths = order.map((i, k) => {
      next[k].position.copy(from[i].position);
      next[k].quaternion.copy(from[i].quaternion);
      return { mesh: next[k], path: toss(from[i], to[k], { clearance: 4 + k * 0.05 }), delay: (k / 32) * 0.45, share: 0.55 };
    });
    cards = next;
    gathering = { paths, length: 1.3 };
    clock = 0;
  }

  function start() {
    for (const [target, kind, fn] of always) target.addEventListener(kind, fn);
    hud.open();
    root = new Group();
    stage.scene.add(root);
    // The deck's own cards, one of each, to celebrate with.
    cards = CODES.map((code) => {
      const mesh = deck.card(code);
      stage.scene.remove(mesh);
      root.add(mesh);
      mesh.rotation.order = "YXZ";
      return mesh;
    });
    keepCamera();
  }

  const api = {
    names,
    random: () => rng.pick(names),
    playing: () => current,
    // Celebrate, from these meshes where they lie (the table's), or from the
    // pile. The table's meshes are hidden until `stop`.
    play(name, { from = null } = {}) {
      if (!scenes[name]) throw new Error(`no celebration called ${name}`);
      const first = !current;
      if (first) {
        start();
        hidden = from ? from.filter((m) => m.visible) : [];
        for (const mesh of hidden) mesh.visible = false;
      } else {
        dropScene();
      }
      current = name;
      hud.title(scenes[name].title, names.indexOf(name), names.length);
      const where = (m) => ({ position: m.position.clone(), quaternion: m.quaternion.clone(), code: m.userData.code ?? null });
      gather((first && from ? from : cards).map(where));
      last = null;
      if (!manual && raf === null) raf = requestAnimationFrame(frame);
    },
    // Back to the table as it was.
    stop() {
      if (!current) return;
      dropScene();
      if (raf !== null) cancelAnimationFrame(raf);
      raf = null;
      gathering = null;
      stage.scene.remove(root);
      root = null;
      cards = [];
      for (const mesh of hidden) mesh.visible = true;
      hidden = [];
      for (const [target, kind, fn] of always) target.removeEventListener(kind, fn);
      restoreCamera();
      current = null;
      hud.close();
      stage.render();
    },
    // For tests and stills: drive the clock by hand.
    manual(on = true) {
      manual = on;
      if (on && raf !== null) {
        cancelAnimationFrame(raf);
        raf = null;
      }
    },
    tick(ms, stepMs = 1000 / 60) {
      for (let left = ms; left > 1e-9; left -= stepMs) step(Math.min(stepMs, left) / 1000, false);
      stage.render();
    },
    pointer,
    keys,
    context: ctx,
  };
  return api;
}
