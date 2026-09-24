//! Measure agents over **mirrored parties**, scored in settlement.
//!
//! The instrument `PLAN.md` says is needed before anything about the partie
//! objective can be judged: a deal-level harness is structurally blind to it,
//! because an agent that concedes a point to keep its opponent under a hundred
//! loses by deal points and wins by the only yardstick that pays.
//!
//! This is the **baseline**. Whatever the objective is changed to afterwards
//! has to beat these numbers, and it has to beat them here rather than in
//! deals.

use piquet_core::agents::Agent;
use piquet_core::heuristics::HeuristicAgent;
use piquet_core::solver::SolverAgent;
use piquet_core::tournament::partie_duel;

fn build(level: u32, seed: u32) -> Box<dyn Agent> {
    if level >= 5 {
        Box::new(SolverAgent::new(seed))
    } else {
        Box::new(HeuristicAgent::new(level, seed).expect("a valid level"))
    }
}

fn main() {
    let pairs: usize = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(50);
    let top: u32 = std::env::args()
        .nth(2)
        .and_then(|a| a.parse().ok())
        .unwrap_or(4);

    println!(
        "  mirrored parties, {pairs} pairs each, scored in settlement\n\
         \x20 (a pair is one partie played twice with the sides swapped)\n"
    );
    println!(
        "  {:>6} vs {:<7} {:>7}  {:>12}  {:>18}",
        "A", "B", "A wins", "net to A", "per pair"
    );

    for a in 1..=top {
        for b in (a + 1)..=top {
            let mut agent_a = build(a, 11 + a);
            let mut agent_b = build(b, 29 + b);
            let result = partie_duel(agent_a.as_mut(), agent_b.as_mut(), pairs, 1674)
                .expect("a partie duel completes");
            println!(
                "  {:>6} vs {:<7} {:6.1}%  {:>12}  {:>+18.1}",
                result.name_a,
                result.name_b,
                100.0 * result.a_win_rate(),
                result.a_settlement,
                result.margin()
            );
        }
    }
}
