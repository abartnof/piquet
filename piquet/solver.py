"""Exact solution of the play phase.

Piquet's play is small enough to solve outright rather than approximate. Twelve
tricks, two players, no trumps, strict follow-suit: a far easier problem than
bridge's double dummy, and the reason `docs/DESIGN.md` §6.1 puts no learning at
all into this part of the game.

Everything here works on **bitmask hands and plain integers**, not on `Deal`
objects. A `Deal` is immutable and carries a score log, which is exactly right
for the rules and exactly wrong for a search that visits millions of nodes.

The value returned is always **elder minus younger**, so elder maximises and
younger minimises. That keeps one number flowing through the recursion instead
of a pair, and the sign convention never changes.

Known limitation: the search scores trick points, the last trick, and the cards
or capot bonus, but not a **pique**. A pique needs elder to reach thirty before
younger has reckoned anything at all, which requires younger to have declared
nothing whatever -- see `pique_is_live`, which says when the omission could
matter.
"""

from __future__ import annotations

import random
from typing import Iterator, Optional

from piquet.cards import Card, Hand
from piquet.chances import weights_for
from piquet.heuristics import MAX_LEVEL, HeuristicAgent
from piquet.inference import possible_hands
from piquet.observation import View
from piquet.scoring import Player
from piquet.style import BALANCED, Style

__all__ = [
    "solve", "best_card", "card_values", "SolverAgent",
    "TRICKS", "CARDS_BONUS", "CAPOT_BONUS", "pique_is_live", "EVEN",
]

TRICKS = 12
CARDS_BONUS = 10
CAPOT_BONUS = 40

_SUIT_MASKS = tuple(0xFF << (suit * 8) for suit in range(4))
_NO_CARD = -1

#: What a point to each seat is worth. The default is the deal objective --
#: a point is a point, whoever gets it -- and anything else is the partie
#: objective, where they are not (see `chances.point_weights`). Elder always
#: maximises `w_elder * E - w_younger * Y` and younger always minimises it,
#: which works because the settlement is zero-sum: both sides agree on the
#: same number and pull in opposite directions.
EVEN = (1.0, 1.0)


def _bits(mask: int) -> Iterator[int]:
    """Card indexes in a bitmask, lowest first."""
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def _legal(hand: int, led: int) -> int:
    """The cards that may be played: follow suit if you can, else anything."""
    if led == _NO_CARD:
        return hand
    following = hand & _SUIT_MASKS[led >> 3]
    return following or hand


def _beats(played: int, led: int) -> bool:
    """A card wins only by being higher in the suit led. There are no trumps."""
    return played >> 3 == led >> 3 and played > led


def _distinct(legal: int, unplayed: int) -> Iterator[int]:
    """Legal plays, skipping cards that are interchangeable with a cheaper one.

    Two cards in the same suit are equivalent when every card between them has
    already gone: holding the king with the queen and jack out of play, the king
    and ten do exactly the same work. Trying only the lower of each run is a
    sound reduction and cuts the tree substantially.
    """
    for card in _bits(legal):
        below = card - 1
        if (
            below >= 0
            and below >> 3 == card >> 3
            and not (unplayed >> below) & 1
        ):
            # The card directly beneath is already gone; walk down the run and
            # skip this card if an equivalent, cheaper one is also legal.
            probe = below
            while probe >= 0 and probe >> 3 == card >> 3 and not (unplayed >> probe) & 1:
                probe -= 1
            if probe >= 0 and probe >> 3 == card >> 3 and (legal >> probe) & 1:
                continue
        yield card


def _check_position(
    elder: Hand, younger: Hand, leader: Player, led: Optional[Card]
) -> None:
    """Reject a position whose two hands cannot both be true.

    At the start of a trick both players hold the same number of cards; once
    one has been led the leader holds one fewer. Given anything else the search
    runs a player out of cards, finds no legal move, and returns `None`, which
    surfaces as a `TypeError` several frames deep in the recursion. The check
    is one subtraction and the alternative is undebuggable.
    """
    gap = 1 if led is not None else 0
    short, tall = (
        (elder, younger) if leader is Player.ELDER else (younger, elder)
    )
    if len(tall) - len(short) != gap:
        raise ValueError(
            f"{leader} leads holding {len(short)} cards against {len(tall)}; "
            f"with {'a card led' if led is not None else 'no card led'} the "
            f"difference must be {gap}"
        )


def _credit(to_elder: bool, amount: float, weights: tuple[float, float]) -> float:
    """What `amount` scored by one seat is worth, in elder-minus-younger."""
    return weights[0] * amount if to_elder else -weights[1] * amount


def _cards_bonus(elder_tricks: int, weights: tuple[float, float] = EVEN) -> float:
    """Ten for the cards, forty for a capot, nothing at six each."""
    if elder_tricks == TRICKS:
        return _credit(True, CAPOT_BONUS, weights)
    if elder_tricks == 0:
        return _credit(False, CAPOT_BONUS, weights)
    if elder_tricks > TRICKS // 2:
        return _credit(True, CARDS_BONUS, weights)
    if elder_tricks < TRICKS // 2:
        return _credit(False, CARDS_BONUS, weights)
    return 0.0


def solve(
    elder: Hand,
    younger: Hand,
    leader: Player = Player.ELDER,
    led: Optional[Card] = None,
    elder_tricks: int = 0,
    weights: tuple[float, float] = EVEN,
) -> float:
    """The best achievable elder-minus-younger score for the rest of the play.

    Both hands are known: this is the double-dummy value, and the outer layer is
    responsible for averaging it over the hands younger might actually hold.

    `elder_tricks` is how many tricks elder has already taken in this deal. The
    cards bonus assumes the deal runs to twelve tricks in total, so a position
    with three cards each belongs with `elder_tricks` plus younger's making
    nine.
    """
    _check_position(elder, younger, leader, led)
    return _search(
        elder.bits,
        younger.bits,
        0 if leader is Player.ELDER else 1,
        _NO_CARD if led is None else led.index,
        elder_tricks,
        {},
        weights,
    )


def _search(
    elder: int,
    younger: int,
    leader: int,
    led: int,
    elder_tricks: int,
    memo: dict,
    weights: tuple[float, float] = EVEN,
) -> float:
    """Memoised minimax, deliberately without alpha-beta.

    The two do not mix naively: a pruned branch yields a *bound*, not a value,
    so storing it in a plain transposition table and reusing it as exact is
    simply wrong. Doing it properly means tagging every entry with whether it is
    exact, a lower bound or an upper bound. The table alone turns out to be fast
    enough here, so the sound-and-simple version wins until measurement says
    otherwise.
    """
    if not elder and not younger and led == _NO_CARD:
        return _cards_bonus(elder_tricks, weights)

    # One packed integer rather than a five-tuple: hashing a single int is
    # appreciably cheaper, and this key is computed at every node.
    key = elder | (younger << 32) | (leader << 64) | ((led + 1) << 65) | (
        elder_tricks << 71
    )
    cached = memo.get(key)
    if cached is not None:
        return cached

    # Unpacked once rather than called per node: `_search` visits millions of
    # them and a function call each is a measurable share of the whole search.
    w_elder, w_younger = weights
    turn = leader if led == _NO_CARD else 1 - leader
    hand = elder if turn == 0 else younger
    unplayed = elder | younger | (0 if led == _NO_CARD else 1 << led)
    legal = _legal(hand, led)

    maximising = turn == 0
    best = None

    for card in _distinct(legal, unplayed):
        remaining = hand & ~(1 << card)
        if led == _NO_CARD:
            # Leading. A point is scored for every card led, whoever wins it.
            value = (w_elder if turn == 0 else -w_younger) + _search(
                remaining if turn == 0 else elder,
                younger if turn == 0 else remaining,
                leader,
                card,
                elder_tricks,
                memo,
                weights,
            )
        else:
            follower_wins = _beats(card, led)
            winner = turn if follower_wins else leader
            next_elder = remaining if turn == 0 else elder
            next_younger = younger if turn == 0 else remaining
            gained = 1 if follower_wins else 0
            if not next_elder and not next_younger:
                gained += 1     # the winner of the last trick scores two
            value = (
                w_elder * gained if winner == 0 else -w_younger * gained
            ) + _search(
                next_elder,
                next_younger,
                winner,
                _NO_CARD,
                elder_tricks + (winner == 0),
                memo,
                weights,
            )

        if best is None or (value > best if maximising else value < best):
            best = value

    memo[key] = best
    return best


def best_card(
    elder: Hand,
    younger: Hand,
    leader: Player = Player.ELDER,
    led: Optional[Card] = None,
    elder_tricks: int = 0,
    weights: tuple[float, float] = EVEN,
) -> tuple[Card, float]:
    """The best card for whoever is to play, and what it is worth.

    The value is still elder-minus-younger, so elder takes the largest and
    younger the smallest. An earlier version re-implemented the root expansion
    and gave every candidate its own transposition table, which cost several
    times as much for exactly the same answer.
    """
    values = card_values(elder, younger, leader, led, elder_tricks, weights)
    turn_is_elder = (leader is Player.ELDER) == (led is None)
    pick = max if turn_is_elder else min
    card = pick(values, key=lambda candidate: values[candidate])
    return card, values[card]


def pique_is_live(younger_declared: int) -> bool:
    """Whether a pique is still possible, and so whether `solve` is incomplete.

    A pique needs elder to reach thirty before younger has reckoned anything at
    all. Younger's declarations are scored the moment elder leads to the first
    trick, so unless she declared precisely nothing the window is shut before a
    card is played and the solver's omission cannot matter.
    """
    return younger_declared == 0


def card_values(
    elder: Hand,
    younger: Hand,
    leader: Player = Player.ELDER,
    led: Optional[Card] = None,
    elder_tricks: int = 0,
    weights: tuple[float, float] = EVEN,
) -> dict[Card, float]:
    """What every legal card is worth, from elder's point of view.

    All the root moves share one transposition table, because their subtrees
    overlap almost entirely. Evaluating each card with a fresh search instead
    costs several times as much for the same answer.
    """
    _check_position(elder, younger, leader, led)
    memo: dict = {}
    turn_is_elder = (leader is Player.ELDER) == (led is None)
    hand = elder if turn_is_elder else younger
    legal = _legal(hand.bits, _NO_CARD if led is None else led.index)

    values: dict[Card, float] = {}
    for index in _bits(legal):
        rest = hand.bits & ~(1 << index)
        if led is None:
            values[Card.from_index(index)] = _credit(
                turn_is_elder, 1, weights
            ) + _search(
                rest if turn_is_elder else elder.bits,
                younger.bits if turn_is_elder else rest,
                0 if leader is Player.ELDER else 1,
                index,
                elder_tricks,
                memo,
                weights,
            )
        else:
            follower_wins = _beats(index, led.index)
            winner_is_elder = (
                turn_is_elder if follower_wins else leader is Player.ELDER
            )
            next_elder = rest if turn_is_elder else elder.bits
            next_younger = younger.bits if turn_is_elder else rest
            gained = 1 if follower_wins else 0
            if not next_elder and not next_younger:
                gained += 1
            values[Card.from_index(index)] = _credit(
                winner_is_elder, gained, weights
            ) + _search(
                next_elder,
                next_younger,
                0 if winner_is_elder else 1,
                _NO_CARD,
                elder_tricks + winner_is_elder,
                memo,
                weights,
            )
    return values


class SolverAgent(HeuristicAgent):
    """Rung 5: heuristic play early, exact play once the endgame is reachable.

    Solving the whole play from twelve cards would take about twenty seconds in
    Python, which is far too slow to sit in front of. Solving from eight is a
    few hundredths of a second, so the agent plays by rule of thumb until the
    endgame comes into range and then plays it perfectly.

    That is not a compromise so much as where the value is. The cards bonus and
    the capot are decided in the endgame, and the endgame is exactly the part a
    human finds hardest to calculate.

    The hands the opponent might hold come from `inference`; each is solved and
    the results averaged. This is perfect-information Monte Carlo, and it
    inherits that method's blind spot: it assumes the opponent can see through
    the table too, so it never sets a trap that depends on their ignorance.
    """

    def __init__(
        self,
        level: int = MAX_LEVEL,
        style: Style = BALANCED,
        erraticism: float = 0.0,
        rng: Optional["random.Random"] = None,
        name: Optional[str] = None,
        exact_from: int = 8,
        max_worlds: int = 30,
    ) -> None:
        # Spelled out rather than forwarded through *args and **kwargs: the
        # forwarding version injected a default `level` into kwargs and then
        # crashed if anyone passed one positionally.
        super().__init__(level, style, erraticism, rng, name or f"solver{exact_from}")
        self.exact_from = exact_from
        self.max_worlds = max_worlds

    def weights(self, view: View) -> tuple[float, float]:
        """What a point to each seat is worth, given where the partie stands.

        The search wants the pair in *seat* order and `chances` reports it in
        *my* order, so which way round they go depends on which chair I am in.
        A point to them is normally worth about minus one, which is why the
        second weight is negated: the search subtracts it.

        Only the ratio decides anything, so the pair is scaled to keep the
        numbers civil. `EVEN` for a deal played on its own, which is the whole
        tournament harness and most of the test suite.
        """
        if view.partie is None:
            return EVEN
        mine, theirs = weights_for(view.partie, view.me is Player.ELDER)
        pair = (mine, -theirs) if view.me is Player.ELDER else (-theirs, mine)
        scale = max(abs(pair[0]), abs(pair[1]))
        if scale < 1e-6:
            return EVEN
        return (pair[0] / scale, pair[1] / scale)

    def play(self, view: View) -> Card:
        legal = list(view.legal_plays)
        if len(legal) == 1:
            return legal[0]
        if len(view.hand) > self.exact_from:
            return super().play(view)

        worlds = possible_hands(view, limit=self.max_worlds, rng=self.rng)
        if not worlds:
            return super().play(view)

        elder_tricks = sum(
            1 for trick in view.tricks if trick.winner is Player.ELDER
        )
        i_lead = view.current_trick is None
        leader = view.me if i_lead else view.opponent
        led = None if i_lead else view.current_trick.led
        sign = 1 if view.me is Player.ELDER else -1

        weights = self.weights(view)
        totals: dict[Card, float] = {card: 0.0 for card in legal}
        for opponent_hand in worlds:
            elder = view.hand if view.me is Player.ELDER else opponent_hand
            younger = opponent_hand if view.me is Player.ELDER else view.hand
            for card, value in card_values(
                elder, younger, leader, led, elder_tricks, weights
            ).items():
                if card in totals:
                    totals[card] += sign * value
        return max(totals, key=lambda c: (totals[c], -c.rank))
