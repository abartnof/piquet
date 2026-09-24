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
from piquet.combos import (  # noqa: E402
    best_point,
    best_sequence,
    best_set,
    compare_point,
    compare_sequence,
    compare_set,
    is_carte_blanche,
    score_sequences,
    score_sets,
    sequences,
    sets,
)

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


# Hands chosen to exercise the rules rather than to look like real deals.
COMBO_HANDS = [
    "",
    "AS KS QS JS TS 9S 8S 7S",
    "AC KD QH JS TC 9D 8H 7S",
    "JH QH KH JS QS KS",
    "AC KC QC 9C 8C 7C",
    "AC AD AH AS KC KD KH KS QC QD QH",
    "TC TD TH TS 9C 9D 9H 9S",
    "AC AD TH TS 9C 8D 7H 9S",
    "AC KC QC JC TC 9C 8C 7C AD KD QD JD",
]

# Two tierces to the king, both keying (3, 13). Which one `best_sequence`
# returns is decided purely by sort stability, so it is pinned deliberately.
TIE_HANDS = [
    "JH QH KH JS QS KS",
    "9C TC JC 9D TD JD",
    "AC KC QC AD KD QD",
]

COMPARE_PAIRS = [
    ("AC KC QC JC TC", "AD KD QD JD 9D"),
    ("AC KC QC JC TC", "AD KD QD JD TD"),
    ("AC KC QC", "AD KD QD JD"),
    ("", "AD KD QD"),
    ("", ""),
    ("AC AD AH AS", "KC KD KH KS"),
    ("AC AD AH", "KC KD KH KS"),
    ("TC TD TH TS", "AC AD AH"),
]

# Understatement -- the mechanism behind sinking. A claim smaller than what is
# held must still be supported by the hand.
SUPPORT_CASES = [
    ("point", "AC KC QC JC TC", {"suit": 0, "length": 5, "pip_value": 51}, True),
    ("point", "AC KC QC JC TC", {"suit": 0, "length": 4, "pip_value": 41}, True),
    ("point", "AC KC QC JC TC", {"suit": 0, "length": 4, "pip_value": 40}, False),
    ("point", "AC KC QC JC TC", {"suit": 1, "length": 3, "pip_value": 30}, False),
    ("sequence", "AC KC QC JC", {"suit": 0, "top": 14, "length": 4}, True),
    ("sequence", "AC KC QC JC", {"suit": 0, "top": 13, "length": 3}, True),
    ("sequence", "AC KC QC JC", {"suit": 0, "top": 14, "length": 5}, False),
    ("sequence", "AC KC QC JC", {"suit": 0, "top": 14, "length": 2}, False),
    ("set", "AC AD AH AS", {"rank": 14, "count": 4}, True),
    ("set", "AC AD AH AS", {"rank": 14, "count": 3}, True),
    ("set", "AC AD AH", {"rank": 14, "count": 4}, False),
    ("set", "9C 9D 9H 9S", {"rank": 9, "count": 4}, False),
]


def _point(p) -> dict | None:
    if p is None:
        return None
    return {
        "suit": int(p.suit),
        "length": p.length,
        "pip_value": p.pip_value,
        "score": p.score,
        "key": list(p.key),
    }


def _sequence(q) -> dict:
    return {
        "suit": int(q.suit),
        "top": int(q.top),
        "length": q.length,
        "score": q.score,
        "name": q.name,
        "key": list(q.key),
    }


def _set(c) -> dict:
    return {
        "rank": int(c.rank),
        "count": c.count,
        "score": c.score,
        "name": c.name,
        "key": list(c.key),
    }


def emit_combos() -> dict:
    from piquet.combos import CardSet, Point, Sequence

    holdings = []
    for code in COMBO_HANDS:
        hand = parse_hand(code)
        holdings.append(
            {
                "hand": code,
                "best_point": _point(best_point(hand)),
                "sequences": [_sequence(q) for q in sequences(hand)],
                "sets": [_set(c) for c in sets(hand)],
                "score_sequences": score_sequences(hand),
                "score_sets": score_sets(hand),
                "carte_blanche": is_carte_blanche(hand),
            }
        )

    # docs/DESIGN.md 3.8: the historical table 3, 4, 15, 16, 17, 18 is a
    # formula, not an arbitrary list. Pinned so a port cannot transcribe it.
    sequence_scores = [
        {"length": n, "score": Sequence(suit=Suit.CLUBS, top=Rank.ACE, length=n).score}
        for n in range(3, 9)
    ]
    set_scores = [
        {"count": n, "score": CardSet(rank=Rank.ACE, count=n).score} for n in (3, 4)
    ]

    ties = []
    for code in TIE_HANDS:
        hand = parse_hand(code)
        found = sequences(hand)
        ties.append(
            {
                "hand": code,
                "note": "equal keys; order is decided by a STABLE sort",
                "keys": [list(q.key) for q in found],
                "order": [{"suit": int(q.suit), "top": int(q.top)} for q in found],
                "best_suit": int(best_sequence(hand).suit),
            }
        )

    comparisons = []
    for left, right in COMPARE_PAIRS:
        a, b = parse_hand(left), parse_hand(right)
        comparisons.append(
            {
                "left": left,
                "right": right,
                "point": compare_point(best_point(a), best_point(b)).value,
                "sequence": compare_sequence(best_sequence(a), best_sequence(b)).value,
                "set": compare_set(best_set(a), best_set(b)).value,
            }
        )

    support = []
    for kind, code, claim, expected in SUPPORT_CASES:
        hand = parse_hand(code)
        if kind == "point":
            obj = Point(Suit(claim["suit"]), claim["length"], claim["pip_value"])
        elif kind == "sequence":
            obj = Sequence(Suit(claim["suit"]), Rank(claim["top"]), claim["length"])
        else:
            obj = CardSet(Rank(claim["rank"]), claim["count"])
        actual = obj.is_supported_by(hand)
        if actual != expected:
            raise SystemExit(f"support case wrong: {kind} {code} {claim} -> {actual}")
        support.append({"kind": kind, "hand": code, "claim": claim, "supported": actual})

    return {
        "module": "combos",
        "generator": "tools/emit_vectors.py",
        "note": (
            "Point, sequence and set: detection, ordering, scoring and "
            "comparison. Sequence and set scores are formulas rather than "
            "tables (docs/DESIGN.md 3.8), and the `ties` section pins an "
            "ordering that only a stable sort reproduces."
        ),
        "holdings": holdings,
        "sequence_scores": sequence_scores,
        "set_scores": set_scores,
        "ties": ties,
        "comparisons": comparisons,
        "support": support,
    }


def main() -> int:
    VECTORS.mkdir(exist_ok=True)
    for name, build in (("cards", emit_cards), ("combos", emit_combos)):
        path = VECTORS / f"{name}.json"
        path.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {path.relative_to(VECTORS.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
