"""Tests for the capability ladder.

Each rung adds a named capability. The tests here check that the capability is
*present*; whether it actually helps is a separate question, answered by
measurement in `test_tournament.py` -- and two proposed rungs have already been
deleted for failing that second test.
"""

import random

import pytest

from piquet.cards import Card, parse_hand
from piquet.combos import Point
from piquet.heuristics import MAX_LEVEL, SINK_CEILING, HeuristicAgent
from piquet.observation import view_for
from piquet.rules import Declaration, Phase, deal_shuffled
from piquet.scoring import Category, Player
from piquet.style import Style

from tests.helpers import deal_with, declaring, skip_declarations

E, Y = Player.ELDER, Player.YOUNGER


def agent(level=1, **kw):
    return HeuristicAgent(level, rng=random.Random(1674), **kw)


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------


@pytest.mark.parametrize("level", [0, MAX_LEVEL + 1, -1])
def test_a_rung_must_exist(level):
    with pytest.raises(ValueError, match="level"):
        HeuristicAgent(level)


def test_erraticism_is_a_proportion():
    with pytest.raises(ValueError, match="erraticism"):
        HeuristicAgent(1, erraticism=1.5)


def test_an_agent_names_itself_after_its_rung():
    assert HeuristicAgent(3).name == "L3"


# --------------------------------------------------------------------------
# The exchange
# --------------------------------------------------------------------------


def test_every_rung_takes_the_full_exchange():
    """Not a judgement call: an agent that under-exchanges throws away most of
    elder's advantage."""
    deal = deal_shuffled(random.Random(1674))
    for level in range(1, MAX_LEVEL + 1):
        view = view_for(deal, E)
        assert len(agent(level).exchange(view)) == view.exchange_limit


def test_rung_one_simply_throws_its_lowest_cards():
    deal = deal_shuffled(random.Random(1674))
    view = view_for(deal, E)
    thrown = agent(1).exchange(view)
    kept = view.hand - thrown
    assert max(c.rank for c in thrown) <= min(c.rank for c in kept)


def test_rung_two_keeps_a_quatorze_that_rung_one_would_break_up():
    """Four tens are worth 14 points. Rung 1 throws them without a thought,
    because the ten is the lowest rank a set can be made of and rung 1 knows
    only that low cards go."""
    view = view_for(
        deal_with(
            elder="TS TH TD TC AS KS QS JS AH KH QH JH",
            younger="AD KD QD JD AC KC QC JC 9S 8S 7S 9H",
        ),
        E,
    )
    tens = parse_hand("TS TH TD TC")
    naive = agent(1).exchange(view) & tens
    shrewd = agent(2).exchange(view) & tens
    assert len(naive) == 4, "rung 1 throws every ten"
    assert len(shrewd) < len(naive), "rung 2 sees the quatorze"


def test_a_bold_style_and_a_cautious_one_discard_differently():
    """Not on every hand -- most discards are obvious to both -- but a style is
    only a style if it shows up somewhere."""
    rng = random.Random(99)
    bold = agent(2, style=Style(discard_boldness=0.95))
    shy = agent(2, style=Style(discard_boldness=0.05))
    differences = 0
    for _ in range(30):
        view = view_for(deal_shuffled(rng), E)
        differences += bold.exchange(view) != shy.exchange(view)
    assert differences > 0


# --------------------------------------------------------------------------
# The play
# --------------------------------------------------------------------------


def at_play(**hands):
    return skip_declarations(declaring(**hands))


PLAIN = dict(
    elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
    younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
)


def test_rung_one_leads_its_highest_card():
    deal = at_play(**PLAIN)
    assert agent(1).play(view_for(deal, E)) == Card.parse("AS")


def test_every_rung_follows_suit():
    deal = at_play(**PLAIN).play(E, Card.parse("AS"))
    for level in range(1, MAX_LEVEL + 1):
        chosen = agent(level).play(view_for(deal, Y))
        assert chosen.suit is Card.parse("AS").suit


def test_rung_two_wins_a_trick_as_cheaply_as_it_can():
    """Beat the card led, but with the smallest card that will do it."""
    deal = at_play(**PLAIN).play(E, Card.parse("7D"))
    assert agent(2).play(view_for(deal, Y)) == Card.parse("QD")


def test_rung_two_throws_its_lowest_when_it_cannot_win():
    deal = at_play(**PLAIN).play(E, Card.parse("AS"))
    assert agent(2).play(view_for(deal, Y)) == Card.parse("9S")


def test_rung_three_prefers_a_suit_it_can_actually_run():
    """Elder's spades are all established -- nothing higher is unaccounted for
    -- while his diamonds are not. Rung 2 cannot tell the difference."""
    deal = at_play(
        elder="AS KS QS JS TS 9S 8S 7S 7D 8D 9D TD",
        younger="AH KH QH JH TH 9H 8H 7H AD KD QD JD",
    )
    assert agent(3).play(view_for(deal, E)).suit is Card.parse("AS").suit


def test_rung_four_keeps_out_of_the_opponents_known_long_suit():
    """Younger's point was shown, so her long suit is public. Leading into it
    is how tricks are given away.

    But it becomes public only once elder has led: she names nothing until
    then. So the capability this rung is named for cannot show itself on the
    first lead -- which is the rule, not an oversight, and is why elder walks
    straight into her hearts here before he can avoid them.
    """
    deal = declaring(
        elder="AS KS 7S 8S AH KH 7H 8H AD KD 7C 8C",
        younger="QS JS TS 9S QH JH TH 9H QD JD QC JC",
    )
    deal = deal.declare(E, Declaration.sink())
    deal = deal.declare(Y, Declaration.full(deal.hand_of(Y), Category.POINT))
    deal = skip_declarations(deal)
    assert view_for(deal, E).seen == (), "she has named nothing yet"

    from piquet.cards import Card

    deal = deal.play(E, Card.parse("AH"))
    deal = deal.play(Y, Card.parse("9H"))

    shown = [c for c in view_for(deal, E).seen if isinstance(c, Point)]
    assert shown, "younger's point must have been exposed for this to mean anything"
    assert agent(4).play(view_for(deal, E)).suit is not shown[0].suit


# --------------------------------------------------------------------------
# Declaring
# --------------------------------------------------------------------------


def test_the_lower_rungs_never_conceal():
    deal = declaring(**PLAIN)
    for level in (1, 2, 3):
        chatty = HeuristicAgent(level, style=Style(sinking=1.0),
                                rng=random.Random(1674))
        assert chatty.declare(view_for(deal, E), Category.POINT)


def test_an_opponent_with_a_sinking_habit_sometimes_says_nothing():
    deal = declaring(**PLAIN)
    sneaky = HeuristicAgent(4, style=Style(sinking=1.0), rng=random.Random(1674))
    assert not sneaky.declare(view_for(deal, E), Category.POINT)


def test_nobody_ever_sinks_a_quatorze():
    """The economics: a tierce exposes three cards to buy 3 points, which is a
    poor trade; a quatorze exposes four to buy 14, which is a fine one."""
    deal = declaring(
        elder="AS AH AD AC KS KH KD KC 7S 8S 7H 8H",
        younger="QS JS TS 9S QH JH TH 9H QD JD QC JC",
    )
    sneaky = HeuristicAgent(4, style=Style(sinking=1.0), rng=random.Random(1674))
    declared = sneaky.declare(view_for(deal, E), Category.SETS)
    assert declared.score > SINK_CEILING


# --------------------------------------------------------------------------
# Erraticism
# --------------------------------------------------------------------------


def test_a_steady_agent_always_plays_at_its_own_rung():
    steady = HeuristicAgent(3, rng=random.Random(1674))
    assert {steady._rung() for _ in range(200)} == {3}


def test_an_erratic_agent_varies_the_capability_it_brings():
    """Not noise on the answer: the *rung* moves, so the agent is occasionally
    sharper and occasionally sloppier, the way a person is."""
    erratic = HeuristicAgent(3, erraticism=0.8, rng=random.Random(1674))
    rungs = {erratic._rung() for _ in range(400)}
    assert len(rungs) > 1
    assert rungs <= set(range(1, MAX_LEVEL + 1))


# --------------------------------------------------------------------------
# Legality, over many deals
# --------------------------------------------------------------------------


def test_no_rung_ever_makes_an_illegal_move():
    from piquet.match import play_deals

    rng = random.Random(1674)
    for level in range(1, MAX_LEVEL + 1):
        deals, _ = play_deals(
            HeuristicAgent(level, style=Style.random(rng), erraticism=0.4, rng=rng),
            HeuristicAgent(level, style=Style.random(rng), rng=rng),
            60,
            rng=rng,
            keep_records=False,
        )
        assert all(d.phase is Phase.COMPLETE for d in deals)
        assert all(len(d.tricks) == 12 for d in deals)
