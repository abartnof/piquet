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
