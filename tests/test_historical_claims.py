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

    A separate run of 400 restarts, too slow for the suite, reached 57 and
    never exceeded it. See docs/DESIGN.md section 3.11.
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
