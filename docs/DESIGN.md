# Piquet — Design Document

> Status: living document. Last substantive revision 2026-09-21.
> This file is the project's memory. If the conversation context is lost,
> this document plus `PLAN.md` should be sufficient to resume work.

## 1. What we are building

A playable, teachable implementation of **Piquet**, the two-player 32-card
game that was France's national card game from the 16th century until it
faded after WWI. David Parlett calls it "still one of the most
skill-rewarding card games for two," but it is now played only by
aficionados. Our audience is therefore *new players*, and teaching is a
first-class goal, not a bonus feature.

Three deliverables, in priority order:

1. A correct, fast, well-tested **rules engine**.
2. An **opponent** whose skill is adjustable, and whose inconsistency is
   separately adjustable.
3. A **training mode** that is interactive rather than expository — bad
   decisions discouraged, impossible decisions blocked, with reasons given.

Non-goals for now: graphics beyond the functional (the user has free card
art we will integrate later), networked play, and the 3- and 4-player
variants (Piquet Normand, Piquet Voleur, Piquet à Écrire).

## 2. Engineering conventions

- **Python** for the reference implementation.
- **Test-driven development** — tests precede implementation.
- **Atomic commits** — one logical change each.
- **Modular design** — GUI, rules, scoring, search, and agents are separable
  so that future card games can reuse the parts.
- **Portability kept cheap, not free**: game state is plain serializable data
  from day one, and the test suite emits golden JSON vectors, so a future
  JavaScript/TypeScript port is a mechanical translation that can be
  *verified* rather than a rewrite. A browser-embeddable version is a
  long-term aspiration.

## 3. The rules, as we will implement them

Sources: pagat.com/notrump/piquet.html and en.wikipedia.org/wiki/Piquet.
Where they disagree, see §3.7.

### 3.1 Pack and deal

32-card pack (A K Q J 10 9 8 7 in each suit). Ace high. 12 cards each,
8 to the **talon**, split 5 (top, for elder) and 3 (bottom, for younger).
The non-dealer is **elder hand**, the dealer **younger hand**; dealing is a
disadvantage. A **partie** is 6 deals with the deal alternating. The dealer
may deal in 2s or 3s but must keep the same method for her remaining deals
in the partie.

Card values for tie-breaking: ace 11, court cards 10, others face value.

### 3.2 Carte blanche

A hand with no court cards scores **10**. It must be announced as soon as
noticed, and proved by dealing the hand rapidly face up — *after* the
opponent has discarded but *before* the holder discards. If elder holds it,
he first announces how many cards he intends to discard, so younger can
choose her own discards before seeing elder's hand.

Two facts we can assert as tests. Carte blanche occurs once in **1,792
hands** (C(20,12)/C(32,12) = 5.579e-4, matching Wikipedia's "roughly once
every 1,800 hands") -- but a deal has *two* hands and they are mutually
exclusive, so one turns up **somewhere in a deal about once in 896 deals**.
Our first draft conflated the two, and the statistical harness caught it at
once by observing 1 in 873. And **both players can never hold it
simultaneously**: that would need 24 non-court cards, and only 20 exist.

### 3.3 The exchange

Elder discards 1–5 face down and draws the same number from the top five.
If he takes fewer than five, he may look at the remainder of those five.
**Elder therefore always knows all five top talon cards.** This single fact
drives most of §4.

Younger then discards at least one and at most (8 − elder's take), usually
3. If she leaves cards, she may expose the remainder to both players after
elder leads.

Each player keeps his own discards beside him and **may refer to them during
play**. This matters: a bot consulting its own discards is not cheating.

### 3.4 Declarations

Three categories, declared **one at a time**, elder first, with younger
answering *good* / *not good* / *equal* after each before the next begins.
Elder may adapt a later declaration to what he learns from an earlier
answer, but **may not revise a declaration upward** once answered. After
elder leads to the first trick, younger announces and scores the categories
where she said *not good*, or that elder skipped.

- **Point** — most cards in one suit; scores that number of cards. Ties
  broken by summed card value; exact ties score for neither.
- **Sequence** — longest run of 3+ in a suit. Tierce 3, quart 4, **quint 15,
  sixième 16, septième 17, huitième 18**. Note the jump from 4 to 15. The
  winner also scores every other sequence he holds; the loser scores none.
  Ties broken by top card; exact ties score for neither.
- **Set** — quatorze (four of A/K/Q/J/10) 14, trio (three of same) 3. Nines
  and below never count. Any quatorze beats any trio. Winner also scores his
  other sets; loser scores none.

**Sinking** — deliberately not declaring a combination — is legal, and is
the strategic heart of the game. Declaring buys points; concealing buys
information advantage in the play.

Either player may afterwards ask to see any combination that was scored for,
or that scored nothing because of equality.

### 3.5 The play

12 tricks, no trumps, must follow suit. Per Cavendish Law 65, each player
scores **1 for every card he leads, and 1 for every trick he wins with the
second card**; the winner of the **last trick scores 2 instead of 1**. **10 for cards**
(winning most tricks; nothing at 6–6), or **40 for capot** (all 12).

### 3.6 Pique and repique

- **Repique** — 30+ in *declarations alone* before the opponent scores
  anything: **+60**. For repique, points are reckoned in strict *category*
  order: carte blanche, point, sequences, sets.
- **Pique** — 30+ in declarations *and play* before the opponent scores
  anything: **+30**. Reckoned in *actual occurrence* order. Only elder can
  score a pique, because he always scores 1 for leading before younger can
  score anything.
- A player scores pique or repique, never both.
- Equality in a declaration does not prevent either.

**These two rules use two different orderings of the same points.** That is
the single subtlest thing in Piquet, and it is why §5.2 models scoring as an
ordered event log rather than a running total.

### 3.7 Rule conflicts across sources

**pagat.com is our authority. Where sources disagree, pagat wins.** The
disagreements are still recorded, because each is a variant someone plays and
most are cheap to put behind a flag.

Sources consulted, roughly in order of trustworthiness:

| Source | Standing |
|---|---|
| **pagat.com** | Our authority |
| **parlettgames.uk** (Parlett, historical rules) | Very high. Codifies the Portland Club game, with Henry Jones ("Cavendish", 1831–99) as principal authority — the same lineage pagat follows |
| **en.wikibooks.org** | High; unusually precise on edge cases |
| **en.wikipedia.org** | Good, but conflates variants with the core game |
| **fr.wikipedia.org**, **de.wikipedia.org** | Good for terminology and history; both describe materially different continental rules (§3.9) |
| **cardgameheaven.com** | Adequate |
| **whiteknucklecards.com** | Mixed — it imports genuine *older* rules into a modern description. Not wrong so much as chronologically confused (§3.9) |
| **Cavendish, *The Laws of Piquet* (1892/96)** | **The club laws themselves** — the authority every modern source descends from. Decisive where cited |
| **britannica.com** | Very high — the piquet entry is **written by David Parlett**, and describes rubicon piquet specifically. Retrieved manually after the site refused automated access |
| CMU medieval text | A different, older game (§3.8) |

| # | Question | pagat | Other sources | Decision |
|---|---|---|---|---|
| R1 | Do the 10 for *cards* count toward a pique? | **No** | **No**: Cavendish (decisive), Cotton 1674, Wikibooks, Parlett. **Yes**: en-Wikipedia, cardgameheaven | **No — closed.** Cavendish Law 67 puts "the cards" in category VI, after points made in play; Law 69 spells out the consequence: "A capot reckons after points made in play; and, therefore, does not count toward a pique." Law 66 makes capot and the ten for cards the same score. Flag kept for configurability only |
| R2 | Minimum length for *point*? | None | Only en-Wikipedia claims 4; everyone else, none | **No minimum** |
| R3 | Must *younger* exchange at least one card? | **Yes** | **The conflict was never a conflict.** Cavendish Law 22 (*Piquet*): younger "is obliged to discard one card." The same volume's *Laws of Piquet au Cent*: younger "is **not** obliged to discard any card." Cotton 1674 agrees with the former | **Yes, at least one — closed.** Sources saying otherwise imported the au cent rule into a Rubicon description. Flag retained |
| R4 | **Carte rouge**? | Not mentioned | Values vary wildly: 10, 20, 40, or 50. **Absent from Cavendish entirely** | **Off by default** — it is a continental rule with an unstable value, not part of the English club game |
| R5 | Last trick worth? | 1 *bonus* | Cavendish Law 65: "The winner of the last trick scores **two** instead of one." fr-Wikipedia agrees (2 total); de-Wikipedia says 3 | **2 to its winner** — i.e. the normal 1 plus a bonus of 1. pagat's "one additional point" says the same thing; our earlier reading of this as a flat 1 was an ambiguity, not a conflict |
| R6 | Exact ties in a category | Neither scores | Wikibooks and Parlett agree explicitly. fr-Wikipedia dissents: all valid combinations count regardless | **Neither scores**; equality still does not block pique or repique |
| R7 | Scoring system | Rubicon, 6 deals | Parlett distinguishes Rubicon from basic "Saunt" (race to 100) | **Rubicon** |

A note on **pique and repique bookkeeping**: French and German sources express
these as the score *jumping to* 60 and 90 respectively, rather than as +30 and
+60 bonuses. These are the same rule — 30+30 and 30+60 — stated differently.
Ours is the additive form, but the continental form is a nice confirmation that
the thresholds are right.

### 3.7a Two things Britannica settles

**Trick scoring is not what it looks like.** Britannica says "a trick scores one
point if won by the player who led it; otherwise it scores two points," and
Parlett's own site gives the same shorthand. Read carelessly, that says the
winner of an opponent-led trick takes 2 and the leader takes nothing — which
would contradict pagat and, more tellingly, contradict Britannica's own
statement that elder "leads a card to the first trick, and adds one point for
leading."

The consistent reading is that this describes the trick's **total yield**, not
one player's take:

- Leader always scores **1 for leading**, regardless of outcome.
- If the opponent wins it, the opponent scores **1** more.
- So the trick is worth 1 point (leader led and won) or 2 (split 1–1).

This matches pagat exactly. Recording it because the shorthand is a genuine
trap, and because getting it wrong would silently corrupt every pique
calculation — pique depends on *who* scored and *when*, not just on totals.

**Set ties are impossible.** Britannica: "ties are not possible" for sets. This
is a fact about the pack rather than a rule — two players cannot both hold three
of the same rank (that needs six cards of a rank; only four exist), and sets are
compared by rank, which is unique. So unlike point and sequence, the set
category never needs exact-tie handling. Assert it rather than handle it.

### 3.8 The sequence scores are a formula, not a table

Worth noticing, because it is both an implementation simplification and a good
teaching device. whiteknucklecards states the sequence scores as "3 and 4 for
tierce and quart, then **10 plus one per card** for five or more":

    tierce  3 -> 3      quint    5 -> 15
    quart   4 -> 4      sixième  6 -> 16
                        septième 7 -> 17
                        huitième 8 -> 18

That reproduces the standard table exactly. The apparently bizarre jump from 4
to 15 is just the point at which a 10-point bonus kicks in. The tutor should
teach it this way — "a fifth card is worth eleven more points than the fourth"
is memorable in a way the table is not, and it explains *why* players will
wreck their point to chase a quint.

### 3.9 The period version and the continental versions

Recorded so we do not mistake them for variants of our game.

**The period game** (CMU medieval text): a **36-card** pack, 12 in stock, up to
8 exchanged per player, "ruffs" scored as one point per ten pips of the best
suit, sequences of 5+ scoring 10 plus length, sets worth **13** for three, capot
worth **60**, first to 100 wins. This is essentially the ancestor, close to
*Le Cent* as Rabelais knew it in 1535; French Wikipedia confirms the pack was
formalised from 36 to 32 cards in the late 17th century.

**The German game** (de-Wikipedia) diverges sharply: forehand discards **3–5**
rather than 1–5, the opponent must exchange **at least 3**, the last trick is
worth **3**, and capot is **30**. It also adds a rule that a loser under 50
points doubles the stake, and notes a variant treating tens as court cards for
carte blanche.

**The French game** (fr-Wikipedia) differs in two ways that matter: the last
trick counts 2, and — contra pagat, Parlett and Wikibooks — *all* valid
combinations score even when subordinate to the opponent's best. It also
records the delightful *Estachin* house rule from the Comtat Venaissin:
peeking at your opponent's cards costs you **70 points**.

**whiteknucklecards** deserves a correction. An earlier revision of this
document called it unreliable for scoring tricks as "1 point for each card led
higher than a 9." That is in fact the **authentic 1674 rule** (§3.11) — the page
is mixing eras, not inventing rules. Its point-scores-1 and sets-rank-"9-and-
above" claims still look like errors, but its sequence formula (§3.8) and its
trick scoring are both genuine historical material.

None of these are being implemented. They are recorded because they explain
where our rules came from, and because the historical literature (Cavendish,
Hoyle, Foster, Parlett) is a source of annotated hands we may want for §10.

### 3.10 Worked examples to use as test fixtures

From Britannica (Parlett), usable directly as golden tests:

**Repique.** Elder scores 7 for point, then 15, 4 and 3 for sequences, then 3
for a trio = **32**, plus **60** for repique = **92**. Note this exercises the
"winner of a category also scores his lesser combinations in it" rule twice.

*Caveat, established with our own engine:* **this is not a constructible
hand.** A point of 7 forces a seven-card suit; that suit can yield either a
quart plus a tierce (7 cards, leaving exactly 5 for the quint, which must all
lie in one other suit) or the quint itself (leaving too few cards for the quart
and tierce). The first case spans only two suits, so no rank can appear three
times and the trio is impossible. Verified by exhaustive search over all
1,360,128 twelve-card hands containing a seven-card suit. Parlett's figure is
illustrative arithmetic, so use it to test the **scoring rules**, not as a deal
fixture.

**Repique denied.** In the same hand, had younger declared a blank, the repique
would be prevented — because carte blanche comes first in the repique ordering,
so younger would have scored before elder reached 30. A precise, adversarial
test of the ordering rule in §3.6.

**Rubicon, both players short.** Britannica is explicit that the loser is
rubiconed "even if the winner also fails" to reach 100. An easy case to get
wrong by guarding on the winner's score instead of the loser's.

**A prior for the exchange policy (§6.2).** Britannica notes elder "in practice
usually exchanges five cards." A trained policy that rarely takes all five is
probably wrong, and this is a cheap sanity check on §6.2 before we spend
anything on compute.

### 3.11 The period sources

Two primary texts, read in full rather than in summary.

#### Cotton, *The Compleat Gamester* (1674) — "The Game at Picket"

This is the **36-card ancestor**, and it confirms the CMU text independently:
throw out "the Deuces, Treys, Fours and Fives," leaving "thirty and six"; the
usual set is "an hundred"; twelve cards each with **twelve** left on the table;
and elder "may take in eight of the twelve in the Stock." Trick scoring is by
high card, not by trick: "for every Ace, King, Queen, Knave, or Ten, he reckons
one." The last trick is worth 2 if won with a ten or better, otherwise 1.

Four things in Cotton bear directly on decisions we had left open.

**R1 is settled.** Cotton states the reckoning order outright, and it is the
only source that spells out where the cards bonus sits:

> "the Blanks are always first reckoned; but if no Blanks, then comes the
> Ruff, next your Sequences, then your Aces, Kings, Queens, Knaves, and Tens,
> next what Cards are reckoned in play, and **last of all the Cards you have
> won**."

The 10 for cards is reckoned *dead last*, after the play points. It therefore
cannot help you reach 30 ahead of your opponent. pagat, Parlett and Wikibooks
are right, and this is now settled rather than merely outvoted.

**R3 is settled the same way.** "Let the Game be never so good the Gamesters are
**both obliged to discard one Card at least**." pagat agrees with the oldest
source; Parlett's permissive version looks like a later relaxation.

**Pique and repique are unchanged since 1674**, including the bookkeeping. 30 in
declarations alone scores "ninety" instead of thirty (+60, repique); 30 before
the opponent has played or reckoned anything scores "sixty" instead of thirty
(+30, pique). The continental habit of *announcing 60 and 90* that we noted in
the French and German articles turns out to be the original English convention
too. Capot is 40 and cards is 10, both already fixed in 1674 — German
Wikipedia's 30 for capot is the outlier, not the survivor.

**Carte blanche blocks the opponent's pique**, exactly as Britannica's worked
example says: "He that hath a Blank, his Blank shall hinder the other Picq and
Repicq, although he hath nothing to shew but his Blank."

Cotton also supplies rules we are not implementing but which are good tutor
material, because they show what the game cared about. Declaring is
use-it-or-lose-it — a player "that sheweth not his Ruff before he play his first
Card" loses it "absolutely," which is the origin of sinking's cost. False
declaration is punished savagely: the offender is "debarred from [reckoning]
any thing he really hath" while the adversary scores everything. And there is a
genuine **disclosure obligation**: a player who discards from four aces and
declares the remaining three "is bound to tell the other, if he ask him, what
Ace, King, Queen he wants."

#### Hoyle, *A Short Treatise on the Game of Piquet* (1745)

By Hoyle the game is **already the modern 32-card version** — he computes "the
Chances of taking in any one, two, three, four, or five certain Cards," and a
five-card draw means elder's modern exchange. So the 36-to-32 transition
happened between 1674 and 1744, matching French Wikipedia's "formalised to 32
cards in the late 17th century."

Hoyle's treatise is, in substance, **§6.2 done by hand in 1744**: an analysis of
which discard maximises your chances. That makes it both a validation target and
a source of worked examples. Two specifics worth keeping:

- **An odds claim to check:** "it is but three to two against the younger-hand's
  taking one Card out of three to save a Pique, or a Repique." A concrete
  probability our engine should reproduce.
- **A maximum-score claim, now confirmed:** asked "What is the highest Number to
  be made of a Repique and Capot?", Hoyle answers **"A hundred and seventy
  points."**

**Hoyle is exactly right, and an earlier draft of this document was wrong.** We
had guessed the maximum at 153, reasoning from a hand that maximises *length* --
a point of eight, a huitieme for 18, a quatorze for 14, giving 40 in
declarations. That is the hand a human reaches for, and it is not the best one.

Sets are worth far more per card than sequences: a quatorze is 14 points for
four cards, where a huitieme is 18 for eight. And the same twelve cards count in
all three categories at once. So the best declaring hand is **ace, king and
queen in every suit**:

    point of 3                      3
    four tierces to the ace        12
    three quatorzes                42
                                   --
                                   57

Which assembles into Hoyle's figure exactly:

    declarations                   57
    repique                        60
    twelve leads                   12
    last trick                      1
    capot                          40
                                   ---
                                  170

And it is reachable in a **legal** deal, compulsory exchange included: deal
elder eleven of those cards plus one junk club, and put the twelfth on top of
the talon, so the exchange he is obliged to make fetches it. Younger, dealt
3-3-3-3 among the jacks, tens and nines, swaps within a suit to keep that shape
and so wins no category and scores nothing. `tests/test_historical_claims.py`
plays the deal through the engine and gets 170 to 0.

Two things this vindicates. Hoyle's arithmetic, obviously -- but also the
decision to build the engine before trusting our own reasoning about the game.
The 153 figure felt right and was confidently written down.

## 4. What the mathematics actually says

The user's opening hypothesis was that Piquet is a large but bounded set of
outcomes that could be precomputed into a state transition matrix. That is
**false at the whole-game level but true, and better than expected, at the
subgame level.**

### 4.1 The whole game is not tabular

Deals alone: C(32,12) x C(20,12) = **2.84e13**. Elder then has 1,585 legal
discards (sum of C(12,k) for k=1..5), and the play tree follows. Suit
symmetry divides by only 24. This is heads-up-limit-poker scale, which
required a research cluster and terabytes of storage. It is not a
pocket-money project, and no transition matrix will be built.

### 4.2 But the play phase is nearly perfect information

Count what each player actually knows when the first card is led:

- **Elder** knows his 12 cards and all 5 top talon cards — 17 identities.
  15 cards remain unknown, and younger holds 12 of them:
  **C(15,12) = 455 possible opponent hands (an upper bound).**
- **Younger** knows her 12 and what she drew — roughly 15 identities, so
  **C(17,12) = 6,188 (an upper bound).**

Then the declaration dialogue happens, and it is extraordinarily
informative: point length and value, sequence length and top card, set rank,
plus the right to inspect any combination scored. In practice the consistent
world count collapses to tens, sometimes to one.

Solving a *single* world is cheap: 12 tricks, two players, no trumps, strict
follow-suit, with equivalent-card collapsing. This is a far smaller problem
than bridge double-dummy and should run in well under a millisecond with
alpha-beta and a transposition table.

**Conclusion: the play phase can be solved essentially exactly, in real
time, on a laptop — by enumeration, not approximation.** This is the
foundation of the whole AI design, and it is a genuinely lucky property of
this particular game.

### 4.3 So the difficulty lives in two other places

- **The exchange.** 1,585 choices made blind against 20 unknown cards. This
  is the expensive computation and the only plausible use of paid compute.
- **Declaration and sinking.** The only genuinely game-theoretic decision,
  because it is a *signaling* problem. See §6.3.

## 5. Architecture

Modules in dependency order. Only `search` is performance-critical, which is
what keeps Python viable.

```
piquet/
  cards.py        ranks, suits, bitboard hand representation
  rules.py        phase state machine; legal action generation
  combos.py       point / sequence / set detection and comparison
  scoring.py      the event log, and pique/repique derivation
  observation.py  what each seat legally knows
  search.py       exact solver + world enumeration   <- the only hot code
  agents/         the capability ladder (see §7)
  explain.py      machine evaluation -> human concepts (see §8)
  train/          self-play drivers and the move log
  ui/             deferred; plug-and-play by contract
```

Britannica classifies piquet as a **trick-and-meld game**, alongside bezique,
pinochle and sixty-six. That is the right seam for the reusable-engine goal: a
trick-taking core (following suit, trick resolution, trick scoring) beneath a
separate declaration/meld layer. Keeping those two apart is what makes the next
card game cheap, so `rules.py` should not let meld logic leak into trick logic.

### 5.1 `observation` is the most important module

It defines the information sets. If it leaks, the bot cheats and every
measurement we take is meaningless; if it is too strict, the bot forgets
things the rules explicitly allow it to consult (its own discards, exposed
talon cards, combinations it may ask to see). Everything the AI does reads
through this module, never from the raw state. It is also what makes the 455
figure in §4.2 a real engineering quantity rather than a thought experiment.

### 5.2 Scoring is an ordered event log, not a tally

Every point scored is an event: `(who, amount, source, category, sequence
number)`. Repique is derived by scanning that log in *category* order;
pique by scanning it in *temporal* order (§3.6). A running integer total
cannot express both.

This structure pays for itself three times over: it makes the hardest rule
in the game testable, it gives the tutor a ready-made narrative ("you
reached 30 before she scored anything — that is a repique, +60"), and it is
already the per-decision training log the project wants for later analysis.
One structure, three purposes.

### 5.3 Evaluations are decomposed, not scalar

The solver returns a *vector* — declaration points, trick points, the cards
bonus, pique/repique — never a single number. This costs almost nothing and
buys explainability: "this discard costs you 2 points of point but gains 14
in quatorze equity" is teachable; "EV −0.3" is not. A scalar evaluation
would quietly make §8 impossible, which is why this is settled now rather
than later.

## 6. The AI plan

Three subgames, three different techniques. This division is the core
insight of the design.

### 6.1 Play phase — exact search

Enumerate the consistent opponent hands (455 or fewer for elder, 6,188 or
fewer for younger, both usually far smaller after declarations), solve each
exactly, combine. No learning, no training data, no cloud compute. It is
solved because it is small.

### 6.2 Exchange — Monte Carlo, then regression

Generate candidate discards heuristically rather than enumerating all 1,585
(keep length in the point suit, keep sequence and quatorze potential,
prefer shedding nines and below). Roll each candidate forward through the
§6.1 solver against sampled talons and opponent hands. Then fit a regression
from hand features to discard value, so the shipped game *evaluates a
function* instead of searching.

This is the only step with a meaningful compute bill, and its cost is
tunable along three axes (candidates considered, rollouts per candidate,
hands sampled). **We will agree an estimated runtime and a local-vs-cloud
decision before launching this in earnest.**

### 6.3 Declaration and sinking — CFR

Counterfactual Regret Minimization. Search is structurally incapable here:
it assumes the opponent knows everything, so it can never learn to conceal.
Sinking a quint trades 15 points for five cards' worth of secrecy, and the
correct answer is a *mixed* strategy — sink this hand some percentage of the
time — because every deterministic rule is exploitable once read.

**The action space is larger than "declare or conceal."** Cavendish's examples
of sinking are all *partial*: declaring five spades while holding six, calling a
tierce to the knave while holding a quart to the knave, calling a trio while
holding a quatorze. A player may declare **any value at or below what he
actually holds**. This materially enlarges the CFR action space and makes the
subgame considerably more interesting — under-declaring is a graded bluff, not a
binary one. Any earlier design note treating sinking as a boolean is wrong.

CFR plays itself, accumulates regret for actions not taken, plays
proportionally to positive regret, and its *average* strategy provably
converges to a Nash equilibrium in two-player zero-sum games. It is
infeasible on the full game (most information sets would never be visited)
but very feasible on the declaration dialogue alone, with the §6.1 solver
supplying the value of each resulting position.

Build this **last**. It is the most complex component and it depends on
everything else.

### 6.4 Why not an LLM

Piquet is a perfect-recall combinatorial game in which exact search is
cheap. A language model would be slower, weaker, and unexplainable. The one
legitimate use is cosmetic and optional: phrasing the tutor's explanations
in natural language. The engine decides; the model only narrates.

### 6.5 A caution about self-play

Pure self-play converges on strategies that beat *the agent's own lineage*
and can be badly exploitable by an unseen human style. We will therefore
maintain a **diverse opponent pool** — every rung of the §7 ladder, plus
deliberately flawed agents — rather than training only against the current
best. This also gives us the honest Elo measurement we need.

## 7. Skill as a capability ladder, not a noise dial

The obvious way to build a weak opponent is to give the strong one less
search and more randomness. That produces a bot that is weak but *alien*:
it blunders uniformly, in ways no human ever would.

Instead, each skill level **adds a named capability** — and each capability
is a concept a human player has to learn:

| Level | Capability gained |
|---|---|
| 1 | Follows suit legally; plays its highest card |
| 2 | Basic discard heuristics; keeps its longest suit |
| 3 | Remembers which cards have been played |
| 4 | Holds stop cards (guards in the opponent's long suit) |
| 5 | Infers the opponent's shape from the declaration dialogue |
| 6 | Plays the exchange from the trained §6.2 policy |
| 7 | Full exact solver in the play phase |
| 8 | Plays for pique/repique and the rubicon threshold |
| 9 | Mixed declaration strategy from §6.3 — sinks correctly |

This unifies the opponent and the tutor: the ladder *is* the curriculum, and
the game can tell the player what changed ("level 5 opponents will use your
declarations against you"). It also makes the opponent's weaknesses
human-shaped, so beating a level-4 bot teaches something real.

Cavendish supports this directly: his treatise contains a section titled *Habit
of Adversary*, and his worked example of detecting a sink begins "your adversary
is a player who rarely discards from his point." Modelling the opponent as a
*person with habits* is how the game's own authority taught it, not a modern
imposition — which is good warrant for both the ladder and the control below.

**Erraticism** is then a separate, orthogonal control: the effective level
is drawn *per decision* from a distribution centred on the slider, with
width set by the erratic control. Real players are inconsistent, not
uniformly bad, so this reads as far more human than epsilon-greedy noise.

### 7.1 Style: a third axis, orthogonal to both

Skill and erraticism are not enough to describe an opponent. There is a third
thing, and it is genuinely separate rather than a rewording of the other two:

- **Skill** is what the agent is *capable* of -- the ladder above.
- **Erraticism** is how *consistently* it brings that capability to bear.
- **Style** is which option it prefers among choices of roughly *equal value*.

That last clause is load-bearing. **A style must be close to EV-neutral.** If a
"style" reliably loses points it is not a style, it is a lower skill level
wearing a hat, and the two controls have smeared into each other. This is
checkable rather than a matter of taste: the Elo round-robin should show two
styles at the same rung scoring within noise of each other, and if it does not,
the style parameter is miscalibrated and must be pulled back towards neutral.

The historical sources hand us the dimensions, so we are not inventing
personality traits:

| Dimension | The judgement it varies |
|---|---|
| **Discard boldness** | How readily it wrecks its point chasing a quint. The oldest strategic question in the game -- Hoyle wrote a whole 1744 treatise on it |
| **Sinking frequency** | How often it conceals. Cavendish's central manoeuvre, with a wide band of defensible answers |
| **Guard retention** | Whether it hoards stop cards in your long suit or plays for length |
| **Rubicon nerve** | How much it gambles when trailing late in a partie, where failing to reach 100 is punished far worse than losing narrowly |

**The style vector must be stable.** Draw it once per opponent, at the start of
a partie, and hold it fixed for the whole match. A style that re-rolls every
decision is just noise, and noise is what the erraticism control already
supplies.

Stability is the entire pedagogical payoff, and it comes straight from
Cavendish. His worked example of spotting a sink opens: *"Your adversary, for
instance, is a player who rarely discards from his point."* That inference only
works if the adversary **has** a persistent habit. A randomly-styled but stable
opponent lets a human build a read across six deals and then exploit it, which
is precisely the skill Cavendish was teaching and which a single "correct" bot
would never develop.

Two things come free. It populates the diverse opponent pool of section 6.5 --
a spread of style vectors is a cheap, principled alternative to a self-play
monoculture. And it is a *tutor* feature as much as an opponent feature: the
game can eventually say "this opponent has sunk three declarations in four
deals; assume they are concealing," teaching the hardest skill in piquet with
machinery built for other reasons.

Cost is low -- a handful of parameters biasing decisions the agent already
makes, with no extra search and no extra training. It belongs in **milestone 4**,
alongside the heuristic agents, because that is the first point at which the
decision points exist to bias. One caveat: style only becomes meaningful at
rungs that have real choices to make. A level-1 agent that plays its highest
card has no room for personality; styles should start to read as distinct
around rungs 4 to 5 and grow richer up the ladder.

## 8. Training mode falls out of the engine

Because the §6.1 solver already produces a decomposed evaluation for *every*
legal action, the interactive tutor is largely a rendering problem over data
we already have:

- **Impossible moves** come straight from `rules.legal_actions` — free.
- **Bad moves** are ranked by evaluation loss and bucketed (sound / dubious
  / blunder).
- **Why** comes from the §5.3 decomposition and the §5.2 event log.

Two things the tutor must do that the engine does not do by itself:

1. **Close the temporal gap.** The consequence of an exchange decision lands
   twenty moves later. Humans cannot perform that credit assignment;
   machines can. The tutor must therefore show the consequence *immediately*
   — "this discard will cost you the point" — rather than at end of hand.
2. **Speak in concepts, not numbers.** See §9.

The declaration phase deserves the most tutorial attention. It is where
beginners are destroyed, it is nearly impossible to learn from a rules page,
and no existing resource teaches sinking well.

## 9. How humans learn card games, and how machines do not

This section exists because a strong bot is **not** automatically a good
teacher, and the difference has to be designed for rather than discovered
late.

**Humans** learn through *named patterns* — and Piquet hands us an unusually
rich vocabulary already: quint, quatorze, repique, capot, sinking, stop
cards. The vocabulary is the curriculum. Humans need *immediate* feedback,
because they cannot assign credit across a twenty-move gap. They learn from
losing in memorable, specific ways. They need *progressive disclosure*:
point before sequences before sinking. They reason about the opponent's
*mind*. And they retain rough heuristics with reasons attached — "throw your
nines even if it wrecks your point, because point is the cheapest category"
is memorable in a way that a coefficient never is.

**Machines** need none of that. They learn in arbitrary order, never forget,
assign credit across long horizons via value functions and regret, and
arrive at policies that are correct and completely inarticulate. A CFR
solution that says "sink 23% of the time" is *right*, and pedagogically
useless on its own.

The design consequences, each already committed to above:

- The **capability ladder** (§7) is a machine implementation of a human
  curriculum — that is why skill is not a noise dial.
- The **event log** (§5.2) and **decomposed evaluation** (§5.3) exist so the
  tutor can say *why*, not just *how much*.
- The **diverse opponent pool** (§6.5) exists because a human is an unseen
  style, and pure self-play is fragile against those.
- The tutor **closes the temporal gap** (§8) because that is the specific
  thing human learning cannot do and our engine can.

### 9.1 The human has to enjoy this

The project's stated goal is not a correct simulator or a strong bot; it is
that **a person and a computer play a good game together**. An opponent that
is strong but joyless has failed, and so has a tutor that is accurate but
tedious. Concretely, this constrains several choices already made:

- The **capability ladder** (§7) matters partly because losing to an opponent
  whose weakness is *comprehensible* is fun, and losing to one that blunders
  randomly is not. You can form a theory of a level-4 opponent. You cannot form
  a theory of noise.
- **Erraticism exists to make the opponent feel alive**, not to tune its
  strength. A player who is occasionally brilliant and occasionally sloppy is a
  better companion than one that is uniformly mediocre.
- The tutor should **explain, not scold**. Parlett puts the central tension of
  the game in one sentence worth quoting to the player directly: *"The point of
  making a declaration is that you thereby score points in return for giving
  away information about your hand."* That is the whole game, and it is more
  useful than any number we could print.
- Piquet's vocabulary is half its charm — quint, quatorze, repique, capot,
  sinking. **Use the real terms**, and teach them, rather than flattening them
  into "four of a kind". The game is 500 years old and that should be part of
  the pleasure of playing it.

Where correctness and enjoyment genuinely trade off, that is a decision to
raise rather than resolve silently in favour of the machine-facing metric.

## 10. Testing strategy

TDD throughout, but three kinds of test deserve naming:

1. **Unit tests** on combination detection, comparison, and the scoring
   event log. Pique and repique get adversarial treatment — that is the
   likeliest place for a subtle permanent bug.
2. **Constructed deals.** A text format for specifying an exact deal, so any
   rules edge case can be written as a fixture. Needed for TDD anyway; also
   lets us encode annotated hands from the historical literature (Cavendish,
   Hoyle, Foster, Parlett).
3. **Statistical invariants** over many random deals — the sort of test that
   catches errors unit tests cannot:
   - carte blanche occurs in 1 hand in ~1,792, and so in 1 deal in ~896
   - both players never hold carte blanche
   - elder wins materially more than younger (dealing is a disadvantage)
   - every deal's points reconcile against the event log
   - the maximum possible score for a single deal, played through the engine,
     reproducing Hoyle's 1744 claim of 170 exactly (§3.11)
   - Hoyle's odds claim that it is "three to two against" younger drawing one
     needed card out of three

Golden JSON vectors are emitted from the suite from the first milestone, to
validate any future port.

## 11. Milestones

1. **Cards and combinations.** Representation, plus point/sequence/set
   detection and comparison. Pure functions, heavily tested.
2. **Rules engine and the event log.** The full phase machine including the
   carte blanche ordering quirk and the category-by-category declaration
   dialogue. Scoring derived from the log; pique and repique correct.
3. **Random agent plays 10,000 legal games** without crashing, with the
   statistical invariants of §10 passing and the move log written from the
   very first game — not retrofitted.
4. **Heuristic agents**, ladder levels 1–5. A round-robin Elo harness.
5. **Exact play solver** (§6.1) and world enumeration. Ladder level 7.
   Verify the 455 bound empirically.
6. **A playable game** with a basic UI and the skill and erratic controls.
7. **Exchange policy** (§6.2). *Runtime and cost agreed before launching.*
8. **Training mode** (§8).
9. **CFR declarations** (§6.3). Ladder level 9.

## 12. Deferred

- Card art (assets already sourced by the user).
- JavaScript/TypeScript port for browser embedding.
- Piquet au Cent (36-card pack, different game).
- Three- and four-player variants.
