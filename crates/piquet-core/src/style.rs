//! Opponent style: a third axis, orthogonal to skill and erraticism.
//!
//! Every field runs 0.0 to 1.0, and 0.5 is neutral. The dimensions are
//! deliberately taken from what the literature argues about rather than
//! invented: each is a genuine judgement call with defensible answers on both
//! sides, which is what makes it a style rather than a mistake.

use crate::rng::Rng;

/// Bands each dimension is drawn from, chosen by measurement rather than taste.
///
/// Every one is narrow enough that the cost of an extreme setting stays below
/// roughly a point per deal -- less than the gap between two rungs of the
/// ladder. **Re-measure these whenever the ladder changes**, since what counts
/// as a near-equal option depends on how well the agent plays.
pub const CALIBRATED: [(&str, f64, f64); 3] = [
    ("discard_boldness", 0.35, 0.65),
    ("guard_retention", 0.35, 0.65),
    ("sinking", 0.0, 0.10),
];

#[derive(Clone, Copy, PartialEq, Debug)]
pub struct Style {
    /// How readily it wrecks its point chasing a sequence or a set. The oldest
    /// strategic question in the game -- Hoyle wrote a treatise on it in 1744.
    /// 0.0 keeps length at all costs; 1.0 chases combinations.
    pub discard_boldness: f64,
    /// How often it conceals a cheap declaration. Cavendish's central
    /// manoeuvre. 0.0 always declares everything; 1.0 sinks whenever it
    /// plausibly could.
    pub sinking: f64,
    /// Whether it hoards stop cards in the opponent's long suit or plays for
    /// length. 0.0 runs its own suits; 1.0 holds guards back.
    pub guard_retention: f64,
}

/// The neutral style. An agent given this one has no personality at all.
pub const BALANCED: Style = Style {
    discard_boldness: 0.5,
    sinking: 0.0,
    guard_retention: 0.5,
};

impl Style {
    pub fn new(discard_boldness: f64, sinking: f64, guard_retention: f64) -> Result<Style, String> {
        for (name, value) in [
            ("discard_boldness", discard_boldness),
            ("sinking", sinking),
            ("guard_retention", guard_retention),
        ] {
            if !(0.0..=1.0).contains(&value) {
                return Err(format!("{name} must be between 0 and 1, got {value}"));
            }
        }
        Ok(Style {
            discard_boldness,
            sinking,
            guard_retention,
        })
    }

    fn band(name: &str) -> (f64, f64) {
        CALIBRATED
            .iter()
            .find(|(field, _, _)| *field == name)
            .map(|(_, low, high)| (*low, *high))
            .expect("every field has a calibrated band")
    }

    /// Draw a style. Call once per opponent, at the start of a partie.
    ///
    /// Drawn from `CALIBRATED`, not from the full 0-to-1 range: the bands are
    /// chosen by measurement so that no style costs much more than a point per
    /// deal, which keeps style from quietly becoming a skill setting.
    pub fn random(rng: &mut Rng) -> Style {
        let draw = |rng: &mut Rng, name: &str| {
            let (low, high) = Style::band(name);
            rng.uniform(low, high)
        };
        Style {
            discard_boldness: draw(rng, "discard_boldness"),
            guard_retention: draw(rng, "guard_retention"),
            sinking: draw(rng, "sinking"),
        }
    }

    fn value_of(&self, name: &str) -> f64 {
        match name {
            "discard_boldness" => self.discard_boldness,
            "sinking" => self.sinking,
            _ => self.guard_retention,
        }
    }

    /// A short phrase for the tutor, so a habit can be named and read.
    ///
    /// Bands are read *relative to the calibrated range*, not to the raw 0-to-1
    /// scale. They have to be: the calibrated bands are narrow enough to keep
    /// style EV-neutral, so on an absolute scale every opponent would be
    /// described as "even-handed" and the tutor would have nothing to say.
    pub fn describe(&self) -> String {
        let band = |name: &str, low: &str, mid: &str, high: &str| -> String {
            let (start, end) = Style::band(name);
            let span = end - start;
            let where_ = if span == 0.0 {
                0.5
            } else {
                (self.value_of(name) - start) / span
            };
            if where_ < 0.34 {
                low.to_string()
            } else if where_ < 0.67 {
                mid.to_string()
            } else {
                high.to_string()
            }
        };
        [
            band(
                "discard_boldness",
                "cautious discarder",
                "even-handed",
                "bold discarder",
            ),
            band(
                "sinking",
                "declares everything",
                "occasionally conceals",
                "conceals what it can",
            ),
            band(
                "guard_retention",
                "runs its suits",
                "balanced",
                "hoards guards",
            ),
        ]
        .join(" · ")
    }
}
