//! CPython's Mersenne Twister, enough of it to reproduce `random.choice`.
//!
//! `chances::futures` samples behind `random.Random(1674)` -- a fixed seed,
//! chosen so that a position always values the same. That makes its output a
//! deterministic function of constants already in the source, and
//! `docs/DESIGN.md` §2.2 notes two ways to carry it across: embed the sampled
//! results as a literal, or reproduce the generator.
//!
//! This is the second. It costs about eighty lines and no binary size, where
//! embedding would have cost roughly 200 KB of tables against a 5 MB budget
//! that card art is going to want.
//!
//! **This is the only place in the engine that reproduces a Python RNG, and it
//! is deliberate.** The standing rule from §2.1 is that no two languages share
//! a random number generator, so fixtures are written against explicit inputs
//! and never a seed. That rule is about *fixtures*. Here the seed is not a
//! fixture: it is a constant of the model, fixed so the valuation is stable,
//! and reproducing it is how the two engines agree on what a point is worth.

const N: usize = 624;
const M: usize = 397;
const MATRIX_A: u32 = 0x9908_b0df;
const UPPER_MASK: u32 = 0x8000_0000;
const LOWER_MASK: u32 = 0x7fff_ffff;

#[derive(Clone)]
pub struct MersenneTwister {
    state: [u32; N],
    index: usize,
}

impl MersenneTwister {
    /// Seed exactly as CPython's `random.seed(n)` does for a positive integer:
    /// `init_by_array` over the absolute value's 32-bit words.
    pub fn seeded(seed: u32) -> MersenneTwister {
        let mut mt = MersenneTwister {
            state: [0; N],
            index: N,
        };
        mt.init_genrand(19_650_218);
        let key = [seed];

        let mut i = 1usize;
        let mut j = 0usize;
        let mut k = N.max(key.len());
        while k > 0 {
            let previous = mt.state[i - 1] ^ (mt.state[i - 1] >> 30);
            mt.state[i] = (mt.state[i] ^ previous.wrapping_mul(1_664_525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= N {
                mt.state[0] = mt.state[N - 1];
                i = 1;
            }
            if j >= key.len() {
                j = 0;
            }
            k -= 1;
        }

        let mut k = N - 1;
        while k > 0 {
            let previous = mt.state[i - 1] ^ (mt.state[i - 1] >> 30);
            mt.state[i] =
                (mt.state[i] ^ previous.wrapping_mul(1_566_083_941)).wrapping_sub(i as u32);
            i += 1;
            if i >= N {
                mt.state[0] = mt.state[N - 1];
                i = 1;
            }
            k -= 1;
        }

        mt.state[0] = 0x8000_0000;
        mt
    }

    fn init_genrand(&mut self, seed: u32) {
        self.state[0] = seed;
        for i in 1..N {
            let previous = self.state[i - 1] ^ (self.state[i - 1] >> 30);
            self.state[i] = previous.wrapping_mul(1_812_433_253).wrapping_add(i as u32);
        }
        self.index = N;
    }

    fn generate(&mut self) {
        for i in 0..N {
            let y = (self.state[i] & UPPER_MASK) | (self.state[(i + 1) % N] & LOWER_MASK);
            let mut next = self.state[(i + M) % N] ^ (y >> 1);
            if y & 1 != 0 {
                next ^= MATRIX_A;
            }
            self.state[i] = next;
        }
        self.index = 0;
    }

    /// One tempered 32-bit word.
    pub fn next_u32(&mut self) -> u32 {
        if self.index >= N {
            self.generate();
        }
        let mut y = self.state[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c_5680;
        y ^= (y << 15) & 0xefc6_0000;
        y ^= y >> 18;
        y
    }

    /// `random.getrandbits(k)` for `k` in `1..=32`.
    pub fn getrandbits(&mut self, k: u32) -> u32 {
        debug_assert!((1..=32).contains(&k));
        self.next_u32() >> (32 - k)
    }

    /// `random._randbelow(n)`: rejection sampling over `n.bit_length()` bits.
    pub fn below(&mut self, n: u32) -> u32 {
        if n == 0 {
            return 0;
        }
        let k = 32 - n.leading_zeros();
        loop {
            let r = self.getrandbits(k);
            if r < n {
                return r;
            }
        }
    }

    /// `random.choice(seq)`.
    pub fn choice<'a, T>(&mut self, items: &'a [T]) -> &'a T {
        &items[self.below(items.len() as u32) as usize]
    }
}

#[cfg(test)]
mod tests {
    use super::MersenneTwister;

    /// Reference values taken from CPython itself:
    ///
    /// ```text
    /// >>> r = random.Random(1674)
    /// >>> [r.getrandbits(9) for _ in range(12)]
    /// ```
    ///
    /// If this fails, `chances` will disagree with the oracle about what a
    /// point is worth, which would surface as a slightly different sink
    /// decision rather than as anything obviously broken.
    const PYTHON_GETRANDBITS_9: [u32; 12] =
        [424, 422, 177, 61, 329, 86, 191, 89, 473, 76, 244, 329];

    #[test]
    fn reproduces_cpython_getrandbits() {
        let mut rng = MersenneTwister::seeded(1674);
        let got: Vec<u32> = (0..12).map(|_| rng.getrandbits(9)).collect();
        assert_eq!(got, PYTHON_GETRANDBITS_9);
    }

    #[test]
    fn reproduces_cpython_randbelow() {
        // 500 is the length of the pairs table `chances` draws from, and 9 is
        // its bit length, so `below(500)` and `getrandbits(9)` agree until a
        // draw is rejected.
        let mut rng = MersenneTwister::seeded(1674);
        let got: Vec<u32> = (0..12).map(|_| rng.below(500)).collect();
        assert_eq!(got, PYTHON_GETRANDBITS_9);
    }
}
