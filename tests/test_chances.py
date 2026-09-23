"""Tests for the chances of scoring so much in a deal.

The one probabilistic question in piquet with nothing hidden inside it: a
distribution over the deck and over our own play, and no opponent policy. So
unlike every other uncertainty in the game it can be measured, and unlike a
measurement it can be *checked* -- against a fresh simulation that knows
nothing about the table.
"""

import random

import pytest

from piquet.chances import (
    CAP,
    MEASURED,
    chance_of,
    chance_of_the_rubicon,
    density,
    in_words,
    survival,
)
from piquet.partie import RUBICON, Partie, Side
from piquet.scoring import Player

E, Y = Player.ELDER, Player.YOUNGER
A, B = Side.A, Side.B


# --------------------------------------------------------------------------
# The table itself
# --------------------------------------------------------------------------


@pytest.mark.parametrize("seat", [E, Y])
def test_each_seat_has_a_proper_distribution(seat):
    rows = density(seat)
    assert len(rows) == CAP + 1
    assert all(p >= 0 for p in rows)
    assert abs(sum(rows) - 1.0) < 1e-9


@pytest.mark.parametrize("seat", [E, Y])
def test_survival_is_the_tail_of_the_density(seat):
    rows, tail = density(seat), survival(seat)
    assert abs(tail[0] - 1.0) < 1e-9
    assert all(tail[i] >= tail[i + 1] for i in range(len(tail) - 1))
    assert abs(tail[30] - sum(rows[30:])) < 1e-9


def test_elder_outscores_younger_at_every_threshold_worth_asking_about():
    """Elder takes the bigger exchange, scores his declarations as he goes and
    is paid for leading to the first trick. It shows up all the way along."""
    elder, younger = survival(E), survival(Y)
    assert all(elder[t] > younger[t] for t in range(5, 60))


# --------------------------------------------------------------------------
# Reaching a total
# --------------------------------------------------------------------------


def test_needing_nothing_is_certain_and_having_no_deals_left_is_hopeless():
    assert chance_of(0, 1, True) == 1.0
    assert chance_of(-5, 0, True) == 1.0
    assert chance_of(1, 0, True) == 0.0


def test_the_more_you_need_the_less_likely_you_are_to_get_it():
    chances = [chance_of(n, 1, True) for n in range(0, 80, 5)]
    assert all(a >= b for a, b in zip(chances, chances[1:]))
    assert chances[0] == 1.0 and chances[-1] < 0.1


def test_another_deal_can_only_help():
    for needed in (20, 45, 70):
        one = chance_of(needed, 1, True)
        two = chance_of(needed, 2, True)
        assert two > one


def test_the_seat_you_sit_in_next_changes_the_answer():
    """Needing eighteen with one deal to play is two chances in three from
    elder's chair and about one in two from younger's. Which is exactly why
    the winner of the cut chooses to deal, and so to be elder in the sixth."""
    assert chance_of(18, 1, True) > chance_of(18, 1, False) + 0.15


def test_six_deals_come_out_the_same_whichever_chair_you_start_in():
    """Three of each either way, and convolution does not care about order."""
    assert chance_of(RUBICON, 6, True) == pytest.approx(
        chance_of(RUBICON, 6, False), abs=1e-12
    )


# --------------------------------------------------------------------------
# The rubicon
# --------------------------------------------------------------------------


def test_the_rubicon_is_read_from_where_the_partie_stands():
    partie = Partie(opening_dealer=A)
    for _ in range(5):
        partie = partie.record_scores(20, 10)
    assert partie.deals_left == 1
    for side in (A, B):
        expected = chance_of(
            RUBICON - partie.score_of(side), 1, partie.elder is side
        )
        assert chance_of_the_rubicon(partie, side) == expected


def test_a_side_already_over_a_hundred_is_home():
    """B takes sixty a deal from whichever chair; A scrapes five. The seats
    alternate, so the scores have to be entered the other way round every
    other deal -- which is the mistake this module exists to make impossible."""
    partie = Partie(opening_dealer=A)
    for number in range(1, 6):
        partie = partie.record_scores(*((60, 5) if number % 2 else (5, 60)))
    assert partie.score_of(B) == 300 and partie.score_of(A) == 25

    assert chance_of_the_rubicon(partie, B) == 1.0
    stranded = chance_of_the_rubicon(partie, A)
    assert 0.0 < stranded < 0.2, "seventy-five in one deal is a long shot"


@pytest.mark.slow
def test_the_table_predicts_how_often_a_side_is_actually_rubiconed():
    """The check that matters. Play parties end to end and compare the rate
    against what convolving the single-deal histograms says it should be --
    two calculations that share nothing but the engine underneath them."""
    from piquet.heuristics import HeuristicAgent
    from piquet.match import play_partie

    rng = random.Random(1674)
    short = played = 0
    for _ in range(80):
        partie, _ = play_partie(
            HeuristicAgent(4, rng=rng, name="a"),
            HeuristicAgent(4, rng=rng, name="b"),
            rng=rng,
        )
        for total in partie.totals:
            played += 1
            short += total < RUBICON

    observed = short / played
    predicted = 1 - chance_of(RUBICON, 6, True)
    assert abs(observed - predicted) < 0.06, (
        f"observed {observed:.3f} against a predicted {predicted:.3f}"
    )


# --------------------------------------------------------------------------
# Saying it out loud
# --------------------------------------------------------------------------


def test_a_chance_is_phrased_as_something_a_player_can_act_on():
    """Odds, not percentages. Hoyle says "three to two against", never "forty
    per cent", and a player deciding whether to gamble thinks the same way."""
    assert in_words(0.99) == "all but certain"
    assert in_words(0.001) == "barely possible"
    assert in_words(0.34) == "about 1 in 3"
    assert in_words(0.66) == "about 2 in 3"
    assert in_words(0.5) == "about 1 in 2"
