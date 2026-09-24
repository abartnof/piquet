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


# --------------------------------------------------------------------------
# What a partie position is worth, and what a point is worth in it
# --------------------------------------------------------------------------


def test_the_settlement_is_the_arithmetic_of_the_rubicon_rule():
    from piquet.chances import settlement_of

    assert settlement_of(105, 101) == 105 - 101 + 100 == 104
    assert settlement_of(97, 89) == 97 + 89 + 100 == 286
    assert settlement_of(89, 97) == -286, "signed from my side"
    assert settlement_of(60, 40) == 200, "the loser is short even though I am too"
    assert settlement_of(120, 120) == 0


def test_a_finished_partie_is_worth_exactly_what_it_pays():
    from piquet.chances import expected_settlement, settlement_of

    assert expected_settlement(105, 101, 0, True) == float(settlement_of(105, 101))


def test_being_ahead_is_worth_more_than_being_behind():
    from piquet.chances import expected_settlement

    ahead = expected_settlement(140, 80, 2, True)
    behind = expected_settlement(80, 140, 2, True)
    assert ahead > 0 > behind
    assert abs(ahead + behind) < abs(ahead), "and roughly a mirror of each other"


def test_a_point_is_worth_about_a_point_when_nothing_is_near_the_line():
    """Far ahead, both sides long over a hundred, one deal to go: the winner
    is settled and the loser is safe, so the settlement is the plain
    difference and the deal objective and the partie objective agree."""
    from piquet.chances import point_weights

    mine, theirs = point_weights(260, 150, 1, True)
    assert 0.8 < mine < 1.4
    assert -1.4 < theirs < -0.8


def test_a_point_is_worth_more_than_a_point_near_a_tie():
    """The settlement is the difference *plus a hundred*, and that hundred
    changes hands at the tie. So one point close to level can be worth two
    hundred, and in expectation a point near level is worth several."""
    from piquet.chances import point_weights

    level, _ = point_weights(180, 180, 1, True)
    settled, _ = point_weights(260, 150, 1, True)
    assert level > 2.5 * settled


def test_the_opponents_points_are_worth_having_when_they_cannot_reach_the_line():
    """A rubiconed loser pays the *sum*, and their score is part of it. So
    while they are far enough back that a hundred is out of reach, every point
    they score is a point they hand you.

    There is no counterpart to this anywhere inside a single deal, which is
    why no amount of tuning a deal-level heuristic could ever have found it.
    """
    from piquet.chances import point_weights

    _, theirs = point_weights(220, 30, 1, True)
    assert theirs > 0.5, "their points add to what they will pay me"


def test_keeping_them_short_is_worth_many_points_when_they_are_close():
    """And it inverts, sharply. A point that carries them over the line turns
    what they pay from the sum into the difference, which costs twice their
    whole score. Just short of it, a point to them is worth several to me."""
    from piquet.chances import point_weights

    _, close = point_weights(220, 88, 1, True)
    _, over = point_weights(220, 130, 1, True)
    assert close < -4.0, "keeping them under is worth a multiple"
    assert -1.4 < over < -0.8, "once they are over it is an ordinary point again"


def test_a_point_is_worth_far_more_when_it_carries_you_over_the_line():
    """Being rubiconed roughly triples what losing costs, so a point that
    helps you across is worth a multiple of one that does not. This is the
    whole reason an agent has to see the standing."""
    from piquet.chances import point_weights

    desperate, _ = point_weights(80, 150, 1, True)
    comfortable, _ = point_weights(190, 150, 1, True)
    assert desperate > 2 * comfortable


def test_the_weights_vanish_once_there_is_nothing_left_to_play():
    from piquet.chances import point_weights

    assert point_weights(120, 110, 0, True) == (0.0, 0.0)
