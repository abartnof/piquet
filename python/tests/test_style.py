"""Tests for playing style, the third axis of an opponent.

Style is preference among roughly equal options. It must be EV-neutral, and it
must be *stable* -- drawn once per opponent, never re-rolled per decision.
"""

import random

import pytest

from piquet.style import BALANCED, CALIBRATED, Style


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


def test_even_the_most_secretive_opponent_only_whispers():
    """Sinking was measured costing points at every setting, because silence is
    only worth something against an opponent who would have used what you hid.
    Until such an opponent exists, the habit stays a whisper."""
    rng = random.Random(1674)
    assert all(Style.random(rng).sinking <= 0.10 for _ in range(200))


def test_a_style_describes_itself_so_a_habit_can_be_named():
    """The tutor needs to be able to say what an opponent tends to do, which is
    the inference Cavendish teaches: notice the habit, then exploit it."""
    bold = Style(discard_boldness=0.65, sinking=0.10, guard_retention=0.35)
    assert "bold discarder" in bold.describe()
    assert "conceals what it can" in bold.describe()
    assert "runs its suits" in bold.describe()

    shy = Style(discard_boldness=0.35, sinking=0.0, guard_retention=0.65)
    assert "cautious discarder" in shy.describe()
    assert "declares everything" in shy.describe()
    assert "hoards guards" in shy.describe()


def test_descriptions_are_read_relative_to_the_calibrated_band():
    """They have to be. The calibrated bands are narrow enough to keep style
    EV-neutral, so on an absolute 0-to-1 scale every opponent would come out
    "even-handed" and the tutor would have nothing to say."""
    low, high = CALIBRATED["discard_boldness"]
    assert "cautious discarder" in Style(discard_boldness=low).describe()
    assert "bold discarder" in Style(discard_boldness=high).describe()
    assert low > 0.0 and high < 1.0, "the band is narrower than the raw range"


def test_random_styles_stay_inside_the_calibrated_bands():
    """Outside them a style stops being EV-neutral and quietly becomes a skill
    setting -- guard retention at 1.0 was measured costing 3.9 points a deal."""
    rng = random.Random(1674)
    for _ in range(200):
        style = Style.random(rng)
        for field, (low, high) in CALIBRATED.items():
            assert low <= getattr(style, field) <= high


def test_styles_compare_by_value():
    assert Style(sinking=0.3) == Style(sinking=0.3)
    assert Style(sinking=0.3) != Style(sinking=0.4)
