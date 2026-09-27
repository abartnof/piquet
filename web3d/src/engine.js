// The engine: the rules, compiled to WebAssembly, behind the table protocol
// (docs/PROTOCOL.md). This is the only way the page learns anything about the
// game, and it knows nothing about the scene.

export async function loadEngine(bytes) {
  const { instance } = await WebAssembly.instantiate(bytes, {});
  const ex = instance.exports;
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  return {
    start(level, seed) {
      ex.piquet_new(level, seed);
    },
    // Read memory.buffer afresh every time: the module may grow its memory,
    // which detaches any view taken before.
    state() {
      const view = new Uint8Array(ex.memory.buffer, ex.piquet_state(), ex.piquet_state_len());
      return JSON.parse(dec.decode(view));
    },
    send(command) {
      const bytes = enc.encode(command);
      const at = ex.piquet_alloc(bytes.length);
      new Uint8Array(ex.memory.buffer, at, bytes.length).set(bytes);
      return ex.piquet_send(bytes.length) === 1;
    },
  };
}

export function decodeBase64(text) {
  return Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
}
