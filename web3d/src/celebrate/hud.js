// The words over a celebration, in the page's own Material style: a burst
// where something lands (the prototype's comic-book "PIQUET!", which the user
// asked for in place of a shout -- here in the page's type and colours), a
// score chip, a result card, and a bar along the bottom with the scene's
// name, the arrows to step through them when staging, and a way back.

import { Vector3 } from "three";
import { el, symbol } from "../overlay.js";
import { BRIGHTS, PALETTE } from "./kit.js";

export function createHud(root, camera, { staging = false, onStep, onClose } = {}) {
  const layer = el("div", { class: "celebrate-layer", "aria-hidden": "true" });
  const score = el("div", { class: "celebrate-score surface", role: "status", hidden: true });
  const message = el("div", { class: "celebrate-message surface", hidden: true });
  const name = el("div", { class: "celebrate-name" });
  const how = el("div", { class: "celebrate-how" });
  const button = (icon, label, fn) => {
    const b = el("md-icon-button", { class: `celebrate-${icon}`, "aria-label": label, "data-tip": label }, symbol(icon));
    b.addEventListener("click", fn);
    return b;
  };
  const prev = button("back", "The celebration before", () => onStep?.(-1));
  const next = button("forward", "The next celebration", () => onStep?.(1));
  const close = button("close", "Back to the table", () => onClose?.());
  const bar = el("div", { class: "celebrate-bar surface" },
    staging ? prev : null,
    el("div", { class: "celebrate-words" }, name, how),
    staging ? next : null,
    close);
  const box = el("div", { class: "celebrate", hidden: true }, layer, score, message, bar);
  root.append(box);

  const at = new Vector3();
  let bursts = 0;

  return {
    open() {
      box.hidden = false;
      document.body.classList.add("celebrating");
    },
    close() {
      this.clear();
      box.hidden = true;
      document.body.classList.remove("celebrating");
    },
    title(words, index, of) {
      name.replaceChildren(words, staging ? el("span", { class: "celebrate-count" }, ` ${index + 1} of ${of}`) : "");
    },
    how(words) {
      how.textContent = words;
    },
    score(words) {
      score.hidden = !words;
      score.textContent = words ?? "";
    },
    // A result, and perhaps an action (play again).
    message(words, action = null) {
      message.hidden = !words;
      message.replaceChildren(
        el("div", { class: "celebrate-result" }, words ?? ""),
        action ? el("md-filled-tonal-button", { onclick: action.fn }, action.label) : "");
    },
    // A burst at a point in the scene: a star in one of the page's bright
    // colours, ink round it, and always the one word (the user: every burst in
    // the endings "should just say 'Piquet!'").
    burst(point, { size = 1, colour } = {}) {
      const words = "Piquet!";
      at.copy(point).project(camera);
      if (at.z > 1 || Math.abs(at.x) > 1.2 || Math.abs(at.y) > 1.2) return;
      const x = Math.min(92, Math.max(8, (at.x * 0.5 + 0.5) * 100));
      const y = Math.min(88, Math.max(10, (-at.y * 0.5 + 0.5) * 100));
      // Wider than tall, as the word is, with shallow points: the word sits
      // in clear space inside the star's inner edge, never on its ink
      // (the user: the text "collides with the outline").
      const n = 12;
      const points = [];
      for (let i = 0; i < n * 2; i++) {
        const a = (i / (n * 2)) * Math.PI * 2;
        const r = i % 2 ? 76 + ((i * 37) % 6) : 98 + ((i * 53) % 5);
        points.push(`${(Math.cos(a) * r * 1.45).toFixed(1)},${(Math.sin(a) * r).toFixed(1)}`);
      }
      const fill = colour ?? BRIGHTS[bursts++ % 4];
      const star = `<svg viewBox="-150 -105 300 210"><polygon points="${points.join(" ")}" fill="${fill}" stroke="${PALETTE.ink}" stroke-width="5" stroke-linejoin="round"/></svg>`;
      const node = el("div", { class: "celebrate-burst" });
      node.innerHTML = star;
      node.append(el("span", {}, words));
      node.style.left = `${x}%`;
      node.style.top = `${y}%`;
      node.style.setProperty("--size", String(size));
      node.style.setProperty("--turn", `${((bursts * 47) % 24) - 12}deg`);
      layer.append(node);
      setTimeout(() => node.remove(), 1300);
    },
    clear() {
      layer.replaceChildren();
      this.score(null);
      this.message(null);
      how.textContent = "";
    },
  };
}
