# Piquet — Living Plan

> Insurance against lost context. `docs/DESIGN.md` holds the *reasoning*,
> `docs/PIQUET.md` the *game*, `docs/LITERATURE.md` the *sources*; this file
> holds *where we are and what is left*. Last updated when development moved
> to Google Cloud and the language was settled on Rust.

## Where we are

**Milestones 1–7 complete, and the Rust port with them. 520 Python tests, 56
Rust.**

**It is playable in Rust.** `cargo run -p piquet-cli -- --level 3` sits you
down against a named opponent for a partie of six deals, settled by the
rubicon. Four measured rungs plus the exact-endgame solver, with styles and
erraticism, and a mirrored-pair tournament that rates them.

```
crates/piquet-core/src/
  cards.rs         32-card pack; Hand as a u32
  combos.rs        point / sequence / set detection, scoring, comparison
  declarations.rs  the meld layer: announcing, showing, sinking
  rules.rs         Deal as an immutable state machine
  scoring.rs       the event log; pique and repique
  partie.rs        six deals, Side vs seat, the rubicon settlement
  chances.rs       the odds on reaching a total; what a point is worth
  observation.rs   View — the only way an agent sees a deal
  agents.rs        the Agent trait; RandomAgent
  heuristics.rs    the capability ladder, rungs 1–4
  style.rs         the third axis, calibrated by measurement
  inference.rs     which hands the opponent can possibly hold
  solver.rs        exact endgame search, and the agent that uses it
  play.rs          running deals and parties; the move log
  tournament.rs    mirrored-pair duels, Bradley-Terry ratings
  mt19937.rs       CPython's generator, for the one fixed-seed model constant
  rng.rs           the agents' own generator
crates/piquet-cli/src/
  main.rs          the table a person sits at; the human as an Agent
  render.rs        drawing a hand in the language the prompt accepts
python/            the oracle: the original, which generates the vectors
vectors/           golden JSON, read by both languages
```

**The parity gate is met.** Both halves of it:

- Every golden vector reproduces in Rust — nine modules, from the pack through
  the solver, including three complete deals replayed transition by
  transition and all eighty rung-against-rung games.
- The measured ladder reproduces. 500 mirrored pairs per pairing, anchored on
  random play: Python **L1 335, L2 776, L3 816, L4 863**; Rust **343, 774,
  811, 858**. Ordering identical, within eight points on every rung — which is
  all that can be asked, since the two draw deals from different generators.

Speed, measured (`docs/DESIGN.md` §13.7): the exact solver is **20–54×**
faster depending on depth, and the ladder tournament **11×** — 54.0 s to 4.9 s.
The interactive frontier moves from eight tricks to about ten, not to twelve;
reaching twelve is an algorithmic problem now, not a language one.

The AI *can* be told what a point is worth in a partie. Told, it plays slightly
worse, so `partie_aware` is off by default in the Python and is not ported at
all — see TODO 1.

Over 60 parties of rung-4 play a side averages **145** across six deals, and
**17 of 120** sides finish short of the rubicon. The threshold is a live
threat, not a curiosity.

## Where the work happens

**All development is on Google Cloud.** Nothing is built, tested or measured on
a laptop, and there is no Rust toolchain on one.

| | |
|---|---|
| Project / zone | `abartnof-piquet`, `us-west1-b` |
| Instance | `piquet-dev`, e2-standard-2 (2 vCPU, 8 GB), Debian 12 |
| Disk | 50 GB, `autoDelete: False` — it survives the instance being deleted |
| Toolchain | Rust 1.98.1 with clippy, rustfmt, rust-analyzer; Python 3.11.2, pytest 9.1.1 |

**Development now happens *on* the VM, not through it.** `~/piquet` there is a
real git clone tracking `origin/main`, with Claude Code installed, so the two
checkouts are joined by GitHub rather than by rsync. `docs/VM.md` is the whole
story: starting it, getting in, and the one foot-gun the change introduces.

`bin/vm` remains useful for `--up`, `--down` and `--status`. Its other modes
rsync the laptop's tree over the VM's with `--delete` and will destroy
unpushed work there; do not use them while working on the VM.

Historically, `bin/vm` was the whole interface. It syncs the working tree and runs the command
there, starting the instance if it is stopped and refreshing the SSH alias,
whose address changes on every stop-start cycle.

    bin/vm cargo test
    bin/vm .venv/bin/pytest -q
    bin/vm --down          # stop it; this is what keeps the bill small

**Measured on arrival**, and worth knowing before it surprises someone: the
full suite takes **188 s** on the VM against ~94 s on the laptop, and the fast
loop **42 s** against ~16 s. The VM is 2× slower per core. That is the honest
cost of the move until Rust lands. It is bounded — the runs that actually hurt
are parallel and the VM has four cores to the laptop's advantage in one, and
the machine resizes in about a minute.

### What it costs, and the safeguard on it

The account runs on Google's **$300 new-customer credit, valid for 90 days**
from September 2026. The trial does *not* auto-charge when the credit is
exhausted — it suspends and asks for an explicit upgrade — so the real risks
are not a surprise bill. They are the credit expiring on the **calendar**
rather than on spend, and an instance left running over a weekend.

| | |
|---|---|
| Instance, while running | ≈$0.067/hour (halved from $0.13 when the heavy measurement runs finished) |
| Disk, always | ≈$5/month, whether or not the instance is up |
| At ~15 hrs/week | ≈$9/month — the credit should outlast the 90 days comfortably |

Two things guard it, deliberately of different kinds. A **budget on the billing
account** (`Piquet — free trial credit`, $300) emails at 25 / 50 / 75 / 90 /
100 % of spend and fires whether or not anyone is paying attention. And the
spend is **checked at the start of each working session**, which Andrew asked
for explicitly as an early warning rather than a backstop.

Anything materially above the figures above means something is running that
should not be, and it is almost always an instance nobody stopped:

    bin/vm --status        # is it up, and what is it costing
    bin/vm --down          # stop it

## Next action

**Where we left off.** The Rust port is complete and both halves of the parity
gate are met. The current line of work is the partie objective (TODO 1): the
search now settles at the leaf, it costs only 1.6×, and over 720 mirrored last
deals it wins 249 to 46 — but the net settlement is 1.3 sigma from zero. It
wins often by little and loses rarely by a lot.

**Pick up here.** Two hypotheses for the loss tail, neither measured, in the
order worth trying:

1. **Teach the search pique and repique.** It ignores them, and a missed
   repique is sixty points — the size of the losses swamping the wins.
   `pique_is_live` (TODO 9) is the unused helper that exists for exactly this,
   so two owed things close together.
2. **Raise `max_worlds` above thirty** and see whether the tail shrinks. Cheap
   to try; the flat objective forgives a thin sample and this one may not.

Judge either on `bin/settle` (mirrored last deals, stacked) and on
`bin/parties` (whole mirrored parties), never on deal points.

Then, in rough order of value:

3. **Milestone 9, the training mode.** The largest unmet *product* requirement
   and it needs no compute. Ladder-based: rank a move by *which rung would
   play it*, so the explanation names a skill the player can go and learn.
   Every rung is already a working agent, so it is nearly free. `explain.rs`
   is owed.

4. **The browser build.** `piquet-wasm`, and the 5 MB single-page target the
   language choice was made for. Low risk — the engine has no dependencies and
   nothing needs threads at the eight-trick cap.

5. **Milestone 8, the exchange policy.** The only item that would spend money,
   and the price fell by an order of magnitude with the port. Run the
   heuristic tier first: it is free now, and answers whether there is any
   signal at all.

6. **`piquet-py`** (PyO3), so the thirty-line experiments this project runs on
   stay thirty lines with the Rust engine underneath.

7. **Milestone 10, CFR declarations.** Still the largest unknown.

## Settled decisions

| Decision | Choice |
|---|---|
| Rule authority | **pagat.com** wins all conflicts; variants behind flags |
| Game implemented | Rubicon Piquet, 32 cards, 6-deal partie |
| Language | **Rust**, decided September 2026 — `docs/DESIGN.md` §13.5 ranked it first on three of the four goals, §2.2 audits what the port hits. Python stays as the oracle until parity |
| Where it runs | **Google Cloud only.** No toolchain on a laptop; `bin/vm` is the interface |
| Transport | `github.com/abartnof/piquet`, private. The 2017 attempt survives as `piquet-2017` |
| Scoring model | Ordered **event log**, not a running total |
| Bonus reckoning | Law 67's **order of precedence**, for pique and repique alike |
| Seats vs people | `Player` is a seat and swaps each deal; `Side` plays the partie |
| Evaluation model | **Decomposed vector**, never a scalar |
| AI objective | Still **points in a deal**. `chances.point_weights` prices a point in settlement and the search accepts the pair, but weighting by it measured *worse* and is off by default — see below |
| Measuring it | **Mirrored parties** (`tournament.partie_duel`), scored in settlement. A deal-level harness is structurally blind to a partie objective |
| Play-phase AI | Exact enumeration + solver. No training needed |
| Exchange AI | Monte Carlo rollouts, then a fitted regression |
| Declaration AI | CFR. Built last |
| Skill model | **Capability ladder**, not a noise dial. 4 rungs built; **2 proposed rungs deleted for failing measurement** |
| Opponent style | Third axis, orthogonal to skill and erraticism. EV-neutral by calibration, stable for a whole partie |
| Measurement | **Always mirrored pairs** (`tournament.duel`). Never independently shuffled deals |
| UI | Terminal first |
| LLM involvement | None in gameplay; optional for phrasing tutor explanations |

## Milestones

- [x] 1. `cards` + `combos`
- [x] 2. `rules` + `scoring` — phase machine, event log, pique/repique
- [x] 3. Random agent, statistical invariants, move log from the first deal
- [x] 4. Heuristic ladder, styles, Elo harness with mirrored pairs
- [x] 5. **Exact endgame solver** + inference; rung 5 (82.5%, +5.0 pts over L4)
- [x] 6. **The partie** — six deals, alternating deal, rubicon settlement
- [x] 7. **Terminal UI**; skill and erratic controls; a playable game
- [ ] 8. Exchange policy — *runtime and cost agreed with Andrew first*
- [ ] 9. Training mode
- [ ] 10. CFR declarations

## The three open questions, settled

All three were measured rather than argued, and one of them went against the
claim that raised it.

### 1. The solver's world prior — real, and small

`possible_hands` treats every consistent hand as equally likely, and it is not:
the cards *not* in her hand are her discards and the talon leftovers, and both
are systematically low. Measured at the point the solver actually runs — eight
cards, not the first lead, which is where the first measurement was wrongly
taken — an unaccounted-for ace is hers 100% of the time against a model that
believes 89%, and a seven 23% against a model that believes 46%.

**But the fix is worth +0.3 points per mirrored pair.** A scratch solver that
weights its worlds by the measured rates, same number of searches per decision,
beat the stock one 39–13 in decisive pairs over 150 — statistically solid at
p = 4×10⁻⁴, and about a sixth of a rung of the ladder. For scale: rung 3 to
rung 4 is +1.8 and the solver over rung 4 is +5.0.

So it is a real effect and a small one, and the claim it was written up under —
"the largest measured weakness in the AI" — was wrong. Not landed, because the
weights are fitted to rung-4 discard habits and would be a guess against a
human. The principled version is milestone 8's exchange policy read backwards.

### 2. `ratings()` around a shutout — fixed

Now Laplace's rule of succession, 1774: half a win and half a loss against a
virtual opponent of average strength. The floor read ~3,700 for a shut-out
anchor and ~713 after one win; the scale is now continuous, and on a
well-populated table the prior moves ratings by about three points.

### 3. `ratings()` and the margin — a preference, not a finding

Bradley-Terry models win probability; using margins means a different model.
Listed here originally as though it were a defect, which it is not. Left alone.

## The exchange is not the seam it looked like

The crippling experiment (`docs/DESIGN.md` §6.4b) puts the discard at −32.6
points per pair, the highest-stakes decision in a deal, governed by six
coefficients chosen by taste. A rollout probe — twelve candidates, twenty
worlds each — beats it by +0.3 points per pair over 250 mirrored pairs, which
at 53 decisive pairs is nothing.

Sweeping the rollout count explains why: agreement with the hand-tuned discard
rises 62% → 79% → 84% as rollouts go 5 → 20 → 80, while the gain the agent
*believes* it is making falls 7.72 → 6.15 → 4.15. It is the optimizer's curse —
the bias from maximising over noisy estimates — and it is most of what a naive
Monte Carlo discard policy would be chasing.

Which validates §6.2's architecture and kills the shortcut: **selecting an
argmax over rollouts amplifies noise; fitting a regression pools across
thousands of deals and averages it out.** Worth knowing before buying compute.

## What the port left behind

Found by auditing the Rust against the Python's public API and the two test
suites against the vectors. Recorded rather than fixed, because each is a
deliberate call rather than an oversight — but they are all real, and a reader
should not have to rediscover them.

- **`tournament.partie_duel` and `PartieResult` are not ported.** This is the
  most significant of them. `PLAN.md` already says a deal-level harness is
  *structurally blind* to a partie objective, so mirrored **parties** are the
  correct instrument for anything about the rubicon. The Rust has mirrored
  deals only. Anything that measures a partie-aware agent needs this first.
- **`round_robin` and `format_table` are not ported.** The round-robin loop is
  inlined in `bin/ladder.rs`, so it works but is not reusable.
- **Colour is not ported.** `terminal.Palette` and `detect_palette` do ANSI
  colour when the stream supports it; `piquet-cli` is plain throughout.
- **`chances::density` and `survival` take no custom table.** The Python
  accepts one, with the docstring inviting you to "measure your own and pass
  it as `table`" — which is exactly what a stronger ladder would want, since
  the measured histogram is a statement about *rung-4* play.
- **`solver.partie_aware` is not ported**, deliberately: it measured worse
  than the flat objective and ships off. See TODO 1, which wants the objective
  settled at the leaf rather than linearised on the way down.
- **The interactive half of the CLI is untested.** The pure renderers have
  tests — including the one that matters, that every card drawn parses back as
  a card you could type — but `HumanAgent`'s prompts and re-prompts do not.
  The Python has 43 terminal tests; the Rust has 8, and they cover a narrower
  thing. A `Console`-style seam would make the rest testable.

## TODO — things owed that are not yet built

Ordered by how much they are needed, not by size.

1. **The partie objective — built, measured, not yet a default.** The search
   now carries both totals to the leaf and settles there
   (`solver::card_settlements`), which is what `docs/DESIGN.md` §6.4a asked
   for. It costs only **1.6× at eight tricks**, far less than the state-space
   argument suggests, because the reachable point splits at a position are
   tightly constrained.

   Over **720 mirrored last deals** it wins 249, loses 46, draws 425 — against
   the linear-weight attempt's 0–9–66. But the net settlement is **−4.49 ±
   3.48**, which is 1.3 sigma and therefore nothing. It wins often by little
   and loses rarely by a lot.

   **Next, and in this order.** Both are hypotheses, neither measured:

   - Teach the search the **pique and repique** bonuses. It ignores them, an
     approximation inherited from the additive version, and a missed repique
     is sixty points — the size of the losses swamping the wins. `pique_is_live`
     (TODO 9) is the unused helper that exists for this.
   - Raise **`max_worlds`** above thirty and see whether the loss tail shrinks.
     The flat objective averages a near-linear quantity and forgives a thin
     sample; this one does not.

   Judge any of it on `tournament::partie_duel`, not on deals. The baseline is
   in "Where we are".

2. **`rubicon nerve`, the fourth style dimension**, specified in
   `docs/DESIGN.md` §7.1 and now finally possible to implement — `chances`
   supplies everything it needs.
3. **The heuristic rungs read the partie in one place only.** The sink ceiling
   is priced in settlement, so nobody sinks a tierce that would carry them
   over the rubicon; but `_lead` and `_follow` are rules rather than an
   objective and there is nothing in them to weight. The solver is where the
   objective lives, and rungs 1–4 are partie-blind in play.
4. **Nothing enforces style stability except `make_opponent`.** The terminal
   draws a style once per opponent, which is right, but an agent constructed
   anywhere else still gets whatever it is handed. There is no lifecycle on the
   `Agent` protocol to hang it from.
5. **Golden JSON vectors — half built.** Six modules covered: `cards`,
   `combos`, `scoring`, `style`, `declarations`, `rules`. Generated by
   `tools/emit_vectors.py` from the Python oracle, replayed by
   `tests/test_vectors.py`, and committed under `vectors/`. 48 of the 495
   tests are now vector tests.

   Still owed: `partie`, `observation`, `chances`, `inference`, `heuristics`,
   `solver`, `match`, `tournament`. `observation` matters most of those — it
   has leaked three times — and `solver` is the one every speed estimate in
   `docs/DESIGN.md` §13 rests on.

   Conventions, both from §2.1 and both already load-bearing. **Never a
   seed**: every case is written against `deal_from` with the pack spelled out,
   because no two languages share a random number generator. **Integers where
   the engine allows it**; a tolerance where it does not, which starts to bite
   at `chances`.

   The generator executes its own error and support cases, so a vector
   claiming `ValueError` cannot be committed unless it raises one. That caught
   a real mistake already: a hand-written "elder sinks" case had the wrong
   derived values, because younger still wins the category and so still
   announces and shows.

6. **A replay format for a finished deal — built.** It came out of TODO 5
   rather than separately: `vectors/rules.json` records a pack in full plus a
   scripted sequence of actions, with the whole state after every step. Enough
   to reconstruct a deal for the tutor, for debugging, and for checking a port
   step by step rather than by its final score.

7. **`explain.py` does not exist.** The design makes it a first-class module
   (§5.3, §8) and nothing has been written. The event log and the `outcomes` /
   `heard` / `seen` split were built to feed it — but §5.3's decomposed
   evaluation, which §8 assumed, never was. The design doc now says so, and
   points at the ladder instead.
8. **Re-measure `style.CALIBRATED`.** The ladder moved when the observation
   leaks were closed, and the bands were fitted against the old one.
9. **`solver.pique_is_live` is still dead code** — a documented intention with
   no caller. Either the solver should score piques or the helper should go.
10. **Younger's untaken talon cards.** If she leaves any she may expose them to
   both players after elder leads, or leave them face down. Not modelled.
11. **Carte blanche's information timing.** Elder must announce how many cards
    he intends to discard so younger can choose hers before seeing his hand.
    We score the ten and skip the choreography.
12. **Documentation and citations.** *Partly done.* A README now exists and
    orients a reader who has not read `DESIGN.md` end to end. The statistical
    bibliography is still owed: Laplace's *rule of succession* (1774) is the
    ratings prior, Zermelo (1929) is the model Bradley and Terry rediscovered
    in 1952, Hoyle (1744) computes a hypergeometric tail by hand, and
    Waldegrave's solution to *Le Her* (1713) is the oldest known mixed-strategy
    equilibrium and the historical reason to expect sinking to want a *mixed*
    answer rather than a rule. All of that still lives in docstrings and commit
    messages.

13. **Card art.** Andrew has assets sourced. Not needed until the terminal UI
    is replaced.

## Code review findings

### Second pass, after Milestone 5 — four bugs, all fixed

The load-bearing thing first: **the solver is exact.** Cross-checked against a
deliberately stupid brute-force reference — plain `Card` objects, no bitmasks,
no memo, no equivalence reduction — over 450 random endgames, leading and
mid-trick: zero mismatches.

| Bug | Why it mattered |
|---|---|
| `pique` scanned the log; `repique` walked the order of precedence | The same fact — younger winning the point — denied elder the 60 and left him the 30. Two derivations in one file contradicting each other. **16 undue piques in 4,000 deals**, 30 points each |
| Inference excluded the truth whenever elder took fewer than five | Younger draws from the top of what he left, which begins *inside* the five he has read. The true hand was excluded **100% of the time** at every setting below five: the solver averaging over worlds every one of which was impossible. Latent only because every agent built takes the full five |
| The tie-break was always public | "Point of five" is what is said; "forty-nine" is asked for only when the shapes match, and a beaten holding is never shown. Narrowed the opponent's possible hands **1.6× more than the rules allow** |
| Elder heard younger's declarations before he had led | She names nothing until he leads to the first trick. He was choosing his sequence and set declarations — *and the card he leads* — on information he does not have |

Two smaller ones: `solve` accepted positions whose two hands cannot both be
true and answered with a `TypeError` several frames deep; and
`test_two_identical_agents_are_evenly_matched` asserted a margin under 1.0
where the true value is exactly 0, because both agents are deterministic — a
tolerance with nothing to absorb.

**Consequences worth knowing.** Elder's first lead is now genuinely blind, so
rung 4 cannot avoid her long suit until his second. And the world counts at the
first lead are asymmetric for the first time — elder median 36 against younger
56 — which is his seat advantage showing up as a number. The tie-break leak had
been hiding it by pinning both at 35.

### First pass, after Milestone 5 — six bugs, all fixed

`opponent_hand_size` decremented for any open trick; `possible_hands(limit=)`
took the first N rather than a random sample; `ratings` crashed on a shutout;
`best_card` duplicated `card_values` and gave every candidate its own
transposition table; `SolverAgent(3, rng=...)` crashed on argument forwarding;
and round-robin pairings saw different deals because boards were drawn from the
same generator the agents drew from.

### Conceptual gaps — not bugs, but things I would not defend

1. **Style stability is claimed, not enforced.** The design says a style is
   drawn once per opponent and held for a partie. Nothing in the code does
   that: agents are constructed once and reused, so stability is an accident of
   how the harness happens to work. `play_partie` is now the natural place to
   make it real.
2. **The `Agent` protocol has no lifecycle.** No notion of a deal beginning or
   ending, no per-partie state, nowhere for an opponent model to live. The
   partie exists now and this is the next thing it will demand.
3. **Every strength claim is self-referential.** Rung N beats rung N−1, and
   that is all we know. The one external check is the solver, which is exact in
   the endgame, and it beats rung 4 by 82.5%.
4. **`heuristics._keep_value` is unvalidated magic numbers.** Its weights were
   chosen by taste.
5. **Perfect-information Monte Carlo has a blind spot by construction.** The
   solver assumes the opponent can see through the table too, so it never sets
   a trap that depends on their ignorance. Known, documented, and not cheap to
   fix.

### The finding still worth chasing

Inference assumes the opponent declared honestly and fully. Against one who
sinks, the filter rules out the truth and falls back to the weaker filters —
and the candidate count goes from a median of **4 to 45**. That is concealment
doing exactly what Cavendish says it does.

And yet, measured: two rung-5 solvers over the same deals, one concealing 60%
of its cheap declarations and one declaring everything —

    conceals vs open: 33.3%, margin -6.1 points per pair

Concealment demonstrably damages the opponent's inference, elevenfold, and
still loses heavily. The reason is that our sinking is **untargeted**: it hides
any cheap declaration at random, paying a certain price for a diffuse benefit.
Cavendish is explicit that the manoeuvre is for particular positions — "it is
especially resorted to when a player has a suit unguarded, and calling all he
holds would expose the fact."

So the open question is no longer *does concealment have value* — it plainly
does — but *can a policy find the positions where that value exceeds the points
it costs?* Which is exactly what CFR is for.

## Ideas worth considering

- **Ladder-based tutoring.** Because every rung is a working agent, the tutor
  can say *"a rung-2 player would lead this; a rung-4 player leads that,
  because it heard your point"*. An explanation in terms of a **named skill the
  player can go and learn**, rather than an EV number, and it costs almost
  nothing.
- **Name the odds, not the score.** The scoreboard already says "18 more to
  cross the rubicon — about 2 in 3". The same sentence is a tutor: it tells a
  player which of the two games they are in, and it is the only place in the
  project where a probability is honest enough to quote.
- **Show the opponent's habit.** Styles are meant to be stable for a whole
  partie, so the game can track what this opponent has actually done and
  surface it: *"they have concealed twice in three deals"*.
- **Teach the blind first lead.** Now that elder really does lead before
  younger names anything, that is a genuine piece of piquet a tutor can point
  at, and it was invisible until the leak was closed.
- **Historical opponents.** A rung-4 agent with a period style vector, named
  for Cotton or Cavendish, as flavour. Cheap; possibly delightful.
- **Let the player ask to see a combination.** The rules give this right and
  the engine models the information correctly, but nothing exposes it as an
  action.

## Hard-won lessons

Things the engine has overturned, all of which had been written down with
conviction first:

| Believed | Measured |
|---|---|
| Maximum deal score is 153 | **170** — Hoyle was right; sets pay far better per card than length |
| Carte blanche is 1 in 1,792 deals | 1 in 1,792 **hands**; 1 in ~896 deals |
| Elder's advantage is structural | Only if he **uses** the full exchange: 52.5% vs 49.6% |
| Keeping guards is a skill | Loses on every seed — piquet pays for tempo, not defence |
| Cashing an ace beats ducking | Ducking wins: the ace takes the *last* trick, worth two |
| The style dimensions are EV-neutral | None were, before calibration |
| A pique reckons in the order it happened | In the **order of precedence**, like a repique — the two derivations had been contradicting each other about the same fact |
| "Point of five, forty-nine" | "Point of five." The tie-break is asked for, never volunteered |
| Elder declares knowing what younger holds | He does not. He leads to the first trick before she names anything, so his first lead is blind |
| A point is a point | Not in a partie. Six, when it carries you over the rubicon; **plus one to your opponent** while a hundred is out of their reach, because a rubiconed loser pays the sum |
| The two scores in a deal are roughly independent | They correlate at **−0.47**, so the joint had to be sampled rather than assumed |
| Every unaccounted-for card is equally likely to be hers | An ace is, 100% of the time; a seven, 28% — though correcting it is worth only +0.3 a pair |
| The hand-tuned discard must be leaving points on the table | A Monte Carlo with a hundredfold more compute per decision agrees with it five times in six |
| Hoyle's three-to-two on younger's draw | Right, and the sentence pins down which sum he did: 23/57, or 1.478 to 1 |

And three methodological ones:

- **Deal luck swamps skill.** Never compare agents over independently shuffled
  deals; an ad-hoc harness without mirroring disagreed with itself by five
  sigma.
- **Prefer measuring to reasoning wherever measuring is cheap.** It has been
  cheap every single time.
- **Beware the maximum of noisy estimates.** The optimizer's curse turned a
  measurement error of a few points into an apparent six-point edge, and it
  will do it again anywhere a policy is chosen by argmax over rollouts.
- **A display that is prettier than it is typeable is unusable.** The hand was
  drawn as `♠ K J 7` and the prompt wanted `KS`. I never saw it because I had
  been typing codes the whole time; the first person to sit down could not
  start. Make the output and the input the same language.
- **A test that cannot fail is not a test.** Two deterministic agents playing
  mirrored pairs come out level *exactly*, so a tolerance of 1.0 was measuring
  nothing. Check whether the slack is doing any work.

## Notes to a future session

- Andrew has wanted to build this for ~10 years. He prefers deliberate design
  conversation to speed, enjoys tangents and side quests, and wants the result
  to be *fun*, not merely correct.
- **Consult him before any long or paid compute run**, with a runtime and cost
  estimate in hand. Milestone 8 is the first one that needs it.
- `observation.py` is still the module most likely to be got subtly wrong. It
  has now leaked three times: `View.results` handed over the opponent's full
  declarations; `Announcement` published the tie-break unconditionally; and
  `_heard` gave elder younger's declarations before he had led. Treat every
  addition to `View` with suspicion, and ask of each field *when was this said
  aloud, and by whom*.
- Tests: 447 of them. `pytest -m "not slow"` is the tight loop at **~16s**;
  the full suite is **~94s**. Both had drifted badly and the drift was one
  test: a full twelve-card solve, unmarked, taking forty-five seconds on its
  own and making the "fast" loop sixty-three. It is marked now, and a cheap
  test covers the same arithmetic. **Check `--durations` when the loop starts
  to feel slow** — it was one test, not creeping decay, and it will be again.
- The slow tests are the statistical ones and they have caught more real bugs
  than the unit tests, so they stay in the default run.
- Re-measure `style.CALIBRATED` whenever the ladder changes. What counts as a
  near-equal option depends on how well the agent plays.
