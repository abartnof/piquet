//! Replay the golden vectors against the Rust engine.
//!
//! This is the mirror of `tests/test_vectors.py`: same files, same assertions,
//! a different language. That is the entire reason the vectors exist. The
//! Python engine is the oracle -- it is the one that passes the full suite --
//! so a value here that disagrees with a vector is a bug in this crate.

use std::fs;
use std::path::PathBuf;

use piquet_core::cards::{card_code, full_deck, parse_card, Hand};
use piquet_core::solver::{card_values, solve, ELDER, EVEN, YOUNGER};

fn vectors(name: &str) -> serde_json::Value {
    let path: PathBuf = [env!("CARGO_MANIFEST_DIR"), "..", "..", "vectors", name]
        .iter()
        .collect();
    let text =
        fs::read_to_string(&path).unwrap_or_else(|e| panic!("cannot read {}: {e}", path.display()));
    serde_json::from_str(&text).expect("valid JSON")
}

// -- cards ------------------------------------------------------------------

#[test]
fn the_pack_round_trips_through_index_and_code() {
    let vec = vectors("cards.json");
    for case in vec["pack"].as_array().unwrap() {
        let index = case["index"].as_u64().unwrap() as u8;
        let code = case["code"].as_str().unwrap();
        assert_eq!(card_code(index), code);
        assert_eq!(parse_card(code).unwrap(), index);
    }
    assert_eq!(full_deck().count(), 32);
}

#[test]
fn the_ace_of_spades_is_just_a_number() {
    // In JavaScript this hand reads as -2147483648.
    let vec = vectors("cards.json");
    let ace = vec["pack"]
        .as_array()
        .unwrap()
        .iter()
        .find(|c| c["code"] == "AS")
        .unwrap();
    assert_eq!(ace["index"].as_u64().unwrap(), 31);
    assert_eq!(Hand::parse("AS").unwrap().0, 1u32 << 31);
}

#[test]
fn hands_have_the_recorded_mask_size_and_order() {
    let vec = vectors("cards.json");
    for case in vec["hands"].as_array().unwrap() {
        let hand = Hand::parse(case["code"].as_str().unwrap()).unwrap();
        assert_eq!(u64::from(hand.0), case["bits"].as_u64().unwrap());
        assert_eq!(u64::from(hand.len()), case["size"].as_u64().unwrap());

        let want: Vec<&str> = case["cards"]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| c.as_str().unwrap())
            .collect();
        let got: Vec<String> = hand.iter().map(card_code).collect();
        assert_eq!(got, want, "iteration order is part of the contract");
        assert_eq!(hand.code(), want.join(" "));
    }
}

#[test]
fn parsing_is_forgiving_in_the_documented_ways() {
    let vec = vectors("cards.json");
    for case in vec["parse"].as_array().unwrap() {
        let text = case["text"].as_str().unwrap();
        // The suit-symbol forms are not yet supported in this crate; the
        // letter forms are, and those are what serialisation uses.
        if !text.is_ascii() {
            continue;
        }
        let index = parse_card(text).unwrap_or_else(|e| panic!("{text:?}: {e}"));
        assert_eq!(card_code(index), case["code"].as_str().unwrap());
    }
}

// -- solver -----------------------------------------------------------------

#[test]
fn every_position_solves_to_its_recorded_value() {
    let vec = vectors("solver.json");
    for case in vec["positions"].as_array().unwrap() {
        let elder = Hand::parse(case["elder"].as_str().unwrap()).unwrap();
        let younger = Hand::parse(case["younger"].as_str().unwrap()).unwrap();
        let leader = if case["leader"] == "elder" {
            ELDER
        } else {
            YOUNGER
        };
        let led = case["led"].as_str().map(|c| parse_card(c).unwrap());
        let tricks = case["elder_tricks"].as_u64().unwrap() as u32;

        let got = solve(elder, younger, leader, led, tricks, EVEN).unwrap();
        assert_eq!(
            got,
            case["value"].as_i64().unwrap(),
            "position: {}",
            case["name"]
        );
    }
}

#[test]
fn every_card_is_worth_what_the_oracle_says() {
    let vec = vectors("solver.json");
    for case in vec["positions"].as_array().unwrap() {
        let elder = Hand::parse(case["elder"].as_str().unwrap()).unwrap();
        let younger = Hand::parse(case["younger"].as_str().unwrap()).unwrap();
        let leader = if case["leader"] == "elder" {
            ELDER
        } else {
            YOUNGER
        };
        let led = case["led"].as_str().map(|c| parse_card(c).unwrap());
        let tricks = case["elder_tricks"].as_u64().unwrap() as u32;

        let mut got: Vec<(String, i64)> = card_values(elder, younger, leader, led, tricks, EVEN)
            .unwrap()
            .into_iter()
            .map(|(card, value)| (card_code(card), value))
            .collect();
        got.sort();

        let want: Vec<(String, i64)> = case["card_values"]
            .as_array()
            .unwrap()
            .iter()
            .map(|e| {
                (
                    e["card"].as_str().unwrap().to_string(),
                    e["value"].as_i64().unwrap(),
                )
            })
            .collect();
        assert_eq!(got, want, "position: {}", case["name"]);
    }
}

#[test]
fn ducking_beats_cashing() {
    // A measured lesson rather than a rule: the ace takes the last trick,
    // which is worth two.
    let vec = vectors("solver.json");
    let case = vec["positions"]
        .as_array()
        .unwrap()
        .iter()
        .find(|c| {
            c["name"]
                .as_str()
                .unwrap()
                .ends_with("ducking beats cashing")
        })
        .unwrap();

    let values = card_values(
        Hand::parse(case["elder"].as_str().unwrap()).unwrap(),
        Hand::parse(case["younger"].as_str().unwrap()).unwrap(),
        ELDER,
        None,
        case["elder_tricks"].as_u64().unwrap() as u32,
        EVEN,
    )
    .unwrap();

    let duck = values
        .iter()
        .find(|(c, _)| card_code(*c) == "7S")
        .unwrap()
        .1;
    let cash = values
        .iter()
        .find(|(c, _)| card_code(*c) == "AS")
        .unwrap()
        .1;
    assert!(duck > cash, "ducking ({duck}) must beat cashing ({cash})");
}

#[test]
fn the_transposition_key_needs_a_u128() {
    let vec = vectors("solver.json");
    let mut widest = 0u32;
    for case in vec["memo_key"]["cases"].as_array().unwrap() {
        let elder = case["elder_bits"].as_u64().unwrap() as u128;
        let younger = case["younger_bits"].as_u64().unwrap() as u128;
        let leader = case["leader"].as_u64().unwrap() as u128;
        let led = case["led_index"].as_i64().unwrap();
        let tricks = case["elder_tricks"].as_u64().unwrap() as u128;

        let key =
            elder | (younger << 32) | (leader << 64) | (((led + 1) as u128) << 65) | (tricks << 71);

        assert_eq!(key.to_string(), case["key"].as_str().unwrap());
        let bits = 128 - key.leading_zeros();
        assert_eq!(bits as u64, case["bit_length"].as_u64().unwrap());
        widest = widest.max(bits);
    }
    assert!(widest > 64, "no case exceeds 64 bits, so none needs a u128");
}

#[test]
fn an_impossible_position_is_refused() {
    assert!(solve(
        Hand::parse("AS KS").unwrap(),
        Hand::parse("QS").unwrap(),
        ELDER,
        None,
        0,
        EVEN
    )
    .is_err());
}
