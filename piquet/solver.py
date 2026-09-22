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

from typing import Iterator, Optional

from piquet.cards import Card, Hand
from piquet.heuristics import MAX_LEVEL, HeuristicAgent
from piquet.inference import possible_hands
from piquet.observation import View
from piquet.scoring import Player

__all__ = [
    "solve", "best_card", "card_values", "SolverAgent",
    "TRICKS", "CARDS_BONUS", "CAPOT_BONUS", "pique_is_live",
]

TRICKS = 12
CARDS_BONUS = 10
CAPOT_BONUS = 40

_SUIT_MASKS = tuple(0xFF << (suit * 8) for suit in range(4))
_NO_CARD = -1


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


def _distinct(hand: int, legal: int, unplayed: int) -> Iterator[int]:
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


def _cards_bonus(elder_tricks: int) -> int:
    """Ten for the cards, forty for a capot, nothing at six each."""
    if elder_tricks == TRICKS:
        return CAPOT_BONUS
    if elder_tricks == 0:
        return -CAPOT_BONUS
    if elder_tricks > TRICKS // 2:
        return CARDS_BONUS
    if elder_tricks < TRICKS // 2:
        return -CARDS_BONUS
    return 0


def solve(
    elder: Hand,
    younger: Hand,
    leader: Player = Player.ELDER,
    led: Optional[Card] = None,
    elder_tricks: int = 0,
) -> int:
    """The best achievable elder-minus-younger score for the rest of the play.

    Both hands are known: this is the double-dummy value, and the outer layer is
    responsible for averaging it over the hands younger might actually hold.

    `elder_tricks` is how many tricks elder has already taken in this deal. The
    cards bonus assumes the deal runs to twelve tricks in total, so a position
    with three cards each belongs with `elder_tricks` plus younger's making
    nine.
    """
    return _search(
        elder.bits,
        younger.bits,
        0 if leader is Player.ELDER else 1,
        _NO_CARD if led is None else led.index,
        elder_tricks,
        {},
    )


def _search(
    elder: int,
    younger: int,
    leader: int,
    led: int,
    elder_tricks: int,
    memo: dict,
) -> int:
    """Memoised minimax, deliberately without alpha-beta.

    The two do not mix naively: a pruned branch yields a *bound*, not a value,
    so storing it in a plain transposition table and reusing it as exact is
    simply wrong. Doing it properly means tagging every entry with whether it is
    exact, a lower bound or an upper bound. The table alone turns out to be fast
    enough here, so the sound-and-simple version wins until measurement says
    otherwise.
    """
    if not elder and not younger and led == _NO_CARD:
        return _cards_bonus(elder_tricks)

    # One packed integer rather than a five-tuple: hashing a single int is
    # appreciably cheaper, and this key is computed at every node.
    key = elder | (younger << 32) | (leader << 64) | ((led + 1) << 65) | (
        elder_tricks << 71
    )
    cached = memo.get(key)
    if cached is not None:
        return cached

    turn = leader if led == _NO_CARD else 1 - leader
    hand = elder if turn == 0 else younger
    unplayed = elder | younger | (0 if led == _NO_CARD else 1 << led)
    legal = _legal(hand, led)

    maximising = turn == 0
    best = None

    for card in _distinct(hand, legal, unplayed):
        remaining = hand & ~(1 << card)
        if led == _NO_CARD:
            # Leading. A point is scored for every card led, whoever wins it.
            value = (1 if turn == 0 else -1) + _search(
                remaining if turn == 0 else elder,
                younger if turn == 0 else remaining,
                leader,
                card,
                elder_tricks,
                memo,
            )
        else:
            follower_wins = _beats(card, led)
            winner = turn if follower_wins else leader
            next_elder = remaining if turn == 0 else elder
            next_younger = younger if turn == 0 else remaining
            gained = 1 if follower_wins else 0
            if not next_elder and not next_younger:
                gained += 1     # the winner of the last trick scores two
            value = (gained if winner == 0 else -gained) + _search(
                next_elder,
                next_younger,
                winner,
                _NO_CARD,
                elder_tricks + (winner == 0),
                memo,
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
) -> tuple[Card, int]:
    """The best card for whoever is to play, and what it is worth.

    The value is still elder-minus-younger, so younger's best card is the one
    that makes it smallest.
    """
    turn_is_elder = (leader is Player.ELDER) == (led is None)
    hand = elder if turn_is_elder else younger
    candidates = _legal(hand.bits, _NO_CARD if led is None else led.index)

    best_value = None
    chosen = None
    for index in _bits(candidates):
        card = Card.from_index(index)
        played = Hand(hand.bits & ~(1 << index))
        if led is None:
            value = (1 if turn_is_elder else -1) + solve(
                played if turn_is_elder else elder,
                younger if turn_is_elder else played,
                leader,
                card,
                elder_tricks,
            )
        else:
            follower_wins = _beats(index, led.index)
            winner = Player.ELDER if (
                (turn_is_elder and follower_wins)
                or (not turn_is_elder and not follower_wins)
            ) else Player.YOUNGER
            next_elder = played if turn_is_elder else elder
            next_younger = younger if turn_is_elder else played
            gained = 1 if follower_wins else 0
            if not next_elder.bits and not next_younger.bits:
                gained += 1
            value = (gained if winner is Player.ELDER else -gained) + solve(
                next_elder,
                next_younger,
                winner,
                None,
                elder_tricks + (winner is Player.ELDER),
            )

        if best_value is None or (
            value > best_value if turn_is_elder else value < best_value
        ):
            best_value, chosen = value, card

    return chosen, best_value


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
) -> dict[Card, int]:
    """What every legal card is worth, from elder's point of view.

    All the root moves share one transposition table, because their subtrees
    overlap almost entirely. Evaluating each card with a fresh search instead
    costs several times as much for the same answer.
    """
    memo: dict = {}
    turn_is_elder = (leader is Player.ELDER) == (led is None)
    hand = elder if turn_is_elder else younger
    legal = _legal(hand.bits, _NO_CARD if led is None else led.index)

    values: dict[Card, int] = {}
    for index in _bits(legal):
        rest = hand.bits & ~(1 << index)
        if led is None:
            values[Card.from_index(index)] = (1 if turn_is_elder else -1) + _search(
                rest if turn_is_elder else elder.bits,
                younger.bits if turn_is_elder else rest,
                0 if leader is Player.ELDER else 1,
                index,
                elder_tricks,
                memo,
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
            values[Card.from_index(index)] = (
                gained if winner_is_elder else -gained
            ) + _search(
                next_elder,
                next_younger,
                0 if winner_is_elder else 1,
                _NO_CARD,
                elder_tricks + winner_is_elder,
                memo,
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

    def __init__(self, *args, exact_from: int = 8, max_worlds: int = 30, **kwargs):
        kwargs.setdefault("level", MAX_LEVEL)
        super().__init__(*args, **kwargs)
        self.exact_from = exact_from
        self.max_worlds = max_worlds
        self.name = kwargs.get("name") or f"solver{exact_from}"

    def play(self, view: View) -> Card:
        legal = list(view.legal_plays)
        if len(legal) == 1:
            return legal[0]
        if len(view.hand) > self.exact_from:
            return super().play(view)

        worlds = possible_hands(view, limit=self.max_worlds)
        if not worlds:
            return super().play(view)

        elder_tricks = sum(
            1 for trick in view.tricks if trick.winner is Player.ELDER
        )
        i_lead = view.current_trick is None
        leader = view.me if i_lead else view.opponent
        led = None if i_lead else view.current_trick.led
        sign = 1 if view.me is Player.ELDER else -1

        totals: dict[Card, int] = {card: 0 for card in legal}
        for opponent_hand in worlds:
            elder = view.hand if view.me is Player.ELDER else opponent_hand
            younger = opponent_hand if view.me is Player.ELDER else view.hand
            for card, value in card_values(
                elder, younger, leader, led, elder_tricks
            ).items():
                if card in totals:
                    totals[card] += sign * value
        return max(totals, key=lambda c: (totals[c], -c.rank))
