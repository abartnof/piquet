# Piquet — Living Plan

> Insurance against lost context. `docs/DESIGN.md` holds the *reasoning*,
> `docs/PIQUET.md` the *game*, `docs/LITERATURE.md` the *sources*; this file
> holds *where we are and what is left*. Last updated after Milestone 6.

## Where we are

**Milestones 1–6 complete. 365 tests. Two review passes; ten bugs fixed.**

A whole partie can now be played: six deals, the deal alternating, settled by
the rubicon. Four measured rungs of opponents exist, plus an exact-endgame
solver, with styles and erraticism, and a tournament harness that rates them.
Every decision is logged to JSONL.

```
piquet/
  cards.py         32-card pack; Hand as a bitmask
  combos.py        point / sequence / set detection, scoring, comparison
  declarations.py  the meld layer: announcing, showing, sinking
  rules.py         Deal as an immutable state machine
  scoring.py       the event log; pique and repique
  partie.py        six deals, Side vs seat, the rubicon settlement
  observation.py   View — the only way an agent sees a deal
  agents.py        the Agent protocol; RandomAgent
  heuristics.py    the capability ladder, rungs 1–4
  style.py         the third axis, calibrated by measurement
  match.py         running deals and parties; the move log
  tournament.py    mirrored-pair duels, Bradley-Terry ratings
  inference.py     which hands the opponent can possibly hold
  solver.py        exact endgame search, and the agent that uses it
```

Ratings, re-measured after the second review pass, 500 mirrored pairs per
pairing, anchored on random play: **L1 336, L2 778, L3 818, L4 866.** The
solver beats L4 by **82.5% / +5.0 points per pair** over 100 pairs — still a
bigger jump than all the heuristic rungs above the first combined.

Over 60 parties of rung-4 play a side averages **145** across six deals, and
**17 of 120** sides finish short of the rubicon. The threshold is a live
threat, not a curiosity.

## Next action

**Undecided — put to Andrew.** Three candidates, in the order I would rank
them; see "Open questions for Andrew" below.

1. **Milestone 7, the terminal UI.** Makes the thing playable by a person,
   which is the point of the project.
2. **Teach the agents the partie.** `View.partie` now exists and nothing reads
   it. This is `docs/DESIGN.md` §6.4a, the objective being wrong above the deal.
3. **Fix the solver's world prior.** The largest measured weakness in the AI
   (see below), and cheap.

## Settled decisions

| Decision | Choice |
|---|---|
| Rule authority | **pagat.com** wins all conflicts; variants behind flags |
| Game implemented | Rubicon Piquet, 32 cards, 6-deal partie |
| Language | Python; plain serialisable state; golden JSON vectors for a future JS port |
| Scoring model | Ordered **event log**, not a running total |
| Bonus reckoning | Law 67's **order of precedence**, for pique and repique alike |
| Seats vs people | `Player` is a seat and swaps each deal; `Side` plays the partie |
| Evaluation model | **Decomposed vector**, never a scalar |
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
- [ ] 7. **Terminal UI**; skill and erratic controls; a playable game
- [ ] 8. Exchange policy — *runtime and cost agreed with Andrew first*
- [ ] 9. Training mode
- [ ] 10. CFR declarations

## Open questions for Andrew

Three things I would not decide alone.

### 1. The solver's model of the opponent is measurably miscalibrated

`possible_hands` treats every consistent hand as equally likely. It is not.
The cards that are *not* in the opponent's hand are her discards and whatever
is left of the talon, and both are systematically low, because everybody
throws low cards. Measured over 600 deals at elder's first lead:

| unseen card | really in her hand | the model believes | error |
|---|---|---|---|
| ace | 100.0% | 89.3% | −10.7 |
| king | 99.9% | 89.9% | −10.0 |
| ten | 96.5% | 85.7% | −10.8 |
| nine | 69.1% | 72.2% | +3.1 |
| eight | 47.6% | 65.2% | +17.6 |
| seven | 27.7% | 56.7% | +29.0 |

The error runs in the worst possible direction: the solver **under-rates the
opponent's high cards and over-rates her low ones**, which is exactly the
mistake that makes it too optimistic about its own winners.

The fix is small — weight the sample by rank, or weight each world's value —
but it changes every strength number we publish, so it wants a deliberate
re-measurement rather than a quiet patch. It also interacts with Milestone 8:
a trained discard policy *is* the correct prior, so a hand-fitted one now is
either a stopgap or a baseline to beat.

### 2. `ratings()` is meaningless around a shutout

The log-of-zero crash was fixed with a `1e-9` floor. With a genuine 0-win
anchor the floor is now the only thing setting the scale: the table reads
~3,700 for everyone, and one single win collapses it to ~713. The number is
the floor constant, not the play. Iterating longer does not change it.

The standard fix is a smoothing prior — a fraction of a win and a loss against
a virtual average opponent — which keeps ratings finite and continuous. It
would move every published rating slightly. Worth doing, but it is the
yardstick, and I would rather not change the yardstick without saying so.

### 3. `ratings()` throws the margin away

Bradley-Terry is fitted on wins and draws only, though `DuelResult.margin` is
described in the code as "the finer-grained measure" — and under rubicon
settlement the margin is what a partie actually pays out on. A deal won by one
point counts the same as a capot. There is a lot of statistical power on the
floor here, and it is free to pick up.

Related: L3 and L4 draw **390 of 500** mirrored pairs. Rung 4's one
distinguishing capability now fires rarely, because it cannot fire on the
first lead at all (see the review below). The rung is real but thin.

## TODO — things owed that are not yet built

Ordered by how much they are needed, not by size.

1. **Nothing reads `View.partie`.** The heuristics, the solver and the style
   calibration all still maximise points within a deal. The interface exists
   now; the behaviour does not. `docs/DESIGN.md` §6.4a.
2. **`rubicon nerve`, the fourth style dimension**, specified in
   `docs/DESIGN.md` §7.1 and now finally possible to implement.
3. **Golden JSON vectors are promised but not produced.** `docs/DESIGN.md`
   says they are emitted "from day one" as portability insurance for a future
   JavaScript port. They are not. Owed.
4. **No replay format for a finished deal.** Needed by the tutor (reviewing a
   hand afterwards), by debugging, and by the golden vectors above.
5. **`explain.py` does not exist.** The design makes it a first-class module
   (§5.3, §8) and nothing has been written. The event log and the `outcomes`
   / `heard` / `seen` split were built to feed it.
6. **Hoyle's odds claim is unchecked.** "Three to two against the younger-hand's
   taking one Card out of three to save a Pique." The maximum-score claim was
   checked and confirmed; this one is still open.
7. **Re-measure `style.CALIBRATED`.** The ladder moved when the observation
   leaks were closed, and the bands were fitted against the old one.
8. **`solver.pique_is_live` is still dead code** — a documented intention with
   no caller. Either the solver should score piques or the helper should go.
9. **Younger's untaken talon cards.** If she leaves any she may expose them to
   both players after elder leads, or leave them face down. Not modelled.
10. **Carte blanche's information timing.** Elder must announce how many cards
    he intends to discard so younger can choose hers before seeing his hand.
    We score the ten and skip the choreography.
11. **Card art.** Andrew has assets sourced. Not needed until the terminal UI
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
| Every unaccounted-for card is equally likely to be hers | An ace is, 100% of the time; a seven, 28% |

And three methodological ones:

- **Deal luck swamps skill.** Never compare agents over independently shuffled
  deals; an ad-hoc harness without mirroring disagreed with itself by five
  sigma.
- **Prefer measuring to reasoning wherever measuring is cheap.** It has been
  cheap every single time.
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
- Tests: `pytest -m "not slow"` runs in ~6s for a tight loop; the full suite is
  ~35s. The slow ones are the statistical tests, and they have caught more real
  bugs than the unit tests, so they stay in the default run.
- Re-measure `style.CALIBRATED` whenever the ladder changes. What counts as a
  near-equal option depends on how well the agent plays.
