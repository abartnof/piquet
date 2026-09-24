//! Drawing the table.
//!
//! One rule governs all of it: **the display and the input are the same
//! language.** An earlier version of the Python drew ranks alone under a suit
//! symbol -- `♠  K J 7` -- which is prettier and, the first person to sit down
//! at it discovered, unusable: the table spoke in symbols and the prompt
//! wanted letters, and nothing anywhere said how to get from one to the other.
//! Every card here is drawn as the code you would type to name it.

use piquet_core::cards::{Card, Hand, Suit};
use piquet_core::combos::{best_point, is_carte_blanche, sequences, sets};
use piquet_core::observation::View;
use piquet_core::partie::Standing;
use piquet_core::scoring::{Player, ScoreLog};

/// Spades, hearts, diamonds, clubs -- the order a player expects to read.
const DISPLAY_ORDER: [Suit; 4] = [Suit::SPADES, Suit::HEARTS, Suit::DIAMONDS, Suit::CLUBS];

const SUIT_NAMES: [&str; 4] = ["clubs", "diamonds", "hearts", "spades"];

pub fn suit_name(suit: Suit) -> &'static str {
    SUIT_NAMES[suit.0 as usize]
}

/// A hand laid out by suit, highest first, legal plays in brackets.
///
/// All four suits are always drawn, a void as a dash. Four fixed rows keep the
/// layout still, so the eye learns where hearts live instead of re-finding
/// them every trick; and a void is a fact you *act* on rather than an absence,
/// because it is exactly what lets you throw whatever you like.
pub fn hand(hand: Hand, legal: Option<Hand>) -> String {
    // Nothing is narrowed, so nothing is worth marking.
    let legal = legal.filter(|l| *l != hand);
    let mut rows = Vec::new();
    for suit in DISPLAY_ORDER {
        let ranks = hand.ranks_in(suit);
        let drawn = if ranks.is_empty() {
            "   —".to_string()
        } else {
            ranks
                .iter()
                .map(|rank| {
                    let card = Card::new(*rank, suit);
                    if legal.is_some_and(|l| l.holds(card)) {
                        format!("[{}]", card.code())
                    } else {
                        format!(" {} ", card.code())
                    }
                })
                .collect::<Vec<_>>()
                .join(" ")
        };
        rows.push(format!("    {} {}", suit.symbol(), drawn));
    }
    rows.join("\n")
}

/// What the hand is worth in declarations, for a player deciding what to keep.
pub fn combinations(held: Hand) -> String {
    let mut parts = Vec::new();
    if let Some(point) = best_point(held) {
        parts.push(format!(
            "point of {} ({}) in {}",
            point.length,
            point.pip_value,
            suit_name(point.suit)
        ));
    }
    for sequence in sequences(held) {
        parts.push(format!(
            "{} to the {} in {}",
            sequence.name(),
            sequence.top.name(),
            suit_name(sequence.suit)
        ));
    }
    for held_set in sets(held) {
        parts.push(format!("{} of {}s", held_set.name(), held_set.rank.name()));
    }
    if is_carte_blanche(held) {
        parts.push("carte blanche — no court card at all".to_string());
    }
    if parts.is_empty() {
        "nothing to call".to_string()
    } else {
        parts.join(", ")
    }
}

/// An example card from the hand, so the prompt can show the form it wants.
pub fn for_example(held: Hand) -> String {
    held.cards()
        .next()
        .map_or_else(|| "AS".to_string(), |c| c.code())
}

pub fn events(log: &ScoreLog, me: Player, my_name: &str, their_name: &str) -> String {
    log.events
        .iter()
        .map(|event| {
            let who = if event.player == me {
                my_name
            } else {
                their_name
            };
            let what = if event.detail.is_empty() {
                event.category.name().to_lowercase().replace('_', " ")
            } else {
                event.detail.clone()
            };
            format!("    {who} scores {} for {what}", event.amount)
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// Where the partie stands, and which of the two games the player is in.
pub fn standing(standing: Standing, odds: Option<(f64, String)>) -> String {
    let mut line = format!(
        "    you {}  ·  them {}  ·  {} deal{} left",
        standing.mine,
        standing.theirs,
        standing.deals_left,
        if standing.deals_left == 1 { "" } else { "s" }
    );
    if let Some((_, words)) = odds {
        let short = 100 - standing.mine;
        line.push_str(&format!(
            "\n    {short} more to cross the rubicon — {words}"
        ));
    }
    line
}

pub fn trick(view: &View, my_name: &str, their_name: &str) -> Option<String> {
    let trick = view.current_trick?;
    let who = if trick.leader == view.me {
        my_name
    } else {
        their_name
    };
    Some(format!("    {who} led {}", trick.led.code()))
}
