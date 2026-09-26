//! The named opponents a person can sit down against.
//!
//! A skill setting is presented as a person rather than a number: each rung
//! of the capability ladder has a name and a one-line account of what that
//! player can do, so choosing an opponent is choosing which skill to face.
//! Every table -- the terminal, the browser, whatever comes after -- draws
//! from this one roster, so the same seed and level make the same opponent
//! wherever it is played.

use crate::agents::Agent;
use crate::heuristics::HeuristicAgent;
use crate::rng::Rng;
use crate::solver::SolverAgent;
use crate::style::Style;

/// One rung of the ladder, as a person.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Opponent {
    pub level: u32,
    pub name: &'static str,
    /// What they can do, as a clause: "Hoyle, who *watches what you show him*".
    pub gloss: &'static str,
}

pub const OPPONENTS: [Opponent; 5] = [
    Opponent {
        level: 1,
        name: "Bess",
        gloss: "plays her highest card and hopes",
    },
    Opponent {
        level: 2,
        name: "Cotton",
        gloss: "knows what a hand is worth",
    },
    Opponent {
        level: 3,
        name: "Cavendish",
        gloss: "remembers what has been played",
    },
    Opponent {
        level: 4,
        name: "Hoyle",
        gloss: "watches what you show him",
    },
    Opponent {
        level: 5,
        name: "Foster",
        gloss: "reads the endgame exactly",
    },
];

/// The opponent at this level, clamped onto the ladder.
pub fn opponent(level: u32) -> Opponent {
    OPPONENTS[(level.clamp(1, 5) - 1) as usize]
}

/// Build the agent for an opponent, drawing its seed and style from `rng`.
///
/// The style is drawn once here and held for the whole partie, which is what
/// `docs/DESIGN.md` §7 means by a style being stable. The draws are made in a
/// fixed order -- seed, then style -- so a table seeded the same way always
/// seats the same opponent.
pub fn seat(level: u32, rng: &mut Rng) -> Box<dyn Agent> {
    let who = opponent(level);
    let seed = rng.below(u32::MAX as usize) as u32;
    let style = Style::random(rng);
    if who.level >= 5 {
        Box::new(SolverAgent::new(seed).named(who.name))
    } else {
        Box::new(
            HeuristicAgent::new(who.level, seed)
                .expect("every rung on the roster is a valid level")
                .with_style(style)
                .named(who.name),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_roster_is_the_ladder_in_order() {
        for (i, who) in OPPONENTS.iter().enumerate() {
            assert_eq!(who.level as usize, i + 1);
        }
    }

    #[test]
    fn a_level_off_the_ladder_is_clamped_onto_it() {
        assert_eq!(opponent(0).level, 1);
        assert_eq!(opponent(9).level, 5);
    }

    #[test]
    fn an_opponent_answers_to_its_name() {
        let mut rng = Rng::seeded(1);
        for level in 1..=5 {
            assert_eq!(seat(level, &mut rng).name(), opponent(level).name);
        }
    }
}
