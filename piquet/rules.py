"""The rules engine: a deal as an immutable state machine.

A `Deal` carries everything about one deal of the six in a partie, and every
action returns a *new* `Deal` rather than mutating. That keeps a deal safe to
hold inside a search node, and makes the whole state trivially serialisable --
which is what will let a future JavaScript port be a mechanical translation
rather than a rewrite.

This module knows the rules. It does not know what a good move is, and it never
decides anything on a player's behalf.

Authority: Cavendish, *The Laws of Piquet adopted by the Portland and Turf
Clubs* (1892). See docs/PIQUET.md for the rules in prose.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from piquet.cards import Card, Hand, full_deck
from piquet.combos import is_carte_blanche
from piquet.scoring import Category, Player, ScoreLog

__all__ = ["Phase", "Deal", "deal_from", "deal_shuffled", "CARTE_BLANCHE_SCORE"]

HAND_SIZE = 12
TALON_SIZE = 8
ELDER_MAX_EXCHANGE = 5
CARTE_BLANCHE_SCORE = 10


class Phase(Enum):
    """Where a deal has got to. Only one action is legal in each phase."""

    ELDER_EXCHANGE = "elder_exchange"
    YOUNGER_EXCHANGE = "younger_exchange"
    DECLARE_POINT = "declare_point"
    DECLARE_SEQUENCES = "declare_sequences"
    DECLARE_SETS = "declare_sets"
    PLAY = "play"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class Deal:
    """One deal, mid-flight. Immutable; every action returns a new `Deal`."""

    hands: tuple[Hand, Hand]
    discards: tuple[Hand, Hand]
    talon: tuple[Card, ...]
    talon_taken: int
    phase: Phase
    log: ScoreLog

    # -- reading ----------------------------------------------------------

    def hand_of(self, player: Player) -> Hand:
        return self.hands[player.index]

    def discard_of(self, player: Player) -> Hand:
        return self.discards[player.index]

    @property
    def talon_remaining(self) -> int:
        """How many talon cards are still available to be taken."""
        return len(self.talon) - self.talon_taken

    @property
    def talon_untaken(self) -> tuple[Card, ...]:
        return self.talon[self.talon_taken:]

    def exchange_limit(self, player: Player) -> int:
        """The most cards this player may exchange, right now.

        Elder is entitled to five. Younger is entitled to whatever elder left,
        which is usually three.
        """
        if player is Player.ELDER:
            return min(ELDER_MAX_EXCHANGE, self.talon_remaining)
        return self.talon_remaining

    # -- the exchange -----------------------------------------------------

    def exchange(self, player: Player, discard: Hand) -> Deal:
        """Discard some cards and take the same number from the talon.

        Cards are taken in order from the top of the stock (Law 23), so younger
        draws from wherever elder stopped.
        """
        expected = (
            Phase.ELDER_EXCHANGE if player is Player.ELDER else Phase.YOUNGER_EXCHANGE
        )
        if self.phase is not expected:
            raise ValueError(
                f"{player} cannot exchange out of turn: the deal is at {self.phase.value}"
            )

        count = len(discard)
        if count < 1:
            # Cotton, 1674: "the Gamesters are both obliged to discard one Card
            # at least." Cavendish's Laws 21 and 22 say the same. His Laws of
            # Piquet au Cent say the opposite, but that is a different game.
            raise ValueError(f"{player} must discard at least one card")

        limit = self.exchange_limit(player)
        if player is Player.ELDER and count > ELDER_MAX_EXCHANGE:
            raise ValueError(
                f"elder may exchange at most five cards, not {count}"
            )
        if count > limit:
            raise ValueError(
                f"{player} may take at most {limit}: only {self.talon_remaining} "
                f"talon cards remain"
            )

        hand = self.hand_of(player)
        if (discard - hand):
            missing = (discard - hand).code
            raise ValueError(f"{player} does not hold: {missing}")

        taken = self.talon[self.talon_taken:self.talon_taken + count]
        new_hand = (hand - discard) | Hand.of(*taken)

        hands = _replace_at(self.hands, player.index, new_hand)
        discards = _replace_at(
            self.discards, player.index, self.discard_of(player) | discard
        )
        next_phase = (
            Phase.YOUNGER_EXCHANGE if player is Player.ELDER else Phase.DECLARE_POINT
        )
        return Deal(
            hands=hands,
            discards=discards,
            talon=self.talon,
            talon_taken=self.talon_taken + count,
            phase=next_phase,
            log=self.log,
        )


def _replace_at(pair: tuple[Hand, Hand], index: int, value: Hand) -> tuple[Hand, Hand]:
    return (value, pair[1]) if index == 0 else (pair[0], value)


# --------------------------------------------------------------------------
# Dealing
# --------------------------------------------------------------------------


def deal_from(cards: Sequence[Card]) -> Deal:
    """Deal from an explicit ordering of the pack.

    The first twelve cards go to elder, the next twelve to younger, and the
    last eight form the talon. Real dealing alternates in twos or threes, but
    only the resulting distribution matters to the rules, and a deterministic
    order lets any deal be written down as a fixture.
    """
    if len(cards) != 32 or len(set(cards)) != 32:
        raise ValueError(
            f"a deal needs the 32 distinct cards of the piquet pack, got {len(cards)} "
            f"({len(set(cards))} distinct)"
        )

    elder = Hand.of(*cards[:HAND_SIZE])
    younger = Hand.of(*cards[HAND_SIZE:HAND_SIZE * 2])
    talon = tuple(cards[HAND_SIZE * 2:])

    log = ScoreLog()
    for player, hand in ((Player.ELDER, elder), (Player.YOUNGER, younger)):
        if is_carte_blanche(hand):
            # Announced as soon as it is noticed, so it is logged before
            # anything else -- which is also where Law 67 puts it.
            log = log.record(
                player, CARTE_BLANCHE_SCORE, Category.CARTE_BLANCHE, "carte blanche"
            )

    return Deal(
        hands=(elder, younger),
        discards=(Hand.empty(), Hand.empty()),
        talon=talon,
        talon_taken=0,
        phase=Phase.ELDER_EXCHANGE,
        log=log,
    )


def deal_shuffled(rng: Optional[random.Random] = None) -> Deal:
    """Shuffle and deal. Pass a seeded `Random` to make a deal reproducible."""
    cards = list(full_deck())
    (rng or random).shuffle(cards)
    return deal_from(cards)
