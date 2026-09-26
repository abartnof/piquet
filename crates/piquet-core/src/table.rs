//! A table: one human, one opponent, a whole partie, one decision at a time.
//!
//! `play::play_deal` asks each agent in turn and waits for the answer, which
//! suits a terminal and nothing else: a browser, or a three-dimensional
//! client, cannot block while a person thinks. So the table turns the loop
//! inside out. It runs the opponent until the human must decide something,
//! stops, and says what that decision is -- a [`Prompt`]. The client answers
//! with an [`Action`] whenever it likes, and the table runs on to the next
//! one.
//!
//! Everything a client is given is derived from the human's
//! [`View`](crate::observation::View) -- the prompt, the narration, the hand
//! -- so a client cannot show what the human could not know, however it is
//! written. [`Table::deal`] is the exception, and says so.
//!
//! The same seed at the same level is the same partie here as it is at the
//! terminal: the opponent is seated and the packs shuffled from one generator,
//! in the same order.

use crate::agents::Agent;
use crate::cards::{Card, Hand, Rank};
use crate::chances::chance_of_the_rubicon;
use crate::declarations::{Announcement, Declaration};
use crate::observation::{view_for, View};
use crate::opponents::{opponent, seat, Opponent};
use crate::options::declaration_options;
use crate::partie::{Partie, Settlement, Side, Standing};
use crate::rng::Rng;
use crate::rules::{deal_from, Deal, Phase};
use crate::scoring::{Category, Player};
use crate::solver::SolverAgent;

/// The human is always side A, and deals first -- so the opponent is elder in
/// the first deal, as at the terminal.
const YOU: Side = Side::A;

/// Which of the two people at the table.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Who {
    You,
    Them,
}

/// What the human must decide now.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Prompt {
    /// Throw between one and `limit` cards, and draw as many.
    Exchange { limit: usize },
    /// Choose one of `options` in this category. The first is the full call.
    Declare {
        category: Category,
        options: Vec<Declaration>,
        /// What the opponent, as elder, has just called -- the thing being
        /// answered. `None` when the human speaks first, or elder said nothing.
        answering: Option<Announcement>,
    },
    /// Lead or follow with one of these.
    Play { legal: Hand },
    /// The deal is over. Deal the next one when ready.
    NextDeal,
    /// The partie is over and settled.
    Over,
}

/// The human's answer to a [`Prompt`].
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Action {
    Exchange(Hand),
    /// An index into the prompt's `options`.
    Declare(usize),
    Play(Card),
    NextDeal,
}

/// The help the human has asked for. Every one is a toggle, and none of them
/// changes the rules: they change what the human is *asked*, never what
/// happens.
///
/// Andrew's brief for the table: "less persnickety, less needless clicking --
/// rather, effortless and fun", with every aid something that "could be
/// turned off".
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Aids {
    /// Offer [`Table::hint`]. The table does nothing with this itself; it is
    /// kept here so a client has one place to read every setting from.
    pub hints: bool,
    /// Play a card for the human when it is the only one they may play.
    pub play_forced: bool,
    /// Call everything, in every category, without asking.
    pub declare_for_me: bool,
}

/// What an advisor would do in the human's place.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Hint {
    pub action: Action,
    /// Who is advising -- a rung of the ladder, so the advice names a player
    /// whose skill can be learnt rather than an anonymous number.
    pub advisor: Opponent,
    said: String,
}

impl Hint {
    /// The advice as a sentence: "Foster would play K♠."
    pub fn text(&self) -> String {
        format!("{} would {}.", self.advisor.name, self.said)
    }
}

/// Something that happened at the table, as the human perceived it.
///
/// Structured rather than prose, so a client can animate it; [`Event::text`]
/// is there for one that just wants to print it.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Event {
    DealBegins {
        number: usize,
        elder: Who,
        /// From the human's chair.
        standing: Standing,
        /// The human's chance of getting over a hundred, in per-mille. `None`
        /// in the first deal, where it says nothing useful.
        rubicon_permille: Option<u32>,
    },
    Exchanged {
        who: Who,
        count: usize,
    },
    /// The human's own exchange, in full.
    Drew {
        discarded: Hand,
        drew: Hand,
    },
    /// Declared aloud. `said` is what was said, never a suit.
    Called {
        who: Who,
        category: Category,
        said: String,
    },
    /// How a category came out: who scores it, if anyone.
    Decided {
        category: Category,
        winner: Option<Who>,
    },
    /// A combination the opponent had to show.
    Showed {
        who: Who,
        what: String,
    },
    Scored {
        who: Who,
        amount: i32,
        what: String,
        /// Which of Law 67's categories it reckons in, for a client keeping a
        /// running tab by category.
        category: Category,
    },
    /// The human had nothing to call, and the table called it for them.
    NothingToCall {
        category: Category,
    },
    Played {
        who: Who,
        card: Card,
    },
    TookTrick {
        who: Who,
        number: usize,
    },
    DealEnds {
        number: usize,
        you: i32,
        them: i32,
    },
    PartieEnds {
        you: i32,
        them: i32,
        settlement: Settlement,
    },
}

fn category_word(category: Category) -> &'static str {
    match category {
        Category::CarteBlanche => "carte blanche",
        Category::Point => "the point",
        Category::Sequences => "sequences",
        Category::Sets => "sets",
        Category::Play => "the play",
        Category::Cards => "the cards",
        Category::Bonus => "the bonus",
    }
}

/// What a log entry was scored for, as the end of a sentence.
///
/// The log's own details are pinned by the golden vectors -- "leads A♠" --
/// and read as notes rather than prose, so the narration rephrases them here
/// rather than the log changing underneath the vectors.
fn scored_for(category: Category, detail: &str) -> String {
    if detail.is_empty() {
        return category_word(category).to_string();
    }
    if let Some(card) = detail.strip_prefix("leads ") {
        return format!("leading {card}");
    }
    if let Some(card) = detail.strip_prefix("wins with ") {
        return format!("winning with {card}");
    }
    if detail == "last trick" {
        return "the last trick".to_string();
    }
    detail.to_string()
}

/// An announcement as it is said aloud, tie-break and all when one was given.
pub fn said(announcement: Announcement) -> String {
    let shape = announcement.spoken();
    match (announcement.category, announcement.tiebreak) {
        (Category::Point, Some(pips)) => format!("{shape}, making {pips}"),
        (Category::Sequences, Some(top)) => {
            format!("{shape} to the {}", Rank(top as u8).name())
        }
        (Category::Sets, Some(rank)) => format!("{shape} of {}s", Rank(rank as u8).name()),
        _ => shape,
    }
}

impl Event {
    /// One line of narration. `them` is the opponent's name.
    pub fn text(&self, them: &str) -> String {
        let name = |who: Who| if who == Who::You { "you" } else { them };
        match self {
            Event::DealBegins { number, elder, .. } => format!(
                "Deal {number} of six. {}",
                if *elder == Who::You {
                    "You are elder, and lead.".to_string()
                } else {
                    format!("{them} is elder; you deal.")
                }
            ),
            Event::Exchanged { who, count } => format!(
                "{} exchange{} {count} card{}.",
                capital(name(*who)),
                if *who == Who::You { "" } else { "s" },
                if *count == 1 { "" } else { "s" }
            ),
            Event::Drew { discarded, drew } => {
                format!("You threw {} and drew {}.", shown(*discarded), shown(*drew))
            }
            Event::Called { who, said, .. } => {
                format!("{}: \u{201c}{said}.\u{201d}", capital(name(*who)))
            }
            Event::Decided { category, winner } => match winner {
                Some(Who::You) => format!("You take {}.", category_word(*category)),
                Some(Who::Them) => format!("{them} takes {}.", category_word(*category)),
                None => format!(
                    "{} is equal: neither scores.",
                    capital(category_word(*category))
                ),
            },
            Event::Showed { who, what } => format!("{} shows {what}.", capital(name(*who))),
            Event::Scored {
                who, amount, what, ..
            } => format!(
                "{} score{} {amount} for {what}.",
                capital(name(*who)),
                if *who == Who::You { "" } else { "s" }
            ),
            Event::NothingToCall { category } => {
                format!("You have nothing to call in {}.", category_word(*category))
            }
            Event::Played { who, card } => {
                format!("{} played {}.", capital(name(*who)), card.display())
            }
            Event::TookTrick { who, number } => format!(
                "{} take{} trick {number}.",
                capital(name(*who)),
                if *who == Who::You { "" } else { "s" }
            ),
            Event::DealEnds {
                number,
                you,
                them: theirs,
            } => {
                format!("Deal {number} is over: you {you}, {them} {theirs}.")
            }
            Event::PartieEnds {
                you,
                them: theirs,
                settlement,
            } => {
                let verdict = match settlement.winner {
                    None => "The partie is drawn.".to_string(),
                    Some(side) if side == YOU => format!(
                        "You win the partie, and {them} pays {}{}.",
                        settlement.points,
                        if settlement.rubicon {
                            " -- rubiconed, so the sum and not the difference"
                        } else {
                            ""
                        }
                    ),
                    Some(_) => format!(
                        "{them} wins the partie, and you pay {}{}.",
                        settlement.points,
                        if settlement.rubicon {
                            " -- you were rubiconed, so the sum and not the difference"
                        } else {
                            ""
                        }
                    ),
                };
                format!("Final score: you {you}, {them} {theirs}. {verdict}")
            }
        }
    }
}

/// Cards as a reader sees them -- `10♣ 7♦` -- rather than as they are typed.
fn shown(cards: Hand) -> String {
    cards
        .cards()
        .map(|c| c.display())
        .collect::<Vec<_>>()
        .join(" ")
}

fn capital(word: &str) -> String {
    let mut chars = word.chars();
    match chars.next() {
        Some(first) => first.to_uppercase().chain(chars).collect(),
        None => String::new(),
    }
}

/// The session. See the module documentation.
pub struct Table {
    seed: u32,
    who: Opponent,
    rng: Rng,
    machine: Box<dyn Agent>,
    partie: Partie,
    deal: Deal,
    /// Where the partie stood when this deal began, from elder's chair.
    standing: Standing,
    events: Vec<Event>,
    /// Announcements by the opponent already narrated this deal, so each is
    /// said once however many times it appears in successive views.
    narrated: Vec<Announcement>,
    /// Whether the finished deal has been entered in the partie.
    recorded: bool,
    aids: Aids,
    /// Every action taken from the human's seat, and whether the table took
    /// it for them. Enough, with the seed, to rebuild the table exactly.
    history: Vec<(Action, bool)>,
    /// While rebuilding from a record, nothing is automatic: the record says
    /// what was done, including what was done for the human.
    replaying: bool,
}

impl Table {
    /// Sit down against the opponent at `level`, with everything drawn from
    /// `seed`.
    pub fn new(level: u32, seed: u32) -> Table {
        Table::with_aids(level, seed, Aids::default())
    }

    /// The same, with some help switched on from the start.
    pub fn with_aids(level: u32, seed: u32, aids: Aids) -> Table {
        let mut table = Table::seated(level, seed, aids, false);
        table.advance();
        table
    }

    /// Rebuild a table from its [`record`](Table::record).
    ///
    /// The table is deterministic -- the opponent, the packs and its choices
    /// all come from the seed -- so the seed and what the human did are the
    /// whole game. A record that does not fit the game is refused.
    pub fn replay(
        level: u32,
        seed: u32,
        aids: Aids,
        record: &[(Action, bool)],
    ) -> Result<Table, String> {
        let mut table = Table::seated(level, seed, aids, true);
        table.advance();
        for (step, (action, automatic)) in record.iter().enumerate() {
            table.apply(action.clone()).map_err(|why| {
                format!("the record does not fit this game at step {step}: {why}")
            })?;
            table.history.push((action.clone(), *automatic));
            table.advance();
        }
        table.replaying = false;
        table.advance();
        Ok(table)
    }

    fn seated(level: u32, seed: u32, aids: Aids, replaying: bool) -> Table {
        let mut rng = Rng::seeded(seed);
        let who = opponent(level);
        let machine = seat(who.level, &mut rng);
        let partie = Partie::new(YOU);
        let standing = partie.standing();
        let deal = deal_from(&shuffled(&mut rng)).expect("a whole pack deals");
        let mut table = Table {
            seed,
            who,
            rng,
            machine,
            partie,
            deal,
            standing,
            events: Vec::new(),
            narrated: Vec::new(),
            recorded: false,
            aids,
            history: Vec::new(),
            replaying,
        };
        table.begin_deal();
        table
    }

    pub fn aids(&self) -> Aids {
        self.aids
    }

    /// Change the help. It takes effect at once: switching on "declare for
    /// me" at a declaration makes it.
    pub fn set_aids(&mut self, aids: Aids) {
        self.aids = aids;
        self.advance();
    }

    /// Every action taken from the human's seat, and whether the table took
    /// it for them. With the level and seed, the whole game.
    pub fn record(&self) -> &[(Action, bool)] {
        &self.history
    }

    /// Take back the human's last decision, and anything the table did for
    /// them after it. The opponent's replies go with it.
    pub fn undo(&mut self) -> Result<(), String> {
        let mut record = self.history.clone();
        loop {
            match record.pop() {
                None => return Err("there is nothing to take back".to_string()),
                Some((_, true)) => continue,
                Some((_, false)) => break,
            }
        }
        *self = Table::replay(self.who.level, self.seed, self.aids, &record)?;
        Ok(())
    }

    /// What an advisor would do in the human's place, from the human's own
    /// view -- so a hint can never tell them anything they could not know.
    ///
    /// The advisor is Foster, the top of the ladder: the exact solver in the
    /// endgame and Hoyle's judgement before it. It has a generator of its own,
    /// seeded from where the game stands, so asking twice gives the same
    /// answer and asking at all changes nothing.
    pub fn hint(&self) -> Option<Hint> {
        let prompt = self.prompt();
        if matches!(prompt, Prompt::NextDeal | Prompt::Over) {
            return None;
        }
        let view = self.view();
        let advisor = opponent(5);
        let seed = self
            .seed
            .rotate_left(7)
            .wrapping_add((self.history.len() as u32).wrapping_mul(0x9E37_79B9));
        let mut agent = SolverAgent::new(seed).named(advisor.name);
        let (action, said) = match prompt {
            Prompt::Exchange { .. } => {
                let discard = agent.exchange(&view);
                (
                    Action::Exchange(discard),
                    format!("throw {}", shown(discard)),
                )
            }
            Prompt::Play { .. } => {
                let card = agent.play(&view);
                let verb = if view.current_trick.is_some() {
                    "play"
                } else {
                    "lead"
                };
                (Action::Play(card), format!("{verb} {}", card.display()))
            }
            Prompt::Declare {
                category, options, ..
            } => {
                let wanted = agent.declare(&view, category);
                let index = options.iter().position(|o| *o == wanted).unwrap_or(0);
                let chosen = &options[index];
                let said = if chosen.is_empty() {
                    "say nothing".to_string()
                } else {
                    format!("call {}", chosen.describe())
                };
                (Action::Declare(index), said)
            }
            Prompt::NextDeal | Prompt::Over => return None,
        };
        Some(Hint {
            action,
            advisor,
            said,
        })
    }

    pub fn seed(&self) -> u32 {
        self.seed
    }

    pub fn opponent(&self) -> Opponent {
        self.who
    }

    pub fn partie(&self) -> &Partie {
        &self.partie
    }

    /// Everything said at the table since the human sat down.
    pub fn events(&self) -> &[Event] {
        &self.events
    }

    /// The human's seat in the current deal.
    pub fn you(&self) -> Player {
        if self.elder_side() == YOU {
            Player::Elder
        } else {
            Player::Younger
        }
    }

    /// Where the partie stood when this deal began, from the human's chair.
    pub fn standing(&self) -> Standing {
        if self.elder_side() == YOU {
            self.standing
        } else {
            self.standing.reversed()
        }
    }

    /// The deal as the human sees it. Render from this.
    pub fn view(&self) -> View {
        view_for(&self.deal, self.you(), Some(self.standing))
    }

    /// The whole truth about the deal, both hands included.
    ///
    /// For tests and for a post-mortem after the deal is over. A client that
    /// renders from this during play is showing the human the opponent's
    /// cards.
    pub fn deal(&self) -> &Deal {
        &self.deal
    }

    /// What the human must decide now.
    pub fn prompt(&self) -> Prompt {
        if self.partie.complete() {
            return Prompt::Over;
        }
        if self.deal.phase == Phase::Complete {
            return Prompt::NextDeal;
        }
        let you = self.you();
        match self.deal.phase {
            Phase::ElderExchange | Phase::YoungerExchange => Prompt::Exchange {
                limit: self.deal.exchange_limit(you),
            },
            Phase::Play => Prompt::Play {
                legal: self.deal.legal_plays(Some(you)),
            },
            _ => {
                let category = self.deal.declaring_category().expect("a declaration phase");
                let view = self.view();
                Prompt::Declare {
                    category,
                    options: declaration_options(view.hand, category),
                    answering: view.awaiting_answer,
                }
            }
        }
    }

    /// Answer the prompt. A move the rules forbid is refused with the reason,
    /// and the table is left exactly as it was.
    pub fn act(&mut self, action: Action) -> Result<(), String> {
        self.apply(action.clone())?;
        self.history.push((action, false));
        self.advance();
        Ok(())
    }

    /// Carry out one action from the human's seat and narrate it, without
    /// running anyone else. The one path for every such action, chosen or
    /// automatic, so a record replays to the same words.
    fn apply(&mut self, action: Action) -> Result<(), String> {
        let you = self.you();
        match (self.prompt(), action) {
            (Prompt::Exchange { .. }, Action::Exchange(discard)) => {
                let before = self.view();
                let next = self.deal.exchange(you, discard)?;
                self.step(next, Who::You, &before);
            }
            (
                Prompt::Declare {
                    category, options, ..
                },
                Action::Declare(index),
            ) => {
                let Some(choice) = options.get(index).cloned() else {
                    return Err(format!(
                        "there are {} options, not {}",
                        options.len(),
                        index + 1
                    ));
                };
                let before = self.view();
                let next = self.deal.declare(you, choice.clone())?;
                // A declaration with nothing to call was never a decision.
                self.events.push(if options.len() == 1 {
                    Event::NothingToCall { category }
                } else {
                    Event::Called {
                        who: Who::You,
                        category,
                        said: if choice.is_empty() {
                            "nothing".to_string()
                        } else {
                            choice.describe()
                        },
                    }
                });
                self.step(next, Who::You, &before);
            }
            (Prompt::Play { legal }, Action::Play(card)) => {
                if !self.view().hand.holds(card) {
                    return Err(format!("you do not hold {}", card.code()));
                }
                if !legal.holds(card) {
                    let led = self.deal.current_trick.expect("a trick in progress").led;
                    return Err(format!(
                        "you must follow {} while you can",
                        led.suit().name()
                    ));
                }
                let before = self.view();
                let next = self.deal.play(you, card)?;
                self.step(next, Who::You, &before);
            }
            (Prompt::NextDeal, Action::NextDeal) => {
                self.deal = deal_from(&shuffled(&mut self.rng)).expect("a whole pack deals");
                self.standing = self.partie.standing();
                self.recorded = false;
                self.narrated.clear();
                self.begin_deal();
            }
            (Prompt::Over, _) => return Err("the partie is over".to_string()),
            (prompt, action) => {
                return Err(format!("{action:?} is not an answer to {prompt:?}"));
            }
        }
        Ok(())
    }

    /// What the table would do for the human here, if anything.
    fn automatic(&self) -> Option<Action> {
        if self.replaying {
            return None;
        }
        match self.prompt() {
            // Nothing to call is not a decision, whatever the aids.
            Prompt::Declare { options, .. } if options.len() == 1 => Some(Action::Declare(0)),
            Prompt::Declare { .. } if self.aids.declare_for_me => Some(Action::Declare(0)),
            Prompt::Play { legal } if self.aids.play_forced && legal.len() == 1 => {
                legal.cards().next().map(Action::Play)
            }
            _ => None,
        }
    }

    fn elder_side(&self) -> Side {
        // While a finished deal awaits NextDeal the partie has already moved
        // on, so ask about the deal that is on the table, not the next one.
        self.partie.elder_in(self.standing.number)
    }

    fn begin_deal(&mut self) {
        let standing = self.standing();
        let rubicon_permille = (standing.number > 1)
            .then(|| (chance_of_the_rubicon(&self.partie, YOU) * 1000.0).round() as u32);
        self.events.push(Event::DealBegins {
            number: standing.number,
            elder: if self.you() == Player::Elder {
                Who::You
            } else {
                Who::Them
            },
            standing,
            rubicon_permille,
        });
    }

    /// Run the opponent, and any move the human has no real choice in, until
    /// the human must decide something or the deal is over.
    fn advance(&mut self) {
        loop {
            if self.deal.phase == Phase::Complete {
                self.finish_deal();
                return;
            }
            let you = self.you();
            let mover = match self.deal.phase {
                Phase::ElderExchange => Player::Elder,
                Phase::YoungerExchange => Player::Younger,
                Phase::Play => self.deal.to_play().expect("the play has a mover"),
                _ => self.deal.to_declare().expect("a declaration has a speaker"),
            };

            if mover == you {
                let Some(action) = self.automatic() else {
                    return;
                };
                self.apply(action.clone())
                    .expect("the table only ever makes legal moves for the human");
                self.history.push((action, true));
                continue;
            }

            let before = self.view();
            let theirs = view_for(&self.deal, mover, Some(self.standing));
            let next = match self.deal.phase {
                Phase::ElderExchange | Phase::YoungerExchange => {
                    let discard = self.machine.exchange(&theirs);
                    self.deal.exchange(mover, discard)
                }
                Phase::Play => {
                    let card = self.machine.play(&theirs);
                    self.deal.play(mover, card)
                }
                _ => {
                    let category = self.deal.declaring_category().expect("a declaration phase");
                    let declaration = self.machine.declare(&theirs, category);
                    self.deal.declare(mover, declaration)
                }
            };
            let next = next.expect("the opponent only ever makes legal moves");
            self.step(next, Who::Them, &before);
        }
    }

    /// Move to `next` and narrate the difference, as the human perceived it.
    fn step(&mut self, next: Deal, actor: Who, before: &View) {
        let phase = self.deal.phase;
        self.deal = next;
        let after = self.view();

        match phase {
            Phase::ElderExchange | Phase::YoungerExchange => {
                let count = before.talon_remaining - after.talon_remaining;
                self.events.push(Event::Exchanged { who: actor, count });
                if actor == Who::You {
                    self.events.push(Event::Drew {
                        discarded: after.my_discards.without(before.my_discards),
                        drew: after.hand.without(before.hand),
                    });
                }
            }
            Phase::Play => {
                let played = |v: &View| {
                    v.tricks
                        .iter()
                        .chain(v.current_trick.iter())
                        .map(|t| usize::from(t.followed.is_some()) + 1)
                        .sum::<usize>()
                };
                // The card just played is the last one on the table.
                let card = match after.current_trick {
                    Some(trick) => trick.followed.unwrap_or(trick.led),
                    None => after
                        .tricks
                        .last()
                        .and_then(|t| t.followed)
                        .expect("a completed trick was followed"),
                };
                debug_assert_eq!(played(&after), played(before) + 1);
                self.events.push(Event::Played { who: actor, card });
                if after.tricks.len() > before.tricks.len() {
                    let trick = after.tricks.last().expect("a trick was just completed");
                    let winner = trick.winner().expect("a completed trick has a winner");
                    self.events.push(Event::TookTrick {
                        who: self.who_is(winner),
                        number: after.tricks.len(),
                    });
                }
            }
            _ => {
                // The opponent, as elder, has just called: say what the human
                // heard, which is the shape and never the suit.
                if actor == Who::Them && after.outcomes.len() == before.outcomes.len() {
                    let category = before.phase.category().expect("a declaration phase");
                    let heard = after.awaiting_answer;
                    self.events.push(Event::Called {
                        who: Who::Them,
                        category,
                        said: heard.map_or_else(|| "nothing".to_string(), said),
                    });
                    if let Some(heard) = heard {
                        self.narrated.push(heard);
                    }
                }
                for (category, winner) in &after.outcomes[before.outcomes.len()..] {
                    self.events.push(Event::Decided {
                        category: *category,
                        winner: winner.map(|w| self.who_is(w)),
                    });
                }
            }
        }

        // Whatever the opponent has now said aloud or shown, once each.
        for heard in &after.heard {
            if !self.narrated.contains(heard) {
                self.narrated.push(*heard);
                self.events.push(Event::Called {
                    who: Who::Them,
                    category: heard.category,
                    said: said(*heard),
                });
            }
        }
        for shown in &after.seen[before.seen.len().min(after.seen.len())..] {
            self.events.push(Event::Showed {
                who: Who::Them,
                what: shown.describe(),
            });
        }
        for event in &after.log.events[before.log.events.len()..] {
            self.events.push(Event::Scored {
                who: self.who_is(event.player),
                amount: event.amount,
                what: scored_for(event.category, &event.detail),
                category: event.category,
            });
        }
    }

    fn who_is(&self, player: Player) -> Who {
        if player == self.you() {
            Who::You
        } else {
            Who::Them
        }
    }

    fn finish_deal(&mut self) {
        if self.recorded {
            return;
        }
        self.recorded = true;
        let you = self.you();
        let (mine, theirs) = (
            self.deal.log.total(you),
            self.deal.log.total(you.opponent()),
        );
        self.events.push(Event::DealEnds {
            number: self.standing.number,
            you: mine,
            them: theirs,
        });
        self.partie = self
            .partie
            .record_scores(
                self.deal.log.total(Player::Elder),
                self.deal.log.total(Player::Younger),
            )
            .expect("a deal in progress belongs to an unfinished partie");
        if let Some(settlement) = self.partie.settlement() {
            let (a, b) = self.partie.totals();
            self.events.push(Event::PartieEnds {
                you: a,
                them: b,
                settlement,
            });
        }
    }
}

fn shuffled(rng: &mut Rng) -> Vec<Card> {
    let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
    rng.shuffle(&mut pack);
    pack
}
