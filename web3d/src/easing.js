// Easing: how a movement is spread over its time. Each takes t in [0, 1] and
// returns how far along the movement is, 0 at the start and 1 at the end,
// clamping outside. The physics behind each is in docs/TABLE3D.md section 7.1.

const clamp01 = (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t);

// A hand-guided movement. Human reaching follows the minimum-jerk profile
// (Flash & Hogan, 1985): at rest and unaccelerated at both ends, peaking at
// 1.875 times its mean speed halfway.
export function minimumJerk(t) {
  const u = clamp01(t);
  return u * u * u * (10 - 15 * u + 6 * u * u);
}

// Something pushed and let go, sliding to a stop against constant friction:
// it decelerates evenly from its starting speed and stops exactly at the end.
export function friction(t) {
  const u = clamp01(t);
  return 1 - (1 - u) * (1 - u);
}

// Falling from rest: accelerating evenly all the way.
export function gravity(t) {
  const u = clamp01(t);
  return u * u;
}

// Evenly accelerated -- a constant force -- starting at `startSlope` times the
// mean speed and so ending at 2 - startSlope. Friction is evenly(2), gravity
// from rest is evenly(0); in between, a thing already moving that a force
// slows or speeds.
export function evenly(startSlope) {
  return (t) => {
    const u = clamp01(t);
    return startSlope * u + (1 - startSlope) * u * u;
  };
}

// A CSS cubic-bezier(x1, y1, x2, y2): find the curve parameter whose x is t
// (Newton's method, falling back to bisection), and return its y.
export function cubicBezier(x1, y1, x2, y2) {
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;
  const x = (u) => ((ax * u + bx) * u + cx) * u;
  const y = (u) => ((ay * u + by) * u + cy) * u;
  const dx = (u) => (3 * ax * u + 2 * bx) * u + cx;

  function solve(t) {
    let u = t;
    for (let i = 0; i < 8; i++) {
      const err = x(u) - t;
      if (Math.abs(err) < 1e-9) return u;
      const d = dx(u);
      if (Math.abs(d) < 1e-9) break;
      u -= err / d;
    }
    let lo = 0;
    let hi = 1;
    u = t;
    for (let i = 0; i < 60; i++) {
      const v = x(u);
      if (Math.abs(v - t) < 1e-10) break;
      if (v < t) lo = u;
      else hi = u;
      u = (lo + hi) / 2;
    }
    return u;
  }

  const ease = (t) => {
    const u = clamp01(t);
    if (u === 0 || u === 1) return u;
    return y(solve(u));
  };
  return ease;
}

// Material 3's easing and duration tokens, as @material/web 2.5.0 ships them
// (tokens/versions/latest/sass/_md-sys-motion.scss).
export const M3 = Object.freeze({
  standard: cubicBezier(0.2, 0, 0, 1),
  standardAccelerate: cubicBezier(0.3, 0, 1, 1),
  standardDecelerate: cubicBezier(0, 0, 0, 1),
  emphasizedAccelerate: cubicBezier(0.3, 0, 0.8, 0.15),
  emphasizedDecelerate: cubicBezier(0.05, 0.7, 0.1, 1),
});

export const M3_MS = Object.freeze({
  short1: 50, short2: 100, short3: 150, short4: 200,
  medium1: 250, medium2: 300, medium3: 350, medium4: 400,
  long1: 450, long2: 500, long3: 550, long4: 600,
  extraLong1: 700, extraLong2: 800, extraLong3: 900, extraLong4: 1000,
});
