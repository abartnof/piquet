"""The partie: six deals, the alternating deal, and the rubicon.

A deal is not the game. Piquet is played over six deals with the deal
alternating, and settled once at the end under the **rubicon** rule: the loser
pays the *difference* plus a hundred if he reached a hundred himself, and the
*sum* plus a hundred if he did not.

That one clause is why maximising points in a deal is not the same thing as
playing well. 105 to 101 pays 104; 97 to 89 pays 286, nearly three times as
much for a closer game. A player on 95 with one deal left is not trying to win
the deal, he is trying to cross a line -- and his opponent has a reason to keep
him *down* that has no counterpart inside a single deal at all.

Seats and people are different things here, and the module keeps them apart.
`Player.ELDER` and `Player.YOUNGER` are seats: they change hands every deal. A
`Side` plays the whole partie, and the rubicon is reckoned over a side.

Authority: pagat.com. "A game consists of a set of 6 deals called a partie,
with the deal alternating... If the loser has scored at least 100 points, the
loser pays the winner the difference between the players' scores plus 100. If
the loser has not scored as many as 100 points then the loser pays the winner
the sum of the players' scores plus 100... If the scores are equal after 6
deals, two more hands are played. If they are then still equal the partie is a
draw."
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from piquet.rules import Deal, Phase
from piquet.scoring import Player

__all__ = [
    "Side", "Standing", "DealOutcome", "Settlement", "Partie",
    "DEALS_IN_PARTIE", "EXTRA_DEALS", "RUBICON", "PARTIE_BONUS",
]

#: Deals in a partie, before any tie-break.
DEALS_IN_PARTIE = 6
#: "If the scores are equal after 6 deals, two more hands are played." Both of
#: them: each player deals one, so neither gains the seat by breaking the tie.
EXTRA_DEALS = 2
#: The line. Reaching it changes what losing costs by a factor of about three.
RUBICON = 100
#: Added to every settlement, difference or sum alike.
PARTIE_BONUS = 100


class Side(IntEnum):
    """One of the two people at the table, as opposed to one of the two seats.

    `Player.ELDER` and `Player.YOUNGER` are seats and change hands every deal.
    A side plays the whole partie. The two need different names or they will be
    confused exactly once, and expensively -- the rubicon is reckoned over a
    person's six deals, not over a chair.

    A and B after the card manuals, which have worked their examples that way
    since Cavendish.
    """

    A = 0
    B = 1

    @property
    def other(self) -> Side:
        return Side.B if self is Side.A else Side.A

    @property
    def index(self) -> int:
        """A stable slot, so per-side state can live in a two-tuple."""
        return int(self)

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class Standing:
    """Where the partie stands, read from one player's side of the table.

    Both totals are public -- scores are called aloud -- and so is the number
    of deals left. Under rubicon settlement that is not colour: it is the
    difference between two quite different games, and an agent that cannot see
    it is optimising a proxy for the thing it is meant to win.
    """

    mine: int
    theirs: int
    deals_left: int

    @property
    def reversed(self) -> Standing:
        """The same table, read from the other chair."""
        return Standing(self.theirs, self.mine, self.deals_left)

    @property
    def is_last_deal(self) -> bool:
        return self.deals_left <= 1

    @property
    def short_of_the_rubicon(self) -> bool:
        """Whether I am still under a hundred, and so still liable to pay the
        sum of both scores rather than the difference."""
        return self.mine < RUBICON

    def __str__(self) -> str:
        return f"{self.mine}-{self.theirs}, {self.deals_left} to play"


@dataclass(frozen=True, slots=True)
class DealOutcome:
    """One deal's contribution, resolved from seats to people."""

    #: Counting from one.
    number: int
    #: Which side sat in elder's chair for it.
    elder: Side
    #: What each side scored, indexed by `Side.index`.
    scores: tuple[int, int]

    def score_of(self, side: Side) -> int:
        return self.scores[side.index]


@dataclass(frozen=True, slots=True)
class Settlement:
    """What the partie pays, and on which of the two clauses."""

    winner: Optional[Side]
    points: int
    #: True when the loser failed to reach a hundred and pays the sum.
    rubicon: bool

    def __str__(self) -> str:
        if self.winner is None:
            return "the partie is drawn"
        how = "rubiconed, paying the sum" if self.rubicon else "paying the difference"
        return f"{self.winner} wins {self.points} -- {how} plus {PARTIE_BONUS}"


@dataclass(frozen=True, slots=True)
class Partie:
    """Six deals between two people, and what they come to.

    Immutable, like `Deal`: entering a result returns a new partie.
    """

    #: Who deals the first deal, and so sits younger in it. pagat: the winner
    #: of the cut "should always choose to deal first, as there is a slight
    #: advantage to being non-dealer on the critical sixth hand" -- because the
    #: deal alternates, dealing the first puts you in elder's chair for the
    #: sixth.
    opening_dealer: Side = Side.A
    outcomes: tuple[DealOutcome, ...] = ()

    # -- where we are -----------------------------------------------------

    @property
    def number(self) -> int:
        """The deal about to be played, counting from one."""
        return len(self.outcomes) + 1

    def elder_in(self, number: int) -> Side:
        """Who sits in elder's chair for that deal.

        The deal alternates and the non-dealer is elder, so whoever dealt first
        is elder in every even-numbered deal -- the sixth among them.
        """
        return self.opening_dealer if number % 2 == 0 else self.opening_dealer.other

    @property
    def elder(self) -> Side:
        """Who is elder in the deal about to be played."""
        return self.elder_in(self.number)

    @property
    def totals(self) -> tuple[int, int]:
        """What each side has scored so far, indexed by `Side.index`."""
        return (
            sum(o.scores[0] for o in self.outcomes),
            sum(o.scores[1] for o in self.outcomes),
        )

    def score_of(self, side: Side) -> int:
        return self.totals[side.index]

    @property
    def deals_left(self) -> int:
        """Deals still to play, counting the one about to begin.

        Six, unless the scores come out level after them, in which case two
        more are played -- both of them, whatever happens in the first.
        """
        played = len(self.outcomes)
        if played < DEALS_IN_PARTIE:
            return DEALS_IN_PARTIE - played
        if played >= DEALS_IN_PARTIE + EXTRA_DEALS:
            return 0
        first, second = self.totals
        if played == DEALS_IN_PARTIE and first != second:
            return 0
        return DEALS_IN_PARTIE + EXTRA_DEALS - played

    @property
    def complete(self) -> bool:
        return self.deals_left == 0

    @property
    def standing(self) -> Standing:
        """Where things stand, from the chair of whoever is elder next.

        Elder's side, because that is the side `view_for` reorients from -- see
        `observation.view_for`, which flips it for younger.
        """
        elder = self.elder
        return Standing(
            mine=self.score_of(elder),
            theirs=self.score_of(elder.other),
            deals_left=self.deals_left,
        )

    # -- entering a result ------------------------------------------------

    def record_scores(self, elder: int, younger: int) -> Partie:
        """Enter a deal by its two scores, given in *seat* order.

        Kept separate from `record` so a partie can be replayed from a written
        score sheet, which is all a period account of a game ever gives you.
        """
        if self.complete:
            raise ValueError("the partie is already settled")
        number = self.number
        elder_side = self.elder_in(number)
        scores = (
            (elder, younger) if elder_side is Side.A else (younger, elder)
        )
        outcome = DealOutcome(number=number, elder=elder_side, scores=scores)
        return Partie(self.opening_dealer, self.outcomes + (outcome,))

    def record(self, deal: Deal) -> Partie:
        """Enter a finished deal, taking both scores from its log."""
        if deal.phase is not Phase.COMPLETE:
            raise ValueError(
                f"that deal is not finished: it is at {deal.phase.value}"
            )
        return self.record_scores(
            deal.log.total(Player.ELDER), deal.log.total(Player.YOUNGER)
        )

    # -- what it comes to -------------------------------------------------

    @property
    def settlement(self) -> Optional[Settlement]:
        """What the partie pays, or `None` while it is still being played.

        The guard is on the **loser's** score, not the winner's: Britannica is
        explicit that the loser is rubiconed "even if the winner also fails" to
        reach a hundred. Two players who crawl to 60 and 40 settle for 200.
        """
        if not self.complete:
            return None
        first, second = self.totals
        if first == second:
            return Settlement(winner=None, points=0, rubicon=False)
        winner = Side.A if first > second else Side.B
        high, low = max(first, second), min(first, second)
        if low < RUBICON:
            return Settlement(winner, high + low + PARTIE_BONUS, rubicon=True)
        return Settlement(winner, high - low + PARTIE_BONUS, rubicon=False)

    def __str__(self) -> str:
        first, second = self.totals
        head = f"A {first} - B {second} after {len(self.outcomes)} deals"
        return f"{head}: {self.settlement}" if self.complete else head
