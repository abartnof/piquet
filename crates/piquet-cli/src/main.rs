//! A table a person can sit down at.
//!
//! `piquet` deals you a partie of six against a named opponent. The engine
//! lives in `piquet-core`; this is only the furniture, and it is deliberately
//! plain -- `docs/DESIGN.md` defers the real interface and says basic graphics
//! are acceptable until then.

mod render;

use std::io::{self, BufRead, Write};

use piquet_core::agents::Agent;
use piquet_core::cards::{Card, Hand};
use piquet_core::chances::{chance_of_the_rubicon, in_words};
use piquet_core::declarations::Declaration;
use piquet_core::observation::View;
use piquet_core::opponents::{opponent, seat};
use piquet_core::options::declaration_options;
use piquet_core::partie::{Partie, Side};
use piquet_core::play::play_deal;
use piquet_core::rng::Rng;
use piquet_core::rules::{deal_from, Deal};
use piquet_core::scoring::{Category, Player};

/// Where the table reads and writes: the terminal, or in the tests a script
/// and a buffer.
struct Table {
    input: Box<dyn BufRead>,
    output: Box<dyn Write>,
    /// What running out of input means. At the terminal, walking away.
    leave: fn() -> !,
}

impl Table {
    fn say(&mut self, line: &str) {
        writeln!(self.output, "{line}").ok();
    }

    fn ask(&mut self, prompt: &str) -> String {
        write!(self.output, "{prompt}").ok();
        self.output.flush().ok();
        let mut line = String::new();
        if self.input.read_line(&mut line).unwrap_or(0) == 0 {
            writeln!(self.output).ok();
            (self.leave)();
        }
        line.trim().to_string()
    }
}

/// End of input at the terminal: the person has walked away from the table.
fn walk_away() -> ! {
    std::process::exit(0)
}

/// The human, as an [`Agent`]. The engine cannot tell the difference, which is
/// what makes the training mode possible later.
struct HumanAgent {
    table: Table,
    opponent: String,
}

impl HumanAgent {
    fn show(&mut self, view: &View, legal: Option<Hand>) {
        self.table.say("");
        self.table.say(&render::hand(view.hand, legal));
    }
}

impl Agent for HumanAgent {
    fn name(&self) -> &str {
        "you"
    }

    fn exchange(&mut self, view: &View) -> Hand {
        let limit = view.exchange_limit;
        self.show(view, None);
        let combos = render::combinations(view.hand);
        self.table.say(&format!("    {combos}"));
        self.table.say(&format!(
            "\n  name 1 to {limit} cards to throw, and draw as many back \
             — like {}",
            render::for_example(view.hand)
        ));
        loop {
            let raw = self.table.ask("  discard: ").replace(',', " ");
            let tokens: Vec<&str> = raw.split_whitespace().collect();
            if tokens.is_empty() || tokens.len() > limit {
                self.table.say(&format!(
                    "  between 1 and {limit} cards, and at least one is compulsory"
                ));
                continue;
            }
            let parsed: Result<Vec<Card>, _> = tokens.iter().map(|t| Card::parse(t)).collect();
            let Ok(cards) = parsed else {
                self.table.say(&format!(
                    "  name each card by rank and suit, like {}",
                    render::for_example(view.hand)
                ));
                continue;
            };
            let Ok(discard) = Hand::of(&cards) else {
                self.table.say("  each card once");
                continue;
            };
            if !discard.without(view.hand).is_empty() {
                self.table.say("  you do not hold all of those");
                continue;
            }
            return discard;
        }
    }

    fn declare(&mut self, view: &View, category: Category) -> Declaration {
        let full = Declaration::full(view.hand, category);
        self.show(view, None);
        if let Some(heard) = view.awaiting_answer {
            self.table
                .say(&format!("    {} calls {}", self.opponent, heard.spoken()));
        }
        if full.is_empty() {
            self.table.say(&format!(
                "    you have no {} to call",
                category.name().to_lowercase().replace('_', " ")
            ));
            return full;
        }

        let options = declaration_options(view.hand, category);
        self.table.say(&format!(
            "\n  {}:",
            category.name().to_lowercase().replace('_', " ")
        ));
        for (number, option) in options.iter().enumerate() {
            let label = if option.is_empty() {
                "say nothing, and give up the category".to_string()
            } else if *option == full {
                format!(
                    "call {} — {} points if it is good",
                    option.describe(),
                    option.score()
                )
            } else {
                format!("call only {} — sinking the rest", option.describe())
            };
            self.table.say(&format!("    {}) {label}", number + 1));
        }
        loop {
            let raw = self.table.ask("  which: ");
            let raw = if raw.is_empty() { "1".to_string() } else { raw };
            if let Ok(choice) = raw.parse::<usize>() {
                if (1..=options.len()).contains(&choice) {
                    return options[choice - 1].clone();
                }
            }
            self.table
                .say(&format!("  a number from 1 to {}", options.len()));
        }
    }

    fn play(&mut self, view: &View) -> Card {
        let legal = view.legal_plays;
        self.show(view, Some(legal));
        if let Some(line) = render::trick(view, "you", &self.opponent) {
            self.table.say(&line);
        }
        if legal != view.hand {
            self.table
                .say("    the bracketed cards are the ones you may play");
        }
        loop {
            let raw = self.table.ask("  your card: ");
            let Ok(card) = Card::parse(&raw) else {
                self.table.say(&format!(
                    "  name a card by rank and suit, like {}",
                    render::for_example(view.hand)
                ));
                continue;
            };
            if !view.hand.holds(card) {
                self.table.say("  you do not hold that one");
                continue;
            }
            if !legal.holds(card) {
                let led = view
                    .current_trick
                    .expect("a trick is in progress")
                    .led
                    .suit();
                self.table.say(&format!(
                    "  you must follow {} while you can",
                    render::suit_name(led)
                ));
                continue;
            }
            return card;
        }
    }
}

fn shuffled(rng: &mut Rng) -> Vec<Card> {
    let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
    rng.shuffle(&mut pack);
    pack
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let level: u32 = args
        .iter()
        .position(|a| a == "--level")
        .and_then(|i| args.get(i + 1))
        .and_then(|v| v.parse().ok())
        .unwrap_or(3);
    let seed: u32 = args
        .iter()
        .position(|a| a == "--seed")
        .and_then(|i| args.get(i + 1))
        .and_then(|v| v.parse().ok())
        .unwrap_or_else(|| {
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.subsec_nanos())
                .unwrap_or(1674)
        });

    let who = opponent(level);
    // No proper names at the table: the machine is "your opponent".
    let (opponent_name, gloss) = ("your opponent", who.gloss);
    let mut rng = Rng::seeded(seed);

    let table = Table {
        input: Box::new(io::stdin().lock()),
        output: Box::new(io::stdout()),
        leave: walk_away,
    };
    println!("\n  Piquet — a partie of six deals");
    println!("  your opponent {gloss}");
    println!("  (seed {seed}; pass --seed to replay, --level 1..5 to change opponent)\n");

    let mut human = HumanAgent {
        table,
        opponent: opponent_name.to_string(),
    };
    let mut machine = seat(who.level, &mut rng);

    // The human is side A and deals first, so the machine is elder in deal one
    // -- the dealer is not elder.
    let mut partie = Partie::new(Side::A);
    while !partie.complete() {
        let number = partie.number();
        let elder_side = partie.elder();
        let standing = partie.standing();

        println!("\n  ── deal {number} of six ──");
        let odds = if number > 1 {
            let chance = chance_of_the_rubicon(&partie, Side::A);
            Some((chance, in_words(chance)))
        } else {
            None
        };
        // `Partie::standing` reports from ELDER's chair, and elder alternates
        // every deal -- so showing it unflipped labelled the human's score as
        // the opponent's on every second deal. The engine wants elder's view
        // (`view_for` flips it for younger); the table wants the human's.
        let mine = if elder_side == Side::A {
            standing
        } else {
            standing.reversed()
        };
        println!("{}", render::standing(mine, odds));
        println!(
            "  you are {}",
            if elder_side == Side::A {
                "elder — you lead"
            } else {
                "younger — you deal"
            }
        );

        let pack = shuffled(&mut rng);
        let deal = match deal_from(&pack) {
            Ok(deal) => deal,
            Err(why) => {
                eprintln!("  the pack was wrong: {why}");
                return;
            }
        };

        let finished: Deal = {
            let (elder, younger): (&mut dyn Agent, &mut dyn Agent) = match elder_side {
                Side::A => (&mut human, &mut machine),
                Side::B => (&mut machine, &mut human),
            };
            match play_deal(deal, elder, younger, Some(standing)) {
                Ok((deal, _)) => deal,
                Err(why) => {
                    eprintln!("  the deal could not be finished: {why}");
                    return;
                }
            }
        };

        let (my_seat, their_seat) = match elder_side {
            Side::A => (Player::Elder, Player::Younger),
            Side::B => (Player::Younger, Player::Elder),
        };
        println!("\n  the deal is over:");
        println!(
            "{}",
            render::events(&finished.log, my_seat, "you", opponent_name)
        );
        println!(
            "\n    you {}  ·  {opponent_name} {}",
            finished.log.total(my_seat),
            finished.log.total(their_seat)
        );

        partie = match partie.record_scores(
            finished.log.total(Player::Elder),
            finished.log.total(Player::Younger),
        ) {
            Ok(partie) => partie,
            Err(why) => {
                eprintln!("  {why}");
                return;
            }
        };
    }

    let (mine, theirs) = partie.totals();
    let settlement = partie.settlement().expect("a complete partie settles");
    println!("\n  ── the partie ──");
    println!("    you {mine}  ·  {opponent_name} {theirs}");
    match settlement.winner {
        None => println!("    drawn."),
        Some(Side::A) => println!(
            "    you win, and {opponent_name} pays {}{}",
            settlement.points,
            if settlement.rubicon {
                " — rubiconed, so the sum and not the difference"
            } else {
                ""
            }
        ),
        Some(Side::B) => println!(
            "    your opponent wins, and you pay {}{}",
            settlement.points,
            if settlement.rubicon {
                " — you were rubiconed, so the sum and not the difference"
            } else {
                ""
            }
        ),
    }
    println!();
}

#[cfg(test)]
mod tests {
    //! The part of a table that needs testing: turning a person's typing into
    //! a legal move, and refusing -- in words -- what is not one. The console
    //! is a script and a buffer, as the Python's terminal tests have it.

    use super::*;
    use piquet_core::observation::view_for;
    use piquet_core::rules::Phase;
    use std::cell::RefCell;
    use std::io::Cursor;
    use std::rc::Rc;

    #[derive(Clone, Default)]
    struct Shown(Rc<RefCell<Vec<u8>>>);

    impl Write for Shown {
        fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
            self.0.borrow_mut().extend_from_slice(bytes);
            Ok(bytes.len())
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    impl Shown {
        fn text(&self) -> String {
            String::from_utf8(self.0.borrow().clone()).unwrap()
        }
    }

    fn ran_out() -> ! {
        panic!("the script ran out of answers")
    }

    /// A human at a scripted console: each line is one answer typed.
    fn human(lines: &[&str]) -> (HumanAgent, Shown) {
        let shown = Shown::default();
        let script = lines.iter().map(|l| format!("{l}\n")).collect::<String>();
        let table = Table {
            input: Box::new(Cursor::new(script)),
            output: Box::new(shown.clone()),
            leave: ran_out,
        };
        let agent = HumanAgent {
            table,
            opponent: "your opponent".to_string(),
        };
        (agent, shown)
    }

    fn hand(text: &str) -> Hand {
        Hand::parse(text).unwrap()
    }

    /// A deal wound past the exchange holding exactly these hands, built
    /// directly because any exchange would change them (the Python's
    /// `tests.helpers.declaring`).
    fn declaring(elder: &str, younger: &str) -> Deal {
        let (e, y) = (hand(elder), hand(younger));
        let rest: Vec<Card> = (0u8..32)
            .map(Card)
            .filter(|c| !e.holds(*c) && !y.holds(*c))
            .collect();
        let pack: Vec<Card> = e.cards().chain(y.cards()).chain(rest).collect();
        let mut deal = deal_from(&pack).unwrap();
        deal.talon_taken = deal.talon.len();
        deal.phase = Phase::DeclarePoint;
        deal
    }

    /// Both players sink every category: on to the play.
    fn skip_declarations(mut deal: Deal) -> Deal {
        while let Some(player) = deal.to_declare() {
            deal = deal.declare(player, Declaration::sink()).unwrap();
        }
        deal
    }

    const ELDER: &str = "AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C";
    const YOUNGER: &str = "JS TS 9S JH TH 9H AD KD QD AC KC QC";
    const LONG: &str = "AS KS QS JS TS 9S 8S 7S AH KH QH JH";
    const OTHER: &str = "AD KD QD JD TD 9D 8D AC KC QC JC TC";

    fn card(code: &str) -> Card {
        Card::parse(code).unwrap()
    }

    // -- the play --

    #[test]
    fn the_person_plays_a_card_by_naming_it() {
        let deal = skip_declarations(declaring(ELDER, YOUNGER));
        let (mut you, _) = human(&["as"]);
        assert_eq!(you.play(&view_for(&deal, Player::Elder, None)), card("AS"));
    }

    #[test]
    fn a_card_that_does_not_follow_is_refused_and_the_person_asked_again() {
        let deal = skip_declarations(declaring(ELDER, YOUNGER));
        let deal = deal.play(Player::Elder, card("AS")).unwrap();
        let (mut you, shown) = human(&["ad", "js"]); // a diamond, while spades were led
        assert_eq!(
            you.play(&view_for(&deal, Player::Younger, None)),
            card("JS")
        );
        assert!(
            shown
                .text()
                .contains("you must follow spades while you can"),
            "{}",
            shown.text()
        );
    }

    #[test]
    fn nonsense_is_refused_without_crashing() {
        let deal = skip_declarations(declaring(ELDER, YOUNGER));
        let (mut you, shown) = human(&["", "zz", "6H", "AS"]);
        assert_eq!(you.play(&view_for(&deal, Player::Elder, None)), card("AS"));
        assert_eq!(
            shown.text().matches("name a card by rank and suit").count(),
            3
        );
    }

    #[test]
    fn a_card_you_do_not_hold_is_refused() {
        let deal = skip_declarations(declaring(ELDER, YOUNGER));
        let (mut you, shown) = human(&["JS", "KS"]);
        assert_eq!(you.play(&view_for(&deal, Player::Elder, None)), card("KS"));
        assert!(shown.text().contains("you do not hold that one"));
    }

    #[test]
    fn the_cards_you_may_play_are_marked_only_when_the_choice_is_narrowed() {
        let deal = skip_declarations(declaring(ELDER, YOUNGER));
        let (mut you, shown) = human(&["AS"]);
        you.play(&view_for(&deal, Player::Elder, None));
        assert!(!shown.text().contains("bracketed"));

        let deal = deal.play(Player::Elder, card("AS")).unwrap();
        let (mut you, shown) = human(&["JS"]);
        you.play(&view_for(&deal, Player::Younger, None));
        assert!(shown
            .text()
            .contains("the bracketed cards are the ones you may play"));
    }

    // -- the exchange --

    #[test]
    fn the_person_discards_by_naming_cards_with_or_without_commas() {
        let deal = deal_from(&(0u8..32).map(Card).collect::<Vec<_>>()).unwrap();
        let held: Vec<String> = deal
            .hand_of(Player::Elder)
            .cards()
            .map(|c| c.code())
            .collect();
        let (mut you, _) = human(&[&format!("{}, {} {}", held[0], held[1], held[2])]);
        let discard = you.exchange(&view_for(&deal, Player::Elder, None));
        assert_eq!(discard, hand(&held[..3].join(" ")));
    }

    #[test]
    fn a_discard_of_the_wrong_size_is_refused() {
        let deal = deal_from(&(0u8..32).map(Card).collect::<Vec<_>>()).unwrap();
        let held: Vec<String> = deal
            .hand_of(Player::Elder)
            .cards()
            .map(|c| c.code())
            .collect();
        let (mut you, shown) = human(&[&held[..6].join(" "), "", &held[..3].join(" ")]);
        let discard = you.exchange(&view_for(&deal, Player::Elder, None));
        assert_eq!(discard.len(), 3);
        assert_eq!(shown.text().matches("between 1 and 5 cards").count(), 2);
    }

    #[test]
    fn a_discard_is_refused_for_each_way_it_can_be_wrong() {
        let deal = deal_from(&(0u8..32).map(Card).collect::<Vec<_>>()).unwrap();
        let held: Vec<String> = deal
            .hand_of(Player::Elder)
            .cards()
            .map(|c| c.code())
            .collect();
        let theirs: String = deal.hand_of(Player::Younger).cards().next().unwrap().code();
        let (mut you, shown) = human(&[
            "zz",                                // not a card
            &format!("{} {}", held[0], held[0]), // the same card twice
            &format!("{} {theirs}", held[0]),    // one they do not hold
            &held[0].clone(),
        ]);
        let discard = you.exchange(&view_for(&deal, Player::Elder, None));
        assert_eq!(discard.len(), 1);
        let text = shown.text();
        assert!(text.contains("name each card by rank and suit"), "{text}");
        assert!(text.contains("each card once"), "{text}");
        assert!(text.contains("you do not hold all of those"), "{text}");
    }

    // -- declaring --

    #[test]
    fn declaring_offers_the_whole_holding_and_the_sink() {
        let deal = declaring(LONG, OTHER);
        let (mut you, shown) = human(&["1"]);
        let called = you.declare(&view_for(&deal, Player::Elder, None), Category::Point);
        assert_eq!(called.score(), 8);
        assert!(shown.text().contains("say nothing"));
    }

    #[test]
    fn an_empty_answer_calls_in_full() {
        let deal = declaring(LONG, OTHER);
        let (mut you, _) = human(&[""]);
        let called = you.declare(&view_for(&deal, Player::Elder, None), Category::Point);
        assert_eq!(called, Declaration::full(hand(LONG), Category::Point));
    }

    #[test]
    fn a_player_may_choose_to_sink() {
        let deal = declaring(LONG, OTHER);
        let (mut you, _) = human(&["2"]);
        let called = you.declare(&view_for(&deal, Player::Elder, None), Category::Point);
        assert_eq!(called, Declaration::sink());
    }

    #[test]
    fn understating_is_offered_because_it_is_the_heart_of_the_game() {
        let deal = declaring(LONG, OTHER);
        let (mut you, _) = human(&["3"]);
        let called = you.declare(&view_for(&deal, Player::Elder, None), Category::Point);
        assert!(
            called.score() > 0 && called.score() < 8,
            "{}",
            called.score()
        );
        assert!(called.claims.iter().all(|c| c.is_supported_by(hand(LONG))));
    }

    #[test]
    fn a_choice_that_is_not_on_the_list_is_refused() {
        let deal = declaring(LONG, OTHER);
        let (mut you, shown) = human(&["0", "99", "one", "2"]);
        let called = you.declare(&view_for(&deal, Player::Elder, None), Category::Point);
        assert_eq!(called, Declaration::sink());
        assert_eq!(shown.text().matches("a number from 1 to").count(), 3);
    }

    #[test]
    fn with_nothing_to_call_nothing_is_asked() {
        // No set of three or better in either hand; the script is empty, so
        // asking anything at all would run out.
        // Elder's pairs of aces, kings and queens make no set.
        let mut deal = declaring(ELDER, YOUNGER);
        while deal.declaring_category() != Some(Category::Sets) {
            deal = deal
                .declare(deal.to_declare().unwrap(), Declaration::sink())
                .unwrap();
        }
        let (mut you, shown) = human(&[]);
        let player = deal.to_declare().unwrap();
        let called = you.declare(&view_for(&deal, player, None), Category::Sets);
        assert!(called.is_empty());
        assert!(
            shown.text().contains("you have no sets to call"),
            "{}",
            shown.text()
        );
    }

    #[test]
    fn younger_hears_what_elder_called() {
        let deal = declaring(LONG, OTHER);
        let deal = deal
            .declare(
                Player::Elder,
                Declaration::full(hand(LONG), Category::Point),
            )
            .unwrap();
        let (mut you, shown) = human(&["1"]);
        you.declare(&view_for(&deal, Player::Younger, None), Category::Point);
        assert!(
            shown.text().contains("your opponent calls"),
            "{}",
            shown.text()
        );
    }

    // -- walking away --

    #[test]
    #[should_panic(expected = "the script ran out of answers")]
    fn running_out_of_input_leaves_the_table() {
        let deal = skip_declarations(declaring(ELDER, YOUNGER));
        let (mut you, _) = human(&[]);
        you.play(&view_for(&deal, Player::Elder, None));
    }
}
