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
