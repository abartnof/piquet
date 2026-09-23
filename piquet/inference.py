"""Working out what the opponent can possibly hold.

The exact solver needs both hands. We only have one, so this module supplies
the other -- every hand consistent with what the rules have made public.

Three sources of information, in increasing order of how much they narrow
things down:

1. **Cards accounted for.** Your hand, your discards, your talon cards, and
   everything played. What is left is the candidate pool.
2. **Cards you watched them take.** If elder exchanges fewer than five, younger
   draws off the top of cards he has already read. Those are certainly hers, so
   they are not enumerated at all: every candidate is *built around* them.
3. **Voids.** A player who failed to follow suit holds none of it, for the rest
   of the deal. Free, certain, and often decisive.
4. **The declarations.** Enormously informative -- they cut the candidates by
   about thirteen-fold on their own (docs/DESIGN.md §4.2).
"""

from __future__ import annotations

import random
from itertools import combinations
from typing import Optional

from piquet.cards import Hand, Suit
from piquet.combos import best_point, best_sequence, best_set
from piquet.observation import View
from piquet.scoring import Category

__all__ = ["possible_hands", "opponent_hand_size", "known_voids", "opponent_played"]

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


def _consistent_with_declarations(hand: Hand, view: View, played: Hand) -> bool:
    """Could this hand have produced the declarations that were actually made?

    The check must run against the opponent's **original twelve**, not what is
    left of them. A quint declared before the play is broken up as soon as one
    of its cards is led, so testing the remaining cards against the declaration
    rejects the true hand -- which is what an earlier version did, and why the
    candidate count went *up* as the deal went on instead of down.

    Assumes the opponent declared honestly and fully. Against one who sinks this
    is too strict, which is exactly what sinking buys, and why `possible_hands`
    falls back gracefully.
    """
    hand = hand | played
    for announcement in view.heard:
        if not announcement.matches(_BEST[announcement.category](hand)):
            return False
    declared = {a.category for a in view.heard}
    for category, finder in _BEST.items():
        if category not in declared and finder(hand) is not None:
            return False
    return all(combination.is_supported_by(hand) for combination in view.seen)


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

    If the declaration filter leaves nothing, it is dropped and the weaker
    filters are used alone. That happens when the opponent sank something: the
    concealed hand is genuinely inconsistent with what was said, so believing
    the declarations would rule out the truth. Falling back is the honest
    response to being lied to by omission -- and it is exactly the advantage
    sinking is bought for.
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

    def build(filtered: bool) -> list[Hand]:
        found = []
        for combination in combinations(candidates, size):
            hand = Hand.of(*combination) | known
            if filtered and not _consistent_with_declarations(hand, view, played):
                continue
            found.append(hand)
        return found

    hands = build(use_declarations)
    if not hands and use_declarations:
        hands = build(False)
    if limit is not None and len(hands) > limit:
        hands = (rng or random).sample(hands, limit)
    return hands
