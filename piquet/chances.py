"""The chances of scoring so much in a deal.

Hoyle's word. His 1744 treatise is a table of chances for the exchange, and
this is the same question asked about the rubicon: *"I am on eighty-two with
one deal left and I am elder -- what are the odds I reach a hundred?"*

Almost every uncertainty in piquet is uncertainty about the *opponent*, and
reading one of those needs a model of how they choose, which is why the
inference and declaration work waits on CFR (docs/DESIGN.md section 6.4b). This
question is the exception. A distribution over deal scores is a distribution
over the deck and over our own play, with nothing hidden inside it, so it can
be measured straight out of the engine. It is the only probabilistic question
in the game that is not waiting on something unbuilt.

**What the table is, and what it is not.** It is 20,000 deals of rung-4 play, one
histogram per seat. It is therefore a statement about *rung-4* play: a stronger
agent scores more and a weaker one less. Deal luck swamps skill in piquet,
which is why the shape survives the change of rung tolerably -- rung 1 and rung
4 differ by about a fifth in the tails -- but it is indicative and not exact.
Measure your own and pass it as `table` if you need better.

Scores above 120 are folded into the top bucket. A single deal that large
already clears any question anyone would ask of this module.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from piquet.partie import RUBICON, Partie, Side
from piquet.scoring import Player

__all__ = [
    "CAP", "MEASURED", "density", "survival", "chance_of",
    "chance_of_the_rubicon", "in_words",
]

#: The top bucket; everything above it is folded in.
CAP = 120

_ELDER_COUNTS = (
       0,   33,   74,  166,  247,  433,  679,  701,  610,  353,  517,  608,   # 0
     509,  410,  384,  328,  240,  238,  281,  603,  405,  353,  658,  554,   # 12
     584,  624,  680,  620,  663,  510,  481,  388,  363,  348,  306,  255,   # 24
     276,  275,  287,  334,  251,  228,  205,  170,   97,   79,   59,   21,   # 36
      17,   27,   22,   19,   19,   44,   11,    5,   48,    9,    1,   78,   # 48
      43,   38,   52,   51,   35,   20,   30,   21,    1,    3,   64,   77,   # 60
     114,  169,  170,  185,  169,  153,  113,   66,   38,   26,    0,    1,   # 72
       5,    2,    0,    0,    1,    0,    0,    0,    0,    0,    1,    0,   # 84
       4,    5,    6,    7,    7,   14,   18,   14,   13,   12,    6,    6,   # 96
      10,   18,   26,   33,   31,   33,   40,   35,   45,   34,   25,   28,   # 108
      94,   # 120
)

_YOUNGER_COUNTS = (
     113,    0,  274,  306,  821, 1041, 1020, 1006,  689,  782, 1116,  802,   # 0
     680,  627,  460,  397,  302,  264,  548,  455,  261,  394,  467,  519,   # 12
     621,  596,  555,  545,  441,  358,  357,  299,  256,  238,  199,  165,   # 24
     180,  128,  137,  130,  152,  126,  128,  113,  106,  114,   89,   87,   # 36
      49,   25,   16,   16,    4,    1,    2,    2,    5,    1,    0,    0,   # 48
       0,    0,    0,    0,    0,    0,    0,    2,    0,    0,    5,    0,   # 60
       6,   10,    2,    5,    2,    3,    4,    3,    0,    4,    1,    0,   # 72
       0,    1,    1,    0,    0,    1,    0,    1,    0,    3,    6,    6,   # 84
      16,   18,   16,   22,   13,   15,   10,   20,   10,    6,    5,    3,   # 96
      12,   13,   14,   13,   14,   13,   18,   15,   12,    9,   16,   11,   # 108
      35,   # 120
)


def _normalise(counts: Sequence[int]) -> tuple[float, ...]:
    total = sum(counts) or 1
    return tuple(c / total for c in counts)


#: Deal-score densities, indexed by `Player.index`. A tuple rather than a dict
#: so it can be hashed, and so the convolutions below can be cached on it.
MEASURED: tuple[tuple[float, ...], tuple[float, ...]] = (
    _normalise(_ELDER_COUNTS),
    _normalise(_YOUNGER_COUNTS),
)


def density(seat: Player, table=MEASURED) -> tuple[float, ...]:
    """P(this seat scores exactly *i*) in one deal, for i in 0..CAP."""
    return table[seat.index]


def survival(seat: Player, table=MEASURED) -> tuple[float, ...]:
    """P(this seat scores *at least* i) in one deal, for i in 0..CAP."""
    rows = density(seat, table)
    out, running = [0.0] * len(rows), 0.0
    for i in range(len(rows) - 1, -1, -1):
        running += rows[i]
        out[i] = running
    return tuple(out)


def _convolve(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    out = [0.0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        if not x:
            continue
        for j, y in enumerate(b):
            if y:
                out[i + j] += x * y
    return tuple(out)


@lru_cache(maxsize=64)
def _over_several(deals_left: int, elder_first: bool, table) -> tuple[float, ...]:
    """The density of a side's total over the deals that remain.

    The deal alternates, so a side plays elder, younger, elder... from
    whichever seat it is in next. That alternation is most of the reason the
    two seats need separate histograms at all: elder averages about 29 a deal
    and younger about 20.
    """
    total = (1.0,)
    elder = elder_first
    for _ in range(deals_left):
        total = _convolve(total, table[Player.ELDER.index if elder else Player.YOUNGER.index])
        elder = not elder
    return total


def chance_of(
    needed: int, deals_left: int, elder_first: bool, table=MEASURED
) -> float:
    """The chance of scoring at least `needed` over the deals that remain.

    `elder_first` says whether this side sits elder in the next of them; after
    that the deal alternates, as it does in a partie.
    """
    if needed <= 0:
        return 1.0
    if deals_left <= 0:
        return 0.0
    spread = _over_several(deals_left, bool(elder_first), table)
    return sum(spread[needed:])


def chance_of_the_rubicon(partie: Partie, side: Side, table=MEASURED) -> float:
    """The chance this side gets over a hundred, from where the partie stands.

    The number the last deal of a partie is really about. Failing to cross
    costs you the *sum* of both scores rather than the difference, so a player
    who is short is playing a different game from one who is not -- and telling
    them which game they are in is most of what a scoreboard is for.
    """
    return chance_of(
        RUBICON - partie.score_of(side),
        partie.deals_left,
        partie.elder is side,
        table,
    )


#: Fractions a person can hold in their head. A player deciding whether to
#: gamble thinks in odds, not percentages, and so does the game's own
#: literature -- Hoyle says "three to two against", never "forty per cent".
_FRACTIONS = (
    (1, 10), (1, 6), (1, 5), (1, 4), (1, 3), (2, 5),
    (1, 2), (3, 5), (2, 3), (3, 4), (4, 5), (9, 10),
)


def in_words(p: float) -> str:
    """A phrase a player can act on rather than a number they must interpret."""
    if p >= 0.97:
        return "all but certain"
    if p <= 0.03:
        return "barely possible"
    numerator, denominator = min(
        _FRACTIONS, key=lambda f: abs(f[0] / f[1] - p)
    )
    return f"about {numerator} in {denominator}"
