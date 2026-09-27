// The timeline: motions run against the clock.
//
// A motion is { target, path, delay, duration, onStart, onDone }: `path(t)`
// gives the target's pose at t in [0, 1], and `apply(target, pose)` --
// supplied by the scene -- puts it there. `onStart` runs once, just before a
// motion's first pose (a card's face shown as it turns up); `onDone` once,
// after its last. The clock is passed in, so the timeline can be
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

  add({ target, path, delay = 0, duration, onStart, onDone }, now = this.now) {
    this.now = Math.max(this.now, now);
    const start = now + delay / this.speed;
    this.motions.push({ target, path, start, length: duration / this.speed, onStart, onDone, started: false });
    this.motions.sort((a, b) => a.start - b.start);
  }

  // Apply every motion that has started, in the order they started, each
  // finished before the next is touched -- so a card hidden as one motion
  // lands and shown as its next begins ends up shown. Returns whether
  // anything is still to move.
  tick(now) {
    this.now = now;
    const landed = [];
    for (const m of this.motions) {
      if (now < m.start) continue;
      const t = m.length > 0 ? Math.min(1, (now - m.start) / m.length) : 1;
      this.begin(m);
      this.apply(m.target, m.path(t));
      if (t >= 1) {
        m.onDone?.();
        landed.push(m);
      }
    }
    this.drop(landed);
    return this.busy();
  }

  // Land everything on its end, now, in the same order.
  skip() {
    const all = [...this.motions];
    for (const m of all) {
      this.begin(m);
      this.apply(m.target, m.path(1));
      m.onDone?.();
    }
    this.drop(all);
  }

  begin(m) {
    if (m.started) return;
    m.started = true;
    m.onStart?.();
  }

  busy() {
    return this.motions.length > 0;
  }

  idle() {
    if (!this.busy()) return Promise.resolve();
    return new Promise((resolve) => this.waiters.push(resolve));
  }

  drop(landed) {
    if (!landed.length) return;
    this.motions = this.motions.filter((m) => !landed.includes(m));
    if (!this.busy()) {
      const waiters = this.waiters;
      this.waiters = [];
      for (const resolve of waiters) resolve();
    }
  }
}
