"""The full count of what the table could say (utterances.py): every event,
every answer, every transition, derived from the rules."""

from utterances import belongs, sequence_lists, set_lists, tally, utterances
from voice import HIGHEST_COUNT


def said(scenario, voice="opponent"):
    return {u[3] for u in utterances() if belongs(scenario, u[0]) and u[1] in ("either", voice)}


def test_every_sequence_and_set_a_hand_can_hold():
    single = {h for held in sequence_lists() for h in held}
    assert len(single) == 21  # tierce to the nine ... the huitième
    assert ((8, 7),) in sequence_lists()
    assert ((3, 6), (3, 6), (3, 2), (3, 2)) in sequence_lists()  # four tierces: twelve cards
    assert not any(sum(n for n, _ in held) > 12 for held in sequence_lists())
    assert ((4, 4), (4, 3), (4, 2)) in set_lists() and len(set_lists()) == 135


def test_the_phrases_say_every_count_holding_and_moment():
    lines = said("phrases")
    assert all(f"{w.capitalize()}." in lines for w in ["one", "forty-eight", "a hundred and seventy"])
    assert "A quart to a king." in lines and "Three aces." in lines and "Four tens." in lines
    for moment in ["Shall we play? Cut for the deal.", "Congratulations! Well played.", "Oh well. Maybe next time.", "What do they make?", "How high?", "Of what?"]:
        assert moment in lines, moment
    assert "Good game." in said("phrases", "player")


def test_maximal_is_the_most_and_phrases_the_least():
    counts = tally()
    for voice in ("opponent", "player"):
        assert counts["maximal", voice][0] > counts["split", voice][0] > counts["phrases", voice][0]
    assert len({t for t in said("maximal") if t.startswith("And the cards: ")}) == HIGHEST_COUNT - 10
