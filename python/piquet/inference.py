"""Working out what the opponent can possibly hold.

The exact solver needs both hands. We only have one, so this module supplies
the other -- every hand consistent with what the rules have made public.

Three sources of information, in increasing order of how much they narrow
things down:

1. **Cards accounted for.** Your hand, your discards, your talon cards, and
   everything played. What is left is the candidate pool.
2. **What was shown, and the floor under what was claimed.** Cards exposed on
   the table are certain, and a declaration can never be more than the hand
   holds -- both survive an opponent who conceals.
3. **Cards you watched them take.** If elder exchanges fewer than five, younger
   draws off the top of cards he has already read. Those are certainly hers, so
   they are not enumerated at all: every candidate is *built around* them.
4. **Voids.** A player who failed to follow suit holds none of it, for the rest
   of the deal. Free, certain, and often decisive.
5. **An honest declarer.** That she named her best, and named it in every
   category she could. Enormously informative, and the only part of this list
   that concealment can take away.
"""

from __future__ import annotations

import random
from itertools import combinations
from typing import Optional

from piquet.cards import Hand, Suit
from piquet.combos import best_point, best_sequence, best_set
from piquet.observation import View
from piquet.scoring import Category

__all__ = [
    "possible_hands", "opponent_hand_size", "known_voids", "opponent_played",
    "LADDER",
]

_BEST = {
    Category.POINT: best_point,
    Category.SEQUENCES: best_sequence,
    Category.SETS: best_set,
}


def opponent_hand_size(view: View) -> int:
    """How many cards the opponent is holding right now.

    Only decrement for a trick in progress if the *opponent* led it. An earlier
    version decremented whenever any trick was open, which was invisible in
    practice -- an agent only asks on its own turn, and then a trick is open
    only because the opponent led -- but wrong for anyone else who looked, and
    it would have generated candidate hands of the wrong length.
    """
    remaining = 12 - len(view.tricks)
    if view.current_trick is not None and view.current_trick.leader is view.opponent:
        remaining -= 1
    return max(remaining, 0)


def known_voids(view: View) -> set[Suit]:
    """Suits the opponent has shown they cannot hold.

    Failing to follow suit is a permanent, certain fact -- the cheapest and
    hardest information in the game.
    """
    voids: set[Suit] = set()
    for trick in view.tricks:
        if trick.followed is None:
            continue
        if trick.leader is view.me and trick.followed.suit is not trick.led.suit:
            voids.add(trick.led.suit)
    return voids


def opponent_played(view: View) -> Hand:
    """Every card the opponent has already put on the table."""
    played = Hand.empty()
    for trick in (*view.tricks, view.current_trick):
        if trick is None:
            continue
        if trick.leader is not view.me:
            played = played | Hand.of(trick.led)
        elif trick.followed is not None:
            played = played | Hand.of(trick.followed)
    return played


def _shown_cards_are_held(original: Hand, view: View) -> bool:
    """Cards the opponent laid on the table. Not an assumption at all.

    "Either player may ask to see any combination that has been scored for or
    which caused no score because of equality." Those cards were exposed. No
    amount of concealment elsewhere in the dialogue can take them back, so this
    is the one rung that is never dropped.
    """
    return all(combination.is_supported_by(original) for combination in view.seen)


def _at_least_what_was_claimed(original: Hand, view: View) -> bool:
    """A declaration is a floor. You may declare less than you hold, never more.

    Cavendish's examples of sinking are all understatements -- "he calls five
    cards, and declares five spades, when he might have six" -- and never
    overstatements, which `Declaration.validate` refuses outright. So "a quint"
    means a sequence of five *or better*, and that stays true however much of
    the rest of the hand went unmentioned.
    """
    for announcement in view.heard:
        best = _BEST[announcement.category](original)
        if best is None or best.key[0] < announcement.primary:
            return False
    return True


def _silence_means_nothing_held(original: Hand, view: View) -> bool:
    """She said nothing in that category, so she had nothing in it.

    True of an honest declarer and false of one who sank the category whole.
    """
    declared = {a.category for a in view.heard}
    return not any(
        category not in declared and finder(original) is not None
        for category, finder in _BEST.items()
    )


def _what_was_named_was_the_best(original: Hand, view: View) -> bool:
    """She named her best holding, exactly, not some lesser one.

    The first rung to go, because partial understatement is the commonest form
    of sinking and the one Cavendish spends his examples on.
    """
    return all(
        announcement.matches(_BEST[announcement.category](original))
        for announcement in view.heard
    )


#: What the dialogue tells you, from what survives any amount of concealment to
#: what only an honest declarer guarantees. `possible_hands` keeps the
#: candidates that satisfy the most of these, so an opponent who sinks costs
#: you the bottom rungs and not the whole ladder. An earlier version ran all
#: four as a single filter and dropped all four together the moment one failed
#: -- which meant that a player who concealed a sequence also stopped the
#: engine believing cards she had physically shown it. Measured against a
#: sinking opponent, her own exposed cards ruled out 88% of the candidate set
#: that was being kept.
LADDER = (
    _shown_cards_are_held,
    _at_least_what_was_claimed,
    _silence_means_nothing_held,
    _what_was_named_was_the_best,
)


def possible_hands(
    view: View,
    limit: Optional[int] = None,
    use_declarations: bool = True,
    rng: Optional[random.Random] = None,
) -> list[Hand]:
    """Every hand the opponent could be holding, as far as anyone can tell.

    Cards elder watched younger take are held out of the enumeration and added
    to every candidate instead. Leaving them in the pool would be wrong twice
    over: it would let a candidate omit a card she demonstrably holds, and --
    because `unseen` rightly excludes cards he has placed -- it would rule out
    her real hand altogether. Every deal in which elder took fewer than five,
    which is every deal a human plays that way.

    `limit` caps the result by taking a **random sample**, not the first so
    many. `itertools.combinations` emits in a fixed order, so truncating it
    yields hands that all share the same low-indexed cards -- a systematically
    skewed picture of what the opponent might hold, which is precisely the
    wrong thing to hand to a Monte Carlo average.

    What the dialogue gives up is graded, not all-or-nothing -- see `LADDER`.
    The candidates kept are those that satisfy the most rungs of it, so an
    opponent who conceals costs you the assumptions about her honesty and none
    of the deductions. Being lied to by omission is exactly what sinking is
    bought for, and it should cost what it buys and no more.

    `use_declarations=False` drops the whole ladder, exposed cards included. It
    is a diagnostic, for measuring how much the dialogue is worth.
    """
    known = view.watched_them_take
    size = opponent_hand_size(view) - len(known)
    if size <= 0:
        return [known]

    pool = view.unseen
    for suit in known_voids(view):
        pool = pool - pool.in_suit(suit)
    candidates = list(pool)
    if len(candidates) < size:
        return []

    played = opponent_played(view)
    ladder = LADDER if use_declarations else ()

    best_rung = -1
    hands: list[Hand] = []
    for combination in combinations(candidates, size):
        hand = Hand.of(*combination) | known
        original = hand | played
        rung = 0
        for check in ladder:
            if not check(original, view):
                break
            rung += 1
        if rung > best_rung:
            best_rung, hands = rung, [hand]
        elif rung == best_rung:
            hands.append(hand)

    if limit is not None and len(hands) > limit:
        hands = (rng or random).sample(hands, limit)
    return hands
