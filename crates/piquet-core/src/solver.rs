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
