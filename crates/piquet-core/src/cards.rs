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
    let bytes = cleaned.as_bytes();
    if bytes.len() != 2 {
        return Err(format!("not a card: {text:?}"));
    }
    let rank = RANK_CHARS
        .iter()
        .position(|&c| c == bytes[0])
        .ok_or_else(|| format!("not a rank in the piquet pack: {text:?}"))?;
    let suit = SUIT_LETTERS
        .iter()
        .position(|&c| c == bytes[1])
        .ok_or_else(|| format!("not a suit: {text:?}"))?;
    Ok((suit * 8 + rank) as u8)
}

/// The 32 cards of the pack, in index order.
pub fn full_deck() -> impl Iterator<Item = u8> {
    0u8..32
}
