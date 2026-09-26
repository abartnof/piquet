//! The meld layer: announcing, showing, and sinking.
//!
//! What is *said* and what is *held* are different things, and keeping them
//! apart is the whole job of this module. At the table you announce "point of
//! five", not "five spades": the suit is never spoken, and neither is the
//! tie-break unless it is asked for.
//!
//! ```text
//! "Point of five."  "Equal."  "Making forty-nine."  "Good."
//! ```
//!
//! Which cards a combination was made of stays private unless it scores, at
//! which point either player "may ask to see any combination that has been
//! scored for or which caused no score because of equality" (Cavendish).

use crate::cards::{Card, Hand, Rank};
use crate::combos::{
    best_point, compare_point, compare_sequence, compare_set, sequences, sets, CardSet, Comparison,
    Point, Sequence,
};
use crate::scoring::{Category, Player};

/// One claimed holding, of whichever kind the category is contesting.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Combination {
    Point(Point),
    Sequence(Sequence),
    Set(CardSet),
}

impl Combination {
    pub fn key(self) -> (u32, u32) {
        match self {
            Combination::Point(c) => c.key(),
            Combination::Sequence(c) => c.key(),
            Combination::Set(c) => c.key(),
        }
    }

    pub fn score(self) -> u32 {
        match self {
            Combination::Point(c) => c.score(),
            Combination::Sequence(c) => c.score(),
            Combination::Set(c) => c.score(),
        }
    }

    pub fn category(self) -> Category {
        match self {
            Combination::Point(_) => Category::Point,
            Combination::Sequence(_) => Category::Sequences,
            Combination::Set(_) => Category::Sets,
        }
    }

    pub fn is_supported_by(self, hand: Hand) -> bool {
        match self {
            Combination::Point(c) => c.is_supported_by(hand),
            Combination::Sequence(c) => c.is_supported_by(hand),
            Combination::Set(c) => c.is_supported_by(hand),
        }
    }

    /// The cards in `hand` this claim is made of -- what would be laid on the
    /// table if it were shown. An understated point is its top cards, since
    /// that is what its pip count was taken from; an understated set is any
    /// `count` of the rank, taken in pack order.
    pub fn cards_in(self, hand: Hand) -> Hand {
        let picked: Vec<Card> = match self {
            Combination::Point(p) => {
                let mut suit: Vec<Card> = hand.in_suit(p.suit).cards().collect();
                suit.sort_by_key(|c| std::cmp::Reverse(c.rank()));
                suit.truncate(p.length as usize);
                suit
            }
            Combination::Sequence(s) => (0..s.length)
                .map(|below| Card::new(Rank(s.top.0 - below as u8), s.suit))
                .filter(|card| hand.holds(*card))
                .collect(),
            Combination::Set(set) => hand
                .cards()
                .filter(|card| card.rank() == set.rank)
                .take(set.count as usize)
                .collect(),
        };
        Hand(picked.iter().fold(0, |mask, card| mask | 1 << card.0))
    }

    /// How it reads aloud once it has to be shown. Never names a suit.
    pub fn describe(self) -> String {
        match self {
            Combination::Point(c) => format!("point of {} ({})", c.length, c.pip_value),
            Combination::Sequence(c) => format!("{} to the {}", c.name(), c.top.name()),
            Combination::Set(c) => format!("{} of {}s", c.name(), c.rank.name()),
        }
    }
}

/// What is actually said aloud when declaring.
///
/// A declaration's sort key stripped of the suit, and often stripped of its
/// second half as well.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Announcement {
    pub category: Category,
    /// Cards in the point or sequence, or the size of the set.
    pub primary: u32,
    /// Pip value, top rank, or set rank. `None` when it was never spoken,
    /// which is the usual case: it is asked for only to separate two matching
    /// shapes.
    pub tiebreak: Option<u32>,
}

impl Announcement {
    /// The same announcement with the tie-break left unsaid.
    pub fn shape(self) -> Announcement {
        Announcement {
            category: self.category,
            primary: self.primary,
            tiebreak: None,
        }
    }

    /// Whether a holding is consistent with what was actually said.
    ///
    /// Only as far as it went: a shape announced without its tie-break rules
    /// out every other length and nothing else. Reading more into it than was
    /// spoken is how an engine quietly gives one player information the table
    /// never gave them.
    pub fn matches(self, best: Option<Combination>) -> bool {
        let Some(best) = best else { return false };
        let (primary, tiebreak) = best.key();
        if primary != self.primary {
            return false;
        }
        self.tiebreak.is_none_or(|t| t == tiebreak)
    }

    pub fn spoken(self) -> String {
        match self.category {
            Category::Point => format!("point of {}", self.primary),
            Category::Sequences => {
                let name = match self.primary {
                    3 => "tierce",
                    4 => "quart",
                    5 => "quint",
                    6 => "sixième",
                    7 => "septième",
                    _ => "huitième",
                };
                name.to_string()
            }
            _ => {
                let name = if self.primary == 4 {
                    "quatorze"
                } else {
                    "trio"
                };
                name.to_string()
            }
        }
    }
}

/// Everything a player claims in one category.
#[derive(Clone, PartialEq, Eq, Debug, Default)]
pub struct Declaration {
    pub claims: Vec<Combination>,
}

impl Declaration {
    /// Announce nothing, conceding the category to buy silence.
    pub fn sink() -> Declaration {
        Declaration { claims: Vec::new() }
    }

    /// Announce everything the hand holds in this category.
    pub fn full(hand: Hand, category: Category) -> Declaration {
        let claims = match category {
            Category::Point => best_point(hand)
                .map(|p| vec![Combination::Point(p)])
                .unwrap_or_default(),
            Category::Sequences => sequences(hand)
                .into_iter()
                .map(Combination::Sequence)
                .collect(),
            Category::Sets => sets(hand).into_iter().map(Combination::Set).collect(),
            _ => Vec::new(),
        };
        Declaration { claims }
    }

    pub fn is_empty(&self) -> bool {
        self.claims.is_empty()
    }

    /// The claim that decides the category.
    ///
    /// `max_by_key` returns the **last** maximum in Rust where Python's `max`
    /// returns the first, so the iterator is reversed to match the oracle.
    pub fn best(&self) -> Option<Combination> {
        self.claims.iter().rev().max_by_key(|c| c.key()).copied()
    }

    /// What this declaration is worth *if it wins the category*.
    pub fn score(&self) -> u32 {
        self.claims.iter().map(|c| c.score()).sum()
    }

    /// Check the claims are of the right kind, held, and consistent.
    pub fn validate(&self, hand: Hand, category: Category) -> Result<(), String> {
        if self.claims.is_empty() {
            return Ok(());
        }
        for claim in &self.claims {
            if claim.category() != category {
                return Err(format!(
                    "{} is the wrong category: {} was being contested",
                    claim.describe(),
                    category.name().to_lowercase()
                ));
            }
            if !claim.is_supported_by(hand) {
                return Err(format!("not held: {}", claim.describe()));
            }
        }

        if category == Category::Point && self.claims.len() > 1 {
            return Err("only one point may be declared".to_string());
        }
        if category == Category::Sequences {
            // Two sequences may share a suit -- a gap splits it -- but they
            // may not overlap.
            let mut seen: Vec<(u8, i32)> = Vec::new();
            for claim in &self.claims {
                let Combination::Sequence(s) = claim else {
                    continue;
                };
                let lowest = i32::from(s.top.0) - s.length as i32 + 1;
                let cells: Vec<(u8, i32)> = (lowest..=i32::from(s.top.0))
                    .map(|r| (s.suit.0, r))
                    .collect();
                if cells.iter().any(|c| seen.contains(c)) {
                    return Err(format!(
                        "cannot claim {}: it shares cards with another sequence \
                         already declared",
                        claim.describe()
                    ));
                }
                seen.extend(cells);
            }
        }
        if category == Category::Sets {
            let mut ranks: Vec<u8> = Vec::new();
            for claim in &self.claims {
                let Combination::Set(s) = claim else { continue };
                if ranks.contains(&s.rank.0) {
                    return Err("two sets cannot be claimed of the same rank".to_string());
                }
                ranks.push(s.rank.0);
            }
        }
        Ok(())
    }

    /// What this declaration sounds like from across the table.
    pub fn announce(&self, category: Category) -> Option<Announcement> {
        let best = self.best()?;
        let (primary, tiebreak) = best.key();
        Some(Announcement {
            category,
            primary,
            tiebreak: Some(tiebreak),
        })
    }

    /// Every card the claims are made of. See [`Combination::cards_in`].
    pub fn cards_in(&self, hand: Hand) -> Hand {
        Hand(
            self.claims
                .iter()
                .fold(0, |mask, c| mask | c.cards_in(hand).0),
        )
    }

    pub fn describe(&self) -> String {
        if self.claims.is_empty() {
            "sunk".to_string()
        } else {
            self.claims
                .iter()
                .map(|c| c.describe())
                .collect::<Vec<_>>()
                .join(", ")
        }
    }
}

/// Compare two holdings within one category.
pub fn compare_in(
    category: Category,
    mine: Option<Combination>,
    theirs: Option<Combination>,
) -> Comparison {
    match category {
        Category::Point => compare_point(mine.and_then(as_point), theirs.and_then(as_point)),
        Category::Sequences => {
            compare_sequence(mine.and_then(as_sequence), theirs.and_then(as_sequence))
        }
        _ => compare_set(mine.and_then(as_set), theirs.and_then(as_set)),
    }
}

fn as_point(c: Combination) -> Option<Point> {
    match c {
        Combination::Point(p) => Some(p),
        _ => None,
    }
}

fn as_sequence(c: Combination) -> Option<Sequence> {
    match c {
        Combination::Sequence(s) => Some(s),
        _ => None,
    }
}

fn as_set(c: Combination) -> Option<CardSet> {
    match c {
        Combination::Set(s) => Some(s),
        _ => None,
    }
}

/// How one category of the dialogue turned out. Kept for the tutor.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CategoryResult {
    pub category: Category,
    pub elder: Declaration,
    pub younger: Declaration,
    pub comparison: Comparison,
}

impl CategoryResult {
    pub fn winner(&self) -> Option<Player> {
        match self.comparison {
            Comparison::Better => Some(Player::Elder),
            Comparison::Worse => Some(Player::Younger),
            Comparison::Equal => None,
        }
    }

    /// What younger says in answer to elder's declaration.
    pub fn response(&self) -> &'static str {
        match self.comparison {
            Comparison::Better => "good",
            Comparison::Worse => "not good",
            Comparison::Equal => "equal",
        }
    }

    pub fn declaration_of(&self, player: Player) -> &Declaration {
        match player {
            Player::Elder => &self.elder,
            Player::Younger => &self.younger,
        }
    }

    /// Whether the two holdings were the same length, or the same size.
    ///
    /// This is the question "equal?" answers, and the only thing that makes
    /// anyone state a tie-break.
    pub fn shapes_match(&self) -> bool {
        match (self.elder.best(), self.younger.best()) {
            (Some(e), Some(y)) => e.key().0 == y.key().0,
            _ => false,
        }
    }

    /// What that player said aloud. Always public.
    ///
    /// Elder gives his tie-break when the shapes match, and not otherwise.
    /// Younger never gives hers at all.
    ///
    /// And younger names a holding only if she won the category with it, or
    /// if the shapes matched -- when her "equal" said as much. Beaten
    /// outright, she said "good" and nothing else: pagat has her announce only
    /// "combinations in categories where she has said 'not good' or where
    /// elder has not made any declaration", and Foster's dealer claims "the
    /// combinations which are good in his own hand".
    pub fn announcement_of(&self, player: Player) -> Option<Announcement> {
        let spoken = self.declaration_of(player).announce(self.category)?;
        if player == Player::Elder && self.shapes_match() {
            Some(spoken)
        } else if player == Player::Younger
            && self.winner() == Some(Player::Elder)
            && !self.shapes_match()
        {
            None
        } else {
            Some(spoken.shape())
        }
    }

    /// The cards this player had to expose, if any.
    ///
    /// A declaration that was beaten scores nothing and is never shown -- so
    /// the loser of a category gives away its shape but not its suit.
    pub fn shown(&self, player: Player) -> Vec<Combination> {
        match self.winner() {
            Some(w) if w == player => self.declaration_of(player).claims.clone(),
            None => self.declaration_of(player).claims.clone(),
            _ => Vec::new(),
        }
    }
}

#[cfg(test)]
mod cards_tests {
    use super::*;
    use crate::cards::Hand;
    use crate::scoring::Category;

    fn cards(hand: &str, category: Category) -> Vec<String> {
        let hand = Hand::parse(hand).unwrap();
        Declaration::full(hand, category)
            .cards_in(hand)
            .cards()
            .map(|c| c.code())
            .collect()
    }

    #[test]
    fn a_point_is_made_of_its_suit() {
        assert_eq!(cards("AS KS 9S 7H 8D", Category::Point), ["9S", "KS", "AS"]);
    }

    #[test]
    fn a_sequence_is_made_of_its_run_and_nothing_either_side() {
        // The quart to the king, not the stray seven below the gap.
        let got = cards("KH QH JH TH 7H AC", Category::Sequences);
        assert_eq!(got, ["TH", "JH", "QH", "KH"]);
    }

    #[test]
    fn a_set_is_made_of_its_rank() {
        let got = cards("AS AH AD 7C 8C", Category::Sets);
        assert_eq!(got, ["AD", "AH", "AS"]);
    }

    #[test]
    fn an_understated_claim_is_made_of_only_what_it_claims() {
        // Five spades called as four: the top four, which is what the pip
        // count of the understatement is taken from.
        let hand = Hand::parse("AS KS QS JS 9S 7H").unwrap();
        let short = crate::options::understatements(hand, Category::Point);
        let got: Vec<String> = short[0].cards_in(hand).cards().map(|c| c.code()).collect();
        assert_eq!(got, ["JS", "QS", "KS", "AS"]);
    }

    #[test]
    fn saying_nothing_is_made_of_nothing() {
        let hand = Hand::parse("AS KS QS").unwrap();
        assert!(Declaration::sink().cards_in(hand).is_empty());
    }
}
