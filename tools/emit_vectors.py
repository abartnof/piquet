#!/usr/bin/env python3
"""Generate the golden JSON vectors from the Python engine.

The Python implementation is the **oracle**: it is the version that passes 447
tests, so what it computes is, by definition, what the Rust port must compute.
This script freezes a representative slice of that behaviour into `vectors/`,
where both languages can read it.

Run it when the engine's behaviour changes *on purpose*:

    python tools/emit_vectors.py

Then look at the diff. A changed vector is either a deliberate rule change or a
regression, and `tests/test_vectors.py` exists to make sure the difference is
never silent.

Two rules, both from `docs/DESIGN.md` §2.1. **Never write a seed** -- no two
languages share a random number generator, so cases are written against
explicit inputs. **Prefer integers to floats** -- where a float is unavoidable
the vector carries a tolerance instead of an exact value. Neither rule is
exercised by `cards`, which is entirely integral and has no randomness at all;
both start to bite from `chances` onward.

The generator checks its own output as it goes. Cases that are supposed to
raise are executed here too, so a vector claiming `ValueError` cannot be
committed unless it genuinely raises one.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from piquet.cards import Card, Hand, Rank, Suit, full_deck, parse_hand  # noqa: E402

VECTORS = pathlib.Path(__file__).resolve().parents[1] / "vectors"

# Hands chosen for what they prove, not for realism. The single ace of spades
# is the §2.1 sign-bit hazard; the full pack is the unsigned boundary at
# 0xFFFFFFFF; the lone seven of clubs is bit zero. The rest are ordinary.
HANDS = [
    "",
    "7C",
    "AS",
    "AS 7C",
    "AS KS QS JS TS 9S 8S 7S",
    "AC KD QH JS TC 9D 8H 7S",
    "AC KC QC JC TC 9C 8C 7C AD KD QD JD",
    " ".join(card.code for card in full_deck()),
]

PARSE_CASES = ["7C", "TS", "10S", "ts", "10s", "AS", "as", "A♠", " AS ", "K♦"]

SUIT_CASES = [
    ("AC KD QH JS TC 9D 8H 7S", Suit.CLUBS),
    ("AC KD QH JS TC 9D 8H 7S", Suit.SPADES),
    ("AS KS QS JS TS 9S 8S 7S", Suit.SPADES),
    ("AS KS QS JS TS 9S 8S 7S", Suit.HEARTS),
    ("AC AD AH AS KC KD", Suit.DIAMONDS),
]

SET_OPS = [
    ("sub", "AC KD QH JS", "KD JS"),
    ("sub", "AC KD QH JS", ""),
    ("sub", "AC KD", "AC KD"),
    ("and", "AC KD QH JS", "KD JS 7C"),
    ("and", "AC KD", "QH JS"),
    ("or", "AC KD", "QH JS"),
    ("or", "", "AS"),
]

ERRORS = [
    ("Card.parse", {"text": "ZZ"}, "ValueError"),
    ("Card.parse", {"text": "2S"}, "ValueError"),
    ("Card.parse", {"text": "6H"}, "ValueError"),
    ("Card.parse", {"text": "AX"}, "ValueError"),
    ("Card.parse", {"text": "A"}, "ValueError"),
    ("Card.parse", {"text": ""}, "ValueError"),
    ("Card.from_index", {"index": 32}, "ValueError"),
    ("Card.from_index", {"index": -1}, "ValueError"),
    ("parse_hand", {"text": "AS AS"}, "ValueError"),
    ("Hand.add", {"hand": "AS KS", "card": "AS"}, "KeyError"),
    ("Hand.remove", {"hand": "AS KS", "card": "QS"}, "KeyError"),
    ("Hand.or", {"left": "AS KS", "right": "KS QS"}, "KeyError"),
]

ERROR_OPS = {
    "Card.parse": lambda a: Card.parse(a["text"]),
    "Card.from_index": lambda a: Card.from_index(a["index"]),
    "parse_hand": lambda a: parse_hand(a["text"]),
    "Hand.add": lambda a: parse_hand(a["hand"]).add(Card.parse(a["card"])),
    "Hand.remove": lambda a: parse_hand(a["hand"]).remove(Card.parse(a["card"])),
    "Hand.or": lambda a: parse_hand(a["left"]) | parse_hand(a["right"]),
}

OPS = {
    "sub": lambda a, b: a - b,
    "and": lambda a, b: a & b,
    "or": lambda a, b: a | b,
}


def emit_cards() -> dict:
    pack = [
        {
            "index": card.index,
            "code": card.code,
            "rank": int(card.rank),
            "suit": int(card.suit),
            "pip_value": card.rank.pip_value,
            "is_court": card.rank.is_court,
            "counts_for_set": card.rank.counts_for_set,
        }
        for card in full_deck()
    ]

    hands = []
    for code in HANDS:
        hand = parse_hand(code)
        hands.append(
            {
                "code": hand.code,
                "bits": hand.bits,
                "size": len(hand),
                "cards": [card.code for card in hand],
            }
        )

    suits = []
    for code, suit in SUIT_CASES:
        hand = parse_hand(code)
        suits.append(
            {
                "hand": code,
                "suit": int(suit),
                "in_suit": hand.in_suit(suit).code,
                "ranks_in": [int(rank) for rank in hand.ranks_in(suit)],
                "counts": [
                    {"rank": int(rank), "count": hand.count_of(rank)} for rank in Rank
                ],
            }
        )

    set_ops = []
    for op, left, right in SET_OPS:
        result = OPS[op](parse_hand(left), parse_hand(right))
        set_ops.append({"op": op, "left": left, "right": right, "result": result.code})

    errors = []
    for op, args, raises in ERRORS:
        try:
            ERROR_OPS[op](args)
        except (ValueError, KeyError) as exc:
            actual = type(exc).__name__
            if actual != raises:
                raise SystemExit(f"{op}{args} raised {actual}, vector says {raises}")
        else:
            raise SystemExit(f"{op}{args} did not raise; vector claims {raises}")
        errors.append({"op": op, "args": args, "raises": raises})

    return {
        "module": "cards",
        "generator": "tools/emit_vectors.py",
        "note": (
            "The 32-card piquet pack. Bit masks are JSON numbers: a 32-bit mask "
            "reaches 2**31, well inside the 2**53 a double holds exactly. Wider "
            "keys must travel as decimal strings."
        ),
        "pack": pack,
        "parse": [{"text": t, "code": Card.parse(t).code} for t in PARSE_CASES],
        "hands": hands,
        "suits": suits,
        "set_ops": set_ops,
        "errors": errors,
    }


def main() -> int:
    VECTORS.mkdir(exist_ok=True)
    for name, build in (("cards", emit_cards),):
        path = VECTORS / f"{name}.json"
        path.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {path.relative_to(VECTORS.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
