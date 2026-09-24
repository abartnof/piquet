//! Small helpers that exist to reconcile two languages' tie-breaking.
//!
//! Python's `max` returns the **first** maximum; Rust's `max_by_key` returns
//! the **last**. Python's `min` and Rust's `min_by_key` both return the first,
//! so only the maximum needs reconciling -- which is exactly the kind of
//! asymmetry that produces a port passing every obvious test and playing a
//! different card once in a while. See `docs/DESIGN.md` §2.2.

/// `max(items, key=...)` with Python's tie-breaking: the first maximum wins.
pub(crate) fn first_max_by_key<T, K: Ord>(items: &[T], key: impl Fn(&T) -> K) -> Option<&T> {
    items.iter().rev().max_by_key(|item| key(item))
}

/// `min(items, key=...)`. Rust already agrees with Python here; the function
/// exists so call sites read symmetrically and nobody "simplifies" the one
/// above into it.
pub(crate) fn first_min_by_key<T, K: Ord>(items: &[T], key: impl Fn(&T) -> K) -> Option<&T> {
    items.iter().min_by_key(|item| key(item))
}

/// `max(items, key=...)` where the key is not `Ord` — a float, in practice.
///
/// Written as a comparator rather than a key because the obvious shortcut is
/// wrong: `f64::to_bits() as i64` looks like a cheap total order and is not
/// one for negative values. The bit pattern of `-2.0` compares *greater* than
/// that of `-1.0`, so an argmax over settlements — which are negative about
/// half the time — would silently prefer the worse move.
pub(crate) fn first_max_by<T>(
    items: &[T],
    compare: impl Fn(&T, &T) -> std::cmp::Ordering,
) -> Option<&T> {
    items.iter().rev().max_by(|a, b| compare(a, b))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_bit_pattern_shortcut_really_is_wrong() {
        // Recorded so nobody reintroduces it as a simplification. `black_box`
        // keeps the comparison out of const evaluation, which would otherwise
        // make it an assertion on constants.
        use std::cmp::Ordering;
        use std::hint::black_box;

        let smaller = black_box(-2.0f64);
        let larger = black_box(-1.0f64);

        assert_eq!(smaller.total_cmp(&larger), Ordering::Less, "numerically");
        assert_eq!(
            (smaller.to_bits() as i64).cmp(&(larger.to_bits() as i64)),
            Ordering::Greater,
            "but the other way round as bit patterns -- which is the trap"
        );
    }

    #[test]
    fn a_float_argmax_prefers_the_larger_value_and_the_earlier_tie() {
        let rows: [(&str, f64); 4] = [("a", -5.0), ("b", -1.0), ("c", -1.0), ("d", -9.0)];
        let best = first_max_by(&rows, |x, y| x.1.total_cmp(&y.1)).unwrap();
        assert_eq!(best.0, "b", "the first of the tied maxima");
    }
}
