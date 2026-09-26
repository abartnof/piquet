"""Declaring: what a player announces, and what it gives away.

Piquet is what Britannica calls a *trick-and-meld* game, alongside bezique,
pinochle and sixty-six: a trick-taking core with a separate layer of
combinations declared from the hand. This module is that layer, kept apart from
`rules` so the trick-taking machinery underneath stays reusable for the next
game -- which is the whole reason the project is built in pieces.

Declaring trades points for information, and the three things that happen are
deliberately distinct here:

- you **announce** a shape, and never a suit;
- if your combination scores, or ties, the opponent may **ask to see it**;
- if it is beaten it scores nothing and is never shown.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from piquet.cards import Hand, Suit
from piquet.combos import (
    CardSet,
    Comparison,
    Point,
    Sequence,
    best_point,
    compare_point,
    compare_sequence,
    compare_set,
    sequences,
    sets,
)
from piquet.scoring import Category, Player

__all__ = ["Announcement", "Declaration", "CategoryResult", "Combination", "compare_in"]

Combination = Union[Point, Sequence, CardSet]

_CATEGORY_TYPE = {
    Category.POINT: Point,
    Category.SEQUENCES: Sequence,
    Category.SETS: CardSet,
}

_COMPARE = {
    Category.POINT: compare_point,
    Category.SEQUENCES: compare_sequence,
    Category.SETS: compare_set,
}


def compare_in(category: Category, mine, theirs) -> Comparison:
    """Compare two holdings by the rule that governs this category."""
    return _COMPARE[category](mine, theirs)


@dataclass(frozen=True, slots=True)
class Announcement:
    """What is actually said aloud when declaring.

    At the table you announce "point of five", not "five spades". The suit is
    never spoken, and neither, unless it is asked for, is the tie-break:

        "Point of five."  "Equal."  "Making forty-nine."  "Good."

    So an announcement is a declaration's sort key stripped of the suit, and
    often stripped of its second half as well. Which cards it was made of stays
    private unless the combination scores, at which point either player "may ask
    to see any combination that has been scored for or which caused no score
    because of equality" (Cavendish).
    """

    category: Category
    #: Cards in the point or sequence, or the size of the set.
    primary: int
    #: Pip value, top rank, or set rank. `None` when it was never spoken, which
    #: is the usual case: it is asked for only to separate two matching shapes.
    tiebreak: Optional[int] = None

    @property
    def shape(self) -> "Announcement":
        """The same announcement with the tie-break left unsaid."""
        return Announcement(self.category, self.primary)

    def matches(self, best: Optional["Combination"]) -> bool:
        """Whether a holding is consistent with what was actually said.

        Only as far as it went: a shape announced without its tie-break rules
        out every other length and nothing else. Reading more into it than was
        spoken is how an engine quietly gives one player information the table
        never gave them.
        """
        if best is None:
            return False
        primary, tiebreak = best.key
        if primary != self.primary:
            return False
        return self.tiebreak is None or tiebreak == self.tiebreak

    def __str__(self) -> str:
        if self.category is Category.POINT:
            return f"point of {self.primary}"
        if self.category is Category.SEQUENCES:
            name = {3: "tierce", 4: "quart", 5: "quint",
                    6: "sixi\u00e8me", 7: "septi\u00e8me", 8: "huiti\u00e8me"}
            return name.get(self.primary, f"sequence of {self.primary}")
        return "quatorze" if self.primary == 4 else "trio"


@dataclass(frozen=True, slots=True)
class Declaration:
    """What a player announces in one category.

    A declaration is a set of combinations claimed. The best of them decides
    who wins the category; if you win, you score all of them.

    Nothing obliges you to announce what you hold. Declaring nothing is a
    **sink**; declaring less than you hold is also a sink, and Cavendish's
    examples are all of that partial kind -- "he calls five cards, and declares
    five spades, when he might have six." What a claim may *not* be is a lie:
    every claim must be supported by the hand.
    """

    claims: tuple[Combination, ...] = ()

    @classmethod
    def sink(cls) -> "Declaration":
        """Announce nothing, conceding the category to buy silence."""
        return cls(())

    @classmethod
    def of(cls, *claims: Combination) -> "Declaration":
        return cls(tuple(claims))

    @classmethod
    def full(cls, hand: Hand, category: Category) -> "Declaration":
        """Announce everything the hand holds in this category."""
        if category is Category.POINT:
            point = best_point(hand)
            return cls((point,) if point is not None else ())
        if category is Category.SEQUENCES:
            return cls(sequences(hand))
        if category is Category.SETS:
            return cls(sets(hand))
        raise ValueError(f"{category} is not a declaration category")

    @property
    def best(self) -> Optional[Combination]:
        """The claim that decides the category."""
        return max(self.claims, key=lambda c: c.key) if self.claims else None

    @property
    def score(self) -> int:
        """What this declaration is worth *if it wins the category*."""
        return sum(claim.score for claim in self.claims)

    def __bool__(self) -> bool:
        return bool(self.claims)

    def validate(self, hand: Hand, category: Category) -> None:
        """Check the claims are of the right kind, held, and consistent."""
        if not self.claims:
            return

        expected = _CATEGORY_TYPE[category]
        for claim in self.claims:
            if not isinstance(claim, expected):
                raise ValueError(
                    f"{claim} is the wrong category: "
                    f"{category.name.lower()} was being contested"
                )
            if not claim.is_supported_by(hand):
                raise ValueError(f"not held: {claim}")

        if category is Category.POINT and len(self.claims) > 1:
            raise ValueError("only one point may be declared")
        if category is Category.SEQUENCES:
            # Two sequences may share a suit -- a gap splits it, so 7-8-9 and
            # J-Q-K-A are both genuinely held. What they may not do is overlap.
            seen: set[tuple[Suit, int]] = set()
            for claim in self.claims:
                lowest = claim.top - claim.length + 1
                cells = {(claim.suit, r) for r in range(lowest, claim.top + 1)}
                if cells & seen:
                    raise ValueError(
                        f"cannot claim {claim}: it shares cards with another "
                        "sequence already declared"
                    )
                seen |= cells
        if category is Category.SETS:
            ranks = [claim.rank for claim in self.claims]
            if len(set(ranks)) != len(ranks):
                raise ValueError("two sets cannot be claimed of the same rank")

    def announce(self, category: Category) -> Optional[Announcement]:
        """What this declaration sounds like from across the table.

        The suit is not spoken, so the opponent learns the shape of the holding
        without learning which cards it is made of.
        """
        best = self.best
        if best is None:
            return None
        primary, tiebreak = best.key
        return Announcement(category, primary, tiebreak)

    def __str__(self) -> str:
        return ", ".join(str(claim) for claim in self.claims) if self.claims else "sunk"


@dataclass(frozen=True, slots=True)
class CategoryResult:
    """How one category of the dialogue turned out. Kept for the tutor."""

    category: Category
    elder: Declaration
    younger: Declaration
    comparison: Comparison

    @property
    def winner(self) -> Optional[Player]:
        if self.comparison is Comparison.BETTER:
            return Player.ELDER
        if self.comparison is Comparison.WORSE:
            return Player.YOUNGER
        return None

    @property
    def response(self) -> str:
        """What younger says in answer to elder's declaration."""
        return {
            Comparison.BETTER: "good",
            Comparison.WORSE: "not good",
            Comparison.EQUAL: "equal",
        }[self.comparison]

    def declaration_of(self, player: Player) -> Declaration:
        return self.elder if player is Player.ELDER else self.younger

    @property
    def shapes_match(self) -> bool:
        """Whether the two holdings were the same length, or the same size.

        This is the question "equal?" answers, and the only thing that makes
        anyone state a tie-break.
        """
        elder, younger = self.elder.best, self.younger.best
        if elder is None or younger is None:
            return False
        return elder.key[0] == younger.key[0]

    def announcement_of(self, player: Player) -> Optional[Announcement]:
        """What that player said aloud. Always public.

        Elder gives his tie-break when the shapes match, and not otherwise.
        Younger never gives hers at all: she answers his number rather than
        naming her own, and on the occasions she has something to name she has
        won the category and has to show the cards anyway.

        And younger names a holding only if she won the category with it, or
        if the shapes matched -- when her "equal" said as much. Beaten
        outright, she said "good" and nothing else: pagat has her announce
        only "combinations in categories where she has said 'not good' or
        where elder has not made any declaration", and Foster's dealer claims
        "the combinations which are good in his own hand".
        """
        spoken = self.declaration_of(player).announce(self.category)
        if spoken is None:
            return None
        if player is Player.ELDER and self.shapes_match:
            return spoken
        if player is Player.YOUNGER and self.winner is Player.ELDER and not self.shapes_match:
            return None
        return spoken.shape

    def shown(self, player: Player) -> tuple:
        """The cards this player had to expose, if any.

        Either player "may ask to see any combination that has been scored for
        or which caused no score because of equality". A declaration that was
        beaten scores nothing and is never shown -- so the loser of a category
        gives away its shape but not its suit.
        """
        if self.winner is player:
            return self.declaration_of(player).claims
        if self.winner is None:
            return self.declaration_of(player).claims
        return ()

    def __str__(self) -> str:
        return (
            f"{self.category.name.lower()}: elder declares {self.elder}, "
            f"younger says {self.response}"
        )
