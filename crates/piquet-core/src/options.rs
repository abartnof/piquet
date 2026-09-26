//! The lesser declarations a hand genuinely supports.
//!
//! Cavendish's examples of sinking are all *partial* — "he calls five cards,
//! and declares five spades, when he might have six"; a quart to the knave
//! called as a tierce to the knave; a quatorze called as a trio. A teaching
//! game that offered only all-or-nothing would have hidden the interesting
//! move in the game, which is why the table has to offer these explicitly:
//! the rules give the right to understate and the engine models it, but a
//! human cannot sink a holding the interface never lists.

use crate::cards::Hand;
use crate::combos::{best_point, sequences, sets, CardSet, Point, Sequence};
use crate::declarations::{Combination, Declaration};
use crate::scoring::Category;

/// Everything a player may say in a category, in the order a table offers it.
///
/// The full declaration first, since it is what a player means nine times in
/// ten; then saying nothing; then calling one step short. A hand with nothing
/// to call has one option, and it is the empty declaration.
pub fn declaration_options(hand: Hand, category: Category) -> Vec<Declaration> {
    let full = Declaration::full(hand, category);
    if full.is_empty() {
        return vec![full];
    }
    let mut options = vec![full, Declaration::sink()];
    options.extend(understatements(hand, category));
    options
}

/// One step short of the full declaration, keeping everything else intact.
pub fn understatements(hand: Hand, category: Category) -> Vec<Declaration> {
    let made = match category {
        Category::Point => {
            let Some(point) = best_point(hand) else {
                return Vec::new();
            };
            if point.length <= 1 {
                return Vec::new();
            }
            let shorter = point.length - 1;
            let pips: u32 = hand
                .ranks_in(point.suit)
                .iter()
                .take(shorter as usize)
                .map(|r| r.pip_value())
                .sum();
            vec![Combination::Point(Point {
                suit: point.suit,
                length: shorter,
                pip_value: pips,
            })]
        }
        Category::Sequences => {
            let runs = sequences(hand);
            let Some(best) = runs.first() else {
                return Vec::new();
            };
            if best.length <= 3 {
                return Vec::new();
            }
            // The best one shortened, and the rest kept. Dropping a lesser
            // claim instead would be a different move, and not one the sources
            // describe.
            let mut claims = vec![Combination::Sequence(Sequence {
                suit: best.suit,
                top: best.top,
                length: best.length - 1,
            })];
            claims.extend(runs[1..].iter().map(|s| Combination::Sequence(*s)));
            claims
        }
        _ => {
            let found = sets(hand);
            let Some(best) = found.first() else {
                return Vec::new();
            };
            if best.count != 4 {
                return Vec::new();
            }
            let mut claims = vec![Combination::Set(CardSet {
                rank: best.rank,
                count: 3,
            })];
            claims.extend(found[1..].iter().map(|s| Combination::Set(*s)));
            claims
        }
    };

    let declaration = Declaration { claims: made };
    if declaration.is_empty() || declaration.validate(hand, category).is_err() {
        return Vec::new();
    }
    vec![declaration]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn offered(text: &str, category: Category) -> Vec<String> {
        let hand = Hand::parse(text).unwrap();
        understatements(hand, category)
            .iter()
            .map(|d| d.describe())
            .collect()
    }

    /// The case an earlier version silently refused.
    ///
    /// It required two claims before offering anything, so a hand holding one
    /// sequence -- the commonest shape there is -- was never offered the
    /// chance to understate it, and sinking was unavailable at the table for
    /// exactly the holdings Cavendish writes about.
    #[test]
    fn a_single_quint_can_still_be_called_as_a_quart() {
        let offers = offered("AC KC QC JC TC 7D 8D 9D", Category::Sequences);
        assert_eq!(offers.len(), 1, "one understatement should be offered");
        assert!(offers[0].contains("quart"), "{offers:?}");
    }

    #[test]
    fn a_shortened_sequence_keeps_its_top_card_and_the_lesser_runs() {
        // A quart to the ace becomes a *tierce to the ace*, not to the king:
        // it is shortened from the bottom, because the top card is what names
        // it and what the opponent is told. And the lesser run is still
        // declared -- dropping a weaker claim instead would be a different
        // move, and not one the sources describe.
        let offers = offered("AC KC QC JC 9D TD JD", Category::Sequences);
        assert_eq!(offers.len(), 1);
        assert_eq!(offers[0], "tierce to the ace, tierce to the jack");
    }

    #[test]
    fn a_tierce_is_already_the_shortest_and_offers_nothing() {
        assert!(offered("AC KC QC 7D 8D", Category::Sequences).is_empty());
    }

    #[test]
    fn a_quatorze_can_be_called_as_a_trio() {
        let offers = offered("AC AD AH AS KC KD KH", Category::Sets);
        assert_eq!(offers.len(), 1);
        assert!(offers[0].contains("trio of aces"), "{offers:?}");
    }

    #[test]
    fn a_trio_offers_nothing_since_three_is_the_minimum() {
        assert!(offered("AC AD AH KC", Category::Sets).is_empty());
    }

    #[test]
    fn a_point_can_be_called_one_card_short() {
        // "He calls five cards, and declares five spades, when he might have
        // six" -- Cavendish's own example.
        let offers = offered("AS KS QS JS TS 9S 7H", Category::Point);
        assert_eq!(offers.len(), 1);
        assert!(offers[0].contains("point of 5"), "{offers:?}");
    }

    #[test]
    fn the_full_call_comes_first_then_silence_then_the_understatements() {
        let hand = Hand::parse("AC KC QC JC TC 7D 8D 9D").unwrap();
        let options = declaration_options(hand, Category::Sequences);
        assert_eq!(options.len(), 3);
        assert_eq!(options[0], Declaration::full(hand, Category::Sequences));
        assert!(options[1].is_empty(), "the second option is saying nothing");
        assert!(options[2].describe().contains("quart"));
    }

    #[test]
    fn a_hand_with_nothing_to_call_has_exactly_one_option() {
        let hand = Hand::parse("AC KD 9H 7S").unwrap();
        let options = declaration_options(hand, Category::Sets);
        assert_eq!(options.len(), 1);
        assert!(options[0].is_empty());
    }

    #[test]
    fn every_understatement_is_actually_held() {
        // The whole point of an understatement is that it is true. One the
        // hand does not support would be refused by the engine, and the table
        // would have offered the player an illegal move.
        for text in [
            "AC KC QC JC TC 7D 8D 9D",
            "AC AD AH AS KC KD KH",
            "AS KS QS JS TS 9S 7H",
            "AC KC QC JC 9D TD JD",
        ] {
            let hand = Hand::parse(text).unwrap();
            for category in [Category::Point, Category::Sequences, Category::Sets] {
                for option in understatements(hand, category) {
                    option
                        .validate(hand, category)
                        .unwrap_or_else(|e| panic!("{text} / {category:?}: {e}"));
                    assert!(
                        option.score() < Declaration::full(hand, category).score(),
                        "{text}: an understatement must be worth less than the full call"
                    );
                }
            }
        }
    }
}
