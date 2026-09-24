//! Replay a large corpus of oracle-played deals and compare move for move.
//!
//! The golden vectors are a *specification*: a handful of positions chosen
//! because somebody could say why they mattered. This is the other kind of
//! check — thousands of deals nobody chose, whose job is to find the
//! divergence no one thought to write a case for.
//!
//! Generate the corpus first, from `python/`:
//!
//! ```text
//! python tools/differential.py 2000 > /tmp/corpus.jsonl
//! ```
//!
//! The test **skips** when the corpus is absent rather than failing, because
//! it is deliberately not committed — it is large and regenerable, and a
//! fixture nobody reads is not worth versioning. `PIQUET_CORPUS` overrides the
//! path.

use std::path::PathBuf;

use piquet_core::cards::Card;
use piquet_core::heuristics::HeuristicAgent;
use piquet_core::play::play_pack;
use piquet_core::scoring::Player;
use piquet_core::solver::SolverAgent;

fn corpus_path() -> PathBuf {
    std::env::var("PIQUET_CORPUS")
        .unwrap_or_else(|_| "/tmp/corpus.jsonl".to_string())
        .into()
}

#[test]
fn the_two_engines_agree_over_a_large_corpus() {
    let path = corpus_path();
    let Ok(text) = std::fs::read_to_string(&path) else {
        eprintln!(
            "skipping: no corpus at {}. Generate one with \
             `python tools/differential.py 2000 > /tmp/corpus.jsonl`",
            path.display()
        );
        return;
    };

    let mut deals = 0usize;
    let mut skipped = 0usize;
    let mut divergences: Vec<String> = Vec::new();

    for (line_number, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        let case: serde_json::Value =
            serde_json::from_str(line).expect("each line is one played deal");

        // When the candidate set outgrows `max_worlds` the solver takes a
        // RANDOM SAMPLE of it, and at that point the two engines part company
        // legitimately: §2.1 settles that no two languages share a generator.
        // Such deals are skipped rather than compared loosely, because a
        // tolerant comparison here would hide the divergences that *are*
        // bugs.
        if case["sampled"].as_bool().unwrap_or(false) {
            skipped += 1;
            continue;
        }

        let pack: Vec<Card> = case["pack"]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| Card::parse(c.as_str().unwrap()).unwrap())
            .collect();
        let elder_level = case["elder_level"].as_u64().unwrap() as u32;
        let younger_level = case["younger_level"].as_u64().unwrap() as u32;

        // Level five means the solver in elder's seat.
        let mut solver = SolverAgent::new(1);
        let mut ladder_elder = HeuristicAgent::new(elder_level.min(4), 1).unwrap();
        let mut younger = HeuristicAgent::new(younger_level, 2).unwrap();
        let elder: &mut dyn piquet_core::agents::Agent = if elder_level == 5 {
            &mut solver
        } else {
            &mut ladder_elder
        };
        let (deal, _) = play_pack(&pack, elder, &mut younger, None)
            .unwrap_or_else(|e| panic!("line {}: the deal would not play: {e}", line_number + 1));

        let where_ = format!(
            "line {} (L{elder_level} vs L{younger_level})",
            line_number + 1
        );
        let mut note = |what: &str, got: String, want: String| {
            if got != want {
                divergences.push(format!(
                    "{where_}: {what}\n     rust: {got}\n     py:   {want}"
                ));
            }
        };

        note(
            "elder's score",
            deal.log.total(Player::Elder).to_string(),
            case["elder_score"].to_string(),
        );
        note(
            "younger's score",
            deal.log.total(Player::Younger).to_string(),
            case["younger_score"].to_string(),
        );
        note(
            "elder's tricks",
            deal.tricks_won(Player::Elder).to_string(),
            case["elder_tricks"].to_string(),
        );

        let played: Vec<String> = deal
            .tricks
            .iter()
            .map(|t| t.led.code())
            .chain(
                deal.tricks
                    .iter()
                    .map(|t| t.followed.expect("a finished trick has both cards").code()),
            )
            .collect();
        let want_played: Vec<String> = case["played"]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| c.as_str().unwrap().to_string())
            .collect();
        note("the cards played", played.join(" "), want_played.join(" "));

        // The event log catches what the scores can hide: the right total
        // arrived at through the wrong categories.
        let events: Vec<String> = deal
            .log
            .events
            .iter()
            .map(|e| {
                format!(
                    "{}/{}/{}/{}",
                    e.player.name(),
                    e.amount,
                    e.category.name(),
                    e.detail
                )
            })
            .collect();
        let want_events: Vec<String> = case["events"]
            .as_array()
            .unwrap()
            .iter()
            .map(|e| {
                let row = e.as_array().unwrap();
                format!(
                    "{}/{}/{}/{}",
                    row[0].as_str().unwrap(),
                    row[1].as_i64().unwrap(),
                    row[2].as_str().unwrap(),
                    row[3].as_str().unwrap()
                )
            })
            .collect();
        note("the event log", events.join(" | "), want_events.join(" | "));

        deals += 1;
    }

    eprintln!(
        "compared {deals} deals against the oracle; skipped {skipped} where the \
         solver sampled and the two generators legitimately part company"
    );
    assert!(deals > 0, "every deal was skipped; nothing was compared");
    assert!(
        divergences.is_empty(),
        "{} of {deals} deals diverged:\n\n{}",
        divergences.len(),
        divergences
            .iter()
            .take(5)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n\n")
    );
}
