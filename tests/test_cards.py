"""Tests for the card representation.

The piquet pack is 32 cards: A K Q J 10 9 8 7 in each suit, ace high.
For tie-breaking, aces count 11, court cards 10, and the rest at face value
(docs/PIQUET.md, "The pack and the deal").
"""

import pytest

from piquet.cards import Card, Hand, Rank, Suit, full_deck, parse_hand


# --------------------------------------------------------------------------
# Rank
# --------------------------------------------------------------------------


def test_the_pack_has_eight_ranks_from_seven_to_ace():
    assert len(Rank) == 8
    assert [r.name for r in Rank] == [
        "SEVEN", "EIGHT", "NINE", "TEN", "JACK", "QUEEN", "KING", "ACE",
    ]


def test_ranks_order_with_ace_high():
    assert Rank.ACE > Rank.KING > Rank.QUEEN > Rank.JACK > Rank.TEN
    assert Rank.TEN > Rank.NINE > Rank.EIGHT > Rank.SEVEN
    assert min(Rank) is Rank.SEVEN
    assert max(Rank) is Rank.ACE


@pytest.mark.parametrize(
    "rank, pips",
    [
        (Rank.SEVEN, 7), (Rank.EIGHT, 8), (Rank.NINE, 9), (Rank.TEN, 10),
        (Rank.JACK, 10), (Rank.QUEEN, 10), (Rank.KING, 10), (Rank.ACE, 11),
    ],
)
def test_pip_values_for_breaking_a_tie_in_point(rank, pips):
    assert rank.pip_value == pips


def test_court_cards_are_jack_queen_and_king_only():
    """Carte blanche is a hand with no court card. The ten is not a court card,
    despite counting for sets."""
    assert [r.name for r in Rank if r.is_court] == ["JACK", "QUEEN", "KING"]
    assert not Rank.TEN.is_court
    assert not Rank.ACE.is_court


def test_only_tens_and_above_count_for_sets():
    """Nines and below never count towards a trio or quatorze."""
    assert [r.name for r in Rank if r.counts_for_set] == [
        "TEN", "JACK", "QUEEN", "KING", "ACE",
    ]


def test_consecutive_ranks_are_consecutive_integers():
    """Sequence detection relies on this."""
    ranks = list(Rank)
    for lower, higher in zip(ranks, ranks[1:]):
        assert higher - lower == 1


# --------------------------------------------------------------------------
# Suit
# --------------------------------------------------------------------------


def test_there_are_four_suits_each_with_a_letter_and_a_symbol():
    assert len(Suit) == 4
    assert {s.letter for s in Suit} == {"C", "D", "H", "S"}
    assert {s.symbol for s in Suit} == {"♣", "♦", "♥", "♠"}


def test_suits_have_stable_distinct_indexes():
    """Piquet has no trumps and no suit hierarchy, so a suit's index carries no
    game meaning. It exists only to give each card a stable slot."""
    assert sorted(s.index for s in Suit) == [0, 1, 2, 3]


# --------------------------------------------------------------------------
# Card
# --------------------------------------------------------------------------


def test_a_card_knows_its_rank_and_suit():
    card = Card(Rank.ACE, Suit.SPADES)
    assert card.rank is Rank.ACE
    assert card.suit is Suit.SPADES


def test_cards_are_immutable_and_hashable():
    card = Card(Rank.ACE, Suit.SPADES)
    with pytest.raises(Exception):
        card.rank = Rank.KING  # type: ignore[misc]
    assert len({Card(Rank.ACE, Suit.SPADES), card}) == 1


def test_every_card_has_a_distinct_index_in_range():
    indexes = {card.index for card in full_deck()}
    assert indexes == set(range(32))


def test_a_card_round_trips_through_its_index():
    for card in full_deck():
        assert Card.from_index(card.index) == card


@pytest.mark.parametrize(
    "code, rank, suit",
    [
        ("AS", Rank.ACE, Suit.SPADES),
        ("KH", Rank.KING, Suit.HEARTS),
        ("TD", Rank.TEN, Suit.DIAMONDS),
        ("7C", Rank.SEVEN, Suit.CLUBS),
    ],
)
def test_a_card_round_trips_through_its_two_letter_code(code, rank, suit):
    assert Card.parse(code) == Card(rank, suit)
    assert Card(rank, suit).code == code


def test_parsing_a_card_is_forgiving_of_case_and_of_writing_ten_in_full():
    assert Card.parse("10s") == Card.parse("TS") == Card(Rank.TEN, Suit.SPADES)
    assert Card.parse("as") == Card(Rank.ACE, Suit.SPADES)


@pytest.mark.parametrize("bad", ["", "A", "AX", "1S", "ZS", "ASD", "6S"])
def test_parsing_rejects_nonsense_and_cards_outside_the_piquet_pack(bad):
    with pytest.raises(ValueError):
        Card.parse(bad)


def test_a_card_displays_with_a_suit_symbol_for_the_terminal():
    assert str(Card(Rank.ACE, Suit.SPADES)) == "A♠"
    assert str(Card(Rank.TEN, Suit.HEARTS)) == "10♥"


# --------------------------------------------------------------------------
# The deck
# --------------------------------------------------------------------------


def test_the_deck_is_thirty_two_distinct_cards():
    deck = full_deck()
    assert len(deck) == 32
    assert len(set(deck)) == 32


def test_the_deck_omits_everything_below_a_seven():
    """Cotton's 1674 game used 36 cards; ours drops the sixes too."""
    assert all(card.rank >= Rank.SEVEN for card in full_deck())
    assert {card.rank for card in full_deck()} == set(Rank)


def test_the_deck_holds_twelve_court_cards():
    """This is why two players can never both hold a carte blanche: that would
    need 24 cards with no court among them, and only 20 exist."""
    assert sum(1 for card in full_deck() if card.rank.is_court) == 12
    assert sum(1 for card in full_deck() if not card.rank.is_court) == 20


# --------------------------------------------------------------------------
# Hand
# --------------------------------------------------------------------------


def test_a_hand_can_be_built_from_cards_and_reports_its_size():
    hand = Hand.of(Card.parse("AS"), Card.parse("KS"))
    assert len(hand) == 2
    assert Card.parse("AS") in hand
    assert Card.parse("QS") not in hand


def test_an_empty_hand_is_falsey_and_a_populated_one_is_truthy():
    assert not Hand.empty()
    assert Hand.of(Card.parse("AS"))


def test_a_hand_is_parsed_from_a_readable_string_for_use_in_fixtures():
    hand = parse_hand("AS KS QS 7H")
    assert len(hand) == 4
    assert Card.parse("7H") in hand


def test_parsing_a_hand_rejects_a_repeated_card():
    with pytest.raises(ValueError):
        parse_hand("AS AS")


def test_hands_are_immutable_adding_and_removing_return_new_hands():
    hand = parse_hand("AS KS")
    bigger = hand.add(Card.parse("QS"))
    smaller = hand.remove(Card.parse("AS"))
    assert len(hand) == 2, "the original hand must be unchanged"
    assert len(bigger) == 3
    assert len(smaller) == 1


def test_removing_a_card_that_is_absent_is_an_error():
    with pytest.raises(KeyError):
        parse_hand("AS").remove(Card.parse("KS"))


def test_adding_a_card_already_held_is_an_error():
    with pytest.raises(KeyError):
        parse_hand("AS").add(Card.parse("AS"))


def test_hands_compare_and_hash_by_content_not_by_order():
    assert parse_hand("AS KS") == parse_hand("KS AS")
    assert len({parse_hand("AS KS"), parse_hand("KS AS")}) == 1


def test_a_hand_lists_the_ranks_it_holds_in_a_suit_highest_first():
    hand = parse_hand("7S TS AS KH")
    assert hand.ranks_in(Suit.SPADES) == [Rank.ACE, Rank.TEN, Rank.SEVEN]
    assert hand.ranks_in(Suit.CLUBS) == []


def test_a_hand_counts_how_many_it_holds_of_a_rank():
    hand = parse_hand("AS AH AD KC")
    assert hand.count_of(Rank.ACE) == 3
    assert hand.count_of(Rank.KING) == 1
    assert hand.count_of(Rank.QUEEN) == 0


def test_a_hand_iterates_in_a_stable_order_by_suit_then_rank():
    hand = parse_hand("7S AS KH 9C")
    assert [card.code for card in hand] == ["9C", "KH", "7S", "AS"]


def test_a_hand_serialises_to_a_string_that_parses_back():
    hand = parse_hand("AS KS QH 7C")
    assert parse_hand(hand.code) == hand


def test_hand_set_operations_support_the_exchange():
    """Discarding and taking in are set operations on a hand."""
    hand = parse_hand("AS KS QS JS")
    discard = parse_hand("QS JS")
    assert hand - discard == parse_hand("AS KS")
    assert (hand - discard) | parse_hand("7C 8C") == parse_hand("AS KS 7C 8C")
    assert hand & parse_hand("KS QS 9D") == parse_hand("KS QS")


def test_combining_overlapping_hands_is_an_error():
    """A card cannot be in two places at once; silently merging would hide
    a dealing bug."""
    with pytest.raises(KeyError):
        parse_hand("AS KS") | parse_hand("KS QS")


def test_a_full_deck_dealt_into_a_hand_holds_every_card():
    hand = Hand.of(*full_deck())
    assert len(hand) == 32
    assert hand.ranks_in(Suit.SPADES) == sorted(Rank, reverse=True)
