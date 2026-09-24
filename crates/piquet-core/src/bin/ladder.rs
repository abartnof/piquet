//! Rate the capability ladder, and check it against the Python's measurement.
//!
//! The parity gate `PLAN.md` asks for: the port is not finished until the Rust
//! reproduces the measured ratings as well as the golden vectors. Ratings are
//! a statistic over mirrored pairs, so they will not match to the point --
//! different agents draw from different generators -- but the *ordering* and
//! the rough spacing must survive, or the ladder has stopped being a ladder.
//!
//! Reference, from `PLAN.md`, 500 mirrored pairs per pairing, anchored on
//! random play: **L1 335, L2 776, L3 816, L4 863.**

use piquet_core::agents::{Agent, RandomAgent};
use piquet_core::heuristics::HeuristicAgent;
use piquet_core::tournament::{duel, ratings, DuelResult};

fn main() {
    let pairs: usize = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(500);

    // One shared set of deals for every pairing, so the whole table is a
    // paired comparison rather than each duel separately.
    let deal_seed = 1674u32;

    let build = |which: usize, seed: u32| -> Box<dyn Agent> {
        match which {
            0 => Box::new(RandomAgent::new(seed)),
            level => Box::new(HeuristicAgent::new(level as u32, seed).expect("a valid level")),
        }
    };
    let entrants = [0usize, 1, 2, 3, 4];

    let mut results: Vec<DuelResult> = Vec::new();
    for (i, a) in entrants.iter().enumerate() {
        for b in entrants.iter().skip(i + 1) {
            let mut agent_a = build(*a, 11 + *a as u32);
            let mut agent_b = build(*b, 29 + *b as u32);
            let result = duel(agent_a.as_mut(), agent_b.as_mut(), pairs, deal_seed)
                .expect("a duel completes");
            println!(
                "  {:>6} vs {:<6} {:5.1}%  margin {:+6.1} per pair",
                result.name_a,
                result.name_b,
                100.0 * result.a_win_rate(),
                result.margin()
            );
            results.push(result);
        }
    }

    println!("\n  ratings, anchored on random play ({pairs} pairs per pairing):");
    let mut table = ratings(&results, Some("random"), 500, 0.5);
    table.sort_by(|a, b| b.1.partial_cmp(&a.1).expect("no NaN in a rating"));
    for (name, rating) in &table {
        println!("    {name:<8} {rating:7.0}");
    }

    println!("\n  Python reference: L1 335, L2 776, L3 816, L4 863");
}
