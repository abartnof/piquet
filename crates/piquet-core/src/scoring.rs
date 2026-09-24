//! Scoring: an ordered event log, and the derivation of pique and repique.
//!
//! Piquet's two bonuses read the *same* points over *different sets of
//! categories*. Repique is made "in his hand alone" and ignores play entirely;
//! pique is made "in hand and play" and counts the points scored for leading
//! and winning tricks as well. Both ask the same question -- did this player
//! reach thirty before the other reckoned anything at all? -- and both must ask
//! it of Law 67's **order of precedence**, not the order the log was written
//! in.
//!
//! Those two orders genuinely differ, which is the whole reason scoring is a
//! log rather than a running total. Younger's declarations are *entered* when
//! elder leads to the first trick, long after elder entered his own, but they
//! *reckon* in their proper categories.
//!
//! Authority: Cavendish, *The Laws of Piquet adopted by the Portland and Turf
//! Clubs* (1892), laws 66-69.

pub const PIQUE_THRESHOLD: i32 = 30;
pub const PIQUE_BONUS: i32 = 30;
pub const REPIQUE_BONUS: i32 = 60;

/// The two seats. Elder is the non-dealer, and has the advantage.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Player {
    Elder,
    Younger,
}

impl Player {
    pub fn opponent(self) -> Player {
        match self {
            Player::Elder => Player::Younger,
            Player::Younger => Player::Elder,
        }
    }

    /// A stable slot, so per-player state can live in a two-element array.
    #[inline]
    pub fn index(self) -> usize {
        match self {
            Player::Elder => 0,
            Player::Younger => 1,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Player::Elder => "elder",
            Player::Younger => "younger",
        }
    }
}

/// Cavendish, Law 67: the order in which scores reckon.
///
/// The discriminants *are* the reckoning order, so sorting by them is the
/// rule. `Bonus` is our own addition, placed last so a pique or repique can be
/// stored in the log without disturbing either derivation.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
#[repr(u8)]
pub enum Category {
    CarteBlanche = 1,
    Point = 2,
    Sequences = 3,
    Sets = 4,
    Play = 5,
    Cards = 6,
    Bonus = 7,
}

impl Category {
    pub const ALL: [Category; 7] = [
        Category::CarteBlanche,
        Category::Point,
        Category::Sequences,
        Category::Sets,
        Category::Play,
        Category::Cards,
        Category::Bonus,
    ];

    pub fn name(self) -> &'static str {
        match self {
            Category::CarteBlanche => "CARTE_BLANCHE",
            Category::Point => "POINT",
            Category::Sequences => "SEQUENCES",
            Category::Sets => "SETS",
            Category::Play => "PLAY",
            Category::Cards => "CARDS",
            Category::Bonus => "BONUS",
        }
    }
}

/// Categories that count towards a repique -- "in his hand alone".
pub const DECLARATION_CATEGORIES: [Category; 4] = [
    Category::CarteBlanche,
    Category::Point,
    Category::Sequences,
    Category::Sets,
];

/// ...and the one more that counts towards a pique, made "in hand and play".
///
/// The cards are excluded deliberately: "a capot reckons after points made in
/// play; and, therefore, does not count toward a pique" (Cavendish, Law 69).
pub const PIQUE_CATEGORIES: [Category; 5] = [
    Category::CarteBlanche,
    Category::Point,
    Category::Sequences,
    Category::Sets,
    Category::Play,
];

/// One score, by one player, from one source.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct ScoreEvent {
    pub player: Player,
    pub amount: i32,
    pub category: Category,
    pub detail: String,
}

/// An append-only record of every point scored in a deal.
///
/// Immutable: `record` returns a new log. Deals are short -- a few dozen
/// events -- so copying is cheap, and immutability keeps the log safe to hold
/// inside a search node.
#[derive(Clone, PartialEq, Eq, Debug, Default)]
pub struct ScoreLog {
    pub events: Vec<ScoreEvent>,
}

impl ScoreLog {
    pub fn new() -> ScoreLog {
        ScoreLog::default()
    }

    /// Return a new log with one more score in it.
    ///
    /// Scores must be positive. An equality scores for neither player, so
    /// nothing is logged: recording a zero would wrongly look like the
    /// adversary had reckoned something, and would silently break both
    /// bonuses.
    pub fn record(
        &self,
        player: Player,
        amount: i32,
        category: Category,
        detail: &str,
    ) -> Result<ScoreLog, String> {
        if amount <= 0 {
            return Err(format!(
                "a score must be positive, got {amount}; an equality is \
                 recorded by logging nothing at all"
            ));
        }
        let mut events = self.events.clone();
        events.push(ScoreEvent {
            player,
            amount,
            category,
            detail: detail.to_string(),
        });
        Ok(ScoreLog { events })
    }

    pub fn len(&self) -> usize {
        self.events.len()
    }

    pub fn is_empty(&self) -> bool {
        self.events.is_empty()
    }

    pub fn total(&self, player: Player) -> i32 {
        self.events
            .iter()
            .filter(|e| e.player == player)
            .map(|e| e.amount)
            .sum()
    }

    /// A breakdown for the tutor: what this player scored, and for what.
    pub fn by_category(&self, player: Player) -> Vec<(Category, i32)> {
        let mut out: Vec<(Category, i32)> = Vec::new();
        for event in self.events.iter().filter(|e| e.player == player) {
            match out.iter_mut().find(|(c, _)| *c == event.category) {
                Some(entry) => entry.1 += event.amount,
                None => out.push((event.category, event.amount)),
            }
        }
        out
    }

    /// Who reached thirty over these categories before the other scored.
    ///
    /// The categories are walked in Law 67's order of precedence, which is not
    /// the order of the log. Within a category the log order stands, which
    /// matters only for points made in play, since no other category can score
    /// for both players.
    fn first_to_thirty(&self, categories: &[Category]) -> Option<Player> {
        let mut running = [0i32; 2];
        for category in categories {
            for event in self.events.iter().filter(|e| e.category == *category) {
                if running[event.player.opponent().index()] > 0 {
                    return None;
                }
                running[event.player.index()] += event.amount;
                if running[event.player.index()] >= PIQUE_THRESHOLD {
                    return Some(event.player);
                }
            }
        }
        None
    }

    /// Law 68: thirty made "in his hand alone", reckoning in category order.
    pub fn repique(&self) -> Option<Player> {
        self.first_to_thirty(&DECLARATION_CATEGORIES)
    }

    /// Law 69: thirty made "in hand and play" before the opponent reckons.
    ///
    /// Only elder can score it, and that falls out of the precedence order
    /// rather than being stipulated. A player scores a pique or a repique,
    /// never both.
    pub fn pique(&self) -> Option<Player> {
        if self.repique().is_some() {
            return None;
        }
        self.first_to_thirty(&PIQUE_CATEGORIES)
    }

    /// Return a log with the pique or repique bonus appended, if any.
    ///
    /// Idempotent, so it is safe to call at the end of a deal without first
    /// checking whether it has already been applied.
    pub fn with_bonuses(&self) -> ScoreLog {
        if self.events.iter().any(|e| e.category == Category::Bonus) {
            return self.clone();
        }
        if let Some(winner) = self.repique() {
            return self
                .record(winner, REPIQUE_BONUS, Category::Bonus, "repique")
                .expect("the repique bonus is positive");
        }
        if let Some(winner) = self.pique() {
            return self
                .record(winner, PIQUE_BONUS, Category::Bonus, "pique")
                .expect("the pique bonus is positive");
        }
        self.clone()
    }
}
