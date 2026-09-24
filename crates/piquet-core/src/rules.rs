//! The deal as an immutable state machine.
//!
//! Every action returns a new `Deal`. Nothing mutates, which keeps a deal
//! cheap enough to hold inside a search node and makes the whole state
//! trivially serialisable -- which is what let this port be a mechanical
//! translation rather than a rewrite.

use crate::cards::{Card, Hand, Suit};
use crate::combos::is_carte_blanche;
use crate::declarations::{compare_in, CategoryResult, Declaration};
use crate::scoring::{Category, Player, ScoreLog};

pub const HAND_SIZE: usize = 12;
pub const TALON_SIZE: usize = 8;
pub const ELDER_MAX_EXCHANGE: usize = 5;
pub const CARTE_BLANCHE_SCORE: i32 = 10;
pub const TRICKS_PER_DEAL: usize = 12;
pub const CARDS_SCORE: i32 = 10;
pub const CAPOT_SCORE: i32 = 40;

/// Where a deal has got to. Only one action is legal in each phase.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Phase {
    ElderExchange,
    YoungerExchange,
    DeclarePoint,
    DeclareSequences,
    DeclareSets,
    Play,
    Complete,
}

impl Phase {
    pub const ALL: [Phase; 7] = [
        Phase::ElderExchange,
        Phase::YoungerExchange,
        Phase::DeclarePoint,
        Phase::DeclareSequences,
        Phase::DeclareSets,
        Phase::Play,
        Phase::Complete,
    ];

    pub fn value(self) -> &'static str {
        match self {
            Phase::ElderExchange => "elder_exchange",
            Phase::YoungerExchange => "younger_exchange",
            Phase::DeclarePoint => "declare_point",
            Phase::DeclareSequences => "declare_sequences",
            Phase::DeclareSets => "declare_sets",
            Phase::Play => "play",
            Phase::Complete => "complete",
        }
    }

    /// Which declaration this phase is contesting.
    pub fn category(self) -> Option<Category> {
        match self {
            Phase::DeclarePoint => Some(Category::Point),
            Phase::DeclareSequences => Some(Category::Sequences),
            Phase::DeclareSets => Some(Category::Sets),
            _ => None,
        }
    }

    fn next_declaration(self) -> Option<Phase> {
        match self {
            Phase::DeclarePoint => Some(Phase::DeclareSequences),
            Phase::DeclareSequences => Some(Phase::DeclareSets),
            Phase::DeclareSets => Some(Phase::Play),
            _ => None,
        }
    }
}

/// One trick: a card led, and the card played to it.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Trick {
    pub leader: Player,
    pub led: Card,
    pub followed: Option<Card>,
}

impl Trick {
    pub fn complete(self) -> bool {
        self.followed.is_some()
    }

    /// The higher card of the suit led takes it.
    ///
    /// There are no trumps, so a card of another suit never wins, however
    /// high. This is the rule newcomers get wrong most reliably.
    pub fn winner(self) -> Result<Player, String> {
        let Some(followed) = self.followed else {
            return Err("the trick is not finished".to_string());
        };
        if followed.suit() == self.led.suit() && followed.rank() > self.led.rank() {
            Ok(self.leader.opponent())
        } else {
            Ok(self.leader)
        }
    }
}

/// One deal, mid-flight.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Deal {
    pub hands: [Hand; 2],
    pub discards: [Hand; 2],
    pub talon: Vec<Card>,
    pub talon_taken: usize,
    pub phase: Phase,
    pub log: ScoreLog,
    /// Elder's declaration in the category being contested, awaiting younger's.
    pub elder_declaration: Option<Declaration>,
    /// How each category turned out, in order. For the tutor and the log.
    pub results: Vec<CategoryResult>,
    /// Younger's winnings, withheld until elder has led to the first trick.
    pub younger_pending: Vec<(i32, Category, String)>,
    pub tricks: Vec<Trick>,
    pub current_trick: Option<Trick>,
    /// Who leads to the next trick. Elder leads to the first.
    pub leader: Player,
}

impl Deal {
    pub fn hand_of(&self, player: Player) -> Hand {
        self.hands[player.index()]
    }

    pub fn discard_of(&self, player: Player) -> Hand {
        self.discards[player.index()]
    }

    pub fn talon_remaining(&self) -> usize {
        self.talon.len() - self.talon_taken
    }

    pub fn talon_untaken(&self) -> &[Card] {
        &self.talon[self.talon_taken..]
    }

    /// Whose turn it is to declare. Elder always speaks first in a category.
    pub fn to_declare(&self) -> Option<Player> {
        self.phase.category()?;
        Some(if self.elder_declaration.is_none() {
            Player::Elder
        } else {
            Player::Younger
        })
    }

    pub fn declaring_category(&self) -> Option<Category> {
        self.phase.category()
    }

    /// What younger has won but not yet scored.
    ///
    /// She scores nothing until elder has led to the first trick, which is the
    /// whole reason only elder can ever score a pique.
    pub fn pending_for_younger(&self) -> i32 {
        self.younger_pending
            .iter()
            .map(|(amount, _, _)| amount)
            .sum()
    }

    /// The most this player may exchange, right now.
    ///
    /// Elder is entitled to five. Younger is entitled to whatever elder left,
    /// which is usually three.
    pub fn exchange_limit(&self, player: Player) -> usize {
        match player {
            Player::Elder => ELDER_MAX_EXCHANGE.min(self.talon_remaining()),
            Player::Younger => self.talon_remaining(),
        }
    }

    /// Discard some cards and take the same number from the talon.
    ///
    /// Cards are taken in order from the top of the stock (Law 23), so younger
    /// draws from wherever elder stopped.
    pub fn exchange(&self, player: Player, discard: Hand) -> Result<Deal, String> {
        let expected = match player {
            Player::Elder => Phase::ElderExchange,
            Player::Younger => Phase::YoungerExchange,
        };
        if self.phase != expected {
            return Err(format!(
                "{} cannot exchange out of turn: the deal is at {}",
                player.name(),
                self.phase.value()
            ));
        }

        let count = discard.len() as usize;
        if count < 1 {
            // Cotton, 1674: "the Gamesters are both obliged to discard one
            // Card at least." Cavendish's Laws 21 and 22 say the same.
            return Err(format!("{} must discard at least one card", player.name()));
        }
        if player == Player::Elder && count > ELDER_MAX_EXCHANGE {
            return Err(format!(
                "elder may exchange at most five cards, not {count}"
            ));
        }
        let limit = self.exchange_limit(player);
        if count > limit {
            return Err(format!(
                "{} may take at most {limit}: only {} talon cards remain",
                player.name(),
                self.talon_remaining()
            ));
        }

        let hand = self.hand_of(player);
        let missing = discard.without(hand);
        if !missing.is_empty() {
            return Err(format!(
                "{} does not hold: {}",
                player.name(),
                missing.code()
            ));
        }

        let taken: Vec<Card> = self.talon[self.talon_taken..self.talon_taken + count].to_vec();
        let new_hand = hand.without(discard).union(Hand::of(&taken)?)?;

        let mut next = self.clone();
        next.hands[player.index()] = new_hand;
        next.discards[player.index()] = self.discard_of(player).union(discard)?;
        next.talon_taken = self.talon_taken + count;
        next.phase = match player {
            Player::Elder => Phase::YoungerExchange,
            Player::Younger => Phase::DeclarePoint,
        };
        // A fresh exchange clears any dialogue state, as in the original.
        next.elder_declaration = None;
        Ok(next)
    }

    /// Announce a declaration in the category currently being contested.
    ///
    /// Elder speaks first and scores at once if he wins. Younger answers, and
    /// her winnings are withheld until elder has led to the first trick.
    pub fn declare(&self, player: Player, declaration: Declaration) -> Result<Deal, String> {
        let Some(category) = self.phase.category() else {
            return Err(format!(
                "nothing is being declared: the deal is at {}",
                self.phase.value()
            ));
        };
        if Some(player) != self.to_declare() {
            return Err(format!(
                "{} cannot declare out of turn: {} is to speak in {}",
                player.name(),
                self.to_declare().map_or("nobody", |p| p.name()),
                category.name().to_lowercase()
            ));
        }

        declaration.validate(self.hand_of(player), category)?;

        if player == Player::Elder {
            let mut next = self.clone();
            next.elder_declaration = Some(declaration);
            return Ok(next);
        }

        let elder_declaration = self
            .elder_declaration
            .clone()
            .unwrap_or_else(Declaration::sink);
        let comparison = compare_in(category, elder_declaration.best(), declaration.best());
        let result = CategoryResult {
            category,
            elder: elder_declaration.clone(),
            younger: declaration.clone(),
            comparison,
        };

        let mut log = self.log.clone();
        let mut pending = self.younger_pending.clone();
        match result.winner() {
            Some(Player::Elder) => {
                log = log.record(
                    Player::Elder,
                    elder_declaration.score() as i32,
                    category,
                    &elder_declaration.describe(),
                )?;
            }
            Some(Player::Younger) => {
                pending.push((declaration.score() as i32, category, declaration.describe()));
            }
            None => {}
        }

        let mut next = self.clone();
        next.phase = self.phase.next_declaration().expect("a declaration phase");
        next.elder_declaration = None;
        next.results.push(result);
        next.log = log;
        next.younger_pending = pending;
        Ok(next)
    }

    /// True once elder has led to the first trick.
    ///
    /// The hinge of the whole dialogue. Younger answers "good" or "not good"
    /// as each category is contested, but she names nothing and scores nothing
    /// until elder has led -- so while he chooses the card he leads, all he
    /// knows of her point is that it beat his.
    pub fn elder_has_led(&self) -> bool {
        !self.tricks.is_empty() || self.current_trick.is_some()
    }

    pub fn to_play(&self) -> Option<Player> {
        if self.phase != Phase::Play {
            return None;
        }
        Some(if self.current_trick.is_none() {
            self.leader
        } else {
            self.leader.opponent()
        })
    }

    pub fn tricks_won(&self, player: Player) -> usize {
        self.tricks
            .iter()
            .filter(|t| t.winner().is_ok_and(|w| w == player))
            .count()
    }

    /// The cards this player may legally play right now.
    ///
    /// The leader may lead anything. The second player must follow suit if he
    /// can, and may otherwise play any card. This is also what the tutor uses
    /// to rule moves out: an illegal move costs nothing to detect.
    pub fn legal_plays(&self, player: Option<Player>) -> Hand {
        let Some(player) = player.or_else(|| self.to_play()) else {
            return Hand::EMPTY;
        };
        let hand = self.hand_of(player);
        let Some(trick) = self.current_trick else {
            return hand;
        };
        let following = hand.in_suit(trick.led.suit());
        if following.is_empty() {
            hand
        } else {
            following
        }
    }

    /// Lead or follow with one card.
    pub fn play(&self, player: Player, card: Card) -> Result<Deal, String> {
        if self.phase != Phase::Play {
            return Err(format!(
                "no card can be played: the deal is at {}",
                self.phase.value()
            ));
        }
        if Some(player) != self.to_play() {
            return Err(format!(
                "{} cannot play out of turn: {} is to play",
                player.name(),
                self.to_play().map_or("nobody", |p| p.name())
            ));
        }
        if !self.hand_of(player).holds(card) {
            return Err(format!("{} does not hold {}", player.name(), card.code()));
        }
        if !self.legal_plays(Some(player)).holds(card) {
            let led = self.current_trick.expect("a trick in progress").led.suit();
            return Err(format!(
                "{} must follow suit: {} were led",
                player.name(),
                suit_name(led)
            ));
        }

        let mut hands = self.hands;
        hands[player.index()] = self.hand_of(player).remove(card)?;

        if self.current_trick.is_none() {
            self.lead(player, card, hands)
        } else {
            self.follow(player, card, hands)
        }
    }

    fn lead(&self, player: Player, card: Card, hands: [Hand; 2]) -> Result<Deal, String> {
        let log = self.log.record(
            player,
            1,
            Category::Play,
            &format!("leads {}", card.display()),
        )?;
        let mut next = self.clone();
        next.hands = hands;
        next.current_trick = Some(Trick {
            leader: player,
            led: card,
            followed: None,
        });
        next.log = log;
        if self.tricks.is_empty() {
            // Younger declares only after elder has led to the first trick.
            // That single point is the whole reason she can never pique.
            next = next.release_youngers_declarations()?;
        }
        Ok(next)
    }

    fn follow(&self, _player: Player, card: Card, hands: [Hand; 2]) -> Result<Deal, String> {
        let mut trick = self.current_trick.expect("a trick in progress");
        trick.followed = Some(card);
        let winner = trick.winner()?;
        let mut tricks = self.tricks.clone();
        tricks.push(trick);

        let mut log = self.log.clone();
        if winner != trick.leader {
            log = log.record(
                winner,
                1,
                Category::Play,
                &format!("wins with {}", card.display()),
            )?;
        }
        if tricks.len() == TRICKS_PER_DEAL {
            log = log.record(winner, 1, Category::Play, "last trick")?;
        }

        let finished = tricks.len() == TRICKS_PER_DEAL;
        let mut next = self.clone();
        next.hands = hands;
        next.tricks = tricks;
        next.current_trick = None;
        next.leader = winner;
        next.log = log;
        if finished {
            next = next.finish()?;
        }
        Ok(next)
    }

    fn release_youngers_declarations(&self) -> Result<Deal, String> {
        let mut log = self.log.clone();
        for (amount, category, detail) in &self.younger_pending {
            log = log.record(Player::Younger, *amount, *category, detail)?;
        }
        let mut next = self.clone();
        next.log = log;
        next.younger_pending = Vec::new();
        Ok(next)
    }

    /// Score the cards, apply the pique or repique, and close the deal.
    fn finish(&self) -> Result<Deal, String> {
        let elder = self.tricks_won(Player::Elder);
        let younger = TRICKS_PER_DEAL - elder;

        let mut log = self.log.clone();
        if elder == TRICKS_PER_DEAL {
            log = log.record(Player::Elder, CAPOT_SCORE, Category::Cards, "capot")?;
        } else if younger == TRICKS_PER_DEAL {
            log = log.record(Player::Younger, CAPOT_SCORE, Category::Cards, "capot")?;
        } else if elder > younger {
            log = log.record(Player::Elder, CARDS_SCORE, Category::Cards, "the cards")?;
        } else if younger > elder {
            log = log.record(Player::Younger, CARDS_SCORE, Category::Cards, "the cards")?;
        }
        // Six each: the cards are divided and neither scores.

        let mut next = self.clone();
        next.phase = Phase::Complete;
        next.log = log.with_bonuses();
        Ok(next)
    }
}

fn suit_name(suit: Suit) -> &'static str {
    match suit.0 {
        0 => "clubs",
        1 => "diamonds",
        2 => "hearts",
        _ => "spades",
    }
}

/// Deal from an explicit ordering of the pack.
///
/// The first twelve cards go to elder, the next twelve to younger, and the
/// last eight form the talon. Real dealing alternates in twos or threes, but
/// only the resulting distribution matters to the rules, and a deterministic
/// order lets any deal be written down as a fixture.
///
/// There is deliberately no shuffling entry point here. No two languages share
/// a random number generator, so every fixture is written against this.
pub fn deal_from(cards: &[Card]) -> Result<Deal, String> {
    let mut seen = 0u32;
    for card in cards {
        seen |= 1 << card.0;
    }
    if cards.len() != 32 || seen.count_ones() != 32 {
        return Err(format!(
            "a deal needs the 32 distinct cards of the piquet pack, got {} ({} distinct)",
            cards.len(),
            seen.count_ones()
        ));
    }

    let elder = Hand::of(&cards[..HAND_SIZE])?;
    let younger = Hand::of(&cards[HAND_SIZE..HAND_SIZE * 2])?;
    let talon = cards[HAND_SIZE * 2..].to_vec();

    let mut log = ScoreLog::new();
    for (player, hand) in [(Player::Elder, elder), (Player::Younger, younger)] {
        if is_carte_blanche(hand) {
            // Announced as soon as it is noticed, so it is logged before
            // anything else -- which is also where Law 67 puts it.
            log = log.record(
                player,
                CARTE_BLANCHE_SCORE,
                Category::CarteBlanche,
                "carte blanche",
            )?;
        }
    }

    Ok(Deal {
        hands: [elder, younger],
        discards: [Hand::EMPTY, Hand::EMPTY],
        talon,
        talon_taken: 0,
        phase: Phase::ElderExchange,
        log,
        elder_declaration: None,
        results: Vec::new(),
        younger_pending: Vec::new(),
        tricks: Vec::new(),
        current_trick: None,
        leader: Player::Elder,
    })
}
