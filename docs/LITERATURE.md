# Piquet — Literature Review

Twenty sources on the game, nine of them period texts read in full from
Internet Archive OCR, plus the mathematics the engine is built on.
**pagat.com is our rule authority**; the period record vindicates it on every
contested point.

Two bibliographies, because there are two questions. What the game *is* —
Cotton, Hoyle, Cavendish, pagat. And how it is *measured and searched* —
Laplace, Zermelo, Bradley and Terry. The second half lived only in docstrings
and commit messages until it was written down here, which is the wrong place
for anyone arriving cold.

## What the reading settled

| Question | Verdict | Authority |
|---|---|---|
| Does the 10 for *cards* count toward a pique? | **No** | Cavendish, Laws 66–69 |
| Must younger discard at least one card? | **Yes** in Rubicon Piquet; no in Piquet au Cent — the conflict was two different games | Cavendish, Law 22 |
| Last trick value | **2 to its winner** | Cavendish, Law 65 |
| Carte rouge | Not in the English club game | Absent from Cavendish |
| Is sinking binary? | **No — you may under-declare** | Cavendish, pp. 156–158 |

## Period sources

**Cotton, *The Compleat Gamester* (1674).** Earliest full English rules. The
36-card ancestor: twelve-card stock, elder takes in up to eight, set at 100,
tricks scored by high card rather than by trick. Contributes the reckoning
order — "the Blanks are always first reckoned… and **last of all the Cards you
have won**" — which is Cavendish's order two centuries early and settles R1. Also
states both players must discard at least one (settling R3), gives pique and
repique their modern values, and establishes that declaring is use-it-or-lose-it,
which is the origin of sinking's cost.

**Hoyle, *A Short Treatise on the Game of Piquet* (1744/45).** The game is
already 32 cards, dating the transition to between 1674 and 1744. The treatise is
our exchange-policy problem done by hand: it computes the odds of drawing given
cards. Two checkable claims — that it is "three to two against the younger-hand's
taking one Card out of three to save a Pique", and that the maximum from "a
Repique and Capot" is **170 points**.

The maximum is now **confirmed**, and the exercise corrected us rather than him.
Our first reading made it 153, reasoning from a hand that maximises *length*. The
best hand maximises *sets*: a quatorze is 14 points for four cards where a
huitième is 18 for eight, and the same twelve cards count in all three categories
at once. Ace, king and queen in every suit declares 57 — a point of 3, four
tierces, three quatorzes — and the engine plays the deal out to exactly 170.

**The odds claim is now confirmed too**, and it pins down his method as well as
his answer. See "The mathematics" below.

**Cavendish [Henry Jones], *The Laws of Piquet adopted by the Portland and Turf
Clubs* (1892/1896).** The most valuable source found, and the direct ancestor of
every modern description — Parlett names Cavendish as his authority. Numbered
laws plus a strategic treatise.

- *Law 67* fixes the reckoning order: carte blanche, point, sequences, quatorzes
  and trios, points made in play, **the cards**.
- *Law 69* settles R1 outright: "A capot reckons after points made in play; and,
  therefore, does not count toward a pique." Law 66 makes capot and the ten for
  cards the same score, so neither can contribute.
- *Laws 21–22* require both players to discard — while the same volume's *Laws of
  Piquet au Cent* says younger need not. Sources claiming younger may stand pat
  have imported the au cent rule.
- *Law 65* gives the last trick as 2 to its winner.
- *Sinking*, pp. 156–158, is the key strategic passage. See PIQUET.md.

**Others.** *Le Second ieu du picquet de la cour* (1649) evidences a French
literature a generation before the English. Seymour's *Court-Gamester* (1722),
Hoyle's collected editions (1748–1790), Chateauneuf's bilingual *New Treatise*
(1770) and Bohn's *Hand-Book of Games* (1850) are largely reissues or
compilations — useful as evidence of how stable the rules stayed, not as
independent testimony.

## Modern sources

**pagat.com** — our authority, vindicated throughout. **Parlett** (his own site,
and the Britannica entry he wrote) is the best modern secondary source, though
his permissive discard rule looks like the au cent rule. **Wikibooks** is
unusually precise on edge cases. **English Wikipedia** is good but conflates
variants, and is wrong on R1. The **French and German** articles describe
genuinely divergent continental games and are the best source of terminology.
**cardgameheaven** is adequate. **whiteknucklecards** mixes eras rather than
inventing rules — its odd trick scoring is authentically Cotton's 1674 rule, and
an earlier draft of our design wrongly called it unreliable.

## The mathematics

Several of these are load-bearing rather than decorative, and one of them
killed an approach before it was built.

**Montmort, *Essay d'analyse sur les jeux de hazard*, 2nd edition (1713).**
Part V is the correspondence between Montmort and Nicolaus Bernoulli, and it
carries **Charles Waldegrave's** solution to *Le Her*, a two-player card game
of imperfect information. It is the **first mixed strategy ever written down** —
two hundred and fifteen years before von Neumann's minimax theorem of 1928.

Not a curiosity for us. Le Her's solution is mixed because a pure rule is
exploitable the moment the opponent knows it, and **sinking has exactly that
shape**: a player who always conceals a tierce is read, and so is one who never
does. That is the historical reason to expect §6.3's answer to be a mixed
strategy rather than a rule of thumb, and the reason `style.sinking` is a
probability and not a flag. Bellhouse and Fillion established which Waldegrave
it was — Charles, an active Jacobite, rather than his nephew James the
diplomat: *Statistical Science* 30:1 (2015), [doi:10.1214/14-STS469](https://projecteuclid.org/journals/statistical-science/volume-30/issue-1/Le-Her-and-Other-Problems-in-Probability-Discussed-by-Bernoulli/10.1214/14-STS469.full).

**Laplace, *Mémoire sur la probabilité des causes par les événements* (1774);
the sunrise example is in the *Essai philosophique sur les probabilités*
(1814).** The rule of succession: having seen *n* successes and no failures,
the next trial succeeds with probability (n+1)/(n+2) rather than 1.

This is `tournament.ratings`' prior, and Laplace's question is exactly ours. An
agent that has won nothing has a maximum-likelihood strength of zero and a
rating of minus infinity — and a shutout is precisely the result the harness
exists to produce. Half a win and half a loss against a virtual opponent of
average strength is the same answer Laplace gave the sunrise.

**Zermelo, "Die Berechnung der Turnier-Ergebnisse als ein Maximumproblem der
Wahrscheinlichkeitsrechnung", *Mathematische Zeitschrift* 29 (1929), 436–460,
[doi:10.1007/BF01180541](https://link.springer.com/content/pdf/10.1007/BF01180541.pdf).**
The model `tournament.ratings` fits, invented to rank **chess** players from
tournament results — our problem exactly, twenty-three years before it acquired
the name it goes by.

**Bradley and Terry, "Rank Analysis of Incomplete Block Designs: I. The Method
of Paired Comparisons", *Biometrika* 39:3–4 (1952), 324–345,
[jstor:2334029](https://www.jstor.org/stable/2334029).** The rediscovery the
model is named after.

**Hunter, "MM algorithms for generalized Bradley–Terry models", *Annals of
Statistics* 32:1 (2004), 384–406,
[doi:10.1214/aos/1079120141](https://projecteuclid.org/journals/annals-of-statistics/volume-32/issue-1/MM-algorithms-for-generalized-Bradley-Terry-models/10.1214/aos/1079120141.full).**
The minorisation–maximisation fit `tournament.ratings` uses, and the reason it
is order-independent where sequential Elo updates are not.

**Smith and Winkler, "The Optimizer's Curse: Skepticism and Postdecision
Surprise in Decision Analysis", *Management Science* 52:3 (2006), 311–322,
[doi:10.1287/mnsc.1050.0451](https://pubsonline.informs.org/doi/10.1287/mnsc.1050.0451).**
Pick the best of several noisy estimates and the winner's estimate is biased
upward, even though every estimate was individually unbiased.

Not background reading: this is what killed the obvious approach to milestone
8. A rollout policy choosing the best of twelve candidate discards *believed*
it was gaining six points a deal and was measured gaining 0.3. The paper is
also the argument for §6.2's "**then** fit a regression" — an argmax amplifies
the noise and a regression pools it away.

**Frank and Basin, "Search in games with incomplete information: a case study
using Bridge card play", *Artificial Intelligence* 100:1–2 (1998), 87–123,
[doi:10.1016/S0004-3702(97)00082-9](https://www.sciencedirect.com/science/article/pii/S0004370297000829).**
Names the two defects of precisely what `solver.SolverAgent` does — sample the
opponent's hand, solve each world double-dummy, average the results.
**Strategy fusion**: the average quietly assumes you may play differently in
worlds you cannot tell apart. **Non-locality**: it assumes the opponent sees
through the table too, so it will never set a trap that depends on their
ignorance. Both are documented in the module. Neither is fixed.

**Zinkevich, Johanson, Bowling and Piccione, "Regret Minimization in Games with
Incomplete Information", *NIPS 20* (2007),
[proceedings](https://papers.nips.cc/paper/3306-regret-minimization-in-games-with-incomplete-information).**
Counterfactual regret minimisation, the method §6.3 earmarks for the
declaration and sinking policy — and the modern answer to the question
Waldegrave posed in 1713.

**Common random numbers.** `chances.point_weights` differences two Monte Carlo
estimates taken over the *same* draws, which makes the difference nearly exact
rather than two noisy numbers subtracted. A standard simulation technique
rather than a citable result; Law and Kelton, *Simulation Modeling and
Analysis*, is the usual reference.

**And Hoyle again.** The 1744 treatise listed above belongs in this section
too. "Three to two against the younger-hand's taking one Card out of three to
save a Pique" is a hypergeometric tail — 1 − C(17,3)/C(20,3) = 23/57, or 1.478
to 1 — computed by hand a century and a half before the distribution had that
name, and right. Four readings of the sentence are arithmetically possible and
only one lands on his answer, so it pins down his method as well as his result.

## Where each source is used

| Module | What it rests on | Source |
|---|---|---|
| `combos`, `declarations` | scoring and comparison of the three categories | Cavendish, Laws 60–64 |
| `scoring` | reckoning order; pique and repique | Cavendish, Laws 66–69 |
| `rules` | both players must discard; last trick is 2 | Cotton 1674; Cavendish, Laws 21–22, 65 |
| `partie` | six deals, alternating deal, rubicon settlement | pagat |
| `observation` | what is said aloud, and when | Cavendish; pagat |
| `chances` | hypergeometric odds; differencing over common random numbers | Hoyle 1744; Law and Kelton |
| `tournament` | Bradley–Terry by MM, with a Laplace prior | Zermelo 1929; Bradley and Terry 1952; Hunter 2004; Laplace 1774 |
| `solver` | perfect-information Monte Carlo, and its two known defects | Frank and Basin 1998 |
| `style` | sinking as a probability rather than a rule | Cavendish pp. 156–158; Waldegrave via Montmort 1713 |
| *planned* — declaration policy | counterfactual regret minimisation | Zinkevich et al. 2007 |
| *rejected* — argmax over rollouts | the optimizer's curse | Smith and Winkler 2006 |

## Archive identifiers

| Year | Work | Identifier |
|---|---|---|
| 1649 | *Le Second ieu du picquet de la cour* | `lesecondievdvpic00unse` |
| 1674 | Cotton, *The Compleat Gamester* | `bim_early-english-books-1641-1700_the-compleat-gamester-_cotton-charles_1674` |
| 1722 | Seymour, *The Court-Gamester* | `courtgamesterorf00seym` |
| 1744 | Hoyle, *A Short Treatise on the Game of Piquet* | `bim_eighteenth-century_a-short-treatise-on-the-_hoyle-edmond_1744` |
| 1748 | Hoyle, *The Accurate Gamester's Companion* | `bim_eighteenth-century_the-accurate-gamesters-_hoyle-edmond_1748` |
| 1763 | *Mr. Hoyle's Games of Whist, Quadrille, Piquet…* | `bim_eighteenth-century_mr-hoyles-games-of-whi_hoyle-edmond_1763` |
| 1770 | Chateauneuf, *A New Treatise on Piquet* | `bim_eighteenth-century_a-new-treatise-on-piquet_chateauneuf-mr-de_1770` |
| 1790 | *Hoyle's Games Improved* | `bim_eighteenth-century_hoyles-games-improved-_hoyle-edmond_1790` |
| 1807 | *Games of Whist, Quadrille, Piquet, Quinze, Vingt-un* | `10431612bsb` |
| 1850 | Bohn, *The Hand-Book of Games* | `handbookofgamesc00bohn` |
| 1892 | Cavendish, *The Laws of Piquet* | `lawsofpiquetadop00cavendi` |
| 1896 | Cavendish, *The Laws of Piquet*, later printing | `lawsofpiquetadop00cave` |

Modern: pagat.com · parlettgames.uk · britannica.com · en.wikibooks.org ·
en/fr/de.wikipedia.org · cardgameheaven.com · whiteknucklecards.com ·
contrib.andrew.cmu.edu
