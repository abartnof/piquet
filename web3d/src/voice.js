// The voice at the table: plays the phrases speech.js asks for, in turn,
// in the voice of whoever says them (docs/VOICE.md). The clips are bundled
// into the page, base64, by web3d/build.py from web3d/audio/, so it works
// offline; each is decoded the first time it is needed.
//
// Everything is said in several ways (docs/PHRASES.md), and each speaker
// picks among them without repeating themselves (bag.js). Each line waits
// for its moment -- the animation's beat for the event it belongs to -- so
// nothing is said before it is seen to happen.
//
// createVoice(voices) -> { say(lines, prefs), wake(), stop(), stats() }
//   voices: { cori: { gender, format, clips: { key: base64 },
//                     groups: { id: [key] }, texts: { key: words } }, ... }
//   lines:  [{ who: "you"|"them", clip, delay }] from speech(): clip is a
//           group id; delay the ms from now until its moment (0 if absent)
//   prefs:  { voice: on/off, opponentVoice: "cori"|"norman", sayMine: on/off }

import { createBags } from "./bag.js";

const GAP = 0.09; // s between one speaker's phrases
const TURN = 0.28; // s when the other speaks
// Decoded clips kept at once: a partie hears about a hundred different
// things, and each decoded second is 190 kB of memory.
const KEEP = 160;

// Words an English voice would say wrongly, respelt as English it knows --
// the same table the recordings are made with (web3d/tools/voice.py,
// docs/VOICE.md §1), for a browser speaking in its own voice.
const RESPELL = { quart: "cart", quatorze: "kuh-torz", capot: "kuh-pot", sixième: "seez yem", septième: "set yem", huitième: "wheat yem", piquet: "pick-ett" };

export function createVoice(voices) {
  let context = null;
  const pick = createBags();
  // A browser that cannot play the recorded clips (Ogg Opus: Safari before
  // 18.4) speaks the same words in its own voice instead.
  const format = Object.values(voices)[0]?.format;
  const probe = typeof document !== "undefined" ? document.createElement("audio") : null;
  const recorded = !!format && !!probe && probe.canPlayType(format === "ogg" ? 'audio/ogg; codecs="opus"' : "audio/mpeg") !== "";
  const fallback = !recorded && typeof window !== "undefined" && "speechSynthesis" in window;
  const decoded = new Map(); // `${voice}/${key}` -> Promise<AudioBuffer|null>, oldest first
  let next = 0; // when the queue is free, in context time
  let lastWho = null;
  let playing = [];
  let queue = Promise.resolve(); // batches, strictly in turn
  let generation = 0; // bumped by stop(): batches still waiting are dropped
  const stats = { said: [], picked: [], decoded: 0, played: 0, failed: 0, dropped: 0 };
  // One way of saying a group, in this voice: never the same twice running.
  const choose = (voice, clip) => pick(`${voice}/${clip}`, voices[voice]?.groups?.[clip]);

  // Browsers let sound start only after the player has touched the page, and
  // may put it to sleep again -- Safari "interrupts" it when the window loses
  // the audio -- so it is woken whenever it is not running, and above all
  // from a click or a key (wake), where every browser allows it.
  function audio() {
    if (!context) {
      const Context = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext);
      if (!Context) return null;
      context = new Context();
    }
    if (context.state !== "running" && context.state !== "closed") context.resume().catch(() => {});
    return context;
  }

  async function running(ctx) {
    if (ctx.state === "running") return true;
    await Promise.race([ctx.resume().catch(() => {}), new Promise((r) => setTimeout(r, 400))]);
    return ctx.state === "running";
  }

  function buffer(voice, key) {
    const id = `${voice}/${key}`;
    if (decoded.has(id)) {
      const kept = decoded.get(id);
      decoded.delete(id); // most recently used goes to the end
      decoded.set(id, kept);
      return kept;
    }
    const data = key && voices[voice]?.clips?.[key];
    const made = data
      ? audio()
        .decodeAudioData(Uint8Array.from(atob(data), (c) => c.charCodeAt(0)).buffer)
        .then((clip) => {
          stats.decoded += 1;
          return clip;
        }, () => {
          stats.failed += 1;
          return null;
        })
      : Promise.resolve(null);
    decoded.set(id, made);
    while (decoded.size > KEEP) decoded.delete(decoded.keys().next().value);
    return made;
  }

  const otherVoice = (name) => Object.keys(voices).find((v) => v !== name) ?? name;

  async function speak(lines, prefs, asked, mine) {
    const theirs = voices[prefs.opponentVoice] ? prefs.opponentVoice : Object.keys(voices)[0];
    const ours = otherVoice(theirs);
    const wanted = lines.filter((line) => line.who === "them" || prefs.sayMine !== false);
    const speaker = (line) => (line.who === "them" ? theirs : ours);
    const keys = wanted.map((line) => choose(speaker(line), line.clip));
    stats.picked.push(...keys);
    if (!recorded) {
      if (!fallback) return;
      wanted.forEach((line, i) => {
        const text = voices[speaker(line)]?.texts?.[keys[i]] ?? "";
        const words = text.replace(/[A-Za-zÀ-ÿ]+/g, (w) => RESPELL[w.toLowerCase()] ?? w);
        if (!words) return;
        const wait = Math.max(0, (line.delay ?? 0) - (performance.now() - asked));
        setTimeout(() => mine === generation && window.speechSynthesis.speak(new SpeechSynthesisUtterance(words)), wait);
      });
      return;
    }
    const ctx = audio();
    if (!ctx) return;
    const buffers = await Promise.all(wanted.map((line, i) => buffer(speaker(line), keys[i])));
    if (mine !== generation) return; // stopped while decoding
    if (!(await running(ctx))) {
      // Asleep and not to be woken: say nothing now rather than all of it
      // at once, late, when it is.
      stats.dropped += wanted.length;
      return;
    }
    const elapsed = (performance.now() - asked) / 1000;
    wanted.forEach((line, i) => {
      const clip = buffers[i];
      if (!clip) return;
      const moment = ctx.currentTime + Math.max(0.02, (line.delay ?? 0) / 1000 - elapsed);
      const gap = lastWho === null ? 0 : line.who === lastWho ? GAP : TURN;
      const start = Math.max(moment, next + gap);
      const source = ctx.createBufferSource();
      source.buffer = clip;
      source.connect(ctx.destination);
      source.start(start);
      source.onended = () => (playing = playing.filter((s) => s !== source));
      playing.push(source);
      stats.played += 1;
      next = start + clip.duration;
      lastWho = line.who;
    });
  }

  return {
    // Queue lines: each batch after the one before, each line at its moment
    // and after the line before it has ended.
    say(lines, prefs = {}) {
      if (!prefs.voice || !lines.length) return queue;
      stats.said.push(...lines.map((line) => `${line.who}:${line.clip}`));
      const asked = performance.now();
      const mine = generation;
      const run = () => (mine === generation ? speak(lines, prefs, asked, mine) : undefined);
      queue = queue.then(run, run).catch(() => {});
      return queue;
    },
    // From a click or a key, or the page shown again: wake the sound.
    wake() {
      if (recorded) audio();
    },
    // For the browser test: what was asked for, decoded, played.
    stats: () => ({ recorded, state: context?.state ?? null, ...stats }),
    // Undo, a new partie, the voice switched off: silence at once, and
    // nothing still waiting is said.
    stop() {
      generation += 1;
      if (fallback) window.speechSynthesis.cancel();
      for (const source of playing) {
        try {
          source.stop();
        } catch (e) {
          /* already ended */
        }
      }
      playing = [];
      next = 0;
      lastWho = null;
    },
  };
}
