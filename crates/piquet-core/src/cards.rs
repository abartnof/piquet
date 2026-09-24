//! The 32-card piquet pack.
//!
//! A card is an index in `0..32`: `suit * 8 + (rank - 7)`. A hand is a bitmask
//! over those indices. The ace of spades is index 31, which in JavaScript makes
//! any hand holding it read as -2147483648; here the mask is a `u32` and the
//! question does not arise.

/// Ranks are stored as their piquet values so that sequence detection can
/// compare adjacent ranks directly. Seven is 7, ace is 14.
pub const RANK_SEVEN: u8 = 7;
pub const RANK_ACE: u8 = 14;

const RANK_CHARS: [u8; 8] = *b"789TJQKA";
const SUIT_LETTERS: [u8; 4] = *b"CDHS";
const SUIT_SYMBOLS: [char; 4] = ['♣', '♦', '♥', '♠'];

/// A rank, carried as its piquet value: seven is 7, ace is 14.
///
/// The values are consecutive so that sequence detection can compare adjacent
/// ranks directly, and `Card::index` is arithmetic on them.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct Rank(pub u8);

impl Rank {
    pub const SEVEN: Rank = Rank(7);
    pub const EIGHT: Rank = Rank(8);
    pub const NINE: Rank = Rank(9);
    pub const TEN: Rank = Rank(10);
    pub const JACK: Rank = Rank(11);
    pub const QUEEN: Rank = Rank(12);
    pub const KING: Rank = Rank(13);
    pub const ACE: Rank = Rank(14);

    pub const ALL: [Rank; 8] = [
        Rank(7),
        Rank(8),
        Rank(9),
        Rank(10),
        Rank(11),
        Rank(12),
        Rank(13),
        Rank(14),
    ];

    /// Value used to break a tie in point: ace 11, courts and tens 10.
    pub fn pip_value(self) -> u32 {
        if self == Rank::ACE {
            11
        } else if self >= Rank::TEN {
            10
        } else {
            u32::from(self.0)
        }
    }

    /// Jack, queen or king. A hand with none of these is a carte blanche; the
    /// ten is not a court card even though it counts towards sets.
    pub fn is_court(self) -> bool {
        Rank::JACK <= self && self <= Rank::KING
    }

    /// Tens and above. Nines and below never form a trio or quatorze.
    pub fn counts_for_set(self) -> bool {
        self >= Rank::TEN
    }

    /// The offset of this rank within a suit's byte.
    #[inline]
    pub fn offset(self) -> u8 {
        self.0 - RANK_SEVEN
    }

    /// How the rank is written for a reader: the ten spelled in full.
    pub fn label(self) -> String {
        if self == Rank::TEN {
            "10".to_string()
        } else {
            (RANK_CHARS[self.offset() as usize] as char).to_string()
        }
    }

    pub fn name(self) -> &'static str {
        match self.0 {
            7 => "seven",
            8 => "eight",
            9 => "nine",
            10 => "ten",
            11 => "jack",
            12 => "queen",
            13 => "king",
            _ => "ace",
        }
    }
}

/// A suit. Piquet has no trumps and no suit hierarchy, so a suit's index
/// exists only to give each card a stable slot.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct Suit(pub u8);

impl Suit {
    pub const CLUBS: Suit = Suit(0);
    pub const DIAMONDS: Suit = Suit(1);
    pub const HEARTS: Suit = Suit(2);
    pub const SPADES: Suit = Suit(3);
    pub const ALL: [Suit; 4] = [Suit(0), Suit(1), Suit(2), Suit(3)];

    #[inline]
    pub fn index(self) -> u8 {
        self.0
    }

    pub fn letter(self) -> char {
        SUIT_LETTERS[self.0 as usize] as char
    }

    pub fn symbol(self) -> char {
        SUIT_SYMBOLS[self.0 as usize]
    }
}

/// A card, stored as its index in `0..32`.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct Card(pub u8);

impl Card {
    pub fn new(rank: Rank, suit: Suit) -> Card {
        Card(suit.0 * 8 + rank.offset())
    }

    #[inline]
    pub fn index(self) -> u8 {
        self.0
    }

    #[inline]
    pub fn rank(self) -> Rank {
        Rank(self.0 % 8 + RANK_SEVEN)
    }

    #[inline]
    pub fn suit(self) -> Suit {
        Suit(self.0 / 8)
    }

    pub fn code(self) -> String {
        card_code(self.0)
    }

    pub fn parse(text: &str) -> Result<Card, String> {
        parse_card(text).map(Card)
    }

    /// How a card is written for a reader, e.g. `10♦`.
    ///
    /// Distinct from `code`, which is the two-character ASCII form used for
    /// serialisation. Both appear in the engine: the log's detail strings use
    /// this one, and the golden vectors record them, so a port that renders it
    /// differently fails on the first replay.
    pub fn display(self) -> String {
        format!("{}{}", self.rank().label(), self.suit().symbol())
    }
}

/// A set of cards, held as a 32-bit mask.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Default)]
pub struct Hand(pub u32);

impl Hand {
    pub const EMPTY: Hand = Hand(0);

    #[inline]
    pub fn len(self) -> u32 {
        self.0.count_ones()
    }

    #[inline]
    pub fn is_empty(self) -> bool {
        self.0 == 0
    }

    #[inline]
    pub fn contains(self, index: u8) -> bool {
        self.0 >> index & 1 == 1
    }

    /// Card indices, lowest first -- by suit, then ascending rank.
    ///
    /// The order is part of the engine's contract, not an implementation
    /// detail: several sorts elsewhere are stable and therefore depend on the
    /// order their input arrived in.
    pub fn iter(self) -> impl Iterator<Item = u8> {
        let mut bits = self.0;
        std::iter::from_fn(move || {
            if bits == 0 {
                return None;
            }
            // Clippy rejects the hand-rolled `bits & bits.wrapping_neg()`.
            let low = bits.isolate_lowest_one();
            bits ^= low;
            Some(low.trailing_zeros() as u8)
        })
    }

    /// Build a hand from cards, rejecting duplicates.
    pub fn of(cards: &[Card]) -> Result<Hand, String> {
        let mut bits = 0u32;
        for card in cards {
            let bit = 1u32 << card.0;
            if bits & bit != 0 {
                return Err(format!("duplicate card: {}", card.code()));
            }
            bits |= bit;
        }
        Ok(Hand(bits))
    }

    #[inline]
    pub fn holds(self, card: Card) -> bool {
        self.contains(card.0)
    }

    /// Just the cards of one suit. A mask, so it is cheap enough for the
    /// play-phase solver to call at every node.
    #[inline]
    pub fn in_suit(self, suit: Suit) -> Hand {
        Hand(self.0 & (0xFFu32 << (suit.0 * 8)))
    }

    /// The ranks held in one suit, highest first.
    pub fn ranks_in(self, suit: Suit) -> Vec<Rank> {
        let base = suit.0 * 8;
        (0..8)
            .rev()
            .filter(|offset| self.0 >> (base + offset) & 1 == 1)
            .map(|offset| Rank(offset + RANK_SEVEN))
            .collect()
    }

    /// How many suits this hand holds the given rank in.
    pub fn count_of(self, rank: Rank) -> u32 {
        Suit::ALL
            .iter()
            .filter(|suit| self.0 >> (suit.0 * 8 + rank.offset()) & 1 == 1)
            .count() as u32
    }

    /// Cards, in index order.
    pub fn cards(self) -> impl Iterator<Item = Card> {
        self.iter().map(Card)
    }

    /// Set difference, as in discarding. Lenient about absent cards.
    #[inline]
    pub fn without(self, other: Hand) -> Hand {
        Hand(self.0 & !other.0)
    }

    #[inline]
    pub fn intersect(self, other: Hand) -> Hand {
        Hand(self.0 & other.0)
    }

    /// Combine two disjoint hands, as in taking in from the talon.
    ///
    /// Strict about overlap: a card cannot be in two places at once, and
    /// silently merging would hide a dealing bug.
    pub fn union(self, other: Hand) -> Result<Hand, String> {
        if self.0 & other.0 != 0 {
            return Err(format!(
                "cards held twice: {}",
                Hand(self.0 & other.0).code()
            ));
        }
        Ok(Hand(self.0 | other.0))
    }

    /// Named `with_card` rather than `add`, which clippy flags as shadowing
    /// `std::ops::Add::add` for a method that is neither addition nor total.
    pub fn with_card(self, card: Card) -> Result<Hand, String> {
        if self.holds(card) {
            return Err(format!("already held: {}", card.code()));
        }
        Ok(Hand(self.0 | 1 << card.0))
    }

    pub fn remove(self, card: Card) -> Result<Hand, String> {
        if !self.holds(card) {
            return Err(format!("not held: {}", card.code()));
        }
        Ok(Hand(self.0 & !(1 << card.0)))
    }

    /// Parse a space-separated list of card codes, e.g. `"AS KS 7H"`.
    pub fn parse(text: &str) -> Result<Hand, String> {
        let mut bits = 0u32;
        for token in text.split_whitespace() {
            let index = parse_card(token)?;
            let bit = 1u32 << index;
            if bits & bit != 0 {
                return Err(format!("duplicate card: {token}"));
            }
            bits |= bit;
        }
        Ok(Hand(bits))
    }

    /// Space-separated codes in iteration order; round-trips through `parse`.
    pub fn code(self) -> String {
        self.iter().map(card_code).collect::<Vec<_>>().join(" ")
    }
}

/// Two-character ASCII form, e.g. `"AS"`.
pub fn card_code(index: u8) -> String {
    let rank = RANK_CHARS[(index % 8) as usize] as char;
    let suit = SUIT_LETTERS[(index / 8) as usize] as char;
    format!("{rank}{suit}")
}

/// Read a card index from its code. Accepts `"10S"` for `"TS"`, any case.
pub fn parse_card(text: &str) -> Result<u8, String> {
    let cleaned = text.trim().to_ascii_uppercase();
    let cleaned = if let Some(rest) = cleaned.strip_prefix("10") {
        format!("T{rest}")
    } else {
        cleaned
    };
    // Chars, not bytes: the suit may be given as its symbol, and those are
    // three bytes each in UTF-8. An earlier version indexed bytes and rejected
    // every symbol form -- and the golden test quietly skipped the non-ASCII
    // cases rather than failing, which is how the divergence survived.
    let chars: Vec<char> = cleaned.chars().collect();
    if chars.len() != 2 {
        return Err(format!("not a card: {text:?}"));
    }
    let rank = RANK_CHARS
        .iter()
        .position(|&c| c as char == chars[0])
        .ok_or_else(|| format!("not a rank in the piquet pack: {text:?}"))?;
    // If the table drew you a spade as ♠ it should accept ♠ back.
    let suit = SUIT_SYMBOLS
        .iter()
        .position(|&c| c == chars[1])
        .or_else(|| SUIT_LETTERS.iter().position(|&c| c as char == chars[1]))
        .ok_or_else(|| format!("not a suit: {text:?}"))?;
    Ok((suit * 8 + rank) as u8)
}

/// The 32 cards of the pack, in index order.
pub fn full_deck() -> impl Iterator<Item = u8> {
    0u8..32
}
