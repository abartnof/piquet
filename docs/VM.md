# Working on the VM

All development for this project happens on a Google Cloud VM, not on the
laptop — there is no Rust toolchain on the laptop at all. Until now the laptop
held the git repository and pushed a copy of the working tree over with
`bin/vm`. That changes here: **the VM is now a full checkout in its own right,
with Claude Code installed on it**, so the work can happen there directly and
the laptop becomes just a terminal.

## The machine

| | |
|---|---|
| Project / zone | `abartnof-piquet`, `us-west1-b` (Oregon) |
| Instance | `piquet-dev` |
| Machine type | `e2-standard-2` — 2 vCPU, 8 GB |
| Disk | 50 GB, survives the instance being deleted |
| OS | Debian 12 (bookworm) |
| Checkout | `~/piquet`, a real git clone tracking `origin/main` |

It was an `e2-standard-4` while the heavy measurement runs were going on. With
that finished it is halved, which also halves the hourly rate. A full
`cargo test --release` from cold takes about **3m15s** on the smaller machine;
warm, it is seconds. Resizing is a stop-change-start and takes about a minute,
so if a big run ever comes back, step it up for the day and step it down after.

## Your laptop is already set up

Nothing to install. `gcloud`, `gh`, `git`, `ssh` and `rsync` are all present
and authenticated, and the SSH alias is written by `gcloud`.

## Turning it on

    bin/vm --up        # start it
    bin/vm --status    # is it up, and what is it costing
    bin/vm --down      # stop it -- do this at the end of every session

`--up` also refreshes the SSH alias, which matters: the VM's external IP is
ephemeral and changes on **every** stop-start cycle. If SSH ever fails with a
connection reset or a wrong host key right after starting, that is what
happened, and the fix is:

    gcloud compute config-ssh

You can do the same thing without the wrapper:

    gcloud compute instances start piquet-dev --zone=us-west1-b
    gcloud compute instances stop  piquet-dev --zone=us-west1-b

Both have to be run **from the laptop**. The VM cannot stop itself: its
service account was created without the compute API scope, so `gcloud` there
fails with *Request had insufficient authentication scopes*. From inside the
VM the equivalent is `sudo shutdown -h now`, which drops the instance to
`TERMINATED` and ends the compute charge. **Tested 27 September 2026:** the
boot log (`last -x`, `journalctl --list-boots`) shows a clean shutdown at
05:11 UTC and a fresh boot at 18:14, thirteen hours later, when the instance
was next started. `start` only boots an instance that is stopped, so the halt
did take it to `TERMINATED` rather than leaving a running machine with its
guest powered off.

Give it 30–60 seconds after `start` before SSH answers. The instance is
booting while `gcloud` has already returned.

## Getting in

    bin/vm                       # interactive shell, in ~/piquet

or plainly:

    ssh piquet-dev.us-west1-b.abartnof-piquet

That long name is the alias `gcloud compute config-ssh` writes into
`~/.ssh/config`; it is not a DNS name, so it only works from this laptop.

## Running Claude Code on the VM

Claude Code **2.1.283** is installed at `~/.local/bin/claude`. Your four
project memories and your `settings.json` were copied across.

    bin/vm                       # or the plain ssh above
    cd ~/piquet
    claude

Nothing was added to any shell startup file, here or on the VM — this document
is the only place that knowledge lives, so there is nothing to clean up
afterwards beyond deleting the machine. Two consequences worth knowing:

- `claude` is on the PATH of a **login** shell only, because Debian's stock
  `~/.profile` puts `~/.local/bin` there. `bin/vm` and a plain `ssh` both give
  you one. If you ever land in a shell where it is not found, run it by its
  full path: `~/.local/bin/claude`.
- **`cargo` is not on the PATH at all.** Put it there for the session with
  `source ~/.cargo/env`, or call it by path as `~/.cargo/bin/cargo`. The
  commands listed under *What is installed on it* below assume you have
  sourced it.

The first run will ask you to log in; it prints a URL to open in the browser
here on the laptop. Do it inside `~/piquet` so Claude picks up the repository
and the memories, which live under
`~/.claude/projects/-home-andrewbartnof-piquet/`.

### Surviving an internet hiccup

A plain `ssh` session does **not** come back. If the link drops, sshd hangs up
on the session, and anything running in it — Claude Code included — gets a
SIGHUP and dies mid-thought. Reconnecting gives you a fresh shell, not the one
you lost.

`tmux` fixes this, and it is installed on the VM (3.3a, from Debian's own
repository, with no config file — stock defaults). The trick is that tmux runs
its own server on the VM, independent of any SSH connection; your terminal
merely attaches to it. Use this instead of a bare `ssh`:

    ssh -t piquet-dev.us-west1-b.abartnof-piquet 'tmux new -A -s piquet'

`new -A` means *attach to the session called `piquet`, or create it if there
isn't one*, so the **same command is both how you start and how you come
back**. After a drop, run it again and you are looking at the same shell, with
Claude Code still running and whatever it printed while you were gone still on
screen.

To step away deliberately, detach with **Ctrl-B then d** — that leaves
everything running. Closing the terminal window does the same thing.

Worth adding keepalives, so a dead link is noticed in a minute rather than
hanging:

    ssh -t -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
        piquet-dev.us-west1-b.abartnof-piquet 'tmux new -A -s piquet'

Measured, not assumed: a tmux session started over SSH kept writing to a file
for the whole time the connection was closed, and was still there — same
session, same output — on reconnecting.

Two things tmux cannot save you from. **Stopping or rebooting the VM** kills
the tmux server with everything else; and if the VM was restarted, the SSH
alias points at the old IP, so run `gcloud compute config-ssh` before
reconnecting. For the first case, Claude Code has its own recovery: `claude
--continue` in `~/piquet` resumes the most recent conversation, and `claude
--resume` lets you pick one.

### One step left, and it needs your browser

The repository is private, so the VM cannot fetch or push until GitHub trusts
it. On the VM, once:

    gh auth login

Choose **GitHub.com → HTTPS → authenticate with a web browser**. It prints a
one-time code and a URL; open the URL here, paste the code. Say yes when it
offers to configure git to use `gh` as its credential helper — that is what
makes `git push` work afterwards. Verify with:

    cd ~/piquet && git fetch && git status

Until you do this the checkout still works for building and testing; only the
network half of git is blocked.

## Which copy is the real one

This is the one genuinely new hazard. There are now two full checkouts — the
laptop's and the VM's — and **GitHub is the thing that joins them**, not
`rsync`.

- Work on the VM, commit there, `git push`.
- On the laptop, `git pull` before touching anything.
- **Do not use `bin/vm --sync`, `bin/vm --check` or `bin/vm <cmd>` any more
  while working this way.** They rsync the laptop's tree over the VM's with
  `--delete`, which would throw away uncommitted work on the VM. They were
  right when the laptop was the only repository; they are a foot-gun now.

If you want the old one-way behaviour back for a quick check, commit on the VM
and push first, so there is nothing on the VM that only exists on the VM.

## What is installed on it

Rust 1.98.1 with clippy, rustfmt and rust-analyzer, and the
`wasm32-unknown-unknown` target; Python 3.11.2 with the project's `.venv`,
pytest and Playwright; Node 18 and Chromium 154 from apt, for testing the
browser build headlessly; `git`, `gh` 2.101, `ripgrep`, and Claude Code. The
`target/` and `.venv/` directories are already warm, so builds do not start
from zero.

For the 3D table (`docs/TABLE3D.md`): npm 9.2 and `librsvg2-bin` 2.54
(`rsvg-convert`, for rasterising the card art), both from apt, added 27
September 2026. The page's libraries and esbuild are pinned by
`web3d/package-lock.json`; `node_modules/` is not committed, so run `npm ci`
in `web3d/` after a fresh clone. Headless Chromium draws WebGL 2 on
SwiftShader, so the 3D page can be screenshotted without a GPU.

    python3 web/build.py                                   # web/piquet.html
    node web/test/ffi.mjs target/wasm32-unknown-unknown/release/piquet_wasm.wasm
    .venv/bin/python web/test/browser.py [screenshot-dir]  # plays it by clicking

    (cd web3d && npm ci)                                   # once, after a clone
    python3 web3d/build.py                                 # web3d/piquet3d.html
    (cd web3d && npm test)                                 # the pure modules, in node
    .venv/bin/python web3d/test/browser.py [screenshot-dir]

    source ~/.cargo/env          # once per shell; nothing does this for you
    cargo test --release
    cargo clippy --all-targets --release -- -D warnings
    cargo fmt --check
    .venv/bin/pytest -q
    cargo run -p piquet-cli -- --level 3

## What it costs

| | |
|---|---|
| Instance, while running | ≈$0.067/hour, down from $0.13 |
| Disk, always | ≈$5/month, whether or not the instance is up |
| At ~15 hrs/week | ≈$9/month |

The account is on Google's $300 new-customer credit, 90 days from September
2026. A budget on the billing account emails at 25 / 50 / 75 / 90 / 100 %. The
realistic failure is not a surprise bill — the trial suspends rather than
charging — it is an instance left running over a weekend. Hence:

    bin/vm --down

## Cleaning up when the project is over

Deleting the instance and its disk removes everything on the VM side. On the
laptop the only residue is the SSH alias block `gcloud` writes into
`~/.ssh/config`, which comes out with:

    gcloud compute config-ssh --remove
