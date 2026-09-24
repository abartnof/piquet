//! What settling at the leaf costs, against the additive search.
//!
//! The additive search merges positions reached by different lines of play,
//! because its value is a sum along the path. Settling at the leaf cannot: the
//! accumulated points split differently, and the settlement is not linear in
//! them. So the question is how many more positions that is, and whether the
//! correct objective is affordable at a depth worth playing.

use std::time::Instant;

use piquet_core::cards::Hand;
use piquet_core::solver::{card_settlements, card_values, Settling, ELDER, EVEN};

fn split(n: u32) -> (Hand, Hand) {
    let (mut elder, mut younger) = (0u32, 0u32);
    for i in 0..n {
        elder |= 1 << (2 * i);
        younger |= 1 << (2 * i + 1);
    }
    (Hand(elder), Hand(younger))
}

fn main() {
    let max: u32 = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(8);

    // A last deal with both sides short of the rubicon: the position where the
    // objectives come apart hardest, since crossing turns what the loser pays
    // from the sum into the difference.
    let ctx = Settling {
        elder_side: 82,
        younger_side: 70,
        elder_so_far: 0,
        younger_so_far: 0,
        deals_left: 1,
        elder_first_next: false,
    };

    println!(
        "{:>7}  {:>12}  {:>14}  {:>8}",
        "tricks", "additive (ms)", "settling (ms)", "ratio"
    );
    for n in 4..=max {
        let (elder, younger) = split(n);

        let start = Instant::now();
        let additive = card_values(elder, younger, ELDER, None, 12 - n, EVEN).unwrap();
        let additive_ms = start.elapsed().as_secs_f64() * 1000.0;

        let start = Instant::now();
        let settling = card_settlements(elder, younger, ELDER, None, 12 - n, &ctx).unwrap();
        let settling_ms = start.elapsed().as_secs_f64() * 1000.0;

        println!(
            "{n:>7}  {additive_ms:>12.2}  {settling_ms:>14.2}  {:>8.1}x",
            settling_ms / additive_ms.max(1e-9)
        );

        if n == max {
            // Do the two objectives even disagree about what to play?
            let best_additive = additive
                .iter()
                .max_by_key(|(_, v)| *v)
                .map(|(c, _)| piquet_core::cards::card_code(*c));
            let best_settling = settling
                .iter()
                .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap())
                .map(|(c, _)| piquet_core::cards::card_code(*c));
            println!(
                "\n  at {n} tricks, from 82 against 70 with one deal left:\n    \
                 additive would play {best_additive:?}\n    settling would play {best_settling:?}"
            );
        }
    }
}
