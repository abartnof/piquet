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
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Sequence as TypingSequence, Union

from piquet.cards import Card, Hand, Suit, full_deck
from piquet.combos import (
    CardSet,
    Comparison,
    Point,
    Sequence,
    best_point,
    compare_point,
    compare_sequence,
    compare_set,
    is_carte_blanche,
    sequences,
    sets,
)
from piquet.scoring import Category, Player, ScoreLog

__all__ = [
    "Phase", "Deal", "Declaration", "CategoryResult", "Trick",
    "deal_from", "deal_shuffled", "CARTE_BLANCHE_SCORE",
]

Combination = Union[Point, Sequence, CardSet]

HAND_SIZE = 12
TALON_SIZE = 8
ELDER_MAX_EXCHANGE = 5
CARTE_BLANCHE_SCORE = 10
TRICKS_PER_DEAL = 12
CARDS_SCORE = 10
CAPOT_SCORE = 40


class Phase(Enum):
    """Where a deal has got to. Only one action is legal in each phase."""

    ELDER_EXCHANGE = "elder_exchange"
    YOUNGER_EXCHANGE = "younger_exchange"
    DECLARE_POINT = "declare_point"
    DECLARE_SEQUENCES = "declare_sequences"
    DECLARE_SETS = "declare_sets"
    PLAY = "play"
    COMPLETE = "complete"



#: Which declaration each phase is contesting.
_PHASE_CATEGORY = {
    Phase.DECLARE_POINT: Category.POINT,
    Phase.DECLARE_SEQUENCES: Category.SEQUENCES,
    Phase.DECLARE_SETS: Category.SETS,
}

_NEXT_PHASE = {
    Phase.DECLARE_POINT: Phase.DECLARE_SEQUENCES,
    Phase.DECLARE_SEQUENCES: Phase.DECLARE_SETS,
    Phase.DECLARE_SETS: Phase.PLAY,
}

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

    def __str__(self) -> str:
        return (
            f"{self.category.name.lower()}: elder declares {self.elder}, "
            f"younger says {self.response}"
        )


@dataclass(frozen=True, slots=True)
class Trick:
    """One trick: a card led, and the card played to it."""

    leader: Player
    led: Card
    followed: Optional[Card] = None

    @property
    def complete(self) -> bool:
        return self.followed is not None

    @property
    def winner(self) -> Player:
        """The higher card of the suit led takes it. There are no trumps, so a
        card of another suit never wins, however high."""
        if self.followed is None:
            raise ValueError("the trick is not finished")
        if (
            self.followed.suit is self.led.suit
            and self.followed.rank > self.led.rank
        ):
            return self.leader.opponent
        return self.leader


@dataclass(frozen=True, slots=True)
class Deal:
    """One deal, mid-flight. Immutable; every action returns a new `Deal`."""

    hands: tuple[Hand, Hand]
    discards: tuple[Hand, Hand]
    talon: tuple[Card, ...]
    talon_taken: int
    phase: Phase
    log: ScoreLog

    #: Elder's declaration in the category being contested, awaiting younger's.
    elder_declaration: Optional[Declaration] = None
    #: How each category turned out, in order. For the tutor and the log.
    results: tuple[CategoryResult, ...] = ()
    #: Younger's winnings, withheld until elder has led to the first trick.
    younger_pending: tuple[tuple[int, Category, str], ...] = ()
    #: Tricks already played, in order.
    tricks: tuple[Trick, ...] = ()
    #: The trick in progress: led to, but not yet followed.
    current_trick: Optional[Trick] = None
    #: Who leads to the next trick. Elder leads to the first.
    leader: Player = Player.ELDER

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

    @property
    def to_declare(self) -> Optional[Player]:
        """Whose turn it is to declare, if the deal is in the dialogue.

        Elder always speaks first in each category; younger answers.
        """
        if self.phase not in _PHASE_CATEGORY:
            return None
        return Player.ELDER if self.elder_declaration is None else Player.YOUNGER

    @property
    def declaring_category(self) -> Optional[Category]:
        """Which category is being contested, if the deal is in the dialogue."""
        return _PHASE_CATEGORY.get(self.phase)

    @property
    def pending_for_younger(self) -> int:
        """What younger has won but not yet scored.

        She scores nothing until elder has led to the first trick, which is the
        whole reason only elder can ever score a pique.
        """
        return sum(amount for amount, _, _ in self.younger_pending)

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

    # -- the declaration dialogue -----------------------------------------

    def declare(self, player: Player, declaration: Declaration) -> Deal:
        """Announce a declaration in the category currently being contested.

        Elder speaks first and scores at once if he wins. Younger answers, and
        her winnings are withheld until elder has led to the first trick.
        """
        category = _PHASE_CATEGORY.get(self.phase)
        if category is None:
            raise ValueError(
                f"nothing is being declared: the deal is at {self.phase.value}"
            )
        if player is not self.to_declare:
            raise ValueError(
                f"{player} cannot declare out of turn: "
                f"{self.to_declare} is to speak in {category.name.lower()}"
            )

        declaration.validate(self.hand_of(player), category)

        if player is Player.ELDER:
            return replace(self, elder_declaration=declaration)

        elder_declaration = self.elder_declaration or Declaration.sink()
        comparison = _COMPARE[category](elder_declaration.best, declaration.best)
        result = CategoryResult(category, elder_declaration, declaration, comparison)

        log = self.log
        pending = self.younger_pending
        if result.winner is Player.ELDER:
            log = log.record(
                Player.ELDER, elder_declaration.score, category, str(elder_declaration)
            )
        elif result.winner is Player.YOUNGER:
            pending = pending + ((declaration.score, category, str(declaration)),)

        return replace(
            self,
            phase=_NEXT_PHASE[self.phase],
            elder_declaration=None,
            results=self.results + (result,),
            log=log,
            younger_pending=pending,
        )

    # -- the play ---------------------------------------------------------

    @property
    def to_play(self) -> Optional[Player]:
        """Whose turn it is to play a card, if the deal is in the play."""
        if self.phase is not Phase.PLAY:
            return None
        return self.leader if self.current_trick is None else self.leader.opponent

    def tricks_won(self, player: Player) -> int:
        return sum(1 for trick in self.tricks if trick.winner is player)

    def legal_plays(self, player: Optional[Player] = None) -> Hand:
        """The cards this player may legally play right now.

        The leader may lead anything. The second player must follow suit if he
        can, and may otherwise play any card. This is also what the tutor uses
        to rule moves out: an illegal move costs nothing to detect.
        """
        if player is None:
            player = self.to_play
        if player is None:
            return Hand.empty()
        hand = self.hand_of(player)
        if self.current_trick is None:
            return hand
        following = hand.in_suit(self.current_trick.led.suit)
        return following if following else hand

    def play(self, player: Player, card: Card) -> Deal:
        """Lead or follow with one card."""
        if self.phase is not Phase.PLAY:
            raise ValueError(
                f"no card can be played: the deal is at {self.phase.value}"
            )
        if player is not self.to_play:
            raise ValueError(
                f"{player} cannot play out of turn: {self.to_play} is to play"
            )
        if card not in self.hand_of(player):
            raise ValueError(f"{player} does not hold {card.code}")
        if card not in self.legal_plays(player):
            led = self.current_trick.led.suit
            raise ValueError(
                f"{player} must follow suit: {led.name.lower()} was led"
            )

        hands = _replace_at(
            self.hands, player.index, self.hand_of(player).remove(card)
        )

        if self.current_trick is None:
            return self._lead(player, card, hands)
        return self._follow(player, card, hands)

    def _lead(self, player: Player, card: Card, hands) -> Deal:
        log = self.log.record(player, 1, Category.PLAY, f"leads {card}")
        deal = replace(
            self, hands=hands, current_trick=Trick(player, card), log=log
        )
        if not self.tricks:
            # Younger declares only after elder has led to the first trick.
            # That single point is the whole reason she can never pique.
            deal = deal._release_youngers_declarations()
        return deal

    def _follow(self, player: Player, card: Card, hands) -> Deal:
        trick = replace(self.current_trick, followed=card)
        winner = trick.winner
        tricks = self.tricks + (trick,)

        log = self.log
        if winner is not trick.leader:
            log = log.record(winner, 1, Category.PLAY, f"wins with {card}")
        if len(tricks) == TRICKS_PER_DEAL:
            log = log.record(winner, 1, Category.PLAY, "last trick")

        deal = replace(
            self,
            hands=hands,
            tricks=tricks,
            current_trick=None,
            leader=winner,
            log=log,
        )
        if len(tricks) == TRICKS_PER_DEAL:
            deal = deal._finish()
        return deal

    def _release_youngers_declarations(self) -> Deal:
        log = self.log
        for amount, category, detail in self.younger_pending:
            log = log.record(Player.YOUNGER, amount, category, detail)
        return replace(self, log=log, younger_pending=())

    def _finish(self) -> Deal:
        """Score the cards, apply the pique or repique, and close the deal."""
        elder = self.tricks_won(Player.ELDER)
        younger = TRICKS_PER_DEAL - elder

        log = self.log
        if elder == TRICKS_PER_DEAL:
            log = log.record(Player.ELDER, CAPOT_SCORE, Category.CARDS, "capot")
        elif younger == TRICKS_PER_DEAL:
            log = log.record(Player.YOUNGER, CAPOT_SCORE, Category.CARDS, "capot")
        elif elder > younger:
            log = log.record(Player.ELDER, CARDS_SCORE, Category.CARDS, "the cards")
        elif younger > elder:
            log = log.record(Player.YOUNGER, CARDS_SCORE, Category.CARDS, "the cards")
        # Six each: the cards are divided and neither scores.

        return replace(self, phase=Phase.COMPLETE, log=log.with_bonuses())


def _replace_at(pair: tuple[Hand, Hand], index: int, value: Hand) -> tuple[Hand, Hand]:
    return (value, pair[1]) if index == 0 else (pair[0], value)


# --------------------------------------------------------------------------
# Dealing
# --------------------------------------------------------------------------


def deal_from(cards: TypingSequence[Card]) -> Deal:
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
