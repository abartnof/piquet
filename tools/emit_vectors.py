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
from piquet.observation import View, view_for  # noqa: E402
from piquet.partie import (  # noqa: E402
    DEALS_IN_PARTIE,
    EXTRA_DEALS,
    PARTIE_BONUS,
    RUBICON,
    Partie,
    Side,
    Standing,
)
from piquet.rules import (  # noqa: E402
    CARDS_SCORE,
    CAPOT_SCORE,
    CARTE_BLANCHE_SCORE,
    ELDER_MAX_EXCHANGE,
    HAND_SIZE,
    TALON_SIZE,
    TRICKS_PER_DEAL,
    Deal,
    Phase,
    Trick,
    deal_from,
)
from piquet.declarations import (  # noqa: E402
    Announcement,
    CategoryResult,
    Declaration,
    compare_in,
)
from piquet.style import BALANCED, CALIBRATED, Style  # noqa: E402
from piquet.scoring import (  # noqa: E402
    DECLARATION_CATEGORIES,
    PIQUE_BONUS,
    PIQUE_CATEGORIES,
    PIQUE_THRESHOLD,
    REPIQUE_BONUS,
    Category,
    Player,
    ScoreLog,
)
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


# Each case is a log written as [player, amount, category, detail], in the
# order the events were entered -- which is deliberately *not* the order they
# reckon in. Younger's declarations are entered only once elder has led to the
# first trick, yet they reckon in categories II-IV, ahead of his play. Getting
# those two orders confused awarded a pique that was not due in one deal in
# 250, which is why these cases exist at all.
SCORE_CASES = [
    {
        "name": "elder repique, exactly thirty in hand",
        "events": [
            ["elder", 10, "CARTE_BLANCHE", "carte blanche"],
            ["elder", 5, "POINT", "point of five"],
            ["elder", 15, "SEQUENCES", "quint"],
        ],
    },
    {
        "name": "twenty-nine in hand is not a repique, but reaches a pique",
        "events": [
            ["elder", 5, "POINT", "point of five"],
            ["elder", 21, "SEQUENCES", "quint and tierce"],
            ["elder", 3, "SETS", "trio of kings"],
            ["elder", 1, "PLAY", "leading"],
        ],
    },
    {
        "name": "elder pique, made in hand and play",
        "events": [
            ["elder", 5, "POINT", "point of five"],
            ["elder", 15, "SEQUENCES", "quint"],
            ["elder", 3, "SETS", "trio"],
            ["elder", 7, "PLAY", "tricks"],
        ],
    },
    {
        "name": "younger repiques; elder leading first is category V and cannot block her",
        "events": [
            ["elder", 1, "PLAY", "leading to the first trick"],
            ["younger", 5, "POINT", "point of five"],
            ["younger", 17, "SEQUENCES", "septieme"],
            ["younger", 14, "SETS", "quatorze of aces"],
        ],
    },
    {
        "name": "younger cannot pique: elder's lead reckons before her play",
        "events": [
            ["younger", 5, "POINT", "point of five"],
            ["younger", 15, "SEQUENCES", "quint"],
            ["younger", 3, "SETS", "trio"],
            ["elder", 1, "PLAY", "leading to the first trick"],
            ["younger", 7, "PLAY", "tricks"],
        ],
    },
    {
        "name": "a capot does not count towards a pique (Cavendish, law 69)",
        "events": [
            ["elder", 5, "POINT", "point of five"],
            ["elder", 17, "SEQUENCES", "septieme"],
            ["elder", 3, "SETS", "trio"],
            ["elder", 4, "PLAY", "tricks"],
            ["elder", 40, "CARDS", "capot"],
        ],
    },
    {
        "name": "both players reckon, so neither bonus is available",
        "events": [
            ["elder", 5, "POINT", "point of five"],
            ["younger", 4, "SEQUENCES", "quart"],
            ["elder", 30, "SETS", "two quatorzes"],
        ],
    },
    {
        "name": "an empty log scores nothing and awards nothing",
        "events": [],
    },
]

BAD_SCORES = [0, -1, -30]


def emit_scoring() -> dict:
    players = {"elder": Player.ELDER, "younger": Player.YOUNGER}

    cases = []
    for case in SCORE_CASES:
        log = ScoreLog()
        for who, amount, category, detail in case["events"]:
            log = log.record(players[who], amount, Category[category], detail)

        settled = log.with_bonuses()
        if len(settled.with_bonuses()) != len(settled):
            raise SystemExit(f"with_bonuses is not idempotent for {case['name']!r}")

        cases.append(
            {
                "name": case["name"],
                "events": case["events"],
                "totals": {
                    "elder": log.total(Player.ELDER),
                    "younger": log.total(Player.YOUNGER),
                },
                "by_category": {
                    who: {c.name: n for c, n in log.by_category(p).items()}
                    for who, p in players.items()
                },
                "repique": log.repique.value if log.repique else None,
                "pique": log.pique.value if log.pique else None,
                "totals_after_bonuses": {
                    "elder": settled.total(Player.ELDER),
                    "younger": settled.total(Player.YOUNGER),
                },
            }
        )

    errors = []
    for amount in BAD_SCORES:
        try:
            ScoreLog().record(Player.ELDER, amount, Category.POINT)
        except ValueError:
            errors.append({"amount": amount, "raises": "ValueError"})
        else:
            raise SystemExit(f"recording {amount} did not raise")

    return {
        "module": "scoring",
        "generator": "tools/emit_vectors.py",
        "note": (
            "The event log, and Law 67's order of precedence. Category values "
            "ARE the reckoning order, so a port must keep the numbers, not "
            "merely the names. The events in each case are listed in the order "
            "they were entered, which is not the order they reckon in."
        ),
        "constants": {
            "PIQUE_THRESHOLD": PIQUE_THRESHOLD,
            "PIQUE_BONUS": PIQUE_BONUS,
            "REPIQUE_BONUS": REPIQUE_BONUS,
        },
        "categories": [{"name": c.name, "value": int(c)} for c in Category],
        "declaration_categories": [c.name for c in DECLARATION_CATEGORIES],
        "pique_categories": [c.name for c in PIQUE_CATEGORIES],
        "cases": cases,
        "errors": errors,
    }


# Styles chosen to sit unambiguously inside a band rather than on its edge.
# `describe` divides by the calibrated span, so an exact boundary value is a
# float comparison across two languages -- precisely the thing 2.1 says to
# avoid pinning. The bands themselves are recorded instead, so a port can check
# its own arithmetic against them.
STYLE_CASES = [
    {"discard_boldness": 0.50, "sinking": 0.00, "guard_retention": 0.50},
    {"discard_boldness": 0.36, "sinking": 0.01, "guard_retention": 0.36},
    {"discard_boldness": 0.64, "sinking": 0.09, "guard_retention": 0.64},
    {"discard_boldness": 0.40, "sinking": 0.05, "guard_retention": 0.60},
    {"discard_boldness": 0.60, "sinking": 0.02, "guard_retention": 0.40},
]

BAD_STYLES = [
    {"discard_boldness": -0.1},
    {"discard_boldness": 1.1},
    {"sinking": 2.0},
    {"guard_retention": -0.0001},
]

# elder hand, younger hand, category
DIALOGUE_CASES = [
    ("AC KC QC JC TC 9C 8C 7C", "AD KD QD JD TD 9D 8D", "POINT"),
    ("AC KC QC JC TC", "AD KD QD JD TD", "POINT"),
    ("AC KC QC JC TC", "AD KD QD JD 9D", "POINT"),
    ("AC KC QC JC", "AD KD QD", "SEQUENCES"),
    ("AC KC QC", "AD KD QD", "SEQUENCES"),
    ("AC AD AH AS", "KC KD KH KS", "SETS"),
    ("AC AD AH", "KC KD KH KS", "SETS"),
    ("7C 8C 9C", "AD KD QD JD", "SEQUENCES"),
    # Elder sinks: announces nothing at all, conceding the category to buy
    # silence. Younger still wins it, so she announces and shows normally --
    # which is the part that is easy to get wrong by hand.
    ("AC KC QC JC", "AD KD QD", "SEQUENCES", "sink"),
]

VALIDATE_CASES = [
    ("wrong category", "AC KC QC JC TC", "POINT", "sequence"),
    ("not held", "AC KC QC JC TC", "POINT", "unheld_point"),
    ("two points", "AC KC QC JC TC", "POINT", "two_points"),
    ("overlapping sequences", "AC KC QC JC TC", "SEQUENCES", "overlap"),
    ("two sets of one rank", "AC AD AH AS", "SETS", "duplicate_rank"),
]


def emit_style() -> dict:
    styles = []
    for fields in STYLE_CASES:
        st = Style(**fields)
        styles.append({**fields, "describe": st.describe()})

    errors = []
    for fields in BAD_STYLES:
        try:
            Style(**fields)
        except ValueError:
            errors.append({"fields": fields, "raises": "ValueError"})
        else:
            raise SystemExit(f"Style({fields}) did not raise")

    return {
        "module": "style",
        "generator": "tools/emit_vectors.py",
        "note": (
            "The third axis, orthogonal to skill and erraticism. The CALIBRATED "
            "bands are measured, not chosen: each is narrow enough that an "
            "extreme setting costs under about a point a deal, which is what "
            "keeps style from becoming a skill dial. Re-measure them whenever "
            "the ladder moves. `describe` reads a style RELATIVE to its band, "
            "because on the raw 0-1 scale every opponent would read as neutral."
        ),
        "calibrated": {k: list(v) for k, v in CALIBRATED.items()},
        "balanced": {
            "discard_boldness": BALANCED.discard_boldness,
            "sinking": BALANCED.sinking,
            "guard_retention": BALANCED.guard_retention,
        },
        "styles": styles,
        "errors": errors,
    }


def _claim(obj) -> dict:
    from piquet.combos import CardSet, Point, Sequence

    if isinstance(obj, Point):
        return {"kind": "point", **_point(obj)}
    if isinstance(obj, Sequence):
        return {"kind": "sequence", **_sequence(obj)}
    if isinstance(obj, CardSet):
        return {"kind": "set", **_set(obj)}
    raise TypeError(obj)


def _announcement(a) -> dict | None:
    if a is None:
        return None
    return {
        "category": a.category.name,
        "primary": a.primary,
        "tiebreak": a.tiebreak,
        "spoken": str(a),
    }


def emit_declarations() -> dict:
    from piquet.combos import CardSet, Point, Sequence
    from piquet.cards import Rank as R, Suit as S

    dialogue = []
    for case in DIALOGUE_CASES:
        elder_code, younger_code, cat_name = case[:3]
        elder_sinks = len(case) > 3 and case[3] == "sink"
        category = Category[cat_name]
        eh, yh = parse_hand(elder_code), parse_hand(younger_code)
        ed = Declaration.sink() if elder_sinks else Declaration.full(eh, category)
        yd = Declaration.full(yh, category)
        ed.validate(eh, category)
        yd.validate(yh, category)
        comparison = compare_in(category, ed.best, yd.best)
        result = CategoryResult(category, ed, yd, comparison)

        dialogue.append(
            {
                "category": cat_name,
                "elder_hand": elder_code,
                "younger_hand": younger_code,
                "elder_sinks": elder_sinks,
                "elder_declares": str(ed),
                "elder_score_if_won": ed.score,
                "younger_score_if_won": yd.score,
                "comparison": comparison.value,
                "response": result.response,
                "winner": result.winner.value if result.winner else None,
                "shapes_match": result.shapes_match,
                # The information discipline: what each side actually learns.
                "announced": {
                    "elder": _announcement(result.announcement_of(Player.ELDER)),
                    "younger": _announcement(result.announcement_of(Player.YOUNGER)),
                },
                "shown": {
                    "elder": [_claim(c) for c in result.shown(Player.ELDER)],
                    "younger": [_claim(c) for c in result.shown(Player.YOUNGER)],
                },
            }
        )

    # `matches` reads only the sort key, and an announcement carries no suit.
    match_cases = []
    for primary, tiebreak, hand_code, cat_name in [
        (5, 51, "AC KC QC JC TC", "POINT"),
        (5, 51, "AS KS QS JS TS", "POINT"),
        (5, 50, "AC KC QC JC TC", "POINT"),
        (5, None, "AS KS QS JS TS", "POINT"),
        (4, None, "AC KC QC JC TC", "POINT"),
        (3, 13, "JH QH KH", "SEQUENCES"),
        (3, 13, "JS QS KS", "SEQUENCES"),
    ]:
        category = Category[cat_name]
        announcement = Announcement(category, primary, tiebreak)
        best = Declaration.full(parse_hand(hand_code), category).best
        match_cases.append(
            {
                "announcement": {
                    "category": cat_name,
                    "primary": primary,
                    "tiebreak": tiebreak,
                },
                "hand": hand_code,
                "matches": announcement.matches(best),
            }
        )

    builders = {
        "sequence": lambda: (Sequence(S.CLUBS, R.ACE, 5),),
        "unheld_point": lambda: (Point(S.DIAMONDS, 3, 30),),
        "two_points": lambda: (Point(S.CLUBS, 5, 51), Point(S.CLUBS, 4, 41)),
        "overlap": lambda: (
            Sequence(S.CLUBS, R.ACE, 5),
            Sequence(S.CLUBS, R.KING, 4),
        ),
        "duplicate_rank": lambda: (CardSet(R.ACE, 4), CardSet(R.ACE, 3)),
    }
    validate = []
    for name, hand_code, cat_name, builder in VALIDATE_CASES:
        category = Category[cat_name]
        declaration = Declaration(builders[builder]())
        try:
            declaration.validate(parse_hand(hand_code), category)
        except ValueError:
            pass
        else:
            raise SystemExit(f"validate case {name!r} did not raise")
        validate.append(
            {
                "name": name,
                "hand": hand_code,
                "category": cat_name,
                "claims": [_claim(c) for c in declaration.claims],
                "raises": "ValueError",
            }
        )

    return {
        "module": "declarations",
        "generator": "tools/emit_vectors.py",
        "note": (
            "The dialogue layer, and the information discipline that goes with "
            "it. The suit is never spoken; a tie-break is spoken only when the "
            "shapes match, and only by elder; and a declaration that was beaten "
            "scores nothing and is never shown -- so the loser of a category "
            "gives away its shape but not its cards."
        ),
        "dialogue": dialogue,
        "matches": match_cases,
        "validate": validate,
    }


# Packs are written out in full and never drawn from a seed: no two languages
# share a random number generator, so `deal_from` is the only honest entry
# point for a fixture (docs/DESIGN.md 2.1).
def _pack_identity() -> list[str]:
    return [c.code for c in full_deck()]


def _pack_reversed() -> list[str]:
    return [c.code for c in reversed(full_deck())]


def _pack_carte_blanche() -> list[str]:
    """Elder holds no jack, queen or king, so the deal opens with ten points.

    Twenty of the thirty-two cards are non-court, so a twelve-card hand without
    one is perfectly constructible -- it is just rare, about one hand in 1,792.
    """
    plain = [c for c in full_deck() if not c.rank.is_court]
    courts = [c for c in full_deck() if c.rank.is_court]
    ordered = plain[:HAND_SIZE] + courts + plain[HAND_SIZE:]
    assert len(ordered) == 32
    return [c.code for c in ordered]


REPLAY_PACKS = [
    ("the pack in index order", _pack_identity),
    ("the pack reversed", _pack_reversed),
    ("elder is dealt a carte blanche", _pack_carte_blanche),
]


def _state(deal: Deal) -> dict:
    return {
        "phase": deal.phase.value,
        "elder_hand": deal.hand_of(Player.ELDER).code,
        "younger_hand": deal.hand_of(Player.YOUNGER).code,
        "talon_taken": deal.talon_taken,
        "talon_remaining": deal.talon_remaining,
        "elder_total": deal.log.total(Player.ELDER),
        "younger_total": deal.log.total(Player.YOUNGER),
        "elder_tricks": deal.tricks_won(Player.ELDER),
        "younger_tricks": deal.tricks_won(Player.YOUNGER),
    }


def _script(pack_codes: list[str]) -> dict:
    """Play a whole deal under a policy with no choices left in it.

    Discard the first cards in hand order, declare everything, play the lowest
    legal card. The policy is not good piquet -- it is not meant to be. It is
    meant to be reproducible in any language without agreeing on a random
    number generator or on what a good move is.
    """
    deal = deal_from([Card.parse(c) for c in pack_codes])
    steps = [{"action": "deal", "after": _state(deal)}]

    for player in (Player.ELDER, Player.YOUNGER):
        limit = deal.exchange_limit(player)
        discard = Hand.of(*list(deal.hand_of(player))[:limit])
        deal = deal.exchange(player, discard)
        steps.append(
            {
                "action": "exchange",
                "player": player.value,
                "discard": discard.code,
                "after": _state(deal),
            }
        )

    while deal.phase in (
        Phase.DECLARE_POINT,
        Phase.DECLARE_SEQUENCES,
        Phase.DECLARE_SETS,
    ):
        category = deal.declaring_category
        player = deal.to_declare
        declaration = Declaration.full(deal.hand_of(player), category)
        deal = deal.declare(player, declaration)
        steps.append(
            {
                "action": "declare",
                "player": player.value,
                "category": category.name,
                "says": str(declaration),
                "after": _state(deal),
            }
        )

    while deal.phase is Phase.PLAY:
        player = deal.to_play
        card = next(iter(deal.legal_plays(player)))
        deal = deal.play(player, card)
        steps.append(
            {
                "action": "play",
                "player": player.value,
                "card": card.code,
                "after": _state(deal),
            }
        )

    return {
        "pack": pack_codes,
        "steps": steps,
        "final": {
            **_state(deal),
            "repique": deal.log.repique.value if deal.log.repique else None,
            "pique": deal.log.pique.value if deal.log.pique else None,
            "events": [
                {
                    "player": e.player.value,
                    "amount": e.amount,
                    "category": e.category.name,
                    "detail": e.detail,
                }
                for e in deal.log
            ],
        },
    }


TRICK_CASES = [
    ("elder", "KS", "AS", "younger"),
    ("elder", "AS", "KS", "elder"),
    ("elder", "7C", "AH", "elder"),
    ("younger", "7C", "8C", "elder"),
    ("younger", "AC", "7H", "younger"),
]


def emit_rules() -> dict:
    replays = []
    for name, build in REPLAY_PACKS:
        replay = _script(build())
        replay["name"] = name
        replays.append(replay)

    tricks = []
    for leader, led, followed, winner in TRICK_CASES:
        who = Player.ELDER if leader == "elder" else Player.YOUNGER
        trick = Trick(who, Card.parse(led), Card.parse(followed))
        if trick.winner.value != winner:
            raise SystemExit(f"trick {leader} {led} {followed} -> {trick.winner.value}")
        tricks.append(
            {
                "leader": leader,
                "led": led,
                "followed": followed,
                "winner": winner,
                "complete": trick.complete,
            }
        )

    # Must follow suit if able; otherwise anything. There are no trumps, so a
    # card of another suit never wins however high.
    legal = []
    deal = deal_from([Card.parse(c) for c in _pack_identity()])
    deal = deal.exchange(Player.ELDER, Hand.of(*list(deal.hand_of(Player.ELDER))[:5]))
    deal = deal.exchange(Player.YOUNGER, Hand.of(*list(deal.hand_of(Player.YOUNGER))[:3]))
    while deal.phase is not Phase.PLAY:
        player = deal.to_declare
        deal = deal.declare(
            player, Declaration.full(deal.hand_of(player), deal.declaring_category)
        )
    legal.append(
        {
            "situation": "leading: anything in hand",
            "hand": deal.hand_of(Player.ELDER).code,
            "led": None,
            "legal": deal.legal_plays(Player.ELDER).code,
        }
    )

    # Two following cases are needed, not one. The interesting rule is the
    # restriction, so lead a suit younger actually holds; the void case, where
    # anything goes, is the easy half and is recorded second.
    elder_hand = deal.hand_of(Player.ELDER)
    younger_hand = deal.hand_of(Player.YOUNGER)
    shared = next(
        (s for s in Suit if elder_hand.in_suit(s) and younger_hand.in_suit(s)), None
    )
    if shared is not None:
        card = next(iter(elder_hand.in_suit(shared)))
        after = deal.play(Player.ELDER, card)
        legal.append(
            {
                "situation": "following: must follow suit when able",
                "hand": after.hand_of(Player.YOUNGER).code,
                "led": card.code,
                "legal": after.legal_plays(Player.YOUNGER).code,
            }
        )

    void = next(
        (s for s in Suit if elder_hand.in_suit(s) and not younger_hand.in_suit(s)),
        None,
    )
    if void is not None:
        card = next(iter(elder_hand.in_suit(void)))
        after = deal.play(Player.ELDER, card)
        legal.append(
            {
                "situation": "following: void in the suit led, so anything goes",
                "hand": after.hand_of(Player.YOUNGER).code,
                "led": card.code,
                "legal": after.legal_plays(Player.YOUNGER).code,
            }
        )

    # Executed here, so a vector claiming an error cannot be committed unless
    # it genuinely raises one -- the same discipline as every other section.
    fresh = lambda: deal_from([Card.parse(c) for c in _pack_identity()])  # noqa: E731
    error_ops = {
        "a pack of thirty-one cards": lambda: deal_from(list(full_deck())[:31]),
        "a pack with a duplicate": lambda: deal_from(
            list(full_deck())[:31] + [full_deck()[0]]
        ),
        "elder exchanges nothing": lambda: fresh().exchange(
            Player.ELDER, Hand.empty()
        ),
        "elder exchanges six": lambda: fresh().exchange(
            Player.ELDER, Hand.of(*list(fresh().hand_of(Player.ELDER))[:6])
        ),
        "exchanging a card not held": lambda: fresh().exchange(
            Player.ELDER, Hand.of(*list(fresh().hand_of(Player.YOUNGER))[:2])
        ),
        "younger exchanges out of turn": lambda: fresh().exchange(
            Player.YOUNGER, Hand.of(*list(fresh().hand_of(Player.YOUNGER))[:2])
        ),
        "playing before the play": lambda: fresh().play(
            Player.ELDER, next(iter(fresh().hand_of(Player.ELDER)))
        ),
        "following with the wrong suit when able": lambda: (
            lambda d, c: d.play(Player.ELDER, c).play(
                Player.YOUNGER,
                next(
                    iter(
                        Hand(
                            d.play(Player.ELDER, c).hand_of(Player.YOUNGER).bits
                            & ~d.play(Player.ELDER, c)
                            .hand_of(Player.YOUNGER)
                            .in_suit(c.suit)
                            .bits
                        )
                    )
                ),
            )
        )(deal, next(iter(elder_hand.in_suit(shared)))),
    }

    errors = []
    for name, op in error_ops.items():
        try:
            op()
        except (ValueError, KeyError) as exc:
            errors.append({"name": name, "raises": type(exc).__name__})
        else:
            raise SystemExit(f"rules error case {name!r} did not raise")

    return {
        "module": "rules",
        "generator": "tools/emit_vectors.py",
        "note": (
            "The deal as a state machine, and the replay format the tutor and "
            "any debugging session need (PLAN.md TODO 6). Each replay is a pack "
            "written out in full plus a scripted sequence of actions -- discard "
            "the first cards in hand order, declare everything, play the lowest "
            "legal card. That policy is not good piquet; it is reproducible "
            "piquet, which is the point. Never a seed."
        ),
        "constants": {
            "HAND_SIZE": HAND_SIZE,
            "TALON_SIZE": TALON_SIZE,
            "ELDER_MAX_EXCHANGE": ELDER_MAX_EXCHANGE,
            "CARTE_BLANCHE_SCORE": CARTE_BLANCHE_SCORE,
            "TRICKS_PER_DEAL": TRICKS_PER_DEAL,
            "CARDS_SCORE": CARDS_SCORE,
            "CAPOT_SCORE": CAPOT_SCORE,
        },
        "phases": [p.value for p in Phase],
        "tricks": tricks,
        "legal_plays": legal,
        "replays": replays,
        "errors": errors,
    }


def _view(v: View) -> dict:
    """A view, flattened. Only the fields a leak could hide in."""
    return {
        "me": v.me.value,
        "phase": v.phase.value,
        "hand": v.hand.code,
        "my_discards": v.my_discards.code,
        "talon_seen": [c.code for c in v.talon_seen],
        "watched_them_take": v.watched_them_take.code,
        "talon_remaining": v.talon_remaining,
        "exchange_limit": v.exchange_limit,
        "unseen": v.unseen.code,
        "outcomes": [[c.name, p.value if p else None] for c, p in v.outcomes],
        "heard": [
            {"category": a.category.name, "primary": a.primary, "tiebreak": a.tiebreak}
            for a in v.heard
        ],
        "seen": [str(c) for c in v.seen],
        "awaiting_answer": (
            None
            if v.awaiting_answer is None
            else {
                "category": v.awaiting_answer.category.name,
                "primary": v.awaiting_answer.primary,
                "tiebreak": v.awaiting_answer.tiebreak,
            }
        ),
        "legal_plays": v.legal_plays.code,
        "to_act": v.to_act,
        "tricks_played": len(v.tricks),
    }


def _observe(pack_codes: list[str], elder_takes: int | None) -> list[dict]:
    """Snapshot both players' views at every step of one scripted deal.

    The vectors record the fields, but the *tests* check an invariant, which is
    the part that actually protects anything: every card of the opponent's hand
    that the viewer does not legitimately know about must lie inside `unseen`.
    A view that leaks fails that immediately, whatever its fields say.
    """
    deal = deal_from([Card.parse(c) for c in pack_codes])
    snapshots = []

    def capture(index: int, action: str) -> None:
        for player in (Player.ELDER, Player.YOUNGER):
            view = view_for(deal, player)
            opponent_hand = deal.hand_of(player.opponent)
            # The oracle's own knowledge, recorded so a test can check the
            # invariant. It is emphatically NOT part of the view.
            leaked = Hand(
                opponent_hand.bits
                & ~view.unseen.bits
                & ~view.watched_them_take.bits
            )
            snapshots.append(
                {
                    "step": index,
                    "action": action,
                    **_view(view),
                    "oracle_opponent_hand": opponent_hand.code,
                    "opponent_cards_not_accounted_for": leaked.code,
                }
            )

    capture(0, "deal")
    index = 1
    for player in (Player.ELDER, Player.YOUNGER):
        limit = deal.exchange_limit(player)
        take = limit if (player is Player.YOUNGER or elder_takes is None) else elder_takes
        deal = deal.exchange(
            player, Hand.of(*list(deal.hand_of(player))[:take])
        )
        capture(index, f"{player.value} exchanges {take}")
        index += 1

    while deal.phase in (
        Phase.DECLARE_POINT,
        Phase.DECLARE_SEQUENCES,
        Phase.DECLARE_SETS,
    ):
        category = deal.declaring_category
        player = deal.to_declare
        deal = deal.declare(
            player, Declaration.full(deal.hand_of(player), category)
        )
        capture(index, f"{player.value} declares {category.name.lower()}")
        index += 1

    while deal.phase is Phase.PLAY:
        player = deal.to_play
        card = next(iter(deal.legal_plays(player)))
        deal = deal.play(player, card)
        capture(index, f"{player.value} plays {card.code}")
        index += 1

    return snapshots


def emit_observation() -> dict:
    pack_codes = _pack_identity()
    return {
        "module": "observation",
        "generator": "tools/emit_vectors.py",
        "note": (
            "The most load-bearing module in the project: agents read the game "
            "ONLY through a View. `oracle_opponent_hand` is the generator's own "
            "knowledge, recorded so a test can assert the invariant -- it is "
            "not part of any view, and no port should expose it. Three "
            "asymmetries matter: elder reads all five of his talon cards even "
            "when he takes fewer; he therefore watches younger draw cards he "
            "has already read; and each player may consult their own discards."
        ),
        "pack": pack_codes,
        "runs": [
            {
                "name": "elder takes all five, so he watches her take nothing",
                "elder_takes": None,
                "snapshots": _observe(pack_codes, None),
            },
            {
                "name": "elder takes two, so younger draws from inside his five",
                "note": (
                    "The asymmetry that matters most. Elder reads all five "
                    "whether he takes them or not; younger discards before she "
                    "draws, so a card she takes in front of him cannot have "
                    "been thrown away and is certainly in her hand. This is the "
                    "only certain knowledge of the other hand the game gives."
                ),
                "elder_takes": 2,
                "snapshots": _observe(pack_codes, 2),
            },
        ],
    }


# Score sheets, in seat order (elder, younger) per deal -- which is all a
# period account of a game ever gives you. The first two are the docstring's
# own worked examples, and they are the whole argument for the rubicon
# mattering: a closer game pays nearly three times as much.
PARTIE_CASES = [
    {
        "name": "both over the rubicon: the difference, plus a hundred",
        "deals": [[17, 18], [18, 17], [17, 17], [17, 17], [16, 18], [17, 17]],
    },
    {
        "name": "the loser is rubiconed: the sum, plus a hundred",
        "deals": [[15, 20], [20, 15], [15, 20], [20, 15], [14, 20], [20, 15]],
    },
    {
        "name": "the winner is short too, and the loser is still rubiconed",
        "deals": [[10, 7], [10, 7], [10, 7], [10, 6], [10, 7], [10, 6]],
    },
    {
        "name": "level after six, so two more are played -- both of them",
        "deals": [[20, 20], [15, 15], [18, 18], [17, 17], [16, 16], [14, 14]],
        "extra": [[25, 10], [5, 5]],
    },
    {
        "name": "level after eight as well, so the partie is drawn",
        "deals": [[20, 20], [15, 15], [18, 18], [17, 17], [16, 16], [14, 14]],
        "extra": [[10, 10], [12, 12]],
    },
]


def emit_partie() -> dict:
    cases = []
    for spec in PARTIE_CASES:
        partie = Partie(opening_dealer=Side.A)
        progress = []
        for elder, younger in spec["deals"] + spec.get("extra", []):
            standing = partie.standing
            progress.append(
                {
                    "deal_number": partie.number,
                    "elder_is": partie.elder.name,
                    "deals_left": partie.deals_left,
                    "standing": {
                        "mine": standing.mine,
                        "theirs": standing.theirs,
                        "deals_left": standing.deals_left,
                        "number": standing.number,
                        "is_last_deal": standing.is_last_deal,
                        "short_of_the_rubicon": standing.short_of_the_rubicon,
                    },
                    "scores_entered": [elder, younger],
                }
            )
            partie = partie.record_scores(elder, younger)

        settlement = partie.settlement
        totals = partie.totals
        cases.append(
            {
                "name": spec["name"],
                "deals": spec["deals"],
                "extra": spec.get("extra", []),
                "progress": progress,
                "complete": partie.complete,
                "deals_played": len(partie.outcomes),
                "totals": {"A": totals[0], "B": totals[1]},
                "settlement": {
                    "winner": (
                        None if settlement.winner is None else settlement.winner.name
                    ),
                    "points": settlement.points,
                    "rubicon": settlement.rubicon,
                },
            }
        )

    # The seat alternates every deal, and a side plays the whole partie. The
    # two get confused exactly once, and expensively.
    alternation = []
    for opening in (Side.A, Side.B):
        partie = Partie(opening_dealer=opening)
        alternation.append(
            {
                "opening_dealer": opening.name,
                "elder_by_deal": [
                    partie.elder_in(n).name
                    for n in range(1, DEALS_IN_PARTIE + EXTRA_DEALS + 1)
                ],
            }
        )

    errors = []
    finished = Partie(opening_dealer=Side.A)
    for elder, younger in PARTIE_CASES[0]["deals"]:
        finished = finished.record_scores(elder, younger)
    try:
        finished.record_scores(1, 1)
    except ValueError:
        errors.append({"name": "recording into a settled partie", "raises": "ValueError"})
    else:
        raise SystemExit("recording into a settled partie did not raise")

    return {
        "module": "partie",
        "generator": "tools/emit_vectors.py",
        "note": (
            "Six deals, the alternating deal, and the rubicon. The guard is on "
            "the LOSER's score, not the winner's: a loser short of a hundred is "
            "rubiconed even if the winner fell short too, so two players who "
            "crawl to 60 and 40 settle for 200. This is the clause that makes "
            "maximising points in a deal different from playing well."
        ),
        "constants": {
            "DEALS_IN_PARTIE": DEALS_IN_PARTIE,
            "EXTRA_DEALS": EXTRA_DEALS,
            "RUBICON": RUBICON,
            "PARTIE_BONUS": PARTIE_BONUS,
        },
        "cases": cases,
        "alternation": alternation,
        "errors": errors,
    }


def main() -> int:
    VECTORS.mkdir(exist_ok=True)
    for name, build in (
        ("cards", emit_cards),
        ("combos", emit_combos),
        ("scoring", emit_scoring),
        ("style", emit_style),
        ("declarations", emit_declarations),
        ("rules", emit_rules),
        ("observation", emit_observation),
        ("partie", emit_partie),
    ):
        path = VECTORS / f"{name}.json"
        path.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {path.relative_to(VECTORS.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
