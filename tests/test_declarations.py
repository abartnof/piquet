"""Tests for the declaration dialogue.

Three categories are contested in order -- point, sequence, set -- and each is a
small dialogue. Elder announces; younger answers "good", "not good" or "equal";
only then does the next category begin, so elder may adapt what he says next to
what he has just learned.

Elder scores as he goes. Younger scores nothing until after elder has led to the
first trick, which is why only elder can ever score a pique.

A player may decline to declare, or declare less than he holds. Cavendish calls
this sinking, and his examples are all partial: "he calls five cards, and
declares five spades, when he might have six."
"""

import pytest

from piquet.cards import Rank, Suit, parse_hand
from piquet.combos import CardSet, Comparison, Point, Sequence
from piquet.rules import Declaration, Phase
from piquet.scoring import Category, Player

from tests.helpers import declaring

E, Y = Player.ELDER, Player.YOUNGER

# Elder holds eight spades; younger seven diamonds. Elder wins point.
LOPSIDED = dict(
    elder="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
    younger="AD KD QD JD TD 9D 8D AC KC QC JC TC",
)

# Both hold a four-card point worth 41. An exact tie.
TIED_POINT = dict(
    elder="AS KS QS JS 7H 8H 9H 7C 8C 9C 7D 8D",
    younger="AD KD QD JD TH JH QH TC JC QC TS 9S",
)

# Younger holds five spades; elder has nothing longer than three.
YOUNGER_WINS = dict(
    elder="7S 8S 9S 7H 8H 9H 7C 8C 9C 7D 8D JD",
    younger="AS KS QS JS TS AH KH QH JH AD KD QD",
)


# --------------------------------------------------------------------------
# Declaration objects
# --------------------------------------------------------------------------


def test_a_full_declaration_announces_everything_the_hand_holds():
    hand = parse_hand("TS JS QS KS AS 9H TH JH 7C 8C 9C 7D")
    declaration = Declaration.full(hand, Category.SEQUENCES)
    assert declaration.score == 15 + 3 + 3
    assert declaration.best.length == 5


def test_a_sink_announces_nothing_and_scores_nothing():
    sunk = Declaration.sink()
    assert sunk.best is None
    assert sunk.score == 0
    assert not sunk


def test_a_declaration_must_be_supported_by_the_hand():
    hand = parse_hand("TS JS QS KS AS 9H TH JH 7C 8C 9C 7D")
    lie = Declaration.of(Sequence(Suit.HEARTS, Rank.ACE, 5))
    with pytest.raises(ValueError, match="not held"):
        lie.validate(hand, Category.SEQUENCES)


def test_a_declaration_must_match_the_category_being_contested():
    hand = parse_hand("AS AH AD AC KS KH KD 7C 8C 9C TD JD")
    wrong = Declaration.of(CardSet(Rank.ACE, 4))
    with pytest.raises(ValueError, match="category"):
        wrong.validate(hand, Category.SEQUENCES)


def test_a_player_may_understate_a_sequence_as_cavendish_describes():
    """Holding a quart to the knave, calling only a tierce to the knave."""
    hand = parse_hand("8S 9S TS JS")
    partial = Declaration.of(Sequence(Suit.SPADES, Rank.JACK, 3))
    partial.validate(hand, Category.SEQUENCES)
    assert partial.score == 3


def test_a_player_may_understate_a_point():
    """Declaring five spades while holding six."""
    hand = parse_hand("7S 8S 9S TS JS QS")
    partial = Declaration.of(Point(Suit.SPADES, 5, 10 + 10 + 10 + 9 + 8))
    partial.validate(hand, Category.POINT)
    assert partial.score == 5


def test_a_player_may_understate_a_quatorze_as_a_trio():
    hand = parse_hand("AS AH AD AC")
    partial = Declaration.of(CardSet(Rank.ACE, 3))
    partial.validate(hand, Category.SETS)
    assert partial.score == 3


def test_a_player_cannot_overstate_what_he_holds():
    hand = parse_hand("AS AH AD")
    with pytest.raises(ValueError, match="not held"):
        Declaration.of(CardSet(Rank.ACE, 4)).validate(hand, Category.SETS)


def test_two_sequences_may_share_a_suit_when_a_gap_splits_it():
    """Seven spades missing the ten are a quart and a tierce, both genuinely
    held and both declarable."""
    hand = parse_hand("7S 8S 9S JS QS KS AS")
    both = Declaration.full(hand, Category.SEQUENCES)
    both.validate(hand, Category.SEQUENCES)
    assert both.score == 4 + 3


def test_two_sequences_cannot_be_claimed_that_share_cards():
    """A tierce to the queen and a tierce to the knave overlap on two cards."""
    hand = parse_hand("7S 8S 9S TS JS QS")
    overlapping = Declaration.of(
        Sequence(Suit.SPADES, Rank.QUEEN, 3), Sequence(Suit.SPADES, Rank.JACK, 3)
    )
    with pytest.raises(ValueError, match="shares cards"):
        overlapping.validate(hand, Category.SEQUENCES)


# --------------------------------------------------------------------------
# The dialogue
# --------------------------------------------------------------------------


def test_elder_declares_first_and_younger_answers():
    deal = declaring(**LOPSIDED)
    assert deal.phase is Phase.DECLARE_POINT
    assert deal.to_declare is E

    mid = deal.declare(E, Declaration.full(deal.hand_of(E), Category.POINT))
    assert mid.to_declare is Y
    assert mid.phase is Phase.DECLARE_POINT


def test_younger_cannot_declare_before_elder():
    with pytest.raises(ValueError, match="out of turn"):
        declaring(**LOPSIDED).declare(Y, Declaration.sink())


def test_the_categories_are_contested_in_order():
    deal = declaring(**LOPSIDED)
    for expected in (Phase.DECLARE_POINT, Phase.DECLARE_SEQUENCES, Phase.DECLARE_SETS):
        assert deal.phase is expected
        deal = deal.declare(E, Declaration.sink())
        deal = deal.declare(Y, Declaration.sink())
    assert deal.phase is Phase.PLAY


def test_elder_hears_the_answer_before_the_next_category_begins():
    """The reason the dialogue is modelled category by category rather than as
    one batch: elder may adapt what he declares next."""
    deal = declaring(**LOPSIDED)
    deal = deal.declare(E, Declaration.full(deal.hand_of(E), Category.POINT))
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))
    assert deal.phase is Phase.DECLARE_SEQUENCES
    assert deal.results[-1].response == "good"


# --------------------------------------------------------------------------
# Who scores
# --------------------------------------------------------------------------


def test_the_better_holding_wins_the_category_and_scores():
    deal = declaring(**LOPSIDED)
    deal = deal.declare(E, Declaration.full(deal.hand_of(E), Category.POINT))
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))

    assert deal.results[-1].winner is E
    assert deal.results[-1].response == "good"
    assert deal.log.by_category(E) == {Category.POINT: 8}


def test_the_loser_of_a_category_scores_nothing_at_all():
    """Even a hand full of sequences scores none of them if it loses."""
    deal = declaring(
        elder="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
        younger="AD KD QD JD AC KC QC JC 7H 8H 9H TH",
    )
    deal = deal.declare(E, Declaration.sink())
    deal = deal.declare(Y, Declaration.sink())
    deal = deal.declare(E, Declaration.full(deal.hand_of(E), Category.SEQUENCES))
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.SEQUENCES))

    assert deal.results[-1].winner is E
    assert deal.log.by_category(E) == {Category.SEQUENCES: 18 + 4}
    assert deal.log.total(Y) == 0


def test_an_exact_tie_scores_for_neither_player():
    deal = declaring(**TIED_POINT)
    deal = deal.declare(E, Declaration.full(deal.hand_of(E), Category.POINT))
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))

    assert deal.results[-1].winner is None
    assert deal.results[-1].response == "equal"
    assert len(deal.log) == 0


def test_sinking_concedes_the_category():
    deal = declaring(**LOPSIDED)
    deal = deal.declare(E, Declaration.sink())
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))
    assert deal.results[-1].winner is Y
    assert deal.results[-1].response == "not good"


def test_if_both_sink_nobody_scores():
    deal = declaring(**LOPSIDED)
    deal = deal.declare(E, Declaration.sink())
    deal = deal.declare(Y, Declaration.sink())
    assert deal.results[-1].winner is None
    assert len(deal.log) == 0


def test_sinking_costs_the_points_but_buys_silence():
    """Elder holds the better point but declares nothing, so younger takes the
    category with a weaker holding. That is the trade the whole game turns on."""
    deal = declaring(**LOPSIDED)
    full = Declaration.full(deal.hand_of(E), Category.POINT)
    assert full.score == 8

    sunk = deal.declare(E, Declaration.sink())
    sunk = sunk.declare(Y, Declaration.full(sunk.hand_of(Y), Category.POINT))
    assert sunk.log.total(E) == 0
    assert sunk.results[-1].winner is Y


# --------------------------------------------------------------------------
# The timing that makes pique possible
# --------------------------------------------------------------------------


def test_youngers_declarations_are_not_scored_until_elder_has_led():
    """The whole reason only elder can score a pique: younger's points are held
    back until after elder leads to the first trick."""
    deal = declaring(**YOUNGER_WINS)
    deal = deal.declare(E, Declaration.sink())
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))

    assert deal.results[-1].winner is Y
    assert deal.log.total(Y) == 0, "younger has not scored yet"
    assert deal.pending_for_younger == 5


def test_elder_scores_his_declarations_immediately():
    deal = declaring(**LOPSIDED)
    deal = deal.declare(E, Declaration.full(deal.hand_of(E), Category.POINT))
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))
    assert deal.log.total(E) == 8
    assert deal.pending_for_younger == 0


def test_the_dialogue_is_recorded_for_the_tutor():
    deal = declaring(**LOPSIDED)
    deal = deal.declare(E, Declaration.full(deal.hand_of(E), Category.POINT))
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))
    result = deal.results[-1]
    assert result.category is Category.POINT
    assert result.comparison is Comparison.BETTER
    assert "point of 8" in str(result.elder.best)
    assert "point of 7" in str(result.younger.best)
