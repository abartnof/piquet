"""Tests for the scoring event log, and for pique and repique.

Piquet's two bonuses read the *same* points in *two different orders*, which is
why scoring is an ordered log rather than a running total:

- **Repique** (Cavendish, Law 68) reckons in strict *category* order --
  carte blanche, point, sequences, sets -- and ignores play entirely.
- **Pique** (Law 69) reckons in *actual occurrence* order, over declarations
  and play together.

Law 67 fixes the categories: I carte blanche, II point, III sequences,
IV quatorzes and trios, V points made in play, VI the cards.
"""

import pytest

from piquet.scoring import (
    PIQUE_BONUS,
    PIQUE_THRESHOLD,
    REPIQUE_BONUS,
    Category,
    Player,
    ScoreLog,
)


def log_of(*entries) -> ScoreLog:
    """Build a log from (player, amount, category) triples, in temporal order."""
    log = ScoreLog()
    for player, amount, category in entries:
        log = log.record(player, amount, category)
    return log


E, Y = Player.ELDER, Player.YOUNGER


# --------------------------------------------------------------------------
# The log itself
# --------------------------------------------------------------------------


def test_an_empty_log_scores_nothing_for_either_player():
    log = ScoreLog()
    assert log.total(E) == 0
    assert log.total(Y) == 0
    assert len(log) == 0


def test_recording_a_score_accumulates_it():
    log = log_of((E, 5, Category.POINT), (E, 15, Category.SEQUENCES))
    assert log.total(E) == 20
    assert log.total(Y) == 0


def test_the_log_is_immutable_so_recording_returns_a_new_log():
    original = log_of((E, 5, Category.POINT))
    extended = original.record(Y, 14, Category.SETS)
    assert original.total(Y) == 0
    assert extended.total(Y) == 14


def test_the_log_preserves_the_order_events_actually_happened_in():
    log = log_of(
        (E, 5, Category.POINT),
        (E, 1, Category.PLAY),
        (Y, 14, Category.SETS),
    )
    assert [event.category for event in log] == [
        Category.POINT, Category.PLAY, Category.SETS,
    ]


def test_a_score_of_zero_is_not_recorded_at_all():
    """An equality scores for neither player, so nothing is logged. Recording a
    zero would wrongly look like the adversary had reckoned something."""
    with pytest.raises(ValueError):
        ScoreLog().record(E, 0, Category.POINT)
    with pytest.raises(ValueError):
        ScoreLog().record(E, -1, Category.POINT)


def test_categories_reckon_in_cavendish_law_67_order():
    assert [c.name for c in sorted(Category)][:6] == [
        "CARTE_BLANCHE", "POINT", "SEQUENCES", "SETS", "PLAY", "CARDS",
    ]


def test_players_know_their_opponent():
    assert E.opponent is Y
    assert Y.opponent is E


# --------------------------------------------------------------------------
# Repique -- category order
# --------------------------------------------------------------------------


def test_elder_repiques_on_thirty_in_declarations_alone():
    """Parlett's arithmetic: 7 for point, 15 + 4 + 3 for sequences, 3 for a
    trio, making 32, plus 60 for the repique."""
    log = log_of(
        (E, 7, Category.POINT),
        (E, 22, Category.SEQUENCES),
        (E, 3, Category.SETS),
    )
    assert log.repique is E
    assert log.with_bonuses().total(E) == 32 + REPIQUE_BONUS == 92


def test_a_carte_blanche_denies_the_opponents_repique():
    """Parlett again: had younger declared a blank, the repique would be
    prevented -- carte blanche reckons first of all."""
    log = log_of(
        (Y, 10, Category.CARTE_BLANCHE),
        (E, 7, Category.POINT),
        (E, 22, Category.SEQUENCES),
        (E, 3, Category.SETS),
    )
    assert log.repique is None


def test_no_repique_when_the_opponent_scores_in_an_earlier_category():
    log = log_of(
        (Y, 5, Category.POINT),
        (E, 22, Category.SEQUENCES),
        (E, 14, Category.SETS),
    )
    assert log.repique is None


def test_a_repique_still_stands_if_the_opponent_scores_in_a_later_category():
    """Elder reaches thirty at sequences; younger's sets reckon after."""
    log = log_of(
        (E, 8, Category.POINT),
        (E, 22, Category.SEQUENCES),
        (Y, 14, Category.SETS),
    )
    assert log.repique is E


def test_younger_can_repique_even_though_elder_led_first():
    """The decisive test of category order. Elder scores 1 for leading before
    younger declares at all -- but that is category V, which reckons after the
    declaration categories, so it does not block younger's repique."""
    log = log_of(
        (E, 1, Category.PLAY),        # elder leads to the first trick
        (Y, 6, Category.POINT),       # younger then declares
        (Y, 16, Category.SEQUENCES),
        (Y, 14, Category.SETS),
    )
    assert log.repique is Y
    assert log.with_bonuses().total(Y) == 36 + REPIQUE_BONUS


def test_play_points_never_contribute_to_a_repique():
    """Repique is made "in his hand alone"."""
    log = log_of(
        (E, 20, Category.SEQUENCES),
        (E, 13, Category.PLAY),
    )
    assert log.repique is None


def test_falling_short_of_thirty_earns_nothing():
    log = log_of((E, 29, Category.SEQUENCES))
    assert log.repique is None
    assert log.with_bonuses().total(E) == 29


def test_exactly_thirty_is_enough():
    log = log_of((E, 30, Category.SEQUENCES))
    assert log.repique is E


# --------------------------------------------------------------------------
# Pique -- temporal order
# --------------------------------------------------------------------------


def test_elder_piques_on_thirty_in_hand_and_play():
    log = log_of(
        (E, 5, Category.POINT),
        (E, 15, Category.SEQUENCES),
        *[(E, 1, Category.PLAY)] * 10,
    )
    assert log.pique is E
    assert log.with_bonuses().total(E) == 30 + PIQUE_BONUS


def test_a_pique_is_stopped_the_moment_the_opponent_reckons_anything():
    log = log_of(
        (E, 5, Category.POINT),
        (E, 15, Category.SEQUENCES),
        (E, 1, Category.PLAY),
        (Y, 14, Category.SETS),        # younger declares after elder leads
        *[(E, 1, Category.PLAY)] * 10,
    )
    assert log.pique is None


def test_younger_can_never_pique():
    """Elder always scores one for leading to the first trick before younger
    can reckon anything, so the window never opens for her."""
    log = log_of(
        (E, 1, Category.PLAY),
        (Y, 8, Category.POINT),
        (Y, 22, Category.SEQUENCES),
        (Y, 14, Category.SETS),
    )
    assert log.pique is None


def test_the_ten_for_cards_does_not_count_towards_a_pique():
    """Cavendish, Law 69: "A capot reckons after points made in play; and,
    therefore, does not count toward a pique." Law 66 makes capot and the ten
    for cards the same score, so neither can contribute.

    Here elder takes every trick and younger reckons nothing all deal, yet
    elder still has no pique: without the capot he is on 18.
    """
    log = log_of(
        (E, 5, Category.POINT),
        *[(E, 1, Category.PLAY)] * 12,   # twelve leads
        (E, 1, Category.PLAY),           # and the last trick
        (E, 40, Category.CARDS),         # capot
    )
    assert log.pique is None
    assert log.with_bonuses().total(E) == 58


def test_a_player_scores_a_pique_or_a_repique_but_never_both():
    log = log_of(
        (E, 8, Category.POINT),
        (E, 22, Category.SEQUENCES),
        *[(E, 1, Category.PLAY)] * 12,
    )
    assert log.repique is E
    assert log.pique is None, "the repique supersedes it"
    assert log.with_bonuses().total(E) == 42 + REPIQUE_BONUS


def test_only_one_bonus_event_is_ever_added():
    log = log_of((E, 8, Category.POINT), (E, 22, Category.SEQUENCES))
    bonuses = [e for e in log.with_bonuses() if e.category is Category.BONUS]
    assert len(bonuses) == 1
    assert bonuses[0].amount == REPIQUE_BONUS


def test_adding_bonuses_twice_does_not_double_them():
    log = log_of((E, 8, Category.POINT), (E, 22, Category.SEQUENCES))
    once = log.with_bonuses()
    assert once.with_bonuses().total(E) == once.total(E)


def test_the_thresholds_are_thirty_and_the_bonuses_sixty_and_thirty():
    assert PIQUE_THRESHOLD == 30
    assert REPIQUE_BONUS == 60
    assert PIQUE_BONUS == 30


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def test_the_log_reports_a_breakdown_by_category_for_the_tutor():
    log = log_of(
        (E, 5, Category.POINT),
        (E, 15, Category.SEQUENCES),
        (Y, 14, Category.SETS),
    )
    assert log.by_category(E) == {Category.POINT: 5, Category.SEQUENCES: 15}
    assert log.by_category(Y) == {Category.SETS: 14}


def test_events_carry_a_human_readable_detail_for_explanation():
    log = ScoreLog().record(E, 15, Category.SEQUENCES, "quint to the ace")
    assert log.events[0].detail == "quint to the ace"
    assert "quint to the ace" in str(log.events[0])
