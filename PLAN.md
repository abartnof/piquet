# Piquet — Living Plan

> Insurance against lost context. `docs/DESIGN.md` holds the *reasoning*,
> `docs/PIQUET.md` the *game*, `docs/LITERATURE.md` the *sources*; this file
> holds *where we are and what is left*. Last updated after Milestone 4.

## Where we are

**Milestones 1–5 complete. 319 tests. Reviewed; six bugs fixed.**

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
  inference.py     which hands the opponent can possibly hold
  solver.py        exact endgame search, and the agent that uses it
```

Ratings, anchored on random play: **L1 359, L2 795, L3 847, L4 903.** The
solver beats L4 by 81% / +6.0 points per mirrored pair — a bigger jump than all
the heuristic rungs combined.

## Next action

**Milestone 6 — the partie.** Six deals, alternating dealer, rubicon settlement.
See the first TODO item: it is the largest thing still missing, and it unblocks
both the rubicon endgame and the fourth style dimension.

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
- [x] 5. **Exact endgame solver** + inference; rung 5 (81%, +6.0 pts over L4)
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

## Code review findings

A critical pass over everything, after Milestone 5.

### Bugs found and fixed

| Bug | Why it mattered |
|---|---|
| `opponent_hand_size` decremented for *any* open trick | Wrong whenever the asker is the leader. Invisible in play — an agent only asks on its own turn — but it would have built candidate hands one card short |
| `possible_hands(limit=)` took the **first** N | `combinations` emits in a fixed order, so the cap returned hands all sharing the same low-indexed cards: a systematically skewed sample fed straight into a Monte Carlo average. Now samples at random |
| `ratings` crashed on a shutout | An agent winning nothing got strength zero, and the Elo conversion took its logarithm. A 10–0 result is exactly what the harness is *for* |
| `best_card` duplicated `card_values` | ~45 duplicated lines, and a fresh transposition table per candidate — several times the cost for an identical answer |
| `SolverAgent(3, rng=...)` crashed | `*args`/`**kwargs` forwarding injected a default `level` and then collided with a positional one |
| Round-robin pairings saw **different deals** | Boards were drawn from the same generator the agents drew from, so a stochastic agent shifted every later deal just by consuming numbers. Deals now come from their own generator, and a round robin shares one set across every pairing — making the whole table a paired comparison |

### Conceptual gaps — not bugs, but things I would not defend

1. **The AI optimises the wrong objective.** Everything — heuristics, solver,
   styles — maximises *points in a deal*. The game is a **partie** with rubicon
   settlement, where failing to reach 100 costs you the sum of both scores
   rather than the difference. Near that threshold, maximising deal points is
   simply not the same as maximising the result. The solver will need a partie
   context before it is playing the actual game.
2. **Every strength claim is self-referential.** Rung N beats rung N−1, and
   that is all we know. A ladder in which each rung beats the one below could
   still be uniformly poor. The one external check we have is the solver, which
   is *exact* in the endgame — and it beats rung 4 by 81%, which suggests rung 4
   is considerably weaker in absolute terms than its rating implies.
3. **Style stability is claimed, not enforced.** The design says a style is
   drawn once per opponent and held for a partie. Nothing in the code does that:
   agents are constructed once and reused, so stability is an accident of how
   the harness happens to work.
4. **The `Agent` protocol has no lifecycle.** No notion of a deal beginning or
   ending, no per-partie state, nowhere for an opponent model to live. That will
   have to change for the partie, and for the "show the opponent's habit" idea.
5. **`solver.pique_is_live` is dead code** — a documented intention with no
   caller. Either the solver should score piques or the helper should go.
6. **`heuristics._keep_value` is unvalidated magic numbers.** Its weights were
   chosen by taste. We know rung 2 beats rung 1 decisively; we do not know that
   these particular coefficients are good ones.
7. **Carte blanche's information timing is not modelled.** Elder must announce
   how many cards he intends to discard so younger can choose hers before seeing
   his hand. We score the ten and skip the choreography.

### One finding worth chasing

Inference assumes the opponent declared honestly and fully. Against an opponent
who sinks, the filter rules out the truth and falls back to the weaker filters —
and the candidate count goes from a median of **4 to 45**. That is concealment
doing exactly what Cavendish says it does.

It also means the earlier verdict that "sinking costs points at every setting"
was measured against opponents that do not use inference at all. Rung 5 does —
so the question was whether sinking finally pays against it.

**Measured: it still does not.** Two rung-5 solvers over the same deals, one
concealing 60% of its cheap declarations and one declaring everything:

    conceals vs open: 33.3%, margin -6.1 points per pair

So concealment demonstrably damages the opponent's inference — elevenfold — and
still loses heavily. The reason is that our sinking is **untargeted**: it hides
any cheap declaration at random, paying a certain price for a diffuse benefit.
Cavendish is explicit that the manoeuvre is for particular positions — "it is
especially resorted to when a player has a suit unguarded, and calling all he
holds would expose the fact."

That sharpens the open question rather than closing it. It is no longer *does
concealment have value* — it plainly does — but *can a policy find the positions
where that value exceeds the points it costs?* Which is exactly what CFR is for,
and a much better-posed question than the one we started with.

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
| Cashing an ace beats ducking | Ducking wins: the ace takes the *last* trick, worth two |
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
- **`View` will need partie context** — the running scores and how many deals
  remain — before an agent can play the rubicon endgame or express the
  *rubicon nerve* style. Deliberately not built yet: designing an interface for
  something that does not exist is how speculative generality gets in. It goes
  in with the partie, in one edit, rather than being guessed at now.
- Tests: `pytest -m "not slow"` runs in ~6s for a tight loop; the full suite is
  ~28s. The slow ones are the statistical tests, and they have caught more real
  bugs than the unit tests, so they stay in the default run.
- Re-measure `style.CALIBRATED` whenever the ladder changes. What counts as a
  near-equal option depends on how well the agent plays.
