// The voice at the table: plays the phrases speech.js asks for, in turn,
// in the voice of whoever says them (docs/VOICE.md). The clips are bundled
// into the page, base64, by web3d/build.py from web3d/audio/, so it works
// offline; each is decoded the first time it is needed.
//
// createVoice(voices) -> { say(lines, prefs), stop() }
//   voices: { cori: { gender, clips: { id: base64 } }, norman: {...} }
//   lines:  [{ who: "you"|"them", clip }] from speech()
//   prefs:  { voice: on/off, opponentVoice: "cori"|"norman", sayMine: on/off }

const GAP = 0.09; // s between one speaker's phrases
const TURN = 0.28; // s when the other speaks

// Words the browser's own voice would say wrongly, respelled for it -- the
// fallback has no phonemes (docs/VOICE.md, §1).
const RESPELL = { quart: "cart", quatorze: "katorz", capot: "kapot", sixième: "see zyem", septième: "set yem", huitième: "weet yem" };

export function createVoice(voices, texts = {}) {
  let context = null;
  // A browser that cannot play the recorded clips (Ogg Opus: Safari before
  // 18.4) speaks the same words in its own voice instead.
  const format = Object.values(voices)[0]?.format;
  const probe = typeof document !== "undefined" ? document.createElement("audio") : null;
  const recorded = !!format && !!probe && probe.canPlayType(format === "ogg" ? 'audio/ogg; codecs="opus"' : "audio/mpeg") !== "";
  const fallback = !recorded && typeof window !== "undefined" && "speechSynthesis" in window;
  const decoded = new Map(); // `${voice}/${clip}` -> Promise<AudioBuffer>
  let next = 0; // when the queue is free, in context time
  let lastWho = null;
  let playing = [];
  const stats = { said: [], decoded: 0, played: 0, failed: 0 };

  // Browsers let sound start only after the player has touched the page;
  // every call comes from a click or a key, so the context is made then.
  function audio() {
    if (!context) {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) return null;
      context = new Context();
    }
    if (context.state === "suspended") context.resume();
    return context;
  }

  function buffer(voice, clip) {
    const key = `${voice}/${clip}`;
    if (!decoded.has(key)) {
      const data = voices[voice]?.clips?.[clip];
      decoded.set(key, data
        ? audio()
          .decodeAudioData(Uint8Array.from(atob(data), (c) => c.charCodeAt(0)).buffer)
          .then((clip) => {
            stats.decoded += 1;
            return clip;
          }, () => {
            stats.failed += 1;
            return null;
          })
        : Promise.resolve(null));
    }
    return decoded.get(key);
  }

  const otherVoice = (name) => Object.keys(voices).find((v) => v !== name) ?? name;

  return {
    // Queue a speaker's lines: each starts when the one before has ended.
    async say(lines, prefs = {}) {
      if (!prefs.voice || !lines.length) return;
      stats.said.push(...lines.map((line) => `${line.who}:${line.clip}`));
      if (!recorded) {
        if (!fallback) return;
        for (const line of lines) {
          if (line.who === "you" && prefs.sayMine === false) continue;
          const words = (texts[line.clip] ?? "").replace(/[A-Za-zÀ-ÿ]+/g, (w) => RESPELL[w.toLowerCase()] ?? w);
          if (words) window.speechSynthesis.speak(new SpeechSynthesisUtterance(words));
        }
        return;
      }
      if (!audio()) return;
      const theirs = voices[prefs.opponentVoice] ? prefs.opponentVoice : Object.keys(voices)[0];
      const mine = otherVoice(theirs);
      const wanted = lines.filter((line) => line.who === "them" || prefs.sayMine !== false);
      const buffers = await Promise.all(wanted.map((line) => buffer(line.who === "them" ? theirs : mine, line.clip)));
      const ctx = audio();
      wanted.forEach((line, i) => {
        const clip = buffers[i];
        if (!clip) return;
        const gap = lastWho === null ? 0 : line.who === lastWho ? GAP : TURN;
        const start = Math.max(ctx.currentTime + 0.02, next + gap);
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
    },
    // For the browser test: what was asked for, decoded, played.
    stats: () => ({ recorded, ...stats }),
    // Undo, a new partie, the voice switched off: silence at once.
    stop() {
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
