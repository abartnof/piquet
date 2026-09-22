"""Tests for playing style, the third axis of an opponent.

Style is preference among roughly equal options. It must be EV-neutral, and it
must be *stable* -- drawn once per opponent, never re-rolled per decision.
"""

import random

import pytest

from piquet.style import BALANCED, Style


def test_the_neutral_style_sits_in_the_middle_and_never_sinks():
    assert BALANCED.discard_boldness == 0.5
    assert BALANCED.guard_retention == 0.5
    assert BALANCED.sinking == 0.0, "concealment is a choice, not a default"


def test_a_style_is_immutable_so_it_cannot_drift_mid_partie():
    style = Style(discard_boldness=0.8)
    with pytest.raises(Exception):
        style.discard_boldness = 0.2  # type: ignore[misc]


@pytest.mark.parametrize("field", ["discard_boldness", "sinking", "guard_retention"])
def test_every_dimension_is_bounded(field):
    with pytest.raises(ValueError, match=field):
        Style(**{field: 1.4})
    with pytest.raises(ValueError, match=field):
        Style(**{field: -0.1})


def test_a_random_style_is_reproducible_from_a_seed():
    assert Style.random(random.Random(7)) == Style.random(random.Random(7))


def test_random_styles_differ_from_one_another():
    rng = random.Random(1674)
    drawn = {Style.random(rng) for _ in range(20)}
    assert len(drawn) == 20


def test_even_bold_random_players_sink_sparingly():
    """Sinking is a costly manoeuvre; a style that concealed most of the time
    would be losing points, which would make it a skill level, not a style."""
    rng = random.Random(1674)
    assert all(Style.random(rng).sinking <= 0.5 for _ in range(200))


def test_a_style_describes_itself_so_a_habit_can_be_named():
    """The tutor needs to be able to say what an opponent tends to do, which is
    the inference Cavendish teaches: notice the habit, then exploit it."""
    bold = Style(discard_boldness=0.9, sinking=0.8, guard_retention=0.1)
    assert "bold discarder" in bold.describe()
    assert "secretive" in bold.describe()
    assert "runs its suits" in bold.describe()

    shy = Style(discard_boldness=0.1, sinking=0.0, guard_retention=0.9)
    assert "cautious discarder" in shy.describe()
    assert "open" in shy.describe()
    assert "hoards guards" in shy.describe()


def test_styles_compare_by_value():
    assert Style(sinking=0.3) == Style(sinking=0.3)
    assert Style(sinking=0.3) != Style(sinking=0.4)
