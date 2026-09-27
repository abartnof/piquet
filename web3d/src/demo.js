// The motion demo (docs/TABLE3D.md, P4): every primitive on a loop, to watch
// -- `?demo`, slowed with `&slow=3` -- and a hook that freezes them all at one
// moment, so a strip of screenshots can show a motion.

import { Quaternion, Vector3 } from "three";
import { place } from "./deck.js";
import { fan, flip, layDown, lying, pickUp, slide, transfer } from "./kinematics.js";

const DEG = Math.PI / 180;
const REST = 0.02;

// A card held up before the human, the way one sits in their hand.
function held(x, stage) {
  const [one] = fan({ count: 1, centre: new Vector3(x, 14, 24), facing: stage.camera.position });
  return one;
}

export function buildDemo(stage, deck, { slow = 1 } = {}) {
  const stations = [];
  const station = (codes, paths, duration) => {
    const meshes = codes.map((code) => deck.card(code));
    stations.push({ meshes, paths, duration: duration * slow });
  };

  // Turned over on the table, along the edge toward where it lands.
  station(["QH"], [flip(lying({ x: -38, z: -8, height: REST, faceUp: false }), { toward: new Vector3(1, 0, 0) })], 480);
  // Pushed, and slowing to a stop under friction.
  station(["9C"], [slide(lying({ x: -22, z: 12, height: REST }), lying({ x: -8, z: 12, height: REST, yaw: -3 * DEG }))], 520);
  // From the hand to the table, meeting it face-parallel.
  station(["KD"], [layDown(held(4, stage), lying({ x: 4, z: -2, height: REST, yaw: 2 * DEG }))], 420);
  // From the table to the hand, near edge first.
  station(
    [null],
    [pickUp(lying({ x: 22, z: -2, height: REST, faceUp: false }), held(20, stage), { toward: new Vector3(0, 0, 1) })],
    380,
  );
  // Carried across the table, arcing over what lies between, turning over in the air.
  station(
    ["AS"],
    [transfer(lying({ x: -22, z: -18, height: REST, faceUp: false }), lying({ x: 14, z: -18, height: REST, yaw: 8 * DEG }))],
    560,
  );
  // A hand opening into a fan from a squared stack.
  const codes = ["AH", "KH", "QS", "JH", "TH"];
  const fanned = fan({ count: 5, centre: new Vector3(-22, 14, 24), facing: stage.camera.position });
  const squared = fanned.map((_, i) => ({
    position: new Vector3(-22, 14, 24).add(new Vector3(0, 0, i * 0.06).applyQuaternion(fanned[2].quaternion)),
    quaternion: new Quaternion().copy(fanned[2].quaternion),
  }));
  station(codes, fanned.map((to, i) => transfer(squared[i], to, { clearance: 0.4 })), 380);

  const at = (t) => {
    for (const s of stations) s.meshes.forEach((mesh, i) => place(mesh, s.paths[i](t)));
    stage.render();
  };
  at(0);

  // Loop each station: play, hold the end a moment, snap back, again.
  let running = false;
  const hold = 900 * slow;
  function frame(now) {
    for (const s of stations) {
      const cycle = s.duration + hold;
      const t = Math.min(1, (now % cycle) / s.duration);
      s.meshes.forEach((mesh, i) => place(mesh, s.paths[i](t)));
    }
    stage.render();
    if (running) requestAnimationFrame(frame);
  }
  return {
    at,
    play() {
      running = true;
      requestAnimationFrame(frame);
    },
    stop() {
      running = false;
    },
  };
}
