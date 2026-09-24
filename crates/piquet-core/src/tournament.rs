//! Measuring how well an agent plays.
//!
//! **Always mirrored pairs.** Deal luck swamps skill in piquet: an ad-hoc
//! harness without mirroring once disagreed with itself by five sigma. Both
//! agents get the same cards from both seats, so the only thing left to
//! measure is how they played them.

use crate::agents::Agent;
use crate::cards::Card;
use crate::partie::{Partie, Side, DEALS_IN_PARTIE, EXTRA_DEALS};
use crate::rng::Rng;
use crate::rules::deal_from;
use crate::scoring::Player;

/// One pairing, over a set of mirrored deals.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct DuelResult {
    pub name_a: String,
    pub name_b: String,
    pub pairs: usize,
    pub a_wins: usize,
    pub b_wins: usize,
    pub drawn: usize,
    pub a_points: i32,
    pub b_points: i32,
}

impl DuelResult {
    pub fn a_win_rate(&self) -> f64 {
        if self.pairs == 0 {
            return 0.0;
        }
        (self.a_wins as f64 + 0.5 * self.drawn as f64) / self.pairs as f64
    }

    /// Mean points by which A beats B per pair. The finer-grained measure.
    pub fn margin(&self) -> f64 {
        if self.pairs == 0 {
            return 0.0;
        }
        f64::from(self.a_points - self.b_points) / self.pairs as f64
    }
}

/// Play each deal twice with the seats swapped.
///
/// The deals come from their **own** generator. Drawing them from the one the
/// agents use means a stochastic agent shifts every later deal simply by
/// consuming random numbers, so two pairings in the same round robin would
/// face different cards for no reason. Passing the same `deal_seed` to every
/// pairing makes the whole table a paired comparison and not just each duel
/// within it.
pub fn duel(
    agent_a: &mut dyn Agent,
    agent_b: &mut dyn Agent,
    pairs: usize,
    deal_seed: u32,
) -> Result<DuelResult, String> {
    let mut deals = Rng::seeded(deal_seed);
    let (mut a_wins, mut b_wins, mut drawn) = (0usize, 0usize, 0usize);
    let (mut a_points, mut b_points) = (0i32, 0i32);

    for _ in 0..pairs {
        let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
        deals.shuffle(&mut pack);
        let board = deal_from(&pack)?;

        let (first, _) = crate::play::play_deal(board.clone(), agent_a, agent_b, None)?;
        let (second, _) = crate::play::play_deal(board, agent_b, agent_a, None)?;

        let a_total = first.log.total(Player::Elder) + second.log.total(Player::Younger);
        let b_total = first.log.total(Player::Younger) + second.log.total(Player::Elder);

        a_points += a_total;
        b_points += b_total;
        match a_total.cmp(&b_total) {
            std::cmp::Ordering::Greater => a_wins += 1,
            std::cmp::Ordering::Less => b_wins += 1,
            std::cmp::Ordering::Equal => drawn += 1,
        }
    }

    Ok(DuelResult {
        name_a: agent_a.name().to_string(),
        name_b: agent_b.name().to_string(),
        pairs,
        a_wins,
        b_wins,
        drawn,
        a_points,
        b_points,
    })
}

/// Bradley-Terry strengths, reported on the Elo scale.
///
/// Fitted by minorisation-maximisation, which converges to the maximum
/// likelihood estimate regardless of the order games were played in.
/// Sequential Elo updates do not have that property, and with a handful of
/// agents the order would visibly change the answer. The model is Zermelo's,
/// 1929, rediscovered by Bradley and Terry in 1952.
///
/// `prior` is **Laplace's rule of succession**, 1774: every agent is credited
/// with half a win and half a loss against a virtual opponent of average
/// strength. A maximum-likelihood fit answers "certain" to a shut-out and
/// sends the loser's rating to minus infinity. An earlier version floored the
/// strength instead, which stops the crash and leaves the number meaningless:
/// a shut-out anchor made the table read about 3,700 for everyone, set
/// entirely by the floor constant.
pub fn ratings(
    results: &[DuelResult],
    anchor: Option<&str>,
    iterations: usize,
    prior: f64,
) -> Vec<(String, f64)> {
    let mut names: Vec<String> = Vec::new();
    for result in results {
        for name in [&result.name_a, &result.name_b] {
            if !names.contains(name) {
                names.push(name.clone());
            }
        }
    }
    if names.is_empty() {
        return Vec::new();
    }

    let index = |name: &str| names.iter().position(|n| n == name).expect("a known name");
    let mut wins = vec![0.0f64; names.len()];
    let mut games: Vec<(usize, usize, f64)> = Vec::new();
    for result in results {
        let a = index(&result.name_a);
        let b = index(&result.name_b);
        wins[a] += result.a_wins as f64 + 0.5 * result.drawn as f64;
        wins[b] += result.b_wins as f64 + 0.5 * result.drawn as f64;
        match games.iter_mut().find(|(x, y, _)| *x == a && *y == b) {
            Some(entry) => entry.2 += result.pairs as f64,
            None => games.push((a, b, result.pairs as f64)),
        }
    }

    // Strengths are renormalised to a mean of one each sweep, so the virtual
    // opponent of "average strength" sits at exactly 1.0.
    let mut strength = vec![1.0f64; names.len()];
    for _ in 0..iterations {
        let mut updated = vec![0.0f64; names.len()];
        for i in 0..names.len() {
            let mut denominator = 2.0 * prior / (strength[i] + 1.0);
            for (a, b, played) in &games {
                if *a == i || *b == i {
                    denominator += played / (strength[*a] + strength[*b]);
                }
            }
            updated[i] = ((wins[i] + prior) / denominator).max(1e-12);
        }
        let total: f64 = updated.iter().sum();
        let total = if total == 0.0 { 1.0 } else { total };
        let scale = names.len() as f64 / total;
        strength = updated.iter().map(|v| v * scale).collect();
    }

    let base = anchor
        .map(|name| strength[index(name)])
        .filter(|s| *s != 0.0)
        .unwrap_or_else(|| {
            (strength.iter().map(|v| v.ln()).sum::<f64>() / names.len() as f64).exp()
        });

    names
        .into_iter()
        .zip(strength)
        .map(|(name, value)| (name, 400.0 * (value / base).log10()))
        .collect()
}

// -- one level up: mirrored parties ------------------------------------------

/// A pairing measured over whole parties, scored in settlement.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct PartieResult {
    pub name_a: String,
    pub name_b: String,
    pub pairs: usize,
    pub a_wins: usize,
    pub b_wins: usize,
    pub drawn: usize,
    /// Net settlement to A, summed over both halves of every mirrored pair.
    pub a_settlement: i32,
}

impl PartieResult {
    pub fn a_win_rate(&self) -> f64 {
        if self.pairs == 0 {
            return 0.0;
        }
        (self.a_wins as f64 + 0.5 * self.drawn as f64) / self.pairs as f64
    }

    /// Mean settlement to A per mirrored pair.
    pub fn margin(&self) -> f64 {
        if self.pairs == 0 {
            return 0.0;
        }
        f64::from(self.a_settlement) / self.pairs as f64
    }
}

/// What a finished partie pays this side, signed.
fn paid_to(partie: &Partie, side: Side) -> i32 {
    let Some(settlement) = partie.settlement() else {
        return 0;
    };
    match settlement.winner {
        None => 0,
        Some(winner) if winner == side => settlement.points,
        Some(_) => -settlement.points,
    }
}

/// Play `pairs` parties, each one twice with the two sides swapped.
///
/// The same mirroring as [`duel`], one level up — and it has to be one level
/// up. **A partie objective cannot be measured in deals.** An agent that gives
/// away a point to keep its opponent under a hundred *loses* by the deal-level
/// yardstick and wins by the only one that pays.
///
/// Scored in **settlement** rather than deal points, because that is what a
/// partie actually pays: the difference plus a hundred, or the sum plus a
/// hundred if the loser was rubiconed.
pub fn partie_duel(
    agent_a: &mut dyn Agent,
    agent_b: &mut dyn Agent,
    pairs: usize,
    deal_seed: u32,
) -> Result<PartieResult, String> {
    let mut deals = Rng::seeded(deal_seed);
    let (mut a_wins, mut b_wins, mut drawn) = (0usize, 0usize, 0usize);
    let mut a_settlement = 0i32;

    for _ in 0..pairs {
        // The two halves must see identical cards, so the packs for the whole
        // partie are drawn once and replayed. A partie runs to eight deals
        // when the sixth leaves the scores level.
        let packs: Vec<Vec<Card>> = (0..DEALS_IN_PARTIE + EXTRA_DEALS)
            .map(|_| {
                let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
                deals.shuffle(&mut pack);
                pack
            })
            .collect();

        let first = crate::play::play_partie(&packs, agent_a, agent_b, Side::A)?;
        let second = crate::play::play_partie(&packs, agent_b, agent_a, Side::A)?;

        // A is side A in the first and side B in the second.
        let paid = paid_to(&first, Side::A) + paid_to(&second, Side::B);
        a_settlement += paid;
        match paid.cmp(&0) {
            std::cmp::Ordering::Greater => a_wins += 1,
            std::cmp::Ordering::Less => b_wins += 1,
            std::cmp::Ordering::Equal => drawn += 1,
        }
    }

    Ok(PartieResult {
        name_a: agent_a.name().to_string(),
        name_b: agent_b.name().to_string(),
        pairs,
        a_wins,
        b_wins,
        drawn,
        a_settlement,
    })
}
