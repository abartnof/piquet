# Piquet — Living Plan

> Insurance policy against lost context. `docs/DESIGN.md` holds the *reasoning*;
> this file holds *where we are*. Update it whenever a decision is made or a
> milestone moves. Last updated 2026-09-21.

## Where we are right now

**Phase: Milestone 2 complete. A full deal can be played end to end.**

Done:
- Rules researched across **twenty sources, nine of them period texts read in
  full** (`docs/LITERATURE.md`), and reconciled in `docs/DESIGN.md` §3.
- `docs/PIQUET.md` written: an encyclopedic account of the game's history,
  rules, strategy and terminology, synthesised from the whole reading. Doubles
  as source material for the training mode.
- **All open rule questions closed**, every one in pagat's favour, most of them
  by Cavendish's Portland Club laws (1892).
- Combinatorics settled: the whole game is not tabular, but the play phase is
  nearly perfect-information and exactly solvable (§4). This is the finding the
  whole AI design rests on.
- Architecture, AI approach, skill model, and tutor design written up (§5–§9).
- Git repository initialised on `main`. Nothing pushed; no remote configured.

Next action: **Milestone 3** — a random agent playing 10,000 legal deals with
the statistical invariants checked and the move log written from the first game.

A smoke run of 5,000 random deals already completes with all invariants
holding. Early figures, from deliberately bad play: elder wins 53% of deals,
carte blanche appeared 3 times against 2.8 expected, and both bonuses occur —
105 elder piques, 32 elder repiques, and 16 **younger** repiques, which is the
observable proof that the category-order derivation is right.

## Settled decisions

| Decision | Choice |
|---|---|
| Rule authority | **pagat.com wins** all conflicts; variants go behind flags |
| Game implemented | Rubicon Piquet, 32 cards, 6-deal partie |
| Language | Python; state as plain serializable data; golden JSON vectors for a future JS port |
| Scoring model | Ordered **event log**, not a running total (two orderings needed for pique vs repique) |
| Evaluation model | **Decomposed vector**, never a scalar — explainability depends on it |
| Play-phase AI | Exact enumeration + solver. No training needed |
| Exchange AI | Monte Carlo rollouts, then a fitted regression |
| Declaration AI | CFR. Built last |
| Skill model | **Capability ladder** (9 named rungs), not a noise dial |
| Erraticism | Effective level drawn per decision from a distribution around the slider |
| LLM involvement | None in gameplay; optional for phrasing tutor explanations |

## Milestones

- [x] 1. `cards` + `combos` — representation, detection, comparison (94 tests)
- [x] 2. `rules` + `scoring` — phase machine, event log, pique/repique (191 tests)
- [ ] 3. Random agent plays 10,000 legal games; statistical invariants pass;
         move log written from the first game
- [ ] 4. Heuristic agents, ladder levels 1–5; Elo round-robin harness
- [ ] 5. Exact play solver; verify the 455-world bound empirically; level 7
- [ ] 6. Playable game, basic UI, skill + erratic controls
- [ ] 7. Exchange policy — **runtime and cost agreed with Andrew first**
- [ ] 8. Training mode
- [ ] 9. CFR declarations; level 9

## Open questions for Andrew

0. **Rules research is complete** unless you want more. Every conflict is
   resolved and documented; further reading is unlikely to change a decision.
1. **Milestone 1 scope** — start with `cards`/`combos`, or go straight at the
   rules state machine? Recommendation: `cards`/`combos` first, they are pure
   functions and everything else depends on them.
2. **UI target** — terminal first, or straight to something graphical? The
   engine does not care, and a terminal UI is nearly free.
3. **Card art** — Andrew has free assets sourced; format and licence TBD.

## Notes to a future session

- Andrew has wanted to build this for ~10 years. He prefers deliberate design
  conversation over speed, and wants to be consulted before any expensive
  training run, with a runtime and cost estimate in hand.
- The single most load-bearing claim in the design is §4.2: elder faces at most
  C(15,12)=455 possible opponent hands, younger at most C(17,12)=6,188, and both
  collapse much further after the declaration dialogue. **Verify this
  empirically at Milestone 5.** If it is wrong, §6.1 needs rethinking.
- `observation.py` is the module most likely to be got subtly wrong, and a leak
  there invalidates every measurement. Treat it with suspicion.
