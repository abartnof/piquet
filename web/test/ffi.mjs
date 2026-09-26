// Drive the WebAssembly module through its four exports, the way the page
// does, playing whole parties with the dullest legal script.
//
//   node web/test/ffi.mjs target/wasm32-unknown-unknown/release/piquet_wasm.wasm
//
// Prints one line per (level, seed): the final state's settlement and a hash
// of the whole final state, so a native run of the same script can be
// compared line for line.
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

const bytes = readFileSync(process.argv[2]);
const { instance } = await WebAssembly.instantiate(bytes, {});
const ex = instance.exports;
const enc = new TextEncoder();
const dec = new TextDecoder();

const state = () =>
  dec.decode(new Uint8Array(ex.memory.buffer, ex.piquet_state(), ex.piquet_state_len()));
const send = (command) => {
  const b = enc.encode(command);
  const p = ex.piquet_alloc(b.length);
  new Uint8Array(ex.memory.buffer, p, b.length).set(b);
  return ex.piquet_send(b.length) === 1;
};

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

let failures = 0;
for (const level of [1, 2, 3, 4, 5]) {
  for (const seed of [1, 2, 3]) {
    ex.piquet_new(level, seed);
    let steps = 0;
    for (;;) {
      const s = JSON.parse(state());
      const command = dull(s);
      if (command === null) break;
      if (!send(command)) {
        console.error(`level ${level} seed ${seed}: refused ${command}: ${JSON.parse(state()).error}`);
        failures++;
        break;
      }
      if (++steps > 3000) { console.error("never ended"); failures++; break; }
    }
    const final = state();
    const s = JSON.parse(final);
    const hash = createHash("sha256").update(final).digest("hex").slice(0, 16);
    console.log(`level ${level} seed ${seed} ${s.partie.you}-${s.partie.them} pays ${s.settlement.points} ${hash}`);
  }
}
// And a refused command must not corrupt anything.
ex.piquet_new(3, 9);
if (send("play ZZ") || JSON.parse(state()).error === null) { console.error("nonsense accepted"); failures++; }
process.exit(failures ? 1 : 0);
