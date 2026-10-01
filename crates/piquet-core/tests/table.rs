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
        Prompt::Cut => Some(Action::Cut(16)),
        Prompt::ChooseDealer => Some(Action::FirstDealer(Who::You)),
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

/// Cut, and if the choice falls to the human, deal first -- the choice
/// Cavendish and pagat both advise.
fn through_the_cut(table: &mut Table) {
    while matches!(table.prompt(), Prompt::Cut | Prompt::ChooseDealer) {
        let action = dull(table).unwrap();
        table.act(action).unwrap();
    }
}

#[test]
fn the_table_opens_on_the_cut_with_nothing_dealt() {
    let mut table = Table::new(3, 1);
    assert_eq!(table.prompt(), Prompt::Cut);
    assert!(
        table.view().hand.is_empty(),
        "no hand is seen before the deal is settled"
    );
    assert!(!table
        .events()
        .iter()
        .any(|e| matches!(e, Event::DealBegins { .. })));
    assert!(
        table.act(Action::Cut(1)).is_err(),
        "a cut lifts at least two cards"
    );
    assert!(
        table.act(Action::Cut(31)).is_err(),
        "and leaves at least two"
    );
    assert!(table.act(Action::NextDeal).is_err());
    through_the_cut(&mut table);
    match table.prompt() {
        Prompt::Exchange { limit } => assert!((1..=5).contains(&limit), "limit {limit}"),
        other => panic!("expected to be asked for a discard, got {other:?}"),
    }
    assert_eq!(table.view().hand.len(), 12);
}

#[test]
fn the_higher_cut_chooses_the_ace_is_high_and_ties_cut_again() {
    let (mut chose, mut deferred, mut tied) = (0, 0, 0);
    for seed in 0..300 {
        let mut table = Table::new(2, seed);
        table.act(Action::Cut(2 + (seed as usize % 29))).unwrap();
        let cuts: Vec<(Who, piquet_core::cards::Card)> = table
            .events()
            .iter()
            .filter_map(|e| match e {
                Event::Cut { who, card } => Some((*who, *card)),
                _ => None,
            })
            .collect();
        assert_eq!(cuts.len(), 2, "both players cut");
        let (mine, theirs) = (cuts[0].1.rank(), cuts[1].1.rank());
        if mine == theirs {
            tied += 1;
            assert_eq!(table.prompt(), Prompt::Cut, "equal cuts are cut again");
            assert!(table.events().iter().any(|e| matches!(e, Event::CutAgain)));
        } else if mine > theirs {
            chose += 1;
            assert_eq!(
                table.prompt(),
                Prompt::ChooseDealer,
                "the higher cut chooses"
            );
        } else {
            deferred += 1;
            // The opponent has the choice, and takes the one the books advise.
            assert!(table.events().iter().any(|e| matches!(
                e,
                Event::FirstDealer {
                    chooser: Who::Them,
                    dealer: Who::Them
                }
            )));
            assert!(matches!(table.prompt(), Prompt::Exchange { .. }));
            assert_eq!(
                table.you(),
                Player::Elder,
                "the opponent deals, so you lead"
            );
        }
    }
    assert!(
        chose > 50 && deferred > 50 && tied > 5,
        "{chose} / {deferred} / {tied}"
    );
}

#[test]
fn whoever_deals_first_is_elder_in_the_sixth_deal() {
    for (dealer, first_seat) in [(Who::You, Player::Younger), (Who::Them, Player::Elder)] {
        let mut found = false;
        for seed in 0..40 {
            let mut table = Table::new(1, seed);
            table.act(Action::Cut(16)).unwrap();
            if table.prompt() != Prompt::ChooseDealer {
                continue;
            }
            table.act(Action::FirstDealer(dealer)).unwrap();
            assert_eq!(table.you(), first_seat, "deal 1");
            while table.partie().outcomes.len() < 5 {
                table.act(dull(&table).unwrap()).unwrap();
            }
            if table.prompt() == Prompt::NextDeal {
                table.act(Action::NextDeal).unwrap();
            }
            assert_eq!(table.you(), first_seat.opponent(), "deal 6 reverses deal 1");
            found = true;
            break;
        }
        assert!(found, "never had the choice in forty cuts");
    }
}

#[test]
fn the_cut_changes_nothing_about_the_cards() {
    // The cut has a generator of its own, so the pack a seed deals is the
    // same however the cut falls -- the same talon always, and, whenever the
    // same player ends up dealing, the same hands. (When the dealer differs
    // the hands differ only because an elder opponent has already exchanged.)
    let mut compared = 0;
    for seed in 0..20 {
        let mut tables: Vec<(bool, Table)> = Vec::new();
        for depth in [2, 9, 16, 23, 30] {
            let mut table = Table::new(3, seed);
            table.act(Action::Cut(depth)).unwrap();
            through_the_cut(&mut table);
            tables.push((table.you() == Player::Younger, table));
        }
        let (first_deals, first) = &tables[0];
        for (deals, other) in &tables[1..] {
            assert_eq!(first.deal().talon, other.deal().talon, "seed {seed}");
            if deals == first_deals {
                assert_eq!(first.deal().hands, other.deal().hands, "seed {seed}");
                compared += 1;
            }
        }
    }
    assert!(
        compared > 20,
        "too few like-for-like cuts to compare: {compared}"
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

const ROSTER: [&str; 5] = ["Bess", "Cotton", "Cavendish", "Hoyle", "Foster"];

#[test]
fn the_opponent_is_never_named() {
    // The user: "don't refer to the dealer as a proper name, just call them
    // your opponent." The roster's names are for the ladder, not the table.
    for level in 1..=5 {
        let mut table = Table::new(level, 90 + level);
        play_out(&mut table);
        let mut called_opponent = 0;
        for event in table.events() {
            let said = event.text();
            for name in ROSTER {
                assert!(!said.contains(name), "level {level}: {said:?} names {name}");
            }
            called_opponent += usize::from(said.to_lowercase().contains("your opponent"));
        }
        assert!(
            called_opponent > 20,
            "level {level}: the opponent is barely mentioned"
        );
    }
}

#[test]
fn every_event_reads_as_a_sentence() {
    let mut table = Table::new(5, 9);
    play_out(&mut table);
    for event in table.events() {
        let said = event.text();
        assert!(
            said.chars().next().is_some_and(char::is_uppercase),
            "a sentence starts with a capital: {said:?}"
        );
        assert!(!said.is_empty(), "{event:?} says nothing");
        assert!(!said.contains("Some(") && !said.contains("None"), "{said}");
        assert!(!said.contains("--"), "a typewriter dash in {said:?}");
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
        play_winners: true,
    }
}

/// On lead, and every card in hand beats everything that might yet be
/// played against it -- whatever is unaccounted for, and whatever elder
/// watched younger draw. Stated here independently of the table.
fn all_sure_winners(table: &Table) -> bool {
    let view = table.view();
    if !matches!(table.prompt(), Prompt::Play { .. }) || view.current_trick.is_some() {
        return false;
    }
    let threats = Hand(view.unseen().0 | view.watched_them_take.0);
    view.hand.cards().all(|mine| {
        threats
            .cards()
            .all(|theirs| theirs.suit() != mine.suit() || theirs.rank() < mine.rank())
    })
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
fn a_hint_is_a_plain_instruction() {
    let mut table = Table::new(1, 45);
    let mut checked = 0;
    while let Some(action) = dull(&table) {
        if let Some(hint) = table.hint() {
            let said = hint.text();
            assert!(
                said.chars().next().is_some_and(char::is_uppercase),
                "{said:?}"
            );
            assert!(said.ends_with('.'), "{said:?}");
            for name in ROSTER {
                assert!(!said.contains(name), "{said:?} names {name}");
            }
            checked += 1;
        }
        table.act(action).unwrap();
    }
    assert!(checked > 50);
}

#[test]
fn there_is_no_hint_between_deals() {
    let mut table = Table::new(1, 46);
    while !matches!(table.prompt(), Prompt::NextDeal) {
        table.act(dull(&table).unwrap()).unwrap();
    }
    assert_eq!(table.hint(), None);
}

#[test]
fn undo_is_instant_even_against_the_solver() {
    // Undo by replaying re-runs every decision the opponent has made, which
    // late in a partie against the solver is seconds in a browser. It must
    // restore a snapshot instead -- and so must a table rebuilt from its
    // record, since that is what a reloaded page undoes against.
    let mut table = Table::with_aids(5, 70, all_aids());
    while table.partie().outcomes.len() < 3 {
        table.act(dull(&table).unwrap()).unwrap();
    }
    while !matches!(table.prompt(), Prompt::Play { .. }) {
        table.act(dull(&table).unwrap()).unwrap();
    }
    let before = (table.prompt(), table.view(), table.events().to_vec());
    table.act(dull(&table).unwrap()).unwrap();

    let started = std::time::Instant::now();
    let mut rebuilt = Table::replay(5, 70, all_aids(), table.record()).unwrap();
    let replaying = started.elapsed();

    let started = std::time::Instant::now();
    table.undo().unwrap();
    let undoing = started.elapsed();
    assert_eq!(
        (table.prompt(), table.view(), table.events().to_vec()),
        before
    );
    assert!(
        undoing * 5 < replaying,
        "undo took {undoing:?} against a replay's {replaying:?}"
    );

    let started = std::time::Instant::now();
    rebuilt.undo().unwrap();
    let undoing = started.elapsed();
    assert_eq!(
        (rebuilt.prompt(), rebuilt.view(), rebuilt.events().to_vec()),
        before
    );
    assert!(
        undoing * 5 < replaying,
        "after a reload, undo took {undoing:?} against a replay's {replaying:?}"
    );
}

#[test]
fn sure_winners_play_themselves() {
    // Find games where the plain table asks the human to lead out a hand of
    // certain winners -- pure clicking -- and check the aid never does.
    let mut found = 0;
    for seed in 80..110 {
        let mut plain = Table::new(3, seed);
        let mut asked = false;
        while let Some(action) = dull(&plain) {
            asked |= all_sure_winners(&plain);
            plain.act(action).unwrap();
        }
        if !asked {
            continue;
        }
        found += 1;
        let mut aided = Table::with_aids(
            3,
            seed,
            Aids {
                play_winners: true,
                ..Aids::default()
            },
        );
        while let Some(action) = dull(&aided) {
            assert!(
                !all_sure_winners(&aided),
                "seed {seed}: asked to lead out certain winners"
            );
            aided.act(action).unwrap();
        }
        // The same cards in the same order as the dull script would have
        // led them, so the same game.
        assert_eq!(aided.events(), plain.events(), "seed {seed}");
    }
    assert!(
        found >= 3,
        "only {found} games ever offered certain winners"
    );
}

#[test]
fn a_decision_says_whether_the_tie_break_was_asked_for() {
    // The point's value, a sequence's top card, a set's rank: asked for only
    // when both players hold the same shape (Cavendish, pp. 60-67) -- and
    // the voice asks "What do they make?" only then. So a decision says
    // whether it was: for your opponent as elder, exactly when their call
    // was narrated with its tie-break; for you, when you gave yours.
    let mut seen = [[0usize; 2]; 2]; // [elder is you][asked]
    for seed in 1..60 {
        let mut table = Table::new(3, seed);
        while let Some(action) = dull(&table) {
            let before = table.events().len();
            table.act(action).unwrap();
            let view = table.view();
            let events = &table.events()[before..];
            for e in events {
                let Event::Decided {
                    category, asked, ..
                } = e
                else {
                    continue;
                };
                let elder_is_you = view.me == Player::Elder;
                let narrated = events.iter().any(|x| match x {
                    Event::Called {
                        who: Who::Them,
                        category: c,
                        said,
                    } => {
                        c == category
                            && (said.contains(", making ")
                                || said.contains(" to the ")
                                || said.contains(" of "))
                    }
                    _ => false,
                });
                let gave = view
                    .said
                    .iter()
                    .any(|a| a.category == *category && a.tiebreak.is_some());
                let expected = if elder_is_you { gave } else { narrated };
                assert_eq!(
                    *asked, expected,
                    "seed {seed}, {category:?}, elder is you: {elder_is_you}"
                );
                seen[usize::from(elder_is_you)][usize::from(*asked)] += 1;
            }
        }
    }
    for (elder, row) in seen.iter().enumerate() {
        assert!(
            row[0] > 5 && row[1] > 5,
            "elder is you: {}; asked and not: {row:?}",
            elder == 1
        );
    }
}

/// pagat: "If elder exchanges fewer than five cards he can look at the
/// remainder of the five." Elder is told which cards those are, and then
/// which of them the opponent drew -- they draw from the top, so the ones
/// left go first. Measured on 30 September: the opponent, as younger, takes
/// every card it may, so they almost never stay in the talon.
#[test]
fn elder_is_told_the_cards_they_left_and_which_the_opponent_drew() {
    use piquet_core::cards::Card;
    let (mut looked, mut took) = (0, 0);
    for seed in 1..=15u32 {
        let mut table = Table::new(3, seed);
        through_the_cut(&mut table);
        let mut deal = 0;
        while table.prompt() != Prompt::Over {
            let elder_exchange =
                matches!(table.prompt(), Prompt::Exchange { .. }) && table.you() == Player::Elder;
            if !elder_exchange {
                let action = dull(&table).unwrap();
                table.act(action).unwrap();
                continue;
            }
            deal += 1;
            let take = 1 + (seed as usize + deal) % 5; // 1 to 5
            let throw: Vec<Card> = table.view().hand.cards().take(take).collect();
            let five = table.deal().talon[..5].to_vec();
            let from = table.events().len();
            table
                .act(Action::Exchange(Hand::of(&throw).unwrap()))
                .unwrap();
            let new = &table.events()[from..];
            let looked_at = new.iter().find_map(|e| match e {
                Event::Looked { cards } => Some(*cards),
                _ => None,
            });
            let told = new.iter().find_map(|e| match e {
                Event::TheyTook { cards } => Some(*cards),
                _ => None,
            });
            if take == 5 {
                assert_eq!((looked_at, told), (None, None), "nothing left to look at");
                continue;
            }
            assert_eq!(looked_at, Some(Hand::of(&five[take..]).unwrap()));
            looked += 1;
            let theirs = table.deal().discards[1].len() as usize;
            let drawn: Vec<Card> = five[take..].iter().take(theirs).copied().collect();
            assert_eq!(
                told,
                Some(Hand::of(&drawn).unwrap()),
                "they draw yours first"
            );
            for card in &drawn {
                assert!(
                    table.deal().hands[1].holds(*card),
                    "{} is in their hand",
                    card.code()
                );
            }
            took += 1;
            // In the order it happened: your draw, your look, their exchange, what they took.
            let at = |f: &dyn Fn(&Event) -> bool| new.iter().position(f).unwrap();
            let order = [
                at(&|e| matches!(e, Event::Drew { .. })),
                at(&|e| matches!(e, Event::Looked { .. })),
                at(&|e| matches!(e, Event::Exchanged { who: Who::Them, .. })),
                at(&|e| matches!(e, Event::TheyTook { .. })),
            ];
            assert!(order.windows(2).all(|w| w[0] < w[1]), "{order:?}");
        }
    }
    assert!(looked >= 10 && took >= 10, "looked {looked}, took {took}");
}

/// Younger sees none of elder's talon cards, and is told nothing of them.
#[test]
fn younger_is_told_nothing_of_elders_talon_cards() {
    for seed in 1..=10u32 {
        let mut table = Table::new(2, seed);
        through_the_cut(&mut table);
        let mut younger_events = Vec::new();
        while let Some(action) = dull(&table) {
            let from = table.events().len();
            let younger = table.you() == Player::Younger;
            table.act(action).unwrap();
            if younger {
                younger_events.extend(table.events()[from..].iter().cloned());
            }
        }
        assert!(!younger_events.is_empty());
        assert!(younger_events
            .iter()
            .all(|e| !matches!(e, Event::Looked { .. } | Event::TheyTook { .. })));
    }
}
