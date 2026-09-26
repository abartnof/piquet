//! What each player is allowed to know.
//!
//! This is the most load-bearing module in the project. Agents read the game
//! *only* through a [`View`]: if it leaks, every strength measurement taken
//! through it is meaningless, and if it is too strict a bot forgets things the
//! rules expressly permit it to consult.
//!
//! It has leaked three times in this engine's history, so the golden vectors
//! check an **invariant** rather than a field list: every card of the
//! opponent's hand must either lie inside [`View::unseen`] -- unaccounted for
//! -- or be one this player legitimately watched them take.
//!
//! Three asymmetries matter more than any other. Elder may look at all five of
//! his talon cards even when he takes fewer, so he always knows five cards
//! younger does not. If he takes fewer than five, younger draws from the top of
//! what is left -- which begins inside his five -- so he also *watches her
//! take* cards he has already read. And each player "keeps his discards by him,
//! and may refer to them during play" (Cavendish), so consulting your own
//! discards is not cheating.

use crate::cards::{Card, Hand};
use crate::declarations::{Announcement, Combination};
use crate::partie::Standing;
use crate::rules::{Deal, Phase, Trick, ELDER_MAX_EXCHANGE};
use crate::scoring::{Category, Player, ScoreLog};

/// One player's legal knowledge of a deal in progress.
///
/// Note what is deliberately *absent*: the opponent's `Declaration` objects.
/// An earlier version handed over the whole `CategoryResult`, which carries the
/// suits of every claim -- including claims that were beaten and so never had
/// to be shown. `heard` and `seen` replace it, and they are not the same thing:
/// you always hear the shape, and you only get to see the cards of a
/// combination that scored or tied.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct View {
    pub me: Player,
    pub phase: Phase,
    pub hand: Hand,
    pub my_discards: Hand,
    /// Talon cards this player has legitimately seen.
    pub talon_seen: Vec<Card>,
    /// Talon cards this player read and then watched the opponent draw, and
    /// which the opponent must therefore still be holding. Certain knowledge,
    /// and the only certain knowledge of the other hand this game ever gives.
    pub watched_them_take: Hand,
    pub talon_remaining: usize,
    pub exchange_limit: usize,
    /// How each settled category came out. Public: the scores are called aloud.
    pub outcomes: Vec<(Category, Option<Player>)>,
    /// What the opponent said aloud in settled categories -- always public,
    /// but it names a shape ("point of five"), never a suit.
    pub heard: Vec<Announcement>,
    /// What this player has said aloud: `heard`, from the other chair. Their
    /// own words, so nothing new -- but inference needs them, because what
    /// the opponent's silence means depends on what it answered.
    pub said: Vec<Announcement>,
    /// The opponent's combinations that had to be exposed, because they scored
    /// or because the category was equal.
    pub seen: Vec<Combination>,
    /// The opponent's declaration waiting on this player's answer, if any.
    pub awaiting_answer: Option<Announcement>,
    /// Where the partie stands, from this player's side. `None` for a deal
    /// played on its own.
    pub partie: Option<Standing>,
    /// Scores are called aloud, so the whole log is public.
    pub log: ScoreLog,
    pub tricks: Vec<Trick>,
    pub current_trick: Option<Trick>,
    pub legal_plays: Hand,
    pub to_act: bool,
}

impl View {
    pub fn opponent(&self) -> Player {
        self.me.opponent()
    }

    /// Every card this player cannot account for.
    ///
    /// These are the cards that might be in the opponent's hand, in their
    /// discards, or still in the talon. Enumerating the opponent's possible
    /// holdings starts here -- but does not end here, because
    /// `watched_them_take` is accounted for and in the opponent's hand at once.
    ///
    /// In Python this needed `& 0xFFFFFFFF` to unsign, which JavaScript cannot
    /// do at all. On a `u32` the complement is simply correct.
    pub fn unseen(&self) -> Hand {
        let mut seen = self.hand.0 | self.my_discards.0;
        for card in &self.talon_seen {
            seen |= 1 << card.0;
        }
        for trick in self.tricks.iter().chain(self.current_trick.iter()) {
            seen |= 1 << trick.led.0;
            if let Some(followed) = trick.followed {
                seen |= 1 << followed.0;
            }
        }
        Hand(!seen)
    }
}

/// The talon cards this player has legitimately looked at.
///
/// Elder sees all five of his, whether or not he takes them: "if he exchanges
/// fewer than five, he can look at the remainder of the five." Younger sees
/// only what she actually drew.
fn talon_seen(deal: &Deal, player: Player) -> Vec<Card> {
    let elder_took = deal.discard_of(Player::Elder).len() as usize;
    let younger_took = deal.discard_of(Player::Younger).len() as usize;

    if player == Player::Elder {
        if deal.phase == Phase::ElderExchange {
            return Vec::new();
        }
        return deal.talon[..ELDER_MAX_EXCHANGE.min(deal.talon.len())].to_vec();
    }
    if matches!(deal.phase, Phase::ElderExchange | Phase::YoungerExchange) {
        return Vec::new();
    }
    deal.talon[elder_took..elder_took + younger_took].to_vec()
}

/// Every card this player has already put on the table.
fn played_by(deal: &Deal, player: Player) -> Hand {
    let mut played = 0u32;
    for trick in deal.tricks.iter().chain(deal.current_trick.iter()) {
        if trick.leader == player {
            played |= 1 << trick.led.0;
        } else if let Some(followed) = trick.followed {
            played |= 1 << followed.0;
        }
    }
    Hand(played)
}

/// Talon cards this player read and then watched the opponent draw.
///
/// Only elder ever has any. He looks at all five of his whether he takes them
/// or not; if he exchanges fewer, younger draws from the top of what is left,
/// which begins inside his five. She discards *before* she draws, so a card she
/// takes in front of him cannot have been thrown away and is certainly in her
/// hand. What comes back is what she is holding *now*, so cards she has since
/// played drop out of it.
fn watched_them_take(deal: &Deal, player: Player) -> Hand {
    if player != Player::Elder {
        return Hand::EMPTY;
    }
    let elder_took = deal.discard_of(Player::Elder).len() as usize;
    let younger_took = deal.discard_of(Player::Younger).len() as usize;
    let end = ELDER_MAX_EXCHANGE.min(elder_took + younger_took);
    if end <= elder_took {
        return Hand::EMPTY;
    }
    let overlap = &deal.talon[elder_took..end];
    let held = Hand::of(overlap).unwrap_or(Hand::EMPTY);
    held.without(played_by(deal, Player::Younger))
}

fn to_act(deal: &Deal, player: Player) -> bool {
    match deal.phase {
        Phase::ElderExchange => player == Player::Elder,
        Phase::YoungerExchange => player == Player::Younger,
        _ => {
            if let Some(declarer) = deal.to_declare() {
                return player == declarer;
            }
            if let Some(mover) = deal.to_play() {
                return player == mover;
            }
            false
        }
    }
}

/// Whether this player has named their combinations yet.
///
/// Elder names and scores his as the dialogue goes along. Younger names none of
/// hers until elder has led to the first trick -- so for the whole of the
/// sequence and set dialogue, and for the card he chooses to lead, elder knows
/// only whether each of her holdings beat his.
fn has_spoken(deal: &Deal, player: Player) -> bool {
    player == Player::Elder || deal.elder_has_led()
}

fn heard(deal: &Deal, player: Player) -> Vec<Announcement> {
    let opponent = player.opponent();
    if !has_spoken(deal, opponent) {
        return Vec::new();
    }
    deal.results
        .iter()
        .filter_map(|r| r.announcement_of(opponent))
        .collect()
}

/// The opponent's combinations this player is entitled to have looked at.
///
/// Nothing can be asked for before it has been declared, so younger shows elder
/// nothing until he has led.
fn seen(deal: &Deal, player: Player) -> Vec<Combination> {
    let opponent = player.opponent();
    if !has_spoken(deal, opponent) {
        return Vec::new();
    }
    deal.results
        .iter()
        .flat_map(|r| r.shown(opponent))
        .collect()
}

/// Elder's declaration, heard by younger before she must answer it.
///
/// She learns the shape -- "point of five" -- and neither the suit nor the pip
/// total, which is what makes answering "good" or "not good" a decision rather
/// than a lookup.
fn awaiting_answer(deal: &Deal, player: Player) -> Option<Announcement> {
    if deal.to_declare() != Some(player) || player != Player::Younger {
        return None;
    }
    let declaration = deal.elder_declaration.as_ref()?;
    let category = deal.declaring_category()?;
    Some(declaration.announce(category)?.shape())
}

/// Everything `player` may legally know about this deal, and nothing else.
///
/// `standing` is given from **elder's** side of the table, because that is how
/// `Partie::standing` reports it, and is flipped here for younger.
pub fn view_for(deal: &Deal, player: Player, standing: Option<Standing>) -> View {
    View {
        me: player,
        phase: deal.phase,
        hand: deal.hand_of(player),
        my_discards: deal.discard_of(player),
        talon_seen: talon_seen(deal, player),
        watched_them_take: watched_them_take(deal, player),
        talon_remaining: deal.talon_remaining(),
        exchange_limit: deal.exchange_limit(player),
        outcomes: deal
            .results
            .iter()
            .map(|r| (r.category, r.winner()))
            .collect(),
        heard: heard(deal, player),
        said: heard(deal, player.opponent()),
        seen: seen(deal, player),
        awaiting_answer: awaiting_answer(deal, player),
        partie: match (standing, player) {
            (None, _) => None,
            (Some(s), Player::Elder) => Some(s),
            (Some(s), Player::Younger) => Some(s.reversed()),
        },
        log: deal.log.clone(),
        tricks: deal.tricks.clone(),
        current_trick: deal.current_trick,
        legal_plays: if deal.to_play() == Some(player) {
            deal.legal_plays(Some(player))
        } else {
            Hand::EMPTY
        },
        to_act: to_act(deal, player),
    }
}
