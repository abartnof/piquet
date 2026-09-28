//! The chances of scoring so much in a deal.
//!
//! Hoyle's word. His 1744 treatise is a table of chances for the exchange, and
//! this is the same question asked about the rubicon: *"I am on eighty-two
//! with one deal left and I am elder -- what are the odds I reach a hundred?"*
//!
//! **What the table is, and what it is not.** It is 20,000 deals of rung-4
//! play, one histogram per seat. It is therefore a statement about *rung-4*
//! play: a stronger agent scores more and a weaker one less. Deal luck swamps
//! skill in piquet, which is why the shape survives the change of rung
//! tolerably, but it is indicative and not exact.
//!
//! This is the first module where floating point enters the engine, so it is
//! also the first whose vectors need a tolerance rather than equality.
//! `convolve` accumulates in a fixed index order and is ported literally
//! rather than tidied, because floating addition is not associative and IEEE
//! 754 then makes the result bit-identical (`docs/DESIGN.md` §2.2).

use std::sync::OnceLock;

use crate::mt19937::MersenneTwister;
use crate::partie::{Partie, Side, Standing, DEALS_IN_PARTIE, EXTRA_DEALS, PARTIE_BONUS, RUBICON};
use crate::scoring::Player;

/// The top bucket; everything above it is folded in.
pub const CAP: usize = 120;

/// How far a finite difference steps. One point is too fine: the settlement
/// has a kink at exactly a hundred, and a single-point step lands on or off it
/// by luck. Three smooths that without ceasing to be local.
const STEP: i32 = 3;
const DRAWS: usize = 3000;
const SEED: u32 = 1674;

pub(crate) const ELDER_COUNTS: [u32; 121] = [
    0, 33, 74, 166, 247, 433, 679, 701, 610, 353, 517, 608, 509, 410, 384, 328, 240, 238, 281, 603,
    405, 353, 658, 554, 584, 624, 680, 620, 663, 510, 481, 388, 363, 348, 306, 255, 276, 275, 287,
    334, 251, 228, 205, 170, 97, 79, 59, 21, 17, 27, 22, 19, 19, 44, 11, 5, 48, 9, 1, 78, 43, 38,
    52, 51, 35, 20, 30, 21, 1, 3, 64, 77, 114, 169, 170, 185, 169, 153, 113, 66, 38, 26, 0, 1, 5,
    2, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 4, 5, 6, 7, 7, 14, 18, 14, 13, 12, 6, 6, 10, 18, 26, 33, 31,
    33, 40, 35, 45, 34, 25, 28, 94,
];
pub(crate) const YOUNGER_COUNTS: [u32; 121] = [
    113, 0, 274, 306, 821, 1041, 1020, 1006, 689, 782, 1116, 802, 680, 627, 460, 397, 302, 264,
    548, 455, 261, 394, 467, 519, 621, 596, 555, 545, 441, 358, 357, 299, 256, 238, 199, 165, 180,
    128, 137, 130, 152, 126, 128, 113, 106, 114, 89, 87, 49, 25, 16, 16, 4, 1, 2, 2, 5, 1, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 2, 0, 0, 5, 0, 6, 10, 2, 5, 2, 3, 4, 3, 0, 4, 1, 0, 0, 1, 1, 0, 0, 1, 0, 1,
    0, 3, 6, 6, 16, 18, 16, 22, 13, 15, 10, 20, 10, 6, 5, 3, 12, 13, 14, 13, 14, 13, 18, 15, 12, 9,
    16, 11, 35,
];
pub(crate) const PAIRS: [u16; 1000] = [
    64, 18, 56, 9, 119, 2, 37, 4, 29, 18, 27, 7, 28, 24, 27, 21, 10, 16, 13, 23, 13, 37, 22, 5, 14,
    42, 5, 30, 11, 16, 25, 16, 41, 8, 18, 17, 24, 12, 28, 7, 42, 5, 16, 7, 62, 7, 16, 13, 30, 5,
    16, 18, 30, 8, 14, 28, 8, 19, 42, 8, 26, 20, 22, 13, 7, 25, 7, 38, 26, 29, 32, 6, 26, 7, 11,
    26, 22, 25, 38, 9, 18, 31, 20, 29, 22, 26, 4, 113, 26, 23, 30, 24, 17, 7, 29, 8, 10, 39, 5, 29,
    20, 8, 32, 8, 36, 11, 28, 10, 10, 11, 18, 102, 31, 10, 60, 7, 14, 23, 21, 30, 26, 6, 4, 45, 40,
    19, 12, 23, 16, 18, 9, 41, 27, 10, 10, 29, 27, 21, 7, 104, 18, 19, 13, 23, 33, 6, 5, 31, 14,
    26, 74, 6, 20, 8, 76, 4, 37, 11, 11, 38, 8, 29, 31, 10, 24, 15, 32, 9, 31, 19, 28, 13, 116, 5,
    19, 15, 23, 14, 5, 34, 10, 29, 6, 44, 28, 9, 25, 26, 6, 24, 23, 29, 71, 6, 11, 18, 101, 0, 29,
    6, 40, 12, 71, 4, 28, 10, 27, 27, 36, 5, 16, 18, 117, 4, 30, 9, 28, 12, 9, 27, 22, 18, 5, 110,
    30, 5, 29, 5, 45, 9, 7, 29, 10, 25, 23, 4, 78, 5, 30, 10, 15, 7, 32, 9, 38, 4, 10, 29, 74, 3,
    17, 10, 23, 6, 40, 12, 32, 11, 27, 24, 42, 7, 12, 31, 40, 12, 12, 19, 22, 7, 22, 99, 9, 24, 15,
    11, 29, 21, 35, 6, 32, 7, 27, 4, 30, 10, 30, 5, 11, 24, 11, 28, 3, 35, 36, 10, 8, 17, 11, 38,
    21, 12, 13, 26, 27, 21, 34, 5, 28, 14, 30, 18, 10, 25, 7, 31, 3, 31, 40, 8, 34, 5, 32, 6, 29,
    10, 5, 37, 59, 5, 21, 29, 23, 12, 8, 41, 41, 6, 28, 25, 67, 24, 29, 11, 19, 34, 11, 27, 5, 40,
    16, 18, 43, 7, 34, 5, 5, 44, 23, 8, 31, 11, 11, 37, 26, 12, 112, 3, 34, 9, 70, 3, 33, 17, 18,
    28, 39, 11, 6, 25, 63, 14, 32, 11, 28, 6, 46, 9, 24, 22, 72, 3, 24, 10, 10, 48, 113, 2, 20, 26,
    7, 26, 27, 9, 46, 8, 26, 29, 12, 29, 75, 5, 6, 45, 10, 24, 8, 12, 24, 18, 20, 22, 28, 12, 30,
    11, 31, 5, 7, 33, 19, 21, 10, 27, 9, 43, 26, 28, 18, 17, 73, 5, 14, 19, 30, 13, 53, 94, 24, 15,
    59, 21, 2, 46, 11, 7, 43, 9, 10, 29, 5, 44, 29, 9, 22, 14, 22, 14, 79, 4, 76, 3, 19, 34, 40,
    11, 11, 29, 24, 9, 21, 19, 71, 3, 9, 34, 17, 12, 22, 12, 27, 11, 33, 11, 4, 37, 5, 29, 32, 5,
    23, 23, 65, 7, 12, 27, 11, 27, 8, 22, 43, 5, 26, 14, 15, 7, 6, 21, 77, 4, 32, 5, 9, 44, 4, 38,
    19, 9, 41, 9, 63, 7, 11, 29, 38, 13, 63, 7, 20, 28, 22, 14, 27, 32, 30, 7, 16, 23, 23, 7, 6,
    33, 37, 24, 19, 22, 27, 4, 25, 26, 116, 2, 25, 10, 4, 30, 7, 39, 5, 47, 7, 27, 21, 11, 42, 9,
    36, 12, 40, 8, 29, 11, 23, 17, 12, 28, 38, 27, 20, 30, 14, 26, 27, 6, 7, 40, 20, 94, 25, 12, 8,
    20, 35, 25, 24, 38, 6, 44, 4, 34, 5, 30, 12, 28, 30, 12, 32, 4, 40, 10, 12, 7, 40, 7, 63, 5,
    14, 10, 77, 3, 22, 20, 34, 9, 21, 17, 32, 19, 25, 10, 35, 9, 19, 23, 12, 27, 27, 16, 31, 18,
    74, 6, 20, 26, 12, 21, 23, 22, 34, 14, 6, 31, 9, 30, 13, 36, 7, 14, 5, 44, 12, 25, 60, 7, 6,
    24, 51, 7, 40, 9, 38, 5, 23, 15, 39, 11, 14, 25, 32, 10, 7, 32, 30, 10, 25, 14, 30, 5, 41, 5,
    10, 28, 7, 103, 28, 24, 10, 37, 11, 29, 33, 5, 18, 18, 29, 8, 30, 5, 8, 40, 19, 31, 26, 30, 26,
    26, 25, 11, 36, 9, 22, 25, 20, 25, 15, 38, 29, 8, 43, 9, 112, 5, 28, 12, 78, 5, 14, 25, 17, 22,
    29, 10, 31, 8, 14, 26, 113, 2, 14, 11, 33, 14, 11, 24, 26, 21, 28, 19, 26, 14, 35, 13, 26, 7,
    8, 32, 77, 5, 13, 11, 20, 13, 7, 43, 44, 9, 17, 11, 78, 5, 25, 26, 7, 31, 36, 3, 40, 7, 77, 2,
    75, 3, 52, 11, 29, 8, 24, 21, 75, 5, 10, 26, 43, 11, 28, 21, 43, 8, 23, 14, 28, 5, 22, 8, 75,
    4, 7, 30, 113, 6, 32, 5, 117, 5, 24, 18, 15, 37, 26, 26, 115, 6, 11, 27, 12, 13, 34, 5, 81, 2,
    19, 99, 18, 8, 10, 27, 5, 36, 22, 12, 40, 11, 17, 7, 27, 8, 16, 10, 26, 9, 33, 5, 3, 49, 17, 7,
    4, 47, 28, 10, 11, 24, 17, 13, 5, 30, 44, 8, 30, 9, 41, 11, 18, 21, 29, 6, 19, 18, 72, 4, 5,
    30, 5, 110, 14, 21, 22, 8, 10, 44, 32, 6, 26, 15, 16, 13, 4, 115, 73, 5, 98, 7, 44, 6, 8, 37,
    29, 18, 117, 4, 24, 18, 10, 16, 15, 18, 8, 19, 34, 13, 8, 45, 26, 5, 24, 22, 38, 8, 12, 14, 5,
    33, 19, 24, 112, 2, 41, 24, 36, 8, 14, 21, 19, 10, 7, 29, 13, 27, 14, 11, 17, 11, 26, 25, 19,
    8, 73, 4, 7, 30, 62, 7, 19, 28, 77, 3, 39, 15, 13, 28, 41, 5, 19, 30, 33, 8, 40, 4, 22, 30,
];
// PAIRS holds 500 (elder, younger) score pairs

fn normalise(counts: &[u32]) -> Vec<f64> {
    let total: u32 = counts.iter().sum();
    let total = if total == 0 { 1 } else { total };
    counts
        .iter()
        .map(|c| f64::from(*c) / f64::from(total))
        .collect()
}

/// Deal-score densities, indexed by `Player::index`: rung-4 play, measured.
pub fn measured() -> &'static Densities {
    static MEASURED: OnceLock<Densities> = OnceLock::new();
    MEASURED.get_or_init(|| [normalise(&ELDER_COUNTS), normalise(&YOUNGER_COUNTS)])
}

/// Deal-score densities for each seat, indexed by `Player::index`: what a
/// deal is worth, as some population of players plays it.
///
/// [`measured`] is rung-4 play. The Python invites the caller to "measure
/// your own and pass it as `table`" -- which is what a stronger ladder would
/// want -- so each question below comes in an `_in` form that takes one.
pub type Densities = [Vec<f64>; 2];

/// P(this seat scores exactly *i*) in one deal, for i in 0..=CAP.
pub fn density(seat: Player) -> &'static [f64] {
    density_in(seat, measured())
}

/// [`density`], by a table of one's own.
pub fn density_in(seat: Player, table: &Densities) -> &[f64] {
    &table[seat.index()]
}

/// P(this seat scores *at least* i) in one deal.
pub fn survival(seat: Player) -> Vec<f64> {
    survival_in(seat, measured())
}

/// [`survival`], by a table of one's own.
pub fn survival_in(seat: Player, table: &Densities) -> Vec<f64> {
    let rows = density_in(seat, table);
    let mut out = vec![0.0; rows.len()];
    let mut running = 0.0;
    for i in (0..rows.len()).rev() {
        running += rows[i];
        out[i] = running;
    }
    out
}

/// Ported literally rather than tidied: floating addition is not associative,
/// so preserving the index order is what makes the result bit-identical.
fn convolve(a: &[f64], b: &[f64]) -> Vec<f64> {
    let mut out = vec![0.0; a.len() + b.len() - 1];
    for (i, x) in a.iter().enumerate() {
        if *x == 0.0 {
            continue;
        }
        for (j, y) in b.iter().enumerate() {
            if *y != 0.0 {
                out[i + j] += x * y;
            }
        }
    }
    out
}

/// The density of a side's total over the deals that remain.
///
/// The deal alternates, so a side plays elder, younger, elder... from
/// whichever seat it is in next. That alternation is most of the reason the
/// two seats need separate histograms at all: elder averages about 29 a deal
/// and younger about 20.
fn over_several(deals_left: usize, elder_first: bool, table: &Densities) -> Vec<f64> {
    let mut total = vec![1.0];
    let mut elder = elder_first;
    for _ in 0..deals_left {
        let seat = if elder {
            Player::Elder
        } else {
            Player::Younger
        };
        total = convolve(&total, density_in(seat, table));
        elder = !elder;
    }
    total
}

/// The chance of scoring at least `needed` over the deals that remain.
pub fn chance_of(needed: i32, deals_left: usize, elder_first: bool) -> f64 {
    chance_of_in(needed, deals_left, elder_first, measured())
}

/// [`chance_of`], by a table of one's own.
pub fn chance_of_in(needed: i32, deals_left: usize, elder_first: bool, table: &Densities) -> f64 {
    if needed <= 0 {
        return 1.0;
    }
    if deals_left == 0 {
        return 0.0;
    }
    let spread = over_several(deals_left, elder_first, table);
    spread.iter().skip(needed as usize).sum()
}

/// The chance this side gets over a hundred, from where the partie stands.
///
/// The number the last deal of a partie is really about. Failing to cross
/// costs you the *sum* of both scores rather than the difference, so a player
/// who is short is playing a different game from one who is not.
pub fn chance_of_the_rubicon(partie: &Partie, side: Side) -> f64 {
    chance_of_the_rubicon_in(partie, side, measured())
}

/// [`chance_of_the_rubicon`], by a table of one's own.
pub fn chance_of_the_rubicon_in(partie: &Partie, side: Side, table: &Densities) -> f64 {
    chance_of_in(
        RUBICON - partie.score_of(side),
        partie.deals_left(),
        partie.elder() == side,
        table,
    )
}

/// Fractions a person can hold in their head.
///
/// A player deciding whether to gamble thinks in odds, not percentages, and so
/// does the game's own literature -- Hoyle says "three to two against", never
/// "forty per cent".
const FRACTIONS: [(u32, u32); 12] = [
    (1, 10),
    (1, 6),
    (1, 5),
    (1, 4),
    (1, 3),
    (2, 5),
    (1, 2),
    (3, 5),
    (2, 3),
    (3, 4),
    (4, 5),
    (9, 10),
];

/// A phrase a player can act on rather than a number they must interpret.
pub fn in_words(p: f64) -> String {
    if p >= 0.97 {
        return "all but certain".to_string();
    }
    if p <= 0.03 {
        return "barely possible".to_string();
    }
    // `min_by` returns the first of equal elements, as Python's `min` does.
    let (numerator, denominator) = FRACTIONS
        .iter()
        .min_by(|a, b| {
            let da = (f64::from(a.0) / f64::from(a.1) - p).abs();
            let db = (f64::from(b.0) / f64::from(b.1) - p).abs();
            da.partial_cmp(&db).expect("no NaN in a probability")
        })
        .expect("the table is not empty");
    format!("about {numerator} in {denominator}")
}

/// Sampled (my points, their points) over the deals that remain.
///
/// The seats alternate, as they do in a partie, so a side that is elder next
/// is younger the deal after -- which is most of why the two sides of a
/// sampled pair cannot simply be averaged.
///
/// The seed is fixed so that a position always values the same, which is what
/// makes this reproducible across languages at all. See `mt19937`.
/// The longest a partie can run: six deals, plus the two played on a tie.
const MOST_DEALS: usize = DEALS_IN_PARTIE + EXTRA_DEALS;

fn futures(deals_left: usize, elder_first: bool) -> &'static [(i32, i32)] {
    /// One sampled future per draw, cached per (deals_left, elder_first).
    type FutureCache = Vec<OnceLock<Vec<(i32, i32)>>>;
    static CACHE: OnceLock<FutureCache> = OnceLock::new();

    // Asserted rather than clamped. An earlier version took
    // `deals_left.min(9)` as the cache slot while computing with the
    // *unclamped* value, so two different horizons shared one entry and the
    // second silently received the first one's distribution. Unreachable --
    // a partie is at most eight deals -- but a wrong answer is a worse
    // failure than a loud one, and the clamp turned the former into the
    // latter.
    assert!(
        deals_left <= MOST_DEALS,
        "a partie runs at most {MOST_DEALS} deals; asked for {deals_left}"
    );

    let cache = CACHE.get_or_init(|| ((0..=MOST_DEALS * 2 + 1).map(|_| OnceLock::new())).collect());
    let slot = deals_left * 2 + usize::from(elder_first);
    cache[slot].get_or_init(|| {
        let pairs: Vec<(i32, i32)> = PAIRS
            .as_chunks::<2>()
            .0
            .iter()
            .map(|p| (i32::from(p[0]), i32::from(p[1])))
            .collect();
        let mut rng = MersenneTwister::seeded(SEED);
        let mut out = Vec::with_capacity(DRAWS);
        for _ in 0..DRAWS {
            let (mut mine, mut theirs) = (0i32, 0i32);
            let mut elder = elder_first;
            for _ in 0..deals_left {
                let scored = *rng.choice(&pairs);
                mine += if elder { scored.0 } else { scored.1 };
                theirs += if elder { scored.1 } else { scored.0 };
                elder = !elder;
            }
            out.push((mine, theirs));
        }
        out
    })
}

/// What a finished partie pays me, signed.
///
/// The difference plus a hundred if the loser reached a hundred, and the sum
/// plus a hundred if they did not -- and the guard is on the *loser*, so two
/// players who crawl to 60 and 40 settle for 200.
pub fn settlement_of(mine: i32, theirs: i32) -> i32 {
    if mine == theirs {
        return 0;
    }
    let high = mine.max(theirs);
    let low = mine.min(theirs);
    let points = if low < RUBICON {
        high + low
    } else {
        high - low
    } + PARTIE_BONUS;
    if mine > theirs {
        points
    } else {
        -points
    }
}

/// The mean settlement from here, over the deals that remain.
pub fn expected_settlement(mine: i32, theirs: i32, deals_left: usize, elder_first: bool) -> f64 {
    if deals_left == 0 {
        return f64::from(settlement_of(mine, theirs));
    }
    let samples = futures(deals_left, elder_first);
    let total: i64 = samples
        .iter()
        .map(|(gained, conceded)| i64::from(settlement_of(mine + gained, theirs + conceded)))
        .sum();
    total as f64 / samples.len() as f64
}

/// What one more point to each side is worth, measured in settlement.
///
/// The bridge from *points in a deal* to *points in a partie*, and the whole
/// reason an agent has to see the standing at all. Four regimes, and only the
/// last is the one every agent in this project has been playing:
///
/// - **both safely over the line** -- about +1 and -1, and maximising the deal
///   margin is correct;
/// - **near level** -- worth two or three times that, because the settlement
///   is the difference *plus a hundred* and that hundred changes hands at the
///   tie;
/// - **I am short and the partie is ending** -- a point to me is worth a
///   multiple of one, because crossing turns what I pay from the *sum* into
///   the *difference*;
/// - **they are short** -- and this one is strange. While a hundred is out of
///   their reach their points are worth **+1 to me**, because a rubiconed
///   loser pays the sum and their score is part of it. Close enough to
///   threaten it and the sign flips hard: at 88 a point to them costs me nine,
///   because carrying them over costs twice their whole score.
///
/// Nothing in that last row has any counterpart inside a single deal, which is
/// why no amount of tuning a deal-level heuristic could have found it.
pub fn point_weights(mine: i32, theirs: i32, deals_left: usize, elder_first: bool) -> (f64, f64) {
    if deals_left == 0 {
        return (0.0, 0.0);
    }
    let here = expected_settlement(mine, theirs, deals_left, elder_first);
    let gained = expected_settlement(mine + STEP, theirs, deals_left, elder_first);
    let conceded = expected_settlement(mine, theirs + STEP, deals_left, elder_first);
    let step = f64::from(STEP);
    ((gained - here) / step, (conceded - here) / step)
}

/// `point_weights` read straight off a player's `Standing`.
pub fn weights_for(standing: Standing, elder: bool) -> (f64, f64) {
    point_weights(standing.mine, standing.theirs, standing.deals_left, elder)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Every horizon a partie can present must get its own distribution.
    ///
    /// The bug this guards against was invisible: the values were plausible,
    /// merely computed for the wrong number of deals.
    #[test]
    fn each_horizon_is_cached_separately() {
        let mut seen: Vec<(usize, bool, i64)> = Vec::new();
        for deals_left in 1..=MOST_DEALS {
            for elder_first in [true, false] {
                let sampled = futures(deals_left, elder_first);
                assert_eq!(sampled.len(), DRAWS);
                let total: i64 = sampled.iter().map(|(mine, _)| i64::from(*mine)).sum();
                seen.push((deals_left, elder_first, total));
            }
        }
        // More deals left means more points expected, so the totals must be
        // strictly increasing with the horizon -- which they cannot be if two
        // horizons share an entry.
        for pair in seen.chunks(2) {
            let elder_first = pair[0].2;
            assert!(elder_first > 0);
        }
        for window in seen.chunks(2).collect::<Vec<_>>().windows(2) {
            assert!(
                window[1][0].2 > window[0][0].2,
                "a longer horizon scored no more: {:?} then {:?}",
                window[0][0],
                window[1][0]
            );
        }
    }

    #[test]
    #[should_panic(expected = "a partie runs at most")]
    fn an_impossible_horizon_is_refused_rather_than_aliased() {
        futures(MOST_DEALS + 1, true);
    }
}
