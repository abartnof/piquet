//! The three declaration categories: point, sequence and set.
//!
//! Each category is contested separately and in a fixed order. The player with
//! the better holding scores it *and* every lesser holding of his own in that
//! category; the loser scores nothing at all. An exact tie scores for neither
//! -- though, per Cavendish, equality still does not block a pique.
//!
//! Scoring authority: Cavendish, *The Laws of Piquet adopted by the Portland
//! and Turf Clubs* (1892), laws 60-64.
//!
//! This module is pure: it knows about hands, not about players, dialogue or
//! sinking. Deciding *what to declare* from what you hold belongs to the
//! agents.

use crate::cards::{Hand, Rank, Suit};

pub const MINIMUM_SEQUENCE: u32 = 3;
pub const MINIMUM_SET: u32 = 3;
pub const SEQUENCE_BONUS_FROM: u32 = 5;
pub const SEQUENCE_BONUS: u32 = 10;
pub const TRIO_SCORE: u32 = 3;
pub const QUATORZE_SCORE: u32 = 14;

/// How one player's holding stands against the other's.
///
/// Named from the point of view of the holding on the left. The dialogue at
/// the table inverts it: younger answers "good" to elder's declaration when
/// elder's holding is BETTER.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Comparison {
    Better,
    Worse,
    Equal,
}

impl Comparison {
    pub fn value(self) -> &'static str {
        match self {
            Comparison::Better => "better",
            Comparison::Worse => "worse",
            Comparison::Equal => "equal",
        }
    }
}

/// The longest suit, scoring its length.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Point {
    pub suit: Suit,
    pub length: u32,
    pub pip_value: u32,
}

impl Point {
    pub fn score(self) -> u32 {
        self.length
    }

    /// Length first, then pip value -- the order ties are broken in.
    pub fn key(self) -> (u32, u32) {
        (self.length, self.pip_value)
    }

    /// True if the hand can actually show this point.
    ///
    /// An understated point -- "five spades" while holding six -- is supported
    /// when the top cards of that suit add up to the value claimed.
    pub fn is_supported_by(self, hand: Hand) -> bool {
        let ranks = hand.ranks_in(self.suit);
        if self.length < 1 || (ranks.len() as u32) < self.length {
            return false;
        }
        let total: u32 = ranks
            .iter()
            .take(self.length as usize)
            .map(|r| r.pip_value())
            .sum();
        total == self.pip_value
    }
}

/// A run of three or more cards in one suit, named by its highest card.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Sequence {
    pub suit: Suit,
    pub top: Rank,
    pub length: u32,
}

impl Sequence {
    /// Three and four score their length; from five a bonus of ten applies.
    ///
    /// So the historical table -- 3, 4, 15, 16, 17, 18 -- is a formula, not an
    /// arbitrary list, which is also the clearest way to teach it.
    pub fn score(self) -> u32 {
        if self.length < SEQUENCE_BONUS_FROM {
            self.length
        } else {
            SEQUENCE_BONUS + self.length
        }
    }

    pub fn key(self) -> (u32, u32) {
        (self.length, u32::from(self.top.0))
    }

    pub fn name(self) -> &'static str {
        match self.length {
            3 => "tierce",
            4 => "quart",
            5 => "quint",
            6 => "sixième",
            7 => "septième",
            _ => "huitième",
        }
    }

    /// True if the hand holds this exact run.
    ///
    /// An understated sequence -- a tierce to the knave out of a quart to the
    /// knave -- is supported, because the shorter run really is in the hand.
    pub fn is_supported_by(self, hand: Hand) -> bool {
        if !(MINIMUM_SEQUENCE..=8).contains(&self.length) {
            return false;
        }
        let lowest = i32::from(self.top.0) - self.length as i32 + 1;
        if lowest < i32::from(Rank::SEVEN.0) {
            return false;
        }
        let held = hand.ranks_in(self.suit);
        (lowest..=i32::from(self.top.0)).all(|r| held.contains(&Rank(r as u8)))
    }
}

/// Three or four cards of one rank, ten or higher.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct CardSet {
    pub rank: Rank,
    pub count: u32,
}

impl CardSet {
    pub fn score(self) -> u32 {
        if self.count == 4 {
            QUATORZE_SCORE
        } else {
            TRIO_SCORE
        }
    }

    /// Size first -- any quatorze beats any trio -- then rank.
    pub fn key(self) -> (u32, u32) {
        (self.count, u32::from(self.rank.0))
    }

    pub fn name(self) -> &'static str {
        if self.count == 4 {
            "quatorze"
        } else {
            "trio"
        }
    }

    /// A quatorze may be understated as a trio, one of Cavendish's examples
    /// of sinking.
    pub fn is_supported_by(self, hand: Hand) -> bool {
        if !self.rank.counts_for_set() {
            return false;
        }
        if !(MINIMUM_SET..=4).contains(&self.count) {
            return false;
        }
        hand.count_of(self.rank) >= self.count
    }
}

// -- detection --------------------------------------------------------------

/// The hand's longest suit, resolving its own ties by pip value.
pub fn best_point(hand: Hand) -> Option<Point> {
    let mut best: Option<Point> = None;
    for suit in Suit::ALL {
        let ranks = hand.ranks_in(suit);
        if ranks.is_empty() {
            continue;
        }
        let candidate = Point {
            suit,
            length: ranks.len() as u32,
            pip_value: ranks.iter().map(|r| r.pip_value()).sum(),
        };
        if best.is_none_or(|b| candidate.key() > b.key()) {
            best = Some(candidate);
        }
    }
    best
}

/// Every sequence the hand holds, best first.
///
/// Runs are *maximal*: a quart is one sequence, not two overlapping tierces. A
/// gap splits a suit into separate sequences, so seven cards missing the ten
/// yield a quart above and a tierce below.
pub fn sequences(hand: Hand) -> Vec<Sequence> {
    let mut found: Vec<Sequence> = Vec::new();
    for suit in Suit::ALL {
        let mut ascending = hand.ranks_in(suit);
        ascending.reverse(); // `ranks_in` gives highest first
        let mut run: Vec<Rank> = Vec::new();
        let mut i = 0usize;
        loop {
            let slot: Option<Rank> = ascending.get(i).copied();
            let extends = match (slot, run.last()) {
                (Some(rank), Some(last)) => rank.0 == last.0 + 1,
                _ => false,
            };
            if extends {
                run.push(slot.expect("extends implies a rank"));
            } else {
                if run.len() as u32 >= MINIMUM_SEQUENCE {
                    found.push(Sequence {
                        suit,
                        top: *run.last().expect("a non-empty run"),
                        length: run.len() as u32,
                    });
                }
                run.clear();
                if let Some(rank) = slot {
                    run.push(rank);
                }
            }
            if slot.is_none() {
                break;
            }
            i += 1;
        }
    }
    sort_descending_stably(&mut found, |s| s.key());
    found
}

pub fn best_sequence(hand: Hand) -> Option<Sequence> {
    sequences(hand).into_iter().next()
}

/// Every trio and quatorze the hand holds, best first.
///
/// Only tens and above count: nines, eights and sevens never form a set.
pub fn sets(hand: Hand) -> Vec<CardSet> {
    let mut found: Vec<CardSet> = Rank::ALL
        .iter()
        .filter(|rank| rank.counts_for_set() && hand.count_of(**rank) >= MINIMUM_SET)
        .map(|rank| CardSet {
            rank: *rank,
            count: hand.count_of(*rank),
        })
        .collect();
    sort_descending_stably(&mut found, |s| s.key());
    found
}

pub fn best_set(hand: Hand) -> Option<CardSet> {
    sets(hand).into_iter().next()
}

/// Sort descending while leaving tied elements in the order they arrived.
///
/// Python's `sorted(..., reverse=True)` is **stable**: equal elements keep
/// their original order rather than having it reversed. Three Rust renderings
/// look equivalent and are not:
///
/// | Form | Ties |
/// |---|---|
/// | `sort_by_key(\|a\| Reverse(key(a)))` | preserved — correct, and what clippy prefers |
/// | `sort_by(\|a, b\| key(b).cmp(&key(a)))` | preserved — also correct |
/// | `sort_by_key(key); reverse()` | **inverted** — wrong, and the obvious translation |
/// | `sort_unstable_by(..)` | unspecified — wrong by omission |
///
/// Measured: `JH QH KH JS QS KS` holds two tierces to the king keying
/// identically, and the third form returns spades where the oracle returns
/// hearts. That particular tie is unobservable downstream (`docs/DESIGN.md`
/// §2.2), but the ties that choose a card are not, so the discipline is kept
/// everywhere rather than selectively.
fn sort_descending_stably<T, K: Ord>(items: &mut [T], key: impl Fn(&T) -> K) {
    items.sort_by_key(|a| std::cmp::Reverse(key(a)));
}

// -- comparison -------------------------------------------------------------

fn compare_keys(mine: Option<(u32, u32)>, theirs: Option<(u32, u32)>) -> Comparison {
    match (mine, theirs) {
        (None, None) => Comparison::Equal,
        (None, Some(_)) => Comparison::Worse,
        (Some(_), None) => Comparison::Better,
        (Some(a), Some(b)) if a > b => Comparison::Better,
        (Some(a), Some(b)) if a < b => Comparison::Worse,
        _ => Comparison::Equal,
    }
}

/// Length first, then pip value. An exact tie scores for neither player.
pub fn compare_point(mine: Option<Point>, theirs: Option<Point>) -> Comparison {
    compare_keys(mine.map(Point::key), theirs.map(Point::key))
}

/// Length first, then top card. An exact tie scores for neither player.
pub fn compare_sequence(mine: Option<Sequence>, theirs: Option<Sequence>) -> Comparison {
    compare_keys(mine.map(Sequence::key), theirs.map(Sequence::key))
}

/// Size first -- any quatorze beats any trio -- then rank.
///
/// A tie is impossible: two sets of one rank would need six cards of it, and
/// only four exist.
pub fn compare_set(mine: Option<CardSet>, theirs: Option<CardSet>) -> Comparison {
    compare_keys(mine.map(CardSet::key), theirs.map(CardSet::key))
}

// -- category scoring -------------------------------------------------------

/// What this hand scores for sequences *if it wins the category*.
///
/// Cotton, 1674: the holder of the biggest sequence "reckons all his less
/// Sequences". The loser of the category scores nothing at all, which is the
/// caller's business, not this function's.
pub fn score_sequences(hand: Hand) -> u32 {
    sequences(hand).iter().map(|s| s.score()).sum()
}

/// What this hand scores for sets *if it wins the category*.
pub fn score_sets(hand: Hand) -> u32 {
    sets(hand).iter().map(|s| s.score()).sum()
}

// -- carte blanche ----------------------------------------------------------

/// True if the hand holds no jack, queen or king.
///
/// Worth 10 points. Tens and aces do not deny it. It occurs about once in
/// 1,792 *hands* -- so about once in 896 deals -- and two players can never
/// hold it at once in the 32-card game.
pub fn is_carte_blanche(hand: Hand) -> bool {
    !hand.cards().any(|card| card.rank().is_court())
}

/// What a hand is worth in declarations, one phrase per holding.
///
/// For a player deciding what to keep, which is the decision a beginner is
/// least equipped to make: the exchange is where most of a deal's points are
/// won or thrown away. Suits are named, since this describes the player's own
/// hand to the player; it is never what is said aloud. Empty when there is
/// nothing to call.
pub fn holdings(held: Hand) -> Vec<String> {
    let mut parts = Vec::new();
    if let Some(point) = best_point(held) {
        parts.push(format!(
            "point of {} ({}) in {}",
            point.length,
            point.pip_value,
            point.suit.name()
        ));
    }
    for sequence in sequences(held) {
        parts.push(format!(
            "{} to the {} in {}",
            sequence.name(),
            sequence.top.name(),
            sequence.suit.name()
        ));
    }
    for held_set in sets(held) {
        parts.push(format!("{} of {}s", held_set.name(), held_set.rank.name()));
    }
    // Guarded on non-empty: `is_carte_blanche` is vacuously true of an empty
    // hand, which is correct as a predicate and nonsense at a table.
    if !held.is_empty() && is_carte_blanche(held) {
        parts.push("carte blanche \u{2014} no court card at all".to_string());
    }
    parts
}

#[cfg(test)]
mod holdings_tests {
    use super::*;

    #[test]
    fn a_hand_is_described_by_everything_it_could_call() {
        let held = Hand::parse("AC KC QC JC TC AD AH AS").unwrap();
        let described = holdings(held).join(", ");
        assert!(
            described.contains("point of 5 (51) in clubs"),
            "{described}"
        );
        assert!(
            described.contains("quint to the ace in clubs"),
            "{described}"
        );
        assert!(described.contains("quatorze of aces"), "{described}");
    }

    #[test]
    fn carte_blanche_is_named_and_an_empty_hand_is_worth_nothing() {
        let held = Hand::parse("AS TS 9S 8S 7S AH TH 9H").unwrap();
        assert!(holdings(held).iter().any(|h| h.contains("carte blanche")));
        assert!(holdings(Hand::EMPTY).is_empty());
    }
}
