"""The golden vectors, and the proof that the engine still agrees with them.

`docs/DESIGN.md` §2 promised these "from day one" and `PLAN.md` TODO 5 recorded,
honestly, that they were never built. They are the specification the Rust port
is checked against: every value under `vectors/` was produced by the Python
engine that passes the rest of this suite, so a Rust implementation which
reproduces them is, to exactly that extent, correct.

This module is the **Python consumer** of those vectors. The Rust one will be
its mirror -- same files, same assertions -- which is the entire point. A vector
nobody replays is a JSON file, not a specification.

It has a second job, and on most days the only one that earns its keep: it locks
the engine against drift. If someone changes what `Card.index` means, this fails
here, in Python, rather than six months later as an inexplicable disagreement
between two languages.

Two rules govern what may go into a vector, both from §2.1:

- **Never a seed.** No two languages share a random number generator, so every
  case is written against an explicit input -- a card code, a hand, a pack
  ordering -- and never against `random.seed(n)`.
- **Integers wherever the engine allows it.** Where a float is genuinely
  unavoidable the vector carries a tolerance rather than an exact value.

Bit masks travel as JSON numbers. A 32-bit mask reaches 2**31, comfortably
inside the 2**53 a double represents exactly, so nothing is lost. Anything wider
-- the solver's 75-bit transposition key, when its turn comes -- must travel as
a decimal string instead.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from piquet.cards import Card, Hand, Suit, full_deck, parse_hand

VECTORS = pathlib.Path(__file__).resolve().parents[1] / "vectors"


def load(name: str) -> dict:
    path = VECTORS / f"{name}.json"
    if not path.exists():
        pytest.fail(
            f"missing vector file {path.name}; generate it with "
            f"`python tools/emit_vectors.py`"
        )
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def vec() -> dict:
    return load("cards")


# -- the pack ---------------------------------------------------------------


def test_pack_covers_every_index_exactly_once(vec):
    assert [case["index"] for case in vec["pack"]] == list(range(32))


def test_pack_round_trips_through_index_and_code(vec):
    for case in vec["pack"]:
        card = Card.from_index(case["index"])
        assert card.code == case["code"]
        assert card.index == case["index"]
        assert Card.parse(case["code"]) == card


def test_pack_pins_rank_and_suit_as_numbers(vec):
    """Rank and suit travel as integers, deliberately.

    A port may name the ace whatever it likes, but `Rank.ACE` must be 14 and
    `Suit.SPADES` must be 3, because `Card.index` is arithmetic on both and
    every bit position in the engine follows from it.
    """
    for case in vec["pack"]:
        card = Card.from_index(case["index"])
        assert int(card.rank) == case["rank"]
        assert int(card.suit) == case["suit"]
        assert card.rank.pip_value == case["pip_value"]
        assert card.rank.is_court == case["is_court"]
        assert card.rank.counts_for_set == case["counts_for_set"]


def test_the_ace_of_spades_sits_on_bit_thirty_one(vec):
    """The hazard §2.1 called the sneakiest, pinned so it cannot go unnoticed.

    In JavaScript a hand holding this card reads as -2147483648. In Rust it is
    a `u32` and the question does not arise -- but it is the vector that proves
    which of those a given port did, rather than the port's own say-so.
    """
    ace = next(c for c in vec["pack"] if c["code"] == "AS")
    assert ace["index"] == 31
    assert Hand.of(Card.parse("AS")).bits == 2**31


# -- reading cards and hands from text --------------------------------------


def test_parsing_is_forgiving_in_the_documented_ways(vec):
    for case in vec["parse"]:
        assert Card.parse(case["text"]).code == case["code"]


def test_hands_have_the_recorded_mask_size_and_order(vec):
    """Iteration order is part of the contract, not an implementation detail.

    §2.2 notes that Python's sorts are stable and Rust's default sort is not;
    that only matters if the *input* order agrees first, and this is where it
    is fixed. A hand iterates by suit, then ascending rank.
    """
    for case in vec["hands"]:
        hand = parse_hand(case["code"])
        assert hand.bits == case["bits"]
        assert len(hand) == case["size"]
        assert [card.code for card in hand] == case["cards"]
        assert hand.code == " ".join(case["cards"])


def test_membership_matches_the_recorded_cards(vec):
    for case in vec["hands"]:
        hand = parse_hand(case["code"])
        held = set(case["cards"])
        for card in full_deck():
            assert (card in hand) is (card.code in held)


# -- suit views -------------------------------------------------------------


def test_suit_views_and_rank_counts(vec):
    for case in vec["suits"]:
        hand = parse_hand(case["hand"])
        suit = Suit(case["suit"])
        assert hand.in_suit(suit).code == case["in_suit"]
        assert [int(r) for r in hand.ranks_in(suit)] == case["ranks_in"]
        for entry in case["counts"]:
            assert hand.count_of(entry["rank"]) == entry["count"]


# -- set operations ---------------------------------------------------------


SET_OPS = {
    "sub": lambda a, b: a - b,
    "and": lambda a, b: a & b,
    "or": lambda a, b: a | b,
}


def test_set_operations(vec):
    for case in vec["set_ops"]:
        left, right = parse_hand(case["left"]), parse_hand(case["right"])
        assert SET_OPS[case["op"]](left, right).code == case["result"]


# -- the things that must fail ----------------------------------------------


ERROR_OPS = {
    "Card.parse": lambda a: Card.parse(a["text"]),
    "Card.from_index": lambda a: Card.from_index(a["index"]),
    "parse_hand": lambda a: parse_hand(a["text"]),
    "Hand.add": lambda a: parse_hand(a["hand"]).add(Card.parse(a["card"])),
    "Hand.remove": lambda a: parse_hand(a["hand"]).remove(Card.parse(a["card"])),
    "Hand.or": lambda a: parse_hand(a["left"]) | parse_hand(a["right"]),
}

EXCEPTIONS = {"ValueError": ValueError, "KeyError": KeyError}


def test_rejected_inputs_are_still_rejected(vec):
    """A port that accepts these is wrong in a way no happy-path vector catches.

    `Hand.__or__` is the interesting one: it refuses to merge overlapping hands
    rather than silently unioning them, because a card cannot be in two places
    and a quiet merge would hide a dealing bug.
    """
    for case in vec["errors"]:
        with pytest.raises(EXCEPTIONS[case["raises"]]):
            ERROR_OPS[case["op"]](case["args"])


# -- the vectors themselves --------------------------------------------------


def test_vector_file_is_self_describing(vec):
    assert vec["module"] == "cards"
    assert vec["generator"] == "tools/emit_vectors.py"
    for section in ("pack", "parse", "hands", "suits", "set_ops", "errors"):
        assert vec[section], f"section {section!r} is empty"


# ===========================================================================
# combos
# ===========================================================================


@pytest.fixture(scope="module")
def cvec() -> dict:
    return load("combos")


def test_holdings_detect_point_sequences_and_sets(cvec):
    from piquet.combos import (
        best_point,
        is_carte_blanche,
        score_sequences,
        score_sets,
        sequences,
        sets,
    )

    for case in cvec["holdings"]:
        hand = parse_hand(case["hand"])

        point = best_point(hand)
        if case["best_point"] is None:
            assert point is None
        else:
            expected = case["best_point"]
            assert int(point.suit) == expected["suit"]
            assert point.length == expected["length"]
            assert point.pip_value == expected["pip_value"]
            assert point.score == expected["score"]
            assert list(point.key) == expected["key"]

        found = sequences(hand)
        assert len(found) == len(case["sequences"])
        for got, want in zip(found, case["sequences"]):
            assert int(got.suit) == want["suit"]
            assert int(got.top) == want["top"]
            assert got.length == want["length"]
            assert got.score == want["score"]
            assert got.name == want["name"]

        held = sets(hand)
        assert len(held) == len(case["sets"])
        for got, want in zip(held, case["sets"]):
            assert int(got.rank) == want["rank"]
            assert got.count == want["count"]
            assert got.score == want["score"]

        assert score_sequences(hand) == case["score_sequences"]
        assert score_sets(hand) == case["score_sets"]
        assert is_carte_blanche(hand) is case["carte_blanche"]


def test_sequence_scoring_is_a_formula_not_a_table(cvec):
    """`docs/DESIGN.md` §3.8: the historical 3, 4, 15, 16, 17, 18 is a formula.

    Three and four score their length; from five the bonus of ten applies. A
    port that transcribes the numbers instead of the rule will be right about
    every sequence that exists and wrong about the reasoning, which matters
    because the tutor explains the rule to a learner.
    """
    from piquet.combos import Sequence
    from piquet.cards import Rank, Suit

    for case in cvec["sequence_scores"]:
        made = Sequence(suit=Suit.CLUBS, top=Rank.ACE, length=case["length"])
        assert made.score == case["score"]

    table = {c["length"]: c["score"] for c in cvec["sequence_scores"]}
    assert table == {3: 3, 4: 4, 5: 15, 6: 16, 7: 17, 8: 18}


def test_set_scoring(cvec):
    from piquet.combos import CardSet
    from piquet.cards import Rank

    for case in cvec["set_scores"]:
        assert CardSet(rank=Rank.ACE, count=case["count"]).score == case["score"]


def test_tied_sequences_keep_the_order_a_stable_sort_gives(cvec):
    """The §2.2 hazard, pinned as data rather than left as a warning.

    Two tierces to the king key identically at `(3, 13)`. Python's
    `sorted(..., reverse=True)` is stable, so the one found first -- the lower
    suit index -- stays first, and `best_sequence` is `found[0]`. A port that
    renders `reverse=True` as a sort followed by `.reverse()` inverts exactly
    these pairs and declares the other suit.
    """
    from piquet.combos import best_sequence, sequences

    for case in cvec["ties"]:
        hand = parse_hand(case["hand"])
        found = sequences(hand)
        assert [list(q.key) for q in found] == case["keys"]
        assert [
            {"suit": int(q.suit), "top": int(q.top)} for q in found
        ] == case["order"]
        assert int(best_sequence(hand).suit) == case["best_suit"]

        # The case is only doing its job while the keys genuinely collide.
        keys = [tuple(k) for k in case["keys"]]
        assert len(keys) != len(set(keys)), (
            f"{case['hand']!r} no longer produces a tie, so it no longer tests "
            f"sort stability; replace it with a hand that does"
        )


def test_comparisons_between_holdings(cvec):
    from piquet.combos import (
        best_point,
        best_sequence,
        best_set,
        compare_point,
        compare_sequence,
        compare_set,
    )

    for case in cvec["comparisons"]:
        a, b = parse_hand(case["left"]), parse_hand(case["right"])
        assert compare_point(best_point(a), best_point(b)).value == case["point"]
        assert (
            compare_sequence(best_sequence(a), best_sequence(b)).value
            == case["sequence"]
        )
        assert compare_set(best_set(a), best_set(b)).value == case["set"]


def test_understated_claims_are_supported_or_not(cvec):
    """Sinking depends on this: a smaller claim must still be true of the hand."""
    from piquet.cards import Rank, Suit
    from piquet.combos import CardSet, Point, Sequence

    for case in cvec["support"]:
        hand, claim = parse_hand(case["hand"]), case["claim"]
        if case["kind"] == "point":
            obj = Point(Suit(claim["suit"]), claim["length"], claim["pip_value"])
        elif case["kind"] == "sequence":
            obj = Sequence(Suit(claim["suit"]), Rank(claim["top"]), claim["length"])
        else:
            obj = CardSet(Rank(claim["rank"]), claim["count"])
        assert obj.is_supported_by(hand) is case["supported"]


def test_combos_vector_file_is_self_describing(cvec):
    assert cvec["module"] == "combos"
    for section in (
        "holdings",
        "sequence_scores",
        "set_scores",
        "ties",
        "comparisons",
        "support",
    ):
        assert cvec[section], f"section {section!r} is empty"


# ===========================================================================
# scoring
# ===========================================================================


@pytest.fixture(scope="module")
def svec() -> dict:
    return load("scoring")


def _rebuild(events: list) -> object:
    from piquet.scoring import Category, Player, ScoreLog

    players = {"elder": Player.ELDER, "younger": Player.YOUNGER}
    log = ScoreLog()
    for who, amount, category, detail in events:
        log = log.record(players[who], amount, Category[category], detail)
    return log


def test_category_values_are_the_reckoning_order(svec):
    """Law 67's precedence is carried by the integers, not by the names.

    A port is free to rename these, but `CARTE_BLANCHE` must be 1 and `PLAY`
    must be 5, because both bonuses are derived by walking the categories in
    numeric order. Renumbering them silently changes which bonus is awarded.
    """
    from piquet.scoring import Category

    for case in svec["categories"]:
        assert int(Category[case["name"]]) == case["value"]
    values = [c["value"] for c in svec["categories"]]
    assert values == sorted(values), "the listing must be in precedence order"


def test_the_two_bonuses_read_different_category_sets(svec):
    """Repique is "in his hand alone"; pique is "in hand and play".

    The difference is exactly one category, and the cards are excluded from
    both -- "a capot reckons after points made in play; and, therefore, does
    not count toward a pique" (Cavendish, Law 69).
    """
    from piquet.scoring import DECLARATION_CATEGORIES, PIQUE_CATEGORIES

    assert [c.name for c in DECLARATION_CATEGORIES] == svec["declaration_categories"]
    assert [c.name for c in PIQUE_CATEGORIES] == svec["pique_categories"]
    assert set(svec["pique_categories"]) - set(svec["declaration_categories"]) == {
        "PLAY"
    }
    assert "CARDS" not in svec["pique_categories"]


def test_constants(svec):
    from piquet.scoring import PIQUE_BONUS, PIQUE_THRESHOLD, REPIQUE_BONUS

    assert svec["constants"] == {
        "PIQUE_THRESHOLD": PIQUE_THRESHOLD,
        "PIQUE_BONUS": PIQUE_BONUS,
        "REPIQUE_BONUS": REPIQUE_BONUS,
    }


def test_every_logged_case_reckons_as_recorded(svec):
    from piquet.scoring import Player

    for case in svec["cases"]:
        log = _rebuild(case["events"])
        where = case["name"]

        assert log.total(Player.ELDER) == case["totals"]["elder"], where
        assert log.total(Player.YOUNGER) == case["totals"]["younger"], where

        for who, player in (("elder", Player.ELDER), ("younger", Player.YOUNGER)):
            got = {c.name: n for c, n in log.by_category(player).items()}
            assert got == case["by_category"][who], where

        got_repique = log.repique.value if log.repique else None
        got_pique = log.pique.value if log.pique else None
        assert got_repique == case["repique"], where
        assert got_pique == case["pique"], where

        settled = log.with_bonuses()
        assert settled.total(Player.ELDER) == case["totals_after_bonuses"]["elder"], where
        assert (
            settled.total(Player.YOUNGER) == case["totals_after_bonuses"]["younger"]
        ), where


def test_a_player_never_scores_both_bonuses(svec):
    for case in svec["cases"]:
        assert not (case["repique"] and case["pique"]), case["name"]


def test_younger_cannot_pique(svec):
    """Not stipulated anywhere -- it falls out of the precedence order.

    Younger's declarations are categories I-IV. If they reach thirty while
    elder is silent she has a *repique*. To need points made in play she must
    be short after declaring, and by then the first entry in category V is
    elder's point for leading to the first trick -- so he has reckoned, and the
    window is shut.
    """
    for case in svec["cases"]:
        assert case["pique"] != "younger", case["name"]


def test_with_bonuses_is_idempotent(svec):
    for case in svec["cases"]:
        log = _rebuild(case["events"])
        once = log.with_bonuses()
        assert len(once.with_bonuses()) == len(once), case["name"]


def test_a_score_must_be_positive(svec):
    """An equality scores for neither player and is recorded by logging nothing.

    A zero would look exactly like the adversary having reckoned something,
    which silently breaks both bonuses -- so it is refused rather than ignored.
    """
    from piquet.scoring import Category, Player, ScoreLog

    for case in svec["errors"]:
        with pytest.raises(ValueError):
            ScoreLog().record(Player.ELDER, case["amount"], Category.POINT)


def test_scoring_vector_file_is_self_describing(svec):
    assert svec["module"] == "scoring"
    for section in ("categories", "cases", "errors", "constants"):
        assert svec[section], f"section {section!r} is empty"
