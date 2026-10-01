# Piquet — Project Plan

> Working notes: where the project stands and what is left. `docs/DESIGN.md`
> holds the *reasoning*, `docs/PIQUET.md` the *game*, `docs/LITERATURE.md` the
> *sources*, `docs/TABLE3D.md` the *3D table*. Kept current as work lands, so
> that a new session resumes from here rather than re-deriving it. Last
> updated 1 October 2026, when the repository was made public.

## Where we are

**Milestones 1–7 complete, and the Rust port with them.** The Python oracle
suite is green; the Rust suite has 206 tests, and the 3D table's pure modules
are node-tested.

**It is playable in a browser, and public.** `web3d/piquet3d.html` is the
whole game in one ~3 MB file: the engine compiled to WebAssembly and inlined,
drawn with three.js as cel-shaded cards with ink outlines, with Material
Design 3 controls, a running score tab, hints, explanations, undo, a
tutorial, the declarations as dialogue boxes, and an end-of-partie
celebration. Open it from disk; no server, no network. Since 1 October 2026
GitHub Pages serves it too (see "Publishing"). `docs/TABLE3D.md` is its
design and record, phases P0–P21. Settings → *Copy game record* gives a seed
and command list that replays any game exactly. Rebuild with
`python3 web3d/build.py`.

**And in a terminal.** `cargo run -p piquet-cli -- --level 3` sits you down
against your opponent for a partie of six deals, cutting for the deal and
settling by the rubicon -- a client of the same session (`table.rs`) as the
browser's page. Four measured rungs plus the exact-endgame solver, with
styles and erraticism, and a mirrored-pair tournament that rates them.

**The GUI is disposable by design.** The user: "don't get too attached to the
gui — we might move to 3d. but i'm interested in the game states, engine,
etc being done." So the investment is in `table.rs` (the session, advanced
one human decision at a time) and `docs/PROTOCOL.md` (the JSON a client
renders); the page holds no rules at all.

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
  prior.rs         the fitted world prior (conditional logit)
  solver.rs        exact endgame search, and the agent that uses it
  play.rs          running deals and parties; the move log
  table.rs         a partie as a session: Prompt / Action / Event, for any client
  options.rs       what a player may declare in a category (full, sink, short)
  opponents.rs     the internal roster, rung by rung, and seating one
  tournament.rs    mirrored-pair duels, Bradley-Terry ratings
  mt19937.rs       CPython's generator, for the one fixed-seed model constant
  rng.rs           the agents' own generator
crates/piquet-cli/src/
  main.rs          the table a person sits at; the human as an Agent
  render.rs        drawing a hand in the language the prompt accepts
crates/piquet-wasm/src/
  lib.rs           the table as a protocol: JSON out, one-line commands in
web3d/
  src/             the 3D table: scene, choreography, overlay, tutorial, celebrations -- no rules
  build.py         bundles and inlines everything into web3d/piquet3d.html
  piquet3d.html    the built, playable, single-file game (committed; GitHub Pages serves it)
  test/            node tests for the pure modules; browser.py plays a partie in Chromium
  tools/           the card art, the dialogue's phrases, the colour scheme
python/            the oracle: the original, which generates the vectors
vectors/           golden JSON, read by both languages
docs/PROTOCOL.md   the contract a replacement client is written against
```

**The parity gate is met.** Both halves of it:

- Every golden vector reproduces in Rust — fourteen modules, from the pack
  through the solver, including three complete deals replayed transition by
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

## Publishing (1 October 2026)

- **The repository is public** (`github.com/abartnof/piquet`), and **GitHub
  Pages serves `main`'s root**: `index.html` forwards to
  `web3d/piquet3d.html`, keeping any query (`?ending`, a seed), and
  `.nojekyll` serves the tree as plain files. Checked over HTTP from the
  repository root in Chromium: it lands on the game, no request leaves the
  site, no console errors.
- **Every commit that rebuilds `web3d/piquet3d.html` goes live** on the
  public site within minutes. Commit a rebuilt page only once it has passed
  the gate (Rust, node, and the browser test); source changes alone change
  nothing players see.
- The README was rewritten short: where to learn the game, how this one
  works, and whom we thank.
- A stray committed `web3d/piquet3d-svg.html` (a stale 3.3 MB comparison
  build) was removed and is now git-ignored; `build.py --art svg` still makes
  it.
- **The spoken voice was removed entirely**: the recordings, the Piper
  tooling, `docs/VOICE.md`, `docs/UTTERANCES.tsv`, and the voice settings.
  The dialogue boxes keep their varied wording, now from
  `web3d/tools/phrases.py` and `web3d/src/dialogue.js`.
- **The 2D page (`web/`) was retired.** The 3D table replaced it; it stays in
  git history (last built at `a5f2e34`). It took with it `web/test/ffi.mjs`,
  a manual check that the native and WebAssembly engines agree byte for
  byte. That check is now automatic: `crates/piquet-wasm/tests/dull-parties.txt`
  records fifteen scripted parties (levels 1–5, seeds 1–3, a hash of each
  final state), and both `cargo test` (native) and `web3d/test/wasm.test.js`
  (the page's wasm) must reproduce it. `PIQUET_BLESS=1 cargo test` rewrites
  it after a deliberate change of behaviour.
- These notes were rewritten as project notes.

## Where the work happens

**All development is on Google Cloud.** Nothing is built, tested or measured on
a laptop, and there is no Rust toolchain on one.

| | |
|---|---|
| Project / zone | `abartnof-piquet`, `us-west1-b` |
| Instance | `piquet-dev`, e2-standard-2 (2 vCPU, 8 GB), Debian 12 |
| Disk | 50 GB, `autoDelete: False` — it survives the instance being deleted |
| Toolchain | Rust 1.98.1 with clippy, rustfmt, rust-analyzer; Python 3.11.2, pytest 9.1.1; Node 18 |

**Development happens *on* the VM, not through it.** `~/piquet` there is a
real git clone tracking `origin/main`, with Claude Code installed, so the two
checkouts are joined by GitHub rather than by rsync. `docs/VM.md` is the whole
story: starting it, getting in, and the one foot-gun the change introduces.

`bin/vm` remains useful for `--up`, `--down` and `--status`. Its other modes
rsync the laptop's tree over the VM's with `--delete` and will destroy
unpushed work there; do not use them while working on the VM.

On the VM itself, `cargo` is not on the PATH until `source ~/.cargo/env`. The
whole gate — `cargo fmt --check`, `cargo clippy --all-targets --release -- -D
warnings`, `cargo test --release` — takes about **3½ minutes** on the
two-core machine, most of it compiling; the tests themselves are one minute,
and one statistical binary is nearly all of that. Playwright lives in the
project `.venv`; Node 18 and Chromium come from apt, as do npm and
`librsvg2-bin` (`sudo` works).

**Stopping from inside works.** `sudo shutdown -h` on the VM reaches
`TERMINATED` cleanly (the boot log shows a clean halt), which matters
because the VM's service account cannot stop it through gcloud.

**The gcloud CLI on the VM cannot see billing.** It runs as the instance's
default service account, whose scopes cover neither `gcloud billing` nor
`gcloud compute instances list`. The per-session spend check needs either
`gcloud auth login` on the VM (an interactive terminal) or a look at the
Console (<https://console.cloud.google.com/billing>).

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
spend is **checked at the start of each working session**, at the user's
request, as an early warning rather than a backstop.

Anything materially above the figures above means something is running that
should not be, and it is almost always an instance nobody stopped:

    bin/vm --status        # is it up, and what is it costing
    bin/vm --down          # stop it

## Working conventions

- **Test-driven**: tests first, throughout.
- **Atomic commits straight to `main`, often**; `PLAN.md` updated as each
  piece of work lands; `set -e` on multi-step shell commands.
- **One self-contained HTML page**, working offline, **modest in size** (5 MB
  is a guideline, not a hard limit; weigh size against what it buys).
- **Material Design 3** for the controls, bundled — no CDNs, no fonts or
  icons fetched at runtime.
- **"Your opponent", never a proper name**, in anything a player reads.
- **Every aid a toggle.**
- The look: *clean, bright, a bit cartoonish, not childish — freed of grubby
  cards on dirty furniture.*
- **The page makes no sound.**
- **Every third-party asset credited in `CREDITS.md`** in the commit that
  brings it in (design systems such as MD3 included).
- **Consult the user before anything that spends money**, and before any long
  compute run, with a runtime and cost estimate in hand.

A new session should read, in this order: this file; `docs/TABLE3D.md`
(§13 is the phase record); `docs/PROTOCOL.md`; `CREDITS.md`.

## Open for the user

In rough order:

1. **TODO 1: make settling (with the prior) the level-5 default?** Measured a
   real and modest gain on whole parties. It is also the question of whether
   to use the prior — fitted to rung 4's discards — against a person at all.
2. **An unvalidated lead:** the opponent as younger always exchanges the most
   it may (7 cards when elder took 1). pagat: *"For younger hand it is more
   frequently correct not to take the maximum, but still rare."* Against an
   elder who takes five (the norm) that is three, and fine; whether
   always-the-maximum costs points is unmeasured. Milestone 8's ground.
3. **Should *declare for me* default on?** It removes the single biggest
   source of clicks (three a deal), but the dialogue is the heart of the
   game. Off today.
4. **Only a real device can answer:** the art's load time
   (`piquet3d.art().readyMs` in the console) and the frame rate on a real GPU.
   The VM emulates one, so every timing in `docs/TABLE3D.md` is a worst case.
5. Smaller: shadows are faint only where cards slide flat on the table —
   lifting slides higher would fix it; an idle sway was not built because it
   would mean rendering every frame forever (it could be an opt-in "living
   table" setting).

## Log

Newest first. Each entry records what landed and what it found; the phase
record for the 3D table is `docs/TABLE3D.md` §13.

### 30 September – 1 October 2026: celebrations, tutorial timing, TODO 1 on whole parties

- **All seven celebrations** (TABLE3D P21), translated from the user's
  prototype into the table's norms (no sound, the normal look and card art,
  real gravity): Plate smash, Card pong, Cup and ball, Disco, The parade,
  Macarena, Card people. In a real partie one comes at random when it ends,
  whoever won, with no arrows; **`web3d/piquet3d.html?ending`** stages them —
  play one card, and all seven are one ‹ › away. The user's notes applied as
  they came: the finale's cards "explode over the screen and then go away";
  "Piquet!" clear of its star, and the only word any burst says; pong's
  paddles clean (flat cards rest 0.02 cm above the table, as in play). The
  prototype is in git at `272ff15`.
- **The tutorial**: pages at each phase's very start (the table held behind
  them), one button arrangement on every page, pages pop up even if paged
  to. **The welcome** lost its tagline. **Shadows** measured present at every
  moment (faint only where cards slide flat).
- **TODO 1 measured on whole parties** — see TODO 1.
- **Decided under delegated judgement** (the user: "i'll follow your
  judgement"), each easy to reverse:
  1. **Landscape: the long explanation moves to the left column** (a "What
     it means" card under the score), so only the question and the answers
     sit under the hand — the user's own rule, "long explanations ... on the
     left side, and shorthand on the bottom". A phone keeps it under the
     hand. (Measured before: at 1280 x 800 with Explain on, the controls
     stood 188–269 px tall where the staging test assumed 112, so the prompt
     covered the lower half of the fan while exchanging or declaring.)
  2. **Phone: Explain and Hints stay in Settings.** The one row under a
     phone's hand holds the sort and undo; per-partie choices belong in
     Settings (keep the play screen quiet).
  3. **Phone celebrations:** the field widens in portrait; pong's court runs
     up the screen; the bar gives touch words.
  4. **Faster reload at level 5: not done, on purpose** — see "Aids" below.

### 30 September 2026: the user's tutorial text; the engine checked against pagat

The user wrote the tutorial's four pages and asked that they be *"identical
to how this videogame works"*, and that the engine be checked against pagat
once more first. Done in that order.

**The engine against pagat, clause by clause** (pagat's page as fetched
30 September, last updated 1 September 2026). Everything agrees -- pack,
cut, deal, exchange limits, younger's obligatory card, discards consulted,
the declarations and their ties, showing, younger declaring after elder's
lead, repique in category order, trick scoring, cards and capot, the
rubicon, and the two extra deals then a draw (pagat's worked settlements
are now tests, `57f8375`) -- **except**:

1. **Pique's reckoning order -- decided: Cavendish, no switch** (R8 in
   `docs/DESIGN.md` §3.7; §3.6 and §5.2 now describe the code). pagat: *"For
   pique the scores are counted in the order they actually occur."* The
   engine counts it in Cavendish's Law 67 category order, as it does
   repique, so younger's won point (entered after elder's lead, but category
   II) blocks elder's pique. pagat's own repique example -- elder 30 in
   sequences and sets, younger the better point -- denies only the repique,
   so on pagat elder has a pique there. **Measured: the readings disagree in
   127 of 20,000 rung-4 deals (1 in 160), 30 points each.** The engine had
   changed on 22 September (`6899b0e`, a code review calling pagat's reading
   a bug) with no flag and no R-row, leaving design and code disagreeing.
   **Cavendish, read verbatim** (*Laws of Piquet*, 1885, archive.org
   `lawsofpiquetadop00caveuoft`), sides with the engine. Law 67: "The
   scores, whether obtained by the elder or younger hand, reckon in the
   following order: I. Carte blanche. II. Point. III. Sequences. IV.
   Quatorzes and trios. V. Points made in play. VI. The cards." Law 69: "A
   pique is obtained on the score of thirty being made by the elder hand, in
   hand and play, before his adversary has reckoned anything that deal." So
   pagat, which gives its rules as "those published by Cavendish in 1882",
   departs from Cavendish on exactly this point. The user, taking the
   recommendation: *"we don't need extra switches, just pick a scoring rule
   and we'll use that."* The tutorial says "points count in round order".
2. **The page never told elder the talon cards they left -- fixed
   (`6e95309`, `772ccff`).** The engine knew (`talon_seen`,
   `watched_them_take`) and the opponent used it. The first proposal, a
   peek at the talon, was measured before it was built: **in all 144 deals
   (levels 1-4) where elder left cards, the opponent as younger drew every
   one**, in the same step as elder's exchange, so they are almost never
   still there to look at. What the rule gives is knowing which they were and
   where they went: two protocol events, `looked` and `they_took`, in the
   game log, and the point's explanation names them ("You left J♠ 8♦; your
   opponent drew them"). This also surfaced the exchange lead in "Open for
   the user".
3. Known and small: younger's option to expose her untaken cards (TODO 10)
   and carte blanche's choreography (TODO 11) are not modelled; the table
   offers the full call, nothing, or one card short, where the engine (and
   pagat) accept any smaller holding.

**The licence** is **MIT, © 2026 Andrew Bartnof** (`LICENSE`, the crates,
web3d's package, the page's Credits).

**The tutorial (TABLE3D P20).** `web3d/tutorial.md` holds the four pages,
the user's words with these corrections, each to what the engine does:
leading scores for *any* card (the draft had tens and higher -- piquet au
cent's rule); the last trick's extra point (missing); younger *must* take
at least one card (the draft allowed none); only elder may peek, at the
cards they left (the draft let either); repique needs the opponent not to
have scored (missing); the settlement is the difference plus 100, or both
totals plus 100 when the loser misses the rubicon (the draft: "extra points
for a big margin"); lying is one card fewer or nothing (what the table
offers); ties score for neither; a line on the order points count in.
Typos, "stock" made "talon" as the table says it, and elder and younger
defined where first used. Then: an X at the top right, pop-ups only in the
tutorial's partie (confirmed: the partie begun from **Tutorial**, not the
first **New game**), and a Settings switch, off by default. The exchange's
page waits for the deal to be decided, and the introduction says the pages
will come by themselves.

### 28 September 2026: the phone's pass, the dialogue boxes, the voice built and unwired

- **The phone's own pass** (TABLE3D P14). Measured first: at 390 x 844 the
  strips took 564 of 844 px. Top strip 325 -> 138 px (the score in one row
  beside two stacked buttons, a tap on it opens the tab; the worth card
  folds to one line); foot 239 -> 190 px at its tallest (one row of tools;
  Explain and Hints are Settings' switches on a phone; "Played for you"
  floats). The upright field is now *fitted* to the band the strips leave
  (`framing.js` `STRIPS`, `CAMERA_PORTRAIT.reach`), under a lower eye with
  re-stacked zones. Your cards ~132 px tall at 390 x 844 (from ~60), ~91 px
  at Safari's 664. Staging tests at five real phone sizes; the browser test
  holds the page's strips to `STRIPS`. A follow-up found that sorting by
  rank fans the hand wider and dipped it ~4 px into the controls on a
  375 x 667 phone; the phone tests now cover every sort (`fd98353`).
- **The declarations as dialogue boxes** (TABLE3D P17): each line of the
  declarations in a box by its speaker's hand, the tail pointing to them;
  each line takes its turn, so the answer follows the call, and the score
  waits until the dialogue has been said. The words come from the phrase
  bank, several ways of saying each thing, never the same twice running —
  which also gave a point called short ("Two cards.") its box.
- **The voice** (TABLE3D P13, P15, P16, P18): a spoken voice was built with
  Piper TTS, audited, and unwired the same day (28 September) at the user's
  request; it was removed from the repository on 1 October. What outlived
  it: the engine's `decided` event carries `asked`, and each dialogue line
  waits for its event's moment on the animation's clock
  (`choreography.js` `beats`).
- **A WebKit smoke test** (Playwright's WebKit 26.6 on Linux — Safari's
  engine, not Safari): the page loads and plays, no console errors, the
  dialogue boxes draw with their tails, at 1280 x 800 and on a phone. The
  tests otherwise run Chromium, so real Safari remains the final check.
- **Reload measured:** levels 1–4 replay in ~10 ms; level 5 (the solver)
  takes 1.4–3.6 s late in a partie. See "Aids" below.
- Engine and CLI, the same days: **the terminal became a client of the core
  session**; **golden vectors for `match` and `tournament`** found three
  Rust port defects (TODO 5); `round_robin` and `format_table` ported; the
  CLI's interactive half tested; colour in the terminal; `chances` takes a
  table of one's own. Details under "What the port left behind" and TODO 5.

### 27 September 2026: the 3D table, P0–P12

The user asked for a three.js table; **`docs/TABLE3D.md` is its plan and its
record** — the brief verbatim, the look, the assets and their licences, the
stack, the architecture, the physics of every motion, the tests, and a
phased TODO with what each phase found. By the end of the day it was
playable end to end, by mouse and on a phone held upright.

- **P1** (`84b30fa`): `web3d/` — npm-pinned three 0.186.1 / Material Web /
  Lit / esbuild, `web3d/build.py` → one offline page, `web3d/test/browser.py`
  (no network request of any kind, canvas drawn, engine answers, no console
  errors; laptop and phone).
- **Art** (`28bcd58`): `web3d/tools/art.py` cuts the deck into per-card SVGs
  and 512 px WebP faces; the back re-framed to 5:7 (our CC BY-SA adaptation).
- **P2** (`a4d11f0`): card geometry (node-tested), cel shading, the ink line —
  pushed *in the model, in the card's plane*; pushing on screen drew a wedge
  over every tilted card — and shadows. `web3d/src/spike.js` is a hand-set
  table mid-deal (`?spike`).
- **P3** (`51c4a32`, `b2e6e53`): vector art (`build.py --art svg`) measured
  against raster (TABLE3D §3.2). Raster is the default and is what ships.
- **P4** (`ceaff44`): `easing.js`, `kinematics.js` (transfer, lay-down,
  pick-up, the rolling two-pivot flip that crests without stopping, slide,
  fan), `timeline.js`; `?demo` loops them, `piquet3d.demoAt(t)` freezes them
  for filmstrips.
- **P5** (`e7c88e7`): `layout.js` — 32 slots from any state, faces only where
  the human may know them, tested over four whole parties
  (`web3d/test/partie.js` plays them through the wasm).
- **P6** (`7bb0b09`): `choreography.js` replays the events between two states
  into the intermediate states and animates between their layouts;
  `director.js` plays it on the page. The cut, the deal in pairs, the
  exchange, tricks swept to their winner, all physically checked.
- **P7–P9** (`680d4cc`, `56b7867`, `f6a6e8e`): the Material 3 overlay
  (`overlay.js`), the app (`main.js`), decoration by ink colour, the phone's
  portrait layout, a browser test that plays a whole partie by clicking,
  reduced motion, a thinking bar, freshly drawn cards standing proud. **VSM
  shadows were cut ~8×** (512², 8 samples) after measuring 4.3 s a frame on
  the VM. Afterwards: **your discards can be picked up and looked at**, as
  the rules allow (`7479a52`); a full hand kept clear of the prompt
  (`53bde1e`); **the whole game playable from the keyboard** — ← → and Space,
  named in a live region (`4082ac7`), every key listed in Settings
  (`2ea37ed`); and tablets, whose score tab had been covering the top bar's
  settings button (`540fd46`).
- **P10–P12**: the user's notes from playing it — the hand's sort bar, the
  hands' tilt and shadows, thrown motion, information left and buttons under
  the hand, a broadcast-style live score bug with the stage table kept as
  the log, facts / explanations / hints as three layers (the last two
  toggles), an optional lifelike cut, and eighteen procedural table tops.
  Each note, verbatim, and what it became are in TABLE3D §13.
- Lessons: three r186 **removed `PCFSoftShadowMap`**; `render()` returns long
  before the frame lands, so time to the second animation frame; every page
  load on the VM takes ~7 s because SwiftShader emulates the GPU.

### 27 September 2026: the second round of notes on the 2D page

After playing the first build the user asked for six things; all six were
built and carried into the 3D table.

1. **Sort the hand to show the best holdings.** Auto / Suit / Rank /
   Combinations. Auto groups by combination while exchanging and declaring
   (best point, sequences, sets, then the rest) and by suit in play. Worth
   chips lift a holding's cards; click to pin. Engine: `combos::holdings`
   gives text + category + cards (protocol 2).
2. **Show what the opponent does.** Their discards are a face-down pile with
   its size (`View::opponent_discards`, derived from the view); their hand is
   a face-down fan; the talon is a pile in the middle.
3. **Played tricks, per the books.** Face up in front of whoever won them,
   examinable any time — Cavendish p.108 and Law 60; pagat (`tricks_played`).
4. **An easy way to turn hints off.**
5. **No proper names.** "Your opponent" everywhere a player reads; levels are
   described by skill (`e67e1e8`).
6. **The cut for deal.** Verified from pagat, Cavendish Laws 3–4 and p.108,
   Foster (1897) and Cotton (1674) — the older lower-card rule is recorded and
   not followed (`docs/PIQUET.md`). The partie opens on a fanned pack; the
   higher card chooses; the opponent, winning it, elects to deal first.

Loose ends from the round: the terminal now cuts too (28 September; an empty
answer cuts the middle of the pack, the page's "Cut for me"), and the same
seed at the same level, cut the same way, is the same partie at the terminal
and on the page. A pushed page once read "Worth: [object Object]" — a patch
that failed silently (`2b30cbd`); since then every multi-step shell command
starts with `set -e`.

### 26 September 2026: the session, the protocol, the 2D page, the fourth leak

1. **The settling search counts a repique already made** (`a84b34b`). Correct,
   and measured to change nothing: 248–46–426 against 249–46–425, net −4.50 ±
   3.48. So it was *not* the loss tail. The tail, split by bonus: **no-bonus
   deals** hold 27 of the 46 losses and −6,724 of the damage (rubicon flips of
   ~250 each); **pique deals** lose 18 of 52 — 35% against 4% elsewhere, which
   points at a pique still *live* when the search starts (TODO 9's
   `pique_is_live`); repique deals lose once. See TODO 1.
2. Docs and lockfile caught up with the VM and the port.
3. `options` and `opponents` moved from the CLI into the engine.
4. **`table.rs`** — the session state machine; **`piquet-wasm`** — the JSON
   protocol; **`docs/PROTOCOL.md`**; and a plain 2D page (`web/`, retired
   1 October 2026), playable.
5. **The dialogue's fourth leak, fixed** (`0765838`): after elder led, the
   engine told him the shape of every holding younger declared, including
   ones she lost outright and never names (pagat; Foster 1897). 46% of deals.
   The inference had been leaning on it; its honesty rung now reads silence
   against the public answers, and elder narrows 5,005 → 958 → 255 through the
   dialogue where he used to sit at 5,005. Rungs 1–4 are unaffected (they
   never read `heard`; the ladder is identical: 858 / 811 / 774 / 343). Rung
   5 against rung 4, 300 mirrored pairs, same deals: **84.0% / +6.4 before,
   83.5% / +6.2 after** — no measurable cost. After elder's first lead, over
   300 deals, his candidate count went from mean 55 to 75 (median 34 → 36):
   the leak had been sharpening his picture by about a quarter.

### Aids: making it effortless and fun (26–28 September)

The user's steer for the game layer: *"less persnickety, less needless
clicking — rather, effortless and fun"* — reorder the hand usefully, keep a
running tab of the scores, offer hints — and every aid a toggle.

**Engine (`table.rs`, then the protocol)** — done (`4baba8c`, `2e42573`,
`8521b87`): `Aids` on the table, a record of every action from the human's
seat, `Table::replay` and `undo`, `Table::hint`, and the protocol commands
`undo` and `set <aid> on|off`. Scores carry their category, for the running
tab.

- **Hints.** `Table::hint()` — what an advisor would do *from the human's
  view*, so it can never leak. Advisor: rung 4 for the exchange and the
  declarations, the solver in the endgame — the first brick of Milestone 9.
- **Undo.** The table is deterministic, so undoing is replaying every
  accepted action but the last human one. Misclicks stop mattering.
- **Auto-play forced cards** (one legal card — always so on the last trick).
- **Declare for me**: call everything without asking (off by default; see
  "Open for the user").
- **Play my sure winners** (`ea7861a`, opt-in): when you are on lead and
  every card you hold beats everything still unseen in its suit, play the
  rest out for you.
- **The cards behind each option**, so a client can highlight what a
  declaration or a "worth" line is made of.

Measured: forced-card play takes a partie from ~97 clicks to ~82; declare for
me removes up to 18 more. **Undo is instant** — a snapshot stack, 3.2 s →
2 ms at level 5 late in a partie.

**Faster reload — decided against (1 October).** A reload replays the
partie: levels 1–4 in about 10 ms, level 5 (the exact solver) in 1.4–3.6 s
late in a partie, about as long as playing it took (the page says "Restoring
your game…"). Making it faster means saving and restoring the level-5
opponent's generators (several Mersenne Twisters inside its agents) through
the core engine, where a slip would silently change the replayed game — a
risk to exact replay, for a few seconds' wait in one case.

Still open: **say *why*, not just what** — the hint's second half,
`explain.rs`, Milestone 9.

### After that, in rough order of value

1. **TODO 1, the partie objective** — measured; the level-5 default is the
   user's call.
2. **Milestone 9, the training mode** — hints are its first half; `explain.rs`
   (why a move is better, by which rung plays it) is the second. Its shape is
   a design conversation to have with the user before building it.
3. **Milestone 8, the exchange policy.** The only item that would spend money.
4. **`piquet-py`** (PyO3), so thirty-line experiments stay thirty lines.
5. **Milestone 10, CFR declarations.** Still the largest unknown.

## Settled decisions

| Decision | Choice |
|---|---|
| Rule authority | **pagat.com**, except where it departs from the Cavendish laws it cites (pique's reckoning order, R8). One rule each; no switches between readings |
| Game implemented | Rubicon Piquet, 32 cards, 6-deal partie |
| Language | **Rust**, decided September 2026 — `docs/DESIGN.md` §13.5 ranked it first on three of the four goals, §2.2 audits what the port hits. Python stays as the oracle |
| Where it runs | **Google Cloud only.** No toolchain on a laptop; development happens on the VM, joined to any other checkout by GitHub (`docs/VM.md`) |
| Repository | `github.com/abartnof/piquet`, **public from 1 October 2026**; GitHub Pages serves the game from `main`. The 2017 attempt survives as `piquet-2017` |
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
| UI | The terminal first, then a plain 2D page (retired 1 October 2026), now the **3D table** (`web3d/`) |
| Sound | **None.** A spoken voice was built and removed (28 September – 1 October 2026) |
| LLM involvement | None in gameplay; optional for phrasing tutor explanations |

## Milestones

- [x] 1. `cards` + `combos`
- [x] 2. `rules` + `scoring` — phase machine, event log, pique/repique
- [x] 3. Random agent, statistical invariants, move log from the first deal
- [x] 4. Heuristic ladder, styles, Elo harness with mirrored pairs
- [x] 5. **Exact endgame solver** + inference; rung 5 (82.5%, +5.0 pts over L4)
- [x] 6. **The partie** — six deals, alternating deal, rubicon settlement
- [x] 7. **Terminal UI**; skill and erratic controls; a playable game
- [ ] 8. Exchange policy — *runtime and cost agreed with the user first*
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
"the largest measured weakness in the AI" — was wrong. Not landed as a
default, because the weights are fitted to rung-4 discard habits and would be
a guess against a human. The principled version is milestone 8's exchange
policy read backwards. (A fitted prior has since been built for TODO 1.)

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

- ~~`tournament.partie_duel` and `PartieResult` are not ported.~~ **Ported
  since** (`2bdd7df`), with `bin/parties` and `bin/settle` as the instruments
  built on it.
- ~~**`round_robin` and `format_table` are not ported.**~~ **Ported** (28
  September), with `Display` for both result types; `bin/ladder` now uses
  `round_robin` and prints exactly what it printed before. The printed forms
  are golden vectors, rounding ties included (both languages round half to
  even from the exact binary value -- measured, not assumed).
- ~~**Colour is not ported.**~~ **Ported** (28 September): `render::Palette`
  paints hearts and diamonds red -- the hand's rows and the card led -- when
  the output is a terminal and `NO_COLOR` is not set; black is never painted,
  so spades survive a dark terminal. (The Python's stage strip, which used
  bold and dim, has no Rust counterpart to colour.)
- ~~**`chances::density` and `survival` take no custom table.**~~ **They do**
  (28 September): `density_in`, `survival_in`, `chance_of_in` and
  `chance_of_the_rubicon_in` take a `Densities` of one's own, the plain
  names reading the measured rung-4 table as before -- the Python's
  "measure your own and pass it as `table`". A small uneven table is a
  golden vector, so ignoring it or mixing up the seats fails.
- **`solver.partie_aware` is not ported**, deliberately: it measured worse
  than the flat objective and ships off. See TODO 1, which wants the objective
  settled at the leaf rather than linearised on the way down.
- ~~**The interactive half of the CLI is untested.**~~ **Tested** (28
  September): the table's `Table` now takes its output and what running out
  of input means as well as its input, and sixteen tests drive `HumanAgent`
  from a script -- every prompt, and every way each answer is refused and
  asked again (not a card, not held, not following, the same card twice, a
  discard of the wrong size, a choice not on the list), the empty answer
  calling in full, understating offered, nothing asked with nothing to call,
  younger hearing elder's call, and walking away at the end of input.

## TODO — things owed that are not yet built

Ordered by how much they are needed, not by size.

1. **The partie objective — built, measured, not yet a default.**
   **Whole parties (1 October):** settling beats flat by **+8.26 ± 2.54
   settlement points a mirrored pair** (z 3.25), both with the fitted prior,
   in self-play at rung 5. A sequential design fixed in advance, as the user
   asked ("if the numbers are conclusive with fewer simulations, you cut the
   simulations short"): batches of 100, O'Brien-Fleming boundaries
   4.05/2.86/2.34/2.02; stopped at the second look, 200 pairs, about fifty
   minutes (`bin/partie-sequential`, `measurements/partie/`). Settling won 70
   pairs, lost 46, tied 84. Real and modest: about four points a partie,
   against settlements that run to hundreds. **Making it the level-5 default
   is the user's call**, tied to whether the prior is fair against a person.

   The history. The search carries both totals to the leaf and settles there
   (`solver::card_settlements`), which is what `docs/DESIGN.md` §6.4a asked
   for. It costs only **1.6× at eight tricks**, far less than the state-space
   argument suggests, because the reachable point splits at a position are
   tightly constrained.

   Over **720 mirrored last deals** it wins 249, loses 46, draws 425 — against
   the linear-weight attempt's 0–9–66. But the net settlement is **−4.49 ±
   3.48**, which is 1.3 sigma and therefore nothing. It wins often by little
   and loses rarely by a lot.

   **Repique — tried, and not it.** The search now counts a pique or repique
   already decided (`solver::settled_log`), which was a real sixty-point
   error in every repique deal. It changed the result by one deal. Splitting
   the 720 by bonus says where the tail really is:

   | deals | count | won | lost | sum of losses |
   |---|---|---|---|---|
   | no bonus | 626 | 221 | 27 | −6,724 |
   | pique | 52 | 18 | **18** | −1,228 |
   | repique | 42 | 9 | 1 | −398 |

   **Both leads, measured (27 September).** The fourth-leak fix had changed
   what both agents know, so the baseline was measured again first. Every
   row is the same 720 mirrored last deals (`settle 120 <worlds>`):

   | settling search | won | lost | drawn | net per deal |
   |---|---|---|---|---|
   | baseline, 30 worlds | 257 | 49 | 414 | −3.40 ± 3.57 |
   | 90 worlds | 257 | 44 | 419 | −2.51 ± 3.69 |
   | **plays for a live pique** (`79cfc82`), 30 worlds | **266** | **33** | 421 | **−1.30 ± 3.55** |

   **The live pique was a real piece of the tail, and stays** — it is what
   the rules say anyway. Like for like (both runs split by bonus,
   `bb0fc35`), pique deals went from 21 lost of 52, costing 1,252 points,
   to **4 lost of 48, costing 26**; the other deals did not move. Sixteen
   fewer losses is about 1.8 sigma even treating the runs as independent,
   and pairing on identical cards should only tighten that. But the net was
   still no distance from zero (0.4 sigma). What was left of the tail was
   **28 rubicon flips in no-bonus deals**, 6,730 points at ~240 each. To
   reproduce: `cargo build --release`, then `target/release/settle 120 30`.

   **Paired, and the tail read again (27 September).** `settle --out FILE`
   records every pair with its pack; `--compare A B` pairs two runs on
   identical deals; `--show FILE STANDING DEAL` replays one pair with belief
   beside truth at every card. Records are in `measurements/settle/`;
   `docs/DESIGN.md` §6.4a has the reasoning.

   - **90 worlds vs 30, paired: +0.01 ± 0.79** — the play differs in 26 of
     720 pairs. Because **85% of searched decisions have ≤30 consistent
     worlds** (64% at eight cards, 96% at four): the sample is already
     the whole set. World count is not a lever.
   - **Flips go both ways, 11 big wins against 13 big losses** (~400
     each). The steady gain is small wins: 255 against 20, **about +2.2 a
     deal**. The −1.30 net is flip noise over that.
   - **All 13 big losses are belief errors, not bugs** — a card believed
     best over the worlds and worse in truth, the truth splitting exactly on
     who reaches a hundred.

   **The calibrated world prior (27 September)**, the lever that acts on the
   flips. `bin/prior` fits a per-rank weight on the opponent's possible hands
   (`prior.rs`, conditional logit) where the solver searches; the solver
   takes it via `SolverAgent::with_prior` (bit-identical without one). Held
   out, a doubtful seven is hers 12% of the time against a uniform belief of
   46%, a king 96% against 55%; the fit matches (`measurements/prior-60.txt`).
   It is worth **+0.68 a pair** to the solver outright (`bin/priorduel`, 47–11
   of decided pairs), and with it **settling beats flat by +10.53 ± 3.16 a
   deal (3.3σ)** on the 720 last deals, rubicon flips **15–2** where they had
   been 11–13 (`measurements/settle/w30-prior.*`). Whole parties were then
   timed at 9.8 s a mirrored pair on one core; most pairs come out level and
   the effect lives in rare rubicon flips, which is why the whole-parties
   run used a sequential design rather than a fixed ~2,000 pairs.

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
5. **Golden JSON vectors — done.** All fourteen modules covered: `cards`,
   `combos`, `scoring`, `style`, `declarations`, `rules`, `observation`,
   `partie`, `solver`, `chances`, `heuristics`, `inference`, and (28
   September) `match` and `tournament`. Generated by
   `python/tools/emit_vectors.py` from the oracle, replayed by the Python's
   `tests/test_vectors.py` and the Rust's `tests/golden.rs`, and committed
   under `vectors/`.

   The last two found **three defects in the Rust port**, all fixed: the
   move log's `bonus` dropped who took it ("repique" for the oracle's
   "elder repique"); `ratings` panicked on an anchor that played nobody,
   where the oracle ignores it; and a result with no pairs had a win rate of
   0 where the oracle's is an even 0.5. `match` pins the training log
   decision by decision, compared as parsed JSON (the Python escapes
   non-ASCII, "sixième", and the Rust writes it raw; both parse the same).
   `tournament` pins everything after the cards — the duels draw their
   deals from a seeded generator, which no two languages share. One oracle
   nit left alone: `ratings([])` divides by zero in Python and returns
   nothing in Rust.

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
9. ~~**`solver.pique_is_live` is still dead code**~~ — **answered in Rust.**
   The settling search now plays for a pique still live
   (`solver::piqued_after`, `79cfc82`), which is the question the helper was
   written to ask. The flat search still ignores piques by design — its
   objective is additive and the pique is not — and the Python helper stays
   dead in the frozen reference. Nothing left to do unless the flat search is
   ever asked to see them.
10. **Younger's untaken talon cards.** If she leaves any she may expose them to
   both players after elder leads, or leave them face down. Not modelled.
11. **Carte blanche's information timing.** Elder must announce how many cards
    he intends to discard so younger can choose hers before seeing his hand.
    We score the ten and skip the choreography.
12. ~~**Documentation and citations.**~~ **Done**: `docs/LITERATURE.md` ("The
    mathematics") carries Laplace (1774), Zermelo (1929), Bradley and Terry
    (1952), Hunter (2004), Waldegrave's *Le Her* via Montmort (1713) and
    Hoyle's hypergeometric tail, with a table of where each is used in the
    code.
13. ~~**Card art.**~~ **Done** — the 3D table's faces and back
    (`web3d/art/`), credited in `CREDITS.md`.
14. ~~**The voice.**~~ Built, unwired on 28 September and removed from the
    repository on 1 October 2026. Closed; not owed.
15. **Tutorial mode — built, the light way** (`docs/TABLE3D.md` P19; the
    user's own four pages replaced the first words on 30 September, P20).
    Chosen instead of a coach that flags moves: *"an introduction (concise,
    bullet points- nothing too wordy), and an introduction before each phase
    of play ... hints+explanations are on by default"*, with a welcome
    offering New game or Tutorial. A move-flagging coach (solver values for
    the play, the top rung's choice elsewhere) and `explain.rs`'s "why"
    remain possible later layers, not asked for.
16. **The declaration dialogue boxes — built** (`docs/TABLE3D.md` P17). Each
    line of the declarations in a box by its speaker's hand, the tail
    pointing to them; each line takes its turn (`web3d/src/dialogue.js`),
    and the score waits for them.
17. ~~**Pique's reckoning order: pagat or Cavendish?**~~ **Decided 30
    September: Cavendish's category order, as the engine already played it;
    no switch.** R8 in `docs/DESIGN.md` §3.7; §3.6 and §5.2 corrected.
18. ~~**Show elder the talon cards they left.**~~ **Done 30 September** as
    two protocol events and a line in the point's explanation; a talon peek
    was measured to be useless against this opponent, which always draws
    them (see the log, 30 September).

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
  because it heard your point"*. An explanation in terms of a **skill the
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
| Younger names the shape of everything she declared | Only what she won, or matched: beaten outright she says "good" and nothing else. Naming the rest leaked in 46% of deals, and the inference had quietly come to depend on it |
| Elder leads blind against five thousand hands | Against about 255 in the vector deal: her public answers narrow him too. The 5,005 was the inference discarding them |
| Every unaccounted-for card is equally likely to be hers | An ace is, 100% of the time; a seven, 28% — though correcting it is worth only +0.3 a pair |
| The hand-tuned discard must be leaving points on the table | A Monte Carlo with a hundredfold more compute per decision agrees with it five times in six |
| Hoyle's three-to-two on younger's draw | Right, and the sentence pins down which sum he did: 23/57, or 1.478 to 1 |

And the methodological ones:

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

- The project prefers deliberate design conversation to speed, welcomes
  tangents, and wants the result to be *fun*, not merely correct.
- **Consult the user before any long or paid compute run**, with a runtime and
  cost estimate in hand. Milestone 8 is the first one that needs it.
- `observation.py` is still the module most likely to be got subtly wrong. It
  has now leaked four times: `View.results` handed over the opponent's full
  declarations; `Announcement` published the tie-break unconditionally;
  `_heard` gave elder younger's declarations before he had led; and
  `announcement_of` named younger's beaten holdings, which she never says.
  Treat every addition to `View` with suspicion, and ask of each field *when
  was this said aloud, and by whom*. The fourth was found by **narrating**
  the dialogue for the browser table — reading it as a player would is a
  good audit.
- Browser testing on the VM: `node` and `chromium` come from apt; Playwright
  lives in the project `.venv` (`.venv/bin/python web3d/test/browser.py
  [shot-dir]`). Screenshots can be read back to check the page by eye.
- Tests: 206 in Rust, the 3D table's node tests, and the Python oracle's
  suite. The Python's fast loop once drifted from sixteen seconds to
  sixty-three, and the drift was one test: a full twelve-card solve,
  unmarked. **When a loop starts to feel slow, look for the one test**
  (`--durations` in pytest; per-binary times in `cargo test`) — it was not
  creeping decay, and it will be one test again.
- The slow tests are the statistical ones and they have caught more real bugs
  than the unit tests, so they stay in the default run.
- Re-measure `style.CALIBRATED` whenever the ladder changes. What counts as a
  near-equal option depends on how well the agent plays.
