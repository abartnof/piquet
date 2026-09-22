"""The three declaration categories: point, sequence and set.

Each category is contested separately and in a fixed order. The player with the
better holding scores it *and* every lesser holding of his own in that category;
the loser scores nothing at all. An exact tie scores for neither -- though, per
Cavendish, equality still does not block a pique.

Scoring authority: Cavendish, *The Laws of Piquet adopted by the Portland and
Turf Clubs* (1892), laws 60-64. See docs/PIQUET.md, "Declarations".

This module is pure: it knows about hands, not about players, dialogue or
sinking. Deciding *what to declare* from what you hold belongs to the agents.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from piquet.cards import Hand, Rank, Suit

__all__ = [
    "Comparison", "Point", "Sequence", "CardSet",
    "best_point", "sequences", "best_sequence", "sets", "best_set",
    "compare_point", "compare_sequence", "compare_set",
    "score_sequences", "score_sets", "is_carte_blanche",
]

MINIMUM_SEQUENCE = 3
MINIMUM_SET = 3
SEQUENCE_BONUS_FROM = 5
SEQUENCE_BONUS = 10
TRIO_SCORE = 3
QUATORZE_SCORE = 14


class Comparison(Enum):
    """How one player's holding stands against the other's.

    Named from the point of view of the holding on the left. The dialogue at
    the table inverts it: younger answers "good" to elder's declaration when
    elder's holding is BETTER.
    """

    BETTER = "better"
    WORSE = "worse"
    EQUAL = "equal"


@dataclass(frozen=True, slots=True)
class Point:
    """The longest suit, scoring its length."""

    suit: Suit
    length: int
    pip_value: int

    @property
    def score(self) -> int:
        return self.length

    @property
    def key(self) -> tuple[int, int]:
        """Length first, then pip value -- the order ties are broken in."""
        return (self.length, self.pip_value)

    def is_supported_by(self, hand: Hand) -> bool:
        """True if the hand can actually show this point.

        An understated point -- "five spades" while holding six -- is supported
        when the top cards of that suit add up to the value claimed.
        """
        ranks = hand.ranks_in(self.suit)
        if self.length < 1 or len(ranks) < self.length:
            return False
        return sum(r.pip_value for r in ranks[: self.length]) == self.pip_value

    def __str__(self) -> str:
        return f"point of {self.length} ({self.pip_value})"


@dataclass(frozen=True, slots=True)
class Sequence:
    """A run of three or more cards in one suit, named by its highest card."""

    suit: Suit
    top: Rank
    length: int

    @property
    def score(self) -> int:
        """3 and 4 score their length; from five cards a bonus of ten applies.

        So the historical table -- 3, 4, 15, 16, 17, 18 -- is a formula, not an
        arbitrary list, which is also the clearest way to teach it.
        """
        if self.length < SEQUENCE_BONUS_FROM:
            return self.length
        return SEQUENCE_BONUS + self.length

    @property
    def key(self) -> tuple[int, int]:
        return (self.length, int(self.top))

    @property
    def name(self) -> str:
        return {
            3: "tierce", 4: "quart", 5: "quint",
            6: "sixième", 7: "septième", 8: "huitième",
        }[self.length]

    def is_supported_by(self, hand: Hand) -> bool:
        """True if the hand holds this exact run.

        An understated sequence -- a tierce to the knave out of a quart to the
        knave -- is supported, because the shorter run really is in the hand.
        """
        if not MINIMUM_SEQUENCE <= self.length <= 8:
            return False
        lowest = self.top - self.length + 1
        if lowest < Rank.SEVEN:
            return False
        held = set(hand.ranks_in(self.suit))
        return all(Rank(r) in held for r in range(lowest, self.top + 1))

    def __str__(self) -> str:
        return f"{self.name} to the {self.top.name.lower()}"


@dataclass(frozen=True, slots=True)
class CardSet:
    """Three or four cards of one rank, ten or higher.

    Named `CardSet` rather than `Set` to stay clear of the builtin.
    """

    rank: Rank
    count: int

    @property
    def score(self) -> int:
        return QUATORZE_SCORE if self.count == 4 else TRIO_SCORE

    @property
    def key(self) -> tuple[int, int]:
        """Size first -- any quatorze beats any trio -- then rank."""
        return (self.count, int(self.rank))

    @property
    def name(self) -> str:
        return "quatorze" if self.count == 4 else "trio"

    def is_supported_by(self, hand: Hand) -> bool:
        """True if the hand holds at least this many of the rank.

        A quatorze may be understated as a trio, which is one of Cavendish's
        examples of sinking.
        """
        if not self.rank.counts_for_set:
            return False
        if not MINIMUM_SET <= self.count <= 4:
            return False
        return hand.count_of(self.rank) >= self.count

    def __str__(self) -> str:
        return f"{self.name} of {self.rank.name.lower()}s"


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------


def best_point(hand: Hand) -> Optional[Point]:
    """The hand's longest suit, resolving its own ties by pip value."""
    best: Optional[Point] = None
    for suit in Suit:
        ranks = hand.ranks_in(suit)
        if not ranks:
            continue
        candidate = Point(
            suit=suit,
            length=len(ranks),
            pip_value=sum(rank.pip_value for rank in ranks),
        )
        if best is None or candidate.key > best.key:
            best = candidate
    return best


def sequences(hand: Hand) -> tuple[Sequence, ...]:
    """Every sequence the hand holds, best first.

    Runs are *maximal*: a quart is one sequence, not two overlapping tierces.
    A gap splits a suit into separate sequences, so seven cards missing the ten
    yield a quart above and a tierce below.
    """
    found: list[Sequence] = []
    for suit in Suit:
        ascending = sorted(hand.ranks_in(suit))
        run: list[Rank] = []
        for rank in ascending + [None]:  # type: ignore[list-item]
            if run and rank is not None and rank - run[-1] == 1:
                run.append(rank)
                continue
            if len(run) >= MINIMUM_SEQUENCE:
                found.append(Sequence(suit=suit, top=run[-1], length=len(run)))
            run = [] if rank is None else [rank]
    return tuple(sorted(found, key=lambda s: s.key, reverse=True))


def best_sequence(hand: Hand) -> Optional[Sequence]:
    found = sequences(hand)
    return found[0] if found else None


def sets(hand: Hand) -> tuple[CardSet, ...]:
    """Every trio and quatorze the hand holds, best first.

    Only tens and above count: nines, eights and sevens never form a set.
    """
    found = [
        CardSet(rank=rank, count=hand.count_of(rank))
        for rank in Rank
        if rank.counts_for_set and hand.count_of(rank) >= MINIMUM_SET
    ]
    return tuple(sorted(found, key=lambda s: s.key, reverse=True))


def best_set(hand: Hand) -> Optional[CardSet]:
    found = sets(hand)
    return found[0] if found else None


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------


def _compare(mine, theirs) -> Comparison:
    """Compare two holdings by their sort key, treating absence as lowest."""
    if mine is None and theirs is None:
        return Comparison.EQUAL
    if mine is None:
        return Comparison.WORSE
    if theirs is None:
        return Comparison.BETTER
    if mine.key > theirs.key:
        return Comparison.BETTER
    if mine.key < theirs.key:
        return Comparison.WORSE
    return Comparison.EQUAL


def compare_point(mine: Optional[Point], theirs: Optional[Point]) -> Comparison:
    """Length first, then pip value. An exact tie scores for neither player."""
    return _compare(mine, theirs)


def compare_sequence(
    mine: Optional[Sequence], theirs: Optional[Sequence]
) -> Comparison:
    """Length first, then top card. An exact tie scores for neither player."""
    return _compare(mine, theirs)


def compare_set(mine: Optional[CardSet], theirs: Optional[CardSet]) -> Comparison:
    """Size first -- any quatorze beats any trio -- then rank.

    A tie is impossible: two sets of one rank would need six cards of it, and
    only four exist.
    """
    return _compare(mine, theirs)


# --------------------------------------------------------------------------
# Category scoring
# --------------------------------------------------------------------------


def score_sequences(hand: Hand) -> int:
    """What this hand scores for sequences *if it wins the category*.

    Cotton, 1674: the holder of the biggest sequence "reckons all his less
    Sequences". The loser of the category scores nothing at all, which is the
    caller's business, not this function's.
    """
    return sum(sequence.score for sequence in sequences(hand))


def score_sets(hand: Hand) -> int:
    """What this hand scores for sets *if it wins the category*."""
    return sum(card_set.score for card_set in sets(hand))


# --------------------------------------------------------------------------
# Carte blanche
# --------------------------------------------------------------------------


def is_carte_blanche(hand: Hand) -> bool:
    """True if the hand holds no jack, queen or king.

    Worth 10 points. Tens and aces do not deny it. It occurs about once in
    1,792 deals, and two players can never hold it at once in the 32-card game.
    """
    return not any(card.rank.is_court for card in hand)
