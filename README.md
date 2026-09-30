# Piquet

A playable, teachable implementation of **Piquet** — the two-player 32-card
game that was France's national card game from the sixteenth century until it
faded after the First World War. David Parlett calls it "still one of the most
skill-rewarding card games for two"; it is now played only by aficionados.

The audience is therefore *new players*, and teaching is a first-class goal
rather than a bonus feature.

```
cargo run -p piquet-cli -- --level 3
```

That cuts for the deal and plays you a partie of six deals against your
opponent, settled by the rubicon. `--level 1..5` chooses how well they play;
`--seed N` replays a partie exactly, cut and played the same way. The terminal
and the browser table are two clients of one session (`piquet_core::table`),
so a seed is the same partie in both.

## What is here

| | |
|---|---|
| `crates/piquet-core` | the engine: rules, scoring, inference, the agents, the exact endgame solver |
| `crates/piquet-cli` | a terminal table you can sit down at |
| `python/` | the **oracle** — the original implementation, which generates the vectors below |
| `vectors/` | golden JSON: what the engine must compute, in a form both languages read |
| `docs/DESIGN.md` | why everything is the way it is. The long one |
| `docs/PIQUET.md` | the rules as implemented, with sources |
| `docs/LITERATURE.md` | the sources themselves, from Cotton (1674) onward |
| `PLAN.md` | where the work has got to and what is left |

## Two implementations, and why

The project was built in Python and ported to Rust. The Python has not been
deleted, because it is the **oracle**: it is the implementation that passes 520
tests, and every value in `vectors/` was produced by it. A Rust engine that
reproduces those vectors is, to exactly that extent, correct.

That is what the vectors are for. They do not make a port *easy* — plain,
serialisable state does that. They make it **verifiable**, which is a different
and larger favour: they turn "did I translate this correctly?" from a code
review into a test run. They caught several things during the port that no
amount of reading would have, including a display format buried in the event
log and a sort whose tie-breaking differs between the two languages.

## Running things

Development happens on a cloud VM, in a git clone there; `docs/VM.md` covers
starting it, getting in, and why `bin/vm`'s sync modes must not be used any
more. On the VM:

```
source ~/.cargo/env                # cargo is not on the PATH otherwise
cargo run -p piquet-cli            # play
cargo fmt --check && cargo clippy --all-targets --release -- -D warnings \
  && cargo test --release          # the whole gate
./target/release/ladder            # rate the opponents against each other
./target/release/bench 12          # time the exact solver by depth
```

And from the laptop, `bin/vm --up`, `--status` and `--down` start, inspect
and stop the instance.

The Python oracle runs from `python/`:

```
cd python && ../.venv/bin/pytest
python tools/emit_vectors.py       # regenerate the golden vectors
```

There is also a **differential harness**, which is a different instrument from
the vectors. The vectors are a specification: a handful of positions chosen
because somebody could say why they mattered. This is the other kind of check
— thousands of deals nobody chose, whose job is to find the divergence no one
thought to write a case for.

```
python tools/differential.py 20000 > /tmp/corpus.jsonl   # the oracle plays
cargo test --release --test differential                 # the Rust replays
```

The corpus is regenerable and deliberately not committed. Deals where the
solver had to sample its opponent-hand candidates are marked and skipped: past
`max_worlds` it takes a *random* sample, and there the two engines part company
legitimately, because no two languages share a generator.

Regenerate the vectors only when the engine's behaviour changes *on purpose*,
and then read the diff. A changed vector is either a deliberate rule change or
a regression, and the tests exist to make sure the difference is never silent.

## A few things the engine knows that the books get wrong

Every one of these was believed, written down, and then overturned by
measurement. The full list is in `PLAN.md`.

- The maximum score in a deal is **170**, not 153. Sets pay far better per card
  than length does.
- **Ducking beats cashing an ace**, because the ace takes the *last* trick,
  which is worth two.
- **A point is not a point.** Under the rubicon it is worth six when it carries
  you over the line — and while your opponent cannot reach a hundred, a point
  *to them* is worth about **+0.6 to you**, because a rubiconed loser pays the
  sum of both scores and theirs is part of it.
- **Elder's advantage is not structural**; it has to be used. He wins 52.5% of
  deals when both players take the full exchange and 49.6% when they do not.
- **Elder leads to the first trick blind.** Measured through the engine's own
  inference, younger can know his hand exactly before a card is played while
  he still has a couple of hundred possibilities open. She answers his calls
  but names nothing of her own until he has led — and afterwards only what
  she won — and that single rule is the whole asymmetry.

## Status

The rules engine, the opponents, the terminal table and a browser table
(`web/piquet.html`, one file, open it from disk) are complete and the game is
playable. Still to come: the training mode, and a mixed strategy for
declarations. `PLAN.md` has the detail.

**A three-dimensional table** — `web3d/piquet3d.html`, again one file that
works offline — is playable too: the same engine, drawn with three.js as
cel-shaded cards with ink outlines over a bright, plain table, every move
animated the way a hand would make it (cards dealt two at a time, turned over
on the table along an edge, tricks swept to their winner), with Material
Design 3 controls, a running score tab, hints and undo. Its design, the
physics of every motion and what was measured along the way are in
`docs/TABLE3D.md`; `?demo` on the page shows the motions on a loop.

## Licence

© 2026 Andrew Bartnof, under the MIT License (`LICENSE`). The card art, the
libraries bundled into the pages and the other third-party pieces keep their
own licences, listed with their authors in `CREDITS.md`; the card back is
CC BY-SA 3.0.
