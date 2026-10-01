"""The phrase bank: everything a player says at the table, for the
declarations' dialogue boxes -- each phrase in several ways, so that the
boxes do not repeat themselves (the user: "i don't want *any* sounds to be
repetitive", said of the voice the bank was first made for). The wordings
come from the period books (docs/PHRASES.md)."""

from pathlib import Path

from phrases import (
    HIGHEST_COUNT,
    SOURCES,
    document,
    files,
    groups,
    phrase_groups,
    sequence_calls,
    words,
    words_json,
)

DOC = Path(__file__).resolve().parents[2] / "docs" / "PHRASES.md"
WORDS = Path(__file__).resolve().parents[1] / "words.json"

# Every point a hand can hold is worth one of these (7+8+9 = 24 at the
# least, the whole suit 75 at the most).
POINT_VALUES = [*range(24, 32), *range(34, 42), *range(44, 52), *range(54, 61), *range(64, 69), 75]
# A point may be called short -- the engine has been heard to call two cards
# -- so the smaller ones too: one card 7 to 11, two 15 to 21.
SHORT_POINTS = [*range(7, 12), *range(15, 22)]


def texts(gid):
    return [files()[key] for key in groups()[gid]]


def test_every_phrase_is_said_in_more_than_one_way():
    for gid, ways in phrase_groups():
        assert len(ways) >= 2, gid


def test_the_ways_of_saying_a_thing_differ_in_words():
    for gid in groups():
        assert len(set(texts(gid))) == len(texts(gid)), gid


def test_what_is_said_most_has_the_most_ways():
    # Measured over simulated parties: "Good." eight times a partie, "Not
    # good." five.
    assert len(groups()["good"]) >= 8
    assert len(groups()["not-good"]) >= 6


def test_the_users_own_examples_are_in_the_bank():
    assert "Ah, not good." in texts("not-good")
    assert "Not good!" in texts("not-good")


def test_the_period_forms_are_in_the_bank():
    assert "I only take four." in texts("take-4")  # Cavendish
    assert "I take only four." in texts("take-4")  # Cady
    assert "I leave a card." in texts("take-4")  # both
    assert "What do they make?" in texts("what-make")  # Cavendish
    assert "How many?" in texts("what-make")  # Cady
    assert "Five cards." in texts("point-5")
    assert "Quatorze aces." in texts("set-4-ace")  # Foster
    assert "Equal." in texts("equal")


def test_the_sequences_are_the_twenty_one_that_can_be_held():
    calls = dict(sequence_calls())
    assert len(calls) == 21
    # Ranks run seven to ace: a tierce tops at ace down to nine, a huitième
    # only at the ace. Cavendish's form comes first.
    assert calls["seq-3-ace"] == "A tierce major"
    assert calls["seq-3-nine"] == "A tierce minor"
    assert calls["seq-4-queen"] == "A quart to a queen"
    assert calls["seq-5-knave"] == "A quint minor"
    assert calls["seq-8-ace"] == "A huitième"
    assert "seq-8-king" not in calls and "seq-3-eight" not in calls
    assert texts("seq-5-ace")[0] == "A quint major."
    assert len({gid for gid in groups() if gid.startswith("seq-") and gid.count("-") == 2}) == 21


def test_the_sets_are_trios_and_quatorzes_of_tens_and_above():
    sets = {gid for gid in groups() if gid.startswith("set-") and gid.count("-") == 2}
    assert len(sets) == 10
    assert texts("set-4-ace")[0] == "Four aces." and texts("set-3-knave")[0] == "Three knaves."


def test_the_shapes_are_called_bare_and_the_tie_breaks_asked_for():
    # Elder gives no more than he must: "A quart." Younger, holding the
    # same, asks: "What do they make?", "How high?", "Of what?" (Cavendish,
    # pp. 60-67; speech.js).
    assert "A quart." in texts("seq-4") and "A sixième." in texts("seq-6")
    assert {f"seq-{n}" for n in range(3, 9)} <= set(groups())
    assert "A trio." in texts("set-3") and "A quatorze." in texts("set-4")
    assert "How high?" in texts("how-high")
    assert "Of what?" in texts("what-set")


def test_every_number_a_deal_can_reach_is_said_one_way():
    said = {gid for gid in groups() if gid.startswith("n-")}
    assert said == {f"n-{n}" for n in range(1, HIGHEST_COUNT + 1)}
    assert texts("n-48") == ["Forty-eight."]
    assert words(48) == "forty-eight"
    assert words(94) == "ninety-four"
    assert words(100) == "a hundred"
    assert words(170) == "a hundred and seventy"
    assert words(104) == "a hundred and four"


def test_a_point_value_is_said_as_a_number_or_as_what_it_is_making():
    # Cavendish: "Forty-nine," or "Making nine." Cady: "Forty-seven," or
    # "Making seven." Only in the forties, where both his examples are.
    for value in POINT_VALUES:
        keys = groups()[f"value-{value}"]
        assert set(groups()[f"n-{value}"]) <= set(keys), value
    assert texts("value-49") == ["Forty-nine.", "Making nine."]
    assert "Making seven." in texts("value-47")
    assert texts("value-51") == ["Fifty-one."]
    assert texts("value-38") == ["Thirty-eight."]


def test_a_point_called_short_is_said_too():
    assert "Two cards." in texts("point-2") and "One card." in texts("point-1")
    for value in SHORT_POINTS:
        assert f"value-{value}" in groups(), value


def test_the_dialogue_boxes_words_are_written_from_the_bank():
    # The build embeds web3d/words.json in the page; `phrases.py` writes it
    # with the doc.
    assert WORDS.read_text() == words_json()


def test_every_wording_is_used_and_every_one_used_exists():
    used = {key for keys in groups().values() for key in keys}
    assert used == set(files())


def test_every_wording_says_where_it_comes_from():
    for gid, variants in phrase_groups():
        for text, source in variants:
            assert source in SOURCES, (gid, text, source)


def test_the_niceties_are_there():
    assert "Congratulations!" in texts("congratulations")
    assert "Good game." in texts("good-game")
    assert "Well played." in texts("well-played")


def test_the_phrases_are_written_down_in_the_docs():
    # docs/PHRASES.md is generated from the bank; regenerate it with
    # `phrases.py` when the bank changes.
    assert DOC.read_text() == document()
