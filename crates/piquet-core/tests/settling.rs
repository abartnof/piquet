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

// ---------------------------------------------------------------------------
// A pique still live when the search begins.
//
// Elder wins a pique by reaching thirty before younger scores anything, in
// Law 67's order of precedence, and the play can make it or deny it: every
// card led scores a point, and so does a trick won against the lead. The
// settling search counted a pique already decided (`settled_log`) but not one
// still in the balance -- and pique deals lost at nine times the rate of the
// rest (PLAN.md TODO 1).

use piquet_core::cards::parse_card;
use piquet_core::solver::{card_settlements, Settling, ELDER};

/// Elder on 28, younger on nothing, two cards each, elder to lead. Leading the
/// ace keeps the lead, so the next card led is elder's thirtieth point before
/// younger has scored: a pique, thirty more, and in the last deal at fifty
/// apiece that carries elder over the rubicon. Leading the seven lets
/// younger's eight take the trick, and her point kills the pique -- though in
/// plain deal points that line is a point better for elder.
fn live_pique_values() -> (f64, f64) {
    let ctx = Settling {
        elder_side: 50,
        younger_side: 50,
        elder_so_far: 28,
        younger_so_far: 0,
        deals_left: 1,
        elder_first_next: false,
    };
    let elder = Hand::parse("AS 7H").unwrap();
    let younger = Hand::parse("KS 8H").unwrap();
    // Five tricks each already: whoever takes one more of these two draws the
    // cards, so no ten for the cards muddies either line.
    let values = card_settlements(elder, younger, ELDER, None, 5, &ctx).unwrap();
    let of = |code: &str| {
        values
            .iter()
            .find(|(c, _)| *c == parse_card(code).unwrap())
            .unwrap()
            .1
    };
    (of("AS"), of("7H"))
}

#[test]
fn the_settling_search_plays_for_a_live_pique() {
    let (ace, seven) = live_pique_values();
    assert!(
        ace > seven,
        "leading the ace makes the pique and should be worth more than the seven: {ace} against {seven}"
    );
}

#[test]
fn a_pique_already_dead_is_not_played_for() {
    // Younger has scored: no pique is possible, and the extra point of the
    // seven line is simply better.
    let ctx = Settling {
        elder_side: 50,
        younger_side: 50,
        elder_so_far: 28,
        younger_so_far: 1,
        deals_left: 1,
        elder_first_next: false,
    };
    let values = card_settlements(
        Hand::parse("AS 7H").unwrap(),
        Hand::parse("KS 8H").unwrap(),
        ELDER,
        None,
        5,
        &ctx,
    )
    .unwrap();
    let of = |code: &str| {
        values
            .iter()
            .find(|(c, _)| *c == parse_card(code).unwrap())
            .unwrap()
            .1
    };
    assert!(of("7H") >= of("AS"));
}
