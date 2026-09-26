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

// ---------------------------------------------------------------------------
// Aids: every one a toggle, none of them changing the rules
// ---------------------------------------------------------------------------

use piquet_core::scoring::Category;
use piquet_core::table::Aids;

fn all_aids() -> Aids {
    Aids {
        hints: true,
        play_forced: true,
        declare_for_me: true,
    }
}

#[test]
fn the_record_replays_the_game_exactly() {
    // Everything taken from the human's seat, chosen or automatic, is kept;
    // replaying it from the seed gives the same table. This is what undo is
    // built on, and what a client keeps to survive a reload.
    let mut table = Table::with_aids(4, 31, all_aids());
    for _ in 0..60 {
        let Some(action) = dull(&table) else { break };
        table.act(action).unwrap();
    }
    let again = Table::replay(4, 31, all_aids(), table.record()).expect("the record replays");
    assert_eq!(again.events(), table.events());
    assert_eq!(again.prompt(), table.prompt());
    assert_eq!(again.view(), table.view());
    assert_eq!(again.record(), table.record());
}

#[test]
fn a_record_that_does_not_fit_the_game_is_refused() {
    let bogus = [(Action::NextDeal, false)];
    assert!(Table::replay(3, 1, Aids::default(), &bogus).is_err());
}

#[test]
fn undo_puts_the_table_back_as_it_was_before_the_last_decision() {
    for aids in [Aids::default(), all_aids()] {
        let mut table = Table::with_aids(3, 32, aids);
        let mut decisions = 0;
        while let Some(action) = dull(&table) {
            let before = (table.prompt(), table.view(), table.events().to_vec());
            table.act(action).unwrap();
            decisions += 1;
            if decisions % 7 == 0 {
                table.undo().expect("there is a decision to take back");
                assert_eq!(
                    (table.prompt(), table.view(), table.events().to_vec()),
                    before,
                    "{aids:?}: undo after decision {decisions}"
                );
                // And the game carries on from there as if nothing happened.
                table.act(dull(&table).unwrap()).unwrap();
            }
            if decisions > 120 {
                break;
            }
        }
        assert!(decisions > 40, "the test never got going");
    }
}

#[test]
fn there_is_nothing_to_undo_before_the_first_decision() {
    let mut table = Table::new(2, 33);
    assert!(table.undo().is_err());
}

#[test]
fn declare_for_me_never_asks_and_calls_everything() {
    let mut table = Table::with_aids(
        3,
        34,
        Aids {
            declare_for_me: true,
            ..Aids::default()
        },
    );
    let mut calls = 0;
    while let Some(action) = dull(&table) {
        assert!(
            !matches!(table.prompt(), Prompt::Declare { .. }),
            "asked to declare with declare-for-me on"
        );
        table.act(action).unwrap();
    }
    for event in table.events() {
        if let Event::Called { who: Who::You, .. } = event {
            calls += 1;
        }
    }
    assert!(calls > 0, "the calls are still narrated");
}

#[test]
fn a_forced_card_plays_itself() {
    let mut table = Table::with_aids(
        3,
        35,
        Aids {
            play_forced: true,
            ..Aids::default()
        },
    );
    while let Some(action) = dull(&table) {
        if let Prompt::Play { legal } = table.prompt() {
            assert!(
                legal.len() > 1,
                "asked to play a card that had no alternative"
            );
        }
        table.act(action).unwrap();
    }
}

#[test]
fn the_aids_change_the_asking_and_not_the_game() {
    // The dull script calls everything and plays the first legal card, which
    // is exactly what the aids would have done -- so with them on or off, the
    // same partie is played and the same things are said.
    let mut plain = Table::new(4, 36);
    let mut aided = Table::with_aids(4, 36, all_aids());
    play_out(&mut plain);
    play_out(&mut aided);
    assert_eq!(plain.events(), aided.events());
}

#[test]
fn switching_an_aid_on_takes_effect_at_once() {
    let mut table = Table::new(3, 37);
    while !matches!(table.prompt(), Prompt::Declare { .. }) {
        table.act(dull(&table).unwrap()).unwrap();
    }
    table.set_aids(Aids {
        declare_for_me: true,
        ..Aids::default()
    });
    assert!(!matches!(table.prompt(), Prompt::Declare { .. }));
    assert!(table.aids().declare_for_me);
}

#[test]
fn every_score_says_what_category_it_was_for() {
    let mut table = Table::new(3, 38);
    play_out(&mut table);
    let categories: std::collections::BTreeSet<String> = table
        .events()
        .iter()
        .filter_map(|e| match e {
            Event::Scored { category, .. } => Some(category.name().to_string()),
            _ => None,
        })
        .collect();
    assert!(categories.contains(Category::Play.name()), "{categories:?}");
    assert!(
        categories.contains(Category::Cards.name()),
        "{categories:?}"
    );
}

// ---------------------------------------------------------------------------
// Hints
// ---------------------------------------------------------------------------

#[test]
fn a_hint_is_always_a_legal_answer() {
    // Follow the advice for a whole partie: every hint must be accepted.
    for level in [2, 5] {
        let mut table = Table::new(level, 40 + level);
        let mut followed = 0;
        while !matches!(table.prompt(), Prompt::Over) {
            if table.prompt() == Prompt::NextDeal {
                table.act(Action::NextDeal).unwrap();
                continue;
            }
            let hint = table.hint().expect("a hint whenever there is a decision");
            table
                .act(hint.action.clone())
                .unwrap_or_else(|e| panic!("hint {hint:?} was refused: {e}"));
            followed += 1;
            assert!(followed < 2000);
        }
        assert!(followed > 50);
    }
}

#[test]
fn asking_for_a_hint_changes_nothing() {
    // The advisor has its own generator. A hint that nudged the opponent's
    // would make a game with hints a different game.
    let mut asked = Table::new(5, 44);
    let mut unasked = Table::new(5, 44);
    while let Some(action) = dull(&asked) {
        let before = (asked.prompt(), asked.view(), asked.events().len());
        let first = asked.hint();
        assert_eq!(asked.hint(), first, "the same question, the same answer");
        assert_eq!((asked.prompt(), asked.view(), asked.events().len()), before);
        asked.act(action.clone()).unwrap();
        unasked.act(action).unwrap();
    }
    assert_eq!(asked.events(), unasked.events());
}

#[test]
fn a_hint_says_who_is_advising() {
    let table = Table::new(1, 45);
    let hint = table.hint().unwrap();
    assert!(!hint.advisor.name.is_empty());
    assert!(!hint.text().is_empty());
    assert!(matches!(hint.action, Action::Exchange(_)));
}

#[test]
fn there_is_no_hint_between_deals() {
    let mut table = Table::new(1, 46);
    while !matches!(table.prompt(), Prompt::NextDeal) {
        table.act(dull(&table).unwrap()).unwrap();
    }
    assert_eq!(table.hint(), None);
}
