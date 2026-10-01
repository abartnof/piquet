//! Running deals and parties: the loop that asks each agent in turn.
//!
//! Named `play` rather than `match`, which is a Rust keyword.
//!
//! Nothing here shuffles. `docs/DESIGN.md` §2.1 settles that no two languages
//! share a random number generator, so a deal is always handed in as an
//! explicit ordering of the pack; whoever wants a shuffled one brings their
//! own.

use crate::agents::Agent;
use crate::cards::Card;
use crate::observation::view_for;
use crate::partie::{Partie, Side, Standing};
use crate::rules::{deal_from, Deal, Phase};
use crate::scoring::Player;

/// One decision, as it goes into the move log.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Decision {
    pub ply: usize,
    pub player: Player,
    pub phase: Phase,
    pub agent: String,
    pub hand: String,
    pub choice: String,
    /// How many legal plays there were, for a play decision.
    pub options: Option<usize>,
    /// Points available but not claimed, for a declaration.
    pub forgone: Option<i32>,
}

/// Everything one deal produced.
///
/// The persistent move log. The user's product requirement is a record of agent
/// decisions "so the correlation between training epochs and skill gained can
/// be analyzed later", which needs the *decisions* and not only the scores.
///
/// One caveat the format carries from the original, recorded rather than
/// fixed: for an exchange or a play, `choice` is a card code and parses back.
/// For a declaration it is English prose — `"point of five (49), tierce to the
/// queen"` — which by design never names a suit and **cannot** be parsed back.
/// A consumer must branch on `phase` to know which it is looking at. That is
/// why `docs/DESIGN.md` §2.2 says the golden vectors needed a structured
/// export of their own rather than reusing this.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct DealRecord {
    pub deal: usize,
    pub elder_agent: String,
    pub younger_agent: String,
    pub decisions: Vec<Decision>,
    pub elder_score: i32,
    pub younger_score: i32,
    pub elder_tricks: usize,
    pub bonus: Option<String>,
}

/// Play one deal to completion, asking each agent in turn.
///
/// `standing` is where the partie stands, from elder's side; a deal played on
/// its own has none, and the agents simply cannot see one.
pub fn play_deal(
    start: Deal,
    elder: &mut dyn Agent,
    younger: &mut dyn Agent,
    standing: Option<Standing>,
) -> Result<(Deal, Vec<Decision>), String> {
    let mut deal = start;
    let mut decisions = Vec::new();
    let mut ply = 0usize;

    let note = |ply: &mut usize,
                decisions: &mut Vec<Decision>,
                deal: &Deal,
                player: Player,
                agent_name: &str,
                hand: String,
                choice: String,
                options: Option<usize>,
                forgone: Option<i32>| {
        *ply += 1;
        decisions.push(Decision {
            ply: *ply,
            player,
            phase: deal.phase,
            agent: agent_name.to_string(),
            hand,
            choice,
            options,
            forgone,
        });
    };

    for player in [Player::Elder, Player::Younger] {
        let view = view_for(&deal, player, standing);
        let agent: &mut dyn Agent = match player {
            Player::Elder => elder,
            Player::Younger => younger,
        };
        let discard = agent.exchange(&view);
        let name = agent.name().to_string();
        note(
            &mut ply,
            &mut decisions,
            &deal,
            player,
            &name,
            view.hand.code(),
            discard.code(),
            None,
            None,
        );
        deal = deal.exchange(player, discard)?;
    }

    while let Some(player) = deal.to_declare() {
        let category = deal.declaring_category().expect("a declaration phase");
        let view = view_for(&deal, player, standing);
        let agent: &mut dyn Agent = match player {
            Player::Elder => elder,
            Player::Younger => younger,
        };
        let declaration = agent.declare(&view, category);
        let available = crate::declarations::Declaration::full(view.hand, category).score() as i32;
        let name = agent.name().to_string();
        let choice = declaration.describe();
        let forgone = available - declaration.score() as i32;
        note(
            &mut ply,
            &mut decisions,
            &deal,
            player,
            &name,
            view.hand.code(),
            choice,
            None,
            Some(forgone),
        );
        deal = deal.declare(player, declaration)?;
    }

    while deal.phase == Phase::Play {
        let player = deal.to_play().expect("the play phase has a mover");
        let view = view_for(&deal, player, standing);
        let agent: &mut dyn Agent = match player {
            Player::Elder => elder,
            Player::Younger => younger,
        };
        let card = agent.play(&view);
        let name = agent.name().to_string();
        let options = view.legal_plays.len() as usize;
        note(
            &mut ply,
            &mut decisions,
            &deal,
            player,
            &name,
            view.hand.code(),
            card.code(),
            Some(options),
            None,
        );
        deal = deal.play(player, card)?;
    }

    Ok((deal, decisions))
}

/// Play a deal from an explicit pack ordering.
pub fn play_pack(
    pack: &[Card],
    elder: &mut dyn Agent,
    younger: &mut dyn Agent,
    standing: Option<Standing>,
) -> Result<(Deal, Vec<Decision>), String> {
    play_deal(deal_from(pack)?, elder, younger, standing)
}

/// Play a whole partie from a sequence of packs, one per deal.
///
/// The seat alternates, so the side that is elder changes every deal; the
/// agents are addressed as sides and seated accordingly.
pub fn play_partie(
    packs: &[Vec<Card>],
    side_a: &mut dyn Agent,
    side_b: &mut dyn Agent,
    opening_dealer: Side,
) -> Result<Partie, String> {
    let mut partie = Partie::new(opening_dealer);
    for pack in packs {
        if partie.complete() {
            break;
        }
        let elder_side = partie.elder();
        let standing = partie.standing();
        let (deal, _) = {
            let (elder, younger): (&mut dyn Agent, &mut dyn Agent) = match elder_side {
                Side::A => (side_a, side_b),
                Side::B => (side_b, side_a),
            };
            play_deal(deal_from(pack)?, elder, younger, Some(standing))?
        };
        partie = partie.record_scores(
            deal.log.total(Player::Elder),
            deal.log.total(Player::Younger),
        )?;
    }
    Ok(partie)
}

// -- the move log ------------------------------------------------------------

/// Escape a string for JSON. Control characters are escaped; everything above
/// them is emitted as UTF-8, so the suit symbols in a log's detail strings
/// survive as themselves.
fn escaped(text: &str) -> String {
    let mut out = String::with_capacity(text.len() + 2);
    for ch in text.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out
}

fn optional(value: Option<i64>) -> String {
    value.map_or_else(|| "null".to_string(), |v| v.to_string())
}

impl Decision {
    fn as_json(&self) -> String {
        format!(
            r#"{{"ply":{},"player":"{}","phase":"{}","agent":"{}","hand":"{}","choice":"{}","options":{},"forgone":{}}}"#,
            self.ply,
            self.player.name(),
            self.phase.value(),
            escaped(&self.agent),
            escaped(&self.hand),
            escaped(&self.choice),
            optional(self.options.map(|o| o as i64)),
            optional(self.forgone.map(i64::from)),
        )
    }
}

impl DealRecord {
    /// Assemble a record from a finished deal and the decisions that made it.
    pub fn of(
        number: usize,
        deal: &Deal,
        elder_agent: &str,
        younger_agent: &str,
        decisions: Vec<Decision>,
    ) -> DealRecord {
        // Who took it and what it was, "elder repique", as the original
        // writes it -- and the last one, as its loop leaves it (a deal holds
        // one at most: a repique and a pique cannot both be made).
        let bonus = deal
            .log
            .events
            .iter()
            .rev()
            .find(|e| e.category == crate::scoring::Category::Bonus)
            .map(|e| format!("{} {}", e.player.name(), e.detail));
        DealRecord {
            deal: number,
            elder_agent: elder_agent.to_string(),
            younger_agent: younger_agent.to_string(),
            decisions,
            elder_score: deal.log.total(Player::Elder),
            younger_score: deal.log.total(Player::Younger),
            elder_tricks: deal.tricks_won(Player::Elder),
            bonus,
        }
    }

    /// One deal per line, as the training analysis wants it.
    pub fn as_json(&self) -> String {
        let decisions: Vec<String> = self.decisions.iter().map(Decision::as_json).collect();
        format!(
            r#"{{"deal":{},"elder_agent":"{}","younger_agent":"{}","decisions":[{}],"elder_score":{},"younger_score":{},"elder_tricks":{},"bonus":{}}}"#,
            self.deal,
            escaped(&self.elder_agent),
            escaped(&self.younger_agent),
            decisions.join(","),
            self.elder_score,
            self.younger_score,
            self.elder_tricks,
            self.bonus
                .as_ref()
                .map_or_else(|| "null".to_string(), |b| format!("\"{}\"", escaped(b))),
        )
    }
}

/// Append records to a JSONL file, one deal per line.
pub fn write_jsonl(records: &[DealRecord], path: &std::path::Path) -> std::io::Result<()> {
    use std::io::Write;
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    let mut file = std::fs::File::create(path)?;
    for record in records {
        writeln!(file, "{}", record.as_json())?;
    }
    Ok(())
}
