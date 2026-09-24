//! Properties that must hold of every deal, checked over many of them.
//!
//! The golden vectors pin chosen positions and the differential corpus
//! compares against the oracle. Neither asks whether a deal is *coherent* --
//! they would both happily agree on the same wrong answer. These do.
//!
//! The Python has a `test_invariants.py` of the same intent, and its own note
//! says the statistical tests there "have caught more real bugs than the unit
//! tests have".

use piquet_core::agents::{Agent, RandomAgent};
use piquet_core::cards::{Card, Hand};
use piquet_core::heuristics::HeuristicAgent;
use piquet_core::observation::view_for;
use piquet_core::play::play_pack;
use piquet_core::rng::Rng;
use piquet_core::rules::{deal_from, Phase, TRICKS_PER_DEAL};
use piquet_core::scoring::Player;
use piquet_core::solver::SolverAgent;

const FULL_PACK: u32 = u32::MAX;

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

fn agent(kind: usize, seed: u32) -> Box<dyn Agent> {
    match kind % 6 {
        0 => Box::new(RandomAgent::new(seed)),
        5 => Box::new(SolverAgent::new(seed)),
        level => Box::new(HeuristicAgent::new(level as u32, seed).unwrap()),
    }
}

#[test]
fn every_deal_finishes_coherently() {
    for (i, pack) in packs(400, 11).into_iter().enumerate() {
        let mut elder = agent(i, 100 + i as u32);
        let mut younger = agent(i + 3, 200 + i as u32);
        let (deal, decisions) = play_pack(&pack, elder.as_mut(), younger.as_mut(), None)
            .unwrap_or_else(|e| panic!("deal {i}: {e}"));

        assert_eq!(deal.phase, Phase::Complete, "deal {i}");
        assert!(
            deal.hand_of(Player::Elder).is_empty(),
            "deal {i}: elder holds cards"
        );
        assert!(deal.hand_of(Player::Younger).is_empty(), "deal {i}");
        assert_eq!(deal.tricks.len(), TRICKS_PER_DEAL, "deal {i}");
        assert!(deal.current_trick.is_none(), "deal {i}");
        assert_eq!(
            deal.tricks_won(Player::Elder) + deal.tricks_won(Player::Younger),
            TRICKS_PER_DEAL,
            "deal {i}: tricks do not add up"
        );

        // Every score is positive: an equality is recorded by logging nothing,
        // because a zero would look like the adversary having reckoned.
        for event in &deal.log.events {
            assert!(event.amount > 0, "deal {i}: a score of {}", event.amount);
        }
        assert!(deal.log.total(Player::Elder) >= 0);
        assert!(deal.log.total(Player::Younger) >= 0);

        // A player scores a pique or a repique, never both.
        assert!(
            !(deal.log.repique().is_some() && deal.log.pique().is_some()),
            "deal {i}: both bonuses"
        );
        // And younger can never pique -- it falls out of the precedence order.
        assert_ne!(deal.log.pique(), Some(Player::Younger), "deal {i}");

        assert!(!decisions.is_empty(), "deal {i}: nothing was logged");
    }
}

#[test]
fn no_card_is_ever_lost_or_duplicated() {
    // The pack is a partition at every moment: hands, discards, the untaken
    // talon and the cards on the table account for all thirty-two, once each.
    for (i, pack) in packs(200, 23).into_iter().enumerate() {
        let mut deal = deal_from(&pack).unwrap();
        let mut elder = agent(i + 1, 300 + i as u32);
        let mut younger = agent(i + 4, 400 + i as u32);

        let census = |deal: &piquet_core::rules::Deal| -> (u32, u32) {
            let mut bits = deal.hand_of(Player::Elder).0
                | deal.hand_of(Player::Younger).0
                | deal.discard_of(Player::Elder).0
                | deal.discard_of(Player::Younger).0;
            let mut count = deal.hand_of(Player::Elder).len()
                + deal.hand_of(Player::Younger).len()
                + deal.discard_of(Player::Elder).len()
                + deal.discard_of(Player::Younger).len();
            for card in deal.talon_untaken() {
                bits |= 1 << card.0;
                count += 1;
            }
            for trick in deal.tricks.iter().chain(deal.current_trick.iter()) {
                bits |= 1 << trick.led.0;
                count += 1;
                if let Some(followed) = trick.followed {
                    bits |= 1 << followed.0;
                    count += 1;
                }
            }
            (bits, count)
        };

        // Step through by hand so the census can run between every action.
        let mut step = 0;
        let check = |deal: &piquet_core::rules::Deal, step: usize| {
            let (bits, count) = census(deal);
            assert_eq!(bits, FULL_PACK, "deal {i} step {step}: cards vanished");
            assert_eq!(count, 32, "deal {i} step {step}: {count} cards, not 32");
        };
        check(&deal, step);

        for player in [Player::Elder, Player::Younger] {
            let view = view_for(&deal, player, None);
            let agent: &mut dyn Agent = match player {
                Player::Elder => elder.as_mut(),
                Player::Younger => younger.as_mut(),
            };
            deal = deal.exchange(player, agent.exchange(&view)).unwrap();
            step += 1;
            check(&deal, step);
        }
        while let Some(player) = deal.to_declare() {
            let category = deal.declaring_category().unwrap();
            let view = view_for(&deal, player, None);
            let agent: &mut dyn Agent = match player {
                Player::Elder => elder.as_mut(),
                Player::Younger => younger.as_mut(),
            };
            deal = deal
                .declare(player, agent.declare(&view, category))
                .unwrap();
            step += 1;
            check(&deal, step);
        }
        while deal.phase == Phase::Play {
            let player = deal.to_play().unwrap();
            let view = view_for(&deal, player, None);
            let agent: &mut dyn Agent = match player {
                Player::Elder => elder.as_mut(),
                Player::Younger => younger.as_mut(),
            };
            deal = deal.play(player, agent.play(&view)).unwrap();
            step += 1;
            check(&deal, step);
        }
    }
}

#[test]
fn no_view_ever_accounts_for_the_opponents_hand() {
    // The scripted version of this runs one deal with one policy. This runs
    // hundreds, against every kind of agent, at every point in the deal --
    // because a leak that only appears after an unusual exchange would sail
    // straight past a single script.
    for (i, pack) in packs(300, 37).into_iter().enumerate() {
        let mut deal = deal_from(&pack).unwrap();
        let mut elder = agent(i + 2, 500 + i as u32);
        let mut younger = agent(i + 5, 600 + i as u32);

        let audit = |deal: &piquet_core::rules::Deal, step: usize| {
            for player in [Player::Elder, Player::Younger] {
                let view = view_for(deal, player, None);
                let opponent = deal.hand_of(player.opponent());
                let leaked = Hand(opponent.0 & !view.unseen().0 & !view.watched_them_take.0);
                assert_eq!(
                    leaked.0,
                    0,
                    "deal {i} step {step}: {} at {} can account for {}",
                    player.name(),
                    view.phase.value(),
                    leaked.code()
                );
                // And a view never shows a card the player does not hold.
                assert_eq!(view.legal_plays.without(view.hand).0, 0);
            }
        };

        let mut step = 0;
        audit(&deal, step);
        for player in [Player::Elder, Player::Younger] {
            let view = view_for(&deal, player, None);
            let a: &mut dyn Agent = match player {
                Player::Elder => elder.as_mut(),
                Player::Younger => younger.as_mut(),
            };
            deal = deal.exchange(player, a.exchange(&view)).unwrap();
            step += 1;
            audit(&deal, step);
        }
        while let Some(player) = deal.to_declare() {
            let category = deal.declaring_category().unwrap();
            let view = view_for(&deal, player, None);
            let a: &mut dyn Agent = match player {
                Player::Elder => elder.as_mut(),
                Player::Younger => younger.as_mut(),
            };
            deal = deal.declare(player, a.declare(&view, category)).unwrap();
            step += 1;
            audit(&deal, step);
        }
        while deal.phase == Phase::Play {
            let player = deal.to_play().unwrap();
            let view = view_for(&deal, player, None);
            let a: &mut dyn Agent = match player {
                Player::Elder => elder.as_mut(),
                Player::Younger => younger.as_mut(),
            };
            deal = deal.play(player, a.play(&view)).unwrap();
            step += 1;
            audit(&deal, step);
        }
    }
}

#[test]
fn elder_only_ever_gains_by_using_the_exchange() {
    // Measured in the Python over 4,000 deals: elder wins 52.5% when both
    // take the full exchange and 49.6% when they take a random number, so his
    // advantage is not structural -- it has to be used. A weak check of the
    // same shape, enough to catch the exchange being wired backwards.
    let mut full_wins = 0;
    let mut total = 0;
    for (i, pack) in packs(600, 71).into_iter().enumerate() {
        let mut elder = HeuristicAgent::new(2, 700 + i as u32).unwrap();
        let mut younger = HeuristicAgent::new(2, 800 + i as u32).unwrap();
        let (deal, _) = play_pack(&pack, &mut elder, &mut younger, None).unwrap();
        let e = deal.log.total(Player::Elder);
        let y = deal.log.total(Player::Younger);
        if e != y {
            total += 1;
            if e > y {
                full_wins += 1;
            }
        }
    }
    let rate = full_wins as f64 / total as f64;
    assert!(
        (0.40..0.65).contains(&rate),
        "elder wins {:.1}% of decided deals at equal rungs, which is not a \
         plausible advantage in either direction",
        100.0 * rate
    );
}
