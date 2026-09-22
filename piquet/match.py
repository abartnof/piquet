"""Running deals between two agents, and recording every decision.

The move log is written from the very first deal rather than retrofitted,
because the point of it is to correlate training effort against skill gained,
and that analysis is only possible if the record goes back to the beginning.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from piquet.agents import Agent
from piquet.observation import view_for
from piquet.rules import Deal, Phase, deal_shuffled
from piquet.scoring import Category, Player, ScoreLog

__all__ = ["Decision", "DealRecord", "play_deal", "play_deals", "write_jsonl"]


@dataclass(frozen=True, slots=True)
class Decision:
    """One choice by one agent, with the alternatives it had."""

    ply: int
    player: str
    phase: str
    agent: str
    hand: str
    choice: str
    #: How many options were available. A choice among one is not a decision.
    options: int


@dataclass(slots=True)
class DealRecord:
    """Everything that happened in one deal, and how it came out."""

    deal: int
    elder_agent: str
    younger_agent: str
    decisions: list[Decision] = field(default_factory=list)
    elder_score: int = 0
    younger_score: int = 0
    elder_tricks: int = 0
    bonus: Optional[str] = None

    def as_dict(self) -> dict:
        return asdict(self)


def _finish_record(record: DealRecord, deal: Deal) -> DealRecord:
    record.elder_score = deal.log.total(Player.ELDER)
    record.younger_score = deal.log.total(Player.YOUNGER)
    record.elder_tricks = deal.tricks_won(Player.ELDER)
    for event in deal.log:
        if event.category is Category.BONUS:
            record.bonus = f"{event.player} {event.detail}"
    return record


def play_deal(
    elder: Agent,
    younger: Agent,
    rng: Optional[random.Random] = None,
    deal: Optional[Deal] = None,
    record: Optional[DealRecord] = None,
) -> tuple[Deal, Optional[DealRecord]]:
    """Play one deal to completion, asking each agent in turn.

    Pass a `deal` to replay a specific one; otherwise a fresh one is shuffled.
    """
    deal = deal if deal is not None else deal_shuffled(rng)
    agents = {Player.ELDER: elder, Player.YOUNGER: younger}
    ply = 0

    def note(player: Player, choice: str, options: int, view) -> None:
        nonlocal ply
        ply += 1
        if record is not None:
            record.decisions.append(
                Decision(
                    ply=ply,
                    player=str(player),
                    phase=deal.phase.value,
                    agent=agents[player].name,
                    hand=view.hand.code,
                    choice=choice,
                    options=options,
                )
            )

    for player in (Player.ELDER, Player.YOUNGER):
        view = view_for(deal, player)
        discard = agents[player].exchange(view)
        note(player, discard.code, view.exchange_limit, view)
        deal = deal.exchange(player, discard)

    while deal.to_declare is not None:
        player = deal.to_declare
        category = deal.declaring_category
        view = view_for(deal, player)
        declaration = agents[player].declare(view, category)
        note(player, str(declaration), 2, view)
        deal = deal.declare(player, declaration)

    while deal.phase is Phase.PLAY:
        player = deal.to_play
        view = view_for(deal, player)
        card = agents[player].play(view)
        note(player, card.code, len(view.legal_plays), view)
        deal = deal.play(player, card)

    if record is not None:
        _finish_record(record, deal)
    return deal, record


def play_deals(
    elder: Agent,
    younger: Agent,
    count: int,
    rng: Optional[random.Random] = None,
    keep_records: bool = True,
) -> tuple[list[Deal], list[DealRecord]]:
    """Play many deals between the same pair of agents."""
    rng = rng or random.Random()
    deals: list[Deal] = []
    records: list[DealRecord] = []
    for index in range(count):
        record = (
            DealRecord(deal=index, elder_agent=elder.name, younger_agent=younger.name)
            if keep_records
            else None
        )
        played, done = play_deal(elder, younger, rng=rng, record=record)
        deals.append(played)
        if done is not None:
            records.append(done)
    return deals, records


def write_jsonl(records: Iterable[DealRecord], path: str | Path) -> Path:
    """Write the move log, one JSON object per deal.

    One deal per line keeps the decisions attached to the outcome they led to,
    which is what the epochs-against-skill analysis will need.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.as_dict(), separators=(",", ":")) + "\n")
    return path
