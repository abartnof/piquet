//! The partie objective's real test (`PLAN.md` TODO 1): whole parties, the
//! settling search against the flat one, both weighing the opponent's hands
//! by the fitted prior (`prior::RUNG4`), scored in settlement.
//!
//! On 720 stacked last deals settling won by +10.53 ± 3.16 a deal once both
//! agents had the prior. A whole partie is the question that pays: most of
//! its deals are nowhere near the rubicon, most mirrored pairs come out
//! exactly level, and the spread is the rare flip -- so it wants many pairs,
//! and runs them on every core it is given.
//!
//! `partieprior PAIRS THREADS [FIRST_SEED] [--out FILE]`: one mirrored partie
//! per seed, FIRST_SEED onward; each pair's settlement to the settling side
//! is written to FILE, one line a pair, and summed up at the end.

use piquet_core::prior::RUNG4;
use piquet_core::solver::SolverAgent;
use piquet_core::tournament::partie_duel;
use std::io::Write;
use std::time::Instant;

/// One mirrored partie: the settlement to the settling side over both halves.
fn pair(seed: u32) -> i32 {
    let mut settling = SolverAgent::new(3).with_prior(RUNG4).settling();
    let mut flat = SolverAgent::new(5).with_prior(RUNG4);
    let result = partie_duel(&mut settling, &mut flat, 1, seed).expect("a partie duel completes");
    result.a_settlement
}

fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let out = args.iter().position(|a| a == "--out").map(|at| {
        let path = args.get(at + 1).cloned().expect("--out needs a file");
        args.drain(at..at + 2);
        path
    });
    let number =
        |i: usize, default: u32| args.get(i).and_then(|a| a.parse().ok()).unwrap_or(default);
    let pairs = number(0, 100);
    let threads = number(1, 1).max(1);
    let first = number(2, 100_000);

    let start = Instant::now();
    let mut results: Vec<(u32, i32)> = std::thread::scope(|scope| {
        let workers: Vec<_> = (0..threads)
            .map(|t| {
                scope.spawn(move || {
                    (first + t..first + pairs)
                        .step_by(threads as usize)
                        .map(|seed| (seed, pair(seed)))
                        .collect::<Vec<_>>()
                })
            })
            .collect();
        workers
            .into_iter()
            .flat_map(|w| w.join().expect("a worker finishes"))
            .collect()
    });
    results.sort_unstable();

    if let Some(path) = out {
        let mut file =
            std::io::BufWriter::new(std::fs::File::create(&path).expect("the record is writable"));
        writeln!(
            file,
            "# partieprior {pairs} {threads} {first}\n# seed\tsettlement_to_settling"
        )
        .unwrap();
        for (seed, settlement) in &results {
            writeln!(file, "{seed}\t{settlement}").unwrap();
        }
    }

    let values: Vec<f64> = results.iter().map(|(_, s)| f64::from(*s)).collect();
    let n = values.len() as f64;
    let mean = values.iter().sum::<f64>() / n;
    let error = if values.len() > 1 {
        (values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n - 1.0) / n).sqrt()
    } else {
        0.0
    };
    let count = |f: &dyn Fn(i32) -> bool| results.iter().filter(|(_, s)| f(*s)).count();
    println!("  whole mirrored parties, settling against flat, both with the fitted prior");
    println!(
        "  {pairs} pairs on {threads} threads in {:.0} s ({:.1} s a pair per thread)",
        start.elapsed().as_secs_f64(),
        start.elapsed().as_secs_f64() * f64::from(threads) / n
    );
    println!(
        "  level {}, settling ahead {} (by more than 150: {}), behind {} (by more than 150: {})",
        count(&|s| s == 0),
        count(&|s| s > 0),
        count(&|s| s > 150),
        count(&|s| s < 0),
        count(&|s| s < -150)
    );
    println!(
        "  net settlement per pair: {mean:+.2} ± {error:.2}  ({:.1} sigma)",
        if error > 0.0 { mean.abs() / error } else { 0.0 }
    );
}
