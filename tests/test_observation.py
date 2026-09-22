"""Tests for what each player is allowed to know.

The two asymmetries that matter: elder may look at all five of his talon cards
even when he takes fewer, and each player may consult his own discards. Between
them they are what make the play phase nearly perfect information.

The counts asserted here are the ones docs/DESIGN.md section 4.2 rests on. If
they change, the whole play-phase AI plan needs rethinking, so they are worth
pinning down.
"""

from math import comb

import pytest

from piquet.cards import Hand, full_deck
from piquet.observation import view_for
from piquet.rules import Phase, deal_from
from piquet.scoring import Player

from tests.helpers import declaring, skip_declarations

E, Y = Player.ELDER, Player.YOUNGER


def plain_deal():
    return deal_from(list(full_deck()))


def exchanged(elder_takes: int, younger_takes: int):
    deal = plain_deal()
    deal = deal.exchange(E, Hand.of(*list(deal.hand_of(E))[:elder_takes]))
    return deal.exchange(Y, Hand.of(*list(deal.hand_of(Y))[:younger_takes]))


# --------------------------------------------------------------------------
# What a view contains
# --------------------------------------------------------------------------


def test_a_view_shows_a_player_his_own_hand():
    deal = plain_deal()
    assert view_for(deal, E).hand == deal.hand_of(E)
    assert view_for(deal, Y).hand == deal.hand_of(Y)


def test_a_view_has_no_way_to_reach_the_opponents_hand():
    """Not a runtime check but a structural one: the dataclass simply has no
    field for it, so a cheating agent cannot be written by accident."""
    fields = view_for(plain_deal(), E).__slots__
    assert "hands" not in fields
    assert not any("opponent" in name for name in fields)


def test_a_player_may_consult_his_own_discards():
    """Cavendish: "Each player keeps his discards by him, and may refer to them
    during play." Remembering them is not cheating."""
    deal = exchanged(5, 3)
    assert len(view_for(deal, E).my_discards) == 5
    assert len(view_for(deal, Y).my_discards) == 3


def test_scores_and_the_dialogue_are_public():
    deal = skip_declarations(declaring(
        elder="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
        younger="AD KD QD JD TD 9D 8D AC KC QC JC TC",
    ))
    for player in (E, Y):
        view = view_for(deal, player)
        assert len(view.results) == 3
        assert view.log is deal.log


# --------------------------------------------------------------------------
# The talon asymmetry
# --------------------------------------------------------------------------


def test_elder_sees_nothing_of_the_talon_before_he_exchanges():
    assert view_for(plain_deal(), E).talon_seen == ()


def test_elder_sees_all_five_of_his_talon_cards_even_taking_fewer():
    """"If he exchanges fewer than five, he can look at the remainder of the
    five." This single rule is why elder faces so few possible hands."""
    deal = exchanged(3, 3)
    assert view_for(deal, E).talon_seen == deal.talon[:5]


def test_younger_sees_only_the_cards_she_actually_drew():
    deal = exchanged(5, 3)
    seen = view_for(deal, Y).talon_seen
    assert seen == deal.talon[5:8]
    assert all(card in deal.hand_of(Y) for card in seen)


def test_younger_draws_from_where_elder_stopped_and_sees_only_that():
    deal = exchanged(2, 4)
    assert view_for(deal, Y).talon_seen == deal.talon[2:6]


def test_younger_never_sees_elders_talon_cards():
    deal = exchanged(5, 3)
    elder_only = set(deal.talon[:5])
    assert not (set(view_for(deal, Y).talon_seen) & elder_only)


# --------------------------------------------------------------------------
# The counts the whole AI plan rests on
# --------------------------------------------------------------------------


@pytest.mark.parametrize("elder_takes", [1, 2, 3, 4, 5])
def test_elder_can_never_account_for_more_than_seventeen_cards(elder_takes):
    """Twelve in hand, his discards, and any of his five he did not take: the
    total is seventeen however many he exchanges, leaving fifteen unknown."""
    deal = exchanged(elder_takes, 3)
    assert len(view_for(deal, E).unseen) == 15


def test_elder_faces_at_most_455_possible_opponent_hands():
    """Fifteen cards unknown, twelve of them in younger's hand. This is the
    number docs/DESIGN.md section 4.2 is built on."""
    deal = exchanged(5, 3)
    unknown = len(view_for(deal, E).unseen)
    assert comb(unknown, 12) == 455


@pytest.mark.parametrize("younger_takes", [1, 2, 3])
def test_younger_is_less_well_informed_than_elder(younger_takes):
    deal = exchanged(5, younger_takes)
    assert len(view_for(deal, Y).unseen) == 20 - younger_takes


def test_younger_faces_at_most_6188_possible_opponent_hands():
    deal = exchanged(5, 3)
    unknown = len(view_for(deal, Y).unseen)
    assert unknown == 17
    assert comb(unknown, 12) == 6188


def test_every_card_played_becomes_known_to_both_players():
    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    before = len(view_for(deal, E).unseen)
    deal = deal.play(E, next(iter(deal.hand_of(E))))
    deal = deal.play(Y, next(iter(deal.legal_plays())))
    after = len(view_for(deal, E).unseen)
    assert after == before - 1, "younger's card is now known; elder's already was"


def test_uncertainty_shrinks_to_nothing_by_the_end_of_the_play():
    from tests.helpers import play_cards

    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    deal = play_cards(
        deal,
        "AS", "9S", "KS", "TS", "QS", "JS",
        "AH", "9H", "KH", "TH", "QH", "JH",
        "7D", "AD", "KD", "8D", "QD", "9D",
        "AC", "7C", "KC", "8C", "QC", "9C",
    )
    # Elder has seen all 24 cards played and his own five talon cards, so his
    # residual uncertainty is exactly three: the bottom of the talon, which in
    # a real deal is younger's discards. Those are the only cards in the pack
    # elder never sees, whatever happens.
    assert len(view_for(deal, E).unseen) == 3


# --------------------------------------------------------------------------
# Turn taking
# --------------------------------------------------------------------------


def test_a_view_says_whether_it_is_this_players_turn():
    deal = plain_deal()
    assert view_for(deal, E).to_act
    assert not view_for(deal, Y).to_act


def test_legal_plays_are_offered_only_to_the_player_on_turn():
    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    assert view_for(deal, E).legal_plays == deal.hand_of(E)
    assert view_for(deal, Y).legal_plays == Hand.empty()
