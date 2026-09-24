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

use piquet_core::declarations::{compare_in, Announcement, CategoryResult, Declaration};

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
