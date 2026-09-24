"""Claims made by the historical authorities, checked against the engine.

These are the most satisfying tests in the project: a 280-year-old assertion
about the game, reproduced exactly by code written from the rules.
"""

import random

from piquet.cards import Card, Hand, full_deck, parse_hand
from piquet.combos import best_point, score_sequences, score_sets
from piquet.rules import Declaration, Phase, deal_from
from piquet.scoring import Category, Player

E, Y = Player.ELDER, Player.YOUNGER


def _cards(text: str) -> list[Card]:
    """An *ordered* list. A Hand would lose the order, which matters for the
    talon, since cards are taken from the top of the stock in order."""
    return [Card.parse(token) for token in text.split()]


def declaration_score(hand: Hand) -> int:
    point = best_point(hand)
    return (point.score if point else 0) + score_sequences(hand) + score_sets(hand)


# --------------------------------------------------------------------------
# Hoyle, 1744: the highest number to be made of a repique and capot
# --------------------------------------------------------------------------


def test_the_best_declaring_hand_scores_fifty_seven():
    """Three quatorzes, which are also four tierces.

    The instructive part is that this is *not* the hand a human first reaches
    for. Maximising point and sequence length -- a point of eight, a huitieme,
    a quatorze -- reaches only 40. Sets are worth far more per card (a quatorze
    is 14 for four cards; a huitieme is 18 for eight), and the same twelve
    cards count in all three categories at once. Ace-king-queen in every suit
    is a point of 3, four tierces for 12, and three quatorzes for 42.
    """
    hand = parse_hand("AS KS QS AH KH QH AD KD QD AC KC QC")
    assert best_point(hand).score == 3
    assert score_sequences(hand) == 4 * 3
    assert score_sets(hand) == 3 * 14
    assert declaration_score(hand) == 57


def test_no_hand_found_declares_better_than_fifty_seven():
    """Hill-climbing never exceeds 57, from any starting hand.

    This is corroboration, not proof: a hill-climb gives a lower bound on the
    maximum, never an upper one. The upper bound is an argument. Three
    quatorzes use all twelve cards and score 42, leaving each suit exactly
    three cards; consecutive ranks make those four tierces for 12, plus a point
    of 3. Spending cards on anything else buys less than it costs -- two
    quatorzes plus a sixieme reaches only 50, and maximising length instead
    (a point of eight, a huitieme, a quatorze) reaches 40.

    A separate run of 5,000 restarts (205 seconds, too slow for the suite)
    reached 57 and never exceeded it. See docs/DESIGN.md section 3.11.
    """
    deck = list(full_deck())
    rng = random.Random(1744)
    best = 0
    for _ in range(40):
        hand = Hand.of(*rng.sample(deck, 12))
        improved = True
        while improved:
            improved = False
            outside = [c for c in deck if c not in hand]
            for drop in list(hand):
                for take in outside:
                    candidate = hand.remove(drop).add(take)
                    if declaration_score(candidate) > declaration_score(hand):
                        hand, improved = candidate, True
                        break
                if improved:
                    break
        best = max(best, declaration_score(hand))
    assert best <= 57


def test_hoyles_maximum_deal_of_a_hundred_and_seventy():
    """Hoyle, 1744, asked "What is the highest Number to be made of a Repique
    and Capot?", answers "A hundred and seventy points."

    He is exactly right, and it is reachable in a legal deal -- compulsory
    exchange included. Elder is dealt eleven of the twelve cards he wants plus
    one junk club, with the twelfth on top of the talon, so the exchange he is
    obliged to make fetches it. Younger swaps within a suit to stay 3-3-3-3 and
    so scores nothing at all.

        declarations  57
        repique       60
        twelve leads  12
        last trick     1
        capot         40
                     ---
                     170
    """
    deal = deal_from(
        _cards("AS AH AD AC KS KH KD KC QS QH QD 7C")
        + _cards("JS TS 9S JH TH 9H JD TD 9D JC TC 9C")
        + _cards("QC 8S 7S 8H 7H 8D 7D 8C")
    )
    deal = deal.exchange(E, parse_hand("7C"))
    deal = deal.exchange(Y, parse_hand("9S"))
    assert deal.hand_of(E) == parse_hand("AS KS QS AH KH QH AD KD QD AC KC QC")

    while deal.to_declare is not None:
        player = deal.to_declare
        deal = deal.declare(
            player, Declaration.full(deal.hand_of(player), deal.declaring_category)
        )
    assert all(result.winner is E for result in deal.results)

    for code in ("AS", "KS", "QS", "AH", "KH", "QH",
                 "AD", "KD", "QD", "AC", "KC", "QC"):
        deal = deal.play(E, Card.parse(code))
        deal = deal.play(Y, min(deal.legal_plays(), key=lambda c: c.rank))

    assert deal.phase is Phase.COMPLETE
    assert deal.tricks_won(E) == 12
    assert deal.log.repique is E
    assert deal.log.by_category(E) == {
        Category.POINT: 3,
        Category.SEQUENCES: 12,
        Category.SETS: 42,
        Category.PLAY: 13,
        Category.CARDS: 40,
        Category.BONUS: 60,
    }
    assert deal.log.total(E) == 170
    assert deal.log.total(Y) == 0


def test_the_capot_is_not_what_carries_elder_past_thirty():
    """Guards the Law 69 exclusion inside the maximum deal: elder is already
    past thirty on declarations alone, so the repique stands on its own."""
    hand = parse_hand("AS KS QS AH KH QH AD KD QD AC KC QC")
    assert declaration_score(hand) >= 30


# --------------------------------------------------------------------------
# Hoyle, 1744: the odds on younger's draw
# --------------------------------------------------------------------------


def test_hoyles_three_to_two_against_younger_saving_a_pique():
    """"Three to two against the younger-hand's taking one Card out of three
    to save a Pique."

    Hoyle's *Short Treatise* is applied probability written before the tools
    had names: he is computing a hypergeometric tail by hand, a century and a
    half before anyone called it that.

    Four readings are arithmetically possible and only one lands on his answer.
    Younger draws **three** cards from the **twenty she cannot see** -- elder's
    twelve and the eight of the talon are interchangeable to her -- and needs
    **any one of three** named cards:

        1 - C(17,3)/C(20,3) = 680/1140 subtracted from one = 0.4035

    which is 1.478 to 1 against, and "three to two" is how you say that at a
    table. The competing readings give 0.22, 5.67 and 0.66 to 1, so the
    sentence pins down the calculation as well as the answer.
    """
    from fractions import Fraction
    from math import comb

    p = 1 - Fraction(comb(20 - 3, 3), comb(20, 3))
    assert p == Fraction(23, 57)
    odds_against = (1 - p) / p
    assert 1.45 < float(odds_against) < 1.50, "Hoyle rounds 1.478 to three to two"

    for drawn, wanted, population in ((3, 3, 8), (3, 1, 20), (5, 3, 20)):
        other = 1 - Fraction(comb(population - wanted, drawn), comb(population, drawn))
        assert abs(float((1 - other) / other) - 1.5) > 0.5, (
            "no competing reading of the sentence comes near three to two"
        )


def test_the_engine_deals_hoyles_odds_when_you_actually_play_them():
    """The arithmetic is one thing; that our dealing agrees with it is another.

    Younger's three talon cards come off the top of a shuffled stock, so
    whether they behave like a fair draw from the twenty she cannot see is a
    property of `deal_from`, not of the formula.
    """
    import random

    from piquet.cards import Hand
    from piquet.observation import view_for
    from piquet.rules import deal_shuffled

    rng = random.Random(1744)
    trials = saves = 0
    for _ in range(4000):
        deal = deal_shuffled(rng)
        before = view_for(deal, Y)
        # Three cards she cannot see, named before she draws.
        wanted = Hand.of(*rng.sample(list(before.unseen), 3))
        deal = deal.exchange(E, Hand.of(*list(deal.hand_of(E))[:5]))
        deal = deal.exchange(Y, Hand.of(*list(deal.hand_of(Y))[:3]))
        drew = Hand.of(*view_for(deal, Y).talon_seen)
        trials += 1
        saves += bool(drew & wanted)

    observed = saves / trials
    assert abs(observed - 23 / 57) < 0.025, (
        f"observed {observed:.3f}, Hoyle's 0.4035"
    )


def test_parletts_worked_repique_is_arithmetic_and_not_a_deal():
    """Parlett totals a repique as 7 for point, then 15, 4 and 3 for
    sequences, then 3 for a trio: 32, plus 60, for 92.

    The arithmetic is right and no hand can do it. Sequences of 15, 4 and 3
    are a quint, a quart and a tierce, and they cannot share a suit -- a quint
    and a quart in one suit would need ten cards of it and only eight exist.
    So they occupy three distinct suits and consume all twelve cards at
    5-4-3, which makes the longest suit five. The point is 5, never 7.

    Built by construction rather than by sampling: every quint, quart and
    tierce in every arrangement of three suits is 2,880 hands, and the point
    is five in all of them.
    """
    from itertools import permutations

    from piquet.cards import Card, Hand, Rank, Suit

    def run(suit, top, length):
        return [Card(Rank(r), suit) for r in range(top - length + 1, top + 1)]

    checked = 0
    for quint_suit, quart_suit, tierce_suit in permutations(Suit, 3):
        for quint_top in range(Rank.SEVEN + 4, Rank.ACE + 1):
            for quart_top in range(Rank.SEVEN + 3, Rank.ACE + 1):
                for tierce_top in range(Rank.SEVEN + 2, Rank.ACE + 1):
                    hand = Hand.of(
                        *run(quint_suit, quint_top, 5),
                        *run(quart_suit, quart_top, 4),
                        *run(tierce_suit, tierce_top, 3),
                    )
                    assert len(hand) == 12
                    assert score_sequences(hand) == 15 + 4 + 3
                    assert best_point(hand).length == 5, (
                        "a point of seven alongside 15, 4 and 3 would be a "
                        f"counterexample: {hand.code}"
                    )
                    checked += 1
    assert checked == 2880
