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
from piquet import chances as chances_mod  # noqa: E402
from piquet.heuristics import MAX_LEVEL, HeuristicAgent  # noqa: E402
from piquet.inference import (  # noqa: E402
    known_voids,
    opponent_hand_size,
    opponent_played,
    possible_hands,
)
from piquet.match import play_deal  # noqa: E402
from piquet.style import BALANCED  # noqa: E402
from piquet.solver import (  # noqa: E402
    SolverAgent,
    CAPOT_BONUS,
    CARDS_BONUS,
    EVEN,
    TRICKS,
    best_card,
    card_values,
    solve,
)
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

VECTORS = pathlib.Path(__file__).resolve().parents[2] / "vectors"

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


# (elder hand, younger hand, leader, card already led, elder's tricks so far).
# Positions must be consistent: equal hands at the start of a trick, and the
# leader one card short once he has led. Elder's trick count is the running
# total, because the ten for the cards and the forty for a capot are decided
# against the full twelve.
SOLVER_POSITIONS = [
    ("the last trick, elder holds the master", "AS", "KS", "elder", None, 6),
    ("the last trick, elder is beaten", "KS", "AS", "elder", None, 6),
    ("the last trick decides a capot", "AS", "KS", "elder", None, 11),
    ("the last trick decides a capot against him", "KS", "AS", "elder", None, 0),
    ("six each, nothing in it", "AS", "KS", "elder", None, 5),
    ("younger leads the last", "AS", "KS", "younger", None, 6),
    ("two tricks left, ducking beats cashing", "AS 7S", "KS 8S", "elder", None, 5),
    ("two tricks left, across two suits", "AS 7H", "KS 8H", "elder", None, 5),
    ("two tricks left, elder is void", "AC KC", "AD KD", "elder", None, 5),
    ("three tricks left", "AS KS QS", "JS TS 9S", "elder", None, 4),
    ("three tricks, split suits", "AS KS 7H", "QS JS 8H", "elder", None, 4),
    ("mid-trick: younger must follow", "KS", "AS QS", "elder", "7S", 5),
    ("mid-trick: younger is void and may discard", "KS", "AH QH", "elder", "7S", 5),
    ("four tricks left", "AS KS 7H 8H", "QS JS 9H TH", "elder", None, 3),
]

BAD_POSITIONS = [
    ("hands of unequal length with nothing led", "AS KS", "QS", "elder", None, 0),
    ("leader not short after leading", "AS KS", "QS JS", "elder", "7S", 0),
]


def _assert_no_sampling(deal, solver, ladder, solver_seat: str) -> None:
    """Refuse to emit a solver vector the Rust could never reproduce."""
    from piquet.inference import possible_hands as _all_hands

    seat = Player.ELDER if solver_seat == "elder" else Player.YOUNGER
    agents = {seat: solver, seat.opponent: ladder}
    probe = deal
    for player in (Player.ELDER, Player.YOUNGER):
        probe = probe.exchange(player, agents[player].exchange(view_for(probe, player)))
    while probe.to_declare is not None:
        player = probe.to_declare
        probe = probe.declare(
            player,
            agents[player].declare(view_for(probe, player), probe.declaring_category),
        )
    while probe.phase is Phase.PLAY:
        player = probe.to_play
        view = view_for(probe, player)
        if (
            player is seat
            and len(view.hand) <= solver.exact_from
            and len(view.legal_plays) > 1
        ):
            candidates = len(_all_hands(view, limit=None))
            if candidates > solver.max_worlds:
                raise SystemExit(
                    f"solver vector would sample: {candidates} candidates "
                    f"against max_worlds={solver.max_worlds}. Pick another pack."
                )
        probe = probe.play(player, agents[player].play(view))


def emit_solver() -> dict:
    positions = []
    for name, elder_code, younger_code, leader_name, led_code, tricks in SOLVER_POSITIONS:
        elder, younger = parse_hand(elder_code), parse_hand(younger_code)
        leader = Player.ELDER if leader_name == "elder" else Player.YOUNGER
        led = Card.parse(led_code) if led_code else None

        value = solve(elder, younger, leader, led, tricks)
        chosen, chosen_value = best_card(elder, younger, leader, led, tricks)
        values = card_values(elder, younger, leader, led, tricks)

        # EVEN is a pair of Python ints, so the default path never produces a
        # fraction despite every type hint saying float. A port may use i64.
        if value != int(value):
            raise SystemExit(f"{name}: default path produced a fraction {value}")

        positions.append(
            {
                "name": name,
                "elder": elder_code,
                "younger": younger_code,
                "leader": leader_name,
                "led": led_code,
                "elder_tricks": tricks,
                "value": int(value),
                "best_card": chosen.code,
                "best_value": int(chosen_value),
                "card_values": sorted(
                    ({"card": c.code, "value": int(v)} for c, v in values.items()),
                    key=lambda e: e["card"],
                ),
            }
        )

    errors = []
    for name, elder_code, younger_code, leader_name, led_code, tricks in BAD_POSITIONS:
        leader = Player.ELDER if leader_name == "elder" else Player.YOUNGER
        try:
            solve(
                parse_hand(elder_code),
                parse_hand(younger_code),
                leader,
                Card.parse(led_code) if led_code else None,
                tricks,
            )
        except ValueError:
            errors.append({"name": name, "raises": "ValueError"})
        else:
            raise SystemExit(f"solver position {name!r} did not raise")

    # docs/DESIGN.md 2.1 singles this out: the transposition key packs two
    # hands, a leader, a led card and a trick count into one integer with
    # shifts up to 71, so it needs 75 bits. JavaScript cannot build it with
    # bitwise operators at all; Rust holds it in a u128. Keys are written as
    # decimal STRINGS because they exceed the 2**53 a JSON double represents
    # exactly -- the one place these vectors break their own number rule.
    keys = []
    for elder_code, younger_code, leader_i, led_i, tricks in [
        ("AS", "KS", 0, -1, 6),
        ("AS", "KS", 1, -1, 6),
        ("AS 7C", "KS 8C", 0, 0, 12),
        (" ".join(c.code for c in full_deck()[:12]), "", 0, 31, 11),
    ]:
        elder_bits = parse_hand(elder_code).bits
        younger_bits = parse_hand(younger_code).bits
        key = (
            elder_bits
            | (younger_bits << 32)
            | (leader_i << 64)
            | ((led_i + 1) << 65)
            | (tricks << 71)
        )
        keys.append(
            {
                "elder_bits": elder_bits,
                "younger_bits": younger_bits,
                "leader": leader_i,
                "led_index": led_i,
                "elder_tricks": tricks,
                "key": str(key),
                "bit_length": key.bit_length(),
            }
        )

    # Rung 5 against rung 4, both deterministic. The solver samples opponent
    # hands, which would normally put it beyond what a golden vector can
    # check. These packs happen to keep the candidate set inside max_worlds
    # the whole way down, so no sample is taken and the agent is deterministic
    # -- a property of the PACKS and not of the solver, which is why
    # _assert_no_sampling checks it rather than trusting it. Over 150 random
    # deals the set reached 35 against a limit of 30 in fourteen of them.
    agent_games = []
    for pack_name, build in (
        ("the pack in index order", _pack_identity),
        ("the pack taken every 7th card", None),
    ):
        if build is None:
            deck = full_deck()
            pack_codes = [deck[(i * 7) % 32].code for i in range(32)]
        else:
            pack_codes = build()
        for solver_seat in ("elder", "younger"):
            solver = SolverAgent(erraticism=0.0, name="solver8")
            ladder = HeuristicAgent(level=4, erraticism=0.0, name="L4")
            elder, younger = (
                (solver, ladder) if solver_seat == "elder" else (ladder, solver)
            )
            deal = deal_from([Card.parse(c) for c in pack_codes])
            # A solver game is only comparable across languages while the
            # candidate set stays within max_worlds: past that it takes a
            # RANDOM SAMPLE and the two engines legitimately diverge. The four
            # packs here happen to stay inside it -- one reaches 24 against a
            # limit of 30 -- so the constraint is asserted rather than assumed,
            # or a later pack would silently emit a vector nothing can satisfy.
            _assert_no_sampling(deal, solver, ladder, solver_seat)
            finished, _ = play_deal(elder, younger, deal=deal)
            agent_games.append(
                {
                    "pack": pack_name,
                    "pack_codes": pack_codes,
                    "solver_seat": solver_seat,
                    "elder_score": finished.log.total(Player.ELDER),
                    "younger_score": finished.log.total(Player.YOUNGER),
                    "elder_tricks": finished.tricks_won(Player.ELDER),
                    "cards_played": [t.led.code for t in finished.tricks]
                    + [t.followed.code for t in finished.tricks],
                }
            )

    return {
        "module": "solver",
        "generator": "tools/emit_vectors.py",
        "note": (
            "Exact endgame search. Under the default EVEN weights -- a pair of "
            "Python ints -- the whole recursion is integer arithmetic end to "
            "end, despite every type hint saying float, so these values are "
            "exact and a port may use i64. Values are elder-minus-younger: "
            "positive favours elder. The memo_key section pins the layout of "
            "the transposition key, which needs 75 bits."
        ),
        "constants": {
            "TRICKS": TRICKS,
            "CARDS_BONUS": CARDS_BONUS,
            "CAPOT_BONUS": CAPOT_BONUS,
            "EVEN": list(EVEN),
        },
        "positions": positions,
        "agent_games": agent_games,
        "memo_key": {
            "layout": (
                "elder | younger<<32 | leader<<64 | (led+1)<<65 | tricks<<71; "
                "led is -1 when nothing has been led, so the field is 0"
            ),
            "cases": keys,
        },
        "errors": errors,
    }


# (needed, deals_left, elder_first)
CHANCE_CASES = [
    (18, 1, True), (18, 1, False), (0, 3, True), (-5, 2, True),
    (40, 1, True), (40, 2, True), (100, 6, True), (100, 6, False),
    (60, 2, False), (25, 1, True), (30, 3, False), (200, 1, True),
]

# (mine, theirs) -- the settlement is integer-exact, so these assert equality
SETTLEMENT_CASES = [
    (105, 101), (101, 105), (120, 89), (51, 49), (100, 100),
    (99, 99), (0, 0), (150, 20), (100, 99), (99, 100),
]

# (mine, theirs, deals_left, elder_first) -- floats, so these carry a tolerance
WEIGHT_CASES = [
    (82, 70, 1, True), (82, 70, 1, False), (0, 0, 6, True),
    (95, 95, 1, True), (120, 88, 1, True), (120, 0, 1, True),
    (120, 20, 1, True), (120, 55, 1, True), (120, 70, 1, True),
    (120, 100, 1, True), (120, 130, 1, True), (60, 60, 2, True),
]


def emit_chances() -> dict:
    densities = {}
    for seat in (Player.ELDER, Player.YOUNGER):
        rows = chances_mod.density(seat)
        surv = chances_mod.survival(seat)
        densities[seat.value] = {
            "length": len(rows),
            "sum": sum(rows),
            "mean": sum(i * p for i, p in enumerate(rows)),
            "first_eight": list(rows[:8]),
            "survival_at_zero": surv[0],
            "survival_at_thirty": surv[30],
        }

    chances = [
        {
            "needed": needed,
            "deals_left": left,
            "elder_first": first,
            "chance": chances_mod.chance_of(needed, left, first),
            "in_words": chances_mod.in_words(
                chances_mod.chance_of(needed, left, first)
            ),
        }
        for needed, left, first in CHANCE_CASES
    ]

    settlements = [
        {"mine": mine, "theirs": theirs, "pays": chances_mod.settlement_of(mine, theirs)}
        for mine, theirs in SETTLEMENT_CASES
    ]

    weights = []
    for mine, theirs, left, first in WEIGHT_CASES:
        w_mine, w_theirs = chances_mod.point_weights(mine, theirs, left, first)
        weights.append(
            {
                "mine": mine,
                "theirs": theirs,
                "deals_left": left,
                "elder_first": first,
                "expected_settlement": chances_mod.expected_settlement(
                    mine, theirs, left, first
                ),
                "weight_mine": w_mine,
                "weight_theirs": w_theirs,
            }
        )

    # The first 12 draws of the fixed-seed generator, so a port can check its
    # own RNG before anything downstream disagrees for reasons that are hard
    # to trace back here.
    import random

    rng = random.Random(1674)
    draws = [rng.getrandbits(9) for _ in range(12)]

    return {
        "module": "chances",
        "generator": "tools/emit_vectors.py",
        "note": (
            "The first module where floating point enters the engine, so the "
            "first whose vectors need a tolerance. settlement_of is integer "
            "and asserts equality; everything derived from the sampled "
            "futures is a float and asserts a tolerance. The sampling is "
            "behind a FIXED seed -- 1674, so a position always values the "
            "same -- which is the one place a port must reproduce a Python "
            "RNG rather than avoid one. rng_draws lets it check that first."
        ),
        "tolerance": 1e-9,
        "cap": chances_mod.CAP,
        "rng_seed": 1674,
        "rng_draws": draws,
        "densities": densities,
        "chances": chances,
        "settlements": settlements,
        "weights": weights,
    }


def emit_heuristics() -> dict:
    """Pin every decision the ladder makes, for each rung against each rung.

    A `HeuristicAgent` with erraticism 0 and the BALANCED style is **fully
    deterministic**: `_rung` returns the level without drawing, and the sinking
    roll can never fire because the probability is zero. So the whole AI is
    comparable across languages exactly, which is otherwise impossible -- an
    agent's own draws are the one thing golden vectors cannot check.
    """
    # Index order and its reverse deal whole suits to one player, so most
    # plays are forced and younger's rung barely shows. A multiplicative
    # permutation of the indices mixes the suits properly while staying
    # written-down rather than seeded -- `stride` is coprime with 32, so each
    # one is a genuine permutation of the pack.
    packs = {
        "the pack in index order": _pack_identity(),
        "the pack reversed": _pack_reversed(),
    }
    for stride in (7, 11, 13):
        deck = full_deck()
        packs[f"the pack taken every {stride}th card"] = [
            deck[(i * stride) % 32].code for i in range(32)
        ]

    games = []
    for pack_name, pack_codes in packs.items():
        for elder_level in range(1, MAX_LEVEL + 1):
            for younger_level in range(1, MAX_LEVEL + 1):
                elder = HeuristicAgent(
                    level=elder_level, style=BALANCED, erraticism=0.0,
                    name=f"L{elder_level}",
                )
                younger = HeuristicAgent(
                    level=younger_level, style=BALANCED, erraticism=0.0,
                    name=f"L{younger_level}",
                )
                deal = deal_from([Card.parse(c) for c in pack_codes])
                finished, _ = play_deal(elder, younger, deal=deal)
                games.append(
                    {
                        "pack": pack_name,
                        "elder_level": elder_level,
                        "younger_level": younger_level,
                        "elder_score": finished.log.total(Player.ELDER),
                        "younger_score": finished.log.total(Player.YOUNGER),
                        "elder_tricks": finished.tricks_won(Player.ELDER),
                        "cards_played": [
                            t.led.code for t in finished.tricks
                        ] + [
                            t.followed.code for t in finished.tricks
                        ],
                        "events": [
                            {
                                "player": e.player.value,
                                "amount": e.amount,
                                "category": e.category.name,
                            }
                            for e in finished.log
                        ],
                    }
                )

    return {
        "module": "heuristics",
        "generator": "tools/emit_vectors.py",
        "note": (
            "Every decision the capability ladder makes, rung against rung, "
            "on two packs. Deterministic because erraticism is zero and the "
            "BALANCED style never sinks, which is what makes the AI itself "
            "comparable across two languages rather than only the rules "
            "beneath it. A port that reproduces the rules and gets these wrong "
            "has a strategy bug, which no other vector would catch."
        ),
        "packs": packs,
        "max_level": MAX_LEVEL,
        "games": games,
    }


def emit_inference() -> dict:
    """Snapshot the candidate set through a deal, with elder taking two.

    The count is recorded, but the assertion that matters is the invariant:
    **the opponent's real hand must always be a candidate**. Inference that
    rules out the truth is worse than inference that rules out nothing, and no
    count would reveal it.
    """
    pack_codes = _pack_identity()
    deal = deal_from([Card.parse(c) for c in pack_codes])
    snapshots = []

    def capture(step: int, action: str) -> None:
        for player in (Player.ELDER, Player.YOUNGER):
            view = view_for(deal, player)
            if view.phase is Phase.COMPLETE:
                continue
            hands = possible_hands(view, limit=None)
            actual = deal.hand_of(player.opponent)
            snapshots.append(
                {
                    "step": step,
                    "action": action,
                    "me": player.value,
                    "phase": view.phase.value,
                    "opponent_hand_size": opponent_hand_size(view),
                    "known_voids": sorted(int(s) for s in known_voids(view)),
                    "opponent_played": opponent_played(view).code,
                    "candidates": len(hands),
                    "actual_is_a_candidate": actual in hands,
                    "watched_them_take": view.watched_them_take.code,
                }
            )

    capture(0, "deal")
    index = 1
    for player, take in ((Player.ELDER, 2), (Player.YOUNGER, None)):
        limit = deal.exchange_limit(player)
        count = take if take is not None else limit
        deal = deal.exchange(
            player, Hand.of(*list(deal.hand_of(player))[:count])
        )
        capture(index, f"{player.value} exchanges {count}")
        index += 1

    while deal.phase in (
        Phase.DECLARE_POINT, Phase.DECLARE_SEQUENCES, Phase.DECLARE_SETS
    ):
        player = deal.to_declare
        category = deal.declaring_category
        deal = deal.declare(
            player, Declaration.full(deal.hand_of(player), category)
        )
        capture(index, f"{player.value} declares {category.name.lower()}")
        index += 1

    # Only the first few tricks: the candidate set is largest early, and the
    # enumeration is a binomial that would take minutes over a whole deal.
    tricks = 0
    while deal.phase is Phase.PLAY and tricks < 8:
        player = deal.to_play
        card = next(iter(deal.legal_plays(player)))
        deal = deal.play(player, card)
        if deal.current_trick is None:
            tricks += 1
            capture(index, f"after trick {tricks}")
        index += 1

    return {
        "module": "inference",
        "generator": "tools/emit_vectors.py",
        "note": (
            "Elder takes two, so he watches younger draw from inside his five "
            "and those cards are held out of the enumeration and added to "
            "every candidate. The invariant is that the opponent's real hand "
            "is always among the candidates; a count alone would not show an "
            "inference that ruled out the truth."
        ),
        "pack": pack_codes,
        "elder_takes": 2,
        "snapshots": snapshots,
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
        ("solver", emit_solver),
        ("chances", emit_chances),
        ("heuristics", emit_heuristics),
        ("inference", emit_inference),
    ):
        path = VECTORS / f"{name}.json"
        path.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {path.relative_to(VECTORS.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
