//! Which hands the opponent can possibly hold.
//!
//! What the dialogue gives up is **graded, not all-or-nothing**. The
//! candidates kept are those satisfying the most rungs of [`LADDER`], so an
//! opponent who conceals costs you the assumptions about her honesty and none
//! of the deductions. Being lied to by omission is exactly what sinking is
//! bought for, and it should cost what it buys and no more.
//!
//! An earlier version ran all four rungs as a single filter and dropped all
//! four the moment one failed -- so a player who concealed a sequence also
//! stopped the engine believing cards she had physically shown it. Measured
//! against a sinking opponent, her own exposed cards ruled out 88% of the
//! candidate set that was being kept.

use crate::cards::{Card, Hand, Suit};
use crate::combos::{best_point, best_sequence, best_set};
use crate::declarations::{Announcement, Combination};
use crate::observation::View;
use crate::rng::Rng;
use crate::scoring::{Category, Player};

/// How many cards the opponent is holding right now.
///
/// Only decrement for a trick in progress if the *opponent* led it. An earlier
/// version decremented whenever any trick was open, which was invisible in
/// practice but would have generated candidate hands of the wrong length.
pub fn opponent_hand_size(view: &View) -> usize {
    let mut remaining = 12i32 - view.tricks.len() as i32;
    if let Some(trick) = view.current_trick {
        if trick.leader == view.opponent() {
            remaining -= 1;
        }
    }
    remaining.max(0) as usize
}

/// Suits the opponent has shown they cannot hold.
///
/// Failing to follow suit is a permanent, certain fact -- the cheapest and
/// hardest information in the game.
pub fn known_voids(view: &View) -> Vec<Suit> {
    let mut voids = Vec::new();
    for trick in &view.tricks {
        let Some(followed) = trick.followed else {
            continue;
        };
        if trick.leader == view.me
            && followed.suit() != trick.led.suit()
            && !voids.contains(&trick.led.suit())
        {
            voids.push(trick.led.suit());
        }
    }
    voids
}

/// Every card the opponent has already put on the table.
pub fn opponent_played(view: &View) -> Hand {
    let mut played = 0u32;
    for trick in view.tricks.iter().chain(view.current_trick.iter()) {
        if trick.leader != view.me {
            played |= 1 << trick.led.0;
        } else if let Some(followed) = trick.followed {
            played |= 1 << followed.0;
        }
    }
    Hand(played)
}

fn best_in(category: Category, hand: Hand) -> Option<Combination> {
    match category {
        Category::Point => best_point(hand).map(Combination::Point),
        Category::Sequences => best_sequence(hand).map(Combination::Sequence),
        Category::Sets => best_set(hand).map(Combination::Set),
        _ => None,
    }
}

const DECLARED_CATEGORIES: [Category; 3] = [Category::Point, Category::Sequences, Category::Sets];

/// Cards the opponent laid on the table. Not an assumption at all.
///
/// Those cards were exposed. No amount of concealment elsewhere in the
/// dialogue can take them back, so this is the one rung never dropped.
fn shown_cards_are_held(original: Hand, view: &View) -> bool {
    view.seen.iter().all(|c| c.is_supported_by(original))
}

/// A declaration is a floor. You may declare less than you hold, never more.
///
/// Cavendish's examples of sinking are all understatements and never
/// overstatements, which `Declaration::validate` refuses outright. So "a
/// quint" means a sequence of five *or better*.
fn at_least_what_was_claimed(original: Hand, view: &View) -> bool {
    view.heard.iter().all(|announcement| {
        best_in(announcement.category, original)
            .is_some_and(|best| best.key().0 >= announcement.primary)
    })
}

/// Whether a holding is worse than a call. A call carries its tie-break only
/// when the shapes matched, and then only the tie-break can decide.
fn short_of(key: (u32, u32), called: Announcement) -> bool {
    match called.tiebreak {
        None => key.0 < called.primary,
        Some(tiebreak) => key.0 == called.primary && key.1 < tiebreak,
    }
}

/// Whether a holding beats a call.
fn beyond(key: (u32, u32), called: Announcement) -> bool {
    match called.tiebreak {
        None => key.0 > called.primary,
        Some(tiebreak) => key.0 == called.primary && key.1 > tiebreak,
    }
}

/// What she did not name, read against what she answered.
///
/// She names only what she won, so a category she is silent in is not one
/// she held nothing in. The answers are public, and they say what her silence
/// means. If he called and she said "good", she holds less than his call. If
/// she said "not good" and has not named it yet -- she names nothing until he
/// has led -- she holds more. "Equal" means the same. Where there was no call
/// to answer, silence means nothing held.
///
/// An earlier version read every silence as "nothing held", in unsettled
/// categories too. That was only ever right because her beaten holdings were
/// being named, which they should not have been; and at elder's blind first
/// lead, when she has named nothing at all, it ruled out every candidate and
/// so quietly told him nothing, discarding answers he had heard.
///
/// True of an honest declarer and false of one who sank.
fn silence_agrees_with_the_answers(original: Hand, view: &View) -> bool {
    for (category, winner) in &view.outcomes {
        if !DECLARED_CATEGORIES.contains(category)
            || view.heard.iter().any(|a| a.category == *category)
        {
            continue;
        }
        let best = best_in(*category, original).map(|c| c.key());
        let called = if view.me == Player::Elder {
            view.said.iter().copied().find(|a| a.category == *category)
        } else {
            None
        };
        let consistent = match called {
            None if view.me == Player::Elder && *winner == Some(view.opponent()) => {
                // She won it and has not named it yet: she holds something.
                best.is_some()
            }
            None => best.is_none(),
            Some(called) if *winner == Some(view.me) => {
                best.is_none_or(|key| short_of(key, called))
            }
            Some(called) if *winner == Some(view.opponent()) => {
                best.is_some_and(|key| beyond(key, called))
            }
            Some(called) => best.is_some() && best == called.tiebreak.map(|t| (called.primary, t)),
        };
        if !consistent {
            return false;
        }
    }
    true
}

/// She named her best holding, exactly, not some lesser one.
///
/// The first rung to go, because partial understatement is the commonest form
/// of sinking and the one Cavendish spends his examples on.
fn what_was_named_was_the_best(original: Hand, view: &View) -> bool {
    view.heard
        .iter()
        .all(|a| a.matches(best_in(a.category, original)))
}

/// What the dialogue tells you, from what survives any amount of concealment
/// to what only an honest declarer guarantees.
pub const LADDER: [fn(Hand, &View) -> bool; 4] = [
    shown_cards_are_held,
    at_least_what_was_claimed,
    silence_agrees_with_the_answers,
    what_was_named_was_the_best,
];

/// Every `size`-card subset of `pool`, in index order.
///
/// Written out rather than pulled in, since it is twenty lines and the engine
/// otherwise has no dependencies at all.
fn combinations(pool: &[Card], size: usize, mut visit: impl FnMut(&[Card])) {
    if size > pool.len() {
        return;
    }
    let mut indices: Vec<usize> = (0..size).collect();
    let mut chosen: Vec<Card> = indices.iter().map(|i| pool[*i]).collect();
    loop {
        visit(&chosen);
        // Advance the rightmost index that can still move.
        let mut i = size;
        loop {
            if i == 0 {
                return;
            }
            i -= 1;
            if indices[i] != i + pool.len() - size {
                break;
            }
        }
        indices[i] += 1;
        for j in i + 1..size {
            indices[j] = indices[j - 1] + 1;
        }
        for (slot, index) in chosen.iter_mut().zip(&indices) {
            *slot = pool[*index];
        }
    }
}

/// Every hand the opponent could be holding, as far as anyone can tell.
///
/// Cards elder watched younger take are held out of the enumeration and added
/// to every candidate instead. Leaving them in the pool would be wrong twice
/// over: it would let a candidate omit a card she demonstrably holds, and --
/// because `unseen` rightly excludes cards he has placed -- it would rule out
/// her real hand altogether.
///
/// `limit` caps the result by taking a **random sample**, not the first so
/// many: the enumeration emits in a fixed order, so truncating it yields hands
/// that all share the same low-indexed cards, which is precisely the wrong
/// thing to hand to a Monte Carlo average.
pub fn possible_hands(
    view: &View,
    limit: Option<usize>,
    use_declarations: bool,
    rng: &mut Rng,
) -> Vec<Hand> {
    let known = view.watched_them_take;
    let size = opponent_hand_size(view).saturating_sub(known.len() as usize);
    if size == 0 {
        return vec![known];
    }

    let mut pool = view.unseen();
    for suit in known_voids(view) {
        pool = pool.without(pool.in_suit(suit));
    }
    let candidates: Vec<Card> = pool.cards().collect();
    if candidates.len() < size {
        return Vec::new();
    }

    let played = opponent_played(view);
    let rungs: &[fn(Hand, &View) -> bool] = if use_declarations { &LADDER } else { &[] };

    let mut best_rung: i32 = -1;
    let mut hands: Vec<Hand> = Vec::new();
    combinations(&candidates, size, |chosen| {
        let hand = Hand(Hand::of(chosen).expect("distinct cards").0 | known.0);
        let original = Hand(hand.0 | played.0);
        let mut rung = 0i32;
        for check in rungs {
            if !check(original, view) {
                break;
            }
            rung += 1;
        }
        if rung > best_rung {
            best_rung = rung;
            hands.clear();
            hands.push(hand);
        } else if rung == best_rung {
            hands.push(hand);
        }
    });

    if let Some(limit) = limit {
        if hands.len() > limit {
            return rng.sample(&hands, limit);
        }
    }
    hands
}
