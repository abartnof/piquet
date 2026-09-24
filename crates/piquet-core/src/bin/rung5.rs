//! Does rung five still beat rung four by what the Python measured?
//!
//! `PLAN.md`: the solver beats L4 by **82.5% / +5.0 points per pair** over 100
//! mirrored pairs. Reproducing the four heuristic rungs was only half the
//! parity gate; this is the other half.
use piquet_core::heuristics::HeuristicAgent;
use piquet_core::solver::SolverAgent;
use piquet_core::tournament::duel;

fn main() {
    let pairs: usize = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(100);
    let mut solver = SolverAgent::new(7);
    let mut ladder = HeuristicAgent::new(4, 13).unwrap().named("L4");
    let result = duel(&mut solver, &mut ladder, pairs, 1674).expect("a duel completes");
    println!(
        "  {} vs {} over {pairs} pairs: {:.1}%  margin {:+.1} points per pair",
        result.name_a,
        result.name_b,
        100.0 * result.a_win_rate(),
        result.margin()
    );
    println!("  Python reference: 82.5% / +5.0");
}
