# Piquet — Living Plan

> Insurance against lost context. `docs/DESIGN.md` holds the *reasoning*,
> `docs/PIQUET.md` the *game*, `docs/LITERATURE.md` the *sources*; this file
> holds *where we are and what is left*. Last updated 27 September 2026
> (third session): **the 3D table has had Andrew's nine notes from playing
> it** (`docs/TABLE3D.md` P10) — hands at 75°, shadows that follow the
> cards, the tug, a dialogue box, controls under the hand, animated folds,
> flourishes for big moments; and **TODO 1 has a calibrated world prior
> fitted and waiting to be measured**.

## Where we are

**Milestones 1–7 complete, and the Rust port with them. Python oracle suite
green; 118 Rust tests.**

**It is playable in a browser.** `web/piquet.html` is the whole game in one
391 KB file — the engine compiled to WebAssembly and inlined, and a
deliberately plain table. Open it from disk; no server. Andrew's goal for it
is to play and send notes; "Copy game record" gives a seed and command list
that replays any game exactly. Rebuild with `python3 web/build.py`.

**And in a terminal.** `cargo run -p piquet-cli -- --level 3` sits you down
against a named opponent for a partie of six deals, settled by the rubicon.
Four measured rungs plus the exact-endgame solver, with styles and
erraticism, and a mirrored-pair tournament that rates them.

**The GUI is disposable by design.** Andrew: "don't get too attached to the
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
  solver.rs        exact endgame search, and the agent that uses it
  play.rs          running deals and parties; the move log
  table.rs         a partie as a session: Prompt / Action / Event, for any client
  options.rs       what a player may declare in a category (full, sink, short)
  opponents.rs     the named roster, Bess to Foster, and seating one
  tournament.rs    mirrored-pair duels, Bradley-Terry ratings
  mt19937.rs       CPython's generator, for the one fixed-seed model constant
  rng.rs           the agents' own generator
crates/piquet-cli/src/
  main.rs          the table a person sits at; the human as an Agent
  render.rs        drawing a hand in the language the prompt accepts
crates/piquet-wasm/src/
  lib.rs           the table as a protocol: JSON out, one-line commands in
web/
  src/             index.html, app.js, style.css -- the page, holding no rules
  build.py         inlines the wasm and the page into web/piquet.html
  piquet.html      the built, playable, single-file game (committed)
  test/ffi.mjs     node drives the .wasm; native and wasm32 agree byte for byte
  test/browser.py  headless Chromium plays whole parties by clicking
python/            the oracle: the original, which generates the vectors
vectors/           golden JSON, read by both languages
docs/PROTOCOL.md   the contract a replacement client is written against
```

**The parity gate is met.** Both halves of it:

- Every golden vector reproduces in Rust — twelve modules, from the pack through
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

On the VM itself, `cargo` is not on the PATH until `source ~/.cargo/env`. The
whole gate — `cargo fmt --check`, `cargo clippy --all-targets --release -- -D
warnings`, `cargo test --release` — takes about **3½ minutes** on the
two-core machine, most of it compiling; the tests themselves are one minute,
and one statistical binary is nearly all of that.

**The gcloud CLI on the VM cannot see billing.** It runs as the instance's
default service account, whose scopes cover neither `gcloud billing` nor
`gcloud compute instances list`. The per-session spend check needs either
`gcloud auth login` on the VM or a look at the Console.

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

### Resume here (third session, 27 September): two threads

**1. The 3D table — Andrew is playing it and sending notes.** His nine
from this session are all built and pushed (`docs/TABLE3D.md` P10, commits
`c8502b7`…`8ef2fe3`); the verbatim notes and what each became are there.
He then rejected the dialogue box for a broadcast-style **live score bug**
— two numbers, a tick for ordinary points, a celebration for big ones —
with the stage table kept as the log (P11).
The overlay is now *information left, buttons under the hand*, a standing
rule (saved to memory). Whatever he sends next is the backlog. Owed from
this round: **the phone's table** (small hand, the info strip covering the
opponent's hand, a heavy shadow blob). His earlier open choices (below)
still stand.

**2. TODO 1 — the calibrated prior works; whole parties are next, and
need Andrew's sign-off.** Measured this session: the prior is worth **+0.68
a pair** to the solver outright (`bin/priorduel`, 47–11 of decided pairs),
and with it **settling beats flat by +10.53 ± 3.16 a deal (3.3σ)** on the
720 last deals, rubicon flips **15–2** where they had been 11–13
(`measurements/settle/w30-prior.*`; `docs/DESIGN.md` §6.4a). **Whole
parties:** timed at **9.8 s a mirrored pair** on one core; most pairs come
out level and the spread is rare flips, so ~2,000 pairs (≈5½ core-hours)
to see +5 a pair. Options for Andrew: the dev box, ~3 hours on both cores
(≈$0.20); or a throwaway 16-vCPU Spot VM, ~25 minutes (≈$0.10, plus a few
minutes' setup). **Shelved by Andrew (27 September)** in favour of the
score display — not urgent, and it does not touch how the game feels. The
instrument is built (`bin/partieprior`, `f1c2020`; 15.7 s a pair per thread
with both vCPUs busy, so ~4½ hours on the dev box for 2,000 pairs; a Spot
VM needs `gcloud auth login` on this VM first, and the free trial likely
leaves only ~6 spare vCPUs). Also his call: whether to ship the prior
against people at all.

*Before the measurements, the setup:*
`bin/prior` fits a per-rank weight on the opponent's possible hands
(`prior.rs`, conditional logit) where the solver searches; the solver takes
it via `SolverAgent::with_prior` (bit-identical without one). Held out, a
doubtful seven is hers 12% of the time against a uniform belief of 46%, a
king 96% against 55%; the fit matches (`measurements/prior-60.txt`). **Next
step:** give `settle` a `--prior` switch (both agents, the fitted constant
from `prior-60.txt`), run `settle 120 30 --prior --out
measurements/settle/w30-prior.tsv` (~21 min on the dev box), and
`--compare` it against `w30.tsv`: do the rubicon flips stop being a coin
toss (11–13 today)? It is a diagnostic first — the prior describes rung 4's
discards, and whether it is fair against a person is Andrew's call.

**Billing check:** still blocked from the VM (its service account has no
billing scope). Ask Andrew to glance at the Console, or run `gcloud auth
login` on the VM himself.

### The 3D table before this session — Andrew's choices, then onward

Andrew asked for a three.js table (27 September 2026); **`docs/TABLE3D.md` is
its plan and its record** — the brief verbatim, the look, the assets and
their licences, the stack, the architecture, the physics of every motion,
the tests, and a phased TODO with what each phase found.

**Where it stands (27 September 2026, second session).** `web3d/piquet3d.html`
is **playable end to end**, by mouse and on a phone held upright: the cut,
the deal in pairs, the exchange, declarations, every trick, the partie's
settlement, with the running score tab, hints, undo, your discards to
consult, and a browser test that plays a whole partie by clicking. P0–P2 and
P4–P9 done; **P3 waits only on Andrew's choice**.

**Next, in order:**
1. **Andrew's decisions**, all on the comparison page
   (https://claude.ai/artifact/X7MRnVJw3iGsR7WbTDW6xp): the table's surface,
   the shadows' softness, the ink weight, and the card art — pictures or
   drawings, which wants `piquet3d.art().readyMs` from both pages on his Mac.
   Record each in §13 of `docs/TABLE3D.md`; delete whichever art page loses.
   Also open: an idle sway (it would mean rendering forever — opt-in?),
   synthesised sound (a toggle?), and the aids' defaults.
   **Two things only his own devices can answer:** the art's load time
   above, and the frame rate on a real GPU — the VM emulates one, so every
   timing in `docs/TABLE3D.md` is a worst case.
2. Then the plan's order below: **TODO 1, the partie objective** — both
   suspects measured today, and the next step is written there — and
   **Milestone 9, the training mode** — the 3D table already has its first
   half (hints, refusals in the engine's words); `explain.rs` is the second.
   The training mode's shape is a design conversation to have with Andrew
   before building it.

- **P1** (`84b30fa`): `web3d/` — npm-pinned three 0.186.1 / Material Web /
  Lit / esbuild, `web3d/build.py` → one offline page, `web3d/test/browser.py`
  (no network request of any kind, canvas drawn, engine answers, no console
  errors; laptop and phone).
- **Art** (`28bcd58`): `web3d/tools/art.py` cuts the deck into per-card SVGs
  and 512 px WebP faces; the back re-framed to 5:7 (our CC BY-SA adaptation).
- **P2** (`a4d11f0`): card geometry (node-tested), cel shading, the ink line —
  pushed *in the model, in the card's plane*; pushing on screen drew a wedge
  over every tilted card — and shadows. `web3d/src/spike.js` is a hand-set
  table mid-deal, to be replaced by the real layout.
- **P3** (`51c4a32`, `b2e6e53`): vector art (`build.py --art svg`) measured
  against raster; both pages committed so Andrew can time them on his Mac.
- **P4** (`ceaff44`): `easing.js`, `kinematics.js` (transfer, lay-down,
  pick-up, the rolling two-pivot flip that crests without stopping, slide,
  fan), `timeline.js`; `?demo` loops them, `piquet3d.demoAt(t)` freezes them
  for filmstrips.
- **P5** (`e7c88e7`): `layout.js` — 32 slots from any state, faces only where
  the human may know them, tested over four whole parties
  (`web3d/test/partie.js` plays them through the wasm). The page now shows
  the real game at rest; `?spike` keeps the hand-set table.
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
- **TODO 1, paired and re-read (27 September, third session).** `settle`
  records pairs, compares runs deal by deal, and replays one with belief
  beside truth (`0f899e1`, `f6e3bef`; `SolverAgent::estimates` and
  `values_in`, `fea4e07`). 90 worlds vs 30: +0.01 ± 0.79, because 85% of
  searches are already exhaustive at 30. Rubicon flips go 11–13, a coin
  toss; the steady gain is +2.2 a deal. Next: a calibrated world prior.
- **TODO 1, both suspects measured (27 September).** On the same 720
  mirrored last deals: today's baseline **257–49–414, net −3.40 ± 3.57**
  (reproduced exactly by a second build; the old 248/46/426 predates the
  fourth-leak fix); **ninety worlds** 257–44–419, −2.51; the **live pique**
  played for (`79cfc82`) **266–33–421, −1.30 ± 3.55**, its whole gain in
  pique deals (21 of 52 lost → 4 of 48). The net is still no distance from
  zero. Table, reading and next steps in TODO 1; `docs/DESIGN.md` §6.4a.
- **Andrew's four choices are on a comparison page:**
  https://claude.ai/artifact/X7MRnVJw3iGsR7WbTDW6xp — table surface
  (provisional: pale sky), shadows (soft/VSM), ink weight (2.5 px), and card
  art (pictures/WebP), plus how to read `piquet3d.art().readyMs`. When he
  answers, record it in §13 of `docs/TABLE3D.md` and delete the losing art
  page.
- Lessons: three r186 **removed `PCFSoftShadowMap`**; `render()` returns long
  before the frame lands, so time to the second animation frame; every page
  load on the VM takes ~7 s because SwiftShader emulates the GPU.

Read, in this order: this section; `docs/TABLE3D.md` (all of it); §13 of it
again as the checklist; `docs/PROTOCOL.md`; `web/src/app.js` (a working client
to borrow from); `CREDITS.md`.

Rules that bind the work, from Andrew: TDD; atomic commits straight to `main`,
often; `PLAN.md` updated as each phase lands; `set -e` on multi-step shell
commands; one self-contained HTML page, **modest in size** (5 MB is a
guideline, not a hard limit — kept small enough to try the card art both
raster and vector and choose by eye), **working offline**;
Material Design 3 for the controls, bundled; **"your opponent", never a proper
name**; every aid a toggle; the look is *clean, bright, a bit cartoonish, not
childish — freed of grubby cards on dirty furniture*; **every third-party
asset credited in `CREDITS.md` in the commit that brings it in** (MD3
included); consult him before anything that spends money.

Environment on the VM: `source ~/.cargo/env` for cargo; Playwright in the
project `.venv`; Node 18 and Chromium from apt; npm and `librsvg2-bin` are
installed in P1 (`sudo` works). The Google Cloud billing check is still
blocked — the VM's gcloud has no billing scope, and `gcloud auth login` needs
an interactive terminal (Andrew was going to run it over `ssh piquet-dev`).

**Stopping from inside works.** 27 September closed with `sudo shutdown -h`
on the VM; the boot log shows a clean halt and a fresh boot thirteen hours
later, so it reached `TERMINATED` (`docs/VM.md`).


### This session, 26 September 2026 — what landed

In order, all committed and pushed:

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
   protocol; **`docs/PROTOCOL.md`**; **`web/piquet.html`**, playable.
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

### Andrew's second round of notes (27 Sept 2026) — done

After playing the first build he asked for six things; all six are built,
tested and pushed, and `web/piquet.html` is current (`a5f2e34`).

1. **Sort the hand in the first segment to show the best holdings.** A sort bar
   beside the hand — Auto / Suit / Rank / Combinations. Auto groups by
   combination while exchanging and declaring (best point, sequences, sets,
   then the rest, each group set apart) and by suit in play. Worth chips lift a
   holding's cards; click to pin. Engine: `combos::holdings` gives text +
   category + cards (protocol 2).
2. **Show what the opponent does.** Their discards are a face-down pile with its
   size (`View::opponent_discards`, derived from the view); their hand is a
   face-down fan; the talon is a pile in the middle.
3. **Played tricks, per the books.** Face up in front of whoever won them,
   examinable any time — Cavendish p.108 and Law 60; pagat (`tricks_played`).
4. **An easy way to turn hints off.** A switch in the header, "Hide hints" on the
   hint itself, and H.
5. **No proper names.** "Your opponent" everywhere a player reads; levels are
   described by skill (`e67e1e8`). Saved as a standing preference.
6. **The cut for deal.** Verified from pagat, Cavendish Laws 3–4 and p.108,
   Foster (1897) and Cotton (1674) — the older lower-card rule is recorded and
   not followed (`docs/PIQUET.md`). The partie opens on a fanned pack; the
   higher card chooses; the opponent, winning it, elects to deal first.

Loose ends from the round:

- The **terminal** does not cut yet; it still deals the human first. The same
  seed gives the same packs everywhere, and the same game whenever the human
  ends up dealing first.
- On a phone a combination group can break across the wrap of the hand.
- A pushed page briefly read "Worth: [object Object]" — a patch that failed
  silently (`2b30cbd`). The browser test now reads the worth line, and every
  multi-step shell command starts with `set -e`.

### Pick up here: making it effortless and fun

Andrew's steer for the game layer: *"less persnickety, less needless
clicking — rather, effortless and fun"*, with his examples of reordering the
hand usefully, a running framework of where the game stands with a tab of the
scores, and hints — and every aid a toggle. The plan, engine first where the
logic belongs in the engine (TDD there), page second:

**Engine (`table.rs`, then the protocol):**

- [x] **Hints.** `Table::hint()` — what an advisor would do *from the human's
      view*, so it can never leak. Advisor: rung 4 for the exchange and the
      declarations, the solver in the endgame. Name the rung in the hint
      ("Hoyle would throw…"), which is the ladder-based tutoring idea and the
      first brick of Milestone 9.
- [x] **Undo.** The table is deterministic, so undoing is replaying every
      accepted action but the last human one. Misclicks stop mattering.
- [x] **Auto-play forced cards** (one legal card — always so on the last
      trick) as a table setting.
- [x] **Declare for me** as a table setting: call everything without asking.
      Open question for Andrew — the default. Three prompts a deal is the
      single biggest source of clicks, but sinking is the interesting move and
      a teaching game should show it exists.
- [x] **The cards behind each option**, so a client can highlight what a
      declaration or a "worth" line is made of.

Engine half done (`4baba8c`, `2e42573`, `8521b87`): `Aids` on the table, a
record of every action from the human's seat, `Table::replay` and `undo`,
`Table::hint`, and the protocol commands `undo` and `set <aid> on|off`.
Scores carry their category now, for the running tab.

**Page:** done (`d702eda`, `53f4d0d`, `83db0c3`).

- [x] Settings panel, every aid a toggle, remembered in `localStorage`.
      Defaults: hints **on**, play forced cards **on**, declare for me
      **off**, running tab on, undo on, trick pause on, hand by suit.
- [x] "Where we are": the six deals as a strip with their scores, the phase
      of this deal (exchange ▸ point ▸ sequences ▸ sets ▸ trick n of 12 ▸
      count), and a running tab by category.
- [x] Hand ordering: alternating colours, or by rank to spot quatorzes; cards
      *slide* to new places; drawn cards marked "new" until play begins;
      hovering a declaration option lifts the cards it is made of; hinted
      cards glow.
- [x] Hints with a **Follow** button; **Undo** (button, U, Ctrl+Z); Enter for
      the main action; digits for declaration options; H toggles hints.
- [x] Pacing: a finished trick stays on the table for 0.9 s; cards land.

Measured: forced-card play takes a partie from ~97 clicks to ~82; declare for
me removes up to 18 more. **Undo is instant** — a snapshot stack, 3.2 s →
2 ms at level 5 late in a partie. **Reload still replays**: up to ~3.3 s at
level 5 late in a partie (the page says "Restoring your game…").

**Open questions for Andrew**, from playing it:

- Should **declare for me** default on? It is the single biggest source of
  clicks (three a deal), but the dialogue is the heart of the game.
- Are hints-on-by-default right, or should they wait to be asked for?
- Anything persnickety left — the notes he sends back are the next backlog.

**Next niceties, not started:**

- [x] **Play my sure winners** as an aid (`ea7861a`, on by default): when you are on lead and every card
      you hold beats everything still unseen in its suit, the rest of the
      tricks are yours whatever happens — play them out for you. The end of
      many deals is exactly this, and it is pure clicking.
- [x] Collapse the narration by deal, the current one open.
- [ ] Faster reload: record the opponent's moves too, so a reload applies
      them instead of re-deciding them. Needs care — the opponent's generator
      would then not have advanced, so the game would stop being reproducible
      from seed and human actions alone.
- [ ] Say *why*, not just what: the hint's second half, `explain.rs`,
      Milestone 9.

### After that, in rough order of value

0. ~~**The 3D table**~~ — built; its look waits on Andrew (above).
1. **TODO 1, the partie objective** — the live pique first, then `max_worlds`.
2. **Milestone 9, the training mode** — hints are its first half; `explain.rs`
   (why a move is better, by which rung plays it) is the second.
3. **Milestone 8, the exchange policy.** The only item that would spend money.
4. **`piquet-py`** (PyO3), so thirty-line experiments stay thirty lines.
5. **Milestone 10, CFR declarations.** Still the largest unknown.

## Settled decisions

| Decision | Choice |
|---|---|
| Rule authority | **pagat.com** wins all conflicts; variants behind flags |
| Game implemented | Rubicon Piquet, 32 cards, 6-deal partie |
| Language | **Rust**, decided September 2026 — `docs/DESIGN.md` §13.5 ranked it first on three of the four goals, §2.2 audits what the port hits. Python stays as the oracle until parity |
| Where it runs | **Google Cloud only.** No toolchain on a laptop; development happens on the VM, joined to any other checkout by GitHub (`docs/VM.md`) |
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

- ~~`tournament.partie_duel` and `PartieResult` are not ported.~~ **Ported
  since** (`2bdd7df`), with `bin/parties` and `bin/settle` as the instruments
  built on it.
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
   and pairing on identical cards should only tighten that. **But the net
   is still no distance from zero** (0.4 sigma), so settling at the leaf is
   not yet shown to beat the flat search where it pays.

   What is left of the tail is **28 rubicon flips in no-bonus deals**, 6,730
   points at ~240 each. Ninety worlds shaved five losses on its own (that
   run predates the split, so from where is unknown); ninety worlds *with*
   the live pique is the obvious next variant, once the comparison is
   paired. To reproduce: `cargo build --release`, then
   `target/release/settle 120 30` — the current search, live pique included.

   **Paired, and the tail read again (27 September, third session).**
   `settle --out FILE` records every pair with its pack; `--compare A B`
   pairs two runs on identical deals; `--show FILE STANDING DEAL` replays
   one pair with belief beside truth at every card. Records are in
   `measurements/settle/`; `docs/DESIGN.md` §6.4a has the reasoning.

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

   **Next, in order:**

   - **A calibrated world prior**, the lever that acts on the flips. Fit a
     per-rank weight on consistent worlds (a conditional logit on the true
     hand, fitted on deals the test does not use), give `SolverAgent` an
     optional prior, and pair settling-with-prior against today's `w30`.
     If the flips stop being a coin toss, that is the finding. Fitted to
     rung-4 discards, so it is a diagnostic first; whether it is fair
     against a human is a question for Andrew before it ships.
   - **Then judge on whole parties**, which is what this TODO has always
     said is the real test: `bin/parties` duels rungs today and needs a
     settling-against-flat mode on `tournament::partie_duel`. Time a small
     run first, and bring Andrew the estimate before a long one.

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
5. **Golden JSON vectors — nearly done.** Twelve modules covered, everything
   the port needed: `cards`, `combos`, `scoring`, `style`, `declarations`,
   `rules`, `observation`, `partie`, `solver`, `chances`, `heuristics`,
   `inference`. Generated by `python/tools/emit_vectors.py` from the oracle,
   replayed by the Python's `tests/test_vectors.py` and the Rust's
   `tests/golden.rs`, and committed under `vectors/`.

   Still owed: `match` and `tournament`, neither of which the parity gate
   needed.

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
| Younger names the shape of everything she declared | Only what she won, or matched: beaten outright she says "good" and nothing else. Naming the rest leaked in 46% of deals, and the inference had quietly come to depend on it |
| Elder leads blind against five thousand hands | Against about 255 in the vector deal: her public answers narrow him too. The 5,005 was the inference discarding them |
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
  has now leaked four times: `View.results` handed over the opponent's full
  declarations; `Announcement` published the tie-break unconditionally;
  `_heard` gave elder younger's declarations before he had led; and
  `announcement_of` named younger's beaten holdings, which she never says.
  Treat every addition to `View` with suspicion, and ask of each field *when
  was this said aloud, and by whom*. The fourth was found by **narrating**
  the dialogue for the browser table — reading it as a player would is a
  good audit.
- Browser testing on the VM: `node` and `chromium` come from apt; Playwright
  lives in the project `.venv` (`.venv/bin/python web/test/browser.py
  [shot-dir]`). Screenshots can be read back to check the page by eye.
- Tests: 95 in Rust, 520 in the Python oracle. The Python's fast loop once
  drifted from sixteen seconds to sixty-three, and the drift was one test: a
  full twelve-card solve, unmarked. **When a loop starts to feel slow, look for
  the one test** (`--durations` in pytest; per-binary times in `cargo test`)
  — it was not creeping decay, and it will be one test again.
- The slow tests are the statistical ones and they have caught more real bugs
  than the unit tests, so they stay in the default run.
- Re-measure `style.CALIBRATED` whenever the ladder changes. What counts as a
  near-equal option depends on how well the agent plays.
