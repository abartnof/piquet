//! Skill as a capability ladder, not a noise dial.
//!
//! Each rung *refines* the one below rather than replacing it, so a rung can
//! only improve on its predecessor -- a lesson learnt the hard way, when a
//! plausible rule for cashing winners turned out to lose to the simpler rung
//! beneath it. Two proposed rungs were deleted for failing measurement.
//!
//! Erraticism varies the *capability* brought to bear rather than adding noise
//! to the answer. An erratic opponent is occasionally brilliant and
//! occasionally sloppy, which reads as far more human than uniform randomness.

use crate::agents::Agent;
use crate::cards::{Card, Hand, Rank, Suit};
use crate::chances::weights_for;
use crate::declarations::{Combination, Declaration};
use crate::observation::View;
use crate::rng::Rng;
use crate::scoring::{Category, Player};
use crate::style::{Style, BALANCED};
use crate::util::{first_max_by_key, first_min_by_key};

pub const MAX_LEVEL: u32 = 4;

/// Above this, in settlement-weighted points, a declaration is too good to
/// sink. Nobody sinks a quatorze.
pub const SINK_CEILING: f64 = 4.0;

#[derive(Clone)]
pub struct HeuristicAgent {
    pub level: u32,
    pub style: Style,
    pub erraticism: f64,
    pub rng: Rng,
    pub label: String,
}

impl HeuristicAgent {
    pub fn new(level: u32, seed: u32) -> Result<HeuristicAgent, String> {
        if !(1..=MAX_LEVEL).contains(&level) {
            return Err(format!("level must be 1..{MAX_LEVEL}, got {level}"));
        }
        Ok(HeuristicAgent {
            level,
            style: BALANCED,
            erraticism: 0.0,
            rng: Rng::seeded(seed),
            label: format!("L{level}"),
        })
    }

    pub fn with_style(mut self, style: Style) -> HeuristicAgent {
        self.style = style;
        self
    }

    pub fn with_erraticism(mut self, erraticism: f64) -> Result<HeuristicAgent, String> {
        if !(0.0..=1.0).contains(&erraticism) {
            return Err(format!("erraticism must be 0..1, got {erraticism}"));
        }
        self.erraticism = erraticism;
        Ok(self)
    }

    pub fn named(mut self, name: &str) -> HeuristicAgent {
        self.label = name.to_string();
        self
    }

    /// The rung this particular decision is made at.
    ///
    /// Python rounds half to even and Rust rounds half away from zero, but the
    /// input is a continuous Gaussian, so the two disagree with probability
    /// zero (`docs/DESIGN.md` §2.2, hazard 4).
    fn rung(&mut self) -> u32 {
        if self.erraticism == 0.0 {
            return self.level;
        }
        let drawn = self
            .rng
            .gauss(f64::from(self.level), self.erraticism * 2.0)
            .round();
        (drawn.max(1.0) as u32).min(MAX_LEVEL)
    }

    /// How much this card is worth holding on to.
    ///
    /// Weighs three things against each other: length, which wins the point;
    /// combination potential, which wins sequences and sets; and raw rank,
    /// which wins tricks. `discard_boldness` sets the exchange rate between
    /// the first two, which is exactly the judgement Hoyle wrote his 1744
    /// treatise about.
    fn keep_value(&self, card: Card, hand: Hand) -> f64 {
        let bold = self.style.discard_boldness;
        let suit_length = f64::from(hand.in_suit(card.suit()).len());
        let held = hand.ranks_in(card.suit());
        let adjacent = [-2i32, -1, 1, 2]
            .iter()
            .filter(|step| {
                let rank = i32::from(card.rank().0) + *step;
                (7..=14).contains(&rank) && held.contains(&Rank(rank as u8))
            })
            .count() as f64;
        let set_size = if card.rank().counts_for_set() {
            f64::from(hand.count_of(card.rank()))
        } else {
            0.0
        };
        let trick_power = f64::from(card.rank().0 - Rank::SEVEN.0);

        let mut value = (1.0 - bold) * 1.5 * suit_length
            + bold * (1.2 * adjacent + 1.6 * set_size)
            + 0.8 * trick_power;
        if !card.rank().counts_for_set() {
            // "Players discard low cards (nine or lower) even if this means
            // getting rid of four or more of one suit."
            value -= 2.0;
        }
        value
    }

    /// What one point to me is worth in settlement, or one on its own.
    ///
    /// A declaration is worth its face value inside a deal and something else
    /// inside a partie. A player three points short of the rubicon with the
    /// partie ending is looking at a tierce worth closer to eighteen, and
    /// sinking it to buy silence stops being a trade anybody would make.
    pub fn point_value(&self, view: &View) -> f64 {
        let Some(standing) = view.partie else {
            return 1.0;
        };
        let (mine, _) = weights_for(standing, view.me == Player::Elder);
        mine.max(0.0)
    }

    /// True if no card that could still beat this one is unaccounted for.
    ///
    /// Rung 3 and above. Simply remembering what has been played, and the
    /// first capability that requires paying attention.
    fn is_established(&self, view: &View, card: Card) -> bool {
        view.unseen()
            .in_suit(card.suit())
            .cards()
            .all(|other| other.rank() < card.rank())
    }

    /// What throwing this card would cost by exposing a higher one.
    ///
    /// Holding king-and-a-small-one, the small one keeps the king alive: throw
    /// it and the king falls to the ace. Measured in rank-units so it competes
    /// with the card's own rank rather than merely breaking ties -- an earlier
    /// version put it behind rank in the sort key, where it could only fire
    /// when two legal cards shared a rank, and so did nothing at all.
    fn guard_cost(&self, view: &View, card: Card) -> f64 {
        let higher: Vec<Card> = view
            .hand
            .in_suit(card.suit())
            .cards()
            .filter(|c| c.rank() > card.rank())
            .collect();
        let Some(protected) = higher.iter().map(|c| c.rank()).max() else {
            return 0.0;
        };
        let worth = f64::from(protected.0.saturating_sub(Rank::TEN.0)) / 4.0;
        self.style.guard_retention * 3.0 * worth
    }

    /// The opponent's point suit, if they had to show it.
    ///
    /// Rung 4 and above. A point that scored must be exposed on request, so
    /// this is information the rules hand over -- and leading into a known
    /// long suit is how tricks are given away.
    fn opponent_long_suit(&self, view: &View) -> Option<Suit> {
        view.seen.iter().find_map(|combination| match combination {
            Combination::Point(point) => Some(point.suit),
            _ => None,
        })
    }

    /// Run a suit. Which suit is what the upper rungs get better at.
    fn lead(&self, view: &View, legal: &[Card], rung: u32) -> Card {
        let avoid = if rung >= 4 {
            self.opponent_long_suit(view)
        } else {
            None
        };
        let candidates: Vec<Card> = {
            let kept: Vec<Card> = legal
                .iter()
                .copied()
                .filter(|c| Some(c.suit()) != avoid)
                .collect();
            if kept.is_empty() {
                legal.to_vec()
            } else {
                kept
            }
        };

        let strength = |card: &Card| -> (u32, u32, Rank) {
            let length = view.hand.in_suit(card.suit()).len();
            if rung >= 3 {
                // Prefer a suit you can actually run: one where your cards are
                // already winners.
                let established = view
                    .hand
                    .in_suit(card.suit())
                    .cards()
                    .filter(|other| self.is_established(view, *other))
                    .count() as u32;
                (established, length, card.rank())
            } else {
                (0, length, card.rank())
            }
        };
        *first_max_by_key(&candidates, strength).expect("a legal play exists")
    }

    fn follow(&self, view: &View, legal: &[Card], rung: u32) -> Card {
        let led = view.current_trick.expect("a trick in progress").led;
        let beating: Vec<Card> = legal
            .iter()
            .copied()
            .filter(|c| c.suit() == led.suit() && c.rank() > led.rank())
            .collect();
        if !beating.is_empty() {
            // Win as cheaply as possible.
            return *first_min_by_key(&beating, |c| (c.rank(), c.suit()))
                .expect("beating is non-empty");
        }

        // Cannot win: throw the lowest card. Style breaks the tie -- a player
        // who hoards guards would rather not strip a high card of its escort.
        if rung >= 3 && self.style.guard_retention > 0.0 {
            let mut ranked = legal.to_vec();
            // Stable: ties keep the order they arrived in, as Python's sort
            // does. The key is a float, so ties are genuinely reachable.
            ranked.sort_by(|a, b| {
                let ka = (
                    f64::from(a.rank().0 - Rank::SEVEN.0) + self.guard_cost(view, *a),
                    a.suit(),
                );
                let kb = (
                    f64::from(b.rank().0 - Rank::SEVEN.0) + self.guard_cost(view, *b),
                    b.suit(),
                );
                ka.0.partial_cmp(&kb.0)
                    .expect("no NaN in a guard cost")
                    .then(ka.1.cmp(&kb.1))
            });
            return ranked[0];
        }
        *first_min_by_key(legal, |c| (c.rank(), c.suit())).expect("a legal play exists")
    }
}

impl Agent for HeuristicAgent {
    fn name(&self) -> &str {
        &self.label
    }

    /// Always take the full exchange; choose what to throw by rung.
    ///
    /// Taking everything on offer is not a judgement call -- measured over
    /// 4,000 deals, an agent that under-exchanges throws away most of elder's
    /// advantage. What to *keep* is the judgement call.
    fn exchange(&mut self, view: &View) -> Hand {
        let rung = self.rung();
        let mut ranked: Vec<Card> = view.hand.cards().collect();
        if rung <= 1 {
            ranked.sort_by_key(|c| (c.rank(), c.suit()));
        } else {
            // A float key, so ties are reachable; the sort must be stable.
            ranked.sort_by(|a, b| {
                self.keep_value(*a, view.hand)
                    .partial_cmp(&self.keep_value(*b, view.hand))
                    .expect("no NaN in a keep value")
            });
        }
        ranked.truncate(view.exchange_limit);
        Hand::of(&ranked).expect("a hand holds no duplicate")
    }

    /// Declare everything, unless this opponent is the concealing sort.
    ///
    /// Sinking is only available at the top of the ladder, where the agent has
    /// enough sense to use the silence it buys.
    fn declare(&mut self, view: &View, category: Category) -> Declaration {
        let full = Declaration::full(view.hand, category);
        if self.rung() < 4 || full.is_empty() {
            return full;
        }
        if f64::from(full.score()) * self.point_value(view) > SINK_CEILING {
            return full;
        }
        if self.rng.next_f64() < self.style.sinking {
            return Declaration::sink();
        }
        full
    }

    fn play(&mut self, view: &View) -> Card {
        let rung = self.rung();
        let legal: Vec<Card> = view.legal_plays.cards().collect();
        if legal.len() == 1 {
            return legal[0];
        }
        if rung <= 1 {
            return *first_max_by_key(&legal, |c| (c.rank(), c.suit()))
                .expect("a legal play exists");
        }
        if view.current_trick.is_none() {
            self.lead(view, &legal, rung)
        } else {
            self.follow(view, &legal, rung)
        }
    }
}
