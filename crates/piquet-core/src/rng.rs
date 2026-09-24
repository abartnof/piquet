//! A small deterministic generator for the agents.
//!
//! Built on the Mersenne Twister already present for `chances`, so the engine
//! carries one generator rather than two and needs no dependency.
//!
//! **This does not reproduce Python's agent choices, and is not meant to.**
//! `docs/DESIGN.md` §2.1 settles that: no two languages share a random number
//! generator, so fixtures are written against explicit inputs and an agent's
//! own draws are outside what the golden vectors can check. The helpers below
//! are therefore the convenient ones rather than transliterations of CPython's
//! `sample`, `gauss` and `uniform`, each of which is a distinct algorithm
//! layered on the same stream.
//!
//! What it *is* required to be is deterministic given a seed, because mirrored
//! measurement depends on replaying the same deal against two agents.

use crate::mt19937::MersenneTwister;

pub struct Rng {
    inner: MersenneTwister,
    /// One spare normal deviate: the polar method produces two at a time.
    spare_normal: Option<f64>,
}

impl Rng {
    pub fn seeded(seed: u32) -> Rng {
        Rng {
            inner: MersenneTwister::seeded(seed),
            spare_normal: None,
        }
    }

    /// A float in `[0, 1)`, with 53 bits of randomness, as CPython's
    /// `random.random` produces.
    pub fn next_f64(&mut self) -> f64 {
        let high = u64::from(self.inner.getrandbits(27));
        let low = u64::from(self.inner.getrandbits(26));
        ((high << 26) | low) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }

    /// A float in `[low, high)`.
    pub fn uniform(&mut self, low: f64, high: f64) -> f64 {
        low + (high - low) * self.next_f64()
    }

    /// An integer in `0..n`.
    pub fn below(&mut self, n: usize) -> usize {
        if n <= 1 {
            return 0;
        }
        self.inner.below(n as u32) as usize
    }

    /// An integer in `low..=high`.
    pub fn in_range(&mut self, low: usize, high: usize) -> usize {
        low + self.below(high - low + 1)
    }

    pub fn choice<'a, T>(&mut self, items: &'a [T]) -> &'a T {
        &items[self.below(items.len())]
    }

    /// `count` distinct items, by a partial Fisher-Yates shuffle.
    pub fn sample<T: Copy>(&mut self, items: &[T], count: usize) -> Vec<T> {
        let mut pool: Vec<T> = items.to_vec();
        let take = count.min(pool.len());
        for i in 0..take {
            let j = i + self.below(pool.len() - i);
            pool.swap(i, j);
        }
        pool.truncate(take);
        pool
    }

    /// A normal deviate, by the Marsaglia polar method.
    pub fn gauss(&mut self, mean: f64, deviation: f64) -> f64 {
        if let Some(spare) = self.spare_normal.take() {
            return mean + deviation * spare;
        }
        loop {
            let u = 2.0 * self.next_f64() - 1.0;
            let v = 2.0 * self.next_f64() - 1.0;
            let s = u * u + v * v;
            if s > 0.0 && s < 1.0 {
                let factor = (-2.0 * s.ln() / s).sqrt();
                self.spare_normal = Some(v * factor);
                return mean + deviation * u * factor;
            }
        }
    }
}
