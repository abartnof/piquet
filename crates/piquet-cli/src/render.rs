//! Drawing the table.
//!
//! One rule governs all of it: **the display and the input are the same
//! language.** An earlier version of the Python drew ranks alone under a suit
//! symbol -- `♠  K J 7` -- which is prettier and, the first person to sit down
//! at it discovered, unusable: the table spoke in symbols and the prompt
//! wanted letters, and nothing anywhere said how to get from one to the other.
//! Every card here is drawn as the code you would type to name it.

use piquet_core::cards::{Card, Hand, Suit};
use piquet_core::combos::holdings;
use piquet_core::observation::View;
use piquet_core::partie::Standing;
use piquet_core::scoring::{Player, ScoreLog};

/// ANSI colour, or nothing at all.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Palette {
    pub enabled: bool,
}

/// For anything that is not a terminal, and for the tests.
pub const PLAIN: Palette = Palette { enabled: false };

impl Palette {
    /// Colour when there is somebody there to see it: off when the output is
    /// not a terminal, and off when `NO_COLOR` is set and not empty -- a
    /// convention worth honouring rather than a special case to argue about.
    pub fn detect(terminal: bool, no_color: Option<String>) -> Palette {
        if terminal && no_color.is_none_or(|v| v.is_empty()) {
            Palette { enabled: true }
        } else {
            PLAIN
        }
    }

    fn wrap(self, text: &str, code: &str) -> String {
        if self.enabled {
            format!("\x1b[{code}m{text}\x1b[0m")
        } else {
            text.to_string()
        }
    }

    /// Hearts and diamonds. Never black for the others: half the world runs
    /// a dark terminal, and the spades would vanish into it.
    pub fn red(self, text: &str) -> String {
        self.wrap(text, "31")
    }
}

fn is_red(suit: Suit) -> bool {
    suit == Suit::HEARTS || suit == Suit::DIAMONDS
}

/// Spades, hearts, diamonds, clubs -- the order a player expects to read.
const DISPLAY_ORDER: [Suit; 4] = [Suit::SPADES, Suit::HEARTS, Suit::DIAMONDS, Suit::CLUBS];

pub fn suit_name(suit: Suit) -> &'static str {
    suit.name()
}

/// A hand laid out by suit, highest first, legal plays in brackets.
///
/// All four suits are always drawn, a void as a dash. Four fixed rows keep the
/// layout still, so the eye learns where hearts live instead of re-finding
/// them every trick; and a void is a fact you *act* on rather than an absence,
/// because it is exactly what lets you throw whatever you like.
pub fn hand(hand: Hand, legal: Option<Hand>, palette: Palette) -> String {
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
        let row = format!("    {} {}", suit.symbol(), drawn);
        rows.push(if is_red(suit) { palette.red(&row) } else { row });
    }
    rows.join("\n")
}

/// What the hand is worth in declarations, for a player deciding what to keep.
pub fn combinations(held: Hand) -> String {
    let parts: Vec<String> = holdings(held).into_iter().map(|h| h.text).collect();
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
            let verb = if event.player == me {
                "score"
            } else {
                "scores"
            };
            format!("    {who} {verb} {} for {what}", event.amount)
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

pub fn trick(view: &View, my_name: &str, their_name: &str, palette: Palette) -> Option<String> {
    let trick = view.current_trick?;
    let who = if trick.leader == view.me {
        my_name
    } else {
        their_name
    };
    let led = trick.led.code();
    let led = if is_red(trick.led.suit()) {
        palette.red(&led)
    } else {
        led
    };
    Some(format!("    {who} led {led}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use piquet_core::cards::parse_card;

    /// The rule the whole module exists for, as a test rather than a comment.
    ///
    /// The Python learnt it the hard way: a hand drawn as `♠ K J 7` is
    /// prettier and unusable, because the prompt wanted `KS` and nothing said
    /// how to get from one to the other. Every token drawn here must parse
    /// back as the card it names.
    #[test]
    fn every_card_drawn_is_a_card_you_could_type() {
        let held = Hand::parse("AS KS JS TS KH QH 9H 8H KD 8D 7D KC").unwrap();
        let drawn = hand(held, None, PLAIN);
        let mut found = 0;
        for token in drawn.split_whitespace() {
            let token = token.trim_matches(|c| c == '[' || c == ']');
            // Suit symbols label the rows; everything else must be a card.
            if token.chars().count() <= 1 {
                continue;
            }
            parse_card(token)
                .unwrap_or_else(|e| panic!("drew {token:?}, which does not parse: {e}"));
            found += 1;
        }
        assert_eq!(found, 12, "every card in the hand is drawn exactly once");
    }

    #[test]
    fn all_four_suits_are_always_drawn_and_a_void_is_a_dash() {
        // Four fixed rows keep the layout still, so the eye learns where
        // hearts live instead of re-finding them every trick -- and a void is
        // a fact you act on, because it is what lets you throw anything.
        let held = Hand::parse("AS KS QS").unwrap();
        let drawn = hand(held, None, PLAIN);
        assert_eq!(drawn.lines().count(), 4, "one row per suit, always");
        assert_eq!(
            drawn.matches('—').count(),
            3,
            "the three voids are drawn as dashes"
        );
    }

    #[test]
    fn legal_plays_are_bracketed_and_nothing_else_is() {
        let held = Hand::parse("AS KS 7H 8H").unwrap();
        let legal = Hand::parse("7H 8H").unwrap();
        let drawn = hand(held, Some(legal), PLAIN);
        assert!(drawn.contains("[7H]") && drawn.contains("[8H]"));
        assert!(!drawn.contains("[AS]") && !drawn.contains("[KS]"));
    }

    #[test]
    fn nothing_is_bracketed_when_nothing_is_narrowed() {
        // Marking every card when every card is legal is noise that teaches
        // the eye to ignore the brackets.
        let held = Hand::parse("AS KS 7H").unwrap();
        assert!(!hand(held, Some(held), PLAIN).contains('['));
    }

    #[test]
    fn combinations_name_what_the_hand_is_worth() {
        let held = Hand::parse("AC KC QC JC TC AD AH AS").unwrap();
        let described = combinations(held);
        assert!(described.contains("point of 5"), "{described}");
        assert!(described.contains("quint"), "{described}");
        assert!(described.contains("quatorze of aces"), "{described}");
    }

    #[test]
    fn a_carte_blanche_is_announced_as_such() {
        let held = Hand::parse("AS TS 9S 8S 7S AH TH 9H").unwrap();
        assert!(combinations(held).contains("carte blanche"));
    }

    #[test]
    fn an_empty_hand_says_so_rather_than_drawing_nothing() {
        assert_eq!(combinations(Hand::EMPTY), "nothing to call");
    }

    #[test]
    fn the_example_offered_by_a_prompt_is_one_of_your_own_cards() {
        let held = Hand::parse("KH QH 9H").unwrap();
        let example = for_example(held);
        let card = parse_card(&example).expect("the example must parse");
        assert!(held.contains(card), "the example must be a card you hold");
    }

    // -- colour --

    #[test]
    fn the_red_suits_are_red_and_the_black_ones_are_left_alone() {
        // Never painted black: half the world runs a dark terminal, and the
        // spades would vanish into it.
        let held = Hand::parse("AS KS AH KH AD KD AC KC").unwrap();
        let lit = hand(held, None, Palette { enabled: true });
        let rows: Vec<&str> = lit.lines().collect();
        assert!(
            rows[1].contains("\x1b[31m") && rows[2].contains("\x1b[31m"),
            "hearts and diamonds"
        );
        assert!(
            !rows[0].contains('\x1b') && !rows[3].contains('\x1b'),
            "spades and clubs"
        );
    }

    #[test]
    fn nothing_is_painted_when_nobody_is_watching() {
        let held = Hand::parse("AS KS AH KH").unwrap();
        assert!(!hand(held, None, PLAIN).contains('\x1b'));
    }

    #[test]
    fn colour_is_on_only_for_a_terminal_and_never_against_no_color() {
        assert!(!Palette::detect(false, None).enabled, "not a terminal");
        assert!(Palette::detect(true, None).enabled, "a terminal");
        // NO_COLOR: a convention worth honouring rather than a special case
        // to argue about -- set and not empty, it turns colour off.
        assert!(!Palette::detect(true, Some("1".into())).enabled);
        assert!(Palette::detect(true, Some(String::new())).enabled);
    }
}
