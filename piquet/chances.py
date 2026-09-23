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

import random
from functools import lru_cache
from typing import Sequence

from piquet.partie import PARTIE_BONUS, RUBICON, Partie, Side, Standing
from piquet.scoring import Player

__all__ = [
    "CAP", "MEASURED", "density", "survival", "chance_of",
    "chance_of_the_rubicon", "in_words",
    "settlement_of", "expected_settlement", "point_weights", "weights_for",
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


# --------------------------------------------------------------------------
# What a partie position is worth
# --------------------------------------------------------------------------
#
# The odds above answer a question about one side. Valuing a *position* needs
# the pair, and the two scores in a deal are not independent -- measured over
# 4,000 deals they correlate at -0.47, because only one player wins each
# declaration category and only one takes the cards. Convolving the marginals
# and multiplying would therefore be wrong, so the joint is kept as sampled
# pairs instead and nothing is assumed about its shape.

_PAIRS = (
     64,  18,  56,   9, 119,   2,  37,   4,  29,  18,  27,   7,  28,  24,  27,  21,  10,  16,  13,  23,
     13,  37,  22,   5,  14,  42,   5,  30,  11,  16,  25,  16,  41,   8,  18,  17,  24,  12,  28,   7,
     42,   5,  16,   7,  62,   7,  16,  13,  30,   5,  16,  18,  30,   8,  14,  28,   8,  19,  42,   8,
     26,  20,  22,  13,   7,  25,   7,  38,  26,  29,  32,   6,  26,   7,  11,  26,  22,  25,  38,   9,
     18,  31,  20,  29,  22,  26,   4, 113,  26,  23,  30,  24,  17,   7,  29,   8,  10,  39,   5,  29,
     20,   8,  32,   8,  36,  11,  28,  10,  10,  11,  18, 102,  31,  10,  60,   7,  14,  23,  21,  30,
     26,   6,   4,  45,  40,  19,  12,  23,  16,  18,   9,  41,  27,  10,  10,  29,  27,  21,   7, 104,
     18,  19,  13,  23,  33,   6,   5,  31,  14,  26,  74,   6,  20,   8,  76,   4,  37,  11,  11,  38,
      8,  29,  31,  10,  24,  15,  32,   9,  31,  19,  28,  13, 116,   5,  19,  15,  23,  14,   5,  34,
     10,  29,   6,  44,  28,   9,  25,  26,   6,  24,  23,  29,  71,   6,  11,  18, 101,   0,  29,   6,
     40,  12,  71,   4,  28,  10,  27,  27,  36,   5,  16,  18, 117,   4,  30,   9,  28,  12,   9,  27,
     22,  18,   5, 110,  30,   5,  29,   5,  45,   9,   7,  29,  10,  25,  23,   4,  78,   5,  30,  10,
     15,   7,  32,   9,  38,   4,  10,  29,  74,   3,  17,  10,  23,   6,  40,  12,  32,  11,  27,  24,
     42,   7,  12,  31,  40,  12,  12,  19,  22,   7,  22,  99,   9,  24,  15,  11,  29,  21,  35,   6,
     32,   7,  27,   4,  30,  10,  30,   5,  11,  24,  11,  28,   3,  35,  36,  10,   8,  17,  11,  38,
     21,  12,  13,  26,  27,  21,  34,   5,  28,  14,  30,  18,  10,  25,   7,  31,   3,  31,  40,   8,
     34,   5,  32,   6,  29,  10,   5,  37,  59,   5,  21,  29,  23,  12,   8,  41,  41,   6,  28,  25,
     67,  24,  29,  11,  19,  34,  11,  27,   5,  40,  16,  18,  43,   7,  34,   5,   5,  44,  23,   8,
     31,  11,  11,  37,  26,  12, 112,   3,  34,   9,  70,   3,  33,  17,  18,  28,  39,  11,   6,  25,
     63,  14,  32,  11,  28,   6,  46,   9,  24,  22,  72,   3,  24,  10,  10,  48, 113,   2,  20,  26,
      7,  26,  27,   9,  46,   8,  26,  29,  12,  29,  75,   5,   6,  45,  10,  24,   8,  12,  24,  18,
     20,  22,  28,  12,  30,  11,  31,   5,   7,  33,  19,  21,  10,  27,   9,  43,  26,  28,  18,  17,
     73,   5,  14,  19,  30,  13,  53,  94,  24,  15,  59,  21,   2,  46,  11,   7,  43,   9,  10,  29,
      5,  44,  29,   9,  22,  14,  22,  14,  79,   4,  76,   3,  19,  34,  40,  11,  11,  29,  24,   9,
     21,  19,  71,   3,   9,  34,  17,  12,  22,  12,  27,  11,  33,  11,   4,  37,   5,  29,  32,   5,
     23,  23,  65,   7,  12,  27,  11,  27,   8,  22,  43,   5,  26,  14,  15,   7,   6,  21,  77,   4,
     32,   5,   9,  44,   4,  38,  19,   9,  41,   9,  63,   7,  11,  29,  38,  13,  63,   7,  20,  28,
     22,  14,  27,  32,  30,   7,  16,  23,  23,   7,   6,  33,  37,  24,  19,  22,  27,   4,  25,  26,
    116,   2,  25,  10,   4,  30,   7,  39,   5,  47,   7,  27,  21,  11,  42,   9,  36,  12,  40,   8,
     29,  11,  23,  17,  12,  28,  38,  27,  20,  30,  14,  26,  27,   6,   7,  40,  20,  94,  25,  12,
      8,  20,  35,  25,  24,  38,   6,  44,   4,  34,   5,  30,  12,  28,  30,  12,  32,   4,  40,  10,
     12,   7,  40,   7,  63,   5,  14,  10,  77,   3,  22,  20,  34,   9,  21,  17,  32,  19,  25,  10,
     35,   9,  19,  23,  12,  27,  27,  16,  31,  18,  74,   6,  20,  26,  12,  21,  23,  22,  34,  14,
      6,  31,   9,  30,  13,  36,   7,  14,   5,  44,  12,  25,  60,   7,   6,  24,  51,   7,  40,   9,
     38,   5,  23,  15,  39,  11,  14,  25,  32,  10,   7,  32,  30,  10,  25,  14,  30,   5,  41,   5,
     10,  28,   7, 103,  28,  24,  10,  37,  11,  29,  33,   5,  18,  18,  29,   8,  30,   5,   8,  40,
     19,  31,  26,  30,  26,  26,  25,  11,  36,   9,  22,  25,  20,  25,  15,  38,  29,   8,  43,   9,
    112,   5,  28,  12,  78,   5,  14,  25,  17,  22,  29,  10,  31,   8,  14,  26, 113,   2,  14,  11,
     33,  14,  11,  24,  26,  21,  28,  19,  26,  14,  35,  13,  26,   7,   8,  32,  77,   5,  13,  11,
     20,  13,   7,  43,  44,   9,  17,  11,  78,   5,  25,  26,   7,  31,  36,   3,  40,   7,  77,   2,
     75,   3,  52,  11,  29,   8,  24,  21,  75,   5,  10,  26,  43,  11,  28,  21,  43,   8,  23,  14,
     28,   5,  22,   8,  75,   4,   7,  30, 113,   6,  32,   5, 117,   5,  24,  18,  15,  37,  26,  26,
    115,   6,  11,  27,  12,  13,  34,   5,  81,   2,  19,  99,  18,   8,  10,  27,   5,  36,  22,  12,
     40,  11,  17,   7,  27,   8,  16,  10,  26,   9,  33,   5,   3,  49,  17,   7,   4,  47,  28,  10,
     11,  24,  17,  13,   5,  30,  44,   8,  30,   9,  41,  11,  18,  21,  29,   6,  19,  18,  72,   4,
      5,  30,   5, 110,  14,  21,  22,   8,  10,  44,  32,   6,  26,  15,  16,  13,   4, 115,  73,   5,
     98,   7,  44,   6,   8,  37,  29,  18, 117,   4,  24,  18,  10,  16,  15,  18,   8,  19,  34,  13,
      8,  45,  26,   5,  24,  22,  38,   8,  12,  14,   5,  33,  19,  24, 112,   2,  41,  24,  36,   8,
     14,  21,  19,  10,   7,  29,  13,  27,  14,  11,  17,  11,  26,  25,  19,   8,  73,   4,   7,  30,
     62,   7,  19,  28,  77,   3,  39,  15,  13,  28,  41,   5,  19,  30,  33,   8,  40,   4,  22,  30,
)


#: Draws taken when valuing a position. They are the **same** draws every
#: time, which is what makes a finite difference between two positions almost
#: exact rather than two noisy numbers subtracted -- common random numbers,
#: the oldest variance reduction there is.
_DRAWS = 3000

#: How far a finite difference steps. One point is too fine: the settlement
#: has a kink at exactly a hundred, and a single-point step lands on or off it
#: by luck. Three smooths that without ceasing to be local.
_STEP = 3


@lru_cache(maxsize=64)
def _futures(deals_left: int, elder_first: bool) -> tuple[tuple[int, int], ...]:
    """Sampled (my points, their points) over the deals that remain.

    The seats alternate, as they do in a partie, so a side that is elder next
    is younger the deal after -- which is most of why the two sides of a
    sampled pair cannot simply be averaged.
    """
    pairs = [(_PAIRS[i], _PAIRS[i + 1]) for i in range(0, len(_PAIRS), 2)]
    rng = random.Random(1674)       # fixed: a position always values the same
    out = []
    for _ in range(_DRAWS):
        mine = theirs = 0
        elder = elder_first
        for _ in range(deals_left):
            scored = rng.choice(pairs)
            mine += scored[0] if elder else scored[1]
            theirs += scored[1] if elder else scored[0]
            elder = not elder
        out.append((mine, theirs))
    return tuple(out)


def settlement_of(mine: int, theirs: int) -> int:
    """What a finished partie pays me, signed.

    The difference plus a hundred if the loser reached a hundred, and the sum
    plus a hundred if they did not -- and the guard is on the *loser*, so two
    players who crawl to 60 and 40 settle for 200.
    """
    if mine == theirs:
        return 0
    high, low = max(mine, theirs), min(mine, theirs)
    points = (high + low if low < RUBICON else high - low) + PARTIE_BONUS
    return points if mine > theirs else -points


@lru_cache(maxsize=8192)
def expected_settlement(
    mine: int, theirs: int, deals_left: int, elder_first: bool
) -> float:
    """The mean settlement from here, over the deals that remain."""
    if deals_left <= 0:
        return float(settlement_of(mine, theirs))
    futures = _futures(deals_left, bool(elder_first))
    total = 0
    for gained, conceded in futures:
        total += settlement_of(mine + gained, theirs + conceded)
    return total / len(futures)


def point_weights(
    mine: int, theirs: int, deals_left: int, elder_first: bool
) -> tuple[float, float]:
    """What one more point to each side is worth, measured in settlement.

    The bridge from *points in a deal* to *points in a partie*, and the whole
    reason an agent has to see the standing at all. Three regimes, and only
    the first is the one every agent in this project has been playing:

    Measured at 220 against a varying opponent with one deal to play, the
    shape is not even monotonic:

        they are on      0    20    40    55    70    88   100   130
        a point to them  +0.6  +1.0  +1.0  -0.2  -5.1  -9.4  -1.0  -1.0

    Four regimes, and only the last is the one every agent in this project has
    been playing:

    - **both safely over the line** — about +1 and −1, and maximising the deal
      margin is correct;
    - **near level** — worth two or three times that, because the settlement
      is the difference *plus a hundred* and that hundred changes hands at the
      tie;
    - **I am short and the partie is ending** — a point to me is worth a
      multiple of one, because crossing turns what I pay from the *sum* into
      the *difference*;
    - **they are short** — and this one is strange. While a hundred is out of
      their reach their points are worth **+1 to me**, because a rubiconed
      loser pays the sum and their score is part of it. Close enough to
      threaten it and the sign flips hard: at 88 a point to them costs me
      nine, because carrying them over costs twice their whole score.

    Nothing in that last row has any counterpart inside a single deal, which
    is why no amount of tuning a deal-level heuristic could have found it.
    """
    if deals_left <= 0:
        return (0.0, 0.0)
    here = expected_settlement(mine, theirs, deals_left, elder_first)
    gained = expected_settlement(mine + _STEP, theirs, deals_left, elder_first)
    conceded = expected_settlement(mine, theirs + _STEP, deals_left, elder_first)
    return ((gained - here) / _STEP, (conceded - here) / _STEP)


def weights_for(standing: Standing, elder: bool) -> tuple[float, float]:
    """`point_weights` read straight off a player's `Standing`."""
    return point_weights(
        standing.mine, standing.theirs, standing.deals_left, elder
    )
