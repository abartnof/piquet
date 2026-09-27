//! What each card is worth to the solver, reported exactly as it plays by it.
//!
//! `SolverAgent::estimates` exposes the values the search averages over the
//! opponent hands it samples, so an instrument can ask *why* a card was
//! played and a tutor can one day say so. That is only honest if the card the
//! agent plays is the best of what it reports: the same worlds, drawn from the
//! same generator, and the same tie-break.

use piquet_core::agents::Agent;
use piquet_core::cards::{Card, Hand};
use piquet_core::declarations::Declaration;
use piquet_core::observation::View;
use piquet_core::partie::Standing;
use piquet_core::play::play_deal;
use piquet_core::rng::Rng;
use piquet_core::rules::deal_from;
use piquet_core::scoring::Category;
use piquet_core::solver::SolverAgent;

/// A solver that, before every play, asks an identical copy of itself what
/// the cards are worth, and checks the answer against what it then plays.
struct Checked {
    inner: SolverAgent,
    searched: usize,
    declined: usize,
}

impl Checked {
    fn new(inner: SolverAgent) -> Checked {
        Checked {
            inner,
            searched: 0,
            declined: 0,
        }
    }
}

impl Agent for Checked {
    fn name(&self) -> &str {
        self.inner.name()
    }

    fn exchange(&mut self, view: &View) -> Hand {
        self.inner.exchange(view)
    }

    fn declare(&mut self, view: &View, category: Category) -> Declaration {
        self.inner.declare(view, category)
    }

    fn play(&mut self, view: &View) -> Card {
        let mut probe = self.inner.clone();
        let estimates = probe.estimates(view);
        let played = self.inner.play(view);
        match estimates {
            Some(estimates) => {
                self.searched += 1;
                assert_eq!(estimates.best(), played, "played what it reported");
                let legal: Vec<Card> = view.legal_plays.cards().collect();
                let reported: Vec<Card> = estimates.totals.iter().map(|(c, _)| *c).collect();
                assert_eq!(
                    reported, legal,
                    "one estimate per legal card, in legal order"
                );
                assert!(estimates.worlds > 0);
                for (card, total) in &estimates.totals {
                    let mean = estimates.mean(*card).unwrap();
                    assert!((mean * estimates.worlds as f64 - total).abs() < 1e-9);
                }
            }
            None => {
                self.declined += 1;
                assert!(
                    view.legal_plays.len() == 1 || view.hand.len() > self.inner.exact_from,
                    "declined to search a position it would have searched"
                );
            }
        }
        played
    }
}

fn duel(
    elder: SolverAgent,
    younger: SolverAgent,
    deals: usize,
    standing: Option<Standing>,
) -> usize {
    let mut rng = Rng::seeded(17);
    let mut searched = 0;
    for _ in 0..deals {
        let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
        rng.shuffle(&mut pack);
        let mut a = Checked::new(elder.clone());
        let mut b = Checked::new(younger.clone());
        play_deal(deal_from(&pack).unwrap(), &mut a, &mut b, standing).unwrap();
        assert!(
            a.declined > 0 && b.declined > 0,
            "the early tricks are the fallback's"
        );
        searched += a.searched + b.searched;
    }
    searched
}

#[test]
fn the_flat_search_plays_the_best_card_it_reports() {
    let searched = duel(
        SolverAgent::new(3).worlds(8),
        SolverAgent::new(5).worlds(8),
        6,
        None,
    );
    assert!(searched > 30, "only {searched} searched decisions checked");
}

#[test]
fn the_settling_search_plays_the_best_card_it_reports() {
    let standing = Standing {
        mine: 95,
        theirs: 88,
        deals_left: 1,
        number: 6,
    };
    let searched = duel(
        SolverAgent::new(3).worlds(8).settling(),
        SolverAgent::new(5).worlds(8),
        6,
        Some(standing),
    );
    assert!(searched > 30, "only {searched} searched decisions checked");
}

#[test]
fn a_card_that_is_not_legal_has_no_estimate() {
    let mut rng = Rng::seeded(17);
    let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
    rng.shuffle(&mut pack);

    /// Keeps the first searched view's estimates, and checks a card outside
    /// the legal plays is not among them.
    struct Once(SolverAgent, bool);
    impl Agent for Once {
        fn name(&self) -> &str {
            self.0.name()
        }
        fn exchange(&mut self, view: &View) -> Hand {
            self.0.exchange(view)
        }
        fn declare(&mut self, view: &View, category: Category) -> Declaration {
            self.0.declare(view, category)
        }
        fn play(&mut self, view: &View) -> Card {
            if let Some(estimates) = self.0.clone().estimates(view) {
                let outside = (0u8..32)
                    .map(Card)
                    .find(|c| !view.legal_plays.contains(c.0))
                    .unwrap();
                assert_eq!(estimates.mean(outside), None);
                self.1 = true;
            }
            self.0.play(view)
        }
    }

    let mut elder = Once(SolverAgent::new(3).worlds(4), false);
    let mut younger = Once(SolverAgent::new(5).worlds(4), false);
    play_deal(deal_from(&pack).unwrap(), &mut elder, &mut younger, None).unwrap();
    assert!(elder.1 || younger.1);
}

/// Every searched view either seat was asked to play from, with the
/// opponent's true hand at that moment, from one deal at a last-deal standing.
fn searched_views_with_the_truth() -> Vec<(View, Hand)> {
    struct Keep(SolverAgent, Vec<View>);
    impl Agent for Keep {
        fn name(&self) -> &str {
            self.0.name()
        }
        fn exchange(&mut self, view: &View) -> Hand {
            self.0.exchange(view)
        }
        fn declare(&mut self, view: &View, category: Category) -> Declaration {
            self.0.declare(view, category)
        }
        fn play(&mut self, view: &View) -> Card {
            if view.hand.len() <= self.0.exact_from && view.legal_plays.len() > 1 {
                self.1.push(view.clone());
            }
            self.0.play(view)
        }
    }

    let standing = Standing {
        mine: 95,
        theirs: 88,
        deals_left: 1,
        number: 6,
    };
    let mut rng = Rng::seeded(17);
    let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
    rng.shuffle(&mut pack);
    let mut elder = Keep(SolverAgent::new(3).worlds(4), Vec::new());
    let mut younger = Keep(SolverAgent::new(5).worlds(4), Vec::new());
    let (deal, _) = play_deal(
        deal_from(&pack).unwrap(),
        &mut elder,
        &mut younger,
        Some(standing),
    )
    .unwrap();

    // Each seat's twelve cards, read back off the finished tricks; a hand
    // mid-deal is those twelve less whatever that seat has played.
    let twelve = |seat: piquet_core::scoring::Player| -> Hand {
        let mut bits = 0u32;
        for trick in &deal.tricks {
            let card = if trick.leader == seat {
                trick.led
            } else {
                trick.followed.unwrap()
            };
            bits |= 1 << card.0;
        }
        Hand(bits)
    };
    let mut out = Vec::new();
    for view in elder.1.into_iter().chain(younger.1) {
        let mut theirs = twelve(view.opponent()).0;
        for trick in view.tricks.iter().chain(view.current_trick.iter()) {
            for card in [Some(trick.led), trick.followed].into_iter().flatten() {
                theirs &= !(1 << card.0);
            }
        }
        out.push((view, Hand(theirs)));
    }
    out
}

#[test]
fn the_true_world_is_valued_in_the_agents_own_objective() {
    let cases = searched_views_with_the_truth();
    assert!(cases.len() >= 6, "only {} searched views", cases.len());
    for (view, theirs) in &cases {
        assert_eq!(
            theirs.len(),
            view.hand.len() - u32::from(view.current_trick.is_some())
        );
        let legal: Vec<Card> = view.legal_plays.cards().collect();

        let flat = SolverAgent::new(1).values_in(view, *theirs).unwrap();
        let settling = SolverAgent::new(1)
            .settling()
            .values_in(view, *theirs)
            .unwrap();
        for values in [&flat, &settling] {
            let cards: Vec<Card> = values.iter().map(|(c, _)| *c).collect();
            assert_eq!(cards, legal, "one value per legal card, in legal order");
        }
        // Points in a deal cannot reach a hundred; a last deal's settlement
        // is at least the hundred for the partie, unless it is dead level.
        assert!(flat.iter().all(|(_, v)| v.abs() < 100.0), "{flat:?}");
        assert!(
            settling.iter().all(|(_, v)| *v == 0.0 || v.abs() >= 100.0),
            "{settling:?}"
        );
    }
}
