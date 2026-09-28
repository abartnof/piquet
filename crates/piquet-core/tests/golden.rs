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

// -- combos -----------------------------------------------------------------

use piquet_core::cards::{Rank, Suit};
use piquet_core::combos::{
    best_point, best_sequence, best_set, compare_point, compare_sequence, compare_set,
    is_carte_blanche, score_sequences, score_sets, sequences, sets, CardSet, Point, Sequence,
};

#[test]
fn holdings_detect_point_sequences_and_sets() {
    let vec = vectors("combos.json");
    for case in vec["holdings"].as_array().unwrap() {
        let hand = Hand::parse(case["hand"].as_str().unwrap()).unwrap();
        let where_ = case["hand"].as_str().unwrap();

        match (best_point(hand), case["best_point"].as_object()) {
            (None, None) => {}
            (Some(point), Some(want)) => {
                assert_eq!(
                    u64::from(point.suit.0),
                    want["suit"].as_u64().unwrap(),
                    "{where_}"
                );
                assert_eq!(u64::from(point.length), want["length"].as_u64().unwrap());
                assert_eq!(
                    u64::from(point.pip_value),
                    want["pip_value"].as_u64().unwrap()
                );
                assert_eq!(u64::from(point.score()), want["score"].as_u64().unwrap());
            }
            _ => panic!("{where_}: point presence disagrees with the oracle"),
        }

        let found = sequences(hand);
        let want = case["sequences"].as_array().unwrap();
        assert_eq!(found.len(), want.len(), "{where_}: sequence count");
        for (got, want) in found.iter().zip(want) {
            assert_eq!(
                u64::from(got.suit.0),
                want["suit"].as_u64().unwrap(),
                "{where_}"
            );
            assert_eq!(
                u64::from(got.top.0),
                want["top"].as_u64().unwrap(),
                "{where_}"
            );
            assert_eq!(u64::from(got.length), want["length"].as_u64().unwrap());
            assert_eq!(u64::from(got.score()), want["score"].as_u64().unwrap());
            assert_eq!(got.name(), want["name"].as_str().unwrap());
        }

        let held = sets(hand);
        let want = case["sets"].as_array().unwrap();
        assert_eq!(held.len(), want.len(), "{where_}: set count");
        for (got, want) in held.iter().zip(want) {
            assert_eq!(u64::from(got.rank.0), want["rank"].as_u64().unwrap());
            assert_eq!(u64::from(got.count), want["count"].as_u64().unwrap());
            assert_eq!(u64::from(got.score()), want["score"].as_u64().unwrap());
        }

        assert_eq!(
            u64::from(score_sequences(hand)),
            case["score_sequences"].as_u64().unwrap(),
            "{where_}"
        );
        assert_eq!(
            u64::from(score_sets(hand)),
            case["score_sets"].as_u64().unwrap(),
            "{where_}"
        );
        assert_eq!(
            is_carte_blanche(hand),
            case["carte_blanche"].as_bool().unwrap(),
            "{where_}"
        );
    }
}

#[test]
fn the_sequence_score_is_a_formula_not_a_table() {
    let vec = vectors("combos.json");
    for case in vec["sequence_scores"].as_array().unwrap() {
        let length = case["length"].as_u64().unwrap() as u32;
        let made = Sequence {
            suit: Suit::CLUBS,
            top: Rank::ACE,
            length,
        };
        assert_eq!(u64::from(made.score()), case["score"].as_u64().unwrap());
    }
}

#[test]
fn tied_sequences_keep_the_order_a_stable_sort_gives() {
    // The §2.2 hazard, and the reason `sort_descending_stably` exists. Two
    // tierces to the king key identically; `sort_by_key(..).reverse()` would
    // return the other one.
    let vec = vectors("combos.json");
    for case in vec["ties"].as_array().unwrap() {
        let hand = Hand::parse(case["hand"].as_str().unwrap()).unwrap();
        let found = sequences(hand);

        let keys: Vec<Vec<u64>> = case["keys"]
            .as_array()
            .unwrap()
            .iter()
            .map(|k| {
                k.as_array()
                    .unwrap()
                    .iter()
                    .map(|n| n.as_u64().unwrap())
                    .collect()
            })
            .collect();
        let got: Vec<Vec<u64>> = found
            .iter()
            .map(|s| vec![u64::from(s.length), u64::from(s.top.0)])
            .collect();
        assert_eq!(got, keys, "{}", case["hand"]);

        let order = case["order"].as_array().unwrap();
        for (got, want) in found.iter().zip(order) {
            assert_eq!(u64::from(got.suit.0), want["suit"].as_u64().unwrap());
            assert_eq!(u64::from(got.top.0), want["top"].as_u64().unwrap());
        }
        assert_eq!(
            u64::from(best_sequence(hand).unwrap().suit.0),
            case["best_suit"].as_u64().unwrap(),
            "the tie decides which sequence is best"
        );
    }
}

#[test]
fn comparisons_between_holdings() {
    let vec = vectors("combos.json");
    for case in vec["comparisons"].as_array().unwrap() {
        let a = Hand::parse(case["left"].as_str().unwrap()).unwrap();
        let b = Hand::parse(case["right"].as_str().unwrap()).unwrap();
        assert_eq!(
            compare_point(best_point(a), best_point(b)).value(),
            case["point"].as_str().unwrap()
        );
        assert_eq!(
            compare_sequence(best_sequence(a), best_sequence(b)).value(),
            case["sequence"].as_str().unwrap()
        );
        assert_eq!(
            compare_set(best_set(a), best_set(b)).value(),
            case["set"].as_str().unwrap()
        );
    }
}

#[test]
fn understated_claims_are_supported_or_not() {
    let vec = vectors("combos.json");
    for case in vec["support"].as_array().unwrap() {
        let hand = Hand::parse(case["hand"].as_str().unwrap()).unwrap();
        let claim = &case["claim"];
        let supported = match case["kind"].as_str().unwrap() {
            "point" => Point {
                suit: Suit(claim["suit"].as_u64().unwrap() as u8),
                length: claim["length"].as_u64().unwrap() as u32,
                pip_value: claim["pip_value"].as_u64().unwrap() as u32,
            }
            .is_supported_by(hand),
            "sequence" => Sequence {
                suit: Suit(claim["suit"].as_u64().unwrap() as u8),
                top: Rank(claim["top"].as_u64().unwrap() as u8),
                length: claim["length"].as_u64().unwrap() as u32,
            }
            .is_supported_by(hand),
            _ => CardSet {
                rank: Rank(claim["rank"].as_u64().unwrap() as u8),
                count: claim["count"].as_u64().unwrap() as u32,
            }
            .is_supported_by(hand),
        };
        assert_eq!(supported, case["supported"].as_bool().unwrap(), "{case}");
    }
}

// -- scoring ----------------------------------------------------------------

use piquet_core::scoring::{Category, Player, ScoreLog, DECLARATION_CATEGORIES, PIQUE_CATEGORIES};

fn category_named(name: &str) -> Category {
    Category::ALL
        .into_iter()
        .find(|c| c.name() == name)
        .unwrap_or_else(|| panic!("unknown category {name}"))
}

fn rebuild_log(events: &serde_json::Value) -> ScoreLog {
    let mut log = ScoreLog::new();
    for event in events.as_array().unwrap() {
        let row = event.as_array().unwrap();
        let player = if row[0] == "elder" {
            Player::Elder
        } else {
            Player::Younger
        };
        log = log
            .record(
                player,
                row[1].as_i64().unwrap() as i32,
                category_named(row[2].as_str().unwrap()),
                row[3].as_str().unwrap(),
            )
            .unwrap();
    }
    log
}

#[test]
fn category_values_are_the_reckoning_order() {
    let vec = vectors("scoring.json");
    for case in vec["categories"].as_array().unwrap() {
        let category = category_named(case["name"].as_str().unwrap());
        assert_eq!(category as u64, case["value"].as_u64().unwrap());
    }
}

#[test]
fn the_two_bonuses_read_different_category_sets() {
    let vec = vectors("scoring.json");
    let declaration: Vec<&str> = DECLARATION_CATEGORIES.iter().map(|c| c.name()).collect();
    let pique: Vec<&str> = PIQUE_CATEGORIES.iter().map(|c| c.name()).collect();
    let want_declaration: Vec<&str> = vec["declaration_categories"]
        .as_array()
        .unwrap()
        .iter()
        .map(|c| c.as_str().unwrap())
        .collect();
    let want_pique: Vec<&str> = vec["pique_categories"]
        .as_array()
        .unwrap()
        .iter()
        .map(|c| c.as_str().unwrap())
        .collect();
    assert_eq!(declaration, want_declaration);
    assert_eq!(pique, want_pique);
    assert!(
        !pique.contains(&"CARDS"),
        "a capot does not count to a pique"
    );
}

#[test]
fn every_logged_case_reckons_as_recorded() {
    let vec = vectors("scoring.json");
    for case in vec["cases"].as_array().unwrap() {
        let log = rebuild_log(&case["events"]);
        let where_ = case["name"].as_str().unwrap();

        assert_eq!(
            i64::from(log.total(Player::Elder)),
            case["totals"]["elder"].as_i64().unwrap(),
            "{where_}"
        );
        assert_eq!(
            i64::from(log.total(Player::Younger)),
            case["totals"]["younger"].as_i64().unwrap(),
            "{where_}"
        );

        let repique = log.repique().map(|p| p.name());
        let pique = log.pique().map(|p| p.name());
        assert_eq!(repique, case["repique"].as_str(), "{where_}: repique");
        assert_eq!(pique, case["pique"].as_str(), "{where_}: pique");
        assert!(
            !(repique.is_some() && pique.is_some()),
            "a player scores one bonus or the other, never both"
        );

        let settled = log.with_bonuses();
        assert_eq!(
            i64::from(settled.total(Player::Elder)),
            case["totals_after_bonuses"]["elder"].as_i64().unwrap(),
            "{where_}"
        );
        assert_eq!(
            i64::from(settled.total(Player::Younger)),
            case["totals_after_bonuses"]["younger"].as_i64().unwrap(),
            "{where_}"
        );
        assert_eq!(
            settled.with_bonuses().len(),
            settled.len(),
            "{where_}: with_bonuses must be idempotent"
        );
    }
}

#[test]
fn younger_can_never_pique() {
    // Not stipulated anywhere: it falls out of the precedence order.
    let vec = vectors("scoring.json");
    for case in vec["cases"].as_array().unwrap() {
        let log = rebuild_log(&case["events"]);
        assert_ne!(log.pique().map(|p| p.name()), Some("younger"));
    }
}

#[test]
fn a_score_must_be_positive() {
    let vec = vectors("scoring.json");
    for case in vec["errors"].as_array().unwrap() {
        let amount = case["amount"].as_i64().unwrap() as i32;
        assert!(ScoreLog::new()
            .record(Player::Elder, amount, Category::Point, "")
            .is_err());
    }
}

// -- declarations -----------------------------------------------------------

use piquet_core::declarations::{
    compare_in, Announcement, CategoryResult, Combination, Declaration,
};

fn build_result(case: &serde_json::Value) -> CategoryResult {
    let category = category_named(case["category"].as_str().unwrap());
    let elder_hand = Hand::parse(case["elder_hand"].as_str().unwrap()).unwrap();
    let younger_hand = Hand::parse(case["younger_hand"].as_str().unwrap()).unwrap();
    let elder = if case["elder_sinks"].as_bool().unwrap_or(false) {
        Declaration::sink()
    } else {
        Declaration::full(elder_hand, category)
    };
    let younger = Declaration::full(younger_hand, category);
    elder.validate(elder_hand, category).unwrap();
    younger.validate(younger_hand, category).unwrap();
    let comparison = compare_in(category, elder.best(), younger.best());
    CategoryResult {
        category,
        elder,
        younger,
        comparison,
    }
}

#[test]
fn the_dialogue_resolves_as_recorded() {
    let vec = vectors("declarations.json");
    for case in vec["dialogue"].as_array().unwrap() {
        let result = build_result(case);
        assert_eq!(
            result.comparison.value(),
            case["comparison"].as_str().unwrap(),
            "{case}"
        );
        assert_eq!(
            result.winner().map(|p| p.name()),
            case["winner"].as_str(),
            "{case}"
        );
        assert_eq!(
            result.shapes_match(),
            case["shapes_match"].as_bool().unwrap(),
            "{case}"
        );
        assert_eq!(
            result.elder.describe(),
            case["elder_declares"].as_str().unwrap()
        );
        assert_eq!(
            u64::from(result.elder.score()),
            case["elder_score_if_won"].as_u64().unwrap()
        );
    }
}

#[test]
fn the_suit_is_never_spoken_and_a_tiebreak_rarely_is() {
    let vec = vectors("declarations.json");
    for case in vec["dialogue"].as_array().unwrap() {
        let result = build_result(case);
        for (name, player) in [("elder", Player::Elder), ("younger", Player::Younger)] {
            let got = result.announcement_of(player);
            let want = &case["announced"][name];
            match (got, want.as_object()) {
                (None, None) => {}
                (Some(a), Some(w)) => {
                    assert_eq!(a.category.name(), w["category"].as_str().unwrap());
                    assert_eq!(u64::from(a.primary), w["primary"].as_u64().unwrap());
                    assert_eq!(a.tiebreak.map(u64::from), w["tiebreak"].as_u64());
                    assert_eq!(a.spoken(), w["spoken"].as_str().unwrap());
                    let said = a.spoken().to_lowercase();
                    assert!(!said.contains("spade") && !said.contains("club"));
                }
                _ => panic!("announcement presence disagrees: {case}"),
            }
        }
        // Younger never volunteers a tie-break.
        if let Some(a) = result.announcement_of(Player::Younger) {
            assert!(a.tiebreak.is_none());
        }
    }
}

#[test]
fn a_beaten_declaration_is_never_shown() {
    let vec = vectors("declarations.json");
    for case in vec["dialogue"].as_array().unwrap() {
        let result = build_result(case);
        for (name, player) in [("elder", Player::Elder), ("younger", Player::Younger)] {
            let shown = result.shown(player);
            let want = case["shown"][name].as_array().unwrap();
            assert_eq!(shown.len(), want.len(), "{case}");
            if let Some(winner) = case["winner"].as_str() {
                if winner != name {
                    assert!(shown.is_empty(), "a beaten declaration must not be shown");
                }
            }
        }
    }
}

#[test]
fn matches_reads_the_key_and_nothing_else() {
    let vec = vectors("declarations.json");
    for case in vec["matches"].as_array().unwrap() {
        let spec = &case["announcement"];
        let category = category_named(spec["category"].as_str().unwrap());
        let announcement = Announcement {
            category,
            primary: spec["primary"].as_u64().unwrap() as u32,
            tiebreak: spec["tiebreak"].as_u64().map(|t| t as u32),
        };
        let hand = Hand::parse(case["hand"].as_str().unwrap()).unwrap();
        let best = Declaration::full(hand, category).best();
        assert_eq!(
            announcement.matches(best),
            case["matches"].as_bool().unwrap(),
            "{case}"
        );
    }
}

// -- partie -----------------------------------------------------------------

use piquet_core::partie::{Partie, Side, PARTIE_BONUS, RUBICON};

fn play_sheet(deals: &serde_json::Value, extra: &serde_json::Value) -> Partie {
    let mut partie = Partie::new(Side::A);
    for source in [deals, extra] {
        for row in source.as_array().unwrap() {
            let pair = row.as_array().unwrap();
            partie = partie
                .record_scores(
                    pair[0].as_i64().unwrap() as i32,
                    pair[1].as_i64().unwrap() as i32,
                )
                .unwrap();
        }
    }
    partie
}

#[test]
fn the_rubicon_decides_which_arithmetic_applies() {
    let vec = vectors("partie.json");
    for case in vec["cases"].as_array().unwrap() {
        let partie = play_sheet(&case["deals"], &case["extra"]);
        let settlement = partie.settlement().expect("a complete partie settles");
        let want = &case["settlement"];

        assert_eq!(
            settlement.winner.map(|s| s.name()),
            want["winner"].as_str(),
            "{}",
            case["name"]
        );
        assert_eq!(
            i64::from(settlement.points),
            want["points"].as_i64().unwrap(),
            "{}",
            case["name"]
        );
        assert_eq!(settlement.rubicon, want["rubicon"].as_bool().unwrap());

        let (first, second) = partie.totals();
        assert_eq!(i64::from(first), case["totals"]["A"].as_i64().unwrap());
        assert_eq!(i64::from(second), case["totals"]["B"].as_i64().unwrap());

        if settlement.winner.is_some() {
            let high = first.max(second);
            let low = first.min(second);
            let expected = if low < RUBICON {
                high + low + PARTIE_BONUS
            } else {
                high - low + PARTIE_BONUS
            };
            assert_eq!(settlement.points, expected);
        }
    }
}

#[test]
fn a_level_partie_plays_two_more_deals_and_both_of_them() {
    let vec = vectors("partie.json");
    let empty = serde_json::json!([]);
    for case in vec["cases"].as_array().unwrap() {
        if case["extra"].as_array().unwrap().is_empty() {
            continue;
        }
        let after_six = play_sheet(&case["deals"], &empty);
        let (a, b) = after_six.totals();
        assert_eq!(a, b, "{}", case["name"]);
        assert!(!after_six.complete());

        let first_extra = serde_json::json!([case["extra"][0]]);
        let after_seven = play_sheet(&case["deals"], &first_extra);
        assert!(
            !after_seven.complete(),
            "the second extra deal is played too"
        );
    }
}

#[test]
fn the_seat_alternates_and_the_side_does_not() {
    let vec = vectors("partie.json");
    for case in vec["alternation"].as_array().unwrap() {
        let opening = if case["opening_dealer"] == "A" {
            Side::A
        } else {
            Side::B
        };
        let partie = Partie::new(opening);
        let want: Vec<&str> = case["elder_by_deal"]
            .as_array()
            .unwrap()
            .iter()
            .map(|s| s.as_str().unwrap())
            .collect();
        let got: Vec<&str> = (1..=want.len())
            .map(|n| partie.elder_in(n).name())
            .collect();
        assert_eq!(got, want);
        assert_ne!(got[0], case["opening_dealer"].as_str().unwrap());
    }
}

#[test]
fn a_settled_partie_takes_no_more_deals() {
    let vec = vectors("partie.json");
    for case in vec["cases"].as_array().unwrap() {
        let partie = play_sheet(&case["deals"], &case["extra"]);
        assert!(partie.complete());
        assert!(partie.record_scores(1, 1).is_err());
    }
}

// -- rules: the whole engine, replayed ---------------------------------------

use piquet_core::rules::{deal_from, Deal, Phase, Trick, TRICKS_PER_DEAL};

fn state_of(deal: &Deal) -> serde_json::Value {
    serde_json::json!({
        "phase": deal.phase.value(),
        "elder_hand": deal.hand_of(Player::Elder).code(),
        "younger_hand": deal.hand_of(Player::Younger).code(),
        "talon_taken": deal.talon_taken,
        "talon_remaining": deal.talon_remaining(),
        "elder_total": deal.log.total(Player::Elder),
        "younger_total": deal.log.total(Player::Younger),
        "elder_tricks": deal.tricks_won(Player::Elder),
        "younger_tricks": deal.tricks_won(Player::Younger),
    })
}

fn pack_of(codes: &serde_json::Value) -> Vec<piquet_core::cards::Card> {
    codes
        .as_array()
        .unwrap()
        .iter()
        .map(|c| piquet_core::cards::Card::parse(c.as_str().unwrap()).unwrap())
        .collect()
}

#[test]
fn every_replay_reproduces_its_recorded_states() {
    // A divergence anywhere -- a mis-dealt talon, an exchange taking from the
    // wrong end of the stock, a declaration scoring in the wrong category, a
    // trick going to the wrong player -- shows up at the step it happened
    // rather than as a wrong number at the end.
    let vec = vectors("rules.json");
    for replay in vec["replays"].as_array().unwrap() {
        let name = replay["name"].as_str().unwrap();
        let mut deal = deal_from(&pack_of(&replay["pack"])).unwrap();

        for (i, step) in replay["steps"].as_array().unwrap().iter().enumerate() {
            match step["action"].as_str().unwrap() {
                "deal" => {}
                "exchange" => {
                    let player = if step["player"] == "elder" {
                        Player::Elder
                    } else {
                        Player::Younger
                    };
                    let discard = Hand::parse(step["discard"].as_str().unwrap()).unwrap();
                    deal = deal.exchange(player, discard).unwrap();
                }
                "declare" => {
                    let player = if step["player"] == "elder" {
                        Player::Elder
                    } else {
                        Player::Younger
                    };
                    let category = category_named(step["category"].as_str().unwrap());
                    let declaration = Declaration::full(deal.hand_of(player), category);
                    deal = deal.declare(player, declaration).unwrap();
                }
                "play" => {
                    let player = if step["player"] == "elder" {
                        Player::Elder
                    } else {
                        Player::Younger
                    };
                    let card =
                        piquet_core::cards::Card::parse(step["card"].as_str().unwrap()).unwrap();
                    deal = deal.play(player, card).unwrap();
                }
                other => panic!("unknown action {other}"),
            }
            assert_eq!(
                state_of(&deal),
                step["after"],
                "{name}: diverged at step {i} ({})",
                step["action"]
            );
        }

        let final_ = &replay["final"];
        assert_eq!(deal.phase, Phase::Complete, "{name}");
        assert_eq!(
            deal.log.repique().map(|p| p.name()),
            final_["repique"].as_str(),
            "{name}"
        );
        assert_eq!(
            deal.log.pique().map(|p| p.name()),
            final_["pique"].as_str(),
            "{name}"
        );

        let events: Vec<serde_json::Value> = deal
            .log
            .events
            .iter()
            .map(|e| {
                serde_json::json!({
                    "player": e.player.name(),
                    "amount": e.amount,
                    "category": e.category.name(),
                    "detail": e.detail,
                })
            })
            .collect();
        assert_eq!(
            serde_json::Value::Array(events),
            final_["events"],
            "{name}: the event log"
        );

        assert_eq!(
            deal.tricks_won(Player::Elder) + deal.tricks_won(Player::Younger),
            TRICKS_PER_DEAL
        );
    }
}

#[test]
fn the_higher_card_of_the_suit_led_takes_the_trick() {
    // There are no trumps, so a card of another suit never wins however high.
    let vec = vectors("rules.json");
    for case in vec["tricks"].as_array().unwrap() {
        let trick = Trick {
            leader: if case["leader"] == "elder" {
                Player::Elder
            } else {
                Player::Younger
            },
            led: piquet_core::cards::Card::parse(case["led"].as_str().unwrap()).unwrap(),
            followed: Some(
                piquet_core::cards::Card::parse(case["followed"].as_str().unwrap()).unwrap(),
            ),
        };
        assert_eq!(trick.complete(), case["complete"].as_bool().unwrap());
        assert_eq!(
            trick.winner().unwrap().name(),
            case["winner"].as_str().unwrap(),
            "{case}"
        );
    }
}

#[test]
fn an_unfinished_trick_has_no_winner() {
    let trick = Trick {
        leader: Player::Elder,
        led: piquet_core::cards::Card::parse("AS").unwrap(),
        followed: None,
    };
    assert!(!trick.complete());
    assert!(trick.winner().is_err());
}

#[test]
fn rules_constants_agree() {
    let vec = vectors("rules.json");
    let constants = &vec["constants"];
    assert_eq!(
        constants["HAND_SIZE"].as_u64().unwrap() as usize,
        piquet_core::rules::HAND_SIZE
    );
    assert_eq!(
        constants["ELDER_MAX_EXCHANGE"].as_u64().unwrap() as usize,
        piquet_core::rules::ELDER_MAX_EXCHANGE
    );
    assert_eq!(
        constants["CAPOT_SCORE"].as_i64().unwrap() as i32,
        piquet_core::rules::CAPOT_SCORE
    );
    let phases: Vec<&str> = Phase::ALL.iter().map(|p| p.value()).collect();
    let want: Vec<&str> = vec["phases"]
        .as_array()
        .unwrap()
        .iter()
        .map(|p| p.as_str().unwrap())
        .collect();
    assert_eq!(phases, want);
}

#[test]
fn an_invalid_deal_or_move_is_refused() {
    use piquet_core::cards::Card;
    let pack: Vec<Card> = (0u8..32).map(Card).collect();
    assert!(deal_from(&pack[..31]).is_err(), "thirty-one cards");

    let mut duplicated = pack[..31].to_vec();
    duplicated.push(pack[0]);
    assert!(deal_from(&duplicated).is_err(), "a duplicate");

    let deal = deal_from(&pack).unwrap();
    assert!(
        deal.exchange(Player::Elder, Hand::EMPTY).is_err(),
        "elder must discard at least one"
    );
    let six = Hand::of(
        &deal
            .hand_of(Player::Elder)
            .cards()
            .take(6)
            .collect::<Vec<_>>(),
    )
    .unwrap();
    assert!(
        deal.exchange(Player::Elder, six).is_err(),
        "elder may take five"
    );
    let hers = Hand::of(
        &deal
            .hand_of(Player::Younger)
            .cards()
            .take(2)
            .collect::<Vec<_>>(),
    )
    .unwrap();
    assert!(
        deal.exchange(Player::Elder, hers).is_err(),
        "a card not held"
    );
    assert!(deal.exchange(Player::Younger, hers).is_err(), "out of turn");
    let first = deal.hand_of(Player::Elder).cards().next().unwrap();
    assert!(deal.play(Player::Elder, first).is_err(), "before the play");
}

// -- observation: what each player is allowed to know ------------------------

use piquet_core::observation::{view_for, View};

/// Re-derive the scripted deal, yielding both players' views at each step.
///
/// Mirrors `tools/emit_vectors.py`. The policy is deterministic, so
/// re-deriving it here also checks that it is genuinely reproducible rather
/// than merely recorded.
fn observe(pack: &[piquet_core::cards::Card], elder_takes: Option<usize>) -> Vec<(View, Hand)> {
    let mut deal = deal_from(pack).unwrap();
    let mut out = Vec::new();

    let capture = |deal: &Deal, out: &mut Vec<(View, Hand)>| {
        for player in [Player::Elder, Player::Younger] {
            out.push((
                view_for(deal, player, None),
                deal.hand_of(player.opponent()),
            ));
        }
    };

    capture(&deal, &mut out);
    for player in [Player::Elder, Player::Younger] {
        let limit = deal.exchange_limit(player);
        let take = match (player, elder_takes) {
            (Player::Elder, Some(n)) => n,
            _ => limit,
        };
        let discard =
            Hand::of(&deal.hand_of(player).cards().take(take).collect::<Vec<_>>()).unwrap();
        deal = deal.exchange(player, discard).unwrap();
        capture(&deal, &mut out);
    }
    while matches!(
        deal.phase,
        Phase::DeclarePoint | Phase::DeclareSequences | Phase::DeclareSets
    ) {
        let player = deal.to_declare().unwrap();
        let category = deal.declaring_category().unwrap();
        let declaration = Declaration::full(deal.hand_of(player), category);
        deal = deal.declare(player, declaration).unwrap();
        capture(&deal, &mut out);
    }
    while deal.phase == Phase::Play {
        let player = deal.to_play().unwrap();
        let card = deal.legal_plays(Some(player)).cards().next().unwrap();
        deal = deal.play(player, card).unwrap();
        capture(&deal, &mut out);
    }
    out
}

#[test]
fn every_view_reproduces_field_for_field() {
    let vec = vectors("observation.json");
    let pack = pack_of(&vec["pack"]);
    for run in vec["runs"].as_array().unwrap() {
        let elder_takes = run["elder_takes"].as_u64().map(|n| n as usize);
        let observed = observe(&pack, elder_takes);
        let recorded = run["snapshots"].as_array().unwrap();
        assert_eq!(observed.len(), recorded.len(), "{}", run["name"]);

        for ((view, _), want) in observed.iter().zip(recorded) {
            let where_ = format!("{}: step {} {}", run["name"], want["step"], want["me"]);
            assert_eq!(view.me.name(), want["me"].as_str().unwrap(), "{where_}");
            assert_eq!(
                view.phase.value(),
                want["phase"].as_str().unwrap(),
                "{where_}"
            );
            assert_eq!(view.hand.code(), want["hand"].as_str().unwrap(), "{where_}");
            assert_eq!(
                view.my_discards.code(),
                want["my_discards"].as_str().unwrap(),
                "{where_}"
            );
            let talon: Vec<String> = view.talon_seen.iter().map(|c| c.code()).collect();
            let want_talon: Vec<&str> = want["talon_seen"]
                .as_array()
                .unwrap()
                .iter()
                .map(|c| c.as_str().unwrap())
                .collect();
            assert_eq!(talon, want_talon, "{where_}");
            assert_eq!(
                view.watched_them_take.code(),
                want["watched_them_take"].as_str().unwrap(),
                "{where_}"
            );
            assert_eq!(
                view.unseen().code(),
                want["unseen"].as_str().unwrap(),
                "{where_}: unseen"
            );
            assert_eq!(
                view.legal_plays.code(),
                want["legal_plays"].as_str().unwrap(),
                "{where_}"
            );
            assert_eq!(view.to_act, want["to_act"].as_bool().unwrap(), "{where_}");
            assert_eq!(
                view.tricks.len() as u64,
                want["tricks_played"].as_u64().unwrap(),
                "{where_}"
            );
        }
    }
}

#[test]
fn no_view_ever_accounts_for_the_opponents_hand() {
    // The invariant the whole module exists to maintain. A view that leaks
    // fails this immediately, whatever its fields say.
    let vec = vectors("observation.json");
    let pack = pack_of(&vec["pack"]);
    for run in vec["runs"].as_array().unwrap() {
        let elder_takes = run["elder_takes"].as_u64().map(|n| n as usize);
        for (view, opponent_hand) in observe(&pack, elder_takes) {
            let leaked = Hand(opponent_hand.0 & !view.unseen().0 & !view.watched_them_take.0);
            assert_eq!(
                leaked.0,
                0,
                "{}: {} at {} can account for {} of the opponent's hand",
                run["name"],
                view.me.name(),
                view.phase.value(),
                leaked.code()
            );
        }
    }
}

#[test]
fn elder_hears_nothing_from_younger_until_he_has_led() {
    let vec = vectors("observation.json");
    let pack = pack_of(&vec["pack"]);
    for run in vec["runs"].as_array().unwrap() {
        let elder_takes = run["elder_takes"].as_u64().map(|n| n as usize);
        for (view, _) in observe(&pack, elder_takes) {
            if view.me != Player::Elder {
                continue;
            }
            if view.tricks.is_empty() && view.current_trick.is_none() {
                assert!(view.heard.is_empty(), "younger has not spoken yet");
                assert!(view.seen.is_empty(), "and has shown nothing");
            }
        }
    }
}

#[test]
fn only_elder_watches_a_draw_and_the_set_only_shrinks() {
    let vec = vectors("observation.json");
    let pack = pack_of(&vec["pack"]);
    let mut ever_watched = false;
    for run in vec["runs"].as_array().unwrap() {
        let elder_takes = run["elder_takes"].as_u64().map(|n| n as usize);
        let mut previous: Option<Hand> = None;
        for (view, opponent_hand) in observe(&pack, elder_takes) {
            if view.me == Player::Younger {
                assert_eq!(view.watched_them_take.0, 0, "only elder watches a draw");
                continue;
            }
            let watched = view.watched_them_take;
            if !watched.is_empty() {
                ever_watched = true;
            }
            assert_eq!(
                watched.without(opponent_hand).0,
                0,
                "a watched card must really be in her hand"
            );
            // Monotonic only once the exchange is over: before that it goes
            // from empty to populated, which is the draw happening.
            if matches!(view.phase, Phase::ElderExchange | Phase::YoungerExchange) {
                continue;
            }
            if let Some(before) = previous {
                assert_eq!(
                    watched.without(before).0,
                    0,
                    "once dealt, the watched set may shrink, never grow"
                );
            }
            previous = Some(watched);
        }
    }
    assert!(
        ever_watched,
        "no run leaves elder watching younger draw, so this tests nothing"
    );
}

#[test]
fn younger_alone_is_asked_to_answer_and_hears_only_a_shape() {
    let vec = vectors("observation.json");
    let pack = pack_of(&vec["pack"]);
    for run in vec["runs"].as_array().unwrap() {
        let elder_takes = run["elder_takes"].as_u64().map(|n| n as usize);
        for (view, _) in observe(&pack, elder_takes) {
            if let Some(announcement) = view.awaiting_answer {
                assert_eq!(view.me, Player::Younger, "only younger answers");
                assert!(
                    announcement.tiebreak.is_none(),
                    "she hears the shape, never the tie-break"
                );
            }
        }
    }
}

// -- chances: the first module with floating point ---------------------------

use piquet_core::chances;

#[test]
fn the_fixed_seed_generator_reproduces_cpython() {
    // Checked before anything downstream, because if this is wrong every
    // weight below is wrong for a reason that is hard to trace back to here.
    let vec = vectors("chances.json");
    let mut rng = piquet_core::test_support::seeded_rng(vec["rng_seed"].as_u64().unwrap() as u32);
    let want: Vec<u64> = vec["rng_draws"]
        .as_array()
        .unwrap()
        .iter()
        .map(|n| n.as_u64().unwrap())
        .collect();
    let got: Vec<u64> = (0..want.len())
        .map(|_| u64::from(rng.getrandbits(9)))
        .collect();
    assert_eq!(got, want);
}

#[test]
fn settlement_is_integer_and_exact() {
    // No tolerance here: the settlement is arithmetic on two integers.
    let vec = vectors("chances.json");
    for case in vec["settlements"].as_array().unwrap() {
        let mine = case["mine"].as_i64().unwrap() as i32;
        let theirs = case["theirs"].as_i64().unwrap() as i32;
        assert_eq!(
            i64::from(chances::settlement_of(mine, theirs)),
            case["pays"].as_i64().unwrap(),
            "{mine} against {theirs}"
        );
    }
}

#[test]
fn the_densities_match() {
    let vec = vectors("chances.json");
    let tolerance = vec["tolerance"].as_f64().unwrap();
    for (name, seat) in [("elder", Player::Elder), ("younger", Player::Younger)] {
        let want = &vec["densities"][name];
        let rows = chances::density(seat);
        assert_eq!(rows.len() as u64, want["length"].as_u64().unwrap());

        let sum: f64 = rows.iter().sum();
        assert!(
            (sum - want["sum"].as_f64().unwrap()).abs() < tolerance,
            "{name}: sum"
        );

        let mean: f64 = rows.iter().enumerate().map(|(i, p)| i as f64 * p).sum();
        assert!(
            (mean - want["mean"].as_f64().unwrap()).abs() < tolerance,
            "{name}: mean"
        );

        let survival = chances::survival(seat);
        assert!((survival[0] - want["survival_at_zero"].as_f64().unwrap()).abs() < tolerance);
        assert!((survival[30] - want["survival_at_thirty"].as_f64().unwrap()).abs() < tolerance);
    }
}

#[test]
fn the_odds_on_reaching_a_total_match() {
    let vec = vectors("chances.json");
    let tolerance = vec["tolerance"].as_f64().unwrap();
    for case in vec["chances"].as_array().unwrap() {
        let got = chances::chance_of(
            case["needed"].as_i64().unwrap() as i32,
            case["deals_left"].as_u64().unwrap() as usize,
            case["elder_first"].as_bool().unwrap(),
        );
        let want = case["chance"].as_f64().unwrap();
        assert!(
            (got - want).abs() < tolerance,
            "{case}: got {got}, want {want}"
        );
        assert_eq!(chances::in_words(got), case["in_words"].as_str().unwrap());
    }
}

#[test]
fn what_a_point_is_worth_in_a_partie_matches() {
    // The bridge from points in a deal to points in a partie, and the whole
    // reason an agent has to see the standing at all.
    let vec = vectors("chances.json");
    let tolerance = vec["tolerance"].as_f64().unwrap();
    for case in vec["weights"].as_array().unwrap() {
        let mine = case["mine"].as_i64().unwrap() as i32;
        let theirs = case["theirs"].as_i64().unwrap() as i32;
        let left = case["deals_left"].as_u64().unwrap() as usize;
        let first = case["elder_first"].as_bool().unwrap();

        let expected = chances::expected_settlement(mine, theirs, left, first);
        assert!(
            (expected - case["expected_settlement"].as_f64().unwrap()).abs() < tolerance,
            "{case}: expected settlement"
        );

        let (w_mine, w_theirs) = chances::point_weights(mine, theirs, left, first);
        assert!(
            (w_mine - case["weight_mine"].as_f64().unwrap()).abs() < tolerance,
            "{case}: my weight"
        );
        assert!(
            (w_theirs - case["weight_theirs"].as_f64().unwrap()).abs() < tolerance,
            "{case}: their weight"
        );
    }
}

#[test]
fn while_they_are_short_their_points_help_me() {
    // The regime with no counterpart inside a single deal: a rubiconed loser
    // pays the SUM, and their score is part of it.
    let vec = vectors("chances.json");
    let rows = vec["weights"].as_array().unwrap();
    let at = |theirs: i64| {
        rows.iter()
            .find(|w| w["mine"] == 120 && w["theirs"] == theirs && w["deals_left"] == 1)
            .map(|w| w["weight_theirs"].as_f64().unwrap())
    };
    let far_short = at(0).expect("a case with them on nothing");
    let nearly_there = at(88).expect("a case with them on 88");
    assert!(
        far_short > 0.0,
        "their points help me while they cannot cross"
    );
    assert!(nearly_there < -5.0, "and hurt sharply once they can");
}
/// How far apart the two languages' floats actually are.
///
/// Measured rather than assumed: 43 of 48 values are **bit-identical**, and
/// the rest differ by one or two ULPs -- worst case 8.9e-16. That is what
/// `docs/DESIGN.md` §2.2 predicts for arithmetic restricted to `+ - * /`,
/// which IEEE 754 requires to be correctly rounded, provided the accumulation
/// order is preserved. `convolve` is ported literally for exactly that reason.
///
/// The handful that differ are most likely a fused multiply-add: an optimising
/// Rust build may contract `a * b + c` into one instruction with a single
/// rounding, which is *more* accurate than Python's two. That is a hypothesis,
/// not something this test establishes.
#[test]
fn the_two_languages_agree_to_within_an_ulp() {
    let vec = vectors("chances.json");
    let mut worst = 0.0f64;
    let mut exact = 0usize;
    let mut total = 0usize;

    let mut compare = |got: f64, want: f64| {
        total += 1;
        if got.to_bits() == want.to_bits() {
            exact += 1;
        }
        worst = worst.max((got - want).abs());
    };

    for case in vec["weights"].as_array().unwrap() {
        let mine = case["mine"].as_i64().unwrap() as i32;
        let theirs = case["theirs"].as_i64().unwrap() as i32;
        let left = case["deals_left"].as_u64().unwrap() as usize;
        let first = case["elder_first"].as_bool().unwrap();
        let (w_mine, w_theirs) = chances::point_weights(mine, theirs, left, first);
        compare(
            chances::expected_settlement(mine, theirs, left, first),
            case["expected_settlement"].as_f64().unwrap(),
        );
        compare(w_mine, case["weight_mine"].as_f64().unwrap());
        compare(w_theirs, case["weight_theirs"].as_f64().unwrap());
    }
    for case in vec["chances"].as_array().unwrap() {
        compare(
            chances::chance_of(
                case["needed"].as_i64().unwrap() as i32,
                case["deals_left"].as_u64().unwrap() as usize,
                case["elder_first"].as_bool().unwrap(),
            ),
            case["chance"].as_f64().unwrap(),
        );
    }

    assert!(
        worst < 1e-14,
        "the two engines have drifted apart: worst difference {worst:e}"
    );
    assert!(
        exact * 2 > total,
        "most values should still be bit-identical, not {exact} of {total}"
    );
}

// -- style ------------------------------------------------------------------

use piquet_core::style::{Style, BALANCED, CALIBRATED};

#[test]
fn the_calibrated_bands_are_the_measured_ones() {
    // Fitted, not chosen, and load-bearing: each band is narrow enough that an
    // extreme setting costs under about a point a deal, which is what stops
    // style becoming a second skill dial.
    let vec = vectors("style.json");
    let want = vec["calibrated"].as_object().unwrap();
    assert_eq!(CALIBRATED.len(), want.len());
    for (name, low, high) in CALIBRATED {
        let bounds = want[name].as_array().unwrap();
        assert_eq!(low, bounds[0].as_f64().unwrap(), "{name}");
        assert_eq!(high, bounds[1].as_f64().unwrap(), "{name}");
    }
}

#[test]
fn the_balanced_style_is_neutral() {
    let vec = vectors("style.json");
    let want = &vec["balanced"];
    assert_eq!(
        BALANCED.discard_boldness,
        want["discard_boldness"].as_f64().unwrap()
    );
    assert_eq!(BALANCED.sinking, want["sinking"].as_f64().unwrap());
    assert_eq!(
        BALANCED.guard_retention,
        want["guard_retention"].as_f64().unwrap()
    );
}

#[test]
fn styles_describe_themselves_relative_to_their_band() {
    // Read against the raw 0-to-1 scale every opponent would be "even-handed".
    let vec = vectors("style.json");
    for case in vec["styles"].as_array().unwrap() {
        let style = Style::new(
            case["discard_boldness"].as_f64().unwrap(),
            case["sinking"].as_f64().unwrap(),
            case["guard_retention"].as_f64().unwrap(),
        )
        .unwrap();
        assert_eq!(
            style.describe(),
            case["describe"].as_str().unwrap(),
            "{case}"
        );
    }
}

#[test]
fn a_style_outside_zero_to_one_is_refused() {
    let vec = vectors("style.json");
    for case in vec["errors"].as_array().unwrap() {
        let fields = case["fields"].as_object().unwrap();
        let get = |name: &str, fallback: f64| {
            fields
                .get(name)
                .and_then(|v| v.as_f64())
                .unwrap_or(fallback)
        };
        assert!(
            Style::new(
                get("discard_boldness", 0.5),
                get("sinking", 0.0),
                get("guard_retention", 0.5)
            )
            .is_err(),
            "{case}"
        );
    }
}

#[test]
fn a_drawn_style_lands_inside_its_bands() {
    // The draw itself cannot match Python's -- `uniform` is a different
    // algorithm on a different stream -- but the bands it respects must.
    let mut rng = piquet_core::rng::Rng::seeded(1674);
    for _ in 0..200 {
        let style = Style::random(&mut rng);
        for (name, low, high) in CALIBRATED {
            let value = match name {
                "discard_boldness" => style.discard_boldness,
                "sinking" => style.sinking,
                _ => style.guard_retention,
            };
            assert!((low..=high).contains(&value), "{name} drew {value}");
        }
    }
}

// -- heuristics: the ladder itself -------------------------------------------

use piquet_core::heuristics::HeuristicAgent;
use piquet_core::play::play_pack;

#[test]
fn the_ladder_makes_exactly_the_recorded_decisions() {
    // An agent's own draws are the one thing golden vectors cannot check --
    // no two languages share a generator. But a HeuristicAgent with
    // erraticism 0 and the BALANCED style never draws at all for a decision:
    // `rung` returns the level directly and the sinking roll cannot fire at
    // probability zero. So the whole AI is comparable exactly, and a port that
    // reproduces the rules but gets these wrong has a strategy bug no other
    // vector would catch.
    let vec = vectors("heuristics.json");
    let packs = vec["packs"].as_object().unwrap();

    for game in vec["games"].as_array().unwrap() {
        let pack_name = game["pack"].as_str().unwrap();
        let pack = pack_of(&packs[pack_name]);
        let elder_level = game["elder_level"].as_u64().unwrap() as u32;
        let younger_level = game["younger_level"].as_u64().unwrap() as u32;

        // The seeds are irrelevant: neither agent draws.
        let mut elder = HeuristicAgent::new(elder_level, 1).unwrap();
        let mut younger = HeuristicAgent::new(younger_level, 2).unwrap();

        let (deal, _) = play_pack(&pack, &mut elder, &mut younger, None).unwrap();
        let where_ = format!("{pack_name}: L{elder_level} against L{younger_level}");

        assert_eq!(
            i64::from(deal.log.total(Player::Elder)),
            game["elder_score"].as_i64().unwrap(),
            "{where_}: elder's score"
        );
        assert_eq!(
            i64::from(deal.log.total(Player::Younger)),
            game["younger_score"].as_i64().unwrap(),
            "{where_}: younger's score"
        );
        assert_eq!(
            deal.tricks_won(Player::Elder) as u64,
            game["elder_tricks"].as_u64().unwrap(),
            "{where_}: tricks"
        );

        // Every card, in the order it was played -- the strongest of these
        // assertions, because it fails on the first decision that differs
        // rather than on a score that happens to come out the same.
        let led: Vec<String> = deal.tricks.iter().map(|t| t.led.code()).collect();
        let followed: Vec<String> = deal
            .tricks
            .iter()
            .map(|t| t.followed.expect("a finished trick").code())
            .collect();
        let played: Vec<String> = led.into_iter().chain(followed).collect();
        let want: Vec<&str> = game["cards_played"]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| c.as_str().unwrap())
            .collect();
        assert_eq!(played, want, "{where_}: the cards played");

        let events: Vec<serde_json::Value> = deal
            .log
            .events
            .iter()
            .map(|e| {
                serde_json::json!({
                    "player": e.player.name(),
                    "amount": e.amount,
                    "category": e.category.name(),
                })
            })
            .collect();
        assert_eq!(
            serde_json::Value::Array(events),
            game["events"],
            "{where_}: the event log"
        );
    }
}

#[test]
fn the_vectors_actually_discriminate_between_rungs() {
    // Index order and its reverse deal whole suits to one player, so most
    // plays are forced and the ladder barely shows. If these numbers collapse,
    // the test above is passing on packs that cannot tell a rung-1 agent from
    // a rung-4 one.
    let vec = vectors("heuristics.json");
    let games = vec["games"].as_array().unwrap();
    let sequences: std::collections::HashSet<String> = games
        .iter()
        .map(|g| g["cards_played"].to_string())
        .collect();
    assert!(
        sequences.len() > games.len() / 4,
        "only {} distinct card sequences across {} games",
        sequences.len(),
        games.len()
    );

    let scores: std::collections::HashSet<i64> = games
        .iter()
        .map(|g| g["elder_score"].as_i64().unwrap())
        .collect();
    assert!(scores.len() > 5, "the rungs barely differ in outcome");
}

// -- inference ---------------------------------------------------------------

use piquet_core::inference::{known_voids, opponent_hand_size, opponent_played, possible_hands};

#[test]
fn the_candidate_set_matches_and_never_excludes_the_truth() {
    // Two assertions, and the second matters more. The count must agree with
    // the oracle; but the *invariant* is that the opponent's real hand is
    // always a candidate, because inference that rules out the truth is worse
    // than inference that rules out nothing, and no count would reveal it.
    let vec = vectors("inference.json");
    let pack = pack_of(&vec["pack"]);
    let elder_takes = vec["elder_takes"].as_u64().unwrap() as usize;
    let mut rng = piquet_core::rng::Rng::seeded(1);

    let mut deal = deal_from(&pack).unwrap();
    let mut recorded = vec["snapshots"].as_array().unwrap().iter();

    let check = |deal: &Deal,
                 recorded: &mut std::slice::Iter<serde_json::Value>,
                 rng: &mut piquet_core::rng::Rng| {
        for player in [Player::Elder, Player::Younger] {
            let view = view_for(deal, player, None);
            if view.phase == Phase::Complete {
                continue;
            }
            let want = recorded.next().expect("a recorded snapshot");
            let where_ = format!("step {} {}", want["step"], want["me"]);

            assert_eq!(view.me.name(), want["me"].as_str().unwrap(), "{where_}");
            assert_eq!(
                opponent_hand_size(&view) as u64,
                want["opponent_hand_size"].as_u64().unwrap(),
                "{where_}"
            );
            let mut voids: Vec<u64> = known_voids(&view).iter().map(|s| u64::from(s.0)).collect();
            voids.sort_unstable();
            let want_voids: Vec<u64> = want["known_voids"]
                .as_array()
                .unwrap()
                .iter()
                .map(|s| s.as_u64().unwrap())
                .collect();
            assert_eq!(voids, want_voids, "{where_}");
            assert_eq!(
                opponent_played(&view).code(),
                want["opponent_played"].as_str().unwrap(),
                "{where_}"
            );

            let hands = possible_hands(&view, None, true, rng);
            assert_eq!(
                hands.len() as u64,
                want["candidates"].as_u64().unwrap(),
                "{where_}: candidate count"
            );
            let actual = deal.hand_of(player.opponent());
            assert!(
                hands.contains(&actual),
                "{where_}: inference ruled out the opponent's real hand"
            );
            assert!(
                want["actual_is_a_candidate"].as_bool().unwrap(),
                "{where_}: the oracle agrees"
            );
        }
    };

    check(&deal, &mut recorded, &mut rng);
    for (player, take) in [(Player::Elder, Some(elder_takes)), (Player::Younger, None)] {
        let limit = deal.exchange_limit(player);
        let count = take.unwrap_or(limit);
        let discard =
            Hand::of(&deal.hand_of(player).cards().take(count).collect::<Vec<_>>()).unwrap();
        deal = deal.exchange(player, discard).unwrap();
        check(&deal, &mut recorded, &mut rng);
    }
    while matches!(
        deal.phase,
        Phase::DeclarePoint | Phase::DeclareSequences | Phase::DeclareSets
    ) {
        let player = deal.to_declare().unwrap();
        let category = deal.declaring_category().unwrap();
        deal = deal
            .declare(player, Declaration::full(deal.hand_of(player), category))
            .unwrap();
        check(&deal, &mut recorded, &mut rng);
    }
    let mut tricks = 0;
    while deal.phase == Phase::Play && tricks < 8 {
        let player = deal.to_play().unwrap();
        let card = deal.legal_plays(Some(player)).cards().next().unwrap();
        deal = deal.play(player, card).unwrap();
        if deal.current_trick.is_none() {
            tricks += 1;
            check(&deal, &mut recorded, &mut rng);
        }
    }
    assert!(recorded.next().is_none(), "unconsumed snapshots");
}

/// What the candidate counts show about who knows what, and when.
///
/// `docs/DESIGN.md` §4.2 argues the play phase is nearly perfect information,
/// and it is -- but not symmetrically, and the asymmetry is the more
/// interesting half.
///
/// Younger hears elder's declarations as the dialogue goes along, so her
/// candidate set collapses 125,970 → 91 → 1 before a card is played. Elder
/// hears only her *answers* -- good, not good, equal -- until he has led, so he
/// narrows only as far as those allow: 5,005 → 958 → 255, and leads to the
/// first trick with a couple of hundred hands still possible against her one.
/// **That is the blind first lead, measured.**
///
/// An earlier version had him at 5,005 throughout, and this comment called
/// that the blind lead. It was the inference discarding answers he had heard:
/// its silence rule read every unnamed category as "nothing held", which
/// before his lead ruled out every candidate and so told him nothing at all.
///
/// One trick later they are both down to a single hand.
#[test]
fn elder_leads_blind_and_younger_does_not() {
    let vec = vectors("inference.json");
    let snapshots = vec["snapshots"].as_array().unwrap();
    let count_at = |action: &str, me: &str| -> u64 {
        snapshots
            .iter()
            .find(|s| s["action"] == action && s["me"] == me)
            .unwrap_or_else(|| panic!("no snapshot for {action} / {me}"))["candidates"]
            .as_u64()
            .unwrap()
    };

    // Through the dialogue, younger narrows and elder does not.
    let younger_narrowing: Vec<u64> = [
        "younger exchanges 6",
        "younger declares point",
        "younger declares sequences",
    ]
    .iter()
    .map(|action| count_at(action, "younger"))
    .collect();
    assert!(
        younger_narrowing.windows(2).all(|w| w[1] <= w[0]),
        "younger should only ever learn more: {younger_narrowing:?}"
    );
    assert_eq!(
        *younger_narrowing.last().unwrap(),
        1,
        "by the end of the dialogue she should know his hand exactly"
    );

    // Elder narrows too, but on her answers alone, and stays far behind.
    let elder_narrowing: Vec<u64> = [
        "younger exchanges 6",
        "younger declares point",
        "younger declares sequences",
        "younger declares sets",
    ]
    .iter()
    .map(|action| count_at(action, "elder"))
    .collect();
    assert!(
        elder_narrowing.windows(2).all(|w| w[1] <= w[0]),
        "elder should only ever learn more: {elder_narrowing:?}"
    );
    assert!(
        elder_narrowing.last() < elder_narrowing.first(),
        "her answers are public, and they tell him something: {elder_narrowing:?}"
    );
    let elder_at_the_lead = count_at("younger declares sets", "elder");
    assert!(
        elder_at_the_lead >= 100,
        "elder should still be guessing when he leads, not {elder_at_the_lead}"
    );

    // And once he has led, her declarations arrive and he catches up at once.
    assert_eq!(count_at("after trick 1", "elder"), 1);
    assert_eq!(count_at("after trick 1", "younger"), 1);

    // From there the play really is perfect information for both.
    for snapshot in snapshots
        .iter()
        .filter(|s| s["action"].as_str().unwrap().starts_with("after trick"))
    {
        assert_eq!(
            snapshot["candidates"].as_u64().unwrap(),
            1,
            "{}: the play should be determined",
            snapshot["action"]
        );
    }
}

// -- the solver agent --------------------------------------------------------

use piquet_core::solver::SolverAgent;

#[test]
fn the_solver_agent_plays_the_recorded_cards() {
    // Rung five samples opponent hands, which would normally put it beyond
    // what a golden vector can check -- no two languages share a generator.
    //
    // These four packs happen to keep the candidate set inside `max_worlds`
    // all the way down, so no sample is ever taken and the agent is
    // deterministic. That is a property of the packs and NOT of the solver: a
    // differential run over 150 random deals found two where the set reached
    // 35 against a limit of 30, and the two engines then chose differently and
    // correctly. The vector generator now asserts the constraint rather than
    // relying on it, so a later pack cannot silently emit a case nothing can
    // satisfy.
    let vec = vectors("solver.json");
    for game in vec["agent_games"].as_array().unwrap() {
        let pack = pack_of(&game["pack_codes"]);
        let solver_is_elder = game["solver_seat"] == "elder";

        let mut solver = SolverAgent::new(1);
        let mut ladder = HeuristicAgent::new(4, 2).unwrap().named("L4");
        let (deal, _) = if solver_is_elder {
            play_pack(&pack, &mut solver, &mut ladder, None).unwrap()
        } else {
            play_pack(&pack, &mut ladder, &mut solver, None).unwrap()
        };

        let where_ = format!("{}: solver as {}", game["pack"], game["solver_seat"]);
        assert_eq!(
            i64::from(deal.log.total(Player::Elder)),
            game["elder_score"].as_i64().unwrap(),
            "{where_}: elder's score"
        );
        assert_eq!(
            i64::from(deal.log.total(Player::Younger)),
            game["younger_score"].as_i64().unwrap(),
            "{where_}: younger's score"
        );
        assert_eq!(
            deal.tricks_won(Player::Elder) as u64,
            game["elder_tricks"].as_u64().unwrap(),
            "{where_}: tricks"
        );

        let led: Vec<String> = deal.tricks.iter().map(|t| t.led.code()).collect();
        let followed: Vec<String> = deal
            .tricks
            .iter()
            .map(|t| t.followed.expect("a finished trick").code())
            .collect();
        let played: Vec<String> = led.into_iter().chain(followed).collect();
        let want: Vec<&str> = game["cards_played"]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| c.as_str().unwrap())
            .collect();
        assert_eq!(played, want, "{where_}: the cards played");
    }
}

// ===========================================================================
// Gaps found by auditing this file against the Python suite.
//
// Section-level coverage looked complete and was not: four sections the
// Python checked had no Rust counterpart, and several fields inside sections
// that *were* checked went unread. Recorded here together rather than
// scattered, so the omission stays visible.
// ===========================================================================

#[test]
fn suit_views_and_rank_counts() {
    let vec = vectors("cards.json");
    for case in vec["suits"].as_array().unwrap() {
        let held = Hand::parse(case["hand"].as_str().unwrap()).unwrap();
        let suit = Suit(case["suit"].as_u64().unwrap() as u8);
        assert_eq!(
            held.in_suit(suit).code(),
            case["in_suit"].as_str().unwrap(),
            "{case}"
        );
        let ranks: Vec<u64> = held.ranks_in(suit).iter().map(|r| u64::from(r.0)).collect();
        let want: Vec<u64> = case["ranks_in"]
            .as_array()
            .unwrap()
            .iter()
            .map(|r| r.as_u64().unwrap())
            .collect();
        assert_eq!(ranks, want, "{case}");
        for entry in case["counts"].as_array().unwrap() {
            let rank = Rank(entry["rank"].as_u64().unwrap() as u8);
            assert_eq!(
                u64::from(held.count_of(rank)),
                entry["count"].as_u64().unwrap(),
                "{case}: count of {rank:?}"
            );
        }
    }
}

#[test]
fn set_operations_on_hands() {
    let vec = vectors("cards.json");
    for case in vec["set_ops"].as_array().unwrap() {
        let left = Hand::parse(case["left"].as_str().unwrap()).unwrap();
        let right = Hand::parse(case["right"].as_str().unwrap()).unwrap();
        let got = match case["op"].as_str().unwrap() {
            "sub" => left.without(right),
            "and" => left.intersect(right),
            // Strict about overlap: a card cannot be in two places, and a
            // silent merge would hide a dealing bug.
            _ => left
                .union(right)
                .expect("the vectors only union disjoint hands"),
        };
        assert_eq!(got.code(), case["result"].as_str().unwrap(), "{case}");
    }
}

#[test]
fn set_scoring() {
    let vec = vectors("combos.json");
    for case in vec["set_scores"].as_array().unwrap() {
        let made = CardSet {
            rank: Rank::ACE,
            count: case["count"].as_u64().unwrap() as u32,
        };
        assert_eq!(u64::from(made.score()), case["score"].as_u64().unwrap());
    }
}

#[test]
fn invalid_declarations_are_refused() {
    // Claims must be of the right kind, genuinely held, and non-overlapping.
    let vec = vectors("declarations.json");
    for case in vec["validate"].as_array().unwrap() {
        let hand = Hand::parse(case["hand"].as_str().unwrap()).unwrap();
        let category = category_named(case["category"].as_str().unwrap());
        let claims: Vec<Combination> = case["claims"]
            .as_array()
            .unwrap()
            .iter()
            .map(|claim| match claim["kind"].as_str().unwrap() {
                "point" => Combination::Point(Point {
                    suit: Suit(claim["suit"].as_u64().unwrap() as u8),
                    length: claim["length"].as_u64().unwrap() as u32,
                    pip_value: claim["pip_value"].as_u64().unwrap() as u32,
                }),
                "sequence" => Combination::Sequence(Sequence {
                    suit: Suit(claim["suit"].as_u64().unwrap() as u8),
                    top: Rank(claim["top"].as_u64().unwrap() as u8),
                    length: claim["length"].as_u64().unwrap() as u32,
                }),
                _ => Combination::Set(CardSet {
                    rank: Rank(claim["rank"].as_u64().unwrap() as u8),
                    count: claim["count"].as_u64().unwrap() as u32,
                }),
            })
            .collect();
        assert!(
            Declaration { claims }.validate(hand, category).is_err(),
            "{}: should have been refused",
            case["name"]
        );
    }
}

#[test]
fn younger_answers_in_the_recorded_words() {
    // "good" / "not good" / "equal" is the dialogue at the table, and the
    // strings are part of the contract rather than decoration.
    let vec = vectors("declarations.json");
    for case in vec["dialogue"].as_array().unwrap() {
        let result = build_result(case);
        assert_eq!(
            result.response(),
            case["response"].as_str().unwrap(),
            "{case}"
        );
        assert_eq!(
            u64::from(result.younger.score()),
            case["younger_score_if_won"].as_u64().unwrap(),
            "{case}"
        );
    }
}

#[test]
fn the_tutors_breakdown_matches() {
    // `by_category` exists for the tutor. Nothing in the engine reads it, so
    // it would drift unnoticed.
    let vec = vectors("scoring.json");
    for case in vec["cases"].as_array().unwrap() {
        let log = rebuild_log(&case["events"]);
        for (name, player) in [("elder", Player::Elder), ("younger", Player::Younger)] {
            let got: std::collections::BTreeMap<String, i64> = log
                .by_category(player)
                .into_iter()
                .map(|(c, n)| (c.name().to_string(), i64::from(n)))
                .collect();
            let want: std::collections::BTreeMap<String, i64> = case["by_category"][name]
                .as_object()
                .unwrap()
                .iter()
                .map(|(k, v)| (k.clone(), v.as_i64().unwrap()))
                .collect();
            assert_eq!(got, want, "{}: {name}", case["name"]);
        }
    }
}

#[test]
fn the_best_card_is_the_recorded_one() {
    use piquet_core::solver::best_card;
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

        let (card, value) = best_card(elder, younger, leader, led, tricks, EVEN).unwrap();
        assert_eq!(
            card_code(card),
            case["best_card"].as_str().unwrap(),
            "{}: best card",
            case["name"]
        );
        assert_eq!(
            value,
            case["best_value"].as_i64().unwrap(),
            "{}: its value",
            case["name"]
        );
    }
}

#[test]
fn what_each_player_heard_and_saw_matches() {
    // `heard` and `seen` are the leak-prone fields and neither suite compared
    // their contents -- only that they were empty before elder led.
    let vec = vectors("observation.json");
    let pack = pack_of(&vec["pack"]);
    for run in vec["runs"].as_array().unwrap() {
        let elder_takes = run["elder_takes"].as_u64().map(|n| n as usize);
        let observed = observe(&pack, elder_takes);
        for ((view, _), want) in observed.iter().zip(run["snapshots"].as_array().unwrap()) {
            let where_ = format!("{}: step {} {}", run["name"], want["step"], want["me"]);

            let heard: Vec<(String, u64, Option<u64>)> = view
                .heard
                .iter()
                .map(|a| {
                    (
                        a.category.name().to_string(),
                        u64::from(a.primary),
                        a.tiebreak.map(u64::from),
                    )
                })
                .collect();
            let want_heard: Vec<(String, u64, Option<u64>)> = want["heard"]
                .as_array()
                .unwrap()
                .iter()
                .map(|a| {
                    (
                        a["category"].as_str().unwrap().to_string(),
                        a["primary"].as_u64().unwrap(),
                        a["tiebreak"].as_u64(),
                    )
                })
                .collect();
            assert_eq!(heard, want_heard, "{where_}: heard");

            let said: Vec<(String, u64, Option<u64>)> = view
                .said
                .iter()
                .map(|a| {
                    (
                        a.category.name().to_string(),
                        u64::from(a.primary),
                        a.tiebreak.map(u64::from),
                    )
                })
                .collect();
            let want_said: Vec<(String, u64, Option<u64>)> = want["said"]
                .as_array()
                .unwrap()
                .iter()
                .map(|a| {
                    (
                        a["category"].as_str().unwrap().to_string(),
                        a["primary"].as_u64().unwrap(),
                        a["tiebreak"].as_u64(),
                    )
                })
                .collect();
            assert_eq!(said, want_said, "{where_}: said");

            let seen: Vec<String> = view.seen.iter().map(|c| c.describe()).collect();
            let want_seen: Vec<&str> = want["seen"]
                .as_array()
                .unwrap()
                .iter()
                .map(|c| c.as_str().unwrap())
                .collect();
            assert_eq!(seen, want_seen, "{where_}: seen");

            let outcomes: Vec<(String, Option<String>)> = view
                .outcomes
                .iter()
                .map(|(c, w)| (c.name().to_string(), w.map(|p| p.name().to_string())))
                .collect();
            let want_outcomes: Vec<(String, Option<String>)> = want["outcomes"]
                .as_array()
                .unwrap()
                .iter()
                .map(|o| {
                    let pair = o.as_array().unwrap();
                    (
                        pair[0].as_str().unwrap().to_string(),
                        pair[1].as_str().map(|s| s.to_string()),
                    )
                })
                .collect();
            assert_eq!(outcomes, want_outcomes, "{where_}: outcomes");
        }
    }
}

// -- the move log ------------------------------------------------------------

#[test]
fn the_move_log_has_the_shape_the_python_writes() {
    // Andrew's product requirement is a persistent record of agent decisions,
    // so that training epochs can later be correlated with skill gained. It is
    // only useful if something else can read it, so the keys and types are
    // pinned against the Python's own output rather than invented here.
    use piquet_core::play::DealRecord;

    let pack: Vec<piquet_core::cards::Card> = (0u8..32).map(piquet_core::cards::Card).collect();
    let mut elder = HeuristicAgent::new(2, 1).unwrap().named("L2");
    let mut younger = HeuristicAgent::new(3, 2).unwrap().named("L3");
    let (deal, decisions) = play_pack(&pack, &mut elder, &mut younger, None).unwrap();
    let record = DealRecord::of(1, &deal, "L2", "L3", decisions);

    let parsed: serde_json::Value =
        serde_json::from_str(&record.as_json()).expect("the log must be valid JSON");

    let mut keys: Vec<&str> = parsed
        .as_object()
        .unwrap()
        .keys()
        .map(|k| k.as_str())
        .collect();
    keys.sort_unstable();
    assert_eq!(
        keys,
        [
            "bonus",
            "deal",
            "decisions",
            "elder_agent",
            "elder_score",
            "elder_tricks",
            "younger_agent",
            "younger_score"
        ]
    );

    let decisions = parsed["decisions"].as_array().unwrap();
    assert!(!decisions.is_empty());
    let mut decision_keys: Vec<&str> = decisions[0]
        .as_object()
        .unwrap()
        .keys()
        .map(|k| k.as_str())
        .collect();
    decision_keys.sort_unstable();
    assert_eq!(
        decision_keys,
        ["agent", "choice", "forgone", "hand", "options", "phase", "player", "ply"]
    );

    // The first decision is elder's exchange: a card-code choice, no options,
    // nothing forgone. Matching the Python's own first row.
    assert_eq!(decisions[0]["ply"], 1);
    assert_eq!(decisions[0]["player"], "elder");
    assert_eq!(decisions[0]["phase"], "elder_exchange");
    assert!(decisions[0]["options"].is_null());
    assert!(decisions[0]["forgone"].is_null());

    // A declaration records what was forgone, which is how sinking becomes
    // visible in the log at all.
    let declared = decisions
        .iter()
        .find(|d| d["phase"].as_str().unwrap().starts_with("declare"))
        .expect("a declaration is logged");
    assert!(declared["forgone"].is_i64());

    // A play records how many legal cards there were, which is what makes a
    // decision's difficulty measurable after the fact.
    let played = decisions
        .iter()
        .find(|d| d["phase"] == "play")
        .expect("a play is logged");
    assert!(played["options"].is_i64());

    // The scores agree with the deal they came from.
    assert_eq!(
        parsed["elder_score"],
        i64::from(deal.log.total(Player::Elder))
    );
    assert_eq!(
        parsed["younger_score"],
        i64::from(deal.log.total(Player::Younger))
    );
}

#[test]
fn the_move_log_survives_the_suit_symbols_in_it() {
    // Detail strings carry `10♦` and friends; a naive escaper would mangle
    // them, and the file is meant to be read back by an analysis script.
    use piquet_core::play::DealRecord;

    let pack: Vec<piquet_core::cards::Card> = (0u8..32).map(piquet_core::cards::Card).collect();
    let mut elder = HeuristicAgent::new(4, 1).unwrap().named("a\"quoted\" name");
    let mut younger = HeuristicAgent::new(4, 2).unwrap().named("L4");
    let (deal, decisions) = play_pack(&pack, &mut elder, &mut younger, None).unwrap();
    let record = DealRecord::of(1, &deal, "a\"quoted\" name", "L4", decisions);

    let parsed: serde_json::Value =
        serde_json::from_str(&record.as_json()).expect("quotes must be escaped");
    assert_eq!(parsed["elder_agent"], "a\"quoted\" name");
}

// -- match: the move log -------------------------------------------------------

use piquet_core::play::DealRecord;

#[test]
fn the_move_log_records_exactly_the_recorded_decisions() {
    // The training log (Andrew: "so the correlation between training epochs
    // and skill gained can be analyzed later"), compared as parsed JSON: the
    // two writers may differ in whether they escape non-ASCII, and both parse
    // to the same log.
    let vec = vectors("match.json");
    let packs = vec["packs"].as_object().unwrap();
    for game in vec["games"].as_array().unwrap() {
        let pack_name = game["pack"].as_str().unwrap();
        let pack = pack_of(&packs[pack_name]);
        let e = game["elder_level"].as_u64().unwrap() as u32;
        let y = game["younger_level"].as_u64().unwrap() as u32;
        let (elder_name, younger_name) = (format!("L{e}"), format!("L{y}"));
        let mut elder = HeuristicAgent::new(e, 1).unwrap().named(&elder_name);
        let mut younger = HeuristicAgent::new(y, 2).unwrap().named(&younger_name);
        let (deal, decisions) = play_pack(&pack, &mut elder, &mut younger, None).unwrap();
        let record = DealRecord::of(3, &deal, &elder_name, &younger_name, decisions);
        let line: serde_json::Value =
            serde_json::from_str(&record.as_json()).expect("the log is JSON");
        assert_eq!(line, game["record"], "{pack_name}: L{e} against L{y}");
    }
}

// -- tournament: the arithmetic of strength --------------------------------------

use piquet_core::tournament::{format_table, ratings, DuelResult, PartieResult};

fn duel_result(r: &serde_json::Value) -> DuelResult {
    DuelResult {
        name_a: r["name_a"].as_str().unwrap().to_string(),
        name_b: r["name_b"].as_str().unwrap().to_string(),
        pairs: r["pairs"].as_u64().unwrap() as usize,
        a_wins: r["a_wins"].as_u64().unwrap() as usize,
        b_wins: r["b_wins"].as_u64().unwrap() as usize,
        drawn: r["drawn"].as_u64().unwrap() as usize,
        a_points: r["a_points"].as_i64().unwrap() as i32,
        b_points: r["b_points"].as_i64().unwrap() as i32,
    }
}

#[test]
fn results_have_the_recorded_win_rates_and_margins() {
    let vec = vectors("tournament.json");
    for case in vec["properties"].as_array().unwrap() {
        let r = duel_result(&case["result"]);
        assert_eq!(r.to_string(), case["text"].as_str().unwrap());
        assert!(
            (r.a_win_rate() - case["a_win_rate"].as_f64().unwrap()).abs() < 1e-12,
            "{case}"
        );
        assert!(
            (r.margin() - case["margin"].as_f64().unwrap()).abs() < 1e-12,
            "{case}"
        );
    }
    for case in vec["partie_properties"].as_array().unwrap() {
        let f = &case["result"];
        let r = PartieResult {
            name_a: f["name_a"].as_str().unwrap().to_string(),
            name_b: f["name_b"].as_str().unwrap().to_string(),
            pairs: f["pairs"].as_u64().unwrap() as usize,
            a_wins: f["a_wins"].as_u64().unwrap() as usize,
            b_wins: f["b_wins"].as_u64().unwrap() as usize,
            drawn: f["drawn"].as_u64().unwrap() as usize,
            a_settlement: f["a_settlement"].as_i64().unwrap() as i32,
        };
        assert_eq!(r.to_string(), case["text"].as_str().unwrap());
        assert!(
            (r.a_win_rate() - case["a_win_rate"].as_f64().unwrap()).abs() < 1e-12,
            "{case}"
        );
        assert!(
            (r.margin() - case["margin"].as_f64().unwrap()).abs() < 1e-12,
            "{case}"
        );
    }
}

#[test]
fn ratings_fit_as_recorded() {
    let vec = vectors("tournament.json");
    for fit in vec["fits"].as_array().unwrap() {
        let name = fit["results"].as_str().unwrap();
        let group: Vec<DuelResult> = vec["results"][name]
            .as_array()
            .unwrap()
            .iter()
            .map(duel_result)
            .collect();
        let anchor = fit["anchor"].as_str();
        let got = ratings(&group, anchor, 500, 0.5);
        let want = fit["ratings"].as_object().unwrap();
        assert_eq!(got.len(), want.len(), "{name}, anchored on {anchor:?}");
        for (agent, value) in got {
            let expected = want[&agent].as_f64().unwrap();
            assert!(
                (value - expected).abs() < 1e-9,
                "{name}, anchored on {anchor:?}: {agent} rates {value}, not {expected}"
            );
        }
    }
}

#[test]
fn the_table_prints_exactly_as_recorded() {
    // Printed figures round half to even from their exact binary values,
    // as the oracle's do: 6.25% is "6.2", a margin of 0.25 is "+0.2".
    let vec = vectors("tournament.json");
    for table in vec["tables"].as_array().unwrap() {
        let name = table["results"].as_str().unwrap();
        let group: Vec<DuelResult> = vec["results"][name]
            .as_array()
            .unwrap()
            .iter()
            .map(duel_result)
            .collect();
        let anchor = table["anchor"].as_str();
        assert_eq!(
            format_table(&group, anchor),
            table["text"].as_str().unwrap(),
            "{name}, anchored on {anchor:?}"
        );
    }
}

#[test]
fn a_table_of_ones_own_gives_the_recorded_chances() {
    // The Python's docstring: "measure your own and pass it as `table`". A
    // small uneven table, so ignoring it or mixing up the seats disagrees.
    let vec = vectors("chances.json");
    let row = |key: &str| -> Vec<f64> {
        vec["custom_table"][key]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| p.as_f64().unwrap())
            .collect()
    };
    let table = [row("elder"), row("younger")];
    for (seat, key) in [(Player::Elder, "elder"), (Player::Younger, "younger")] {
        assert_eq!(chances::density_in(seat, &table), &table[seat.index()][..]);
        let want: Vec<f64> = vec["custom_survival"][key]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| p.as_f64().unwrap())
            .collect();
        let got = chances::survival_in(seat, &table);
        assert_eq!(got.len(), want.len());
        for (g, w) in got.iter().zip(&want) {
            assert!((g - w).abs() < 1e-12, "{key}: {got:?} against {want:?}");
        }
    }
    for case in vec["custom_chances"].as_array().unwrap() {
        let got = chances::chance_of_in(
            case["needed"].as_i64().unwrap() as i32,
            case["deals_left"].as_u64().unwrap() as usize,
            case["elder_first"].as_bool().unwrap(),
            &table,
        );
        let want = case["chance"].as_f64().unwrap();
        assert!((got - want).abs() < 1e-12, "{case}: {got}");
    }
}

#[test]
fn the_measured_table_is_the_default() {
    let table = chances::measured();
    for seat in [Player::Elder, Player::Younger] {
        assert_eq!(chances::density_in(seat, table), chances::density(seat));
        assert_eq!(chances::survival_in(seat, table), chances::survival(seat));
    }
    for (needed, left, first) in [(18, 1, true), (40, 2, false), (100, 6, true)] {
        assert_eq!(
            chances::chance_of_in(needed, left, first, table),
            chances::chance_of(needed, left, first)
        );
    }
}
