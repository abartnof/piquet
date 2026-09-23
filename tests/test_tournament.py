"""Tests for measuring agent strength.

The harness exists because deal luck swamps skill. An early ad-hoc version put
rung 3 at 45.2% against rung 2 on one seed and 51.6% on another -- a
five-sigma disagreement that was entirely the cards. Mirrored pairs fixed it.
"""

import random

import pytest

from piquet.agents import RandomAgent
from piquet.heuristics import MAX_LEVEL, HeuristicAgent
from piquet.style import BALANCED, CALIBRATED, Style
from piquet.tournament import DuelResult, duel, format_table, ratings, round_robin


def L(level):
    return lambda rng: HeuristicAgent(level, rng=rng, name=f"L{level}")


def R(rng):
    return RandomAgent(rng, name="random")


# --------------------------------------------------------------------------
# Duels
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_a_duel_plays_every_deal_from_both_seats():
    result = duel(L(2), L(1), 40, random.Random(1674))
    assert result.pairs == 40
    assert result.a_wins + result.b_wins + result.drawn == 40


@pytest.mark.slow
def test_two_identical_agents_are_exactly_level():
    """The sharpest check that the mirroring works: the same agent playing
    itself must come out level, because elder's advantage cancels.

    These rungs are deterministic, so "level" here is not a statistical claim
    but an exact one -- every pair is drawn, to the point. Asserting a
    tolerance would let a real asymmetry hide inside it.
    """
    result = duel(L(3), L(3), 250, random.Random(1674))
    assert result.margin == 0.0
    assert result.drawn == result.pairs


@pytest.mark.slow
def test_mirroring_holds_up_against_agents_that_roll_dice():
    """With erraticism the two halves of a pair are no longer identical, so
    this one really is statistical -- and it is the case the harness is for."""
    def erratic(rng):
        return HeuristicAgent(3, erraticism=0.5, rng=rng, name="erratic")

    result = duel(erratic, erratic, 250, random.Random(1674))
    assert abs(result.a_win_rate - 0.5) < 0.08
    assert abs(result.margin) < 2.0


@pytest.mark.slow
def test_the_same_seed_gives_the_same_answer():
    a = duel(L(2), L(1), 60, random.Random(7))
    b = duel(L(2), L(1), 60, random.Random(7))
    assert a == b


@pytest.mark.slow
def test_a_duel_reports_both_a_win_rate_and_a_points_margin():
    """Win rate is coarse -- a deal won by one point counts the same as a
    capot -- so the margin is the finer instrument."""
    result = duel(L(4), R, 60, random.Random(1674))
    assert result.a_win_rate > 0.8
    assert result.margin > 10


@pytest.mark.slow
def test_draws_count_as_half():
    result = DuelResult("a", "b", pairs=10, a_wins=4, b_wins=4, drawn=2,
                        a_points=0, b_points=0)
    assert result.a_win_rate == 0.5


# --------------------------------------------------------------------------
# The ladder
# --------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("level", range(2, MAX_LEVEL + 1))
@pytest.mark.slow
def test_every_rung_beats_the_one_below_it(level):
    """The ladder's whole claim. Two proposed rungs were deleted for failing
    this: one that kept guards, and one that judged cards probably-good rather
    than certainly-good. Both were plausible; neither survived measurement."""
    result = duel(L(level), L(level - 1), 250, random.Random(1674))
    assert result.a_win_rate > 0.5
    assert result.margin > 0


@pytest.mark.slow
def test_the_bottom_rung_still_crushes_random_play():
    result = duel(L(1), R, 200, random.Random(1674))
    assert result.a_win_rate > 0.8


# --------------------------------------------------------------------------
# Ratings
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_ratings_order_the_ladder_correctly():
    results = round_robin([R, L(1), L(2), L(4)], 120, random.Random(1674))
    table = ratings(results, anchor="random")
    assert table["random"] == 0
    assert table["L1"] < table["L2"] < table["L4"]


@pytest.mark.slow
def test_ratings_do_not_depend_on_the_order_games_were_played():
    """Bradley-Terry is fitted over the whole round robin. Sequential Elo
    updates would give a different answer depending on who met whom first."""
    results = round_robin([R, L(1), L(2)], 100, random.Random(1674))
    forward = ratings(results, anchor="random")
    backward = ratings(list(reversed(results)), anchor="random")
    for name in forward:
        assert forward[name] == pytest.approx(backward[name], abs=1e-6)


@pytest.mark.slow
def test_a_table_can_be_printed():
    results = round_robin([R, L(2)], 40, random.Random(1674))
    text = format_table(results, anchor="random")
    assert "random" in text and "L2" in text and "rating" in text


# --------------------------------------------------------------------------
# Styles must be EV-neutral
# --------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("dimension", sorted(CALIBRATED))
@pytest.mark.slow
def test_no_calibrated_style_costs_as_much_as_a_rung(dimension):
    """A style that reliably loses is not a style, it is a lower rung wearing a
    hat. The calibrated bands are chosen by measurement so that the extremes
    stay inside half a rung -- rung 3 to rung 4 is worth about +1.7 points.

    The first attempt failed this badly: guard retention at 1.0 cost 3.9 points
    per deal and sinking at 0.5 cost 4.1.
    """
    low, high = CALIBRATED[dimension]
    neutral = lambda rng: HeuristicAgent(4, style=BALANCED, rng=rng, name="neutral")
    for setting in (low, high):
        styled = (
            lambda rng, s=setting: HeuristicAgent(
                4, style=Style(**{dimension: s}), rng=rng, name="styled"
            )
        )
        result = duel(styled, neutral, 300, random.Random(1674))
        assert abs(result.margin) < 1.7, f"{dimension}={setting} is a skill change"
