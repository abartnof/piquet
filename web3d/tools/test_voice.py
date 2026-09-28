"""The voice's phrase bank: everything a player says at the table, each in
several ways, so that nothing is heard the same way twice running (Andrew:
"i don't want *any* sounds to be repetitive"). The wordings come from the
period books (docs/VOICE.md, docs/PHRASES.md)."""

from pathlib import Path

from voice import (
    HIGHEST_COUNT,
    RESPELL,
    SOURCES,
    document,
    files,
    groups,
    phrase_groups,
    sequence_calls,
    speakable,
    words,
)

DOC = Path(__file__).resolve().parents[2] / "docs" / "PHRASES.md"

# Every point a hand can hold is worth one of these (7+8+9 = 24 at the
# least, the whole suit 75 at the most).
POINT_VALUES = [*range(24, 32), *range(34, 42), *range(44, 52), *range(54, 61), *range(64, 69), 75]


def texts(gid):
    return [files()[key]["text"] for key in groups()[gid]]


def test_nothing_is_said_only_one_way():
    for gid, keys in groups().items():
        assert len(keys) >= 2, gid


def test_the_ways_of_saying_a_thing_differ_in_words_or_in_delivery():
    for gid, keys in groups().items():
        takes = [(files()[k]["text"], files()[k]["pace"]) for k in keys]
        assert len(set(takes)) == len(takes), gid


def test_what_is_heard_most_has_the_most_ways():
    # Measured over simulated parties: "Good." eight times a partie, "Not
    # good." five; a number between one and forty a few times; a large one
    # hardly ever.
    assert len(groups()["good"]) >= 8
    assert len(groups()["not-good"]) >= 6
    assert all(len(groups()[f"n-{n}"]) == 3 for n in range(1, 41))
    assert all(len(groups()[f"n-{n}"]) == 2 for n in range(41, HIGHEST_COUNT + 1))


def test_andrews_own_examples_are_in_the_bank():
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
    assert len({gid for gid in groups() if gid.startswith("seq-")}) == 21


def test_the_sets_are_trios_and_quatorzes_of_tens_and_above():
    sets = {gid for gid in groups() if gid.startswith("set-")}
    assert len(sets) == 10
    assert texts("set-4-ace")[0] == "Four aces." and texts("set-3-knave")[0] == "Three knaves."


def test_every_number_a_deal_can_reach_is_said():
    said = {gid for gid in groups() if gid.startswith("n-")}
    assert said == {f"n-{n}" for n in range(1, HIGHEST_COUNT + 1)}
    assert set(texts("n-48")) == {"Forty-eight."}  # the same words, several takes
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
    assert "Making nine." in texts("value-49")
    assert "Making seven." in texts("value-47")
    assert not any(t.startswith("Making") for t in texts("value-51"))
    assert not any(t.startswith("Making") for t in texts("value-38"))


def test_every_recording_is_heard_and_every_one_heard_is_recorded():
    used = {key for keys in groups().values() for key in keys}
    assert used == set(files())


def test_the_hard_words_reach_the_voice_as_english_it_already_knows():
    # Raw phonemes made the male voice babble on "capot" -- Andrew heard it
    # and checked it -- so every French term is respelled as plain English
    # (his suggestion: "english homonyms"), which each voice says through
    # its own trained path, in its own accent.
    for key, spec in files().items():
        spoken = speakable(spec["text"])
        assert "[[" not in spoken, (key, spoken)
        for word in RESPELL:
            assert word not in spoken.lower().split(), (key, spoken)
    assert speakable("Capot!") == "Kuh-pot!"
    assert speakable("A quart major.") == "A cart major."
    assert speakable("Quatorze aces.") == "Kuh-torz aces."
    assert speakable("A huitième, the whole suit.") == "A wheat yem, the whole suit."
    assert speakable("Four quatorzes") == "Four quatorzes"  # whole words only
    assert speakable("A tierce minor.") == "A tierce minor."


def test_every_wording_says_where_it_comes_from():
    for gid, variants in phrase_groups():
        for text, source in variants:
            assert source in SOURCES, (gid, text, source)


def test_the_niceties_are_there():
    assert "Congratulations!" in texts("congratulations")
    assert "Good game." in texts("good-game")
    assert "Well played." in texts("well-played")


def test_the_phrases_are_written_down_in_the_docs():
    # Andrew: "remember to write these phrases down somewhere local as
    # well". docs/PHRASES.md is generated from the bank; regenerate it with
    # `voice.py --doc` when the bank changes.
    assert DOC.read_text() == document()
