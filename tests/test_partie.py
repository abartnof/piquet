"""Tests for the partie: six deals, the alternating deal, and the rubicon.

A deal is not the game, and the settlement clause is why. If the loser reached
a hundred he pays the *difference* plus a hundred; if he did not he pays the
*sum* plus a hundred. So 105 to 101 pays 104, while 97 to 89 pays 286. Failing
to cross the line is punished far more severely than losing narrowly, which is
the whole shape of correct play late in a partie.

Authority: pagat.com. "A game consists of a set of 6 deals called a partie,
with the deal alternating... If the scores are equal after 6 deals, two more
hands are played. If they are then still equal the partie is a draw."
"""

import random

import pytest

from piquet.heuristics import HeuristicAgent
from piquet.observation import view_for
from piquet.partie import (
    DEALS_IN_PARTIE,
    PARTIE_BONUS,
    RUBICON,
    Partie,
    Side,
    Standing,
)
from piquet.scoring import Player

A, B = Side.A, Side.B
E, Y = Player.ELDER, Player.YOUNGER


#: Six deals that do not come out level. Any *constant* pair of scores does,
#: because the seats swap every deal -- which is itself the point of mirrored
#: pairs in `tournament`, seen from the other end.
DECISIVE_SIX = [(20, 10)] * 5 + [(50, 5)]


def partie_of(*deals, opening_dealer=A):
    """A partie built from (elder's score, younger's score) pairs."""
    partie = Partie(opening_dealer=opening_dealer)
    for elder, younger in deals:
        partie = partie.record_scores(elder, younger)
    return partie


# --------------------------------------------------------------------------
# Six deals, and who is elder in each
# --------------------------------------------------------------------------


def test_a_partie_is_six_deals():
    partie = Partie()
    assert partie.deals_left == DEALS_IN_PARTIE
    partie = partie_of(*DECISIVE_SIX[:5])
    assert not partie.complete and partie.deals_left == 1
    partie = partie.record_scores(*DECISIVE_SIX[5])
    assert partie.complete and partie.deals_left == 0


def test_the_deal_alternates_and_the_first_dealer_is_elder_in_the_sixth():
    """pagat: the winner of the cut "should always choose to deal first, as
    there is a slight advantage to being non-dealer on the critical sixth
    hand". Dealing the first deal is what puts you in elder's seat for it."""
    partie = Partie(opening_dealer=A)
    assert [partie.elder_in(n) for n in range(1, 7)] == [B, A, B, A, B, A]
    assert partie.elder_in(DEALS_IN_PARTIE) is A

    flipped = Partie(opening_dealer=B)
    assert [flipped.elder_in(n) for n in range(1, 7)] == [A, B, A, B, A, B]


def test_the_seat_that_scored_is_resolved_to_the_person_who_sat_in_it():
    """The only thing this module is really for. Elder and younger change
    hands every deal; the rubicon is reckoned over a person."""
    partie = partie_of((30, 5), (2, 40), opening_dealer=A)
    # deal 1: B is elder and scores 30; deal 2: A is elder and scores 2.
    assert partie.score_of(B) == 30 + 40
    assert partie.score_of(A) == 5 + 2
    assert partie.totals == (7, 70)


def test_a_finished_deal_can_be_entered_straight_from_its_log():
    from piquet.rules import Phase, deal_shuffled
    from piquet.match import play_deal

    agent = HeuristicAgent(3, rng=random.Random(1674))
    deal, _ = play_deal(agent, agent, deal=deal_shuffled(random.Random(7)))
    assert deal.phase is Phase.COMPLETE
    partie = Partie().record(deal)
    assert partie.totals[partie.elder_in(1).index] == deal.log.total(E)
    assert partie.totals[partie.elder_in(1).other.index] == deal.log.total(Y)


def test_an_unfinished_deal_is_not_a_result():
    from piquet.rules import deal_shuffled

    with pytest.raises(ValueError, match="not finished"):
        Partie().record(deal_shuffled(random.Random(1)))


def test_nothing_can_be_entered_into_a_partie_that_is_over():
    partie = partie_of(*DECISIVE_SIX)
    assert partie.complete
    with pytest.raises(ValueError, match="already settled"):
        partie.record_scores(1, 1)


# --------------------------------------------------------------------------
# The rubicon
# --------------------------------------------------------------------------


def test_the_loser_who_reached_a_hundred_pays_the_difference():
    """105 to 101 pays 104."""
    partie = partie_of((105, 101), *[(0, 0)] * 5)
    settlement = partie.settlement
    assert settlement.winner is B and not settlement.rubicon
    assert settlement.points == 105 - 101 + PARTIE_BONUS == 104


def test_the_loser_who_did_not_pays_the_sum():
    """97 to 89 pays 286 -- nearly three times as much for a closer game."""
    partie = partie_of((97, 89), *[(0, 0)] * 5)
    settlement = partie.settlement
    assert settlement.winner is B and settlement.rubicon
    assert settlement.points == 97 + 89 + PARTIE_BONUS == 286


def test_a_loser_exactly_on_a_hundred_is_over_the_rubicon():
    """"At least 100." The boundary is the whole point of the rule, so it is
    worth pinning which side of it a hundred exactly falls on."""
    assert not partie_of((120, RUBICON), *[(0, 0)] * 5).settlement.rubicon
    assert partie_of((120, RUBICON - 1), *[(0, 0)] * 5).settlement.rubicon


def test_the_winner_being_short_himself_does_not_save_the_loser():
    """Britannica is explicit that the loser is rubiconed "even if the winner
    also fails" to reach 100. Easy to get wrong by guarding on the wrong
    score: here the winner is on 60 and still collects the sum."""
    settlement = partie_of((60, 40), *[(0, 0)] * 5).settlement
    assert settlement.rubicon
    assert settlement.points == 60 + 40 + PARTIE_BONUS


def test_a_partie_is_not_settled_until_it_is_over():
    assert partie_of(*DECISIVE_SIX[:5]).settlement is None
    assert partie_of(*DECISIVE_SIX).settlement is not None


# --------------------------------------------------------------------------
# Level scores
# --------------------------------------------------------------------------


def test_level_after_six_deals_means_two_more():
    partie = partie_of(*[(15, 15)] * 6)
    assert not partie.complete
    assert partie.deals_left == 2
    assert partie.settlement is None


def test_both_extra_deals_are_played_even_once_the_tie_is_broken():
    """"Two more hands are played" -- each player deals one of them, so the
    pair is played out rather than stopping the moment someone edges ahead.
    Anything else would hand the seat advantage to whoever broke the tie."""
    partie = partie_of(*[(15, 15)] * 6).record_scores(30, 10)
    assert not partie.complete
    assert partie.deals_left == 1


def test_still_level_after_the_extra_deals_is_a_draw():
    partie = partie_of(*[(15, 15)] * 8)
    assert partie.complete
    settlement = partie.settlement
    assert settlement.winner is None and settlement.points == 0


def test_the_extra_deals_keep_alternating_the_deal():
    partie = Partie(opening_dealer=A)
    assert [partie.elder_in(n) for n in (7, 8)] == [B, A]


# --------------------------------------------------------------------------
# What a player may know about where the partie stands
# --------------------------------------------------------------------------


def test_a_standing_reads_the_same_table_from_either_side():
    standing = Standing(mine=95, theirs=120, deals_left=1)
    assert standing.is_last_deal
    assert standing.short_of_the_rubicon
    assert standing.reversed == Standing(mine=120, theirs=95, deals_left=1)
    assert not standing.reversed.short_of_the_rubicon


def test_the_partie_reports_the_standing_for_the_deal_about_to_be_played():
    partie = partie_of((30, 5), (2, 40), opening_dealer=A)   # A: 7, B: 70
    standing = partie.standing                                # deal 3, B is elder
    assert partie.elder is B
    assert standing == Standing(mine=70, theirs=7, deals_left=4)


def test_a_view_carries_the_standing_from_that_players_side():
    from piquet.rules import deal_shuffled

    deal = deal_shuffled(random.Random(1674))
    standing = Standing(mine=95, theirs=120, deals_left=1)
    assert view_for(deal, E, standing).partie == standing
    assert view_for(deal, Y, standing).partie == standing.reversed


def test_a_deal_played_on_its_own_has_no_standing_at_all():
    """Most of the test suite and the whole tournament harness. A deal is a
    complete object without a partie around it."""
    from piquet.rules import deal_shuffled

    assert view_for(deal_shuffled(random.Random(1674)), E).partie is None


# --------------------------------------------------------------------------
# Playing one
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_a_partie_plays_six_deals_with_the_seats_swapping():
    from piquet.match import play_partie

    rng = random.Random(1674)
    partie, records = play_partie(
        HeuristicAgent(3, rng=rng, name="north"),
        HeuristicAgent(3, rng=rng, name="south"),
        rng=rng,
    )
    assert partie.complete
    assert len(partie.outcomes) >= DEALS_IN_PARTIE
    assert [o.elder for o in partie.outcomes[:6]] == [B, A, B, A, B, A]
    assert sum(partie.totals) == sum(sum(o.scores) for o in partie.outcomes)
    assert partie.settlement is not None
    assert len(records) == len(partie.outcomes)
    assert {r.elder_agent for r in records} == {"north", "south"}


@pytest.mark.slow
def test_a_partie_hands_each_agent_the_running_scores():
    """The agents cannot play the rubicon endgame without them, and they are
    public: scores are called aloud."""
    from piquet.match import play_partie

    seen = []

    class Watchful(HeuristicAgent):
        def play(self, view):
            seen.append(view.partie)
            return super().play(view)

    rng = random.Random(1674)
    play_partie(Watchful(3, rng=rng), HeuristicAgent(3, rng=rng), rng=rng)
    assert all(s is not None for s in seen)
    assert {s.deals_left for s in seen} == {6, 5, 4, 3, 2, 1}
    assert seen[0] == Standing(mine=0, theirs=0, deals_left=6)
