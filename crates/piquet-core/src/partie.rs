//! The partie: six deals, the alternating deal, and the rubicon.
//!
//! A deal is not the game. Piquet is played over six deals with the deal
//! alternating, and settled once at the end under the **rubicon** rule: the
//! loser pays the *difference* plus a hundred if he reached a hundred himself,
//! and the *sum* plus a hundred if he did not.
//!
//! That one clause is why maximising points in a deal is not the same thing as
//! playing well. 105 to 101 pays 104; 97 to 89 pays 286, nearly three times as
//! much for a closer game. A player on 95 with one deal left is not trying to
//! win the deal, he is trying to cross a line -- and his opponent has a reason
//! to keep him *down* that has no counterpart inside a single deal at all.
//!
//! Seats and people are different things here, and the module keeps them
//! apart. `Player::Elder` and `Player::Younger` are seats and change hands
//! every deal. A `Side` plays the whole partie, and the rubicon is reckoned
//! over a side.
//!
//! Authority: pagat.com.

use crate::scoring::Player;

/// Deals in a partie, before any tie-break.
pub const DEALS_IN_PARTIE: usize = 6;
/// "If the scores are equal after 6 deals, two more hands are played." Both of
/// them: each player deals one, so neither gains the seat by breaking the tie.
pub const EXTRA_DEALS: usize = 2;
/// The line. Reaching it changes what losing costs by a factor of about three.
pub const RUBICON: i32 = 100;
/// Added to every settlement, difference or sum alike.
pub const PARTIE_BONUS: i32 = 100;

/// One of the two people at the table, as opposed to one of the two seats.
///
/// The two need different names or they will be confused exactly once, and
/// expensively -- the rubicon is reckoned over a person's six deals, not over
/// a chair.
///
/// Note that `Side::A` is 0. In Python that made it *falsy*, and testing a
/// winner for truthiness reported a drawn partie that had a winner. Rust has
/// no such trap, but the comparison is written explicitly anyway.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Side {
    A = 0,
    B = 1,
}

impl Side {
    pub fn other(self) -> Side {
        match self {
            Side::A => Side::B,
            Side::B => Side::A,
        }
    }

    #[inline]
    pub fn index(self) -> usize {
        self as usize
    }

    pub fn name(self) -> &'static str {
        match self {
            Side::A => "A",
            Side::B => "B",
        }
    }
}

/// Where the partie stands, from one side's chair.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Standing {
    pub mine: i32,
    pub theirs: i32,
    pub deals_left: usize,
    pub number: usize,
}

impl Standing {
    pub fn reversed(self) -> Standing {
        Standing {
            mine: self.theirs,
            theirs: self.mine,
            deals_left: self.deals_left,
            number: self.number,
        }
    }

    pub fn is_last_deal(self) -> bool {
        self.deals_left <= 1
    }

    pub fn short_of_the_rubicon(self) -> bool {
        self.mine < RUBICON
    }
}

/// One finished deal, recorded in side order.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct DealOutcome {
    pub number: usize,
    pub elder: Side,
    pub scores: [i32; 2],
}

impl DealOutcome {
    pub fn score_of(self, side: Side) -> i32 {
        self.scores[side.index()]
    }
}

/// What the partie pays.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Settlement {
    pub winner: Option<Side>,
    pub points: i32,
    pub rubicon: bool,
}

/// A partie in progress, or finished.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Partie {
    pub opening_dealer: Side,
    pub outcomes: Vec<DealOutcome>,
}

impl Partie {
    pub fn new(opening_dealer: Side) -> Partie {
        Partie {
            opening_dealer,
            outcomes: Vec::new(),
        }
    }

    /// The number of the deal about to be played, counting from one.
    pub fn number(&self) -> usize {
        self.outcomes.len() + 1
    }

    /// Which side is elder in a given deal. The dealer is not elder.
    pub fn elder_in(&self, number: usize) -> Side {
        if number % 2 == 1 {
            self.opening_dealer.other()
        } else {
            self.opening_dealer
        }
    }

    pub fn elder(&self) -> Side {
        self.elder_in(self.number())
    }

    pub fn totals(&self) -> (i32, i32) {
        let mut totals = [0i32; 2];
        for outcome in &self.outcomes {
            totals[0] += outcome.scores[0];
            totals[1] += outcome.scores[1];
        }
        (totals[0], totals[1])
    }

    pub fn score_of(&self, side: Side) -> i32 {
        let (a, b) = self.totals();
        match side {
            Side::A => a,
            Side::B => b,
        }
    }

    /// Deals still to play, counting the one about to begin.
    ///
    /// Six, unless the scores come out level after them, in which case two
    /// more are played -- both of them, whatever happens in the first.
    pub fn deals_left(&self) -> usize {
        let played = self.outcomes.len();
        if played < DEALS_IN_PARTIE {
            return DEALS_IN_PARTIE - played;
        }
        if played >= DEALS_IN_PARTIE + EXTRA_DEALS {
            return 0;
        }
        let (first, second) = self.totals();
        if played == DEALS_IN_PARTIE && first != second {
            return 0;
        }
        DEALS_IN_PARTIE + EXTRA_DEALS - played
    }

    pub fn complete(&self) -> bool {
        self.deals_left() == 0
    }

    /// Where things stand, from the chair of whoever is elder next.
    pub fn standing(&self) -> Standing {
        let elder = self.elder();
        Standing {
            mine: self.score_of(elder),
            theirs: self.score_of(elder.other()),
            deals_left: self.deals_left(),
            number: self.number(),
        }
    }

    /// Enter a deal by its two scores, given in *seat* order.
    ///
    /// Kept separate from recording a finished `Deal` so that a partie can be
    /// replayed from a written score sheet, which is all a period account of a
    /// game ever gives you.
    pub fn record_scores(&self, elder: i32, younger: i32) -> Result<Partie, String> {
        if self.complete() {
            return Err("the partie is already settled".to_string());
        }
        let number = self.number();
        let elder_side = self.elder_in(number);
        let scores = match elder_side {
            Side::A => [elder, younger],
            Side::B => [younger, elder],
        };
        let mut outcomes = self.outcomes.clone();
        outcomes.push(DealOutcome {
            number,
            elder: elder_side,
            scores,
        });
        Ok(Partie {
            opening_dealer: self.opening_dealer,
            outcomes,
        })
    }

    /// What the partie pays, or `None` while it is still being played.
    ///
    /// The guard is on the **loser's** score, not the winner's: Britannica is
    /// explicit that the loser is rubiconed "even if the winner also fails" to
    /// reach a hundred. Two players who crawl to 60 and 40 settle for 200.
    pub fn settlement(&self) -> Option<Settlement> {
        if !self.complete() {
            return None;
        }
        let (first, second) = self.totals();
        if first == second {
            return Some(Settlement {
                winner: None,
                points: 0,
                rubicon: false,
            });
        }
        let winner = if first > second { Side::A } else { Side::B };
        let high = first.max(second);
        let low = first.min(second);
        Some(if low < RUBICON {
            Settlement {
                winner: Some(winner),
                points: high + low + PARTIE_BONUS,
                rubicon: true,
            }
        } else {
            Settlement {
                winner: Some(winner),
                points: high - low + PARTIE_BONUS,
                rubicon: false,
            }
        })
    }
}

/// Which seat a side holds in a given deal.
pub fn seat_of(elder_side: Side, side: Side) -> Player {
    if side == elder_side {
        Player::Elder
    } else {
        Player::Younger
    }
}
