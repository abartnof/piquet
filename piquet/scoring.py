"""Scoring: an ordered event log, and the derivation of pique and repique.

Piquet's two bonuses read the *same* points in *two different orders*. Repique
reckons in strict category order and ignores play; pique reckons in the order
things actually happened, over declarations and play together. A running total
cannot express both, so every point scored is recorded as an event and the
bonuses are derived by scanning the log two different ways.

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

    @property
    def repique(self) -> Optional[Player]:
        """Law 68: thirty made "in his hand alone", reckoning in category order.

        Both players can repique. Younger's is the interesting case: elder
        scores one for leading to the first trick before younger declares at
        all, but that is category V, which reckons *after* the declaration
        categories, so it does not block her.
        """
        running = {Player.ELDER: 0, Player.YOUNGER: 0}
        for category in DECLARATION_CATEGORIES:
            for event in self.events:
                if event.category is category:
                    running[event.player] += event.amount
            for player in (Player.ELDER, Player.YOUNGER):
                if (
                    running[player] >= PIQUE_THRESHOLD
                    and running[player.opponent] == 0
                ):
                    return player
        return None

    @property
    def pique(self) -> Optional[Player]:
        """Law 69: thirty made by elder "in hand and play", in temporal order.

        Only elder can score it. The cards are excluded: "A capot reckons after
        points made in play; and, therefore, does not count toward a pique" --
        and Law 66 makes capot and the ten for cards the same score, so neither
        contributes.

        A player scores a pique or a repique, never both.
        """
        if self.repique is Player.ELDER:
            return None
        running = 0
        for event in self.events:
            if event.category is Category.BONUS:
                continue
            if event.player is Player.YOUNGER:
                return None  # the window closes the moment she reckons anything
            if event.category is Category.CARDS:
                continue
            running += event.amount
            if running >= PIQUE_THRESHOLD:
                return Player.ELDER
        return None

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
