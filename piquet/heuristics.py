"""The capability ladder: opponents that are weak in human-shaped ways.

The obvious way to build a weak opponent is to give a strong one less search and
more randomness. That produces a bot that is weak but *alien*: it blunders
uniformly, in ways no person ever would, and you cannot form a theory of it.

Instead each rung **adds a named capability**, and each capability is something a
human player also has to learn:

    1  plays its highest card, and throws its lowest
    2  discards with judgement, and wins tricks as cheaply as it can
    3  remembers what has been played, and runs the suits it can run
    4  listens to the declarations, and keeps out of the opponent's long suit

So the ladder *is* the curriculum: beating a rung-3 opponent means you have
learned to notice something real.

**Every rung here is measured, not assumed** (`tournament`). That discipline has
already cost two rungs. An earlier rung 4 kept guards -- the stop cards of the
textbooks -- and lost, consistently, across every seed: piquet pays a point for
every card you lead, so hoarding defensive cards while throwing winners gives
away tempo you never recover. A replacement rung 4 that judged cards *probably*
good rather than certainly good lost by more. Both were plausible. Neither
survived contact with the harness, and the design ladder was renumbered to
match rather than the other way round.

That is also the expected shape of the thing. Hand-written heuristics run out of
road fast, which is the argument for the exact solver: the remaining rungs come
from search and training, not from more rules of thumb.

Style (`piquet.style`) biases choices of roughly equal value; erraticism varies
the rung per decision. The three are independent by construction.
"""

from __future__ import annotations

import random
from typing import Optional

from piquet.cards import Card, Hand, Rank, Suit
from piquet.combos import Point
from piquet.observation import View
from piquet.rules import Declaration
from piquet.scoring import Category
from piquet.style import BALANCED, Style

__all__ = ["HeuristicAgent", "MAX_LEVEL", "SINK_CEILING"]

MAX_LEVEL = 4

#: The most a declaration may be worth before sinking it stops making sense.
#: The economics are the point: a tierce exposes three cards to buy 3 points,
#: which is a poor trade, while a quatorze exposes four to buy 14, which is a
#: good one. Nobody sinks a quatorze.
SINK_CEILING = 4


class HeuristicAgent:
    """An opponent at a named rung of the ladder, with a style and a temper."""

    def __init__(
        self,
        level: int = 1,
        style: Style = BALANCED,
        erraticism: float = 0.0,
        rng: Optional[random.Random] = None,
        name: Optional[str] = None,
    ) -> None:
        if not 1 <= level <= MAX_LEVEL:
            raise ValueError(f"level must be 1..{MAX_LEVEL}, got {level}")
        if not 0.0 <= erraticism <= 1.0:
            raise ValueError(f"erraticism must be 0..1, got {erraticism}")
        self.level = level
        self.style = style
        self.erraticism = erraticism
        self.rng = rng or random.Random()
        self.name = name or f"L{level}"

    # -- the temper -------------------------------------------------------

    def _rung(self) -> int:
        """The rung this particular decision is made at.

        Real players are inconsistent, not uniformly bad, so erraticism varies
        the *capability* brought to bear rather than adding noise to the answer.
        An erratic opponent is occasionally brilliant and occasionally sloppy,
        which reads as far more human than uniform randomness.
        """
        if not self.erraticism:
            return self.level
        drawn = round(self.rng.gauss(self.level, self.erraticism * 2.0))
        return max(1, min(MAX_LEVEL, drawn))

    # -- the exchange -----------------------------------------------------

    def exchange(self, view: View) -> Hand:
        """Always take the full exchange; choose what to throw by rung.

        Taking everything on offer is not a judgement call -- measured over
        4,000 deals, an agent that under-exchanges throws away most of elder's
        advantage. What to *keep* is the judgement call.
        """
        rung = self._rung()
        if rung <= 1:
            ranked = sorted(view.hand, key=lambda c: (c.rank, c.suit))
        else:
            ranked = sorted(view.hand, key=lambda c: self._keep_value(c, view.hand))
        return Hand.of(*ranked[: view.exchange_limit])

    def _keep_value(self, card: Card, hand: Hand) -> float:
        """How much this card is worth holding on to.

        Weighs three things against each other: length, which wins the point;
        combination potential, which wins sequences and sets; and raw rank,
        which wins tricks. `discard_boldness` sets the exchange rate between the
        first two, which is exactly the judgement Hoyle wrote his 1744 treatise
        about.
        """
        bold = self.style.discard_boldness
        suit_length = len(hand.in_suit(card.suit))
        held = set(hand.ranks_in(card.suit))
        adjacent = sum(1 for step in (-2, -1, 1, 2) if card.rank + step in held)
        set_size = hand.count_of(card.rank) if card.rank.counts_for_set else 0
        trick_power = card.rank - Rank.SEVEN

        value = (
            (1.0 - bold) * 1.5 * suit_length
            + bold * (1.2 * adjacent + 1.6 * set_size)
            + 0.8 * trick_power
        )
        if not card.rank.counts_for_set:
            # "Players discard low cards (nine or lower) even if this means
            # getting rid of four or more of one suit."
            value -= 2.0
        return value

    # -- declaring --------------------------------------------------------

    def declare(self, view: View, category: Category) -> Declaration:
        """Declare everything, unless this opponent is the concealing sort.

        Sinking is only available at the top of the heuristic ladder, where the
        agent has enough sense to use the silence it buys. A later milestone
        replaces this crude rule with a mixed strategy from CFR; until then it
        is a habit, not a calculation.
        """
        full = Declaration.full(view.hand, category)
        if self._rung() < 4 or not full:
            return full
        if full.score > SINK_CEILING:
            return full
        if self.rng.random() < self.style.sinking:
            return Declaration.sink()
        return full

    # -- the play ---------------------------------------------------------

    def play(self, view: View) -> Card:
        rung = self._rung()
        legal = list(view.legal_plays)
        if len(legal) == 1:
            return legal[0]
        if rung <= 1:
            return max(legal, key=lambda c: (c.rank, c.suit))
        if view.current_trick is None:
            return self._lead(view, legal, rung)
        return self._follow(view, legal, rung)

    def _lead(self, view: View, legal: list[Card], rung: int) -> Card:
        """Run a suit. Which suit is what the upper rungs get better at.

        Each rung refines the one below rather than replacing it, so a rung can
        only improve on its predecessor -- a lesson learnt the hard way, when a
        plausible rule for cashing winners turned out to *lose* to the simpler
        rung beneath it.
        """
        avoid = self._opponent_long_suit(view) if rung >= 4 else None
        candidates = [c for c in legal if c.suit is not avoid] or legal

        def suit_strength(card: Card) -> tuple:
            length = len(view.hand.in_suit(card.suit))
            if rung >= 3:
                # Prefer a suit you can actually run: one where your cards are
                # already winners. Remembering what has been played is what
                # makes that visible.
                established = sum(
                    1 for other in view.hand.in_suit(card.suit)
                    if self._is_established(view, other)
                )
                return (established, length, card.rank)
            return (length, card.rank)

        return max(candidates, key=suit_strength)

    def _follow(self, view: View, legal: list[Card], rung: int) -> Card:
        led = view.current_trick.led
        beating = [
            c for c in legal if c.suit is led.suit and c.rank > led.rank
        ]
        if beating:
            # Win as cheaply as possible.
            return min(beating, key=lambda c: (c.rank, c.suit))

        # Cannot win: throw the lowest card. Style breaks the tie -- a player
        # who hoards guards would rather not strip a high card of its escort.
        if rung >= 3 and self.style.guard_retention:
            return min(
                legal,
                key=lambda c: (
                    (c.rank - Rank.SEVEN) + self._guard_cost(view, c), c.suit
                ),
            )
        return min(legal, key=lambda c: (c.rank, c.suit))

    # -- what each rung knows ---------------------------------------------

    def _is_established(self, view: View, card: Card) -> bool:
        """True if no card that could still beat this one is unaccounted for.

        Rung 3 and above. This is simply remembering what has been played, and
        it is the first capability that requires paying attention.
        """
        higher = view.unseen.in_suit(card.suit)
        return all(other.rank < card.rank for other in higher)

    def _guard_cost(self, view: View, card: Card) -> float:
        """What throwing this card would cost by exposing a higher one.

        Holding king-and-a-small-one, the small one is what
        keeps the king alive: throw it and the king falls to the ace. That is
        the stop card of the textbooks, and noticing it is a real skill.

        Measured in rank-units so it competes with the card's own rank rather
        than merely breaking ties between equal ranks. An earlier version put it
        behind rank in the sort key, where it could only fire when two legal
        cards happened to share a rank -- and so did nothing at all, which the
        tournament duly reported as a dead rung.

        Weighted by what is being protected: guarding a king is worth a great
        deal and guarding a ten is worth nothing. `guard_retention` decides how
        much this agent cares -- some players hoard stoppers and some run their
        own suits, and both are defensible, which is what makes it a style.
        """
        higher = [c for c in view.hand.in_suit(card.suit) if c.rank > card.rank]
        if not higher:
            return 0.0
        protected = max(c.rank for c in higher)
        worth = max(0, protected - Rank.TEN) / 4.0
        return self.style.guard_retention * 3.0 * worth

    def _opponent_long_suit(self, view: View) -> Optional[Suit]:
        """The opponent's point suit, if they had to show it.

        Rung 4 and above. A point that scored must be exposed on request, so
        this is information the rules hand over -- and leading into a known long
        suit is how tricks are given away.
        """
        for combination in view.seen:
            if isinstance(combination, Point):
                return combination.suit
        return None

    def __repr__(self) -> str:
        return f"HeuristicAgent(level={self.level}, name={self.name!r})"
