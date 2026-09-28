//! The table as a protocol: JSON out, one-line commands in.
//!
//! A client -- the browser page under `web/`, or anything that replaces it --
//! holds no game logic at all. It asks for the state, draws it, and sends back
//! one of four commands:
//!
//! ```text
//! cut 16                 lift sixteen cards in the cut for deal (2 to 30)
//! dealer you             with the choice of deal: you deal first (or: them)
//! exchange 7C 8C KC      throw these, draw as many
//! declare 0              choose option 0 of the declaration prompt
//! play KS                lead or follow with this card
//! next                   deal the next hand
//! undo                   take back the last decision
//! set hints on           switch an aid: hints, play_forced, declare_for_me,
//!                        play_winners
//! ```
//!
//! The state's shape is documented in `docs/PROTOCOL.md`, and every field in
//! it is derived from the human's view, so a client cannot show more than the
//! human at the table could know.
//!
//! Compiled to WebAssembly the crate exports four functions (see [`ffi`]),
//! passing strings through linear memory. There is no `wasm-bindgen`: the
//! engine has no dependencies and the four functions do not need one.

use piquet_core::cards::{Card, Hand, Suit};
use piquet_core::chances::in_words;
use piquet_core::combos::holdings;
use piquet_core::declarations::Declaration;
use piquet_core::rules::Trick;
use piquet_core::scoring::{Category, Player};
use piquet_core::table::{
    said, Action, Aids, Event, Prompt, Table, Who, DEEPEST_CUT, SHALLOWEST_CUT,
};

/// Bumped whenever the state changes shape in a way a client would notice.
pub const PROTOCOL: u32 = 2;

/// One human at one table, and the reason the last command was refused.
pub struct Session {
    table: Table,
    level: u32,
    error: Option<String>,
}

impl Session {
    pub fn new(level: u32, seed: u32) -> Session {
        Session {
            table: Table::new(level, seed),
            level: level.clamp(1, 5),
            error: None,
        }
    }

    pub fn table(&self) -> &Table {
        &self.table
    }

    /// Carry out one command. On refusal the table is untouched and the
    /// reason is in the state's `error` until the next command succeeds.
    pub fn send(&mut self, command: &str) -> bool {
        match self.carry_out(command) {
            Ok(()) => {
                self.error = None;
                true
            }
            Err(why) => {
                self.error = Some(why);
                false
            }
        }
    }

    pub fn state(&self) -> String {
        state(&self.table, self.level, self.error.as_deref())
    }

    fn carry_out(&mut self, command: &str) -> Result<(), String> {
        let mut lines = command.lines();
        let first: Vec<&str> = lines.next().unwrap_or("").split_whitespace().collect();
        if first.first() == Some(&"replay") {
            return self.reload(&first, lines);
        }
        let words: Vec<&str> = command.split_whitespace().collect();
        match words.as_slice() {
            ["undo"] => self.table.undo(),
            ["set", aid, value] => {
                let on = match *value {
                    "on" => true,
                    "off" => false,
                    other => return Err(format!("set {aid} on, or off -- not {other:?}")),
                };
                let mut aids = self.table.aids();
                match *aid {
                    "hints" => aids.hints = on,
                    "play_forced" => aids.play_forced = on,
                    "declare_for_me" => aids.declare_for_me = on,
                    "play_winners" => aids.play_winners = on,
                    other => return Err(format!("there is no aid called {other:?}")),
                }
                self.table.set_aids(aids);
                Ok(())
            }
            ["set", ..] => Err("set which aid, on or off?".to_string()),
            _ => parse(command).and_then(|action| self.table.act(action)),
        }
    }
}

impl Session {
    /// `replay LEVEL SEED`, then one record entry per line: rebuild the
    /// table from a record in one pass. A record that does not fit leaves
    /// the table alone.
    fn reload<'a>(
        &mut self,
        first: &[&str],
        entries: impl Iterator<Item = &'a str>,
    ) -> Result<(), String> {
        let [_, level, seed] = first else {
            return Err("replay LEVEL SEED, then the record, one entry a line".to_string());
        };
        let level: u32 = level
            .parse()
            .map_err(|_| format!("{level:?} is not a level"))?;
        let seed: u32 = seed
            .parse()
            .map_err(|_| format!("{seed:?} is not a seed"))?;
        let mut record = Vec::new();
        for line in entries.map(str::trim).filter(|l| !l.is_empty()) {
            let (automatic, entry) = match line.strip_prefix('*') {
                Some(rest) => (true, rest),
                None => (false, line),
            };
            record.push((parse(entry)?, automatic));
        }
        self.table = Table::replay(level, seed, Aids::default(), &record)?;
        self.level = level.clamp(1, 5);
        Ok(())
    }
}

/// A record entry: the command, marked `*` when the table took it for the
/// human.
fn entry(action: &Action, automatic: bool) -> String {
    format!("{}{}", if automatic { "*" } else { "" }, command(action))
}

/// The command that carries out an action, as a client would send it.
fn command(action: &Action) -> String {
    match action {
        Action::Cut(depth) => format!("cut {depth}"),
        Action::FirstDealer(Who::You) => "dealer you".to_string(),
        Action::FirstDealer(Who::Them) => "dealer them".to_string(),
        Action::Exchange(discard) => {
            let codes: Vec<String> = discard.cards().map(|c| c.code()).collect();
            format!("exchange {}", codes.join(" "))
        }
        Action::Declare(index) => format!("declare {index}"),
        Action::Play(card) => format!("play {}", card.code()),
        Action::NextDeal => "next".to_string(),
    }
}

fn parse(command: &str) -> Result<Action, String> {
    let mut words = command.split_whitespace();
    let verb = words.next().unwrap_or("");
    let rest: Vec<&str> = words.collect();
    match verb {
        "cut" => {
            let depth = rest
                .first()
                .and_then(|w| w.parse::<usize>().ok())
                .ok_or_else(|| "cut how deep? give the number of cards to lift".to_string())?;
            Ok(Action::Cut(depth))
        }
        "dealer" => match rest.first() {
            Some(&"you") => Ok(Action::FirstDealer(Who::You)),
            Some(&"them") => Ok(Action::FirstDealer(Who::Them)),
            _ => Err("dealer you, or dealer them".to_string()),
        },
        "exchange" => {
            if rest.is_empty() {
                return Err("name at least one card to throw".to_string());
            }
            let cards = rest
                .iter()
                .map(|w| Card::parse(w))
                .collect::<Result<Vec<Card>, String>>()?;
            Ok(Action::Exchange(Hand::of(&cards)?))
        }
        "declare" => {
            let index = rest
                .first()
                .and_then(|w| w.parse::<usize>().ok())
                .ok_or_else(|| "declare which option? give its number".to_string())?;
            Ok(Action::Declare(index))
        }
        "play" => {
            let word = rest.first().ok_or_else(|| "play which card?".to_string())?;
            Ok(Action::Play(Card::parse(word)?))
        }
        "next" => Ok(Action::NextDeal),
        "" => Err("an empty command".to_string()),
        other => Err(format!("unknown command {other:?}")),
    }
}

// ---------------------------------------------------------------------------
// Writing JSON. Twenty lines rather than a dependency.
// ---------------------------------------------------------------------------

fn text(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn object(fields: &[(&str, String)]) -> String {
    let body: Vec<String> = fields
        .iter()
        .map(|(k, v)| format!("{}:{}", text(k), v))
        .collect();
    format!("{{{}}}", body.join(","))
}

fn list(items: impl IntoIterator<Item = String>) -> String {
    format!("[{}]", items.into_iter().collect::<Vec<_>>().join(","))
}

fn or_null(value: Option<String>) -> String {
    value.unwrap_or_else(|| "null".to_string())
}

// ---------------------------------------------------------------------------
// The state.
// ---------------------------------------------------------------------------

/// Spades, hearts, diamonds, clubs; high to low within each. The order a
/// player reads a fanned hand in, and the one the terminal draws.
const DISPLAY_ORDER: [Suit; 4] = [Suit::SPADES, Suit::HEARTS, Suit::DIAMONDS, Suit::CLUBS];

fn hand(cards: Hand) -> String {
    let mut out = Vec::new();
    for suit in DISPLAY_ORDER {
        let mut these: Vec<Card> = cards.in_suit(suit).cards().collect();
        these.sort_by_key(|c| std::cmp::Reverse(c.rank()));
        out.extend(these.iter().map(|c| text(&c.code())));
    }
    list(out)
}

fn who(who: Who) -> String {
    text(match who {
        Who::You => "you",
        Who::Them => "them",
    })
}

fn category(category: Category) -> String {
    text(match category {
        Category::CarteBlanche => "carte_blanche",
        Category::Point => "point",
        Category::Sequences => "sequences",
        Category::Sets => "sets",
        Category::Play => "play",
        Category::Cards => "cards",
        Category::Bonus => "bonus",
    })
}

fn trick(trick: &Trick, you: Player, complete: bool) -> String {
    let side = |p: Player| who(if p == you { Who::You } else { Who::Them });
    let mut fields = vec![
        ("leader", side(trick.leader)),
        ("led", text(&trick.led.code())),
        ("followed", or_null(trick.followed.map(|c| text(&c.code())))),
    ];
    if complete {
        let winner = trick.winner().expect("a complete trick has a winner");
        fields.push(("winner", side(winner)));
    }
    object(&fields)
}

fn option(declaration: &Declaration, full: bool, held: Hand) -> String {
    object(&[
        (
            "text",
            text(&if declaration.is_empty() {
                "nothing".to_string()
            } else {
                declaration.describe()
            }),
        ),
        ("score", declaration.score().to_string()),
        ("full", full.to_string()),
        ("cards", hand(declaration.cards_in(held))),
    ])
}

fn prompt(prompt: &Prompt, held: Hand) -> String {
    match prompt {
        Prompt::Cut => object(&[
            ("kind", text("cut")),
            ("fewest", SHALLOWEST_CUT.to_string()),
            ("most", DEEPEST_CUT.to_string()),
        ]),
        Prompt::ChooseDealer => object(&[("kind", text("choose_dealer"))]),
        Prompt::Exchange { limit } => {
            object(&[("kind", text("exchange")), ("limit", limit.to_string())])
        }
        Prompt::Declare {
            category: c,
            options,
            answering,
        } => object(&[
            ("kind", text("declare")),
            ("category", category(*c)),
            ("answering", or_null(answering.map(|a| text(&said(a))))),
            (
                "options",
                list(
                    options
                        .iter()
                        .enumerate()
                        .map(|(i, d)| option(d, i == 0 && !d.is_empty(), held)),
                ),
            ),
        ]),
        Prompt::Play { legal } => object(&[("kind", text("play")), ("legal", hand(*legal))]),
        Prompt::NextDeal => object(&[("kind", text("next_deal"))]),
        Prompt::Over => object(&[("kind", text("over"))]),
    }
}

fn event(event: &Event, deal: usize) -> String {
    let mut fields: Vec<(&str, String)> = Vec::new();
    let kind = match event {
        Event::Cut { who: w, card } => {
            fields.push(("who", who(*w)));
            fields.push(("card", text(&card.code())));
            "cut"
        }
        Event::CutAgain => "cut_again",
        Event::ChoiceOfDeal { who: w } => {
            fields.push(("who", who(*w)));
            "choice_of_deal"
        }
        Event::FirstDealer { chooser, dealer } => {
            fields.push(("chooser", who(*chooser)));
            fields.push(("dealer", who(*dealer)));
            "first_dealer"
        }
        Event::DealBegins {
            elder,
            standing,
            rubicon_permille,
            ..
        } => {
            fields.push(("elder", who(*elder)));
            fields.push(("you_total", standing.mine.to_string()));
            fields.push(("them_total", standing.theirs.to_string()));
            fields.push((
                "rubicon_permille",
                or_null(rubicon_permille.map(|p| p.to_string())),
            ));
            "deal_begins"
        }
        Event::Exchanged { who: w, count } => {
            fields.push(("who", who(*w)));
            fields.push(("count", count.to_string()));
            "exchanged"
        }
        Event::Drew { discarded, drew } => {
            fields.push(("discarded", hand(*discarded)));
            fields.push(("drew", hand(*drew)));
            "drew"
        }
        Event::Called {
            who: w,
            category: c,
            said,
        } => {
            fields.push(("who", who(*w)));
            fields.push(("category", category(*c)));
            fields.push(("said", text(said)));
            "called"
        }
        Event::Decided {
            category: c,
            winner,
            asked,
        } => {
            fields.push(("category", category(*c)));
            fields.push(("winner", or_null(winner.map(who))));
            fields.push(("asked", asked.to_string()));
            "decided"
        }
        Event::Showed { who: w, what } => {
            fields.push(("who", who(*w)));
            fields.push(("what", text(what)));
            "showed"
        }
        Event::Scored {
            who: w,
            amount,
            what,
            category: c,
        } => {
            fields.push(("who", who(*w)));
            fields.push(("amount", amount.to_string()));
            fields.push(("what", text(what)));
            fields.push(("category", category(*c)));
            "scored"
        }
        Event::NothingToCall { category: c } => {
            fields.push(("category", category(*c)));
            "nothing_to_call"
        }
        Event::Played { who: w, card } => {
            fields.push(("who", who(*w)));
            fields.push(("card", text(&card.code())));
            "played"
        }
        Event::TookTrick { who: w, number } => {
            fields.push(("who", who(*w)));
            fields.push(("number", number.to_string()));
            "took_trick"
        }
        Event::DealEnds { you, them, .. } => {
            fields.push(("you", you.to_string()));
            fields.push(("them", them.to_string()));
            "deal_ends"
        }
        Event::PartieEnds { you, them, .. } => {
            fields.push(("you", you.to_string()));
            fields.push(("them", them.to_string()));
            "partie_ends"
        }
    };
    let mut all = vec![
        ("kind", text(kind)),
        ("deal", deal.to_string()),
        ("text", text(&event.text())),
    ];
    all.extend(fields);
    object(&all)
}

fn aids(table: &Table) -> String {
    let aids = table.aids();
    object(&[
        ("hints", aids.hints.to_string()),
        ("play_forced", aids.play_forced.to_string()),
        ("declare_for_me", aids.declare_for_me.to_string()),
        ("play_winners", aids.play_winners.to_string()),
    ])
}

/// The advice, when hints are on: a sentence, the command that follows it,
/// and the cards it concerns, for a client that wants to point at them.
fn hint(table: &Table, held: Hand) -> Option<String> {
    if !table.aids().hints {
        return None;
    }
    let hint = table.hint()?;
    let cards = match (&hint.action, table.prompt()) {
        (Action::Exchange(discard), _) => *discard,
        (Action::Play(card), _) => Hand(1 << card.0),
        (Action::Declare(index), Prompt::Declare { options, .. }) => options
            .get(*index)
            .map_or(Hand::EMPTY, |d| d.cards_in(held)),
        _ => Hand::EMPTY,
    };
    Some(object(&[
        ("text", text(&hint.text())),
        ("command", text(&command(&hint.action))),
        ("cards", hand(cards)),
    ]))
}

/// The whole state of the table, from the human's chair.
pub fn state(table: &Table, level: u32, error: Option<&str>) -> String {
    let view = table.view();
    let you = table.you();
    let standing = table.standing();

    let mut deal_number = 0;
    let events: Vec<String> = table
        .events()
        .iter()
        .map(|e| {
            if let Event::DealBegins { number, .. } = e {
                deal_number = *number;
            }
            event(e, deal_number)
        })
        .collect();

    let rubicon = table.events().iter().rev().find_map(|e| match e {
        Event::DealBegins {
            rubicon_permille, ..
        } => Some(*rubicon_permille),
        _ => None,
    });
    let rubicon = rubicon.flatten().map(|p| {
        object(&[
            ("permille", p.to_string()),
            ("words", text(&in_words(f64::from(p) / 1000.0))),
        ])
    });

    let tricks_won = |p: Player| {
        view.tricks
            .iter()
            .filter(|t| t.winner().is_ok_and(|w| w == p))
            .count()
    };

    let deals = list(table.partie().outcomes.iter().map(|o| {
        object(&[
            ("number", o.number.to_string()),
            ("you", o.scores[0].to_string()),
            ("them", o.scores[1].to_string()),
        ])
    }));
    let (partie_you, partie_them) = table.partie().totals();

    let settlement = table.partie().settlement().map(|s| {
        object(&[
            (
                "winner",
                or_null(s.winner.map(|w| {
                    who(if w == piquet_core::partie::Side::A {
                        Who::You
                    } else {
                        Who::Them
                    })
                })),
            ),
            ("points", s.points.to_string()),
            ("rubicon", s.rubicon.to_string()),
        ])
    });

    object(&[
        ("protocol", PROTOCOL.to_string()),
        ("seed", table.seed().to_string()),
        ("level", level.to_string()),
        (
            "opponent",
            object(&[
                ("level", table.opponent().level.to_string()),
                ("skill", text(table.opponent().gloss)),
            ]),
        ),
        ("deal", standing.number.to_string()),
        (
            "you_are",
            if table.cutting() {
                "null".to_string()
            } else {
                text(if you == Player::Elder {
                    "elder"
                } else {
                    "younger"
                })
            },
        ),
        (
            "phase",
            text(if table.cutting() {
                "cut"
            } else {
                view.phase.value()
            }),
        ),
        (
            "standing",
            object(&[
                ("you", standing.mine.to_string()),
                ("them", standing.theirs.to_string()),
                ("deals_left", standing.deals_left.to_string()),
            ]),
        ),
        ("rubicon", or_null(rubicon)),
        ("hand", hand(view.hand)),
        (
            "worth",
            list(holdings(view.hand).iter().map(|h| {
                object(&[
                    ("text", text(&h.text)),
                    ("category", category(h.category)),
                    ("cards", hand(h.cards)),
                    ("score", h.score.to_string()),
                ])
            })),
        ),
        ("discards", hand(view.my_discards)),
        (
            "talon_seen",
            list(view.talon_seen.iter().map(|c| text(&c.code()))),
        ),
        ("talon_remaining", view.talon_remaining.to_string()),
        ("their_discards", view.opponent_discards().to_string()),
        (
            "tricks_played",
            list(view.tricks.iter().map(|t| trick(t, you, true))),
        ),
        (
            "trick",
            or_null(view.current_trick.as_ref().map(|t| trick(t, you, false))),
        ),
        (
            "last_trick",
            or_null(view.tricks.last().map(|t| trick(t, you, true))),
        ),
        (
            "tricks",
            object(&[
                ("you", tricks_won(you).to_string()),
                ("them", tricks_won(you.opponent()).to_string()),
            ]),
        ),
        (
            "score",
            object(&[
                ("you", view.log.total(you).to_string()),
                ("them", view.log.total(you.opponent()).to_string()),
            ]),
        ),
        ("prompt", prompt(&table.prompt(), view.hand)),
        ("aids", aids(table)),
        (
            "can_undo",
            table
                .record()
                .iter()
                .any(|(_, automatic)| !automatic)
                .to_string(),
        ),
        ("hint", or_null(hint(table, view.hand))),
        (
            "record",
            list(
                table
                    .record()
                    .iter()
                    .map(|(a, auto)| text(&entry(a, *auto))),
            ),
        ),
        ("events", list(events)),
        ("deals", deals),
        (
            "partie",
            object(&[
                ("you", partie_you.to_string()),
                ("them", partie_them.to_string()),
            ]),
        ),
        ("settlement", or_null(settlement)),
        ("error", or_null(error.map(text))),
    ])
}

/// The four functions a WebAssembly host calls.
///
/// Strings cross the boundary as UTF-8 in the module's linear memory: the
/// host asks for a buffer with `piquet_alloc`, writes a command into it and
/// calls `piquet_send`; it reads the state from `piquet_state`, which returns
/// a pointer, and `piquet_state_len`. One session per module instance.
pub mod ffi {
    use super::Session;
    use std::cell::RefCell;

    thread_local! {
        static SESSION: RefCell<Option<Session>> = const { RefCell::new(None) };
        static OUT: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) };
        static IN: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) };
    }

    /// A buffer of `len` bytes for the host to write a command into. Valid
    /// until the next call to this function.
    #[no_mangle]
    pub extern "C" fn piquet_alloc(len: usize) -> *mut u8 {
        IN.with(|buffer| {
            let mut buffer = buffer.borrow_mut();
            buffer.clear();
            buffer.resize(len, 0);
            buffer.as_mut_ptr()
        })
    }

    /// Sit down at a new table, discarding any old one.
    #[no_mangle]
    pub extern "C" fn piquet_new(level: u32, seed: u32) {
        SESSION.with(|s| *s.borrow_mut() = Some(Session::new(level, seed)));
        render();
    }

    /// Carry out the command in the `len` bytes just written. 1 if accepted.
    #[no_mangle]
    pub extern "C" fn piquet_send(len: usize) -> u32 {
        let command = IN.with(|buffer| {
            let buffer = buffer.borrow();
            String::from_utf8_lossy(&buffer[..len.min(buffer.len())]).into_owned()
        });
        let accepted = SESSION.with(|s| match s.borrow_mut().as_mut() {
            Some(session) => session.send(&command),
            None => false,
        });
        render();
        u32::from(accepted)
    }

    /// Where the state, as UTF-8 JSON, begins.
    #[no_mangle]
    pub extern "C" fn piquet_state() -> *const u8 {
        OUT.with(|out| out.borrow().as_ptr())
    }

    #[no_mangle]
    pub extern "C" fn piquet_state_len() -> usize {
        OUT.with(|out| out.borrow().len())
    }

    fn render() {
        let json = SESSION.with(|s| {
            s.borrow()
                .as_ref()
                .map_or_else(|| "null".to_string(), |session| session.state())
        });
        OUT.with(|out| *out.borrow_mut() = json.into_bytes());
    }
}
