// Real protocol states for the tests: whole parties played through the
// engine's WebAssembly by a dull scripted human, every state kept. The wasm is
// the one web3d/build.py compiles; build first.

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { loadEngine } from "../src/engine.js";

const WASM = fileURLToPath(new URL("../../target/wasm32-unknown-unknown/release/piquet_wasm.wasm", import.meta.url));

export async function engine() {
  if (!existsSync(WASM)) throw new Error(`no engine at ${WASM}: run python3 web3d/build.py first`);
  return loadEngine(readFileSync(WASM));
}

// The dullest legal script, varied a little by `n` so parties differ: it
// throws a few cards, calls in full or sinks, and plays the first or last
// legal card.
export function dull(s, n = 0) {
  const p = s.prompt;
  switch (p.kind) {
    case "cut":
      return `cut ${2 + ((n * 7) % 29)}`;
    case "choose_dealer":
      return n % 2 ? "dealer them" : "dealer you";
    case "exchange": {
      const k = 1 + (n % Math.min(p.limit, 3));
      return `exchange ${s.hand.slice(-k).join(" ")}`;
    }
    case "declare":
      return `declare ${n % 3 === 2 ? p.options.length - 1 : 0}`;
    case "play":
      return `play ${n % 2 ? p.legal[p.legal.length - 1] : p.legal[0]}`;
    case "next_deal":
      return "next";
    default:
      return null;
  }
}

// Every state of a partie, from the cut to the settlement.
export async function partie(level, seed) {
  const e = await engine();
  e.start(level, seed);
  const states = [e.state()];
  for (let n = 0; n < 2000; n++) {
    const command = dull(states[states.length - 1], n + seed);
    if (!command) break;
    if (!e.send(command)) throw new Error(`refused "${command}": ${e.state().error}`);
    states.push(e.state());
  }
  return states;
}
