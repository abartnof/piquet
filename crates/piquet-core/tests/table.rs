//! The table: a whole partie against one opponent, one human decision at a time.
//!
//! This is the contract every client renders from -- the browser page today,
//! something three-dimensional perhaps later. So these tests are about what a
//! client may rely on: it is always told what it may do, an impossible move is
//! refused without disturbing anything, the same seed is the same game, and
//! nothing it is given says more than the human at the table could know.

use piquet_core::cards::Hand;
use piquet_core::scoring::Player;
use piquet_core::table::{Action, Event, Prompt, Table, Who};

/// The dullest legal answer to every prompt: throw one card, call everything,
/// play the first legal card. It is here to walk the machinery, not to win.
fn dull(table: &Table) -> Option<Action> {
    match table.prompt() {
        Prompt::Exchange { .. } => {
            let first = table
                .view()
                .hand
                .cards()
                .next()
                .expect("a hand to discard from");
            Some(Action::Exchange(Hand::of(&[first]).unwrap()))
        }
        Prompt::Declare { .. } => Some(Action::Declare(0)),
        Prompt::Play { legal } => Some(Action::Play(legal.cards().next().unwrap())),
        Prompt::NextDeal => Some(Action::NextDeal),
        Prompt::Over => None,
    }
}

fn play_out(table: &mut Table) -> usize {
    let mut steps = 0;
    while let Some(action) = dull(table) {
        table
            .act(action)
            .unwrap_or_else(|e| panic!("a legal action was refused: {e}"));
        steps += 1;
        assert!(steps < 2000, "the partie never ended");
    }
    steps
}

#[test]
fn the_table_opens_on_a_decision_for_the_human() {
    // The human deals first, so the opponent is elder in deal one and has
    // already exchanged by the time the human is asked anything.
    let table = Table::new(3, 1);
    assert_eq!(table.you(), Player::Younger);
    match table.prompt() {
        Prompt::Exchange { limit } => assert!((1..=3).contains(&limit), "limit {limit}"),
        other => panic!("expected to be asked for a discard, got {other:?}"),
    }
    assert!(
        table
            .events()
            .iter()
            .any(|e| matches!(e, Event::Exchanged { who: Who::Them, .. })),
        "the opponent's exchange is narrated"
    );
}

#[test]
fn a_whole_partie_can_be_played_through_the_table_at_every_level() {
    for level in 1..=5 {
        let mut table = Table::new(level, 100 + level);
        play_out(&mut table);
        assert!(
            table.partie().complete(),
            "level {level}: partie unfinished"
        );
        let settled = table
            .partie()
            .settlement()
            .expect("a complete partie settles");

        let ended = table
            .events()
            .iter()
            .filter(|e| matches!(e, Event::DealEnds { .. }))
            .count();
        assert_eq!(
            ended,
            table.partie().outcomes.len(),
            "one DealEnds per deal"
        );
        assert!(
            matches!(table.events().last(), Some(Event::PartieEnds { .. })),
            "the last thing said is the settlement"
        );
        if let Some(Event::PartieEnds { settlement, .. }) = table.events().last() {
            assert_eq!(*settlement, settled);
        }
    }
}

#[test]
fn every_declaration_prompt_is_a_real_choice() {
    // A hand with nothing to call has exactly one option, and asking a person
    // to click it is a chore rather than a decision: the table makes it for
    // them and says so.
    let mut table = Table::new(2, 7);
    while let Some(action) = dull(&table) {
        if let Prompt::Declare { options, .. } = table.prompt() {
            assert!(
                options.len() >= 2,
                "a forced declaration was put to the human"
            );
        }
        table.act(action).unwrap();
    }
}

#[test]
fn an_impossible_move_is_refused_and_changes_nothing() {
    let mut table = Table::new(3, 2);

    let before = (table.prompt(), table.view(), table.events().len());
    let not_held = Hand(!table.view().hand.0);
    let one_not_held = Hand::of(&[not_held.cards().next().unwrap()]).unwrap();
    assert!(table.act(Action::Exchange(one_not_held)).is_err());
    assert!(
        table.act(Action::Exchange(Hand::EMPTY)).is_err(),
        "one card is compulsory"
    );
    assert!(table.act(Action::Declare(0)).is_err(), "out of turn");
    assert!(table.act(Action::NextDeal).is_err(), "the deal is not over");
    assert_eq!(
        (table.prompt(), table.view(), table.events().len()),
        before,
        "a refused move must leave the table exactly as it was"
    );

    // And during play: a card that does not follow suit when it could.
    while !matches!(table.prompt(), Prompt::Play { .. }) {
        let action = dull(&table).unwrap();
        table.act(action).unwrap();
    }
    loop {
        if let Prompt::Play { legal } = table.prompt() {
            let illegal = table.view().hand.without(legal);
            if let Some(card) = illegal.cards().next() {
                let before = (table.view(), table.events().len());
                let refusal = table.act(Action::Play(card)).unwrap_err();
                assert!(
                    refusal.contains("follow"),
                    "the refusal says why: {refusal}"
                );
                assert_eq!((table.view(), table.events().len()), before);
                return;
            }
        }
        let Some(action) = dull(&table) else { break };
        table.act(action).unwrap();
    }
    panic!("never found a position where a card was illegal");
}

#[test]
fn the_same_seed_is_the_same_partie() {
    let mut first = Table::new(4, 1674);
    let mut second = Table::new(4, 1674);
    play_out(&mut first);
    play_out(&mut second);
    assert_eq!(first.events(), second.events());

    let mut other = Table::new(4, 1675);
    play_out(&mut other);
    assert_ne!(
        first.events(),
        other.events(),
        "a different seed, a different game"
    );
}

#[test]
fn younger_names_nothing_until_elder_has_led() {
    // The rule observation.rs has leaked three times. With the human as
    // elder, nothing the opponent holds may be named -- in a call, a showing,
    // or a score -- before the human has led to the first trick.
    let mut table = Table::new(4, 3);
    let mut checked = 0;
    while let Some(action) = dull(&table) {
        let human_leads_first =
            table.you() == Player::Elder && matches!(table.prompt(), Prompt::Play { .. });
        if human_leads_first
            && table.view().tricks.is_empty()
            && table.view().current_trick.is_none()
        {
            let since_deal_began = table
                .events()
                .iter()
                .rev()
                .take_while(|e| !matches!(e, Event::DealBegins { .. }));
            for event in since_deal_began {
                let premature = matches!(
                    event,
                    Event::Called { who: Who::Them, .. }
                        | Event::Showed { who: Who::Them, .. }
                        | Event::Scored { who: Who::Them, .. }
                );
                assert!(!premature, "younger spoke before elder led: {event:?}");
            }
            checked += 1;
        }
        table.act(action).unwrap();
    }
    assert!(checked >= 2, "the human led first in only {checked} deals");
}

#[test]
fn the_scores_narrated_are_the_scores_recorded() {
    let mut table = Table::new(3, 5);
    play_out(&mut table);

    let mut narrated = [0i32; 2];
    for event in table.events() {
        if let Event::Scored { who, amount, .. } = event {
            narrated[if *who == Who::You { 0 } else { 1 }] += amount;
        }
    }
    let (mine, theirs) = table.partie().totals();
    assert_eq!(
        narrated,
        [mine, theirs],
        "every point scored was narrated, once"
    );
}

#[test]
fn every_event_reads_as_a_sentence() {
    let mut table = Table::new(5, 9);
    play_out(&mut table);
    for event in table.events() {
        let said = event.text("Foster");
        assert!(!said.is_empty(), "{event:?} says nothing");
        assert!(!said.contains("Some(") && !said.contains("None"), "{said}");
    }
}
