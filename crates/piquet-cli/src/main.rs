//! A table a person can sit down at.
//!
//! `piquet` deals you a partie of six against your opponent. The engine lives
//! in `piquet-core`, and so does the session: this is a client of
//! [`piquet_core::table::Table`], as the browser's page is. It prints what the
//! session says has happened and answers what it asks -- so the terminal cuts
//! for the deal as the page does, and the same seed at the same level, cut
//! the same way, is the same partie in both. Deliberately plain:
//! `docs/DESIGN.md` defers the real interface and says basic graphics are
//! acceptable until then.

mod render;

use std::io::{self, BufRead, IsTerminal, Write};

use piquet_core::agents::Agent;
use piquet_core::cards::{Card, Hand};
use piquet_core::chances::{chance_of_the_rubicon, in_words};
use piquet_core::declarations::Declaration;
use piquet_core::observation::View;
use piquet_core::options::declaration_options;
use piquet_core::partie::Side;
use piquet_core::scoring::Category;
use piquet_core::table::{Action, Event, Prompt, Table, Who, DEEPEST_CUT, SHALLOWEST_CUT};

/// Where the table reads and writes: the terminal, or in the tests a script
/// and a buffer.
struct Console {
    input: Box<dyn BufRead>,
    output: Box<dyn Write>,
    /// What running out of input means. At the terminal, walking away.
    leave: fn() -> !,
}

impl Console {
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

/// Whoever answers the session's questions, and hears what happened: the
/// person at the terminal, or in the tests a machine in their chair.
trait Seat: Agent {
    fn say(&mut self, line: &str);
    fn cut(&mut self) -> usize;
    fn choose_dealer(&mut self) -> Who;
    fn next_deal(&mut self);
}

/// The human, as an [`Agent`]. The engine cannot tell the difference, which is
/// what makes the training mode possible later.
struct HumanAgent {
    console: Console,
    opponent: String,
    palette: render::Palette,
}

impl HumanAgent {
    fn show(&mut self, view: &View, legal: Option<Hand>) {
        self.console.say("");
        self.console
            .say(&render::hand(view.hand, legal, self.palette));
    }
}

impl Seat for HumanAgent {
    fn say(&mut self, line: &str) {
        self.console.say(line);
    }

    /// Cut for the deal: how many cards to lift. Cutting is the person's own
    /// act if they want it, and not a chore if they do not (the user: "it
    /// should be optional to actually pick a card") -- an empty answer cuts
    /// the middle of the pack.
    fn cut(&mut self) -> usize {
        self.console.say(&format!(
            "\n  cut for the deal: lift {SHALLOWEST_CUT} to {DEEPEST_CUT} cards \
             — the higher card shown chooses who deals first"
        ));
        loop {
            let raw = self.console.ask("  lift (enter to cut the middle): ");
            if raw.is_empty() {
                return 16;
            }
            match raw.parse::<usize>() {
                Ok(n) if (SHALLOWEST_CUT..=DEEPEST_CUT).contains(&n) => return n,
                _ => self.console.say(&format!(
                    "  a number from {SHALLOWEST_CUT} to {DEEPEST_CUT}: at least two lifted, and two left"
                )),
            }
        }
    }

    /// The person cut higher: who deals first?
    fn choose_dealer(&mut self) -> Who {
        self.console.say(&format!(
            "\n  who deals first?\n    1) you — it makes you elder in the sixth deal, when it matters most\n    2) {}",
            self.opponent
        ));
        loop {
            match self.console.ask("  which: ").as_str() {
                "" | "1" => return Who::You,
                "2" => return Who::Them,
                _ => self.console.say("  1 or 2"),
            }
        }
    }

    /// Between deals: a pause, so the deal's ending can be read.
    fn next_deal(&mut self) {
        self.console.ask("\n  enter for the next deal: ");
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
        self.console.say(&format!("    {combos}"));
        self.console.say(&format!(
            "\n  name 1 to {limit} cards to throw, and draw as many back \
             — like {}",
            render::for_example(view.hand)
        ));
        loop {
            let raw = self.console.ask("  discard: ").replace(',', " ");
            let tokens: Vec<&str> = raw.split_whitespace().collect();
            if tokens.is_empty() || tokens.len() > limit {
                self.console.say(&format!(
                    "  between 1 and {limit} cards, and at least one is compulsory"
                ));
                continue;
            }
            let parsed: Result<Vec<Card>, _> = tokens.iter().map(|t| Card::parse(t)).collect();
            let Ok(cards) = parsed else {
                self.console.say(&format!(
                    "  name each card by rank and suit, like {}",
                    render::for_example(view.hand)
                ));
                continue;
            };
            let Ok(discard) = Hand::of(&cards) else {
                self.console.say("  each card once");
                continue;
            };
            if !discard.without(view.hand).is_empty() {
                self.console.say("  you do not hold all of those");
                continue;
            }
            return discard;
        }
    }

    fn declare(&mut self, view: &View, category: Category) -> Declaration {
        let full = Declaration::full(view.hand, category);
        self.show(view, None);
        if let Some(heard) = view.awaiting_answer {
            self.console
                .say(&format!("    {} calls {}", self.opponent, heard.spoken()));
        }
        if full.is_empty() {
            self.console.say(&format!(
                "    you have no {} to call",
                category.name().to_lowercase().replace('_', " ")
            ));
            return full;
        }

        let options = declaration_options(view.hand, category);
        self.console.say(&format!(
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
            self.console.say(&format!("    {}) {label}", number + 1));
        }
        loop {
            let raw = self.console.ask("  which: ");
            let raw = if raw.is_empty() { "1".to_string() } else { raw };
            if let Ok(choice) = raw.parse::<usize>() {
                if (1..=options.len()).contains(&choice) {
                    return options[choice - 1].clone();
                }
            }
            self.console
                .say(&format!("  a number from 1 to {}", options.len()));
        }
    }

    fn play(&mut self, view: &View) -> Card {
        let legal = view.legal_plays;
        self.show(view, Some(legal));
        if let Some(line) = render::trick(view, "you", &self.opponent, self.palette) {
            self.console.say(&line);
        }
        if legal != view.hand {
            self.console
                .say("    the bracketed cards are the ones you may play");
        }
        loop {
            let raw = self.console.ask("  your card: ");
            let Ok(card) = Card::parse(&raw) else {
                self.console.say(&format!(
                    "  name a card by rank and suit, like {}",
                    render::for_example(view.hand)
                ));
                continue;
            };
            if !view.hand.holds(card) {
                self.console.say("  you do not hold that one");
                continue;
            }
            if !legal.holds(card) {
                let led = view
                    .current_trick
                    .expect("a trick is in progress")
                    .led
                    .suit();
                self.console.say(&format!(
                    "  you must follow {} while you can",
                    render::suit_name(led)
                ));
                continue;
            }
            return card;
        }
    }
}

/// No proper names at the table: the machine is "your opponent".
const THEM: &str = "your opponent";

/// One line of what happened, as the terminal tells it.
fn narrate(seat: &mut dyn Seat, session: &Table, event: &Event) {
    match event {
        Event::DealBegins { .. } => {
            let partie = session.partie();
            let odds = if partie.number() > 1 {
                let chance = chance_of_the_rubicon(partie, Side::A);
                Some((chance, in_words(chance)))
            } else {
                None
            };
            seat.say(&format!("\n  ── deal {} of six ──", partie.number()));
            seat.say(&render::standing(session.standing(), odds));
        }
        Event::DealEnds { .. } => {
            // A post-mortem: the deal is over and every score in it was said
            // aloud, so the whole log is the human's to read.
            let finished = session.deal();
            let (mine, theirs) = (session.you(), session.you().opponent());
            seat.say("\n  the deal is over:");
            seat.say(&render::events(&finished.log, mine, "you", THEM));
            seat.say(&format!(
                "\n    you {}  ·  {THEM} {}",
                finished.log.total(mine),
                finished.log.total(theirs)
            ));
            return;
        }
        // The hand and the trick are drawn at each decision; the moves in
        // between are narrated.
        _ => {}
    }
    seat.say(&format!("  {}", event.text()));
}

/// A whole partie at the session's table: tell the seat what happened, ask
/// it what the session asks, and carry on until the partie is settled.
fn run(session: &mut Table, seat: &mut dyn Seat) -> Result<(), String> {
    let mut told = 0;
    loop {
        let events = session.events().to_vec();
        for event in &events[told..] {
            narrate(seat, session, event);
        }
        told = events.len();

        let view = session.view();
        let action = match session.prompt() {
            Prompt::Cut => Action::Cut(seat.cut()),
            Prompt::ChooseDealer => Action::FirstDealer(seat.choose_dealer()),
            Prompt::Exchange { .. } => Action::Exchange(seat.exchange(&view)),
            Prompt::Declare {
                category, options, ..
            } => {
                let called = seat.declare(&view, category);
                let index = options
                    .iter()
                    .position(|option| *option == called)
                    .ok_or_else(|| format!("the call {called:?} was not one of the choices"))?;
                Action::Declare(index)
            }
            Prompt::Play { .. } => Action::Play(seat.play(&view)),
            Prompt::NextDeal => {
                seat.next_deal();
                Action::NextDeal
            }
            Prompt::Over => return Ok(()),
        };
        // Every answer was checked against the view before it was given, so
        // the session refusing one is a bug, not a typing mistake.
        session
            .act(action)
            .map_err(|why| format!("the table refused that: {why}"))?;
    }
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

    let mut session = Table::new(level, seed);
    println!("\n  Piquet — a partie of six deals");
    println!("  your opponent {}", session.opponent().gloss);
    println!("  (seed {seed}; pass --seed to replay, --level 1..5 to change opponent)");

    let mut human = HumanAgent {
        console: Console {
            input: Box::new(io::stdin().lock()),
            output: Box::new(io::stdout()),
            leave: walk_away,
        },
        opponent: THEM.to_string(),
        palette: render::Palette::detect(
            io::stdout().is_terminal(),
            std::env::var("NO_COLOR").ok(),
        ),
    };
    if let Err(why) = run(&mut session, &mut human) {
        eprintln!("  {why}");
        std::process::exit(1);
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
    use piquet_core::rules::{deal_from, Deal, Phase};
    use piquet_core::scoring::Player;
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
        let console = Console {
            input: Box::new(Cursor::new(script)),
            output: Box::new(shown.clone()),
            leave: ran_out,
        };
        let agent = HumanAgent {
            console,
            opponent: "your opponent".to_string(),
            palette: render::PLAIN,
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

    // -- a whole partie, through the session --

    /// A machine in the person's chair, remembering what it was told.
    struct Machine {
        agent: piquet_core::heuristics::HeuristicAgent,
        heard: Vec<String>,
    }

    impl Agent for Machine {
        fn name(&self) -> &str {
            "you"
        }
        fn exchange(&mut self, view: &View) -> Hand {
            self.agent.exchange(view)
        }
        fn declare(&mut self, view: &View, category: Category) -> Declaration {
            self.agent.declare(view, category)
        }
        fn play(&mut self, view: &View) -> Card {
            self.agent.play(view)
        }
    }

    impl Seat for Machine {
        fn say(&mut self, line: &str) {
            self.heard.push(line.to_string());
        }
        fn cut(&mut self) -> usize {
            16
        }
        fn choose_dealer(&mut self) -> Who {
            Who::You
        }
        fn next_deal(&mut self) {}
    }

    #[test]
    fn the_terminal_plays_a_whole_partie_through_the_session() {
        for seed in [7, 1674, 2026] {
            let mut session = Table::new(3, seed);
            let mut seat = Machine {
                agent: piquet_core::heuristics::HeuristicAgent::new(4, seed).unwrap(),
                heard: Vec::new(),
            };
            run(&mut session, &mut seat).unwrap();
            assert_eq!(session.prompt(), Prompt::Over);
            let heard = seat.heard.join("\n");
            let deals = session.partie().number().min(6);
            for n in 1..=deals {
                assert!(
                    heard.contains(&format!("── deal {n} of six ──")),
                    "seed {seed}: no deal {n}"
                );
            }
            assert!(
                heard.matches("the deal is over:").count() >= 6,
                "seed {seed}"
            );
            assert!(heard.contains("Final score"), "seed {seed}");
            // Cut for the deal, as the page does, before the first deal.
            assert!(
                heard.find(" cut").unwrap() < heard.find("── deal 1").unwrap(),
                "seed {seed}"
            );
        }
    }
}
