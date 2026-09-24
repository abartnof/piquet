"""Agents: the players' brains.

An agent sees a deal only through a `View`, never through the `Deal` itself, so
it cannot consult the opponent's hand even by mistake.

Strength is a **ladder of capabilities**, not a dial of noise (docs/DESIGN.md
section 7). Each rung adds something a human player also has to learn, so a weak
opponent is weak in a comprehensible, human-shaped way -- you can form a theory
of it and beat it, which you cannot do with randomness. `RandomAgent` sits below
the bottom rung: it is the baseline everything else is measured against.
"""

from __future__ import annotations

import random
from typing import Protocol, runtime_checkable

from piquet.cards import Card, Hand
from piquet.observation import View
from piquet.rules import Declaration
from piquet.scoring import Category

__all__ = ["Agent", "RandomAgent"]


@runtime_checkable
class Agent(Protocol):
    """What every player -- human, heuristic or searching -- must provide."""

    name: str

    def exchange(self, view: View) -> Hand:
        """Which cards to discard. Between one and `view.exchange_limit`."""
        ...

    def declare(self, view: View, category: Category) -> Declaration:
        """What to announce in this category. May be less than is held."""
        ...

    def play(self, view: View) -> Card:
        """Which card to lead or follow with, from `view.legal_plays`."""
        ...


class RandomAgent:
    """Legal moves chosen at random. The baseline, below the ladder's first rung.

    It randomises only the genuinely strategic choices -- which cards to throw
    and which card to play -- while making the structurally obvious ones:
    exchange as many cards as allowed, and declare everything held. An agent
    that threw points away arbitrarily would be a misleading baseline.

    The default matters more than it looks. Measured over 4,000 deals, elder
    wins 52.5% when both players take the full exchange but only 49.6% when
    they take a random number, so elder's advantage is not automatic -- it has
    to be *used*. That is the empirical backing for Britannica's remark that
    elder "in practice usually exchanges five cards".

    `exchange_size="random"` and `sink_probability` both give deliberately
    weaker opponents.
    """

    def __init__(
        self,
        rng: random.Random | None = None,
        sink_probability: float = 0.0,
        exchange_size: str = "max",
        name: str = "random",
    ) -> None:
        self.rng = rng or random.Random()
        self.sink_probability = sink_probability
        self.exchange_size = exchange_size
        self.name = name

    def exchange(self, view: View) -> Hand:
        count = (
            view.exchange_limit
            if self.exchange_size == "max"
            else self.rng.randint(1, view.exchange_limit)
        )
        return Hand.of(*self.rng.sample(list(view.hand), count))

    def declare(self, view: View, category: Category) -> Declaration:
        if self.rng.random() < self.sink_probability:
            return Declaration.sink()
        return Declaration.full(view.hand, category)

    def play(self, view: View) -> Card:
        return self.rng.choice(list(view.legal_plays))

    def __repr__(self) -> str:
        return f"RandomAgent({self.name!r})"
