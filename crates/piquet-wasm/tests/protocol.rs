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
            let mut current = s.clone();
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
                for token in text.split(|c: char| !c.is_ascii_alphanumeric()) {
                    if token.len() != 2 || token.to_uppercase() != token {
                        continue;
                    }
                    let Ok(card) = Card::parse(token) else {
                        continue;
                    };
                    assert!(
                        !theirs.holds(card) || known.holds(card),
                        "seed {seed}: the state names {token}, which the opponent holds, in {text:?}"
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
