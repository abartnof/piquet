"""Tests for the play of the tricks.

Twelve tricks, no trumps, follow suit if you can. Cavendish, Law 65: "each
player scores one for every card he leads, or with which he wins a trick. The
winner of the last trick scores two instead of one." Law 66: more than six
tricks scores ten for the cards, all twelve scores forty for capot, and six each
scores nothing.
"""

import pytest

from piquet.cards import Card, parse_hand
from piquet.rules import Declaration, Phase
from piquet.scoring import Category, Player

from tests.helpers import declaring, play_cards, skip_declarations

E, Y = Player.ELDER, Player.YOUNGER

# Elder takes the first six tricks, younger the last six. Six each, no cards.
SIX_ALL = dict(
    elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
    younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
)
SIX_ALL_PLAY = (
    "AS", "9S", "KS", "TS", "QS", "JS",
    "AH", "9H", "KH", "TH", "QH", "JH",
    "7D", "AD", "KD", "8D", "QD", "9D",
    "AC", "7C", "KC", "8C", "QC", "9C",
)

# Elder is void in everything younger holds, and holds the top hearts.
CAPOT = dict(
    elder="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
    younger="TH 9H 8H 7H AD KD QD JD AC KC QC JC",
)


def at_play(**hands):
    return skip_declarations(declaring(**hands))


# --------------------------------------------------------------------------
# Leading and following
# --------------------------------------------------------------------------


def test_elder_leads_to_the_first_trick():
    deal = at_play(**SIX_ALL)
    assert deal.phase is Phase.PLAY
    assert deal.to_play is E


def test_leading_scores_one():
    deal = play_cards(at_play(**SIX_ALL), "AS")
    assert deal.log.by_category(E) == {Category.PLAY: 1}


def test_the_second_player_must_follow_suit():
    deal = play_cards(at_play(**SIX_ALL), "AS")
    assert deal.to_play is Y
    with pytest.raises(ValueError, match="follow suit"):
        deal.play(Y, Card.parse("JH"))


def test_a_player_void_in_the_suit_led_may_play_anything():
    deal = play_cards(at_play(**CAPOT), "AS")
    after = deal.play(Y, Card.parse("JC"))
    assert len(after.tricks) == 1


def test_legal_plays_are_the_suit_led_when_you_can_follow():
    deal = play_cards(at_play(**SIX_ALL), "AS")
    assert deal.legal_plays() == parse_hand("JS TS 9S")


def test_legal_plays_are_the_whole_hand_when_void():
    deal = play_cards(at_play(**CAPOT), "AS")
    assert deal.legal_plays() == deal.hand_of(Y)


def test_the_leader_may_lead_anything():
    deal = at_play(**SIX_ALL)
    assert deal.legal_plays() == deal.hand_of(E)


def test_a_player_cannot_play_a_card_he_does_not_hold():
    deal = at_play(**SIX_ALL)
    with pytest.raises(ValueError, match="does not hold"):
        deal.play(E, Card.parse("JS"))


def test_a_player_cannot_play_out_of_turn():
    deal = at_play(**SIX_ALL)
    with pytest.raises(ValueError, match="out of turn"):
        deal.play(Y, Card.parse("JS"))


# --------------------------------------------------------------------------
# Winning tricks
# --------------------------------------------------------------------------


def test_the_higher_card_of_the_suit_led_takes_the_trick():
    deal = play_cards(at_play(**SIX_ALL), "AS", "9S")
    assert deal.tricks[-1].winner is E
    assert deal.to_play is E, "the winner leads to the next trick"


def test_a_card_of_another_suit_never_wins_however_high():
    deal = play_cards(at_play(**CAPOT), "7S", "AD")
    assert deal.tricks[-1].winner is E


def test_winning_the_opponents_lead_scores_one():
    deal = play_cards(at_play(**SIX_ALL), "7D", "AD")
    assert deal.log.by_category(E) == {Category.PLAY: 1}   # for leading
    assert deal.log.by_category(Y) == {Category.PLAY: 1}   # for winning it


def test_leading_and_winning_your_own_trick_scores_only_one():
    """The trick is worth one point, not two, when the leader takes it."""
    deal = play_cards(at_play(**SIX_ALL), "AS", "9S")
    assert deal.log.total(E) == 1
    assert deal.log.total(Y) == 0


# --------------------------------------------------------------------------
# The end of the play
# --------------------------------------------------------------------------


def test_the_winner_of_the_last_trick_scores_an_extra_point():
    deal = play_cards(at_play(**SIX_ALL), *SIX_ALL_PLAY)
    last = [e for e in deal.log if "last trick" in e.detail]
    assert len(last) == 1
    assert last[0].player is Y
    assert last[0].amount == 1


def test_six_tricks_each_scores_nothing_for_the_cards():
    deal = play_cards(at_play(**SIX_ALL), *SIX_ALL_PLAY)
    assert deal.tricks_won(E) == 6
    assert deal.tricks_won(Y) == 6
    assert Category.CARDS not in deal.log.by_category(E)
    assert Category.CARDS not in deal.log.by_category(Y)


def test_the_play_scores_add_up_as_cavendish_describes():
    """Elder leads tricks one to seven, scoring seven. Younger wins the
    seventh as second player, leads the last five, and takes the last trick."""
    deal = play_cards(at_play(**SIX_ALL), *SIX_ALL_PLAY)
    assert deal.log.by_category(E) == {Category.PLAY: 7}
    assert deal.log.by_category(Y) == {Category.PLAY: 1 + 5 + 1}


def test_the_play_ends_the_deal():
    deal = play_cards(at_play(**SIX_ALL), *SIX_ALL_PLAY)
    assert deal.phase is Phase.COMPLETE
    assert len(deal.tricks) == 12


def test_no_card_may_be_played_once_the_deal_is_complete():
    deal = play_cards(at_play(**SIX_ALL), *SIX_ALL_PLAY)
    with pytest.raises(ValueError):
        deal.play(E, Card.parse("AS"))


# --------------------------------------------------------------------------
# Cards and capot
# --------------------------------------------------------------------------


def test_taking_every_trick_scores_forty_for_capot():
    deal = at_play(**CAPOT)
    while deal.phase is Phase.PLAY:
        deal = deal.play(deal.to_play, _lowest(deal))
    assert deal.tricks_won(E) == 12
    assert deal.log.by_category(E)[Category.CARDS] == 40


def test_the_capot_does_not_help_towards_a_pique():
    """Cavendish, Law 69. Elder takes every trick and younger reckons nothing
    all deal, yet elder has no pique: without the capot he is on 13."""
    deal = at_play(**CAPOT)
    while deal.phase is Phase.PLAY:
        deal = deal.play(deal.to_play, _lowest(deal))
    assert deal.log.total(Y) == 0
    assert deal.log.pique is None
    assert deal.log.total(E) == 13 + 40


def _lowest(deal) -> Card:
    return min(deal.legal_plays(), key=lambda c: (c.rank, c.suit))


# --------------------------------------------------------------------------
# The timing that makes pique possible
# --------------------------------------------------------------------------


def test_youngers_declarations_are_scored_once_elder_has_led():
    deal = declaring(
        elder="7S 8S 9S 7H 8H 9H 7C 8C 9C 7D 8D JD",
        younger="AS KS QS JS TS AH KH QH JH AD KD QD",
    )
    deal = deal.declare(E, Declaration.sink())
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))
    deal = skip_declarations(deal)
    assert deal.log.total(Y) == 0, "still withheld at the start of play"

    deal = deal.play(E, Card.parse("7S"))
    assert deal.log.by_category(Y) == {Category.POINT: 5}
    assert deal.pending_for_younger == 0


def test_elders_lead_is_logged_before_youngers_declarations():
    """The order matters: it is what stops younger ever scoring a pique."""
    deal = declaring(
        elder="7S 8S 9S 7H 8H 9H 7C 8C 9C 7D 8D JD",
        younger="AS KS QS JS TS AH KH QH JH AD KD QD",
    )
    deal = deal.declare(E, Declaration.sink())
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))
    deal = skip_declarations(deal)
    deal = deal.play(E, Card.parse("7S"))

    assert [(e.player, e.category) for e in deal.log] == [
        (E, Category.PLAY),
        (Y, Category.POINT),
    ]
