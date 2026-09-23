"""Measuring how strong an agent actually is.

Piquet deals are wildly uneven -- a single deal can score anything from nothing
to 170 -- so comparing two agents over independently shuffled deals is mostly
measuring who was dealt better cards. An early ad-hoc harness put rung 3 at
45.2% against rung 2 on one seed and 51.6% on another, a five-sigma
disagreement that was entirely deal luck.

The fix is **mirrored pairs**: every deal is played twice, once with each agent
as elder, and the pair is scored as a unit. Both agents meet the same cards from
both seats, so the deal cancels out and what is left is the difference between
them. It also cancels elder's advantage, which is worth about two and a half
points of win rate on its own.

Ratings come from Bradley-Terry fitted over the whole round robin, which is
order-independent -- unlike sequential Elo updates, where who played whom first
changes the answer.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from piquet.match import play_deal
from piquet.rules import deal_shuffled
from piquet.scoring import Player

__all__ = ["DuelResult", "duel", "round_robin", "ratings", "format_table"]

AgentFactory = Callable[[random.Random], object]


@dataclass(frozen=True, slots=True)
class DuelResult:
    """The outcome of one agent meeting another over mirrored pairs."""

    name_a: str
    name_b: str
    pairs: int
    a_wins: int
    b_wins: int
    drawn: int
    a_points: int
    b_points: int

    @property
    def a_win_rate(self) -> float:
        """Draws count as half, as they do in chess."""
        return (self.a_wins + 0.5 * self.drawn) / self.pairs if self.pairs else 0.5

    @property
    def margin(self) -> float:
        """Mean points by which A beats B per pair. The finer-grained measure."""
        return (self.a_points - self.b_points) / self.pairs if self.pairs else 0.0

    def __str__(self) -> str:
        return (
            f"{self.name_a} vs {self.name_b}: {100 * self.a_win_rate:.1f}% "
            f"({self.a_wins}-{self.b_wins}-{self.drawn}), "
            f"margin {self.margin:+.1f} points per pair"
        )


def duel(
    make_a: AgentFactory,
    make_b: AgentFactory,
    pairs: int,
    rng: Optional[random.Random] = None,
    deal_seed: Optional[float] = None,
) -> DuelResult:
    """Play `pairs` deals, each one twice with the seats swapped.

    Both agents get the same cards from both seats, so the only thing left to
    measure is how they played them.

    The deals come from their **own** generator. Drawing them from the same one
    the agents use means a stochastic agent shifts every later deal simply by
    consuming random numbers, so two pairings in the same round robin would face
    different cards for no reason. Pass `deal_seed` to give every pairing an
    identical set -- which makes the whole table a paired comparison, not just
    each duel within it.
    """
    rng = rng or random.Random()
    deals = random.Random(deal_seed if deal_seed is not None else rng.random())
    agent_a, agent_b = make_a(rng), make_b(rng)

    a_wins = b_wins = drawn = 0
    a_points = b_points = 0

    for _ in range(pairs):
        board = deal_shuffled(deals)

        first, _ = play_deal(agent_a, agent_b, deal=board)
        second, _ = play_deal(agent_b, agent_a, deal=board)

        a_total = first.log.total(Player.ELDER) + second.log.total(Player.YOUNGER)
        b_total = first.log.total(Player.YOUNGER) + second.log.total(Player.ELDER)

        a_points += a_total
        b_points += b_total
        if a_total > b_total:
            a_wins += 1
        elif b_total > a_total:
            b_wins += 1
        else:
            drawn += 1

    return DuelResult(
        name_a=getattr(agent_a, "name", "A"),
        name_b=getattr(agent_b, "name", "B"),
        pairs=pairs,
        a_wins=a_wins,
        b_wins=b_wins,
        drawn=drawn,
        a_points=a_points,
        b_points=b_points,
    )


def round_robin(
    factories: Sequence[AgentFactory],
    pairs: int,
    rng: Optional[random.Random] = None,
) -> list[DuelResult]:
    """Every agent against every other, once, over one shared set of deals."""
    rng = rng or random.Random()
    deal_seed = rng.random()
    results: list[DuelResult] = []
    for i, make_a in enumerate(factories):
        for make_b in factories[i + 1:]:
            results.append(duel(make_a, make_b, pairs, rng, deal_seed=deal_seed))
    return results


def ratings(
    results: Sequence[DuelResult],
    anchor: Optional[str] = None,
    iterations: int = 500,
    prior: float = 0.5,
) -> dict[str, float]:
    """Bradley-Terry strengths, reported on the Elo scale.

    Fitted by minorisation-maximisation, which converges to the maximum
    likelihood estimate regardless of the order games were played in.
    Sequential Elo updates do not have that property, and with a handful of
    agents the order would visibly change the answer. The model is Zermelo's,
    1929, invented to rate chess players and rediscovered by Bradley and Terry
    in 1952.

    `prior` is **Laplace's rule of succession**, 1774: every agent is credited
    with half a win and half a loss against a virtual opponent of average
    strength. Laplace's own question was what odds to give on a sunrise you
    have only ever seen succeed, and it is exactly ours -- a maximum-likelihood
    fit answers "certain" and sends the loser's strength to zero and its rating
    to minus infinity.

    An earlier version floored the strength at 1e-9 instead. That stops the
    crash and leaves the number meaningless: a shut-out anchor made the table
    read ~3,700 for everyone, set entirely by the floor constant, and one
    single win collapsed it to ~713. A rating scale should not be
    discontinuous at the result the harness exists to produce.
    """
    names: list[str] = []
    for result in results:
        for name in (result.name_a, result.name_b):
            if name not in names:
                names.append(name)

    wins = {name: 0.0 for name in names}
    games: dict[tuple[str, str], float] = {}
    for result in results:
        a, b = result.name_a, result.name_b
        wins[a] += result.a_wins + 0.5 * result.drawn
        wins[b] += result.b_wins + 0.5 * result.drawn
        games[(a, b)] = games.get((a, b), 0.0) + result.pairs

    # Strengths are renormalised to a mean of one each sweep, so the virtual
    # opponent of "average strength" sits at exactly 1.0.
    strength = {name: 1.0 for name in names}
    for _ in range(iterations):
        updated = {}
        for name in names:
            denominator = 2.0 * prior / (strength[name] + 1.0)
            for (a, b), played in games.items():
                if name in (a, b):
                    denominator += played / (strength[a] + strength[b])
            updated[name] = max((wins[name] + prior) / denominator, 1e-12)
        total = sum(updated.values()) or 1.0
        strength = {name: value * len(names) / total for name, value in updated.items()}

    base = strength.get(anchor) if anchor else None
    if not base:
        base = math.exp(sum(math.log(v) for v in strength.values()) / len(strength))
    return {
        name: 400.0 * math.log10(value / base) for name, value in strength.items()
    }


def format_table(results: Sequence[DuelResult], anchor: Optional[str] = None) -> str:
    """A readable summary: pairwise results, then the fitted ratings."""
    lines = [str(result) for result in results]
    lines.append("")
    lines.append(f"{'agent':<18}{'rating':>9}")
    scores = ratings(results, anchor=anchor)
    for name, rating in sorted(scores.items(), key=lambda kv: -kv[1]):
        lines.append(f"{name:<18}{rating:>9.0f}")
    return "\n".join(lines)
