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

VECTORS = pathlib.Path(__file__).resolve().parents[2] / "vectors"


def load(name: str) -> dict:
    path = VECTORS / f"{name}.json"
    if not path.exists():
        pytest.fail(
            f"missing vector file {path.name}; generate it with "
            f"`python tools/emit_vectors.py` from `python/`"
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


# ===========================================================================
# style
# ===========================================================================


@pytest.fixture(scope="module")
def styvec() -> dict:
    return load("style")


def test_calibrated_bands_are_the_measured_ones(styvec):
    """These numbers were fitted, not chosen, and they are load-bearing.

    Each band is narrow enough that an extreme setting costs under about a
    point a deal, which is what stops style becoming a second skill dial. They
    want re-measuring whenever the ladder moves, so pinning them here makes a
    silent drift impossible.
    """
    from piquet.style import CALIBRATED

    assert {k: list(v) for k, v in CALIBRATED.items()} == styvec["calibrated"]


def test_the_balanced_style_is_neutral(styvec):
    from piquet.style import BALANCED

    assert BALANCED.discard_boldness == styvec["balanced"]["discard_boldness"]
    assert BALANCED.sinking == styvec["balanced"]["sinking"]
    assert BALANCED.guard_retention == styvec["balanced"]["guard_retention"]


def test_styles_describe_themselves_relative_to_the_band(styvec):
    """Read against the raw 0-to-1 scale every opponent would be "even-handed".

    The bands are deliberately narrow, so `describe` divides by the calibrated
    span instead. What a player needs to know is whether this opponent is
    bolder than the others they might meet, not where it sits in the abstract.
    """
    from piquet.style import Style

    for case in styvec["styles"]:
        fields = {k: v for k, v in case.items() if k != "describe"}
        assert Style(**fields).describe() == case["describe"]


def test_a_style_outside_zero_to_one_is_refused(styvec):
    from piquet.style import Style

    for case in styvec["errors"]:
        with pytest.raises(ValueError):
            Style(**case["fields"])


# ===========================================================================
# declarations
# ===========================================================================


@pytest.fixture(scope="module")
def dvec() -> dict:
    return load("declarations")


def _result(case):
    from piquet.declarations import CategoryResult, Declaration, compare_in
    from piquet.scoring import Category

    category = Category[case["category"]]
    eh = parse_hand(case["elder_hand"])
    yh = parse_hand(case["younger_hand"])
    ed = Declaration.sink() if case["elder_sinks"] else Declaration.full(eh, category)
    yd = Declaration.full(yh, category)
    return category, CategoryResult(category, ed, yd, compare_in(category, ed.best, yd.best))


def test_the_dialogue_resolves_as_recorded(dvec):
    for case in dvec["dialogue"]:
        _, result = _result(case)
        where = f"{case['category']} {case['elder_hand']!r} vs {case['younger_hand']!r}"
        assert result.comparison.value == case["comparison"], where
        got_winner = result.winner.value if result.winner else None
        assert got_winner == case["winner"], where
        assert result.shapes_match == case["shapes_match"], where


def test_the_suit_is_never_spoken(dvec):
    """An announcement is a sort key stripped of its suit, and often of more.

    This is the discipline that `observation` has broken three times in this
    project's history, so it is pinned at the source rather than only where it
    is consumed.
    """
    from piquet.scoring import Player

    for case in dvec["dialogue"]:
        _, result = _result(case)
        for who, player in (("elder", Player.ELDER), ("younger", Player.YOUNGER)):
            want = case["announced"][who]
            got = result.announcement_of(player)
            if want is None:
                assert got is None, case["category"]
                continue
            assert got.category.name == want["category"]
            assert got.primary == want["primary"]
            assert got.tiebreak == want["tiebreak"]
            assert str(got) == want["spoken"]
            assert "spade" not in str(got).lower()
            assert "club" not in str(got).lower()


def test_a_tiebreak_is_spoken_only_when_the_shapes_match(dvec):
    """And only by elder. Younger answers his number rather than naming hers.

    "Point of five." "Equal." "Making forty-nine." "Good." -- the tie-break is
    asked for, never volunteered, which was itself a corrected overclaim in
    this project's history.
    """
    for case in dvec["dialogue"]:
        elder = case["announced"]["elder"]
        younger = case["announced"]["younger"]
        if elder is not None and elder["tiebreak"] is not None:
            assert case["shapes_match"], case["category"]
        if younger is not None:
            assert younger["tiebreak"] is None, (
                "younger never volunteers a tie-break"
            )


def test_a_beaten_declaration_is_never_shown(dvec):
    """The loser of a category gives away its shape but not its cards."""
    from piquet.scoring import Player

    for case in dvec["dialogue"]:
        _, result = _result(case)
        for who, player in (("elder", Player.ELDER), ("younger", Player.YOUNGER)):
            shown = result.shown(player)
            assert len(shown) == len(case["shown"][who]), case["category"]
            if case["winner"] is not None and case["winner"] != who:
                assert shown == (), "a beaten declaration must not be shown"


def test_matches_reads_the_key_and_nothing_else(dvec):
    """Which is why two holdings of the same shape are indistinguishable.

    A hand of five clubs and a hand of five spades worth the same pips answer
    to the same announcement, because the announcement never named a suit.
    """
    from piquet.declarations import Announcement, Declaration
    from piquet.scoring import Category

    for case in dvec["matches"]:
        spec = case["announcement"]
        category = Category[spec["category"]]
        announcement = Announcement(category, spec["primary"], spec["tiebreak"])
        best = Declaration.full(parse_hand(case["hand"]), category).best
        assert announcement.matches(best) is case["matches"], case


def test_invalid_declarations_are_refused(dvec):
    """Claims must be of the right kind, genuinely held, and non-overlapping."""
    from piquet.cards import Rank, Suit
    from piquet.combos import CardSet, Point, Sequence
    from piquet.declarations import Declaration
    from piquet.scoring import Category

    def rebuild(claim):
        if claim["kind"] == "point":
            return Point(Suit(claim["suit"]), claim["length"], claim["pip_value"])
        if claim["kind"] == "sequence":
            return Sequence(Suit(claim["suit"]), Rank(claim["top"]), claim["length"])
        return CardSet(Rank(claim["rank"]), claim["count"])

    for case in dvec["validate"]:
        declaration = Declaration(tuple(rebuild(c) for c in case["claims"]))
        with pytest.raises(ValueError):
            declaration.validate(parse_hand(case["hand"]), Category[case["category"]])


def test_remaining_vector_files_are_self_describing(styvec, dvec):
    assert styvec["module"] == "style"
    assert dvec["module"] == "declarations"
    for section in ("calibrated", "balanced", "styles", "errors"):
        assert styvec[section], f"style section {section!r} is empty"
    for section in ("dialogue", "matches", "validate"):
        assert dvec[section], f"declarations section {section!r} is empty"


# ===========================================================================
# rules -- the deal as a state machine, and the replay format
# ===========================================================================


@pytest.fixture(scope="module")
def rvec() -> dict:
    return load("rules")


def test_rules_constants(rvec):
    import piquet.rules as rules

    for name, value in rvec["constants"].items():
        assert getattr(rules, name) == value, name


def test_phases_are_named_and_ordered_as_recorded(rvec):
    from piquet.rules import Phase

    assert [p.value for p in Phase] == rvec["phases"]


def test_the_higher_card_of_the_suit_led_takes_the_trick(rvec):
    """There are no trumps, so a card of another suit never wins, however high.

    `7C` beaten by `AH` is still elder's trick. This is the rule newcomers
    most reliably get wrong, and it is one line in the engine.
    """
    from piquet.cards import Card
    from piquet.rules import Trick
    from piquet.scoring import Player

    players = {"elder": Player.ELDER, "younger": Player.YOUNGER}
    for case in rvec["tricks"]:
        trick = Trick(
            players[case["leader"]],
            Card.parse(case["led"]),
            Card.parse(case["followed"]),
        )
        assert trick.complete is case["complete"]
        assert trick.winner.value == case["winner"], case


def test_an_incomplete_trick_has_no_winner():
    from piquet.cards import Card
    from piquet.rules import Trick
    from piquet.scoring import Player

    trick = Trick(Player.ELDER, Card.parse("AS"))
    assert not trick.complete
    with pytest.raises(ValueError):
        trick.winner


def _replay(pack_codes, steps):
    """Drive a deal through a recorded script, yielding (step, deal) as it goes.

    This is the replay format PLAN.md TODO 6 asks for. It is written against
    `deal_from` and an explicit pack, never a seed, because no two languages
    share a random number generator.
    """
    from piquet.cards import Card, Hand
    from piquet.rules import deal_from
    from piquet.declarations import Declaration
    from piquet.scoring import Category, Player

    players = {"elder": Player.ELDER, "younger": Player.YOUNGER}
    deal = deal_from([Card.parse(c) for c in pack_codes])

    for step in steps:
        if step["action"] == "deal":
            pass
        elif step["action"] == "exchange":
            deal = deal.exchange(
                players[step["player"]], parse_hand(step["discard"])
            )
        elif step["action"] == "declare":
            player = players[step["player"]]
            deal = deal.declare(
                player,
                Declaration.full(deal.hand_of(player), Category[step["category"]]),
            )
        elif step["action"] == "play":
            deal = deal.play(players[step["player"]], Card.parse(step["card"]))
        else:
            raise AssertionError(f"unknown action {step['action']!r}")
        yield step, deal


def _state_of(deal) -> dict:
    from piquet.scoring import Player

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


def test_every_replay_reproduces_its_recorded_states(rvec):
    """The whole engine, end to end, checked at every single step.

    A divergence anywhere -- a mis-dealt talon, an exchange taking from the
    wrong end of the stock, a declaration scoring in the wrong category, a
    trick going to the wrong player -- shows up at the step it happened rather
    than as a wrong number at the end.
    """
    for replay in rvec["replays"]:
        for i, (step, deal) in enumerate(_replay(replay["pack"], replay["steps"])):
            assert _state_of(deal) == step["after"], (
                f"{replay['name']}: diverged at step {i} ({step['action']})"
            )


def test_every_replay_finishes_and_settles(rvec):
    from piquet.scoring import Player

    for replay in rvec["replays"]:
        deal = None
        for _, deal in _replay(replay["pack"], replay["steps"]):
            pass
        final = replay["final"]
        assert deal.phase.value == "complete", replay["name"]
        assert _state_of(deal) == {k: final[k] for k in _state_of(deal)}
        assert (deal.log.repique.value if deal.log.repique else None) == final["repique"]
        assert (deal.log.pique.value if deal.log.pique else None) == final["pique"]
        assert [
            {
                "player": e.player.value,
                "amount": e.amount,
                "category": e.category.name,
                "detail": e.detail,
            }
            for e in deal.log
        ] == final["events"]


def test_all_twelve_tricks_are_accounted_for(rvec):
    from piquet.rules import TRICKS_PER_DEAL

    for replay in rvec["replays"]:
        final = replay["final"]
        assert final["elder_tricks"] + final["younger_tricks"] == TRICKS_PER_DEAL


def test_carte_blanche_is_logged_before_anything_else(rvec):
    """Announced as soon as it is noticed, which is also where Law 67 puts it."""
    for replay in rvec["replays"]:
        events = replay["final"]["events"]
        blanche = [i for i, e in enumerate(events) if e["category"] == "CARTE_BLANCHE"]
        if blanche:
            assert blanche == [0], replay["name"]


def test_legal_plays_follow_suit_when_able(rvec):
    for case in rvec["legal_plays"]:
        hand, legal = parse_hand(case["hand"]), parse_hand(case["legal"])
        assert (legal - hand).bits == 0, "a legal play must be in hand"
        if case["led"] is None:
            assert legal.bits == hand.bits, "the leader may lead anything"
            continue
        from piquet.cards import Card

        led_suit = Card.parse(case["led"]).suit
        in_suit = hand.in_suit(led_suit)
        if in_suit:
            assert legal.bits == in_suit.bits, "must follow suit when able"
        else:
            assert legal.bits == hand.bits, "void: anything goes"


def test_rules_vector_file_is_self_describing(rvec):
    assert rvec["module"] == "rules"
    for section in ("constants", "phases", "tricks", "legal_plays", "replays", "errors"):
        assert rvec[section], f"section {section!r} is empty"
    assert len(rvec["errors"]) >= 7


# ===========================================================================
# observation -- what each player is allowed to know
# ===========================================================================


@pytest.fixture(scope="module")
def ovec() -> dict:
    return load("observation")


def _observe(pack_codes, elder_takes):
    """Re-derive the scripted deal, yielding both players' views at each step.

    Mirrors `tools/emit_vectors.py`. The policy is deterministic, so
    re-deriving it here also checks that it is genuinely reproducible rather
    than merely recorded.
    """
    from piquet.cards import Card, Hand
    from piquet.declarations import Declaration
    from piquet.observation import view_for
    from piquet.rules import Phase, deal_from
    from piquet.scoring import Player

    deal = deal_from([Card.parse(c) for c in pack_codes])

    def both():
        return [(p, view_for(deal, p), deal.hand_of(p.opponent))
                for p in (Player.ELDER, Player.YOUNGER)]

    yield both()
    for player in (Player.ELDER, Player.YOUNGER):
        limit = deal.exchange_limit(player)
        take = limit if (player is Player.YOUNGER or elder_takes is None) else elder_takes
        deal = deal.exchange(player, Hand.of(*list(deal.hand_of(player))[:take]))
        yield both()

    while deal.phase in (
        Phase.DECLARE_POINT, Phase.DECLARE_SEQUENCES, Phase.DECLARE_SETS
    ):
        player = deal.to_declare
        deal = deal.declare(
            player, Declaration.full(deal.hand_of(player), deal.declaring_category)
        )
        yield both()

    while deal.phase is Phase.PLAY:
        player = deal.to_play
        deal = deal.play(player, next(iter(deal.legal_plays(player))))
        yield both()


def _flat(view):
    return {
        "me": view.me.value,
        "phase": view.phase.value,
        "hand": view.hand.code,
        "my_discards": view.my_discards.code,
        "talon_seen": [c.code for c in view.talon_seen],
        "watched_them_take": view.watched_them_take.code,
        "talon_remaining": view.talon_remaining,
        "exchange_limit": view.exchange_limit,
        "unseen": view.unseen.code,
        "legal_plays": view.legal_plays.code,
        "to_act": view.to_act,
        "tricks_played": len(view.tricks),
    }


def test_every_view_reproduces_field_for_field(ovec):
    for run in ovec["runs"]:
        recorded = iter(run["snapshots"])
        for group in _observe(ovec["pack"], run["elder_takes"]):
            for _, view, _ in group:
                want = next(recorded)
                got = _flat(view)
                assert got == {k: want[k] for k in got}, (
                    f"{run['name']}: step {want['step']} {want['me']}"
                )


def test_no_view_ever_accounts_for_the_opponents_hand(ovec):
    """The invariant the whole module exists to maintain.

    Every card of the opponent's hand must either be inside `unseen` -- that
    is, unaccounted for -- or be one this player legitimately watched them
    take. Anything else means the view has handed over information the table
    never gave, and every strength measurement taken through it is worthless.
    """
    from piquet.cards import Hand

    for run in ovec["runs"]:
        for group in _observe(ovec["pack"], run["elder_takes"]):
            for player, view, opponent_hand in group:
                leaked = Hand(
                    opponent_hand.bits
                    & ~view.unseen.bits
                    & ~view.watched_them_take.bits
                )
                assert leaked.bits == 0, (
                    f"{run['name']}: {player.value} at {view.phase.value} can "
                    f"account for {leaked.code} of the opponent's hand"
                )


def test_elder_hears_nothing_from_younger_until_he_has_led(ovec):
    """Her declarations are withheld until he has led to the first trick.

    Which makes elder's first lead genuinely blind, and is a real piece of
    piquet a tutor can point at. Closing this leak is what moved the ladder.
    """
    for run in ovec["runs"]:
        for group in _observe(ovec["pack"], run["elder_takes"]):
            for player, view, _ in group:
                if player.value != "elder":
                    continue
                if not view.tricks and view.current_trick is None:
                    assert view.heard == (), "younger has not spoken yet"
                    assert view.seen == (), "and has shown nothing"


def test_only_elder_ever_watches_the_opponent_draw(ovec):
    for run in ovec["runs"]:
        for group in _observe(ovec["pack"], run["elder_takes"]):
            for player, view, _ in group:
                if player.value == "younger":
                    assert view.watched_them_take.bits == 0


def test_watched_cards_are_certain_and_shrink_as_she_plays(ovec):
    """What comes back is what she holds *now*, so played cards drop out.

    The set is only monotonic once the exchange is over. Before that it is
    empty and then becomes populated, which is the exchange happening rather
    than elder learning something he should not have.
    """
    from piquet.rules import Phase
    from piquet.scoring import Player

    exchanging = (Phase.ELDER_EXCHANGE, Phase.YOUNGER_EXCHANGE)
    for run in ovec["runs"]:
        previous = None
        for group in _observe(ovec["pack"], run["elder_takes"]):
            for player, view, opponent_hand in group:
                if player is not Player.ELDER:
                    continue
                watched = view.watched_them_take
                assert (watched - opponent_hand).bits == 0, (
                    "a watched card must really be in her hand"
                )
                if view.phase in exchanging:
                    continue
                if previous is not None:
                    assert (watched - previous).bits == 0, (
                        "once dealt, the watched set may shrink, never grow"
                    )
                previous = watched


def test_the_watched_case_is_actually_exercised(ovec):
    """Otherwise the three tests above are asserting things about empty sets."""
    non_empty = [
        s
        for run in ovec["runs"]
        for s in run["snapshots"]
        if s["watched_them_take"]
    ]
    assert non_empty, "no run leaves elder watching younger draw; add one"


def test_younger_alone_is_asked_to_answer_and_hears_only_a_shape(ovec):
    for run in ovec["runs"]:
        for s in run["snapshots"]:
            if s["awaiting_answer"] is None:
                continue
            assert s["me"] == "younger", "only younger answers a declaration"
            assert s["awaiting_answer"]["tiebreak"] is None, (
                "she hears the shape, never the tie-break"
            )


def test_observation_vector_file_is_self_describing(ovec):
    assert ovec["module"] == "observation"
    assert len(ovec["pack"]) == 32
    assert len(ovec["runs"]) >= 2
    for run in ovec["runs"]:
        assert run["snapshots"], run["name"]


# ===========================================================================
# partie -- six deals, the alternating deal, and the rubicon
# ===========================================================================


@pytest.fixture(scope="module")
def pvec() -> dict:
    return load("partie")


def _play_sheet(deals):
    from piquet.partie import Partie, Side

    partie = Partie(opening_dealer=Side.A)
    for elder, younger in deals:
        partie = partie.record_scores(elder, younger)
    return partie


def test_partie_constants(pvec):
    import piquet.partie as partie

    for name, value in pvec["constants"].items():
        assert getattr(partie, name) == value, name


def test_the_rubicon_decides_which_arithmetic_applies(pvec):
    """The guard is on the LOSER's score, not the winner's.

    A loser short of a hundred pays the *sum* plus a hundred, even when the
    winner fell short too -- so two players who crawl to 60 and 40 settle for
    200. That single clause is why maximising points in a deal is not the same
    thing as playing well: 105 to 101 pays 104, and a closer-looking 97 to 89
    pays nearly three times as much.
    """
    from piquet.partie import PARTIE_BONUS, RUBICON

    for case in pvec["cases"]:
        partie = _play_sheet(case["deals"] + case["extra"])
        settlement = partie.settlement
        want = case["settlement"]

        got_winner = None if settlement.winner is None else settlement.winner.name
        assert got_winner == want["winner"], case["name"]
        assert settlement.points == want["points"], case["name"]
        assert settlement.rubicon == want["rubicon"], case["name"]

        first, second = partie.totals
        assert {"A": first, "B": second} == case["totals"], case["name"]

        if settlement.winner is None:
            continue
        high, low = max(first, second), min(first, second)
        if low < RUBICON:
            assert settlement.points == high + low + PARTIE_BONUS
        else:
            assert settlement.points == high - low + PARTIE_BONUS


def test_a_winner_is_compared_with_is_none_not_truthiness(pvec):
    """`Side.A` is 0, and therefore falsy.

    The engine compares sides with `is` everywhere and is unaffected. The first
    draft of the vector generator did not, and quietly reported a drawn partie
    that in fact had a winner -- so this is pinned rather than left to be
    rediscovered by whoever next writes tooling against these types.
    """
    from piquet.partie import Side

    assert int(Side.A) == 0
    assert not bool(Side.A), "the trap itself"
    assert bool(Side.B)

    for case in pvec["cases"]:
        settlement = _play_sheet(case["deals"] + case["extra"]).settlement
        if case["settlement"]["winner"] == "A":
            assert settlement.winner is not None
            assert settlement.winner is Side.A


def test_a_level_partie_plays_two_more_deals_and_both_of_them(pvec):
    """Each player deals one, so neither gains the seat by breaking the tie."""
    from piquet.partie import DEALS_IN_PARTIE, EXTRA_DEALS

    for case in pvec["cases"]:
        if not case["extra"]:
            continue
        after_six = _play_sheet(case["deals"])
        assert after_six.totals[0] == after_six.totals[1], case["name"]
        assert not after_six.complete
        assert after_six.deals_left == EXTRA_DEALS

        after_seven = _play_sheet(case["deals"] + case["extra"][:1])
        assert not after_seven.complete, "the second extra deal is played too"

        full = _play_sheet(case["deals"] + case["extra"])
        assert full.complete
        assert len(full.outcomes) == DEALS_IN_PARTIE + EXTRA_DEALS


def test_the_seat_alternates_and_the_side_does_not(pvec):
    """`Player` is a chair and changes hands; `Side` is a person and does not.

    The two get confused exactly once, and expensively, because the rubicon is
    reckoned over a person's six deals rather than over a chair.
    """
    from piquet.partie import Partie, Side

    for case in pvec["alternation"]:
        partie = Partie(opening_dealer=Side[case["opening_dealer"]])
        got = [
            partie.elder_in(n).name for n in range(1, len(case["elder_by_deal"]) + 1)
        ]
        assert got == case["elder_by_deal"]
        assert got[0] != case["opening_dealer"], "the dealer is not elder"
        for a, b in zip(got, got[1:]):
            assert a != b, "the seat alternates every deal"


def test_the_progress_of_each_partie_matches(pvec):
    for case in pvec["cases"]:
        partie = _play_sheet([])
        for step in case["progress"]:
            standing = partie.standing
            assert partie.number == step["deal_number"], case["name"]
            assert partie.elder.name == step["elder_is"], case["name"]
            assert partie.deals_left == step["deals_left"], case["name"]
            assert standing.mine == step["standing"]["mine"]
            assert standing.theirs == step["standing"]["theirs"]
            assert standing.is_last_deal == step["standing"]["is_last_deal"]
            assert (
                standing.short_of_the_rubicon
                == step["standing"]["short_of_the_rubicon"]
            )
            elder, younger = step["scores_entered"]
            partie = partie.record_scores(elder, younger)


def test_a_settled_partie_takes_no_more_deals(pvec):
    for case in pvec["cases"]:
        partie = _play_sheet(case["deals"] + case["extra"])
        assert partie.complete
        with pytest.raises(ValueError):
            partie.record_scores(1, 1)


def test_partie_vector_file_is_self_describing(pvec):
    assert pvec["module"] == "partie"
    for section in ("constants", "cases", "alternation", "errors"):
        assert pvec[section], f"section {section!r} is empty"


# ===========================================================================
# solver -- exact endgame search
# ===========================================================================


@pytest.fixture(scope="module")
def solvec() -> dict:
    return load("solver")


def _position(case):
    from piquet.cards import Card
    from piquet.scoring import Player

    return (
        parse_hand(case["elder"]),
        parse_hand(case["younger"]),
        Player.ELDER if case["leader"] == "elder" else Player.YOUNGER,
        Card.parse(case["led"]) if case["led"] else None,
        case["elder_tricks"],
    )


def test_solver_constants(solvec):
    import piquet.solver as solver

    assert solver.TRICKS == solvec["constants"]["TRICKS"]
    assert solver.CARDS_BONUS == solvec["constants"]["CARDS_BONUS"]
    assert solver.CAPOT_BONUS == solvec["constants"]["CAPOT_BONUS"]
    assert list(solver.EVEN) == solvec["constants"]["EVEN"]


def test_the_default_path_is_integer_exact(solvec):
    """`EVEN` is `(1, 1)` -- two ints -- so no fraction is ever produced.

    Every type hint in `solver.py` says `float`, and Python's numeric tower
    quietly accepts either. A port must decide deliberately: `f64` is exact
    here by construction, but `i64` makes the exactness a fact about the type
    rather than an argument about the values.
    """
    from piquet.solver import solve

    for case in solvec["positions"]:
        value = solve(*_position(case))
        assert value == int(value), case["name"]
        assert isinstance(value, int) or value.is_integer()


def test_every_position_solves_to_its_recorded_value(solvec):
    """Values are elder-minus-younger: positive favours elder."""
    from piquet.solver import solve

    for case in solvec["positions"]:
        assert solve(*_position(case)) == case["value"], case["name"]


def test_the_cards_and_the_capot_are_scored_at_the_right_thresholds(solvec):
    """Ten for the cards, forty for a capot, nothing at six each.

    The capot cases are the ones worth having: they differ from the ordinary
    last trick by thirty points, and only in the running trick count.
    """
    by_name = {c["name"]: c for c in solvec["positions"]}
    ordinary = by_name["the last trick, elder holds the master"]
    capot = by_name["the last trick decides a capot"]
    level = by_name["six each, nothing in it"]

    assert capot["value"] - ordinary["value"] == 30, "forty for a capot, not ten"
    assert ordinary["value"] - level["value"] == 10, "ten for the cards"


def test_ducking_beats_cashing(solvec):
    """A measured lesson, pinned as data.

    `PLAN.md` records this among the beliefs the engine overturned: cashing an
    ace looks right and is not, because the ace takes the *last* trick, which
    is worth two. A port that reproduces every other value and gets this one
    wrong has a real strategic bug, not a rounding difference.
    """
    case = next(
        c for c in solvec["positions"] if c["name"].endswith("ducking beats cashing")
    )
    values = {c["card"]: c["value"] for c in case["card_values"]}
    assert values["7S"] > values["AS"], "ducking must beat cashing"
    assert case["best_card"] == "7S"


def test_the_chosen_card_is_one_of_the_best(solvec):
    from piquet.solver import best_card, card_values

    for case in solvec["positions"]:
        position = _position(case)
        chosen, value = best_card(*position)
        assert chosen.code == case["best_card"], case["name"]
        assert value == case["best_value"], case["name"]

        values = {c.code: v for c, v in card_values(*position).items()}
        assert values == {c["card"]: c["value"] for c in case["card_values"]}, (
            case["name"]
        )
        assert values[chosen.code] == max(values.values()) or values[
            chosen.code
        ] == min(values.values()), "the chosen card must be optimal for whoever acts"


def test_the_transposition_key_needs_more_than_a_double(solvec):
    """§2.1's worst hazard, pinned.

    The key packs two hands, a leader, a led card and a trick count into one
    integer with shifts up to 71, so it occupies 75 bits. JavaScript cannot
    build it with bitwise operators at all -- those top out at 32 -- and a
    double holds only 53 bits of integer exactly. Rust puts it in a `u128`.

    These are the one place in the vectors where a number travels as a string,
    for exactly that reason.
    """
    for case in solvec["memo_key"]["cases"]:
        key = (
            case["elder_bits"]
            | (case["younger_bits"] << 32)
            | (case["leader"] << 64)
            | ((case["led_index"] + 1) << 65)
            | (case["elder_tricks"] << 71)
        )
        assert str(key) == case["key"]
        assert key.bit_length() == case["bit_length"]
        assert key > 2**53, "otherwise this case is not testing the hazard"
    assert max(c["bit_length"] for c in solvec["memo_key"]["cases"]) > 64, (
        "no case exceeds 64 bits, so none of them needs a u128"
    )


def test_an_impossible_position_is_refused(solvec):
    """One subtraction, and the alternative is undebuggable.

    Given inconsistent hands the search runs a player out of cards, finds no
    legal move and returns `None`, which surfaces as a `TypeError` several
    frames deep in the recursion.
    """
    from piquet.cards import Card
    from piquet.scoring import Player
    from piquet.solver import solve

    assert len(solvec["errors"]) >= 2
    with pytest.raises(ValueError):
        solve(parse_hand("AS KS"), parse_hand("QS"), Player.ELDER, None, 0)
    with pytest.raises(ValueError):
        solve(
            parse_hand("AS KS"), parse_hand("QS JS"), Player.ELDER, Card.parse("7S"), 0
        )


def test_solver_vector_file_is_self_describing(solvec):
    assert solvec["module"] == "solver"
    for section in ("constants", "positions", "memo_key", "errors"):
        assert solvec[section], f"section {section!r} is empty"


# ===========================================================================
# The oracle checks its own vectors too
#
# These three sections were generated by the Python and replayed only by the
# Rust, which is the wrong way round. The Python is the oracle: if it drifts,
# a stale vector surfaces as a *Rust* failure and the wrong half gets blamed.
# ===========================================================================


@pytest.fixture(scope="module")
def cvec_chances() -> dict:
    return load("chances")


def test_the_fixed_seed_draws_are_still_these(cvec_chances):
    """`chances._futures` samples behind `random.Random(1674)`.

    Fixed so a position always values the same, which is also what let the
    Rust reproduce it at all. If CPython's generator ever changed under us,
    every weight below would move and nothing else would say so.
    """
    import random

    rng = random.Random(cvec_chances["rng_seed"])
    drawn = [rng.getrandbits(9) for _ in cvec_chances["rng_draws"]]
    assert drawn == cvec_chances["rng_draws"]


def test_settlement_is_integer_and_exact(cvec_chances):
    from piquet.chances import settlement_of

    for case in cvec_chances["settlements"]:
        assert settlement_of(case["mine"], case["theirs"]) == case["pays"]


def test_the_measured_densities_have_not_moved(cvec_chances):
    from piquet.chances import density, survival
    from piquet.scoring import Player

    tolerance = cvec_chances["tolerance"]
    for name, seat in (("elder", Player.ELDER), ("younger", Player.YOUNGER)):
        want = cvec_chances["densities"][name]
        rows = density(seat)
        assert len(rows) == want["length"]
        assert abs(sum(rows) - want["sum"]) < tolerance
        mean = sum(i * p for i, p in enumerate(rows))
        assert abs(mean - want["mean"]) < tolerance
        surviving = survival(seat)
        assert abs(surviving[0] - want["survival_at_zero"]) < tolerance
        assert abs(surviving[30] - want["survival_at_thirty"]) < tolerance


def test_the_odds_and_the_weights_have_not_moved(cvec_chances):
    from piquet.chances import chance_of, expected_settlement, in_words, point_weights

    tolerance = cvec_chances["tolerance"]
    for case in cvec_chances["chances"]:
        got = chance_of(case["needed"], case["deals_left"], case["elder_first"])
        assert abs(got - case["chance"]) < tolerance, case
        assert in_words(got) == case["in_words"]

    for case in cvec_chances["weights"]:
        args = (case["mine"], case["theirs"], case["deals_left"], case["elder_first"])
        assert (
            abs(expected_settlement(*args) - case["expected_settlement"]) < tolerance
        ), case
        mine, theirs = point_weights(*args)
        assert abs(mine - case["weight_mine"]) < tolerance, case
        assert abs(theirs - case["weight_theirs"]) < tolerance, case


@pytest.fixture(scope="module")
def hvec() -> dict:
    return load("heuristics")


def test_the_ladder_still_makes_these_decisions(hvec):
    """The agents, not merely the rules beneath them.

    Deterministic because erraticism is zero and BALANCED never sinks, which
    is the only seam through which a strategy can be pinned at all.
    """
    from piquet.heuristics import HeuristicAgent
    from piquet.match import play_deal
    from piquet.rules import deal_from
    from piquet.scoring import Player
    from piquet.style import BALANCED

    for game in hvec["games"]:
        pack = [Card.parse(code) for code in hvec["packs"][game["pack"]]]
        elder = HeuristicAgent(level=game["elder_level"], style=BALANCED, erraticism=0.0)
        younger = HeuristicAgent(
            level=game["younger_level"], style=BALANCED, erraticism=0.0
        )
        finished, _ = play_deal(elder, younger, deal=deal_from(pack))
        where = f"{game['pack']}: L{game['elder_level']} vs L{game['younger_level']}"

        assert finished.log.total(Player.ELDER) == game["elder_score"], where
        assert finished.log.total(Player.YOUNGER) == game["younger_score"], where
        assert finished.tricks_won(Player.ELDER) == game["elder_tricks"], where

        played = [t.led.code for t in finished.tricks] + [
            t.followed.code for t in finished.tricks
        ]
        assert played == game["cards_played"], where


def test_the_solver_agent_still_plays_these_cards():
    from piquet.heuristics import HeuristicAgent
    from piquet.match import play_deal
    from piquet.rules import deal_from
    from piquet.scoring import Player
    from piquet.solver import SolverAgent

    vec = load("solver")
    for game in vec["agent_games"]:
        pack = [Card.parse(code) for code in game["pack_codes"]]
        solver = SolverAgent(erraticism=0.0, name="solver8")
        ladder = HeuristicAgent(level=4, erraticism=0.0, name="L4")
        elder, younger = (
            (solver, ladder) if game["solver_seat"] == "elder" else (ladder, solver)
        )
        finished, _ = play_deal(elder, younger, deal=deal_from(pack))
        where = f"{game['pack']}: solver as {game['solver_seat']}"

        assert finished.log.total(Player.ELDER) == game["elder_score"], where
        assert finished.log.total(Player.YOUNGER) == game["younger_score"], where
        played = [t.led.code for t in finished.tricks] + [
            t.followed.code for t in finished.tricks
        ]
        assert played == game["cards_played"], where


# -- match: the move log ---------------------------------------------------------


def test_the_move_log_still_records_these_decisions():
    """The training log, decision by decision, compared as parsed JSON."""
    from piquet.heuristics import HeuristicAgent
    from piquet.match import DealRecord, play_deal
    from piquet.rules import deal_from
    from piquet.style import BALANCED

    vec = load("match")
    for game in vec["games"]:
        pack = [Card.parse(code) for code in vec["packs"][game["pack"]]]
        e, y = game["elder_level"], game["younger_level"]
        elder = HeuristicAgent(level=e, style=BALANCED, erraticism=0.0, name=f"L{e}")
        younger = HeuristicAgent(level=y, style=BALANCED, erraticism=0.0, name=f"L{y}")
        record = DealRecord(deal=3, elder_agent=elder.name, younger_agent=younger.name)
        _, record = play_deal(elder, younger, deal=deal_from(pack), record=record)
        line = json.dumps(record.as_dict(), separators=(",", ":"))
        assert json.loads(line) == game["record"], f"{game['pack']}: L{e} vs L{y}"


# -- tournament: the arithmetic of strength ----------------------------------------


def test_results_and_ratings_come_out_as_recorded():
    from piquet.tournament import DuelResult, PartieResult, format_table, ratings

    vec = load("tournament")
    for case in vec["properties"]:
        r = DuelResult(**case["result"])
        assert r.a_win_rate == pytest.approx(case["a_win_rate"], abs=1e-12), case
        assert r.margin == pytest.approx(case["margin"], abs=1e-12), case
        assert str(r) == case["text"]
    for case in vec["partie_properties"]:
        r = PartieResult(**case["result"])
        assert r.a_win_rate == pytest.approx(case["a_win_rate"], abs=1e-12), case
        assert r.margin == pytest.approx(case["margin"], abs=1e-12), case
        assert str(r) == case["text"]
    for table in vec["tables"]:
        group = [DuelResult(**r) for r in vec["results"][table["results"]]]
        assert format_table(group, anchor=table["anchor"]) == table["text"], table["results"]
    for fit in vec["fits"]:
        group = [DuelResult(**r) for r in vec["results"][fit["results"]]]
        got = ratings(group, anchor=fit["anchor"])
        assert got.keys() == fit["ratings"].keys(), fit
        for name, value in fit["ratings"].items():
            assert got[name] == pytest.approx(value, abs=1e-9), (fit["results"], fit["anchor"], name)
