//! Fit the solver's world prior on the positions it actually searches.
//!
//! Plays mirrored last deals exactly as `settle` does -- the same standings,
//! the same agents in the same chairs -- but from a different shuffle, so the
//! fitted weights are never scored on the deals they were fitted to. At every
//! decision the solver searches, it records every hand the opponent could
//! hold and the hand she held, then fits `prior::fit` on half the deals and
//! scores it on the other half.
//!
//! As a check on the inference, it counts any decision whose true hand is
//! missing from the consistent set: the solver averaging over worlds none of
//! which is real, which has happened before (`PLAN.md`, code review, second
//! pass).
//!
//! `prior [deals per standing] [ridge]`

use piquet_core::agents::Agent;
use piquet_core::cards::{Card, Hand};
use piquet_core::declarations::Declaration;
use piquet_core::inference::possible_hands;
use piquet_core::observation::View;
use piquet_core::partie::Standing;
use piquet_core::play::play_deal;
use piquet_core::prior::{fit, log_likelihood, RankPrior, Sample};
use piquet_core::rng::Rng;
use piquet_core::rules::deal_from;
use piquet_core::scoring::{Category, Player};
use piquet_core::solver::SolverAgent;

/// The standings `settle` plays, elder's side first.
const STANDINGS: [(i32, i32); 6] = [(82, 70), (70, 82), (95, 88), (88, 95), (120, 88), (88, 120)];

/// Keeps every view the solver would search from.
struct Keep(SolverAgent, Vec<View>);

impl Agent for Keep {
    fn name(&self) -> &str {
        self.0.name()
    }
    fn exchange(&mut self, view: &View) -> Hand {
        self.0.exchange(view)
    }
    fn declare(&mut self, view: &View, category: Category) -> Declaration {
        self.0.declare(view, category)
    }
    fn play(&mut self, view: &View) -> Card {
        if view.legal_plays.len() > 1 && view.hand.len() <= self.0.exact_from {
            self.1.push(view.clone());
        }
        self.0.play(view)
    }
}

const RANKS: [&str; 8] = ["7", "8", "9", "10", "J", "Q", "K", "A"];

fn main() {
    let deals: usize = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(60);
    let ridge: f64 = std::env::args()
        .nth(2)
        .and_then(|a| a.parse().ok())
        .unwrap_or(1.0);

    // Samples by deal, so the split into fitting and scoring halves never
    // puts two decisions from one deal on opposite sides.
    let mut by_deal: Vec<Vec<Sample>> = Vec::new();
    let mut missing = 0usize;
    let mut rng = Rng::seeded(9001);
    for (mine, theirs) in STANDINGS {
        let standing = Standing {
            mine,
            theirs,
            deals_left: 1,
            number: 6,
        };
        for _ in 0..deals {
            let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
            rng.shuffle(&mut pack);
            for settling_elder in [true, false] {
                let elder = SolverAgent::new(3);
                let younger = SolverAgent::new(5);
                let (elder, younger) = if settling_elder {
                    (elder.settling(), younger)
                } else {
                    (elder, younger.settling())
                };
                let mut elder = Keep(elder, Vec::new());
                let mut younger = Keep(younger, Vec::new());
                let (deal, _) = play_deal(
                    deal_from(&pack).unwrap(),
                    &mut elder,
                    &mut younger,
                    Some(standing),
                )
                .unwrap();

                let twelve = |seat: Player| -> u32 {
                    deal.tricks.iter().fold(0u32, |bits, t| {
                        let card = if t.leader == seat {
                            t.led
                        } else {
                            t.followed.expect("a finished deal's tricks are complete")
                        };
                        bits | 1 << card.0
                    })
                };
                let mut samples = Vec::new();
                for view in elder.1.iter().chain(younger.1.iter()) {
                    let mut theirs_now = twelve(view.opponent());
                    for t in view.tricks.iter().chain(view.current_trick.iter()) {
                        for card in [Some(t.led), t.followed].into_iter().flatten() {
                            theirs_now &= !(1 << card.0);
                        }
                    }
                    let truth = Hand(theirs_now);
                    let mut unused = Rng::seeded(1);
                    let worlds = possible_hands(view, Some(1_000_000), true, &mut unused);
                    if !worlds.contains(&truth) {
                        missing += 1;
                        continue;
                    }
                    samples.push(Sample { worlds, truth });
                }
                by_deal.push(samples);
            }
        }
    }

    let (fitting, scoring): (Vec<_>, Vec<_>) = by_deal
        .into_iter()
        .enumerate()
        .partition(|(i, _)| i % 2 == 0);
    let fitting: Vec<Sample> = fitting.into_iter().flat_map(|(_, s)| s).collect();
    let scoring: Vec<Sample> = scoring.into_iter().flat_map(|(_, s)| s).collect();
    let decisions = fitting.len() + scoring.len();
    println!(
        "  {decisions} searched decisions from {} deals; true hand missing from the consistent set in {missing}",
        deals * STANDINGS.len() * 2
    );

    let prior = fit(&fitting, ridge);
    println!("\n  fitted on {} decisions, ridge {ridge}:", fitting.len());
    println!(
        "    {}",
        RANKS
            .iter()
            .zip(prior.0)
            .map(|(r, v)| format!("{r} {v:+.2}"))
            .collect::<Vec<_>>()
            .join("   ")
    );
    println!(
        "    as a constant: {:?}",
        prior.0.map(|v| (v * 1000.0).round() / 1000.0)
    );

    let uniform = log_likelihood(&RankPrior::UNIFORM, &scoring);
    let fitted = log_likelihood(&prior, &scoring);
    println!(
        "\n  held out ({} decisions), mean log-likelihood of the true hand:",
        scoring.len()
    );
    println!(
        "    uniform {uniform:.4}   fitted {fitted:.4}   gain {:+.4} nats a decision",
        fitted - uniform
    );

    // Calibration by rank, held out: for each card that is hers in some
    // worlds and not others, how often it really was hers, against what
    // each prior believed.
    println!("\n  held out, cards whose ownership is in doubt:");
    println!("    rank   cards   really hers   uniform believed   fitted believed");
    for rank in 0..8 {
        let (mut n, mut hers, mut by_uniform, mut by_fitted) = (0usize, 0usize, 0.0f64, 0.0f64);
        for sample in &scoring {
            let everywhere = sample.worlds.iter().fold(u32::MAX, |acc, h| acc & h.0);
            let anywhere = sample.worlds.iter().fold(0u32, |acc, h| acc | h.0);
            let doubtful = anywhere & !everywhere;
            let weights: Vec<f64> = sample.worlds.iter().map(|h| prior.weight(*h)).collect();
            let total: f64 = weights.iter().sum();
            for card in Hand(doubtful).iter().filter(|c| c % 8 == rank) {
                n += 1;
                hers += usize::from(sample.truth.contains(card));
                let holding: Vec<bool> = sample.worlds.iter().map(|h| h.contains(card)).collect();
                by_uniform +=
                    holding.iter().filter(|&&x| x).count() as f64 / sample.worlds.len() as f64;
                by_fitted += holding
                    .iter()
                    .zip(&weights)
                    .filter(|(x, _)| **x)
                    .map(|(_, w)| w)
                    .sum::<f64>()
                    / total;
            }
        }
        if n == 0 {
            continue;
        }
        let nf = n as f64;
        println!(
            "    {:>4}   {n:>5}   {:>10.0}%   {:>15.0}%   {:>14.0}%",
            RANKS[rank as usize],
            100.0 * hers as f64 / nf,
            100.0 * by_uniform / nf,
            100.0 * by_fitted / nf
        );
    }
}
