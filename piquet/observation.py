"""What each player is allowed to know.

This is the most load-bearing module in the project. Agents read the game
*only* through a `View`: if it leaks, every strength measurement we take is
meaningless, and if it is too strict, a bot forgets things the rules expressly
permit it to consult.

Three asymmetries matter more than any other. Elder may look at all five of his
talon cards even when he takes fewer, so he always knows five cards younger
does not. If he takes fewer than five, younger draws from the top of what is
left -- which begins inside his five -- so he also *watches her take* cards he
has already read. And each player "keeps his discards by him, and may refer to
them during play" (Cavendish), so consulting your own discards is not cheating.

Together these are what collapse the play phase to a handful of consistent
opponent hands -- see docs/DESIGN.md section 4.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from piquet.cards import Card, Hand
from piquet.rules import (
    Announcement,
    Deal,
    ELDER_MAX_EXCHANGE,
    Phase,
    Trick,
)
from piquet.scoring import Category, Player, ScoreLog

__all__ = ["View", "view_for"]


@dataclass(frozen=True, slots=True)
class View:
    """One player's legal knowledge of a deal in progress.

    Everything here is either public at the table or private to `me`. Nothing
    in it can be used to reconstruct the opponent's hand except by inference,
    which is exactly the point.

    Note what is deliberately *absent*: the opponent's `Declaration` objects.
    An earlier version handed over the whole `CategoryResult`, which carries the
    suits of every claim -- including claims that were beaten and so never had
    to be shown. `heard` and `seen` replace it, and they are not the same thing:
    you always hear the shape, and you only get to see the cards of a
    combination that scored or tied.
    """

    me: Player
    phase: Phase
    hand: Hand
    my_discards: Hand
    #: Talon cards this player has legitimately seen.
    talon_seen: tuple[Card, ...]
    #: Talon cards this player read and then watched the opponent draw, and
    #: which the opponent must therefore still be holding. Certain knowledge,
    #: and the only certain knowledge of the other hand this game ever gives.
    watched_them_take: Hand
    talon_remaining: int
    exchange_limit: int
    #: How each settled category came out. Public: the scores are called aloud.
    outcomes: tuple[tuple[Category, Optional[Player]], ...]
    #: What the opponent said aloud in settled categories -- always public, but
    #: it names a shape ("point of five"), never a suit.
    heard: tuple[Announcement, ...]
    #: The opponent's combinations that had to be exposed, because they scored
    #: or because the category was equal. A beaten declaration is never shown,
    #: so its owner gives away the shape of the holding but not its suit.
    seen: tuple[object, ...]
    #: The opponent's declaration waiting on this player's answer, if any.
    awaiting_answer: Optional[Announcement]
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
        holdings starts here -- but it does not end here, because
        `watched_them_take` is accounted for and in the opponent's hand at
        once. Those must be *added* to every candidate rather than enumerated,
        which is what `inference.possible_hands` does.
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


def _played_by(deal: Deal, player: Player) -> Hand:
    """Every card this player has already put on the table."""
    played = Hand.empty()
    for trick in (*deal.tricks, deal.current_trick):
        if trick is None:
            continue
        if trick.leader is player:
            played = played | Hand.of(trick.led)
        elif trick.followed is not None:
            played = played | Hand.of(trick.followed)
    return played


def _watched_them_take(deal: Deal, player: Player) -> Hand:
    """Talon cards this player read and then watched the opponent draw.

    Only elder ever has any. He looks at all five of his whether he takes them
    or not; if he exchanges fewer, younger draws from the top of what is left,
    which begins inside his five. She discards *before* she draws, so a card
    she takes in front of him cannot have been thrown away and is certainly in
    her hand.

    What comes back is what she is holding *now*, so cards she has since played
    drop out of it.
    """
    if player is not Player.ELDER:
        return Hand.empty()
    elder_took = len(deal.discard_of(Player.ELDER))
    younger_took = len(deal.discard_of(Player.YOUNGER))
    overlap = deal.talon[
        elder_took:min(ELDER_MAX_EXCHANGE, elder_took + younger_took)
    ]
    if not overlap:
        return Hand.empty()
    return Hand.of(*overlap) - _played_by(deal, Player.YOUNGER)


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


def _has_spoken(deal: Deal, player: Player) -> bool:
    """Whether this player has named their combinations yet.

    Elder names and scores his as the dialogue goes along. Younger names none
    of hers until elder has led to the first trick -- so for the whole of the
    sequence and set dialogue, and for the card he chooses to lead, elder knows
    only whether each of her holdings beat his.
    """
    return player is Player.ELDER or deal.elder_has_led


def _heard(deal: Deal, player: Player) -> tuple[Announcement, ...]:
    """What the opponent announced in settled categories. Always public."""
    opponent = player.opponent
    if not _has_spoken(deal, opponent):
        return ()
    spoken = (result.announcement_of(opponent) for result in deal.results)
    return tuple(a for a in spoken if a is not None)


def _seen(deal: Deal, player: Player) -> tuple:
    """The opponent's combinations this player is entitled to have looked at.

    Nothing can be asked for before it has been declared, so younger shows
    elder nothing until he has led.
    """
    opponent = player.opponent
    if not _has_spoken(deal, opponent):
        return ()
    return tuple(c for result in deal.results for c in result.shown(opponent))


def _awaiting_answer(deal: Deal, player: Player) -> Optional[Announcement]:
    """Elder's declaration, heard by younger before she must answer it.

    She learns the shape -- "point of five" -- and neither the suit nor the pip
    total, which is what makes answering "good" or "not good" a decision rather
    than a lookup. If the shapes match she says "equal", and he answers with
    his number; that is `CategoryResult.announcement_of`, one step later.
    """
    if deal.to_declare is not player or player is not Player.YOUNGER:
        return None
    if deal.elder_declaration is None or deal.declaring_category is None:
        return None
    spoken = deal.elder_declaration.announce(deal.declaring_category)
    return None if spoken is None else spoken.shape


def view_for(deal: Deal, player: Player) -> View:
    """Everything `player` may legally know about this deal, and nothing else."""
    return View(
        me=player,
        phase=deal.phase,
        hand=deal.hand_of(player),
        my_discards=deal.discard_of(player),
        talon_seen=_talon_seen(deal, player),
        watched_them_take=_watched_them_take(deal, player),
        talon_remaining=deal.talon_remaining,
        exchange_limit=deal.exchange_limit(player),
        outcomes=tuple((r.category, r.winner) for r in deal.results),
        heard=_heard(deal, player),
        seen=_seen(deal, player),
        awaiting_answer=_awaiting_answer(deal, player),
        log=deal.log,
        tricks=deal.tricks,
        current_trick=deal.current_trick,
        legal_plays=deal.legal_plays(player) if deal.to_play is player else Hand.empty(),
        to_act=_to_act(deal, player),
    )
