//! Time the exact search against the Python baseline.
//!
//! `docs/DESIGN.md` §13.7 made this the deciding measurement: every speed
//! estimate in §13 rests on the solver, and none of them had been measured.
//! The positions are the same ones the Python was timed on -- alternate cards
//! off the pack, n each -- so the two numbers are comparable.

use std::time::Instant;

use piquet_core::cards::Hand;
use piquet_core::solver::{solve_with_stats, ELDER, EVEN};

/// A deterministic n-card-each position: alternate cards off the pack.
fn split(n: u32) -> (Hand, Hand) {
    let mut elder = 0u32;
    let mut younger = 0u32;
    for i in 0..n {
        elder |= 1 << (2 * i);
        younger |= 1 << (2 * i + 1);
    }
    (Hand(elder), Hand(younger))
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let max: u32 = args.get(1).and_then(|a| a.parse().ok()).unwrap_or(8);
    let repeats: u32 = args.get(2).and_then(|a| a.parse().ok()).unwrap_or(5);

    println!(
        "{:>7}  {:>12}  {:>8}  {:>14}",
        "tricks", "best (ms)", "value", "positions"
    );
    for n in 4..=max {
        let (elder, younger) = split(n);
        let mut best = f64::INFINITY;
        let mut value = 0i64;
        let mut positions = 0usize;
        for _ in 0..repeats {
            let start = Instant::now();
            let (v, p) = solve_with_stats(elder, younger, ELDER, None, 12 - n, EVEN).unwrap();
            let elapsed = start.elapsed().as_secs_f64() * 1000.0;
            best = best.min(elapsed);
            value = v;
            positions = p;
        }
        println!("{n:>7}  {best:>12.3}  {value:>8}  {positions:>14}");
    }
}
