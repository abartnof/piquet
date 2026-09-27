//! Does the fitted world prior make the solver stronger? Mirrored pairs, in
//! deal points: the solver weighing the opponent's hands by `prior::RUNG4`
//! against the same solver weighing them alike.
//!
//! `priorduel [pairs] [seed]`. The prior was fitted on deals from seed 9001
//! (`bin/prior`); the default seed here is another.
use piquet_core::prior::RUNG4;
use piquet_core::solver::SolverAgent;
use piquet_core::tournament::duel;

fn main() {
    let pairs: usize = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(200);
    let seed: u32 = std::env::args()
        .nth(2)
        .and_then(|a| a.parse().ok())
        .unwrap_or(2718);
    let mut weighed = SolverAgent::new(7).with_prior(RUNG4);
    let mut plain = SolverAgent::new(7);
    let r = duel(&mut weighed, &mut plain, pairs, seed).expect("a duel completes");
    println!(
        "  {} vs {} over {pairs} pairs (seed {seed}): {:.1}% of decided pairs, margin {:+.2} points per pair",
        r.name_a, r.name_b, 100.0 * r.a_win_rate(), r.margin()
    );
    println!("  {r:?}");
}
