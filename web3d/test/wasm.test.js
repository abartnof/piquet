// Every build of the engine, native or WebAssembly, plays the same partie
// from the same level and seed, byte for byte -- which is what makes a seed
// and its commands a complete game record (docs/PROTOCOL.md). This is the
// WebAssembly half: the page's own engine, driven through its four exports,
// must end the dull parties exactly as the native engine recorded them
// (crates/piquet-wasm/tests/protocol.rs, the_dull_parties_end_as_recorded).
// The wasm is the one web3d/build.py compiles; build first.

import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const WASM = fileURLToPath(new URL("../../target/wasm32-unknown-unknown/release/piquet_wasm.wasm", import.meta.url));
const RECORDED = fileURLToPath(new URL("../../crates/piquet-wasm/tests/dull-parties.txt", import.meta.url));

// FNV-1a, 64 bits, as protocol.rs computes it.
function fnv1a(bytes) {
  let h = 0xcbf29ce484222325n;
  for (const b of bytes) h = ((h ^ BigInt(b)) * 0x100000001b3n) & 0xffffffffffffffffn;
  return h.toString(16).padStart(16, "0");
}

// The dullest legal command, as protocol.rs's `dull` has it.
function dull(s) {
  const p = s.prompt;
  switch (p.kind) {
    case "cut": return "cut 16";
    case "choose_dealer": return "dealer you";
    case "exchange": return `exchange ${s.hand[0]}`;
    case "declare": return "declare 0";
    case "play": return `play ${p.legal[0]}`;
    case "next_deal": return "next";
    default: return null;
  }
}

test("the WebAssembly engine ends the dull parties as the native one recorded them", async () => {
  assert.ok(existsSync(WASM), `no engine at ${WASM}: run python3 web3d/build.py first`);
  const { instance } = await WebAssembly.instantiate(readFileSync(WASM), {});
  const ex = instance.exports;
  const enc = new TextEncoder();
  const raw = () => new Uint8Array(ex.memory.buffer, ex.piquet_state(), ex.piquet_state_len()).slice();
  const send = (command) => {
    const b = enc.encode(command);
    const at = ex.piquet_alloc(b.length);
    new Uint8Array(ex.memory.buffer, at, b.length).set(b);
    return ex.piquet_send(b.length) === 1;
  };
  let out = "";
  for (const level of [1, 2, 3, 4, 5]) {
    for (const seed of [1, 2, 3]) {
      ex.piquet_new(level, seed);
      for (let steps = 0; ; steps++) {
        assert.ok(steps < 3000, `level ${level} seed ${seed} never ended`);
        const command = dull(JSON.parse(new TextDecoder().decode(raw())));
        if (command === null) break;
        assert.ok(send(command), `level ${level} seed ${seed}: refused ${command}`);
      }
      const bytes = raw();
      const s = JSON.parse(new TextDecoder().decode(bytes));
      out += `level ${level} seed ${seed} ${s.partie.you}-${s.partie.them} pays ${s.settlement.points} ${fnv1a(bytes)}\n`;
    }
  }
  assert.equal(out, readFileSync(RECORDED, "utf8"));
});
