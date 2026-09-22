"""Tests for detecting, scoring and comparing the three declaration categories.

Rules and their sources are set out in docs/PIQUET.md ("Declarations") and
docs/DESIGN.md section 3.4. The scoring authority is Cavendish's Laws of Piquet
(1892), laws 60-64.
"""

import pytest

from piquet.cards import Rank, Suit, full_deck, parse_hand
from piquet.combos import (
    Comparison,
    best_point,
    best_sequence,
    best_set,
    compare_point,
    compare_sequence,
    compare_set,
    is_carte_blanche,
    score_sequences,
    score_sets,
    sequences,
    sets,
)


# --------------------------------------------------------------------------
# Point
# --------------------------------------------------------------------------


def test_point_is_the_longest_suit_and_scores_its_length():
    point = best_point(parse_hand("AS KS QS JS 7H 8H 9C"))
    assert point.suit is Suit.SPADES
    assert point.length == 4
    assert point.score == 4


def test_point_prefers_length_over_pip_value():
    """Five low cards beat four high ones: point is counted by length."""
    point = best_point(parse_hand("7S 8S 9S TS JS AH KH QH JH"))
    assert point.suit is Suit.SPADES
    assert point.length == 5


def test_point_breaks_a_tie_between_a_players_own_suits_by_pip_value():
    """A hand declares its best point, so equal lengths resolve by value."""
    point = best_point(parse_hand("AS KS QS JS 7H 8H 9H TH"))
    assert point.suit is Suit.SPADES
    assert point.pip_value == 11 + 10 + 10 + 10


def test_point_pip_value_counts_aces_eleven_and_courts_ten():
    point = best_point(parse_hand("AS KS QS JS TS"))
    assert point.pip_value == 11 + 10 + 10 + 10 + 10


def test_an_empty_hand_has_no_point():
    assert best_point(parse_hand("")) is None


@pytest.mark.parametrize(
    "mine, theirs, expected",
    [
        ("AS KS QS JS", "AH KH QH", Comparison.BETTER),
        ("AS KS QS", "AH KH QH JH", Comparison.WORSE),
        ("AS KS QS JS", "AH KH QH JH", Comparison.EQUAL),
        ("AS KS QS JS", "TH 9H 8H 7H", Comparison.BETTER),
        ("TS 9S 8S 7S", "AH KH QH JH", Comparison.WORSE),
    ],
)
def test_comparing_point_uses_length_then_pip_value(mine, theirs, expected):
    assert compare_point(best_point(parse_hand(mine)),
                         best_point(parse_hand(theirs))) is expected


def test_an_exactly_equal_point_scores_for_neither_player():
    """Cavendish: equality in a category means nobody scores it -- though it
    still does not block a pique."""
    same = compare_point(best_point(parse_hand("AS KS QS JS")),
                         best_point(parse_hand("AH KH QH JH")))
    assert same is Comparison.EQUAL


def test_holding_a_point_beats_holding_none():
    assert compare_point(best_point(parse_hand("AS KS")), None) is Comparison.BETTER
    assert compare_point(None, best_point(parse_hand("AS"))) is Comparison.WORSE
    assert compare_point(None, None) is Comparison.EQUAL


# --------------------------------------------------------------------------
# Sequences
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cards, length, score",
    [
        ("QS KS AS", 3, 3),                          # tierce
        ("JS QS KS AS", 4, 4),                       # quart
        ("TS JS QS KS AS", 5, 15),                   # quint
        ("9S TS JS QS KS AS", 6, 16),                # sixieme
        ("8S 9S TS JS QS KS AS", 7, 17),             # septieme
        ("7S 8S 9S TS JS QS KS AS", 8, 18),          # huitieme
    ],
)
def test_sequence_scores_follow_the_historical_table(cards, length, score):
    """3 and 4 score their length; from five cards a bonus of ten applies, so
    the scores run 3, 4, 15, 16, 17, 18."""
    sequence = best_sequence(parse_hand(cards))
    assert sequence.length == length
    assert sequence.score == score


def test_a_run_of_two_is_not_a_sequence():
    assert best_sequence(parse_hand("KS AS")) is None
    assert sequences(parse_hand("KS AS 9H TH")) == ()


def test_a_sequence_must_be_in_one_suit():
    assert best_sequence(parse_hand("QS KH AD")) is None


def test_a_sequence_is_named_by_its_highest_card():
    assert best_sequence(parse_hand("QS KS AS")).top is Rank.ACE
    assert best_sequence(parse_hand("9S TS JS")).top is Rank.JACK


def test_sequences_are_maximal_runs_not_every_sub_run():
    """A quart is one sequence, not two overlapping tierces."""
    found = sequences(parse_hand("JS QS KS AS"))
    assert len(found) == 1
    assert found[0].length == 4


def test_a_gap_in_a_suit_splits_it_into_two_sequences():
    """Seven cards missing the ten give a quart above and a tierce below."""
    found = sequences(parse_hand("7S 8S 9S JS QS KS AS"))
    assert [(s.length, s.score) for s in found] == [(4, 4), (3, 3)]


def test_sequences_are_returned_best_first():
    found = sequences(parse_hand("QS KS AS TH JH QH KH"))
    assert [s.length for s in found] == [4, 3]


@pytest.mark.parametrize(
    "mine, theirs, expected",
    [
        ("JS QS KS AS", "QH KH AH", Comparison.BETTER),      # longer wins
        ("QS KS AS", "JH QH KH AH", Comparison.WORSE),
        ("QS KS AS", "JH QH KH", Comparison.BETTER),         # higher top card
        ("9S TS JS", "QH KH AH", Comparison.WORSE),
        ("QS KS AS", "QH KH AH", Comparison.EQUAL),          # exactly equal
    ],
)
def test_comparing_sequences_uses_length_then_top_card(mine, theirs, expected):
    assert compare_sequence(best_sequence(parse_hand(mine)),
                            best_sequence(parse_hand(theirs))) is expected


def test_holding_a_sequence_beats_holding_none():
    assert compare_sequence(best_sequence(parse_hand("QS KS AS")), None) is (
        Comparison.BETTER
    )
    assert compare_sequence(None, None) is Comparison.EQUAL


def test_the_winner_of_the_category_scores_every_sequence_he_holds():
    """Cotton, 1674: he that hath the biggest sequence "reckons all his less
    Sequences", and the loser scores nothing at all."""
    hand = parse_hand("TS JS QS KS AS 9H TH JH 7C 8C 9C")
    assert score_sequences(hand) == 15 + 3 + 3


def test_scoring_sequences_of_a_hand_that_has_none_is_zero():
    assert score_sequences(parse_hand("AS KH QD JC")) == 0


# --------------------------------------------------------------------------
# Sets
# --------------------------------------------------------------------------


def test_a_trio_scores_three_and_a_quatorze_fourteen():
    assert best_set(parse_hand("AS AH AD")).score == 3
    assert best_set(parse_hand("AS AH AD AC")).score == 14


def test_sets_below_a_ten_do_not_count():
    """Nines, eights and sevens never form a set."""
    assert best_set(parse_hand("9S 9H 9D 9C")) is None
    assert best_set(parse_hand("8S 8H 8D")) is None
    assert best_set(parse_hand("TS TH TD")) is not None


def test_a_pair_is_not_a_set():
    assert best_set(parse_hand("AS AH")) is None


def test_any_quatorze_beats_any_trio():
    """Even the lowest quatorze beats a trio of aces."""
    quatorze_of_tens = best_set(parse_hand("TS TH TD TC"))
    trio_of_aces = best_set(parse_hand("AS AH AD"))
    assert compare_set(quatorze_of_tens, trio_of_aces) is Comparison.BETTER


def test_sets_of_equal_size_are_compared_by_rank():
    assert compare_set(best_set(parse_hand("AS AH AD")),
                       best_set(parse_hand("KS KH KD"))) is Comparison.BETTER
    assert compare_set(best_set(parse_hand("TS TH TD")),
                       best_set(parse_hand("JS JH JD"))) is Comparison.WORSE


def test_holding_a_set_beats_holding_none():
    assert compare_set(best_set(parse_hand("AS AH AD")), None) is Comparison.BETTER
    assert compare_set(None, None) is Comparison.EQUAL


def test_two_players_can_never_tie_on_sets():
    """A fact about the pack, not a rule: two sets of one rank would need six
    cards of that rank, and only four exist. So unlike point and sequence, the
    set category never needs exact-tie handling."""
    for rank in Rank:
        copies = sum(1 for card in full_deck() if card.rank is rank)
        assert copies == 4
        assert copies < 6, "two players could otherwise both hold a trio"


def test_the_winner_of_the_category_scores_every_set_he_holds():
    hand = parse_hand("AS AH AD AC KS KH KD 7C 8C 9C TD JD")
    assert score_sets(hand) == 14 + 3


def test_sets_are_returned_best_first():
    found = sets(parse_hand("KS KH KD AS AH AD AC TS TH TD"))
    assert [(s.rank, s.count) for s in found] == [
        (Rank.ACE, 4), (Rank.KING, 3), (Rank.TEN, 3),
    ]


# --------------------------------------------------------------------------
# Carte blanche
# --------------------------------------------------------------------------


def test_a_hand_with_no_court_card_is_a_carte_blanche():
    assert is_carte_blanche(parse_hand("7S 8S 9S TS AS 7H 8H 9H TH AH 7D 8D"))


def test_a_single_court_card_denies_carte_blanche():
    assert not is_carte_blanche(parse_hand("7S 8S 9S TS AS 7H 8H 9H TH AH 7D JD"))


def test_tens_and_aces_do_not_deny_carte_blanche():
    """Only jacks, queens and kings are court cards."""
    assert is_carte_blanche(parse_hand("TS TH TD TC AS AH AD AC 7S 8S 9S 7H"))
