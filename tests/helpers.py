"""Fixture helpers for building specific deals.

Writing a deal out card by card is how the awkward cases get tested, so these
take two explicit hands and fill the talon with whatever is left of the pack.
"""

from __future__ import annotations

from piquet.cards import Card, Hand, full_deck, parse_hand
from piquet.combos import is_carte_blanche
from piquet.rules import CARTE_BLANCHE_SCORE, Deal, Phase, deal_from
from piquet.scoring import Category, Player, ScoreLog

__all__ = ["deal_with", "declaring", "remaining_after"]


def remaining_after(*hands: Hand) -> list[Card]:
    """The cards of the pack not in any of the given hands, in index order."""
    held = Hand.empty()
    for hand in hands:
        held = held | hand
    return [card for card in full_deck() if card not in held]


def deal_with(elder: str, younger: str) -> Deal:
    """A fresh deal with these two hands; the talon is whatever is left."""
    elder_hand, younger_hand = parse_hand(elder), parse_hand(younger)
    talon = remaining_after(elder_hand, younger_hand)
    if len(talon) != 8:
        raise ValueError(
            f"hands of {len(elder_hand)} and {len(younger_hand)} leave "
            f"{len(talon)} talon cards; a deal needs 12, 12 and 8"
        )
    return deal_from(list(elder_hand) + list(younger_hand) + talon)


def declaring(elder: str, younger: str) -> Deal:
    """A deal wound past the exchange, holding exactly these hands.

    Built directly rather than by exchanging, because any exchange would change
    the hands and the point of these fixtures is to fix them.
    """
    elder_hand, younger_hand = parse_hand(elder), parse_hand(younger)
    talon = remaining_after(elder_hand, younger_hand)
    if len(talon) != 8:
        raise ValueError(f"these hands leave {len(talon)} talon cards, not 8")

    log = ScoreLog()
    for player, hand in ((Player.ELDER, elder_hand), (Player.YOUNGER, younger_hand)):
        if is_carte_blanche(hand):
            log = log.record(
                player, CARTE_BLANCHE_SCORE, Category.CARTE_BLANCHE, "carte blanche"
            )

    return Deal(
        hands=(elder_hand, younger_hand),
        discards=(Hand.empty(), Hand.empty()),
        talon=tuple(talon),
        talon_taken=len(talon),
        phase=Phase.DECLARE_POINT,
        log=log,
    )
