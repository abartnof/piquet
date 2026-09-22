"""Tests for dealing, carte blanche, and the exchange.

Twelve cards each and eight to the talon, split five for elder and three for
younger. Elder discards one to five and draws the same number; younger then
discards at least one and at most what elder left. Cards are taken in order
from the top of the stock (Cavendish, Law 23).
"""

import pytest

from piquet.cards import Card, Hand, full_deck
from piquet.rules import Deal, Phase, deal_from, deal_shuffled
from piquet.scoring import Category, Player

E, Y = Player.ELDER, Player.YOUNGER


def ordered_deal(*, elder: str, younger: str, talon: str) -> Deal:
    """Build a deal from explicit card lists, for fixtures."""
    cards = [Card.parse(t) for t in f"{elder} {younger} {talon}".split()]
    return deal_from(cards)


def a_plain_deal() -> Deal:
    """A deal with no carte blanche and nothing remarkable about it."""
    return deal_from(list(full_deck()))


# --------------------------------------------------------------------------
# Dealing
# --------------------------------------------------------------------------


def test_a_deal_gives_twelve_cards_each_and_eight_to_the_talon():
    deal = a_plain_deal()
    assert len(deal.hand_of(E)) == 12
    assert len(deal.hand_of(Y)) == 12
    assert len(deal.talon) == 8


def test_every_card_is_dealt_exactly_once():
    deal = a_plain_deal()
    seen = list(deal.hand_of(E)) + list(deal.hand_of(Y)) + list(deal.talon)
    assert len(seen) == 32
    assert len(set(seen)) == 32


def test_dealing_from_an_explicit_order_is_reproducible():
    """The first twelve cards go to elder, the next twelve to younger, and the
    last eight to the talon. Deterministic, so fixtures can be written."""
    deal = deal_from(list(full_deck()))
    assert list(deal.hand_of(E)) == sorted(full_deck()[:12], key=lambda c: c.index)
    assert deal.talon == tuple(full_deck()[24:])


def test_a_shuffled_deal_is_reproducible_from_a_seed():
    import random

    first = deal_shuffled(random.Random(1674))
    again = deal_shuffled(random.Random(1674))
    assert first.hand_of(E) == again.hand_of(E)
    assert first.talon == again.talon


def test_dealing_rejects_anything_but_a_full_distinct_pack():
    with pytest.raises(ValueError):
        deal_from(list(full_deck())[:31])
    with pytest.raises(ValueError):
        deal_from([Card.parse("AS")] * 32)


def test_a_fresh_deal_waits_for_elder_to_exchange():
    assert a_plain_deal().phase is Phase.ELDER_EXCHANGE


# --------------------------------------------------------------------------
# Carte blanche
# --------------------------------------------------------------------------


def test_carte_blanche_scores_ten_at_once_and_reckons_first():
    """Announced as soon as it is noticed, so it is logged before anything
    else -- which is right for both derivations, since it is also the first
    category in Cavendish's reckoning order."""
    deal = ordered_deal(
        elder="7S 8S 9S TS AS 7H 8H 9H TH AH 7D 8D",
        younger="JS QS KS JH QH KH JD QD KD JC QC KC",
        talon="9D TD AD 7C 8C 9C TC AC",
    )
    assert deal.log.total(E) == 10
    assert deal.log.by_category(E) == {Category.CARTE_BLANCHE: 10}
    assert deal.log.total(Y) == 0


def test_an_ordinary_hand_scores_no_carte_blanche():
    assert a_plain_deal().log.total(E) == 0


def test_younger_can_hold_carte_blanche_too():
    deal = ordered_deal(
        younger="7S 8S 9S TS AS 7H 8H 9H TH AH 7D 8D",
        elder="JS QS KS JH QH KH JD QD KD JC QC KC",
        talon="9D TD AD 7C 8C 9C TC AC",
    )
    assert deal.log.total(Y) == 10


def test_two_carte_blanches_at_once_are_impossible_in_the_thirty_two_card_game():
    """That would need 24 cards with no court among them, and only 20 exist.
    Nothing to test in the engine; this asserts the fact the engine relies on."""
    non_court = [c for c in full_deck() if not c.rank.is_court]
    assert len(non_court) == 20 < 24


# --------------------------------------------------------------------------
# Elder's exchange
# --------------------------------------------------------------------------


def test_elder_exchanges_and_keeps_twelve_cards():
    deal = a_plain_deal()
    discard = Hand.of(*list(deal.hand_of(E))[:3])
    after = deal.exchange(E, discard)
    assert len(after.hand_of(E)) == 12
    assert len(after.discard_of(E)) == 3


def test_elder_takes_the_cards_from_the_top_of_the_talon_in_order():
    """Cavendish, Law 23: the cards must be taken in order from the top."""
    deal = a_plain_deal()
    discard = Hand.of(*list(deal.hand_of(E))[:3])
    after = deal.exchange(E, discard)
    for card in deal.talon[:3]:
        assert card in after.hand_of(E)
    assert deal.talon[3] not in after.hand_of(E)


def test_elder_may_exchange_between_one_and_five_cards():
    deal = a_plain_deal()
    for count in (1, 2, 3, 4, 5):
        discard = Hand.of(*list(deal.hand_of(E))[:count])
        assert len(deal.exchange(E, discard).hand_of(E)) == 12


def test_elder_must_discard_at_least_one_card():
    """Cotton, 1674: "the Gamesters are both obliged to discard one Card at
    least." Cavendish's Law 21 says the same."""
    deal = a_plain_deal()
    with pytest.raises(ValueError, match="at least one"):
        deal.exchange(E, Hand.empty())


def test_elder_may_not_exchange_more_than_five():
    deal = a_plain_deal()
    discard = Hand.of(*list(deal.hand_of(E))[:6])
    with pytest.raises(ValueError, match="five"):
        deal.exchange(E, discard)


def test_a_player_cannot_discard_a_card_he_does_not_hold():
    deal = a_plain_deal()
    stranger = next(c for c in deal.hand_of(Y))
    with pytest.raises(ValueError, match="does not hold"):
        deal.exchange(E, Hand.of(stranger))


def test_after_elder_exchanges_it_is_youngers_turn():
    deal = a_plain_deal()
    after = deal.exchange(E, Hand.of(*list(deal.hand_of(E))[:5]))
    assert after.phase is Phase.YOUNGER_EXCHANGE


def test_younger_cannot_exchange_before_elder():
    deal = a_plain_deal()
    with pytest.raises(ValueError, match="not younger's turn|out of turn"):
        deal.exchange(Y, Hand.of(*list(deal.hand_of(Y))[:3]))


# --------------------------------------------------------------------------
# Younger's exchange
# --------------------------------------------------------------------------


def _after_elder_takes(deal: Deal, count: int) -> Deal:
    return deal.exchange(E, Hand.of(*list(deal.hand_of(E))[:count]))


def test_younger_takes_the_usual_three_when_elder_takes_five():
    deal = _after_elder_takes(a_plain_deal(), 5)
    after = deal.exchange(Y, Hand.of(*list(deal.hand_of(Y))[:3]))
    assert len(after.hand_of(Y)) == 12
    assert after.talon_remaining == 0


def test_younger_may_take_what_elder_left():
    """Elder took three, so five remain and younger may have all of them."""
    deal = _after_elder_takes(a_plain_deal(), 3)
    after = deal.exchange(Y, Hand.of(*list(deal.hand_of(Y))[:5]))
    assert len(after.hand_of(Y)) == 12
    assert after.talon_remaining == 0


def test_younger_may_not_take_more_than_remains():
    deal = _after_elder_takes(a_plain_deal(), 5)
    discard = Hand.of(*list(deal.hand_of(Y))[:4])
    with pytest.raises(ValueError, match="only 3 remain|remain"):
        deal.exchange(Y, discard)


def test_younger_must_also_discard_at_least_one():
    """Cavendish Law 22 for Piquet. His Laws of Piquet au Cent say the opposite,
    which is where the modern confusion comes from -- but that is another game.
    """
    deal = _after_elder_takes(a_plain_deal(), 5)
    with pytest.raises(ValueError, match="at least one"):
        deal.exchange(Y, Hand.empty())


def test_younger_draws_from_where_elder_stopped():
    deal = a_plain_deal()
    after_elder = _after_elder_takes(deal, 3)
    after = after_elder.exchange(Y, Hand.of(*list(after_elder.hand_of(Y))[:2]))
    assert deal.talon[3] in after.hand_of(Y)
    assert deal.talon[4] in after.hand_of(Y)
    assert deal.talon[5] not in after.hand_of(Y)


def test_the_exchange_ends_with_the_declaration_of_point():
    deal = _after_elder_takes(a_plain_deal(), 5)
    after = deal.exchange(Y, Hand.of(*list(deal.hand_of(Y))[:3]))
    assert after.phase is Phase.DECLARE_POINT


def test_neither_player_can_exchange_twice():
    """Cotton: "No man is permitted to discard twice in one dealing."""
    deal = _after_elder_takes(a_plain_deal(), 5)
    after = deal.exchange(Y, Hand.of(*list(deal.hand_of(Y))[:3]))
    with pytest.raises(ValueError):
        after.exchange(Y, Hand.of(*list(after.hand_of(Y))[:1]))


def test_the_discards_are_kept_and_can_be_consulted():
    """Cavendish: "Each player keeps his discards by him, and may refer to them
    during play." A bot consulting its own discards is not cheating."""
    deal = a_plain_deal()
    thrown = Hand.of(*list(deal.hand_of(E))[:3])
    after = deal.exchange(E, thrown)
    assert after.discard_of(E) == thrown
    assert after.discard_of(Y) == Hand.empty()


def test_cards_are_conserved_across_the_whole_exchange():
    deal = a_plain_deal()
    after = _after_elder_takes(deal, 4)
    after = after.exchange(Y, Hand.of(*list(after.hand_of(Y))[:2]))
    seen = (
        list(after.hand_of(E)) + list(after.hand_of(Y))
        + list(after.discard_of(E)) + list(after.discard_of(Y))
        + list(after.talon_untaken)
    )
    assert len(seen) == 32
    assert len(set(seen)) == 32
