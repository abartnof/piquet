//! The Piquet rules engine.
//!
//! A port of the Python implementation under `python/`, which remains the
//! oracle: it is the version that passes the full test suite, it generates the
//! golden vectors in `vectors/`, and it is not retired until this crate
//! reproduces both them and the measured rating ladder.
//!
//! Every hazard catalogued in `docs/DESIGN.md` §2.1 was a consequence of
//! JavaScript having no unsigned integer type and only 53 bits of safe
//! integer. None of them survive here: a hand is a `u32`, popcount is
//! `count_ones`, and the solver's 75-bit transposition key is a `u128`.

pub mod agents;
pub mod cards;
pub mod chances;
pub mod combos;
pub mod declarations;
pub(crate) mod mt19937;

/// Exposed only so the golden tests can check the generator directly.
pub mod test_support {
    pub use crate::mt19937::MersenneTwister;
    pub fn seeded_rng(seed: u32) -> MersenneTwister {
        MersenneTwister::seeded(seed)
    }
}
pub mod heuristics;
pub mod inference;
pub mod observation;
pub mod opponents;
pub mod options;
pub mod partie;
pub mod play;
pub mod rng;
pub mod rules;
pub mod scoring;
pub mod solver;
pub mod style;
pub mod table;
pub mod tournament;
pub(crate) mod util;
