//! The protocol a client drives the table with: JSON out, one-line commands in.
//!
//! What a client may rely on, whatever it draws with. Every test goes through
//! the same two calls a browser makes -- `send` and `state` -- and reads the
//! state back as JSON, so what is tested is the wire format and not the Rust.

use piquet_core::cards::{Card, Hand};
use piquet_core::scoring::Player;
use piquet_wasm::Session;
use serde_json::Value;

fn state(session: &Session) -> Value {
    serde_json::from_str(&session.state()).expect("the state is valid JSON")
}

fn cards(value: &Value) -> Vec<String> {
    value
        .as_array()
        .expect("a list of cards")
        .iter()
        .map(|c| c.as_str().expect("a card code").to_string())
        .collect()
}

/// Every card a piece of text names, in either form a client might print:
/// the code a player types (`AS`, `TC`) or the form a reader sees (`A♠`,
/// `10♣`).
fn named_cards(text: &str) -> Vec<Card> {
    let mut found = Vec::new();
    for token in text.split(|c: char| !c.is_ascii_alphanumeric()) {
        if token.len() == 2 && token.to_uppercase() == token {
            if let Ok(card) = Card::parse(token) {
                found.push(card);
            }
        }
    }
    let chars: Vec<char> = text.chars().collect();
    for (i, c) in chars.iter().enumerate() {
        let suit = match c {
            '\u{2663}' => 'C',
            '\u{2666}' => 'D',
            '\u{2665}' => 'H',
            '\u{2660}' => 'S',
            _ => continue,
        };
        let rank = if i >= 2 && chars[i - 2] == '1' && chars[i - 1] == '0' {
            'T'
        } else if i >= 1 {
            chars[i - 1]
        } else {
            continue;
        };
        if let Ok(card) = Card::parse(&format!("{rank}{suit}")) {
            found.push(card);
        }
    }
    found
}

#[test]
fn the_scan_for_named_cards_reads_both_forms() {
    let named: Vec<String> = named_cards("You threw 10\u{2663} 7\u{2666} and KS")
        .iter()
        .map(|c| c.code())
        .collect();
    assert_eq!(named, ["KS", "TC", "7D"]);
}

/// The dullest legal command for whatever the state asks.
fn dull(state: &Value) -> Option<String> {
    let prompt = &state["prompt"];
    match prompt["kind"].as_str().expect("a prompt kind") {
        "exchange" => Some(format!("exchange {}", cards(&state["hand"])[0])),
        "declare" => Some("declare 0".to_string()),
        "play" => Some(format!("play {}", cards(&prompt["legal"])[0])),
        "next_deal" => Some("next".to_string()),
        "over" => None,
        other => panic!("unknown prompt kind {other}"),
    }
}

fn play_out(session: &mut Session, mut each: impl FnMut(&Session, &Value)) -> Value {
    for _ in 0..3000 {
        let now = state(session);
        each(session, &now);
        let Some(command) = dull(&now) else {
            return now;
        };
        assert!(
            session.send(&command),
            "refused {command:?}: {}",
            state(session)["error"]
        );
    }
    panic!("the partie never ended");
}

#[test]
fn a_new_session_describes_a_decision() {
    let session = Session::new(3, 11);
    let s = state(&session);
    assert_eq!(s["protocol"], 1);
    assert_eq!(s["seed"], 11);
    assert_eq!(s["opponent"]["name"], "Cavendish");
    assert_eq!(s["deal"], 1);
    assert_eq!(s["you_are"], "younger");
    assert_eq!(cards(&s["hand"]).len(), 12);
    assert!(
        s["worth"].as_array().unwrap().iter().all(|w| w.is_string()),
        "what the hand is worth, one phrase per holding"
    );
    assert_eq!(s["prompt"]["kind"], "exchange");
    assert!(s["prompt"]["limit"].as_u64().unwrap() >= 1);
    assert!(s["error"].is_null());
    assert!(
        s["events"]
            .as_array()
            .unwrap()
            .iter()
            .all(|e| e["text"].is_string()),
        "every event carries its sentence"
    );
}

#[test]
fn a_whole_partie_can_be_played_by_commands() {
    let mut session = Session::new(4, 12);
    let mut kinds = std::collections::BTreeSet::new();
    let last = play_out(&mut session, |_, s| {
        kinds.insert(s["prompt"]["kind"].as_str().unwrap().to_string());
    });
    for kind in ["exchange", "declare", "play", "next_deal"] {
        assert!(kinds.contains(kind), "never prompted to {kind}");
    }
    assert_eq!(last["prompt"]["kind"], "over");
    let settlement = &last["settlement"];
    assert!(settlement.is_object(), "a finished partie is settled");
    assert!(settlement["points"].as_i64().unwrap() >= 0);
    let deals = last["deals"].as_array().unwrap();
    assert!(deals.len() >= 6);
    let you: i64 = deals.iter().map(|d| d["you"].as_i64().unwrap()).sum();
    assert_eq!(last["partie"]["you"].as_i64().unwrap(), you);
}

#[test]
fn a_declaration_prompt_lists_its_options_with_the_full_call_first() {
    let mut session = Session::new(2, 13);
    let mut seen = 0;
    play_out(&mut session, |_, s| {
        if s["prompt"]["kind"] == "declare" {
            let options = s["prompt"]["options"].as_array().unwrap();
            assert!(options.len() >= 2);
            assert_eq!(options[0]["full"], true);
            assert_eq!(options[1]["text"], "nothing");
            assert!(s["prompt"]["category"].is_string());
            seen += 1;
        }
    });
    assert!(seen > 0);
}

#[test]
fn a_refused_command_says_why_and_changes_nothing() {
    let mut session = Session::new(3, 14);
    let before = state(&session);
    for nonsense in ["play ZZ", "exchange", "declare 9", "fly me to the moon", ""] {
        assert!(!session.send(nonsense), "{nonsense:?} was accepted");
        let after = state(&session);
        assert!(after["error"].is_string(), "{nonsense:?} gave no reason");
        assert_eq!(after["hand"], before["hand"]);
        assert_eq!(after["events"], before["events"]);
        assert_eq!(after["prompt"], before["prompt"]);
    }
    let command = dull(&before).unwrap();
    assert!(session.send(&command));
    assert!(
        state(&session)["error"].is_null(),
        "success clears the error"
    );
}

#[test]
fn nothing_in_the_state_names_a_card_the_opponent_still_holds() {
    // Walk every string in the state -- lists, prompts, narration -- and
    // treat any two-letter token that parses as a card as a claim. The only
    // opponent cards a player may name are the ones elder watched younger
    // draw from the talon, which the rules let him know.
    fn strings<'a>(value: &'a Value, out: &mut Vec<&'a str>) {
        match value {
            Value::String(s) => out.push(s),
            Value::Array(items) => items.iter().for_each(|v| strings(v, out)),
            Value::Object(map) => map.values().for_each(|v| strings(v, out)),
            _ => {}
        }
    }
    for seed in 20..26 {
        let mut session = Session::new(4, seed);
        play_out(&mut session, |session, s| {
            let table = session.table();
            let theirs = table.deal().hand_of(table.you().opponent());
            let known = table.view().watched_them_take;
            // Events from earlier deals name cards that have been shuffled
            // back into the pack since; only this deal's are claims about it.
            // The record is left out for the same reason: it is the human's
            // own past actions, so within this deal it names only cards that
            // were theirs, and across deals it names reshuffled ones.
            let mut current = s.clone();
            current["record"] = Value::Null;
            let deal = s["deal"].clone();
            current["events"] = Value::Array(
                s["events"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .filter(|e| e["deal"] == deal)
                    .cloned()
                    .collect(),
            );
            let mut found = Vec::new();
            strings(&current, &mut found);
            for text in found {
                for card in named_cards(text) {
                    assert!(
                        !theirs.holds(card) || known.holds(card),
                        "seed {seed}: the state names {}, which the opponent holds, in {text:?}",
                        card.code()
                    );
                }
            }
        });
    }
}

#[test]
fn the_hand_in_the_state_is_the_hand_in_the_view() {
    let mut session = Session::new(5, 15);
    play_out(&mut session, |session, s| {
        let drawn: Vec<Card> = cards(&s["hand"])
            .iter()
            .map(|c| Card::parse(c).unwrap())
            .collect();
        assert_eq!(Hand::of(&drawn).unwrap(), session.table().view().hand);
        let seat = if session.table().you() == Player::Elder {
            "elder"
        } else {
            "younger"
        };
        assert_eq!(s["you_are"], seat);
    });
}

#[test]
fn every_legal_card_offered_is_accepted() {
    let mut session = Session::new(1, 16);
    loop {
        let s = state(&session);
        if s["prompt"]["kind"] == "play" {
            for code in cards(&s["prompt"]["legal"]) {
                let mut trial = Session::new(1, 16);
                // Replay to here by the same dull script, then try this card.
                let mut guard = 0;
                while trial.state() != session.state() {
                    let now = state(&trial);
                    assert!(trial.send(&dull(&now).unwrap()));
                    guard += 1;
                    assert!(guard < 500);
                }
                assert!(
                    trial.send(&format!("play {code}")),
                    "{code} was offered but refused"
                );
            }
            return;
        }
        assert!(session.send(&dull(&s).unwrap()));
    }
}

// ---------------------------------------------------------------------------
// Aids, undo and hints
// ---------------------------------------------------------------------------

#[test]
fn undo_takes_back_the_last_decision() {
    let mut session = Session::new(3, 50);
    assert_eq!(state(&session)["can_undo"], false);
    assert!(!session.send("undo"), "nothing to take back yet");

    for _ in 0..25 {
        let before = state(&session);
        assert!(session.send(&dull(&before).unwrap()));
        assert_eq!(state(&session)["can_undo"], true);
        assert!(session.send("undo"));
        let after = state(&session);
        for key in ["hand", "prompt", "events", "score", "trick", "deal"] {
            assert_eq!(after[key], before[key], "{key} after undo");
        }
        assert!(
            session.send(&dull(&before).unwrap()),
            "and play on from there"
        );
    }
}

#[test]
fn aids_are_switched_by_command_and_reported() {
    let mut session = Session::new(3, 51);
    let s = state(&session);
    for aid in ["hints", "play_forced", "declare_for_me"] {
        assert_eq!(s["aids"][aid], false, "{aid} starts off");
    }
    assert!(session.send("set declare_for_me on"));
    assert!(session.send("set play_forced on"));
    assert_eq!(state(&session)["aids"]["declare_for_me"], true);
    for nonsense in ["set declare_for_me maybe", "set telepathy on", "set"] {
        assert!(!session.send(nonsense), "{nonsense:?} was accepted");
    }
    play_out(&mut session, |_, s| {
        assert_ne!(
            s["prompt"]["kind"], "declare",
            "asked to declare with it on"
        );
        if s["prompt"]["kind"] == "play" {
            assert!(
                cards(&s["prompt"]["legal"]).len() > 1,
                "asked to play a forced card"
            );
        }
    });
}

#[test]
fn a_hint_appears_only_when_asked_for_and_can_be_followed() {
    let mut session = Session::new(4, 52);
    assert!(state(&session)["hint"].is_null());
    assert!(session.send("set hints on"));
    let mut followed = 0;
    for _ in 0..40 {
        let s = state(&session);
        if s["prompt"]["kind"] == "next_deal" {
            assert!(s["hint"].is_null());
            assert!(session.send("next"));
            continue;
        }
        let hint = &s["hint"];
        assert!(hint["text"].as_str().unwrap().contains(" would "), "{hint}");
        let command = hint["command"].as_str().unwrap().to_string();
        assert!(
            session.send(&command),
            "the hint's own command {command:?} was refused"
        );
        followed += 1;
    }
    assert!(followed > 30);
}

#[test]
fn each_declaration_option_names_its_cards() {
    let mut session = Session::new(2, 53);
    let mut checked = 0;
    play_out(&mut session, |_, s| {
        if s["prompt"]["kind"] != "declare" {
            return;
        }
        let hand: Vec<String> = cards(&s["hand"]);
        for option in s["prompt"]["options"].as_array().unwrap() {
            let these = cards(&option["cards"]);
            assert!(these.iter().all(|c| hand.contains(c)), "{option}");
            if option["text"] == "nothing" {
                assert!(these.is_empty());
            } else {
                assert!(!these.is_empty(), "{option}");
            }
        }
        checked += 1;
    });
    assert!(checked > 0);
}

#[test]
fn every_score_carries_its_category() {
    let mut session = Session::new(3, 54);
    let last = play_out(&mut session, |_, _| {});
    let scored: Vec<&Value> = last["events"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|e| e["kind"] == "scored")
        .collect();
    assert!(!scored.is_empty());
    for event in scored {
        assert!(event["category"].is_string(), "{event}");
    }
}

// ---------------------------------------------------------------------------
// Reloading a game from its record
// ---------------------------------------------------------------------------

fn record_of(s: &Value) -> Vec<String> {
    s["record"]
        .as_array()
        .expect("the state carries the record")
        .iter()
        .map(|r| r.as_str().unwrap().to_string())
        .collect()
}

#[test]
fn a_game_reloads_exactly_from_its_record() {
    // Aids switched mid-game and a decision taken back: the record still
    // rebuilds the same table in one pass, which is what a reload does.
    let mut session = Session::new(4, 60);
    for step in 0..40 {
        let now = state(&session);
        let Some(command) = dull(&now) else { break };
        assert!(session.send(&command));
        if step == 10 {
            assert!(session.send("set play_forced on"));
        }
        if step == 20 {
            assert!(session.send("undo"));
        }
        if step == 25 {
            assert!(session.send("set declare_for_me on"));
        }
    }
    let original = state(&session);
    let record = record_of(&original);
    assert!(
        record.iter().any(|r| r.starts_with('*')),
        "automatic moves are marked"
    );
    for entry in &record {
        let verb = entry.trim_start_matches('*').split(' ').next().unwrap();
        assert!(
            ["exchange", "declare", "play", "next"].contains(&verb),
            "a record entry is a command: {entry:?}"
        );
    }

    let mut reloaded = Session::new(1, 1);
    let payload = format!("replay 4 60\n{}", record.join("\n"));
    assert!(reloaded.send(&payload), "{}", state(&reloaded)["error"]);
    assert!(reloaded.send("set play_forced on"));
    assert!(reloaded.send("set declare_for_me on"));
    let again = state(&reloaded);
    for key in [
        "hand", "prompt", "events", "score", "deal", "record", "aids", "seed", "level",
    ] {
        assert_eq!(again[key], original[key], "{key} after reloading");
    }
    assert_eq!(again["can_undo"], true, "and it can still be taken back");
}

#[test]
fn a_record_that_does_not_fit_is_refused() {
    let mut session = Session::new(3, 61);
    let before = state(&session);
    assert!(!session.send("replay 3 61\nplay ZZ"));
    assert!(!session.send("replay 3 61\nnext"));
    assert!(!session.send("replay three 61"));
    let after = state(&session);
    assert!(after["error"].is_string());
    assert_eq!(
        after["hand"], before["hand"],
        "a refused replay leaves the table alone"
    );
}
