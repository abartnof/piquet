#!/usr/bin/env python3
"""Emit a large corpus of played deals, for the Rust to replay and compare.

The golden vectors pin a handful of hand-chosen positions. They are a
*specification*, and a good one, but they cover five packs. This covers
thousands, and its job is different: to find the divergence nobody thought to
write a case for.

Deterministic agents only -- erraticism zero and the BALANCED style, which
never draws for a decision. That is the only seam through which two languages
can be compared move for move at all.

The corpus is deliberately **not committed**. It is large, it is regenerable,
and a fixture nobody reads is not worth versioning; the vectors are the things
meant to be read.

    python tools/differential.py 2000 > /tmp/corpus.jsonl
"""

from __future__ import annotations

import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from piquet.cards import full_deck
from piquet.heuristics import MAX_LEVEL, HeuristicAgent
from piquet.match import play_deal
from piquet.rules import deal_from
from piquet.scoring import Player
from piquet.solver import SolverAgent
from piquet.style import BALANCED


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    # "solver" swaps elder for rung five. Far slower per deal, so it is asked
    # for separately rather than mixed in by default.
    kind = sys.argv[2] if len(sys.argv) > 2 else "ladder"
    # A seed is fine here: the packs are written into the corpus in full, so
    # the Rust never needs to reproduce the generator -- only to replay what
    # it is handed. That is the distinction §2.1 draws.
    rng = random.Random(20260924)
    deck = list(full_deck())

    for index in range(count):
        cards = deck[:]
        rng.shuffle(cards)
        elder_level = 1 + index % MAX_LEVEL
        younger_level = 1 + (index // MAX_LEVEL) % MAX_LEVEL

        if kind == "solver":
            elder = SolverAgent(style=BALANCED, erraticism=0.0, name="solver8")
            elder_level = 5
        else:
            elder = HeuristicAgent(level=elder_level, style=BALANCED, erraticism=0.0)
        younger = HeuristicAgent(level=younger_level, style=BALANCED, erraticism=0.0)
        deal, _ = play_deal(elder, younger, deal=deal_from(cards))

        print(
            json.dumps(
                {
                    "pack": [c.code for c in cards],
                    "elder_level": elder_level,
                    "younger_level": younger_level,
                    "elder_score": deal.log.total(Player.ELDER),
                    "younger_score": deal.log.total(Player.YOUNGER),
                    "elder_tricks": deal.tricks_won(Player.ELDER),
                    "played": [t.led.code for t in deal.tricks]
                    + [t.followed.code for t in deal.tricks],
                    "events": [
                        [e.player.value, e.amount, e.category.name, e.detail]
                        for e in deal.log
                    ],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
