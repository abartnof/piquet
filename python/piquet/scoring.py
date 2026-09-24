"""Scoring: an ordered event log, and the derivation of pique and repique.

Piquet's two bonuses read the *same* points over *different sets of
categories*. Repique is made "in his hand alone" and ignores play entirely;
pique is made "in hand and play" and so counts the points scored for leading
and winning tricks as well. Both ask the same question -- did this player
reach thirty before the other reckoned anything at all? -- and both must ask it
of Law 67's **order of precedence**, not of the order the log was written in.

The two orders are genuinely different, which is the whole reason scoring is a
log rather than a running total. Younger's declarations are *entered* when
elder leads to the first trick, long after elder has entered his own, but they
*reckon* in their proper categories: her point is II and comes before his
sequences at III. An earlier version scanned the raw log for the pique and the
precedence order for the repique, so the same fact -- younger winning the point
-- denied elder the sixty and left him the thirty. Measured over four thousand
deals that awarded a pique that was not due in one deal in two hundred and
fifty.

The log pays for itself three times over: it makes the hardest rule in the game
testable, it gives the tutor a ready-made narrative, and it is already the
per-decision training record we want for later analysis.

Authority: Cavendish, *The Laws of Piquet adopted by the Portland and Turf
Clubs* (1892), laws 66-69. See docs/DESIGN.md section 5.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Iterator, Optional

__all__ = [
    "Player", "Category", "ScoreEvent", "ScoreLog",
    "PIQUE_THRESHOLD", "PIQUE_BONUS", "REPIQUE_BONUS",
    "DECLARATION_CATEGORIES", "PIQUE_CATEGORIES",
]

PIQUE_THRESHOLD = 30
PIQUE_BONUS = 30
REPIQUE_BONUS = 60


class Player(Enum):
    """The two seats. Elder is the non-dealer, and has the advantage."""

    ELDER = "elder"
    YOUNGER = "younger"

    @property
    def opponent(self) -> Player:
        return Player.YOUNGER if self is Player.ELDER else Player.ELDER

    @property
    def index(self) -> int:
        """A stable slot, so per-player state can live in a two-tuple."""
        return 0 if self is Player.ELDER else 1

    def __str__(self) -> str:
        return self.value


class Category(IntEnum):
    """Cavendish, Law 67: the order in which scores reckon.

    The integer values *are* the reckoning order, so sorting by them is the
    rule. `BONUS` is our own addition, placed last so that a pique or repique
    can be stored in the log without disturbing either derivation.
    """

    CARTE_BLANCHE = 1
    POINT = 2
    SEQUENCES = 3
    SETS = 4
    PLAY = 5
    CARDS = 6
    BONUS = 7


#: Categories that count towards a repique -- "in his hand alone".
DECLARATION_CATEGORIES = (
    Category.CARTE_BLANCHE,
    Category.POINT,
    Category.SEQUENCES,
    Category.SETS,
)

#: ...and the one more that counts towards a pique, made "in hand and play".
#: The cards are excluded deliberately: "a capot reckons after points made in
#: play; and, therefore, does not count toward a pique" (Cavendish, Law 69).
PIQUE_CATEGORIES = DECLARATION_CATEGORIES + (Category.PLAY,)


@dataclass(frozen=True, slots=True)
class ScoreEvent:
    """One score, by one player, from one source."""

    player: Player
    amount: int
    category: Category
    detail: str = ""

    def __str__(self) -> str:
        what = self.detail or self.category.name.lower().replace("_", " ")
        return f"{self.player} scores {self.amount} for {what}"


@dataclass(frozen=True, slots=True)
class ScoreLog:
    """An append-only record of every point scored in a deal.

    Immutable: `record` returns a new log. Deals are short -- a few dozen
    events -- so copying is cheap, and immutability keeps the log safe to hold
    inside a search node.
    """

    events: tuple[ScoreEvent, ...] = field(default_factory=tuple)

    # -- building ---------------------------------------------------------

    def record(
        self,
        player: Player,
        amount: int,
        category: Category,
        detail: str = "",
    ) -> ScoreLog:
        """Return a new log with one more score in it.

        Scores must be positive. An equality scores for neither player, so
        nothing is logged: recording a zero would wrongly look like the
        adversary had reckoned something, and would silently break both
        bonuses.
        """
        if amount <= 0:
            raise ValueError(
                f"a score must be positive, got {amount}; "
                "an equality is recorded by logging nothing at all"
            )
        return ScoreLog(self.events + (ScoreEvent(player, amount, category, detail),))

    # -- reading ----------------------------------------------------------

    def __len__(self) -> int:
        return len(self.events)

    def __iter__(self) -> Iterator[ScoreEvent]:
        return iter(self.events)

    def total(self, player: Player) -> int:
        return sum(e.amount for e in self.events if e.player is player)

    def by_category(self, player: Player) -> dict[Category, int]:
        """A breakdown for the tutor: what this player scored, and for what."""
        breakdown: dict[Category, int] = {}
        for event in self.events:
            if event.player is player:
                breakdown[event.category] = (
                    breakdown.get(event.category, 0) + event.amount
                )
        return breakdown

    # -- the two bonuses --------------------------------------------------

    def _first_to_thirty(self, categories: tuple[Category, ...]) -> Optional[Player]:
        """Who reached thirty over these categories before the other scored.

        The categories are walked in Law 67's order of precedence, which is not
        the order of the log: younger's declarations are entered only once
        elder has led to the first trick. Within a category the log order
        stands, which matters only for points made in play, since no other
        category can score for both players.

        As soon as both sides have reckoned something, neither can have got
        there "before his opponent counted anything", so the walk stops.
        """
        running = {Player.ELDER: 0, Player.YOUNGER: 0}
        for category in categories:
            for event in self.events:
                if event.category is not category:
                    continue
                if running[event.player.opponent]:
                    return None
                running[event.player] += event.amount
                if running[event.player] >= PIQUE_THRESHOLD:
                    return event.player
        return None

    @property
    def repique(self) -> Optional[Player]:
        """Law 68: thirty made "in his hand alone", reckoning in category order.

        Both players can repique. Younger's is the interesting case: elder
        scores one for leading to the first trick before younger declares at
        all, but that is category V, which is not reckoned here at all, so it
        does not block her.
        """
        return self._first_to_thirty(DECLARATION_CATEGORIES)

    @property
    def pique(self) -> Optional[Player]:
        """Law 69: thirty made "in hand and play" before the opponent reckons.

        Only elder can score it, and that falls out of the precedence order
        rather than being stipulated. Younger's declarations are categories
        I-IV; if they reach thirty with elder silent she has a repique, not a
        pique. To need points made in play she would have to be short of thirty
        after declaring -- and then the very first entry in category V is
        elder's point for leading to the first trick, by which time she has
        reckoned and the window is shut.

        A player scores a pique or a repique, never both.
        """
        if self.repique is not None:
            return None
        return self._first_to_thirty(PIQUE_CATEGORIES)

    def with_bonuses(self) -> ScoreLog:
        """Return a log with the pique or repique bonus appended, if any.

        Idempotent, so it is safe to call at the end of a deal without first
        checking whether it has already been applied.
        """
        if any(e.category is Category.BONUS for e in self.events):
            return self

        winner = self.repique
        if winner is not None:
            return self.record(winner, REPIQUE_BONUS, Category.BONUS, "repique")

        winner = self.pique
        if winner is not None:
            return self.record(winner, PIQUE_BONUS, Category.BONUS, "pique")

        return self

    def __str__(self) -> str:
        return "\n".join(str(event) for event in self.events)
