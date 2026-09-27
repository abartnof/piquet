"""The voice's inventory: everything a player says at the table, no more
and nothing missing (docs/VOICE.md; Cavendish, 1885)."""

from voice import HIGHEST_COUNT, PRONOUNCE, inventory, sequence_calls, speakable, words


def test_every_phrase_has_a_unique_id():
    ids = [pid for pid, _ in inventory()]
    assert len(ids) == len(set(ids))


def test_the_sequences_are_the_twenty_one_that_can_be_held():
    calls = dict(sequence_calls())
    assert len(calls) == 21
    # Ranks run seven to ace: a tierce tops at ace down to nine, a huitième
    # only at the ace.
    assert calls["seq-3-ace"] == "A tierce major"
    assert calls["seq-3-nine"] == "A tierce minor"
    assert calls["seq-4-queen"] == "A quart to a queen"
    assert calls["seq-5-knave"] == "A quint minor"
    assert calls["seq-8-ace"] == "A huitième"
    assert "seq-8-king" not in calls and "seq-3-eight" not in calls


def test_the_sets_are_trios_and_quatorzes_of_tens_and_above():
    sets = {pid: text for pid, text in inventory() if pid.startswith("set-")}
    assert len(sets) == 10
    assert sets["set-4-ace"] == "Four aces." and sets["set-3-knave"] == "Three knaves."


def test_every_number_a_deal_can_reach_is_said():
    said = {pid for pid, _ in inventory() if pid.startswith("n-")}
    assert said == {f"n-{n}" for n in range(1, HIGHEST_COUNT + 1)}
    assert words(48) == "forty-eight"
    assert words(94) == "ninety-four"
    assert words(100) == "a hundred"
    assert words(170) == "a hundred and seventy"
    assert words(104) == "a hundred and four"


def test_the_point_values_are_all_said():
    # A point is worth 24-31, 34-41, 44-51, 54-60, 64-68 or 75: all are
    # numbers the counting bank already says.
    said = {pid for pid, _ in inventory()}
    for value in [*range(24, 32), *range(34, 42), *range(44, 52), *range(54, 61), *range(64, 69), 75]:
        assert f"n-{value}" in said


def test_the_hard_words_reach_the_voice_as_phonemes():
    for pid, text in inventory():
        spoken = speakable(text)
        for word in PRONOUNCE:
            assert word not in spoken.lower().replace("[[", "").split("]]")[-1], (pid, spoken)
    assert speakable("Four quatorzes") == "Four quatorzes"  # whole words only
    # Punctuation and an article go inside the block, or the voice reads
    # them as "exclamation" and the letter "A".
    assert speakable("Capot!") == "[[kəpˈɒt!]]"
    assert speakable("A quart major.") == "[[ɐ kˈɑːt]] major."
    assert speakable("A tierce minor.") == "A tierce minor."


def test_the_niceties_are_there():
    said = dict(inventory())
    assert said["congratulations"] == "Congratulations!"
    assert said["good-game"] == "Good game."
