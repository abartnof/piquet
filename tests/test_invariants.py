"""Statistical invariants over many deals.

These catch what unit tests cannot. The declaration bug that survived unit
testing -- two sequences in one suit are legal when a gap splits it -- was found
by playing deals, not by reasoning about them.

They are also where the engine is checked against what the historical sources
claim: that dealing is a disadvantage, and how often a carte blanche turns up.
"""

import random
from math import comb, sqrt

import pytest

from piquet.agents import RandomAgent
from piquet.cards import Hand, full_deck
from piquet.combos import is_carte_blanche
from piquet.match import play_deals
from piquet.rules import Phase
from piquet.scoring import Category, Player

E, Y = Player.ELDER, Player.YOUNGER

DEALS = 3000           # full deals, played out; about two seconds
HANDS = 200_000        # hands dealt but not played; much cheaper


@pytest.fixture(scope="module")
def played():
    rng = random.Random(1674)
    deals, records = play_deals(
        RandomAgent(rng, name="elder-random"),
        RandomAgent(rng, name="younger-random"),
        DEALS,
        rng=rng,
    )
    return deals, records


def within_noise(observed: int, expected: float, sigmas: float = 4.0) -> bool:
    """Poisson-ish tolerance, so a correct engine does not fail on a bad day."""
    return abs(observed - expected) <= sigmas * sqrt(max(expected, 1.0))


# --------------------------------------------------------------------------
# Carte blanche
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_carte_blanche_turns_up_about_once_in_1792_hands():
    """C(20,12)/C(32,12). Wikipedia's "roughly once every 1,800 hands" -- and
    note that it is per *hand*, not per deal."""
    expected_rate = comb(20, 12) / comb(32, 12)
    assert round(1 / expected_rate) == 1792

    rng = random.Random(1674)
    deck = list(full_deck())
    seen = sum(
        1 for _ in range(HANDS)
        if is_carte_blanche(Hand.of(*rng.sample(deck, 12)))
    )
    assert within_noise(seen, HANDS * expected_rate)


@pytest.mark.slow
def test_a_whole_deal_shows_one_about_twice_as_often():
    """A deal has two hands and they are mutually exclusive, so a carte blanche
    appears somewhere in a deal about once in 896 deals rather than 1,792."""
    from piquet.rules import deal_shuffled

    rng = random.Random(99)
    trials = 60_000
    seen = sum(
        1 for _ in range(trials)
        if any(e.category is Category.CARTE_BLANCHE for e in deal_shuffled(rng).log)
    )
    assert within_noise(seen, trials * 2 * comb(20, 12) / comb(32, 12))


@pytest.mark.slow
def test_two_carte_blanches_at_once_never_happen(played):
    deals, _ = played
    for deal in deals:
        holders = {
            event.player for event in deal.log
            if event.category is Category.CARTE_BLANCHE
        }
        assert len(holders) <= 1


# --------------------------------------------------------------------------
# The sources' claims about the game
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_dealing_is_a_disadvantage(played):
    """Every source since Cotton says so, and it shows even under random play.

    The margin is thin here because these agents choose their discards at
    random: elder's edge comes from information and tempo he does not know how
    to use. It should widen as the ladder is climbed, and that widening is
    itself a check that the heuristics are doing something.
    """
    deals, _ = played
    elder_wins = sum(1 for d in deals if d.log.total(E) > d.log.total(Y))
    assert elder_wins / len(deals) > 0.51


@pytest.mark.slow
def test_elders_advantage_depends_on_taking_the_full_exchange(played):
    """An agent that exchanges a random number of cards throws away most of
    elder's edge -- which is why Britannica says elder "in practice usually
    exchanges five cards"."""
    rng = random.Random(1674)
    lazy, _ = play_deals(
        RandomAgent(rng, exchange_size="random"),
        RandomAgent(rng, exchange_size="random"),
        1500,
        rng=rng,
        keep_records=False,
    )
    lazy_rate = sum(1 for d in lazy if d.log.total(E) > d.log.total(Y)) / len(lazy)
    deals, _ = played
    keen_rate = sum(1 for d in deals if d.log.total(E) > d.log.total(Y)) / len(deals)
    assert keen_rate > lazy_rate


@pytest.mark.slow
def test_only_elder_ever_scores_a_pique(played):
    deals, _ = played
    piques = [
        event.player for d in deals for event in d.log
        if event.category is Category.BONUS and event.detail == "pique"
    ]
    assert piques, "no pique occurred in the sample; the test proves nothing"
    assert set(piques) == {E}


@pytest.mark.slow
def test_younger_does_sometimes_repique(played):
    """The observable fingerprint of Cavendish's Law 67. Repique reckons in
    category order, so elder's point for leading -- category V -- does not block
    her. Had we derived repique temporally, this count would be zero and
    everything else would still look right."""
    deals, _ = played
    younger_repiques = sum(
        1 for d in deals for event in d.log
        if event.category is Category.BONUS
        and event.detail == "repique"
        and event.player is Y
    )
    assert younger_repiques > 0


# --------------------------------------------------------------------------
# Engine invariants
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_every_deal_completes_legally(played):
    deals, _ = played
    for deal in deals:
        assert deal.phase is Phase.COMPLETE
        assert len(deal.tricks) == 12
        assert not deal.hand_of(E) and not deal.hand_of(Y)
        assert deal.pending_for_younger == 0


@pytest.mark.slow
def test_every_card_is_accounted_for_at_the_end(played):
    deals, _ = played
    for deal in deals:
        played_cards = [
            card
            for trick in deal.tricks
            for card in (trick.led, trick.followed)
        ]
        accounted = (
            played_cards
            + list(deal.discard_of(E))
            + list(deal.discard_of(Y))
            + list(deal.talon_untaken)
        )
        assert len(accounted) == 32
        assert len(set(accounted)) == 32


@pytest.mark.slow
def test_every_score_reconciles_against_the_event_log(played):
    deals, records = played
    for deal, record in zip(deals, records):
        assert record.elder_score == deal.log.total(E)
        assert record.younger_score == deal.log.total(Y)
        assert sum(e.amount for e in deal.log) == (
            deal.log.total(E) + deal.log.total(Y)
        )


@pytest.mark.slow
def test_no_player_scores_both_a_pique_and_a_repique(played):
    deals, _ = played
    for deal in deals:
        bonuses = [e for e in deal.log if e.category is Category.BONUS]
        assert len(bonuses) <= 1


@pytest.mark.slow
def test_the_cards_are_scored_to_exactly_one_player_unless_tricks_are_even(played):
    deals, _ = played
    for deal in deals:
        cards = [e for e in deal.log if e.category is Category.CARDS]
        elder_tricks = deal.tricks_won(E)
        if elder_tricks == 6:
            assert cards == []
        else:
            assert len(cards) == 1
            assert cards[0].amount in (10, 40)
            assert (cards[0].amount == 40) == (elder_tricks in (0, 12))


# --------------------------------------------------------------------------
# The move log
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_every_deal_records_thirty_two_decisions(played):
    """Two exchanges, six declarations, twenty-four cards."""
    _, records = played
    for record in records:
        assert len(record.decisions) == 2 + 6 + 24


@pytest.mark.slow
def test_the_move_log_round_trips_through_json(played, tmp_path):
    import json

    from piquet.match import write_jsonl

    _, records = played
    path = write_jsonl(records[:50], tmp_path / "moves.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 50
    first = json.loads(lines[0])
    assert first["elder_agent"] == "elder-random"
    assert len(first["decisions"]) == 32
    assert set(first) >= {"deal", "decisions", "elder_score", "younger_score", "bonus"}


def test_the_log_records_what_a_declaration_gave_up(played):
    """`forgone` is the cost side of sinking, and the signal to look for when
    asking later whether concealment ever paid."""
    _, records = played
    declarations = [
        d for r in records for d in r.decisions if d.phase.startswith("declare")
    ]
    assert declarations
    assert all(d.forgone == 0 for d in declarations), "these agents never sink"
    assert all(d.options is None for d in declarations), (
        "a declaration may be understated to any smaller holding, so its "
        "alternatives are not enumerable"
    )


@pytest.mark.slow
def test_the_log_counts_alternatives_only_where_they_can_be_counted(played):
    _, records = played
    plays = [d for r in records for d in r.decisions if d.phase == "play"]
    assert all(1 <= d.options <= 12 for d in plays)
