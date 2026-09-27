//! Does settling at the leaf actually play better?
//!
//! Measured the way the failed attempt was measured: **mirrored last deals,
//! stacked at standings where the objective should matter most**, and scored
//! in settlement rather than in deal points. The previous try — pricing a
//! point and feeding it in as a linear weight — went 0 won, 9 lost, 66 drawn
//! over 75 such deals.
//!
//! A last deal is the sharpest case available: with no deals to follow, the
//! settlement is exact rather than an expectation over futures.

use piquet_core::agents::Agent;
use piquet_core::cards::{Card, Hand};
use piquet_core::chances::settlement_of;
use piquet_core::declarations::Declaration;
use piquet_core::observation::View;
use piquet_core::partie::Standing;
use piquet_core::play::play_deal;
use piquet_core::prior::RUNG4;
use piquet_core::rng::Rng;
use piquet_core::rules::deal_from;
use piquet_core::scoring::{Category, Player};
use piquet_core::solver::{settled_log, Estimates, SolverAgent};
use std::io::Write;

/// Standings chosen for where the two objectives come apart.
const STANDINGS: [(i32, i32, &str); 6] = [
    (82, 70, "both short, me closer"),
    (70, 82, "both short, them closer"),
    (95, 88, "both a whisker short"),
    (88, 95, "both a whisker short, mirrored"),
    (120, 88, "I am safe, they are not"),
    (88, 120, "they are safe, I am not"),
];

/// `settle [deals] [worlds] [--prior] [--out FILE]` runs the measurement, writing one
/// line per pair to FILE if asked; `settle --compare FIRST SECOND` pairs two
/// such files deal by deal; `settle --show FILE STANDING DEAL` replays one
/// recorded pair and says what the settling search believed at each card.
fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    if args.first().map(String::as_str) == Some("--show") {
        let parsed = match args.as_slice() {
            [_, path, standing, deal] => standing
                .parse()
                .ok()
                .zip(deal.parse().ok())
                .map(|(s, d)| (path.clone(), s, d)),
            _ => None,
        };
        let Some((path, standing, deal)) = parsed else {
            eprintln!("usage: settle --show FILE STANDING DEAL");
            std::process::exit(2);
        };
        if let Err(e) = show(&path, standing, deal) {
            eprintln!("settle: {e}");
            std::process::exit(1);
        }
        return;
    }
    if args.first().map(String::as_str) == Some("--compare") {
        if let [_, first, second] = args.as_slice() {
            if let Err(e) = compare(first, second) {
                eprintln!("settle: {e}");
                std::process::exit(1);
            }
            return;
        }
        eprintln!("usage: settle --compare FIRST SECOND");
        std::process::exit(2);
    }
    // Both agents weigh the opponent's hands by the fitted prior (prior.rs).
    let prior = match args.iter().position(|a| a == "--prior") {
        Some(at) => {
            args.remove(at);
            true
        }
        None => false,
    };
    let out_path = match args.iter().position(|a| a == "--out") {
        Some(at) if at + 1 < args.len() => {
            let path = args.remove(at + 1);
            args.remove(at);
            Some(path)
        }
        Some(_) => {
            eprintln!("usage: settle [deals] [worlds] [--out FILE]");
            std::process::exit(2);
        }
        None => None,
    };

    let deals: usize = args.first().and_then(|a| a.parse().ok()).unwrap_or(75);
    // Opponent worlds each solver samples per decision. Both agents get the
    // same number, so only the objective differs: the question it serves is
    // whether settling -- which is non-linear where the flat objective is
    // nearly linear -- needs a thicker sample than thirty (PLAN.md TODO 1).
    let worlds: usize = args.get(1).and_then(|a| a.parse().ok()).unwrap_or(30);

    let mut out = out_path.map(|path| {
        let mut file = std::io::BufWriter::new(
            std::fs::File::create(&path).unwrap_or_else(|e| panic!("{path}: {e}")),
        );
        let header = Header {
            deals,
            worlds,
            prior,
        };
        writeln!(file, "{}", header.line()).expect("the record is writable");
        writeln!(file, "{HEADER}").expect("the record is writable");
        file
    });

    println!(
        "  mirrored LAST deals, scored in settlement\n\
         \x20 settling-at-the-leaf against the flat deal objective\n\
         \x20 (positive means settling is ahead)\n"
    );
    println!(
        "  {worlds} opponent worlds a decision, for both agents{}\n",
        if prior {
            ", weighed by the fitted prior"
        } else {
            ""
        }
    );
    println!(
        "  {:<34} {:>5} {:>5} {:>5}  {:>16}",
        "standing (mine / theirs)", "won", "lost", "drew", "net per deal"
    );

    let mut overall = (0usize, 0usize, 0usize, 0.0f64);
    let mut all_paid: Vec<f64> = Vec::new();
    // Deals, won, lost, and the sum of what the losses cost, by the biggest
    // bonus either half of the pair held: where the loss tail lives.
    let mut by_bonus = [(0usize, 0usize, 0usize, 0i64); 3];

    // The mirror has to cancel TWO advantages, not one. Swapping seats alone
    // leaves the standing in place, and from 88 against 120 you lose heavily
    // however well you play -- a first version of this measured exactly that
    // and produced a beautifully antisymmetric table saying nothing about
    // either agent.
    //
    // So both halves use the SAME standing and the same cards, and only the
    // agent in elder's chair changes. `settlement_of` is antisymmetric, so
    // the younger side's result is the negation of the elder side's, and the
    // whole comparison reduces to the difference between the two halves.

    for (index, (mine, theirs, label)) in STANDINGS.into_iter().enumerate() {
        let mut rng = Rng::seeded(4242);
        let (mut won, mut lost, mut drew) = (0usize, 0usize, 0usize);
        let mut net = 0i64;
        let mut paid_each: Vec<f64> = Vec::with_capacity(deals);

        for deal_index in 0..deals {
            let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
            rng.shuffle(&mut pack);
            let standing = Standing {
                mine,
                theirs,
                deals_left: 1,
                number: 6,
            };

            // Both sides' totals and the settlement to elder, and the biggest
            // bonus the deal held: 2 a repique, 1 a pique, 0 neither.
            let play_half = |a: &mut dyn Agent, b: &mut dyn Agent| -> (Half, usize) {
                let (deal, _) = play_deal(deal_from(&pack).unwrap(), a, b, Some(standing)).unwrap();
                let bonus = if deal.log.repique().is_some() {
                    2
                } else {
                    usize::from(deal.log.pique().is_some())
                };
                let elder = mine + deal.log.total(Player::Elder);
                let younger = theirs + deal.log.total(Player::Younger);
                let settlement = settlement_of(elder, younger);
                (
                    Half {
                        elder,
                        younger,
                        settlement,
                    },
                    bonus,
                )
            };

            let [mut settling, mut flat] = seats(worlds, true, prior);
            let (half_a, bonus_a) = play_half(&mut settling, &mut flat);

            let [mut flat_elder, mut settling_younger] = seats(worlds, false, prior);
            let (half_b, bonus_b) = play_half(&mut flat_elder, &mut settling_younger);

            // Ahead as elder by this much; and by the same again as younger,
            // since the other side's settlement is the negation.
            let paid = 2 * (i64::from(half_a.settlement) - i64::from(half_b.settlement));
            if let Some(file) = out.as_mut() {
                let record = Record {
                    standing: index,
                    deal: deal_index,
                    bonus: bonus_a.max(bonus_b),
                    pack: pack.iter().map(|c| c.code()).collect(),
                    a: half_a,
                    b: half_b,
                    paid,
                };
                writeln!(file, "{}", record.line()).expect("the record is writable");
            }
            let class = &mut by_bonus[bonus_a.max(bonus_b)];
            class.0 += 1;
            match paid.cmp(&0) {
                std::cmp::Ordering::Greater => class.1 += 1,
                std::cmp::Ordering::Less => {
                    class.2 += 1;
                    class.3 += paid;
                }
                std::cmp::Ordering::Equal => {}
            }
            net += paid;
            paid_each.push(paid as f64);
            match paid.cmp(&0) {
                std::cmp::Ordering::Greater => won += 1,
                std::cmp::Ordering::Less => lost += 1,
                std::cmp::Ordering::Equal => drew += 1,
            }
        }

        // The settlement swings hard near the rubicon -- a mistake there
        // costs the sum rather than the difference -- so the mean alone says
        // very little without its error.
        let per = net as f64 / deals as f64;
        let variance = paid_each.iter().map(|p| (p - per) * (p - per)).sum::<f64>()
            / (deals.max(2) - 1) as f64;
        let error = (variance / deals as f64).sqrt();
        all_paid.extend(paid_each);
        println!("  {label:<34} {won:>5} {lost:>5} {drew:>5}  {per:>+8.1} ± {error:<5.1}");
        overall.0 += won;
        overall.1 += lost;
        overall.2 += drew;
        overall.3 += per;
    }

    println!(
        "\n  overall: {} won, {} lost, {} drawn over {} deals",
        overall.0,
        overall.1,
        overall.2,
        deals * STANDINGS.len()
    );
    let n = all_paid.len() as f64;
    let mean = all_paid.iter().sum::<f64>() / n;
    let variance = all_paid
        .iter()
        .map(|p| (p - mean) * (p - mean))
        .sum::<f64>()
        / (n - 1.0);
    let error = (variance / n).sqrt();
    println!(
        "  net settlement per deal: {mean:+.2} ± {error:.2}  ({:.1} sigma)",
        (mean / error).abs()
    );
    println!("\n  by the biggest bonus either half of a pair held:");
    println!(
        "  {:<10} {:>6} {:>5} {:>5}  {:>14}",
        "deals", "count", "won", "lost", "sum of losses"
    );
    for (name, (count, won, lost, losses)) in ["no bonus", "pique", "repique"].iter().zip(by_bonus)
    {
        println!("  {name:<10} {count:>6} {won:>5} {lost:>5}  {losses:>+14}");
    }
    println!("\n  the linear-weight attempt managed 0 won, 9 lost, 66 drawn over 75.");
    if let Some(mut file) = out {
        file.flush().expect("the record is writable");
    }
}

/// Pair two runs' records and say how far apart they really are.
fn compare(first_path: &str, second_path: &str) -> Result<(), String> {
    let first = read_records(first_path)?;
    let second = read_records(second_path)?;
    let paired = pair(&first, &second)?;

    println!("  {first_path}  against  {second_path}");
    println!("  (positive means the first run's settling search did better)\n");
    println!(
        "  {} pairs; the play differs in {}, the settlement in {}",
        paired.pairs,
        paired.differ,
        paired.better + paired.worse
    );
    println!(
        "  first better in {}, second better in {}",
        paired.better, paired.worse
    );
    let sigma = if paired.error > 0.0 {
        paired.mean.abs() / paired.error
    } else {
        0.0
    };
    println!(
        "  difference per deal: {:+.2} ± {:.2}  ({sigma:.1} sigma)",
        paired.mean, paired.error
    );

    // Where the difference comes from: the biggest swings, either way.
    let by_key: std::collections::HashMap<(usize, usize), &Record> =
        second.iter().map(|r| ((r.standing, r.deal), r)).collect();
    let mut swings: Vec<(&Record, &Record)> = first
        .iter()
        .map(|r| (r, by_key[&(r.standing, r.deal)]))
        .filter(|(one, other)| one.paid != other.paid)
        .collect();
    swings.sort_by_key(|(one, other)| -(one.paid - other.paid).abs());
    if !swings.is_empty() {
        println!("\n  the largest swings (standing, deal: first, second):");
        for (one, other) in swings.iter().take(12) {
            println!(
                "  {:>2} {:>4}   {:>+6} {:>+6}   {:>+6}   {}",
                one.standing,
                one.deal,
                one.paid,
                other.paid,
                one.paid - other.paid,
                STANDINGS[one.standing].2
            );
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// One line per mirrored pair, so two runs can be compared deal by deal.
//
// Every row of PLAN.md TODO 1's table shares the same 720 deals, and so the
// same card luck; the ± on each row carries that luck, which overstates the
// noise *between* rows. Pairing on identical deals takes it out: a variant
// that changes no decision in a deal changes nothing there, and only the
// deals it does touch contribute to the error.
// ---------------------------------------------------------------------------

/// One half of a mirrored pair: both sides' partie totals after the deal,
/// and the settlement to the side that sat elder.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Half {
    elder: i32,
    younger: i32,
    settlement: i32,
}

/// A mirrored pair as it is written to disk. Half `a` has the settling
/// search in elder's chair, half `b` the flat one.
#[derive(Clone, Debug, PartialEq, Eq)]
struct Record {
    standing: usize,
    deal: usize,
    /// 2 a repique, 1 a pique, 0 neither: the biggest either half held.
    bonus: usize,
    /// The pack in full, so a deal can be replayed from its line alone.
    pack: String,
    a: Half,
    b: Half,
    /// What settling gained over the pair, in settlement points.
    paid: i64,
}

/// Two runs over the same deals, compared pair by pair.
#[derive(Debug, PartialEq)]
struct Paired {
    pairs: usize,
    /// Pairs whose outcome differs between the runs at all.
    differ: usize,
    /// Pairs where the first run's settling search did better, and worse.
    better: usize,
    worse: usize,
    /// The mean of (first − second) per pair, and its standard error.
    mean: f64,
    error: f64,
}

/// The two agents of a half, elder first. Seeds belong to the chair, so both
/// halves draw identical worlds until the objectives first disagree.
fn seats(worlds: usize, settling_elder: bool, prior: bool) -> [SolverAgent; 2] {
    let weigh = |agent: SolverAgent| {
        if prior {
            agent.with_prior(RUNG4)
        } else {
            agent
        }
    };
    let elder = weigh(SolverAgent::new(3).worlds(worlds));
    let younger = weigh(SolverAgent::new(5).worlds(worlds));
    if settling_elder {
        [elder.settling(), younger]
    } else {
        [elder, younger.settling()]
    }
}

/// A solver that keeps, for every play, the view it played from, what an
/// identical copy of it estimated there, and the card it played.
struct Traced {
    agent: SolverAgent,
    steps: Vec<(View, Option<Estimates>, Card)>,
}

impl Agent for Traced {
    fn name(&self) -> &str {
        self.agent.name()
    }

    fn exchange(&mut self, view: &View) -> Hand {
        self.agent.exchange(view)
    }

    fn declare(&mut self, view: &View, category: Category) -> Declaration {
        self.agent.declare(view, category)
    }

    fn play(&mut self, view: &View) -> Card {
        let believed = self.agent.clone().estimates(view);
        let played = self.agent.play(view);
        self.steps.push((view.clone(), believed, played));
        played
    }
}

/// Replay one recorded pair and set, beside every card the settling search
/// chose from, what it believed each card was worth against what it was
/// worth with both hands on the table.
fn show(path: &str, standing_index: usize, deal_index: usize) -> Result<(), String> {
    let text = std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?;
    let header = Header::read(text.lines().next().unwrap_or(""))?;
    let worlds = header.worlds;
    let record = read_records(path)?
        .into_iter()
        .find(|r| r.standing == standing_index && r.deal == deal_index)
        .ok_or(format!(
            "no standing {standing_index} deal {deal_index} in {path}"
        ))?;
    let pack: Vec<Card> = record
        .pack
        .as_bytes()
        .chunks(2)
        .map(|code| Card::parse(std::str::from_utf8(code).unwrap_or("?")))
        .collect::<Result<_, _>>()?;
    let (mine, theirs, label) = STANDINGS[standing_index];
    let standing = Standing {
        mine,
        theirs,
        deals_left: 1,
        number: 6,
    };

    println!("  standing {standing_index}, {label}: elder's side on {mine}, younger's on {theirs}");
    println!(
        "  deal {deal_index}, {worlds} worlds; paid {:+} to settling\n",
        record.paid
    );

    for (name, settling_elder, recorded) in [("A", true, record.a), ("B", false, record.b)] {
        let [elder_agent, younger_agent] = seats(worlds, settling_elder, header.prior);
        let mut elder = Traced {
            agent: elder_agent,
            steps: Vec::new(),
        };
        let mut younger = Traced {
            agent: younger_agent,
            steps: Vec::new(),
        };
        let (deal, _) = play_deal(deal_from(&pack)?, &mut elder, &mut younger, Some(standing))?;
        let totals = (
            mine + deal.log.total(Player::Elder),
            theirs + deal.log.total(Player::Younger),
        );
        if totals != (recorded.elder, recorded.younger) {
            return Err(format!(
                "half {name} replays to {totals:?}, but the record says {:?}",
                (recorded.elder, recorded.younger)
            ));
        }

        let who = if settling_elder { "elder" } else { "younger" };
        println!(
            "  half {name}: settling sits {who}; finishes {} / {}, settlement to elder {:+}",
            totals.0, totals.1, recorded.settlement
        );
        let tricks: Vec<String> = deal
            .tricks
            .iter()
            .map(|t| {
                let won = if t.winner() == Ok(Player::Elder) {
                    "E"
                } else {
                    "Y"
                };
                let lead = if t.leader == Player::Elder { "E" } else { "Y" };
                format!(
                    "{lead}{}{}{won}",
                    t.led.code(),
                    t.followed.map_or("--".into(), |c| c.code())
                )
            })
            .collect();
        println!("    tricks  {}", tricks.join(" "));

        // Each seat's twelve cards, read back off the finished tricks.
        let twelve = |seat: Player| -> u32 {
            deal.tricks.iter().fold(0u32, |bits, t| {
                let card = if t.leader == seat {
                    t.led
                } else {
                    t.followed.expect("a finished deal's tricks are complete")
                };
                bits | 1 << card.0
            })
        };

        let settler = if settling_elder { &elder } else { &younger };
        for (view, believed, played) in &settler.steps {
            let Some(believed) = believed else { continue };
            let mut theirs_now = twelve(view.opponent());
            for t in view.tricks.iter().chain(view.current_trick.iter()) {
                for card in [Some(t.led), t.followed].into_iter().flatten() {
                    theirs_now &= !(1 << card.0);
                }
            }
            let truth = settler.agent.values_in(view, Hand(theirs_now))?;
            let banked = settled_log(view);
            let (my_side, their_side) = (
                view.partie.map_or(0, |p| p.mine),
                view.partie.map_or(0, |p| p.theirs),
            );
            let me = view.me;
            println!(
                "    trick {:>2}, {} to {}: banked {} / {}, over {} worlds",
                view.tricks.len() + 1,
                if me == Player::Elder {
                    "elder"
                } else {
                    "younger"
                },
                if view.current_trick.is_some() {
                    "follow"
                } else {
                    "lead"
                },
                my_side + banked.total(me),
                their_side + banked.total(me.opponent()),
                believed.worlds
            );
            let best_true = truth
                .iter()
                .map(|(_, v)| *v)
                .fold(f64::NEG_INFINITY, f64::max);
            for (card, total) in &believed.totals {
                let true_value = truth
                    .iter()
                    .find(|(c, _)| c == card)
                    .map_or(f64::NAN, |x| x.1);
                let mark = match (card == played, true_value < best_true) {
                    (true, true) => "  played, and worse than the best in truth",
                    (true, false) => "  played",
                    (false, _) if true_value == best_true => "  best in truth",
                    _ => "",
                };
                println!(
                    "      {}  believed {:>+8.1}   true {:>+6.0}{mark}",
                    card.code(),
                    total / believed.worlds as f64,
                    true_value
                );
            }
        }
        println!();
    }
    Ok(())
}

/// How a run was made, as the first line of its record: enough for `--show`
/// to seat exactly the same agents again.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Header {
    deals: usize,
    worlds: usize,
    /// Both agents weigh the opponent's hands by the fitted prior.
    prior: bool,
}

impl Header {
    fn line(self) -> String {
        let prior = if self.prior { " prior" } else { "" };
        format!("# settle {} {}{prior}", self.deals, self.worlds)
    }

    fn read(line: &str) -> Result<Header, String> {
        let rest = line
            .strip_prefix("# settle ")
            .ok_or("the file has no '# settle DEALS WORLDS' header")?;
        let words: Vec<&str> = rest.split_whitespace().collect();
        let number = |i: usize| -> Result<usize, String> {
            words
                .get(i)
                .and_then(|w| w.parse().ok())
                .ok_or(format!("a malformed header: {line:?}"))
        };
        Ok(Header {
            deals: number(0)?,
            worlds: number(1)?,
            prior: words.get(2) == Some(&"prior"),
        })
    }
}

const HEADER: &str = "# standing\tdeal\tbonus\tpack\t\
a_elder\ta_younger\ta_settlement\tb_elder\tb_younger\tb_settlement\tpaid";

impl Record {
    fn line(&self) -> String {
        let (a, b) = (self.a, self.b);
        format!(
            "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
            self.standing,
            self.deal,
            self.bonus,
            self.pack,
            a.elder,
            a.younger,
            a.settlement,
            b.elder,
            b.younger,
            b.settlement,
            self.paid
        )
    }

    fn read(line: &str) -> Result<Record, String> {
        let fields: Vec<&str> = line.split('\t').collect();
        if fields.len() != 11 {
            return Err(format!(
                "expected 11 fields, found {}: {line:?}",
                fields.len()
            ));
        }
        fn number<T: std::str::FromStr>(text: &str) -> Result<T, String> {
            text.parse().map_err(|_| format!("not a number: {text:?}"))
        }
        let half = |at: usize| -> Result<Half, String> {
            Ok(Half {
                elder: number(fields[at])?,
                younger: number(fields[at + 1])?,
                settlement: number(fields[at + 2])?,
            })
        };
        Ok(Record {
            standing: number(fields[0])?,
            deal: number(fields[1])?,
            bonus: number(fields[2])?,
            pack: fields[3].to_string(),
            a: half(4)?,
            b: half(7)?,
            paid: number(fields[10])?,
        })
    }
}

/// Every record in a file written by `--out`, comments skipped.
fn read_records(path: &str) -> Result<Vec<Record>, String> {
    std::fs::read_to_string(path)
        .map_err(|e| format!("{path}: {e}"))?
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .map(Record::read)
        .collect()
}

/// Compare two runs pair by pair. They must cover exactly the same deals --
/// the same standings, indices *and* cards -- or the comparison means nothing.
fn pair(first: &[Record], second: &[Record]) -> Result<Paired, String> {
    if first.len() != second.len() {
        return Err(format!(
            "the runs cover {} and {} pairs",
            first.len(),
            second.len()
        ));
    }
    let by_key: std::collections::HashMap<(usize, usize), &Record> =
        second.iter().map(|r| ((r.standing, r.deal), r)).collect();

    let mut differences = Vec::with_capacity(first.len());
    let (mut differ, mut better, mut worse) = (0, 0, 0);
    for one in first {
        let other = by_key.get(&(one.standing, one.deal)).ok_or_else(|| {
            format!(
                "standing {} deal {} is in one run only",
                one.standing, one.deal
            )
        })?;
        if one.pack != other.pack {
            return Err(format!(
                "standing {} deal {} was dealt different cards in the two runs",
                one.standing, one.deal
            ));
        }
        if one.a != other.a || one.b != other.b {
            differ += 1;
        }
        let difference = one.paid - other.paid;
        match difference.cmp(&0) {
            std::cmp::Ordering::Greater => better += 1,
            std::cmp::Ordering::Less => worse += 1,
            std::cmp::Ordering::Equal => {}
        }
        differences.push(difference as f64);
    }

    let (mean, error) = mean_and_error(&differences);
    Ok(Paired {
        pairs: first.len(),
        differ,
        better,
        worse,
        mean,
        error,
    })
}

/// The mean and its standard error, from the sample variance.
fn mean_and_error(values: &[f64]) -> (f64, f64) {
    let n = values.len() as f64;
    if values.is_empty() {
        return (0.0, 0.0);
    }
    let mean = values.iter().sum::<f64>() / n;
    if values.len() < 2 {
        return (mean, 0.0);
    }
    let variance = values.iter().map(|v| (v - mean) * (v - mean)).sum::<f64>() / (n - 1.0);
    (mean, (variance / n).sqrt())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn record(standing: usize, deal: usize, paid: i64) -> Record {
        Record {
            standing,
            deal,
            bonus: 1,
            pack: "7S8S9STSJSQSKSAS7H8H9HTHJHQHKHAH7C8C9CTCJCQCKCAC7D8D9DTDJDQDKDAD".into(),
            a: Half {
                elder: 131,
                younger: 88,
                settlement: 319,
            },
            b: Half {
                elder: 98,
                younger: 101,
                settlement: -299,
            },
            paid,
        }
    }

    #[test]
    fn a_record_reads_back_as_written() {
        let original = record(3, 117, 1236);
        let line = original.line();
        assert!(!line.contains('\n'));
        assert_eq!(Record::read(&line), Ok(original));
    }

    #[test]
    fn a_header_says_how_the_run_was_made() {
        assert_eq!(
            Header::read("# settle 120 30"),
            Ok(Header {
                deals: 120,
                worlds: 30,
                prior: false
            })
        );
        let with = Header {
            deals: 12,
            worlds: 90,
            prior: true,
        };
        assert_eq!(Header::read(&with.line()), Ok(with));
        assert!(Header::read("# standing\tdeal").is_err());
    }

    #[test]
    fn a_malformed_line_is_an_error_not_a_panic() {
        assert!(Record::read("").is_err());
        assert!(Record::read("1\t2\tthree").is_err());
    }

    #[test]
    fn identical_runs_differ_by_exactly_nothing() {
        let run = vec![record(0, 0, 20), record(0, 1, -480), record(1, 0, 0)];
        let paired = pair(&run, &run).unwrap();
        assert_eq!(
            paired,
            Paired {
                pairs: 3,
                differ: 0,
                better: 0,
                worse: 0,
                mean: 0.0,
                error: 0.0,
            }
        );
    }

    #[test]
    fn only_the_deals_a_variant_touches_carry_error() {
        // Four pairs; the variant changes two of them. The large, shared
        // -480 is card luck common to both runs and must cancel exactly.
        let first = vec![
            record(0, 0, 20),
            record(0, 1, -480),
            record(1, 0, 10),
            record(1, 1, 0),
        ];
        let mut second = first.clone();
        // `paid` is twice the gap between the halves' settlements, so a
        // variant that moves it moves a half too.
        second[0].paid = 16; // first run better by 4
        second[0].a.settlement -= 2;
        second[2].paid = 30; // first run worse by 20
        second[2].a.settlement += 10;
        let paired = pair(&first, &second).unwrap();
        assert_eq!(paired.pairs, 4);
        assert_eq!(paired.differ, 2);
        assert_eq!((paired.better, paired.worse), (1, 1));
        // Differences 4, 0, -20, 0: mean -4; deviations 8, 4, -16, 4, so
        // sample variance 352 / 3 and error sqrt(352 / 3 / 4) = sqrt(88 / 3).
        assert!((paired.mean - -4.0).abs() < 1e-12);
        assert!((paired.error - (88.0f64 / 3.0).sqrt()).abs() < 1e-12);
    }

    #[test]
    fn a_pair_that_differs_only_in_its_totals_still_counts_as_differing() {
        // Settlement can come out equal while the play did not: record it.
        let first = vec![record(0, 0, 20)];
        let mut second = first.clone();
        second[0].a.elder += 2;
        second[0].a.younger += 2;
        let paired = pair(&first, &second).unwrap();
        assert_eq!(paired.differ, 1);
        assert_eq!((paired.better, paired.worse), (0, 0));
    }

    #[test]
    fn runs_over_different_deals_refuse_to_pair() {
        let first = vec![record(0, 0, 20), record(0, 1, 0)];

        let mut other_cards = first.clone();
        other_cards[1].pack = other_cards[1].pack.chars().rev().collect();
        assert!(pair(&first, &other_cards).is_err());

        let shorter = vec![first[0].clone()];
        assert!(pair(&first, &shorter).is_err());

        let mut reordered = first.clone();
        reordered.swap(0, 1);
        assert!(
            pair(&first, &reordered).is_ok(),
            "matched by key, not by line"
        );
    }
}
