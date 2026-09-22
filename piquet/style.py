"""Playing style: preference among roughly equal options.

Style is the third axis of an opponent, orthogonal to the other two:

- **Skill** is what the agent is capable of -- the ladder in `heuristics`.
- **Erraticism** is how consistently it brings that capability to bear.
- **Style** is which option it prefers among choices of roughly *equal value*.

That last clause is load-bearing. **A style must be close to EV-neutral.** If a
style reliably loses points it is not a style, it is a lower skill level wearing
a hat, and the two controls have smeared into each other. This is checkable
rather than a matter of taste, and `tournament` checks it: two styles at the
same rung should rate within noise of each other.

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
        """Draw a style. Call once per opponent, at the start of a partie."""
        rng = rng or random.Random()
        return cls(
            discard_boldness=rng.random(),
            sinking=rng.random() * 0.5,   # even bold players sink sparingly
            guard_retention=rng.random(),
        )

    def describe(self) -> str:
        """A short phrase for the tutor, so a habit can be named and read.

        The point is to let a human form the same inference Cavendish teaches:
        notice the habit across several deals, then exploit it.
        """
        def band(value: float, low: str, mid: str, high: str) -> str:
            return low if value < 0.34 else (mid if value < 0.67 else high)

        return " · ".join([
            band(self.discard_boldness, "cautious discarder", "even-handed",
                 "bold discarder"),
            band(self.sinking, "open", "occasionally secretive", "secretive"),
            band(self.guard_retention, "runs its suits", "balanced",
                 "hoards guards"),
        ])

    def __str__(self) -> str:
        return self.describe()


#: The neutral style. An agent given this one has no personality at all.
BALANCED = Style()
