//! How likely each consistent opponent hand is.
//!
//! `inference::possible_hands` finds every hand she could hold, and the
//! solver has always treated them as equally likely. They are not: the cards
//! she does not hold are her discards and the talon's leftovers, and both
//! run low, so an unaccounted-for ace is hers far more often than a uniform
//! prior believes and a seven far less (`PLAN.md`, "The solver's world
//! prior").
//!
//! A `RankPrior` weighs a hand by one log-odds per rank, summed over its
//! cards. Every world in a set has the same number of cards, so only the
//! differences between ranks matter, and a card every world shares cancels
//! out: this is a **conditional logit**. `fit` finds the weights under which
//! the hands she really held were most likely.
//!
//! The weights describe the players the samples came from. Fitted to rung-4
//! discards they are a statement about rung 4, and would be a guess against
//! a person.

use crate::cards::Hand;

/// Log-odds per rank, seven first and ace last.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RankPrior(pub [f64; 8]);

impl RankPrior {
    /// Every consistent hand equally likely: what the solver has always done.
    pub const UNIFORM: RankPrior = RankPrior([0.0; 8]);

    /// The log of a hand's relative weight.
    pub fn log_weight(&self, hand: Hand) -> f64 {
        hand.iter().map(|card| self.0[usize::from(card % 8)]).sum()
    }

    /// A hand's relative weight; only ratios between hands mean anything.
    pub fn weight(&self, hand: Hand) -> f64 {
        self.log_weight(hand).exp()
    }
}

/// Fitted by `bin/prior 60` on 8,601 searched decisions from 720 mirrored
/// last deals, rung-4 exchanges on both sides, ridge 1, fitted on half the
/// deals and scored on the other (`measurements/prior-60.txt`): held out, a
/// doubtful seven is hers 12% of the time, as this believes, where a uniform
/// prior believes 46%; a king 96% against 55%. A statement about rung 4.
pub const RUNG4: RankPrior = RankPrior([-2.753, -2.235, -1.72, -0.299, 0.723, 1.257, 2.212, 2.815]);

/// One observation: every hand she could have held, and the one she held.
#[derive(Clone, Debug)]
pub struct Sample {
    pub worlds: Vec<Hand>,
    pub truth: Hand,
}

/// The mean log-probability of the true hands under `prior`.
pub fn log_likelihood(prior: &RankPrior, samples: &[Sample]) -> f64 {
    if samples.is_empty() {
        return 0.0;
    }
    let features: Vec<Features> = samples.iter().map(Features::of).collect();
    likelihood(&prior.0, &features, 0.0) / samples.len() as f64
}

/// A sample as rank counts: one row per world, and the true hand's.
struct Features {
    worlds: Vec<[f64; 8]>,
    truth: [f64; 8],
}

impl Features {
    fn of(sample: &Sample) -> Features {
        Features {
            worlds: sample.worlds.iter().map(|h| counts(*h)).collect(),
            truth: counts(sample.truth),
        }
    }
}

fn counts(hand: Hand) -> [f64; 8] {
    let mut out = [0.0; 8];
    for card in hand.iter() {
        out[usize::from(card % 8)] += 1.0;
    }
    out
}

fn dot(a: &[f64; 8], b: &[f64; 8]) -> f64 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

/// The summed log-likelihood, less the ridge penalty.
fn likelihood(theta: &[f64; 8], features: &[Features], ridge: f64) -> f64 {
    let penalty = 0.5 * ridge * dot(theta, theta);
    features
        .iter()
        .map(|f| {
            let scores: Vec<f64> = f.worlds.iter().map(|x| dot(theta, x)).collect();
            let top = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            let log_total = top + scores.iter().map(|s| (s - top).exp()).sum::<f64>().ln();
            dot(theta, &f.truth) - log_total
        })
        .sum::<f64>()
        - penalty
}

/// Solve `a x = b` by Gaussian elimination with partial pivoting.
fn solve(mut a: [[f64; 8]; 8], mut b: [f64; 8]) -> [f64; 8] {
    for col in 0..8 {
        let pivot = (col..8)
            .max_by(|&i, &j| a[i][col].abs().total_cmp(&a[j][col].abs()))
            .expect("a non-empty range");
        a.swap(col, pivot);
        b.swap(col, pivot);
        let pivot_row = a[col];
        for row in col + 1..8 {
            let factor = a[row][col] / pivot_row[col];
            for (cell, above) in a[row][col..].iter_mut().zip(&pivot_row[col..]) {
                *cell -= factor * above;
            }
            b[row] -= factor * b[col];
        }
    }
    let mut x = [0.0; 8];
    for row in (0..8).rev() {
        let rest: f64 = (row + 1..8).map(|k| a[row][k] * x[k]).sum();
        x[row] = (b[row] - rest) / a[row][row];
    }
    x
}

/// The weights under which the true hands were most likely, by Newton's
/// method on the conditional-logit likelihood, less `ridge / 2` times the
/// squared weights. The ridge keeps the fit finite where a rank separates
/// perfectly -- a player who never throws an ace makes every unaccounted ace
/// hers, and the unpenalised optimum is infinite. Returned centred on zero.
pub fn fit(samples: &[Sample], ridge: f64) -> RankPrior {
    let features: Vec<Features> = samples.iter().map(Features::of).collect();
    let mut theta = [0.0f64; 8];
    let mut current = likelihood(&theta, &features, ridge);

    for _ in 0..100 {
        // Gradient: the true hand's counts less their expectation under the
        // current weights. Hessian: minus the covariance of the counts.
        let mut gradient = [0.0f64; 8];
        let mut hessian = [[0.0f64; 8]; 8];
        for f in &features {
            let scores: Vec<f64> = f.worlds.iter().map(|x| dot(&theta, x)).collect();
            let top = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            let weights: Vec<f64> = scores.iter().map(|s| (s - top).exp()).collect();
            let total: f64 = weights.iter().sum();
            let mut mean = [0.0f64; 8];
            let mut second = [[0.0f64; 8]; 8];
            for (x, w) in f.worlds.iter().zip(&weights) {
                let p = w / total;
                for i in 0..8 {
                    mean[i] += p * x[i];
                    for j in 0..8 {
                        second[i][j] += p * x[i] * x[j];
                    }
                }
            }
            for i in 0..8 {
                gradient[i] += f.truth[i] - mean[i];
                for j in 0..8 {
                    hessian[i][j] -= second[i][j] - mean[i] * mean[j];
                }
            }
        }
        for i in 0..8 {
            gradient[i] -= ridge * theta[i];
            hessian[i][i] -= ridge;
        }

        // Newton's step, halved until it improves the penalised likelihood:
        // a rank close to separating can make the full step overshoot.
        let step = solve(hessian, gradient);
        let mut scale = 1.0;
        let mut improved = false;
        while scale > 1e-6 {
            let trial: [f64; 8] = std::array::from_fn(|i| theta[i] - scale * step[i]);
            let value = likelihood(&trial, &features, ridge);
            if value >= current {
                let moved = step.iter().map(|s| (scale * s).abs()).fold(0.0, f64::max);
                theta = trial;
                current = value;
                improved = moved > 1e-9;
                break;
            }
            scale /= 2.0;
        }
        if !improved {
            break;
        }
    }

    let mean = theta.iter().sum::<f64>() / 8.0;
    RankPrior(theta.map(|v| v - mean))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cards::Card;
    use crate::rng::Rng;

    fn hand(codes: &str) -> Hand {
        Hand::parse(codes).unwrap()
    }

    /// Every `size`-card subset of `pool`.
    fn subsets(pool: &[Card], size: usize) -> Vec<Hand> {
        let mut out = Vec::new();
        let n = pool.len();
        for mask in 0u32..(1 << n) {
            if mask.count_ones() as usize == size {
                let bits = (0..n)
                    .filter(|i| mask & (1 << i) != 0)
                    .fold(0u32, |acc, i| acc | 1 << pool[i].0);
                out.push(Hand(bits));
            }
        }
        out
    }

    /// Samples whose true hand is drawn from the conditional logit `truth`.
    fn synthetic(truth: &RankPrior, count: usize, seed: u32) -> Vec<Sample> {
        let mut rng = Rng::seeded(seed);
        let mut out = Vec::with_capacity(count);
        for _ in 0..count {
            let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
            rng.shuffle(&mut pack);
            let pool = &pack[..10];
            let size = rng.in_range(3, 6);
            let worlds = subsets(pool, size);
            let weights: Vec<f64> = worlds.iter().map(|h| truth.weight(*h)).collect();
            let mut pick = rng.next_f64() * weights.iter().sum::<f64>();
            let mut chosen = worlds[worlds.len() - 1];
            for (world, weight) in worlds.iter().zip(&weights) {
                if pick < *weight {
                    chosen = *world;
                    break;
                }
                pick -= weight;
            }
            out.push(Sample {
                worlds,
                truth: chosen,
            });
        }
        out
    }

    fn centred(prior: &RankPrior) -> [f64; 8] {
        let mean = prior.0.iter().sum::<f64>() / 8.0;
        prior.0.map(|v| v - mean)
    }

    #[test]
    fn the_uniform_prior_weighs_every_hand_alike() {
        for codes in ["AS", "7C 8C 9C", "AS AH AD AC KS KH KD KC"] {
            assert_eq!(RankPrior::UNIFORM.weight(hand(codes)), 1.0);
        }
    }

    #[test]
    fn a_hand_is_weighed_by_the_sum_of_its_ranks() {
        let mut odds = [0.0; 8];
        odds[7] = 1.0; // ace
        odds[0] = -0.5; // seven
        odds[3] = 0.25; // ten
        let prior = RankPrior(odds);
        assert_eq!(prior.log_weight(hand("AS AH 7C")), 1.5);
        assert_eq!(prior.log_weight(hand("TD 9D 8D")), 0.25);
        assert_eq!(prior.log_weight(Hand(0)), 0.0);
    }

    #[test]
    fn the_uniform_prior_gives_every_world_its_share() {
        let pool: Vec<Card> = (0u8..6).map(Card).collect();
        let worlds = subsets(&pool, 3);
        let samples = vec![Sample {
            truth: worlds[4],
            worlds: worlds.clone(),
        }];
        let expected = -(worlds.len() as f64).ln();
        assert!((log_likelihood(&RankPrior::UNIFORM, &samples) - expected).abs() < 1e-12);
    }

    #[test]
    fn the_fit_recovers_the_weights_the_hands_were_drawn_from() {
        let truth = RankPrior([-1.0, -0.6, -0.3, 0.0, 0.2, 0.5, 0.8, 1.2]);
        let samples = synthetic(&truth, 3000, 11);
        let fitted = fit(&samples, 1e-6);
        let (want, got) = (centred(&truth), centred(&fitted));
        for rank in 0..8 {
            assert!(
                (want[rank] - got[rank]).abs() < 0.15,
                "rank {rank}: wanted {:.2}, fitted {:.2}",
                want[rank],
                got[rank]
            );
        }
        assert!(log_likelihood(&fitted, &samples) > log_likelihood(&RankPrior::UNIFORM, &samples));
    }

    #[test]
    fn hands_drawn_uniformly_fit_to_nearly_nothing() {
        let samples = synthetic(&RankPrior::UNIFORM, 2000, 12);
        let fitted = fit(&samples, 1e-6);
        assert!(fitted.0.iter().all(|v| v.abs() < 0.15), "{fitted:?}");
    }

    #[test]
    fn a_rank_that_separates_perfectly_stays_finite() {
        // Whenever an ace could be hers, it is: the unpenalised optimum is
        // infinite, and the ridge must hold it.
        let pool: Vec<Card> = ["AS", "7H", "8H", "9C", "TD"]
            .iter()
            .map(|c| Card::parse(c).unwrap())
            .collect();
        let worlds = subsets(&pool, 2);
        let with_ace: Vec<Hand> = worlds
            .iter()
            .copied()
            .filter(|h| h.contains(pool[0].0))
            .collect();
        let samples: Vec<Sample> = with_ace
            .iter()
            .map(|truth| Sample {
                worlds: worlds.clone(),
                truth: *truth,
            })
            .collect();
        let fitted = fit(&samples, 0.1);
        assert!(fitted.0.iter().all(|v| v.is_finite()));
        let ace = fitted.0[7];
        assert!(fitted.0.iter().all(|v| *v <= ace), "{fitted:?}");
        assert!(fitted.0.iter().sum::<f64>().abs() < 1e-9, "centred");
    }
}
