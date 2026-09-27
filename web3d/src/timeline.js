// The timeline: motions run against the clock.
//
// A motion is { target, path, delay, duration, onDone }: `path(t)` gives the
// target's pose at t in [0, 1], and `apply(target, pose)` -- supplied by the
// scene -- puts it there. The clock is passed in, so the timeline can be
// driven by requestAnimationFrame in the page and by hand in a test. `speed`
// scales every delay and duration; a duration of zero lands at once.

export class Timeline {
  constructor({ apply, speed = 1 }) {
    this.apply = apply;
    this.speed = speed;
    this.motions = [];
    this.now = 0;
    this.waiters = [];
  }

  add({ target, path, delay = 0, duration, onDone }, now = this.now) {
    this.now = Math.max(this.now, now);
    const start = now + delay / this.speed;
    this.motions.push({ target, path, start, length: duration / this.speed, onDone });
    this.motions.sort((a, b) => a.start - b.start);
  }

  // Apply every motion that has started, in the order they started; drop the
  // ones that have landed. Returns whether anything is still to move.
  tick(now) {
    this.now = now;
    const landed = [];
    for (const m of this.motions) {
      if (now < m.start) continue;
      const t = m.length > 0 ? Math.min(1, (now - m.start) / m.length) : 1;
      this.apply(m.target, m.path(t));
      if (t >= 1) landed.push(m);
    }
    this.finish(landed);
    return this.busy();
  }

  // Land everything on its end, now.
  skip() {
    const all = [...this.motions];
    for (const m of all) this.apply(m.target, m.path(1));
    this.finish(all);
  }

  busy() {
    return this.motions.length > 0;
  }

  idle() {
    if (!this.busy()) return Promise.resolve();
    return new Promise((resolve) => this.waiters.push(resolve));
  }

  finish(landed) {
    if (!landed.length) return;
    this.motions = this.motions.filter((m) => !landed.includes(m));
    for (const m of landed) m.onDone?.();
    if (!this.busy()) {
      const waiters = this.waiters;
      this.waiters = [];
      for (const resolve of waiters) resolve();
    }
  }
}
