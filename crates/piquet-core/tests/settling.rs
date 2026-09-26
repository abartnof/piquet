//! What the settling search counts as already banked when it begins.
//!
//! A repique is made in declarations alone, so it is decided before a card is
//! played -- yet the bonus enters the log only when the deal is finished. A
//! search that settles at the leaf from `log.total` alone is therefore sixty
//! points wrong in every repique deal, and near the rubicon sixty points is
//! the difference between paying the difference and paying the sum.

use piquet_core::agents::Agent;
use piquet_core::cards::{Card, Hand};
use piquet_core::declarations::Declaration;
use piquet_core::heuristics::HeuristicAgent;
use piquet_core::observation::View;
use piquet_core::play::play_deal;
use piquet_core::rng::Rng;
use piquet_core::rules::deal_from;
use piquet_core::scoring::{Category, Player};
use piquet_core::solver::settled_log;

/// A rung-4 player that keeps every view it is asked to play from.
struct Watching {
    inner: HeuristicAgent,
    plays: Vec<View>,
}

impl Watching {
    fn new(seed: u32) -> Watching {
        Watching {
            inner: HeuristicAgent::new(4, seed).unwrap(),
            plays: Vec::new(),
        }
    }
}

impl Agent for Watching {
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
        self.plays.push(view.clone());
        self.inner.play(view)
    }
}

/// The first deal from a fixed shuffle in which somebody makes a repique:
/// who made it, and the views each seat was asked to play from.
fn a_repique_deal() -> (Player, Vec<View>, Vec<View>) {
    let mut rng = Rng::seeded(68);
    for _ in 0..2000 {
        let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
        rng.shuffle(&mut pack);
        let mut elder = Watching::new(1);
        let mut younger = Watching::new(2);
        let (deal, _) =
            play_deal(deal_from(&pack).unwrap(), &mut elder, &mut younger, None).unwrap();
        if let Some(winner) = deal.log.repique() {
            return (winner, elder.plays, younger.plays);
        }
    }
    panic!("no repique in two thousand deals");
}

#[test]
fn a_repique_is_banked_once_the_play_has_begun() {
    let (winner, elder_views, younger_views) = a_repique_deal();
    let mid_deal = elder_views
        .iter()
        .chain(younger_views.iter())
        .filter(|v| !v.tricks.is_empty());

    let mut checked = 0;
    for view in mid_deal {
        let settled = settled_log(view);
        assert_eq!(
            settled.total(winner) - view.log.total(winner),
            60,
            "{} at trick {}: the repique is not counted",
            view.me.name(),
            view.tricks.len() + 1
        );
        assert_eq!(
            settled.total(winner.opponent()),
            view.log.total(winner.opponent()),
            "the loser of a repique banks nothing extra"
        );
        checked += 1;
    }
    assert!(checked > 0, "no view after the first trick was captured");
}

#[test]
fn nothing_is_banked_before_younger_has_declared() {
    // Younger names nothing until elder has led, so from elder's first lead
    // the log is missing whatever she will score. A repique read off it
    // could be one she is about to deny him.
    let (_, elder_views, _) = a_repique_deal();
    let first_lead = elder_views
        .iter()
        .find(|v| v.tricks.is_empty() && v.current_trick.is_none())
        .expect("elder leads to the first trick");
    let settled = settled_log(first_lead);
    for seat in [Player::Elder, Player::Younger] {
        assert_eq!(settled.total(seat), first_lead.log.total(seat));
    }
}
