//! Exact endgame search: memoised minimax, deliberately without alpha-beta.
//!
//! The two do not mix naively -- a pruned branch yields a *bound*, not a value,
//! so storing it in a plain transposition table and reusing it as exact is
//! simply wrong. Doing it properly means tagging every entry as exact, a lower
//! bound or an upper bound. The table alone is fast enough, so the sound and
//! simple version wins until measurement says otherwise.
//!
//! Weights are a pair of integers. The default, [`EVEN`], is the deal
//! objective: a point is a point, whoever scores it. The Python original types
//! these as `float` throughout but its default is a pair of `int`s, so the
//! whole recursion is integer arithmetic; making that a fact about the type
//! rather than an argument about the values is one of the few places this port
//! deliberately differs.

use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};

use crate::cards::Hand;
use crate::scoring::{PIQUE_BONUS, PIQUE_THRESHOLD};

pub const TRICKS: u32 = 12;
pub const CARDS_BONUS: i64 = 10;
pub const CAPOT_BONUS: i64 = 40;

/// A point to each seat is worth the same: the deal objective.
pub const EVEN: (i64, i64) = (1, 1);

const NO_CARD: i32 = -1;

/// A trivial hasher for the transposition table.
///
/// Measured, and the reason this exists: with the standard library's default
/// `SipHash` the eight-trick search took 19.8 ms; with this it takes a
/// fraction of that. SipHash is cryptographic -- it is designed to resist
/// hash-flooding from untrusted input -- and the keys here are our own
/// construction, densely packed and already well distributed. Python's dict
/// hashes an integer to itself, so this is also the fairer comparison.
#[derive(Default)]
struct KeyHasher(u64);

impl Hasher for KeyHasher {
    #[inline]
    fn finish(&self) -> u64 {
        self.0
    }

    #[inline]
    fn write(&mut self, bytes: &[u8]) {
        for &byte in bytes {
            self.0 = (self.0 ^ u64::from(byte)).wrapping_mul(0x0100_0000_01b3);
        }
    }

    #[inline]
    fn write_u128(&mut self, value: u128) {
        // Fold the two halves together with a single multiply. The low half
        // carries elder's hand, which alone is close to unique per node.
        const GOLDEN: u64 = 0x9E37_79B9_7F4A_7C15;
        let low = value as u64;
        let high = (value >> 64) as u64;
        self.0 = (low ^ high.wrapping_mul(GOLDEN)).wrapping_mul(GOLDEN);
    }
}

type Memo = HashMap<u128, i64, BuildHasherDefault<KeyHasher>>;

/// Elder is 0, younger is 1 -- matching `Player.index` in the Python.
pub type Seat = u8;
pub const ELDER: Seat = 0;
pub const YOUNGER: Seat = 1;

#[inline]
fn legal(hand: u32, led: i32) -> u32 {
    if led == NO_CARD {
        return hand;
    }
    let following = hand & (0xFFu32 << ((led >> 3) * 8));
    if following != 0 {
        following
    } else {
        hand
    }
}

/// A card wins only by being higher in the suit led. There are no trumps.
#[inline]
fn beats(played: i32, led: i32) -> bool {
    played >> 3 == led >> 3 && played > led
}

/// Legal plays, skipping cards interchangeable with a cheaper one.
///
/// Two cards in the same suit are equivalent when every card between them has
/// gone: holding the king with the queen and jack out of play, the king and the
/// ten do exactly the same work. Trying only the lower of each run is a sound
/// reduction and cuts the tree substantially.
fn distinct(legal_mask: u32, unplayed: u32, out: &mut [u8; 12]) -> usize {
    let mut count = 0;
    let mut bits = legal_mask;
    while bits != 0 {
        let low = bits.isolate_lowest_one();
        bits ^= low;
        let card = low.trailing_zeros() as i32;

        let below = card - 1;
        let mut skip = false;
        if below >= 0 && below >> 3 == card >> 3 && (unplayed >> below) & 1 == 0 {
            // The card directly beneath has gone; walk down the run and skip
            // this one if an equivalent, cheaper card is also legal.
            let mut probe = below;
            while probe >= 0 && probe >> 3 == card >> 3 && (unplayed >> probe) & 1 == 0 {
                probe -= 1;
            }
            if probe >= 0 && probe >> 3 == card >> 3 && (legal_mask >> probe) & 1 == 1 {
                skip = true;
            }
        }
        if !skip {
            out[count] = card as u8;
            count += 1;
        }
    }
    count
}

#[inline]
fn credit(to_elder: bool, amount: i64, w: (i64, i64)) -> i64 {
    if to_elder {
        w.0 * amount
    } else {
        -w.1 * amount
    }
}

/// Ten for the cards, forty for a capot, nothing at six each.
fn cards_bonus(elder_tricks: u32, w: (i64, i64)) -> i64 {
    if elder_tricks == TRICKS {
        return credit(true, CAPOT_BONUS, w);
    }
    if elder_tricks == 0 {
        return credit(false, CAPOT_BONUS, w);
    }
    if elder_tricks > TRICKS / 2 {
        return credit(true, CARDS_BONUS, w);
    }
    if elder_tricks < TRICKS / 2 {
        return credit(false, CARDS_BONUS, w);
    }
    0
}

/// The transposition key: two hands, a leader, a led card and a trick count.
///
/// Shifts run to 71 and the value occupies up to 75 bits. JavaScript cannot
/// build this with bitwise operators at all -- those top out at 32 -- and a
/// double holds only 53 bits of integer exactly. Here it is simply a `u128`.
#[inline]
fn memo_key(elder: u32, younger: u32, leader: Seat, led: i32, elder_tricks: u32) -> u128 {
    (elder as u128)
        | ((younger as u128) << 32)
        | ((leader as u128) << 64)
        | (((led + 1) as u128) << 65)
        | ((elder_tricks as u128) << 71)
}

fn search(
    elder: u32,
    younger: u32,
    leader: Seat,
    led: i32,
    elder_tricks: u32,
    memo: &mut Memo,
    w: (i64, i64),
) -> i64 {
    if elder == 0 && younger == 0 && led == NO_CARD {
        return cards_bonus(elder_tricks, w);
    }

    let key = memo_key(elder, younger, leader, led, elder_tricks);
    if let Some(&cached) = memo.get(&key) {
        return cached;
    }

    let turn: Seat = if led == NO_CARD { leader } else { 1 - leader };
    let hand = if turn == ELDER { elder } else { younger };
    let unplayed = elder | younger | if led == NO_CARD { 0 } else { 1u32 << led };
    let legal_mask = legal(hand, led);
    let maximising = turn == ELDER;

    let mut options = [0u8; 12];
    let count = distinct(legal_mask, unplayed, &mut options);

    let mut best: Option<i64> = None;
    for &option in options.iter().take(count) {
        let card = option as i32;
        let remaining = hand & !(1u32 << card);

        let value = if led == NO_CARD {
            // A point is scored for every card led, whoever wins the trick.
            credit(turn == ELDER, 1, w)
                + search(
                    if turn == ELDER { remaining } else { elder },
                    if turn == ELDER { younger } else { remaining },
                    leader,
                    card,
                    elder_tricks,
                    memo,
                    w,
                )
        } else {
            let follower_wins = beats(card, led);
            let winner: Seat = if follower_wins { turn } else { leader };
            let next_elder = if turn == ELDER { remaining } else { elder };
            let next_younger = if turn == ELDER { younger } else { remaining };
            let mut gained: i64 = i64::from(follower_wins);
            if next_elder == 0 && next_younger == 0 {
                gained += 1; // the winner of the last trick scores two
            }
            credit(winner == ELDER, gained, w)
                + search(
                    next_elder,
                    next_younger,
                    winner,
                    NO_CARD,
                    elder_tricks + u32::from(winner == ELDER),
                    memo,
                    w,
                )
        };

        best = Some(match best {
            None => value,
            Some(current) if maximising => current.max(value),
            Some(current) => current.min(value),
        });
    }

    let best = best.expect("a position with cards in it always has a legal move");
    memo.insert(key, best);
    best
}

/// Reject a position whose two hands cannot both be true.
///
/// At the start of a trick both players hold the same number of cards; once one
/// has been led the leader holds one fewer. Given anything else the search runs
/// a player out of cards and fails deep in the recursion, which is undebuggable.
fn check_position(elder: Hand, younger: Hand, leader: Seat, led: Option<u8>) -> Result<(), String> {
    let gap = i64::from(led.is_some());
    let (short, tall) = if leader == ELDER {
        (elder, younger)
    } else {
        (younger, elder)
    };
    let difference = i64::from(tall.len()) - i64::from(short.len());
    if difference != gap {
        return Err(format!(
            "seat {leader} leads holding {} cards against {}; the difference must be {gap}",
            short.len(),
            tall.len()
        ));
    }
    Ok(())
}

/// How many distinct positions a search had to remember.
///
/// Growing the transposition table from empty means rehashing everything
/// already in it, repeatedly, and that turned out to cost more than the search
/// itself past about eight tricks. Sizing it up front is worth a great deal,
/// which is why this is exposed rather than kept private to the benchmark.
pub fn expected_positions(cards_each: u32) -> usize {
    // Fitted to measured table sizes, at roughly 1.5x headroom. Both errors
    // cost time, which is why this is a fitted table and not a generous
    // guess: under-reserving rehashes repeatedly, and over-reserving pays to
    // allocate and fault in pages that are never touched. Reserving a million
    // entries for an eight-trick search, which needs 82k, took it from 8.4 ms
    // to 26.2 ms.
    match cards_each {
        0..=4 => 1 << 10,
        5 => 1 << 11,
        6 => 1 << 13,
        7 => 1 << 15,
        8 => 1 << 17,
        9 => 1 << 18,
        10 => 1 << 20,
        11 => 1 << 22,
        _ => 1 << 24,
    }
}

/// The exact value of a position, as elder-minus-younger.
pub fn solve(
    elder: Hand,
    younger: Hand,
    leader: Seat,
    led: Option<u8>,
    elder_tricks: u32,
    weights: (i64, i64),
) -> Result<i64, String> {
    Ok(solve_with_stats(elder, younger, leader, led, elder_tricks, weights)?.0)
}

/// The value of a position, and how many positions had to be remembered.
pub fn solve_with_stats(
    elder: Hand,
    younger: Hand,
    leader: Seat,
    led: Option<u8>,
    elder_tricks: u32,
    weights: (i64, i64),
) -> Result<(i64, usize), String> {
    check_position(elder, younger, leader, led)?;
    let cards_each = elder.len().max(younger.len());
    let mut memo =
        Memo::with_capacity_and_hasher(expected_positions(cards_each), Default::default());
    let value = search(
        elder.0,
        younger.0,
        leader,
        led.map_or(NO_CARD, i32::from),
        elder_tricks,
        &mut memo,
        weights,
    );
    Ok((value, memo.len()))
}

/// The best card for whoever is to play, and what it is worth.
///
/// The value is still elder-minus-younger, so elder takes the largest and
/// younger the smallest. Ties go to the **first** card in hand order, matching
/// Python's `max`, which returns the first maximum where Rust's `max_by_key`
/// returns the last.
pub fn best_card(
    elder: Hand,
    younger: Hand,
    leader: Seat,
    led: Option<u8>,
    elder_tricks: u32,
    weights: (i64, i64),
) -> Result<(u8, i64), String> {
    let values = card_values(elder, younger, leader, led, elder_tricks, weights)?;
    let led_index = led.map_or(NO_CARD, i32::from);
    let turn: Seat = if led_index == NO_CARD {
        leader
    } else {
        1 - leader
    };
    let chosen = if turn == ELDER {
        crate::util::first_max_by_key(&values, |(_, value)| *value)
    } else {
        crate::util::first_min_by_key(&values, |(_, value)| *value)
    };
    chosen
        .copied()
        .ok_or_else(|| "a position with cards in it always has a legal move".to_string())
}

/// What each legal card is worth to whoever is to play.
pub fn card_values(
    elder: Hand,
    younger: Hand,
    leader: Seat,
    led: Option<u8>,
    elder_tricks: u32,
    weights: (i64, i64),
) -> Result<Vec<(u8, i64)>, String> {
    check_position(elder, younger, leader, led)?;
    let led_index = led.map_or(NO_CARD, i32::from);
    let turn: Seat = if led_index == NO_CARD {
        leader
    } else {
        1 - leader
    };
    let hand = if turn == ELDER { elder.0 } else { younger.0 };
    let mut memo = Memo::default();

    let mut out = Vec::new();
    for card in Hand(legal(hand, led_index)).iter() {
        let index = i32::from(card);
        let remaining = hand & !(1u32 << index);
        let value = if led_index == NO_CARD {
            credit(turn == ELDER, 1, weights)
                + search(
                    if turn == ELDER { remaining } else { elder.0 },
                    if turn == ELDER { younger.0 } else { remaining },
                    leader,
                    index,
                    elder_tricks,
                    &mut memo,
                    weights,
                )
        } else {
            let follower_wins = beats(index, led_index);
            let winner: Seat = if follower_wins { turn } else { leader };
            let next_elder = if turn == ELDER { remaining } else { elder.0 };
            let next_younger = if turn == ELDER { younger.0 } else { remaining };
            let mut gained: i64 = i64::from(follower_wins);
            if next_elder == 0 && next_younger == 0 {
                gained += 1;
            }
            credit(winner == ELDER, gained, weights)
                + search(
                    next_elder,
                    next_younger,
                    winner,
                    NO_CARD,
                    elder_tricks + u32::from(winner == ELDER),
                    &mut memo,
                    weights,
                )
        };
        out.push((card, value));
    }
    Ok(out)
}

// -- the agent that uses it --------------------------------------------------

use crate::agents::Agent;
use crate::cards::Card;
use crate::declarations::Declaration;
use crate::heuristics::HeuristicAgent;
use crate::inference::possible_hands;
use crate::observation::View;
use crate::prior::RankPrior;
use crate::scoring::{Category, Player, ScoreLog};
use crate::util::first_max_by;

/// Rung 5: heuristic play early, exact play once the endgame is reachable.
///
/// The cap is the whole design. Solving from twelve cards costs seconds even
/// in Rust (`docs/DESIGN.md` §13.7), and a decision samples `max_worlds`
/// opponent hands rather than one, so the cost per move is that many solves.
/// Eight is what the Python shipped; the measured figures put the interactive
/// frontier at about ten.
///
/// `partie_aware` is **not implemented here**. In the Python it weights the
/// search by what a point is worth in settlement, and it measured *worse* than
/// the flat objective, so it ships off by default -- see `PLAN.md` TODO 1,
/// which wants the objective settled at the leaf instead of linearised on the
/// way down. Porting a flag that is known to lose would have meant making the
/// search generic over its weight type for no gain.
#[derive(Clone)]
pub struct SolverAgent {
    pub fallback: HeuristicAgent,
    pub exact_from: u32,
    pub max_worlds: usize,
    /// Settle at the leaf instead of maximising points in the deal.
    ///
    /// The objective `docs/DESIGN.md` §6.4a says the engine ought to have.
    /// Off by default until it is measured to win, because the previous
    /// attempt at the same idea measured to lose and shipped off for that
    /// reason.
    pub partie_aware: bool,
    /// How likely each consistent opponent hand is. `None` weighs them all
    /// alike, which is what the solver always did; `prior::RankPrior` says
    /// why that is wrong.
    pub prior: Option<RankPrior>,
    /// Its own name, and not the fallback's.
    ///
    /// Delegating to the fallback made it report `L4`, which is not cosmetic:
    /// `tournament::ratings` keys games by name, so a round robin containing
    /// both this and a rung-4 agent merged their results into one entrant
    /// without saying so.
    pub label: String,
}

impl SolverAgent {
    pub fn new(seed: u32) -> SolverAgent {
        SolverAgent {
            fallback: HeuristicAgent::new(crate::heuristics::MAX_LEVEL, seed)
                .expect("the top rung is a valid level"),
            exact_from: 8,
            max_worlds: 30,
            partie_aware: false,
            prior: None,
            label: "solver8".to_string(),
        }
    }

    /// Settle at the leaf. Names itself differently so a tournament cannot
    /// merge it with the flat-objective agent.
    pub fn settling(mut self) -> SolverAgent {
        self.partie_aware = true;
        self.label = format!("settle{}", self.exact_from);
        self
    }

    pub fn named(mut self, name: &str) -> SolverAgent {
        self.label = name.to_string();
        self
    }

    pub fn from_depth(mut self, cards: u32) -> SolverAgent {
        self.exact_from = cards;
        self.label = format!("solver{cards}");
        self
    }

    pub fn worlds(mut self, worlds: usize) -> SolverAgent {
        self.max_worlds = worlds;
        self
    }

    /// Weigh the opponent's possible hands by `prior` rather than alike.
    /// Renamed, so a tournament cannot merge it with the unweighted agent.
    pub fn with_prior(mut self, prior: RankPrior) -> SolverAgent {
        self.prior = Some(prior);
        self.label = format!("{}+prior", self.label);
        self
    }
}

impl Agent for SolverAgent {
    fn name(&self) -> &str {
        &self.label
    }

    fn exchange(&mut self, view: &View) -> Hand {
        self.fallback.exchange(view)
    }

    fn declare(&mut self, view: &View, category: Category) -> Declaration {
        self.fallback.declare(view, category)
    }

    fn play(&mut self, view: &View) -> Card {
        let legal: Vec<Card> = view.legal_plays.cards().collect();
        if legal.len() == 1 {
            return legal[0];
        }
        match self.estimates(view) {
            Some(estimates) => estimates.best(),
            None => self.fallback.play(view),
        }
    }
}

/// What each legal card is worth to a `SolverAgent`, summed over the opponent
/// hands it sampled, each weighted by its prior: in points, or in settlement
/// if it settles, and always to whoever is to play, so larger is better for
/// the mover.
#[derive(Clone, Debug)]
pub struct Estimates {
    /// Every legal card, in legal order, with its weighted total.
    pub totals: Vec<(Card, f64)>,
    /// The sampled worlds the search could evaluate.
    pub worlds: usize,
    /// Their summed weight: the count again, when there is no prior.
    pub weight: f64,
}

impl Estimates {
    /// The card the agent plays: the largest total, ties to the lower rank
    /// and then to the first in legal order.
    pub fn best(&self) -> Card {
        // Python's `max` over the dict returns the FIRST maximum in insertion
        // order, which is `legal` order. Among equal values the lower rank
        // wins, hence the negated rank. Ordered on bits so that ties break
        // identically to the integer path.
        first_max_by(&self.totals, |(card_a, value_a), (card_b, value_b)| {
            value_a
                .total_cmp(value_b)
                .then_with(|| card_b.rank().cmp(&card_a.rank()))
        })
        .map(|(card, _)| *card)
        .expect("a searched position has a legal card")
    }

    /// A card's weighted average over the worlds, or `None` if it is not
    /// legal.
    pub fn mean(&self, card: Card) -> Option<f64> {
        self.totals
            .iter()
            .find(|(c, _)| *c == card)
            .map(|(_, total)| total / self.weight)
    }
}

impl SolverAgent {
    /// What it would play by, without playing: `None` where it would not
    /// search -- one legal card, more in hand than `exact_from`, or no
    /// consistent world to search.
    ///
    /// Draws its worlds from the agent's own generator exactly as `play`
    /// does, so a clone asked first reports the card the original then
    /// plays.
    pub fn estimates(&mut self, view: &View) -> Option<Estimates> {
        let legal: Vec<Card> = view.legal_plays.cards().collect();
        if legal.len() <= 1 || view.hand.len() > self.exact_from {
            return None;
        }

        let worlds = possible_hands(view, Some(self.max_worlds), true, &mut self.fallback.rng);
        if worlds.is_empty() {
            return None;
        }

        let mut totals: Vec<(Card, f64)> = legal.iter().map(|c| (*c, 0.0)).collect();
        let mut searched = 0usize;
        let mut weight = 0.0f64;
        for opponent_hand in worlds {
            let Ok(values) = self.values_in(view, opponent_hand) else {
                continue;
            };
            searched += 1;
            // Without a prior every world weighs exactly one, and `1.0 * v`
            // is `v` bit for bit, so the unweighted search is unchanged.
            let w = self.prior.map_or(1.0, |p| p.weight(opponent_hand));
            weight += w;
            for (card, value) in values {
                if let Some(slot) = totals.iter_mut().find(|(c, _)| *c == card) {
                    slot.1 += w * value;
                }
            }
        }

        // Every world failing to search leaves every total at zero, and the
        // original then played the first of the tied cards by the same rule;
        // `best` does exactly that, so the count only matters for `mean`.
        Some(Estimates {
            totals,
            worlds: searched.max(1),
            weight: if searched == 0 { 1.0 } else { weight },
        })
    }

    /// What each legal card is worth in one world -- the opponent holding
    /// `opponent_hand` -- by this agent's objective, to whoever is to play,
    /// in legal order. `estimates` sums this over the worlds it samples;
    /// handed the true hand, it says what a card was really worth.
    pub fn values_in(&self, view: &View, opponent_hand: Hand) -> Result<Vec<(Card, f64)>, String> {
        let elder_tricks = view
            .tricks
            .iter()
            .filter(|t| t.winner().is_ok_and(|w| w == Player::Elder))
            .count() as u32;
        let i_lead = view.current_trick.is_none();
        let leader = if i_lead {
            if view.me == Player::Elder {
                ELDER
            } else {
                YOUNGER
            }
        } else if view.opponent() == Player::Elder {
            ELDER
        } else {
            YOUNGER
        };
        let led = view.current_trick.map(|t| t.led.0);
        let sign: i64 = if view.me == Player::Elder { 1 } else { -1 };
        let (elder, younger) = if view.me == Player::Elder {
            (view.hand, opponent_hand)
        } else {
            (opponent_hand, view.hand)
        };

        let values: Vec<(u8, f64)> = match self.settling_context(view) {
            Some(ctx) => card_settlements(elder, younger, leader, led, elder_tricks, &ctx)?,
            None => card_values(elder, younger, leader, led, elder_tricks, EVEN)?
                .into_iter()
                .map(|(c, v)| (c, v as f64))
                .collect(),
        };
        Ok(values
            .into_iter()
            .map(|(card, value)| (Card(card), sign as f64 * value))
            .collect())
    }

    /// The settling objective needs the partie, and there may not be one:
    /// a deal played on its own has no standing, and then the two
    /// objectives coincide anyway.
    fn settling_context(&self, view: &View) -> Option<Settling> {
        if !self.partie_aware {
            return None;
        }
        view.partie.map(|standing| {
            let (elder_side, younger_side) = if view.me == Player::Elder {
                (standing.mine, standing.theirs)
            } else {
                (standing.theirs, standing.mine)
            };
            let banked = settled_log(view);
            Settling {
                elder_side,
                younger_side,
                elder_so_far: banked.total(Player::Elder),
                younger_so_far: banked.total(Player::Younger),
                deals_left: standing.deals_left,
                // The seat alternates, so whoever sits elder now sits
                // younger in the next deal.
                elder_first_next: false,
            }
        })
    }
}

// ===========================================================================
// Settling at the leaf
//
// `docs/DESIGN.md` §6.4a: the objective above the deal is wrong. The search
// maximises points *in a deal*, and the game is a partie settled by the
// rubicon, where a loser short of a hundred pays the **sum** of both scores
// rather than the difference. The first attempt at a remedy priced a point in
// settlement and fed it in as a linear weight; it lost 0–9–66 over 75 mirrored
// last deals, because a marginal price is a linearisation and the settlement
// is violently non-linear exactly where the price is extreme.
//
// The remedy the document asks for is to carry both totals to the leaf and
// settle there. That costs more than it sounds, and the reason is worth
// writing down.
//
// **Play points are path-dependent.** Elder's points are
// `(tricks he led) + (tricks he won as follower) + (1 if he won the last)`.
// Writing E for his trick count and Q for the tricks he both led and won, that
// comes to `1 + 2E − Q` — and Q is not recoverable from E. Two lines of play
// reaching the same cards-remaining position can therefore have split the
// points differently, so the accumulated pair has to sit in the memo key.
//
// That is what makes this expensive: positions the additive search merged are
// now distinct. The key grows from 75 bits to 87, which a `u128` still holds,
// but the state space multiplies. Whether the objective is worth the depth it
// costs is a question for measurement, not for argument.
// ===========================================================================

/// The log as it will be scored, so far as that is already decided.
///
/// A repique is made in declarations alone, so it is settled before a card is
/// played; a pique is settled the moment elder reaches thirty with younger
/// still on nothing. Neither enters the log until the deal is finished, and a
/// settlement read off `log.total` is sixty points wrong in a repique deal --
/// which near the rubicon is the difference between paying the difference and
/// paying the sum.
///
/// Before elder has led, younger has not declared, and a bonus read off the
/// log as it stands could be one her declarations are about to deny him.
pub fn settled_log(view: &View) -> ScoreLog {
    if view.tricks.is_empty() && view.current_trick.is_none() {
        view.log.clone()
    } else {
        view.log.with_bonuses()
    }
}

/// Everything outside the play that the settlement depends on.
#[derive(Clone, Copy, Debug)]
pub struct Settling {
    /// The partie score of whoever sits elder, before this deal.
    pub elder_side: i32,
    /// And of whoever sits younger.
    pub younger_side: i32,
    /// Points already banked this deal, by seat: declarations, any play
    /// points made before the search begins, and a pique or repique already
    /// decided (`settled_log`).
    pub elder_so_far: i32,
    pub younger_so_far: i32,
    /// Deals still to play, counting this one.
    pub deals_left: usize,
    /// Whether the side sitting elder now sits elder in the *next* deal.
    /// It never does — the seat alternates — but it is carried explicitly
    /// rather than assumed, because `expected_settlement` needs it and the
    /// convention is easy to invert by accident.
    pub elder_first_next: bool,
}

/// Whether elder has won a pique by this point in the play.
///
/// A pique or repique already decided arrives in `ctx`, banked. One still
/// *live* when the search begins -- younger on nothing, elder short of thirty
/// -- is made or denied by the play, in order: the declarations are all
/// reckoned before a card is led (Law 67), so from here on elder wins it at
/// the first point that brings him to thirty while younger's count is still
/// nothing, and loses it at her first point. The same rule as
/// `ScoreLog::pique`, walked one point at a time. Only the settling search
/// counts it; the flat search stays as it was, bit for bit with the golden
/// vectors.
#[inline]
fn piqued_after(already: bool, elder_pts: i32, younger_pts: i32, ctx: &Settling) -> bool {
    already
        || (ctx.younger_so_far == 0
            && younger_pts == 0
            && ctx.elder_so_far < PIQUE_THRESHOLD
            && ctx.elder_so_far + elder_pts >= PIQUE_THRESHOLD)
}

/// The settlement to elder's **side**, in points, at the end of the deal,
/// counting a pique made in the play (`piqued_after`).
fn settle(
    elder_tricks: u32,
    elder_pts: i32,
    younger_pts: i32,
    piqued: bool,
    ctx: &Settling,
) -> f64 {
    let (elder_bonus, younger_bonus) = if elder_tricks == TRICKS {
        (CAPOT_BONUS as i32, 0)
    } else if elder_tricks == 0 {
        (0, CAPOT_BONUS as i32)
    } else if elder_tricks > TRICKS / 2 {
        (CARDS_BONUS as i32, 0)
    } else if elder_tricks < TRICKS / 2 {
        (0, CARDS_BONUS as i32)
    } else {
        (0, 0)
    };

    let pique = if piqued { PIQUE_BONUS } else { 0 };
    let elder_deal = ctx.elder_so_far + elder_pts + elder_bonus + pique;
    let younger_deal = ctx.younger_so_far + younger_pts + younger_bonus;

    crate::chances::expected_settlement(
        ctx.elder_side + elder_deal,
        ctx.younger_side + younger_deal,
        ctx.deals_left.saturating_sub(1),
        ctx.elder_first_next,
    )
}

#[inline]
#[allow(clippy::too_many_arguments)]
fn settlement_key(
    elder: u32,
    younger: u32,
    leader: Seat,
    led: i32,
    elder_tricks: u32,
    elder_pts: i32,
    younger_pts: i32,
    piqued: bool,
) -> u128 {
    memo_key(elder, younger, leader, led, elder_tricks)
        | ((elder_pts as u128 & 0x3F) << 75)
        | ((younger_pts as u128 & 0x3F) << 81)
        | (u128::from(piqued) << 87)
}

type SettlementMemo = std::collections::HashMap<u128, f64, BuildHasherDefault<KeyHasher>>;

#[allow(clippy::too_many_arguments)]
fn search_settlement(
    elder: u32,
    younger: u32,
    leader: Seat,
    led: i32,
    elder_tricks: u32,
    elder_pts: i32,
    younger_pts: i32,
    piqued: bool,
    memo: &mut SettlementMemo,
    ctx: &Settling,
) -> f64 {
    if elder == 0 && younger == 0 && led == NO_CARD {
        return settle(elder_tricks, elder_pts, younger_pts, piqued, ctx);
    }

    let key = settlement_key(
        elder,
        younger,
        leader,
        led,
        elder_tricks,
        elder_pts,
        younger_pts,
        piqued,
    );
    if let Some(&cached) = memo.get(&key) {
        return cached;
    }

    let turn: Seat = if led == NO_CARD { leader } else { 1 - leader };
    let hand = if turn == ELDER { elder } else { younger };
    let unplayed = elder | younger | if led == NO_CARD { 0 } else { 1u32 << led };
    let legal_mask = legal(hand, led);
    let maximising = turn == ELDER;

    let mut options = [0u8; 12];
    let count = distinct(legal_mask, unplayed, &mut options);

    let mut best: Option<f64> = None;
    for &option in options.iter().take(count) {
        let card = option as i32;
        let remaining = hand & !(1u32 << card);

        let value = if led == NO_CARD {
            // A point for every card led, whoever wins the trick.
            let (e, y) = if turn == ELDER {
                (elder_pts + 1, younger_pts)
            } else {
                (elder_pts, younger_pts + 1)
            };
            search_settlement(
                if turn == ELDER { remaining } else { elder },
                if turn == ELDER { younger } else { remaining },
                leader,
                card,
                elder_tricks,
                e,
                y,
                piqued_after(piqued, e, y, ctx),
                memo,
                ctx,
            )
        } else {
            let follower_wins = beats(card, led);
            let winner: Seat = if follower_wins { turn } else { leader };
            let next_elder = if turn == ELDER { remaining } else { elder };
            let next_younger = if turn == ELDER { younger } else { remaining };
            let mut gained: i32 = i32::from(follower_wins);
            if next_elder == 0 && next_younger == 0 {
                gained += 1; // the winner of the last trick scores two
            }
            let (e, y) = if winner == ELDER {
                (elder_pts + gained, younger_pts)
            } else {
                (elder_pts, younger_pts + gained)
            };
            search_settlement(
                next_elder,
                next_younger,
                winner,
                NO_CARD,
                elder_tricks + u32::from(winner == ELDER),
                e,
                y,
                piqued_after(piqued, e, y, ctx),
                memo,
                ctx,
            )
        };

        best = Some(match best {
            None => value,
            Some(current) if maximising => current.max(value),
            Some(current) => current.min(value),
        });
    }

    let best = best.expect("a position with cards in it always has a legal move");
    memo.insert(key, best);
    best
}

/// What each legal card is worth **in settlement** to whoever is to play.
///
/// The partie objective, done properly: both totals carried to the leaf and
/// settled there, rather than collapsed to a weighted scalar on the way down.
pub fn card_settlements(
    elder: Hand,
    younger: Hand,
    leader: Seat,
    led: Option<u8>,
    elder_tricks: u32,
    ctx: &Settling,
) -> Result<Vec<(u8, f64)>, String> {
    check_position(elder, younger, leader, led)?;
    let led_index = led.map_or(NO_CARD, i32::from);
    let turn: Seat = if led_index == NO_CARD {
        leader
    } else {
        1 - leader
    };
    let hand = if turn == ELDER { elder.0 } else { younger.0 };
    let mut memo = SettlementMemo::default();

    let mut out = Vec::new();
    for card in Hand(legal(hand, led_index)).iter() {
        let index = i32::from(card);
        let remaining = hand & !(1u32 << index);
        let value = if led_index == NO_CARD {
            let (e, y) = if turn == ELDER { (1, 0) } else { (0, 1) };
            search_settlement(
                if turn == ELDER { remaining } else { elder.0 },
                if turn == ELDER { younger.0 } else { remaining },
                leader,
                index,
                elder_tricks,
                e,
                y,
                piqued_after(false, e, y, ctx),
                &mut memo,
                ctx,
            )
        } else {
            let follower_wins = beats(index, led_index);
            let winner: Seat = if follower_wins { turn } else { leader };
            let next_elder = if turn == ELDER { remaining } else { elder.0 };
            let next_younger = if turn == ELDER { younger.0 } else { remaining };
            let mut gained: i32 = i32::from(follower_wins);
            if next_elder == 0 && next_younger == 0 {
                gained += 1;
            }
            let (e, y) = if winner == ELDER {
                (gained, 0)
            } else {
                (0, gained)
            };
            search_settlement(
                next_elder,
                next_younger,
                winner,
                NO_CARD,
                elder_tricks + u32::from(winner == ELDER),
                e,
                y,
                piqued_after(false, e, y, ctx),
                &mut memo,
                ctx,
            )
        };
        out.push((card, value));
    }
    Ok(out)
}
