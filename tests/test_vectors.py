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
