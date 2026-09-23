"""Tests for the exact play solver and the inference that feeds it.

The solver returns **elder minus younger** for the rest of the play, so elder
maximises and younger minimises and one number flows through the recursion.

Positions here are written with an `elder_tricks` that makes the deal add up to
twelve tricks in total, because the cards bonus depends on the whole deal and
not just on the fragment being solved.
"""

import random

import pytest

from piquet.cards import Card, parse_hand
from piquet.heuristics import HeuristicAgent
from piquet.inference import known_voids, opponent_hand_size, possible_hands
from piquet.observation import view_for
from piquet.rules import Phase, deal_shuffled
from piquet.scoring import Player
from piquet.solver import CAPOT_BONUS, CARDS_BONUS, best_card, card_values, solve

E, Y = Player.ELDER, Player.YOUNGER


# --------------------------------------------------------------------------
# The endgame, worked by hand
# --------------------------------------------------------------------------


def test_the_last_trick_taken_by_the_leader():
    """Elder leads the ace and takes the last trick: one for leading, one more
    for the last trick, and ten for the cards on seven tricks to five."""
    value = solve(parse_hand("AS"), parse_hand("KS"), E, elder_tricks=6)
    assert value == 1 + 1 + CARDS_BONUS


def test_the_last_trick_taken_by_the_follower():
    """Elder leads and loses it: he still scores for leading, younger scores
    for winning and again for the last trick, and six each pays nobody."""
    value = solve(parse_hand("7S"), parse_hand("AS"), E, elder_tricks=6)
    assert value == 1 - 1 - 1


def test_a_capot_is_worth_forty_on_top_of_the_trick_points():
    """Elder holds every card that matters: twelve leads, the last trick, and
    forty for taking all twelve."""
    elder = parse_hand("AS KS QS JS TS 9S 8S 7S AH KH QH JH")
    younger = parse_hand("TH 9H 8H 7H AD KD QD JD AC KC QC JC")
    assert solve(elder, younger, E) == 12 + 1 + CAPOT_BONUS


def test_a_card_of_another_suit_never_wins():
    """Younger is void in spades and holds the ace of diamonds; it takes
    nothing, because piquet has no trumps."""
    value = solve(parse_hand("7S"), parse_hand("AD"), E, elder_tricks=6)
    assert value == 1 + 1 + CARDS_BONUS


def test_six_tricks_each_pays_neither_player():
    value = solve(parse_hand("AS"), parse_hand("KS"), E, elder_tricks=5)
    assert value == 1 + 1


# --------------------------------------------------------------------------
# Choosing a card
# --------------------------------------------------------------------------


def test_the_solver_ducks_where_a_greedy_player_would_cash():
    """Ace and seven against king and eight, elder to lead.

    The instinct is to cash the ace. The solver leads the *seven*, and it is
    right: the ace wins whenever it is played, so spending it on the first
    trick buys a trick worth one, while ducking lets it win the **last** trick,
    which is worth two. Leading the ace is worth 0; leading the seven is +1.

    This test originally asserted the opposite, on the author's intuition. The
    solver disagreed and the solver was correct -- which is the whole argument
    for having one.
    """
    elder, younger = parse_hand("AS 7S"), parse_hand("KS 8S")
    card, value = best_card(elder, younger, E, elder_tricks=5)
    assert card == Card.parse("7S")
    assert value == 1
    assert value == solve(elder, younger, E, elder_tricks=5)

    values = card_values(elder, younger, E, elder_tricks=5)
    assert values[Card.parse("AS")] == 0, "cashing the ace throws a point away"


def test_younger_plays_to_make_the_value_smallest():
    """The sign convention never flips: elder maximises, younger minimises.

    Elder has led the nine holding the ace behind it. Younger must head the
    trick with the king: ducking hands elder the lead, the last trick and the
    ten for cards.
    """
    elder, younger = parse_hand("AS"), parse_hand("KS 7S")
    values = card_values(
        elder, younger, leader=E, led=Card.parse("9S"), elder_tricks=5
    )
    assert values[Card.parse("KS")] < values[Card.parse("7S")]
    card, _ = best_card(
        elder, younger, leader=E, led=Card.parse("9S"), elder_tricks=5
    )
    assert card == Card.parse("KS")


def test_card_values_agree_with_the_best_card():
    elder, younger = parse_hand("AS QS 7S"), parse_hand("KS JS 8S")
    values = card_values(elder, younger, E, elder_tricks=4)
    card, value = best_card(elder, younger, E, elder_tricks=4)
    assert values[card] == value
    assert value == max(values.values())


def test_every_legal_card_is_valued():
    elder, younger = parse_hand("AS QS 7H"), parse_hand("KS JS 8H")
    values = card_values(elder, younger, E, elder_tricks=4)
    assert set(values) == set(elder)


# --------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------


def played_out(seed: int):
    """A deal wound into the middle of the play."""
    rng = random.Random(seed)
    deal = deal_shuffled(rng)
    agents = (HeuristicAgent(4, rng=rng), HeuristicAgent(4, rng=rng))
    for player in (E, Y):
        deal = deal.exchange(player, agents[player.index].exchange(view_for(deal, player)))
    while deal.to_declare is not None:
        player = deal.to_declare
        deal = deal.declare(
            player,
            agents[player.index].declare(view_for(deal, player), deal.declaring_category),
        )
    for _ in range(8):
        player = deal.to_play
        deal = deal.play(player, agents[player.index].play(view_for(deal, player)))
    return deal


def test_the_opponents_real_hand_is_always_a_candidate():
    """The one thing inference must never do is rule out the truth."""
    for seed in range(1674, 1684):
        deal = played_out(seed)
        if deal.phase is not Phase.PLAY:
            continue
        for player in (E, Y):
            view = view_for(deal, player)
            assert deal.hand_of(player.opponent) in possible_hands(view)


def test_the_opponents_hand_size_is_known_exactly():
    deal = played_out(1674)
    for player in (E, Y):
        view = view_for(deal, player)
        assert opponent_hand_size(view) == len(deal.hand_of(player.opponent))


def test_a_void_is_remembered_for_the_rest_of_the_deal():
    """Failing to follow suit is permanent, certain information."""
    from tests.helpers import declaring, play_cards, skip_declarations

    deal = skip_declarations(declaring(
        elder="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
        younger="TH 9H 8H 7H AD KD QD JD AC KC QC JC",
    ))
    deal = play_cards(deal, "AS", "JC")     # younger cannot follow spades
    view = view_for(deal, E)
    from piquet.cards import Suit

    assert Suit.SPADES in known_voids(view)
    assert all(not hand.in_suit(Suit.SPADES) for hand in possible_hands(view, limit=20))


def test_declarations_narrow_the_candidates_sharply():
    """They must be read against the opponent's *original* twelve, not what is
    left of them -- a quint is broken up the moment one of its cards is led."""
    deal = played_out(1674)
    view = view_for(deal, E)
    with_talk = len(possible_hands(view))
    without = len(possible_hands(view, use_declarations=False))
    assert with_talk <= without


# --------------------------------------------------------------------------
# The agent
# --------------------------------------------------------------------------


def test_the_solver_agent_only_searches_once_the_endgame_is_in_range():
    from piquet.solver import SolverAgent

    agent = SolverAgent(rng=random.Random(1674), exact_from=8)
    assert agent.exact_from == 8


@pytest.mark.slow
def test_the_solver_agent_plays_legal_cards_throughout():
    from piquet.match import play_deals
    from piquet.solver import SolverAgent

    rng = random.Random(1674)
    deals, _ = play_deals(
        SolverAgent(rng=rng, exact_from=6),
        HeuristicAgent(4, rng=rng),
        6,
        rng=rng,
        keep_records=False,
    )
    assert all(d.phase is Phase.COMPLETE for d in deals)
    assert all(len(d.tricks) == 12 for d in deals)


# --------------------------------------------------------------------------
# Regressions from the code review
# --------------------------------------------------------------------------


def test_the_opponents_hand_size_is_right_while_a_trick_is_open():
    """Only the opponent having *led* reduces their count. An earlier version
    decremented for any open trick, which was invisible in play -- an agent only
    asks on its own turn -- but would have built candidate hands one card short.
    """
    from tests.helpers import declaring, play_cards, skip_declarations

    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    deal = play_cards(deal, "AS")   # elder has led; younger has not yet played
    for player in (E, Y):
        view = view_for(deal, player)
        assert opponent_hand_size(view) == len(deal.hand_of(player.opponent))


def test_capping_the_candidates_samples_rather_than_truncates():
    """`combinations` emits in a fixed order, so taking the first N yields hands
    that all share the same low-indexed cards -- a skewed picture, and precisely
    the wrong thing to feed a Monte Carlo average."""
    for seed in range(1674, 1700):
        deal = played_out(seed)
        if deal.phase is not Phase.PLAY:
            continue
        view = view_for(deal, E)
        everything = possible_hands(view)
        if len(everything) >= 8:
            break
    else:
        pytest.fail("no position with enough candidates to sample from")

    first = possible_hands(view, limit=2, rng=random.Random(1))
    second = possible_hands(view, limit=2, rng=random.Random(99))
    assert len(first) == len(second) == 2
    assert all(hand in everything for hand in first + second)
    assert set(first) != set(second), "different seeds must give different samples"


def test_ratings_survive_a_shutout():
    """An agent that wins nothing would otherwise be given a strength of zero,
    and the Elo conversion would take its logarithm."""
    from piquet.tournament import DuelResult, ratings

    table = ratings(
        [DuelResult("winner", "loser", pairs=10, a_wins=10, b_wins=0, drawn=0,
                    a_points=100, b_points=0)],
        anchor="winner",
    )
    assert table["winner"] == 0
    assert table["loser"] < -500


def test_best_card_agrees_with_card_values_for_both_seats():
    elder, younger = parse_hand("AS QS 7S"), parse_hand("KS JS 8S")
    for leader, led in ((E, None), (E, Card.parse("7S"))):
        hand = elder if (leader is E) == (led is None) else younger
        if led is not None:
            hand = younger
        values = card_values(elder if led is None else parse_hand("AS QS"),
                             younger, leader, led, elder_tricks=4)
        card, value = best_card(elder if led is None else parse_hand("AS QS"),
                                younger, leader, led, elder_tricks=4)
        assert values[card] == value
        assert value == (max(values.values()) if led is None else min(values.values()))


@pytest.mark.parametrize("elder_takes", [1, 2, 3, 4, 5])
def test_inference_never_rules_out_the_truth_however_elder_exchanges(elder_takes):
    """Every agent built so far takes the full five, which hid this entirely.

    When elder takes fewer, younger draws from the top of what is left -- which
    starts inside the five he has read. Those cards are hers, and he watched
    her take them, so candidates must be *built* around them rather than
    enumerated from the cards he cannot place.
    """
    from piquet.cards import Hand
    from piquet.rules import Declaration

    rng = random.Random(1674)
    for _ in range(12):
        deal = deal_shuffled(rng)
        deal = deal.exchange(E, Hand.of(*list(deal.hand_of(E))[:elder_takes]))
        deal = deal.exchange(Y, Hand.of(*list(deal.hand_of(Y))[:3]))
        while deal.to_declare is not None:
            player = deal.to_declare
            deal = deal.declare(
                player,
                Declaration.full(deal.hand_of(player), deal.declaring_category),
            )
        for player in (E, Y):
            view = view_for(deal, player)
            assert deal.hand_of(player.opponent) in possible_hands(view)


def test_elder_taking_fewer_cards_leaves_him_less_certain_not_more():
    """He has read seventeen cards either way, but taking fewer leaves more of
    the talon face down -- and a face-down talon card is indistinguishable from
    one of her discards. Knowing three of her cards does not make up for it."""
    from piquet.cards import Hand

    counts = {}
    for elder_takes in (5, 2):
        deal = deal_shuffled(random.Random(1674))
        deal = deal.exchange(E, Hand.of(*list(deal.hand_of(E))[:elder_takes]))
        deal = deal.exchange(Y, Hand.of(*list(deal.hand_of(Y))[:3]))
        counts[elder_takes] = len(possible_hands(view_for(deal, E), use_declarations=False))
    assert counts[5] == 455
    assert counts[2] == 5005


def test_an_impossible_position_is_rejected_rather_than_explored():
    """Two hands that cannot both be true used to run a player out of cards
    somewhere deep in the recursion and surface as a TypeError."""
    with pytest.raises(ValueError, match="difference must be 0"):
        solve(parse_hand("AS KS"), parse_hand("QS"), E, elder_tricks=5)
    with pytest.raises(ValueError, match="difference must be 1"):
        card_values(
            parse_hand("AS KS"), parse_hand("QS"), E,
            led=Card.parse("7S"), elder_tricks=5,
        )


# --------------------------------------------------------------------------
# What survives concealment
# --------------------------------------------------------------------------
#
# The dialogue gives up three different grades of information and they are not
# equally trustworthy:
#
#   what she showed  -- cards on the table. Not an assumption at all.
#   what she claimed -- a floor. You may declare less than you hold, never more.
#   what she did not -- only worth anything if she declared fully.
#
# An opponent who sinks breaks the third and nothing else.


def _sinking_deal():
    """Younger wins the point and shows it, then sinks a huitieme."""
    from piquet.rules import Declaration
    from piquet.scoring import Category
    from tests.helpers import after_elders_lead, declaring

    deal = declaring(
        elder="AD KD QD JD TD 9D 8D AC KC QC JC TC",
        younger="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
    )
    deal = deal.declare(E, Declaration.full(deal.hand_of(E), Category.POINT))
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))
    deal = deal.declare(E, Declaration.full(deal.hand_of(E), Category.SEQUENCES))
    deal = deal.declare(Y, Declaration.sink())
    deal = deal.declare(E, Declaration.sink())
    deal = deal.declare(Y, Declaration.sink())
    return after_elders_lead(deal)


def test_sinking_does_not_make_the_engine_forget_what_it_was_shown():
    """She won the point, so elder was entitled to look at it, and did. Those
    eight spades are on the table. Concealing her sequence cannot un-show them,
    but they shared one filter with the honesty assumption and one fallback."""
    deal = _sinking_deal()
    view = view_for(deal, E)
    assert view.seen, "her point scored, so it had to be shown"

    hands = possible_hands(view)
    assert deal.hand_of(Y) in hands, "and the truth is still in there"
    for hand in hands:
        assert all(c.is_supported_by(hand) for c in view.seen)


def test_a_declaration_is_a_floor_that_concealment_cannot_lower():
    """"He calls five cards, and declares five spades, when he might have six."
    Never four. Understating is allowed and overstating is not, so the number
    she said is the least she can hold -- true however much she sank."""
    deal = _sinking_deal()
    view = view_for(deal, Y)
    spoken = {a.category: a.primary for a in view.heard}
    assert spoken, "elder declared his point and his sequences"

    from piquet.combos import best_point, best_sequence
    from piquet.scoring import Category

    for hand in possible_hands(view):
        assert best_point(hand).length >= spoken[Category.POINT]
        if Category.SEQUENCES in spoken:
            assert best_sequence(hand).length >= spoken[Category.SEQUENCES]
