"""The piquet pack: ranks, suits, cards, and hands.

The pack is 32 cards -- A K Q J 10 9 8 7 in each suit, ace high. Suits carry no
game meaning: piquet has no trumps and no suit hierarchy, so a suit's index
exists only to give each card a stable slot.

A `Hand` is a 32-bit mask behind a small immutable interface. That keeps the
representation cheap enough for the exact play-phase solver (docs/DESIGN.md
section 6.1) while reading like a set at the call site.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterator

__all__ = ["Rank", "Suit", "Card", "Hand", "full_deck", "parse_hand"]

_RANK_CHARS = "789TJQKA"
_SUIT_LETTERS = "CDHS"
_SUIT_SYMBOLS = "♣♦♥♠"


class Rank(IntEnum):
    """Ranks from seven to ace.

    The integer values are consecutive so that sequence detection can simply
    compare adjacent ranks.
    """

    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def pip_value(self) -> int:
        """Value used to break a tie in point: ace 11, courts and tens 10."""
        if self is Rank.ACE:
            return 11
        return 10 if self >= Rank.TEN else int(self)

    @property
    def is_court(self) -> bool:
        """Jack, queen or king. A hand with none of these is a carte blanche.

        The ten is not a court card, even though it counts towards sets.
        """
        return Rank.JACK <= self <= Rank.KING

    @property
    def counts_for_set(self) -> bool:
        """Tens and above. Nines and below never form a trio or quatorze."""
        return self >= Rank.TEN

    @property
    def char(self) -> str:
        return _RANK_CHARS[self - Rank.SEVEN]

    @property
    def label(self) -> str:
        """How the rank is written for a reader: the ten spelled in full."""
        return "10" if self is Rank.TEN else self.char


class Suit(IntEnum):
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3

    @property
    def index(self) -> int:
        return int(self)

    @property
    def letter(self) -> str:
        return _SUIT_LETTERS[self]

    @property
    def symbol(self) -> str:
        return _SUIT_SYMBOLS[self]


@dataclass(frozen=True, slots=True)
class Card:
    rank: Rank
    suit: Suit

    @property
    def index(self) -> int:
        """A stable slot in 0..31, used as the bit position within a `Hand`."""
        return self.suit.index * 8 + (self.rank - Rank.SEVEN)

    @classmethod
    def from_index(cls, index: int) -> Card:
        if not 0 <= index < 32:
            raise ValueError(f"card index out of range: {index}")
        suit, offset = divmod(index, 8)
        return cls(Rank(Rank.SEVEN + offset), Suit(suit))

    @property
    def code(self) -> str:
        """Two-character ASCII form, e.g. "AS". Canonical for serialisation."""
        return f"{self.rank.char}{self.suit.letter}"

    @classmethod
    def parse(cls, text: str) -> Card:
        """Read a card from its code.

        Forgiving on purpose, because this is what a person types. "10S" and
        "TS" are the same card, case does not matter, and the suit may be
        given as its **symbol** as well as its letter -- if the table drew you
        a spade as ♠ it should accept ♠ back.
        """
        cleaned = text.strip().upper()
        if cleaned.startswith("10"):
            cleaned = "T" + cleaned[2:]
        if len(cleaned) != 2:
            raise ValueError(f"not a card: {text!r}")
        rank_char, suit_char = cleaned
        if rank_char not in _RANK_CHARS:
            raise ValueError(f"not a rank in the piquet pack: {text!r}")
        if suit_char in _SUIT_SYMBOLS:
            suit = Suit(_SUIT_SYMBOLS.index(suit_char))
        elif suit_char in _SUIT_LETTERS:
            suit = Suit(_SUIT_LETTERS.index(suit_char))
        else:
            raise ValueError(f"not a suit: {text!r}")
        return cls(Rank(Rank.SEVEN + _RANK_CHARS.index(rank_char)), suit)

    def __str__(self) -> str:
        return f"{self.rank.label}{self.suit.symbol}"


def full_deck() -> tuple[Card, ...]:
    """The 32 cards of the piquet pack, in index order."""
    return tuple(Card.from_index(i) for i in range(32))


@dataclass(frozen=True, slots=True)
class Hand:
    """An immutable set of cards, held as a 32-bit mask.

    Iteration is in index order -- by suit, then ascending rank -- so any
    rendering of a hand is stable.
    """

    bits: int = 0

    @classmethod
    def empty(cls) -> Hand:
        return cls(0)

    @classmethod
    def of(cls, *cards: Card) -> Hand:
        bits = 0
        for card in cards:
            bit = 1 << card.index
            if bits & bit:
                raise ValueError(f"duplicate card: {card.code}")
            bits |= bit
        return cls(bits)

    def __len__(self) -> int:
        return self.bits.bit_count()

    def __bool__(self) -> bool:
        return self.bits != 0

    def __contains__(self, card: Card) -> bool:
        return bool(self.bits >> card.index & 1)

    def __iter__(self) -> Iterator[Card]:
        bits = self.bits
        while bits:
            low = bits & -bits
            yield Card.from_index(low.bit_length() - 1)
            bits ^= low

    def add(self, card: Card) -> Hand:
        if card in self:
            raise KeyError(f"already held: {card.code}")
        return Hand(self.bits | 1 << card.index)

    def remove(self, card: Card) -> Hand:
        if card not in self:
            raise KeyError(f"not held: {card.code}")
        return Hand(self.bits & ~(1 << card.index))

    def __sub__(self, other: Hand) -> Hand:
        """Set difference, as in discarding. Lenient about absent cards."""
        return Hand(self.bits & ~other.bits)

    def __and__(self, other: Hand) -> Hand:
        return Hand(self.bits & other.bits)

    def __or__(self, other: Hand) -> Hand:
        """Combine two disjoint hands, as in taking in from the talon.

        Strict about overlap: a card cannot be in two places at once, and
        silently merging would hide a dealing bug.
        """
        if self.bits & other.bits:
            shared = Hand(self.bits & other.bits)
            raise KeyError(f"cards held twice: {shared.code}")
        return Hand(self.bits | other.bits)

    def in_suit(self, suit: Suit) -> Hand:
        """Just the cards of one suit. A mask, so it is cheap enough for the
        play-phase solver to call on every node."""
        return Hand(self.bits & (0xFF << (suit.index * 8)))

    def ranks_in(self, suit: Suit) -> list[Rank]:
        """The ranks held in one suit, highest first."""
        base = suit.index * 8
        return [
            Rank(Rank.SEVEN + offset)
            for offset in range(7, -1, -1)
            if self.bits >> (base + offset) & 1
        ]

    def count_of(self, rank: Rank) -> int:
        """How many suits this hand holds the given rank in."""
        offset = rank - Rank.SEVEN
        return sum(1 for suit in Suit if self.bits >> (suit.index * 8 + offset) & 1)

    @property
    def code(self) -> str:
        """Space-separated ASCII codes; parses back via `parse_hand`."""
        return " ".join(card.code for card in self)

    def __str__(self) -> str:
        return " ".join(str(card) for card in self)


def parse_hand(text: str) -> Hand:
    """Build a hand from readable text such as "AS KS QS 7H"."""
    return Hand.of(*(Card.parse(token) for token in text.split()))
