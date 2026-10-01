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

use crate::cards::{Card, Hand, Rank, Suit};
use crate::scoring::Category;

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

/// One thing a hand could declare, described for its holder.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Holding {
    /// "point of 5 (46) in clubs" -- suits named, since this describes the
    /// player's own hand to the player; it is never what is said aloud.
    pub text: String,
    /// Carte blanche, point, sequences or sets.
    pub category: Category,
    /// The cards it is made of. For carte blanche, the whole hand, which is
    /// what has to be shown to prove it.
    pub cards: Hand,
    /// What it scores if it is good -- if the category is won with it.
    pub score: u32,
}

/// What a hand is worth in declarations, one holding at a time.
///
/// For a player deciding what to keep, which is the decision a beginner is
/// least equipped to make: the exchange is where most of a deal's points are
/// won or thrown away. Empty when there is nothing to call.
pub fn holdings(held: Hand) -> Vec<Holding> {
    let mut found = Vec::new();
    if let Some(point) = best_point(held) {
        found.push(Holding {
            text: format!(
                "point of {} ({}) in {}",
                point.length,
                point.pip_value,
                point.suit.name()
            ),
            category: Category::Point,
            cards: held.in_suit(point.suit),
            score: point.score(),
        });
    }
    for sequence in sequences(held) {
        let run = (0..sequence.length)
            .map(|below| Card::new(Rank(sequence.top.0 - below as u8), sequence.suit))
            .fold(0u32, |mask, card| mask | 1 << card.0);
        found.push(Holding {
            text: format!(
                "{} to the {} in {}",
                sequence.name(),
                sequence.top.name(),
                sequence.suit.name()
            ),
            category: Category::Sequences,
            cards: Hand(run),
            score: sequence.score(),
        });
    }
    for held_set in sets(held) {
        let of_rank = held
            .cards()
            .filter(|card| card.rank() == held_set.rank)
            .fold(0u32, |mask, card| mask | 1 << card.0);
        found.push(Holding {
            text: format!("{} of {}s", held_set.name(), held_set.rank.name()),
            category: Category::Sets,
            cards: Hand(of_rank),
            score: held_set.score(),
        });
    }
    // Guarded on non-empty: `is_carte_blanche` is vacuously true of an empty
    // hand, which is correct as a predicate and nonsense at a table.
    if !held.is_empty() && is_carte_blanche(held) {
        found.push(Holding {
            text: "carte blanche \u{2014} no court card at all".to_string(),
            category: Category::CarteBlanche,
            cards: held,
            score: crate::rules::CARTE_BLANCHE_SCORE as u32,
        });
    }
    found
}

#[cfg(test)]
mod holdings_tests {
    use super::*;

    fn codes(cards: Hand) -> Vec<String> {
        cards.cards().map(|c| c.code()).collect()
    }

    #[test]
    fn a_hand_is_described_by_everything_it_could_call() {
        let held = Hand::parse("AC KC QC JC TC AD AH AS").unwrap();
        let described: Vec<String> = holdings(held).into_iter().map(|h| h.text).collect();
        let described = described.join(", ");
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
    fn each_holding_names_its_category_and_its_cards() {
        // So a table can lift the cards a line is about, or sort the hand by
        // what it is worth.
        let held = Hand::parse("KH QH JH 9H AS AC AD 7C").unwrap();
        let found = holdings(held);
        let point = found
            .iter()
            .find(|h| h.category == Category::Point)
            .unwrap();
        assert_eq!(codes(point.cards), ["9H", "JH", "QH", "KH"]);
        let run = found
            .iter()
            .find(|h| h.category == Category::Sequences)
            .unwrap();
        assert_eq!(
            codes(run.cards),
            ["JH", "QH", "KH"],
            "the run, not the stray nine"
        );
        let set = found.iter().find(|h| h.category == Category::Sets).unwrap();
        assert_eq!(codes(set.cards), ["AC", "AD", "AS"]);
        for holding in &found {
            assert_eq!(holding.cards.without(held), Hand::EMPTY, "only cards held");
        }
    }

    #[test]
    fn each_holding_says_what_it_scores_if_good() {
        // The user: the worth list should say "point: sequence: set: and then
        // showed the points you'd get (if you won each declaration)".
        let held = Hand::parse("AS KS QS JS TS 9S AD KD QD QH 8C 7C").unwrap();
        let score_of = |text: &str| {
            holdings(held)
                .into_iter()
                .find(|h| h.text.starts_with(text))
                .unwrap_or_else(|| panic!("no {text}"))
                .score
        };
        assert_eq!(score_of("point of 6"), 6);
        assert_eq!(score_of("sixième"), 16);
        assert_eq!(score_of("tierce"), 3);
        assert_eq!(score_of("trio of queens"), 3);
        let four = Hand::parse("AS AH AD AC 7S").unwrap();
        assert_eq!(
            holdings(four)
                .iter()
                .find(|h| h.category == Category::Sets)
                .unwrap()
                .score,
            14
        );
        let blank = Hand::parse("AS TS 9S 8S 7S AH TH 9H").unwrap();
        let carte = holdings(blank)
            .into_iter()
            .find(|h| h.category == Category::CarteBlanche)
            .unwrap();
        assert_eq!(carte.score, 10);
    }

    #[test]
    fn carte_blanche_is_named_and_an_empty_hand_is_worth_nothing() {
        let held = Hand::parse("AS TS 9S 8S 7S AH TH 9H").unwrap();
        let blank = holdings(held)
            .into_iter()
            .find(|h| h.category == Category::CarteBlanche)
            .expect("carte blanche is a holding");
        assert!(blank.text.contains("carte blanche"));
        assert_eq!(blank.cards, held, "the whole hand is the proof");
        assert!(holdings(Hand::EMPTY).is_empty());
    }
}
