# Piquet — Literature Review

Twenty sources, nine of them period texts read in full from Internet Archive
OCR. **pagat.com is our rule authority**; the period record vindicates it on
every contested point.

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
The odds claim remains to be checked.

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
