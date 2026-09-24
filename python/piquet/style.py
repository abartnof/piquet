"""Playing style: preference among roughly equal options.

Style is the third axis of an opponent, orthogonal to the other two:

- **Skill** is what the agent is capable of -- the ladder in `heuristics`.
- **Erraticism** is how consistently it brings that capability to bear.
- **Style** is which option it prefers among choices of roughly *equal value*.

That last clause is load-bearing. **A style must be close to EV-neutral.** If a
style reliably loses points it is not a style, it is a lower skill level wearing
a hat, and the two controls have smeared into each other. This is checkable
rather than a matter of taste, and `tournament` checks it.

It checked, and the first attempt failed. Measured at rung 4 over mirrored
pairs, against the neutral style, the margin per pair runs:

    discard_boldness   0.0  +2.05    guard_retention  0.0  +0.84
                       0.5   0.00                     0.5   0.00
                       1.0  -1.67                     1.0  -3.89

    sinking            0.0   0.00    0.2  -1.76    0.5  -4.14

So every dimension, at its extreme, was a skill penalty rather than a style.
`CALIBRATED` narrows each one to a band measured as costing about a point or
less, which is under a rung's worth (rung 3 to rung 4 is +1.7).

**Sinking is the interesting failure.** It is monotonically costly at every
setting, and it should be: concealment only has value against an opponent who
would otherwise have *used* what you concealed. The heuristic ladder barely
reads declarations, so silence buys nothing and the points are simply gone.
That is not a miscalibration to tune away -- it is the measurement confirming
why sinking belongs with the search and CFR rungs rather than here. Until an
opponent exists that punishes information, sinking stays a whisper.

The same logic caps how expressive style can be for now. A style needs several
*near-equal* options to choose between, and crude heuristics do not have them;
almost any change to them is simply better or worse play. Styles will widen as
the ladder gets stronger.

A style is drawn **once per opponent and held fixed**, never re-rolled per
decision -- a style that changes every move is just noise, and erraticism
already supplies that. Stability is the whole pedagogical point, and it comes
from Cavendish, whose worked example of spotting a sink opens: *"Your adversary,
for instance, is a player who rarely discards from his point."* That inference
only works against an opponent who **has** a persistent habit.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

__all__ = ["Style", "BALANCED"]


@dataclass(frozen=True, slots=True)
class Style:
    """How an opponent leans, on dimensions the historical sources identify.

    Every field runs 0.0 to 1.0, and 0.5 is the neutral setting. The dimensions
    are deliberately taken from what the literature argues about rather than
    invented: each is a genuine judgement call with defensible answers on both
    sides, which is what makes it a style rather than a mistake.
    """

    #: How readily it wrecks its point chasing a sequence or a set. The oldest
    #: strategic question in the game -- Hoyle wrote a treatise on it in 1744.
    #: 0.0 keeps length at all costs; 1.0 chases combinations.
    discard_boldness: float = 0.5

    #: How often it conceals a cheap declaration. Cavendish's central manoeuvre.
    #: 0.0 always declares everything; 1.0 sinks whenever it plausibly could.
    sinking: float = 0.0

    #: Whether it hoards stop cards in the opponent's long suit or plays for
    #: length. 0.0 runs its own suits; 1.0 holds guards back.
    guard_retention: float = 0.5

    def __post_init__(self) -> None:
        for name in self.__slots__:
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1, got {value}")

    @classmethod
    def random(cls, rng: random.Random | None = None) -> Style:
        """Draw a style. Call once per opponent, at the start of a partie.

        Drawn from `CALIBRATED`, not from the full 0-to-1 range: the bands are
        chosen by measurement so that no style costs much more than a point per
        deal, which keeps style from quietly becoming a skill setting.
        """
        rng = rng or random.Random()
        return cls(**{
            field: rng.uniform(low, high)
            for field, (low, high) in CALIBRATED.items()
        })

    def describe(self) -> str:
        """A short phrase for the tutor, so a habit can be named and read.

        The point is to let a human form the same inference Cavendish teaches:
        notice the habit across several deals, then exploit it.

        Bands are read *relative to the calibrated range*, not to the raw 0-to-1
        scale. They have to be: the calibrated bands are narrow enough to keep
        style EV-neutral, so on an absolute scale every opponent would be
        described as "even-handed" and the tutor would have nothing to say.
        What matters to a player is whether this opponent is bolder or shyer
        than the others they might meet.
        """
        def band(field: str, low: str, mid: str, high: str) -> str:
            start, end = CALIBRATED[field]
            span = end - start
            where = (getattr(self, field) - start) / span if span else 0.5
            return low if where < 0.34 else (mid if where < 0.67 else high)

        return " · ".join([
            band("discard_boldness", "cautious discarder", "even-handed",
                 "bold discarder"),
            band("sinking", "declares everything", "occasionally conceals",
                 "conceals what it can"),
            band("guard_retention", "runs its suits", "balanced",
                 "hoards guards"),
        ])

    def __str__(self) -> str:
        return self.describe()


#: Bands each dimension is drawn from, chosen by measurement rather than taste.
#: Every one is narrow enough that the cost of an extreme setting stays below
#: roughly a point per deal -- less than the gap between two rungs of the
#: ladder. Re-measure these whenever the ladder changes, since what counts as a
#: near-equal option depends on how well the agent plays.
CALIBRATED: dict[str, tuple[float, float]] = {
    "discard_boldness": (0.35, 0.65),
    "guard_retention": (0.35, 0.65),
    "sinking": (0.0, 0.10),
}

#: The neutral style. An agent given this one has no personality at all.
BALANCED = Style()
