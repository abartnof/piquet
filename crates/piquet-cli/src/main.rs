//! A table a person can sit down at.
//!
//! `piquet` deals you a partie of six against a named opponent. The engine
//! lives in `piquet-core`; this is only the furniture, and it is deliberately
//! plain -- `docs/DESIGN.md` defers the real interface and says basic graphics
//! are acceptable until then.

mod options;
mod render;

use std::io::{self, BufRead, Write};

use options::understatements;
use piquet_core::agents::Agent;
use piquet_core::cards::{Card, Hand};
use piquet_core::chances::{chance_of_the_rubicon, in_words};
use piquet_core::declarations::Declaration;
use piquet_core::heuristics::HeuristicAgent;
use piquet_core::observation::View;
use piquet_core::partie::{Partie, Side};
use piquet_core::play::play_deal;
use piquet_core::rng::Rng;
use piquet_core::rules::{deal_from, Deal};
use piquet_core::scoring::{Category, Player};
use piquet_core::solver::SolverAgent;
use piquet_core::style::Style;

/// Named opponents, so a skill setting is a person rather than a number.
const OPPONENTS: [(u32, &str, &str); 5] = [
    (1, "Bess", "plays her highest card and hopes"),
    (2, "Cotton", "knows what a hand is worth"),
    (3, "Cavendish", "remembers what has been played"),
    (4, "Hoyle", "watches what you show him"),
    (5, "Foster", "reads the endgame exactly"),
];

struct Table {
    input: Box<dyn BufRead>,
}

impl Table {
    fn say(&self, line: &str) {
        println!("{line}");
    }

    fn ask(&mut self, prompt: &str) -> String {
        print!("{prompt}");
        io::stdout().flush().ok();
        let mut line = String::new();
        if self.input.read_line(&mut line).unwrap_or(0) == 0 {
            // End of input: treat it as walking away from the table.
            println!();
            std::process::exit(0);
        }
        line.trim().to_string()
    }
}

/// The human, as an [`Agent`]. The engine cannot tell the difference, which is
/// what makes the training mode possible later.
struct HumanAgent {
    table: Table,
    opponent: String,
}

impl HumanAgent {
    fn show(&self, view: &View, legal: Option<Hand>) {
        println!();
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

        let mut options = vec![full.clone(), Declaration::sink()];
        options.extend(understatements(view.hand, category));
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

fn make_opponent(level: u32, rng: &mut Rng, name: &str) -> Box<dyn Agent> {
    let seed = rng.below(u32::MAX as usize) as u32;
    let style = Style::random(rng);
    if level >= 5 {
        Box::new(SolverAgent::new(seed))
    } else {
        Box::new(
            HeuristicAgent::new(level, seed)
                .expect("a level from the table is valid")
                .with_style(style)
                .named(name),
        )
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

    let level = level.clamp(1, 5);
    let (_, opponent_name, gloss) = OPPONENTS[(level - 1) as usize];
    let mut rng = Rng::seeded(seed);

    let table = Table {
        input: Box::new(io::stdin().lock()),
    };
    println!("\n  Piquet — a partie of six deals");
    println!("  your opponent is {opponent_name}, who {gloss}");
    println!("  (seed {seed}; pass --seed to replay, --level 1..5 to change opponent)\n");

    let mut human = HumanAgent {
        table,
        opponent: opponent_name.to_string(),
    };
    let mut machine = make_opponent(level, &mut rng, opponent_name);

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
                Side::A => (&mut human, machine.as_mut()),
                Side::B => (machine.as_mut(), &mut human),
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
            "    {opponent_name} wins, and you pay {}{}",
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
