"""What each player is allowed to know.

This is the most load-bearing module in the project. Agents read the game
*only* through a `View`: if it leaks, every strength measurement we take is
meaningless, and if it is too strict, a bot forgets things the rules expressly
permit it to consult.

Two asymmetries matter more than any other. Elder may look at all five of his
talon cards even when he takes fewer, so he always knows five cards younger
does not. And each player "keeps his discards by him, and may refer to them
during play" (Cavendish), so consulting your own discards is not cheating.

Together these are what collapse the play phase to a handful of consistent
opponent hands -- see docs/DESIGN.md section 4.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from piquet.cards import Card, Hand
from piquet.rules import CategoryResult, Deal, ELDER_MAX_EXCHANGE, Phase, Trick
from piquet.scoring import Player, ScoreLog

__all__ = ["View", "view_for"]


@dataclass(frozen=True, slots=True)
class View:
    """One player's legal knowledge of a deal in progress.

    Everything here is either public at the table or private to `me`. Nothing
    in it can be used to reconstruct the opponent's hand except by inference,
    which is exactly the point.
    """

    me: Player
    phase: Phase
    hand: Hand
    my_discards: Hand
    #: Talon cards this player has legitimately seen.
    talon_seen: tuple[Card, ...]
    talon_remaining: int
    exchange_limit: int
    #: The declaration dialogue so far. Both players hear all of it.
    results: tuple[CategoryResult, ...]
    #: Scores are called aloud, so the whole log is public.
    log: ScoreLog
    #: Cards already played are public, and may be reviewed.
    tricks: tuple[Trick, ...]
    current_trick: Optional[Trick]
    legal_plays: Hand
    to_act: bool

    @property
    def opponent(self) -> Player:
        return self.me.opponent

    @property
    def unseen(self) -> Hand:
        """Every card this player cannot account for.

        These are the cards that might be in the opponent's hand, in their
        discards, or still in the talon. Enumerating the opponent's possible
        holdings starts here.
        """
        seen = self.hand.bits | self.my_discards.bits
        for card in self.talon_seen:
            seen |= 1 << card.index
        for trick in (*self.tricks, self.current_trick):
            if trick is None:
                continue
            seen |= 1 << trick.led.index
            if trick.followed is not None:
                seen |= 1 << trick.followed.index
        return Hand(~seen & 0xFFFFFFFF)

    def __str__(self) -> str:
        return f"{self.me} at {self.phase.value}: {self.hand}"


def _talon_seen(deal: Deal, player: Player) -> tuple[Card, ...]:
    """The talon cards this player has legitimately looked at.

    Elder sees all five of his, whether or not he takes them: "if he exchanges
    fewer than five, he can look at the remainder of the five." Younger sees
    only what she actually drew -- she may look at cards she leaves only by
    exposing them to both players, which we do not model as an action yet.
    """
    elder_took = len(deal.discard_of(Player.ELDER))
    younger_took = len(deal.discard_of(Player.YOUNGER))

    if player is Player.ELDER:
        if deal.phase is Phase.ELDER_EXCHANGE:
            return ()
        return deal.talon[:ELDER_MAX_EXCHANGE]

    if deal.phase in (Phase.ELDER_EXCHANGE, Phase.YOUNGER_EXCHANGE):
        return ()
    return deal.talon[elder_took:elder_took + younger_took]


def _to_act(deal: Deal, player: Player) -> bool:
    if deal.phase in (Phase.ELDER_EXCHANGE, Phase.YOUNGER_EXCHANGE):
        return player is (
            Player.ELDER if deal.phase is Phase.ELDER_EXCHANGE else Player.YOUNGER
        )
    if deal.to_declare is not None:
        return player is deal.to_declare
    if deal.to_play is not None:
        return player is deal.to_play
    return False


def view_for(deal: Deal, player: Player) -> View:
    """Everything `player` may legally know about this deal, and nothing else."""
    return View(
        me=player,
        phase=deal.phase,
        hand=deal.hand_of(player),
        my_discards=deal.discard_of(player),
        talon_seen=_talon_seen(deal, player),
        talon_remaining=deal.talon_remaining,
        exchange_limit=deal.exchange_limit(player),
        results=deal.results,
        log=deal.log,
        tricks=deal.tricks,
        current_trick=deal.current_trick,
        legal_plays=deal.legal_plays(player) if deal.to_play is player else Hand.empty(),
        to_act=_to_act(deal, player),
    )
