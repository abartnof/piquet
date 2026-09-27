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
use piquet_core::cards::Card;
use piquet_core::chances::settlement_of;
use piquet_core::partie::Standing;
use piquet_core::play::play_deal;
use piquet_core::rng::Rng;
use piquet_core::rules::deal_from;
use piquet_core::scoring::Player;
use piquet_core::solver::SolverAgent;

/// Standings chosen for where the two objectives come apart.
const STANDINGS: [(i32, i32, &str); 6] = [
    (82, 70, "both short, me closer"),
    (70, 82, "both short, them closer"),
    (95, 88, "both a whisker short"),
    (88, 95, "both a whisker short, mirrored"),
    (120, 88, "I am safe, they are not"),
    (88, 120, "they are safe, I am not"),
];

fn main() {
    let deals: usize = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(75);
    // Opponent worlds each solver samples per decision. Both agents get the
    // same number, so only the objective differs: the question it serves is
    // whether settling -- which is non-linear where the flat objective is
    // nearly linear -- needs a thicker sample than thirty (PLAN.md TODO 1).
    let worlds: usize = std::env::args()
        .nth(2)
        .and_then(|a| a.parse().ok())
        .unwrap_or(30);

    println!(
        "  mirrored LAST deals, scored in settlement\n\
         \x20 settling-at-the-leaf against the flat deal objective\n\
         \x20 (positive means settling is ahead)\n"
    );
    println!("  {worlds} opponent worlds a decision, for both agents\n");
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

    for (mine, theirs, label) in STANDINGS {
        let mut rng = Rng::seeded(4242);
        let (mut won, mut lost, mut drew) = (0usize, 0usize, 0usize);
        let mut net = 0i64;
        let mut paid_each: Vec<f64> = Vec::with_capacity(deals);

        for _ in 0..deals {
            let mut pack: Vec<Card> = (0u8..32).map(Card).collect();
            rng.shuffle(&mut pack);
            let standing = Standing {
                mine,
                theirs,
                deals_left: 1,
                number: 6,
            };

            // The settlement to elder, and the biggest bonus the deal held:
            // 2 a repique, 1 a pique, 0 neither.
            let elder_settlement = |a: &mut dyn Agent, b: &mut dyn Agent| -> (i32, usize) {
                let (deal, _) = play_deal(deal_from(&pack).unwrap(), a, b, Some(standing)).unwrap();
                let bonus = if deal.log.repique().is_some() {
                    2
                } else {
                    usize::from(deal.log.pique().is_some())
                };
                let settlement = settlement_of(
                    mine + deal.log.total(Player::Elder),
                    theirs + deal.log.total(Player::Younger),
                );
                (settlement, bonus)
            };

            let mut settling = SolverAgent::new(3).worlds(worlds).settling();
            let mut flat = SolverAgent::new(5).worlds(worlds);
            let (with_settling, bonus_a) = elder_settlement(&mut settling, &mut flat);

            let mut flat_elder = SolverAgent::new(3).worlds(worlds);
            let mut settling_younger = SolverAgent::new(5).worlds(worlds).settling();
            let (with_flat, bonus_b) = elder_settlement(&mut flat_elder, &mut settling_younger);

            // Ahead as elder by this much; and by the same again as younger,
            // since the other side's settlement is the negation.
            let paid = 2 * (i64::from(with_settling) - i64::from(with_flat));
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
}
