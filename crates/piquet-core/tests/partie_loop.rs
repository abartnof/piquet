//! `play_partie` exists in the library and nothing called it.
//!
//! Untested code in a library is a claim, not a feature. The CLI runs its own
//! loop because it has to interleave prompting, so this path had no user at
//! all -- which is exactly how a seat-swapping bug would survive.

use piquet_core::cards::Card;
use piquet_core::heuristics::HeuristicAgent;
use piquet_core::partie::{Side, DEALS_IN_PARTIE, PARTIE_BONUS, RUBICON};
use piquet_core::play::play_partie;
use piquet_core::rng::Rng;

fn packs(count: usize, seed: u32) -> Vec<Vec<Card>> {
    let mut rng = Rng::seeded(seed);
    (0..count)
        .map(|_| {
            let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
            rng.shuffle(&mut pack);
            pack
        })
        .collect()
}

#[test]
fn a_partie_runs_to_a_settlement() {
    let mut a = HeuristicAgent::new(4, 1).unwrap().named("A");
    let mut b = HeuristicAgent::new(2, 2).unwrap().named("B");
    let partie = play_partie(&packs(8, 1674), &mut a, &mut b, Side::A).unwrap();

    assert!(partie.complete());
    assert!(partie.outcomes.len() >= DEALS_IN_PARTIE);
    let settlement = partie.settlement().expect("a complete partie settles");

    let (first, second) = partie.totals();
    if first == second {
        assert_eq!(settlement.points, 0);
        assert!(settlement.winner.is_none());
    } else {
        let high = first.max(second);
        let low = first.min(second);
        let expected = if low < RUBICON {
            high + low + PARTIE_BONUS
        } else {
            high - low + PARTIE_BONUS
        };
        assert_eq!(settlement.points, expected);
    }
}

#[test]
fn the_seat_alternates_through_the_whole_partie() {
    // The distinction that gets confused exactly once, and expensively: a side
    // plays the partie, a seat changes hands every deal.
    let mut a = HeuristicAgent::new(3, 1).unwrap().named("A");
    let mut b = HeuristicAgent::new(3, 2).unwrap().named("B");
    let partie = play_partie(&packs(8, 99), &mut a, &mut b, Side::B).unwrap();

    let elders: Vec<Side> = partie.outcomes.iter().map(|o| o.elder).collect();
    assert_eq!(elders[0], Side::A, "the dealer is not elder");
    for pair in elders.windows(2) {
        assert_ne!(pair[0], pair[1], "the seat alternates every deal");
    }
}

#[test]
fn a_stronger_side_does_better_over_a_partie() {
    // Not a strength claim -- one partie is far too few for that. It is a
    // smoke test that the seats are wired the right way round: a rung-4 agent
    // against rung 1 should not be losing, and if the seat mapping were
    // inverted it would be.
    let mut strong = HeuristicAgent::new(4, 7).unwrap().named("strong");
    let mut weak = HeuristicAgent::new(1, 8).unwrap().named("weak");
    let partie = play_partie(&packs(8, 4242), &mut strong, &mut weak, Side::A).unwrap();
    let (strong_total, weak_total) = partie.totals();
    assert!(
        strong_total > weak_total,
        "rung 4 scored {strong_total} against rung 1's {weak_total}"
    );
}

/// pagat's own worked settlements: "the scores are A:99, B:120. Player A pays
/// 319 to player B" and "A:101, B:120. Player A pays 119".
#[test]
fn pagats_worked_settlements() {
    use piquet_core::partie::Partie;
    for (loser, pays, rubiconed) in [(99, 319, true), (101, 119, false)] {
        let mut partie = Partie::new(Side::A);
        partie = partie.record_scores(loser, 120).unwrap();
        for _ in 1..DEALS_IN_PARTIE {
            partie = partie.record_scores(0, 0).unwrap();
        }
        let settlement = partie.settlement().expect("six deals, unequal: settled");
        assert_eq!(settlement.points, pays, "{loser} to 120");
        assert_eq!(settlement.rubicon, rubiconed);
    }
}

/// "If the scores are equal after 6 deals, two more hands are played. If they
/// are then still equal the partie is a draw."
#[test]
fn a_level_partie_plays_two_more_deals_then_may_be_drawn() {
    use piquet_core::partie::Partie;
    let mut partie = Partie::new(Side::A);
    for _ in 0..DEALS_IN_PARTIE {
        partie = partie.record_scores(20, 20).unwrap();
    }
    assert!(!partie.complete(), "level after six: two more");
    assert_eq!(partie.deals_left(), 2);
    partie = partie.record_scores(30, 0).unwrap();
    assert!(
        !partie.complete(),
        "both extra deals are played, whatever the first"
    );
    partie = partie.record_scores(30, 0).unwrap();
    let settlement = partie.settlement().expect("eight deals: settled");
    assert!(settlement.winner.is_none(), "level again: a draw");
    assert_eq!(settlement.points, 0);
}
