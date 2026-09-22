# Piquet — Living Plan

> Insurance against lost context. `docs/DESIGN.md` holds the *reasoning*,
> `docs/PIQUET.md` the *game*, `docs/LITERATURE.md` the *sources*; this file
> holds *where we are and what is left*. Last updated after Milestone 4.

## Where we are

**Milestones 1–4 complete. 295 tests, ~28s to run, nothing has cost more than a
few seconds of CPU except one 205-second search.**

A deal can be dealt, exchanged, declared, played and scored. Four measured rungs
of opponents exist, with styles and erraticism, and a tournament harness that
rates them. Every decision is logged to JSONL.

```
piquet/
  cards.py         32-card pack; Hand as a bitmask
  combos.py        point / sequence / set detection, scoring, comparison
  declarations.py  the meld layer: announcing, showing, sinking
  rules.py         Deal as an immutable state machine
  scoring.py       the event log; pique and repique
  observation.py   View — the only way an agent sees a deal
  agents.py        the Agent protocol; RandomAgent
  heuristics.py    the capability ladder, rungs 1–4
  style.py         the third axis, calibrated by measurement
  match.py         running deals; the move log
  tournament.py    mirrored-pair duels, Bradley-Terry ratings
```

Ratings, anchored on random play: **L1 359, L2 795, L3 847, L4 903.**

## Next action

**Milestone 5 — the exact play-phase solver.** Now de-risked: the world count
after declarations is a median of 21 (measured, `docs/DESIGN.md` §4.2), so
enumeration is cheap enough to run while somebody waits.

## Settled decisions

| Decision | Choice |
|---|---|
| Rule authority | **pagat.com** wins all conflicts; variants behind flags |
| Game implemented | Rubicon Piquet, 32 cards, 6-deal partie |
| Language | Python; plain serialisable state; golden JSON vectors for a future JS port |
| Scoring model | Ordered **event log**, not a running total |
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
- [ ] 5. **Exact play solver**; ladder rung for it
- [ ] 6. **The partie** — six deals, alternating deal, rubicon settlement
- [ ] 7. **Terminal UI**; skill and erratic controls; a playable game
- [ ] 8. Exchange policy — *runtime and cost agreed with Andrew first*
- [ ] 9. Training mode
- [ ] 10. CFR declarations

## TODO — things owed that are not yet built

Ordered by how much they are needed, not by size.

1. **The partie does not exist.** Everything so far is one deal. Piquet is six,
   with rubicon settlement, and that is where the game actually lives — being
   under 100 late in a partie changes correct play completely. It also unblocks
   the fourth style dimension, *rubicon nerve*, which is specified in
   `docs/DESIGN.md` §7.1 but not implemented because there is nothing to be
   nervous about yet.
2. **Golden JSON vectors are promised but not produced.** `docs/DESIGN.md` says
   they are emitted "from day one" as portability insurance for a future
   JavaScript port. They are not. Owed.
3. **No replay format for a finished deal.** Needed by the tutor (reviewing a
   hand afterwards), by debugging, and by the golden vectors above.
4. **`explain.py` does not exist.** The design makes it a first-class module
   (§5.3, §8) and nothing has been written. The event log and the `outcomes`
   / `heard` / `seen` split were built to feed it.
5. **Hoyle's odds claim is unchecked.** "Three to two against the younger-hand's
   taking one Card out of three to save a Pique." The maximum-score claim was
   checked and confirmed; this one is still open.
6. **Card art.** Andrew has assets sourced. Not needed until the terminal UI is
   replaced.

## Ideas worth considering

- **Ladder-based tutoring.** Because every rung is a working agent, the tutor can
  say *"a rung-2 player would lead this; a rung-4 player leads that, because it
  heard your point"*. That is an explanation in terms of a **named skill the
  player can go and learn**, rather than an EV number, and it costs almost
  nothing — the agents already exist.
- **Show the opponent's habit.** Styles are stable for a whole partie, so the
  game can track what this opponent has actually done and surface it: *"they
  have concealed twice in three deals"*. That teaches Cavendish's central
  inference using machinery built for other reasons.
- **Historical opponents.** A rung-4 agent with a period style vector, named for
  Cotton or Cavendish, as flavour. Cheap; possibly delightful.
- **Let the player ask to see a combination.** The rules give this right and the
  engine models the information correctly, but nothing exposes it as an action.

## Hard-won lessons

Things the engine has overturned, all of which had been written down with
conviction first:

| Believed | Measured |
|---|---|
| Maximum deal score is 153 | **170** — Hoyle was right; sets pay far better per card than length |
| Carte blanche is 1 in 1,792 deals | 1 in 1,792 **hands**; 1 in ~896 deals |
| Elder's advantage is structural | Only if he **uses** the full exchange: 52.5% vs 49.6% |
| Keeping guards is a skill | Loses on every seed — piquet pays for tempo, not defence |
| The style dimensions are EV-neutral | None were, before calibration |

And two methodological ones:

- **Deal luck swamps skill.** Never compare agents over independently shuffled
  deals; an ad-hoc harness without mirroring disagreed with itself by five sigma.
- **Prefer measuring to reasoning wherever measuring is cheap.** It has been
  cheap every single time.

## Notes to a future session

- Andrew has wanted to build this for ~10 years. He prefers deliberate design
  conversation to speed, enjoys tangents and side quests, and wants the result to
  be *fun*, not merely correct.
- **Consult him before any long or paid compute run**, with a runtime and cost
  estimate in hand. Milestone 8 is the first one that needs it.
- `observation.py` is the module most likely to be got subtly wrong. It has
  already leaked once — `View.results` handed over the opponent's full
  declarations including suits. Treat every addition to `View` with suspicion.
- Re-measure `style.CALIBRATED` whenever the ladder changes. What counts as a
  near-equal option depends on how well the agent plays.
