//! What every player -- human, heuristic or searching -- must provide.
//!
//! Agents read the game *only* through an [`Observation`](crate::observation),
//! which is what makes a strength measurement mean anything.

use crate::cards::{Card, Hand};
use crate::declarations::Declaration;
use crate::observation::View;
use crate::rng::Rng;
use crate::scoring::Category;

/// The contract every opponent satisfies.
///
/// Takes `&mut self` because an agent may carry a generator. The Python
/// original is a `typing.Protocol`, which nothing ever checks at runtime -- a
/// trait makes the same contract binding.
pub trait Agent {
    fn name(&self) -> &str;

    /// Which cards to discard. Between one and `view.exchange_limit`.
    fn exchange(&mut self, view: &View) -> Hand;

    /// What to announce in this category. May be less than is held.
    fn declare(&mut self, view: &View, category: Category) -> Declaration;

    /// Which card to lead or follow with, from `view.legal_plays`.
    fn play(&mut self, view: &View) -> Card;
}

/// How many cards to throw.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ExchangeSize {
    /// Take everything on offer. Measured over 4,000 deals, an agent that
    /// under-exchanges throws away most of elder's advantage.
    Max,
    /// Deliberately weaker.
    Random,
}

/// Legal moves chosen at random. The baseline, below the ladder's first rung.
///
/// It randomises only the genuinely strategic choices -- which cards to throw
/// and which card to play -- while making the structurally obvious ones:
/// exchange as many cards as allowed, and declare everything held. An agent
/// that threw points away arbitrarily would be a misleading baseline.
///
/// The default matters more than it looks. Measured over 4,000 deals, elder
/// wins 52.5% when both players take the full exchange but only 49.6% when
/// they take a random number, so elder's advantage is not automatic -- it has
/// to be *used*.
pub struct RandomAgent {
    pub rng: Rng,
    pub sink_probability: f64,
    pub exchange_size: ExchangeSize,
    pub label: String,
}

impl RandomAgent {
    pub fn new(seed: u32) -> RandomAgent {
        RandomAgent {
            rng: Rng::seeded(seed),
            sink_probability: 0.0,
            exchange_size: ExchangeSize::Max,
            label: "random".to_string(),
        }
    }

    pub fn named(mut self, name: &str) -> RandomAgent {
        self.label = name.to_string();
        self
    }
}

impl Agent for RandomAgent {
    fn name(&self) -> &str {
        &self.label
    }

    fn exchange(&mut self, view: &View) -> Hand {
        let count = match self.exchange_size {
            ExchangeSize::Max => view.exchange_limit,
            ExchangeSize::Random => self.rng.in_range(1, view.exchange_limit),
        };
        let cards: Vec<Card> = view.hand.cards().collect();
        Hand::of(&self.rng.sample(&cards, count)).expect("a sample holds no duplicate")
    }

    fn declare(&mut self, view: &View, category: Category) -> Declaration {
        if self.rng.next_f64() < self.sink_probability {
            return Declaration::sink();
        }
        Declaration::full(view.hand, category)
    }

    fn play(&mut self, view: &View) -> Card {
        let legal: Vec<Card> = view.legal_plays.cards().collect();
        *self.rng.choice(&legal)
    }
}
