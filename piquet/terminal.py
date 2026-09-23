"""The terminal table: a person against the engine.

The engine has never had a player. This is the smallest thing that gives it
one, and it is deliberately a *client* of everything underneath rather than a
layer inside it -- the human is an `Agent` like any other, so `match` and
`partie` run a person and a bot with the same loop they run two bots with.

Two rules shape it. **The table never shows a player anything the rules do
not**: every line rendered comes out of a `View`, so the display cannot leak
what the opponent holds even by accident. And **it does the arithmetic a
person at a real table would not have to do in their head**: your own
combinations are named for you, because you can see your own cards, and the
scoreboard says how far you are from the rubicon and what the odds are,
because failing to cross it costs the sum of both scores rather than the
difference and a bare number does not say that.

The rendering is pure functions of a `View` and the input is a small injected
console, so the interesting parts are testable and the shell around them is
thin.
"""

from __future__ import annotations

import random
from typing import Callable, Optional, Sequence as TypingSequence

from piquet.agents import Agent
from piquet.cards import Card, Hand, Suit
from piquet.chances import chance_of, in_words
from piquet.combos import CardSet, Point, Sequence, best_point, sequences, sets
from piquet.heuristics import HeuristicAgent
from piquet.observation import View
from piquet.partie import RUBICON, Partie, Side
from piquet.rules import Declaration, Deal
from piquet.scoring import Category, Player, ScoreLog
from piquet.solver import SolverAgent
from piquet.style import Style

__all__ = [
    "render_hand", "render_combinations", "render_standing", "render_trick",
    "render_events", "HumanAgent", "Console", "Table", "name_for", "OPPONENTS",
    "main",
]

#: Suits in the order a player expects to see them laid out.
_DISPLAY_ORDER = (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)

#: How wide a card's name is drawn, so the columns line up under the tens.
_CELL = 5


def _name(card: Card) -> str:
    """What to call a card at a person, and what they may type back.

    `Card.code` spells the ten "T", which is canonical for serialisation and
    opaque to somebody meeting card codes for the first time. `Card.parse`
    accepts "10D" and "TD" alike, so the friendlier one is free.
    """
    return f"{card.rank.label}{card.suit.letter}"


# --------------------------------------------------------------------------
# Turning state into words
# --------------------------------------------------------------------------


def render_hand(hand: Hand, legal: Optional[Hand] = None) -> str:
    """A hand laid out by suit, highest first, legal plays in brackets.

    Every card is drawn as the code you would type to name it. An earlier
    version drew the ranks alone under a suit symbol -- "♠  K J 7" -- which is
    prettier and, the first person to sit down at it discovered, unusable:
    the table spoke in symbols and the prompt wanted letters, and nothing
    anywhere said how to get from one to the other. The display and the input
    are now the same language, so there is nothing to translate.

    A void suit is not drawn at all: an empty row is a line of noise, and what
    you are void in is something you already know.
    """
    rows = []
    if legal is not None and legal == hand:
        legal = None        # nothing is narrowed, so nothing is worth marking
    for suit in _DISPLAY_ORDER:
        ranks = hand.ranks_in(suit)
        if not ranks:
            continue
        cells = []
        for rank in ranks:
            card = Card(rank, suit)
            marked = legal is not None and card in legal
            drawn = f"[{_name(card)}]" if marked else f" {_name(card)} "
            cells.append(drawn.ljust(_CELL))
        rows.append(f"  {suit.symbol} " + "".join(cells).rstrip())
    return "\n".join(rows)


def _for_example(hand: Hand, count: int = 2) -> str:
    """Two cards out of the player's own hand, to show the shape of an answer.

    A worked example beats a description of a format, and one drawn from the
    cards actually in front of them cannot be mistaken for a rule about which
    cards to throw.
    """
    cards = list(hand)
    picked = [cards[0], cards[-1]][:count] if len(cards) > 1 else cards[:1]
    return " or ".join(_name(card) for card in picked)


def render_combinations(hand: Hand) -> str:
    """What this hand can declare, spelled out.

    Not a hint. It is your own hand, and a person at a real table can see it;
    making them total their own pips is the difference between a game and a
    spreadsheet.
    """
    point = best_point(hand)
    parts = [f"point of {point.length} ({point.pip_value})"] if point else []
    runs = sequences(hand)
    parts.append(" and ".join(str(s) for s in runs) if runs else "no sequence")
    found = sets(hand)
    parts.append(" and ".join(str(s) for s in found) if found else "no set")
    return "  ·  ".join(parts)


def render_standing(view: View, opponent: str, full: bool = True) -> str:
    """The scoreboard, and what it means.

    Late in a partie the score alone is not the useful fact. A player who is
    short of a hundred pays the *sum* of both scores instead of the
    difference, so they are playing a different game from one who is not, and
    what they need to know is the distance and the odds. `chances` can answer
    that because the uncertainty is over the deck and their own play, with no
    opponent model in it at all.

    Which chair you are in is the other thing a player cannot otherwise work
    out. It changes every deal, and it is why the discard is sometimes five
    cards and sometimes three -- a player who has not been told will read that
    as the table misbehaving.

    `full=False` drops the seat gloss and the rubicon line. Neither can change
    inside a deal, so saying them at every prompt is noise; the table says
    them once, when the deal opens.
    """
    standing = view.partie
    if standing is None:
        return ""
    deals = standing.deals_left
    plural = "" if deals == 1 else "s"
    elder = view.me is Player.ELDER
    mine, theirs = ("elder", "younger") if elder else ("younger", "elder")
    lines = [
        f"  you ({mine}) {standing.mine}  ·  {opponent} ({theirs}) {standing.theirs}"
        f"   ·  {deals} deal{plural} to play"
    ]
    if full:
        lines.append(
            "  you exchange first, up to five, and lead to the first trick"
            if elder else
            f"  {opponent} exchanges first and leads; you take what he leaves"
        )
        needed = RUBICON - standing.mine
        if needed > 0:
            odds = chance_of(needed, deals, elder)
            lines.append(f"  {needed} more to cross the rubicon — {in_words(odds)}")
    return "\n".join(lines)


def render_trick(view: View, opponent: str) -> str:
    """The card on the table, and whether you are held to its suit."""
    trick = view.current_trick
    if trick is None:
        return ""
    if trick.leader is view.me:
        return f"  you lead {trick.led}"
    line = f"  {opponent} leads {trick.led}"
    if view.hand.in_suit(trick.led.suit):
        line += f" — you must follow {trick.led.suit.name.lower()}s"
    return line


def render_events(
    log: ScoreLog,
    since: int,
    me: Optional[Player] = None,
    mine: str = "you",
    theirs: str = "your opponent",
) -> tuple[list[str], int]:
    """Whatever has been reckoned since last time, and a new watermark.

    Scores are called aloud, so the whole log is public; the table's job is
    only to avoid reading it out twice, and to say "you" where the engine
    says "elder" -- which seat you are in changes every deal and is not how
    anyone would put it to your face.
    """
    events = list(log)
    lines = []
    for event in events[since:]:
        who = str(event.player) if me is None else (
            mine if event.player is me else theirs
        )
        verb = "score" if who.lower() == "you" else "scores"
        what = event.detail or event.category.name.lower().replace("_", " ")
        lines.append(f"  {who} {verb} {event.amount} for {what}")
    return lines, len(events)


# --------------------------------------------------------------------------
# The person
# --------------------------------------------------------------------------


class Console:
    """Where the table reads and writes. Injected, so nothing needs a tty."""

    def __init__(self, write: Callable = print, read: Callable = input) -> None:
        self._write, self._read = write, read

    def write(self, text: str = "") -> None:
        self._write(text)

    def read(self, prompt: str = "") -> str:
        return self._read(prompt)


def _understatements(hand: Hand, category: Category) -> list[Declaration]:
    """Lesser declarations the hand genuinely supports.

    Cavendish's examples of sinking are all partial -- "he calls five cards,
    and declares five spades, when he might have six"; a quart to the knave
    called as a tierce to the knave; a quatorze called as a trio. A teaching
    game that offered only all-or-nothing would have hidden the interesting
    move in the game.
    """
    if category is Category.POINT:
        point = best_point(hand)
        if point and point.length > 1:
            ranks = hand.ranks_in(point.suit)[: point.length - 1]
            return [Declaration.of(Point(
                suit=point.suit,
                length=point.length - 1,
                pip_value=sum(r.pip_value for r in ranks),
            ))]
        return []

    if category is Category.SEQUENCES:
        runs = sequences(hand)
        if runs and runs[0].length > 3:
            shorter = Sequence(runs[0].suit, runs[0].top, runs[0].length - 1)
            return [Declaration.of(shorter, *runs[1:])]
        return []

    found = sets(hand)
    if found and found[0].count == 4:
        return [Declaration.of(CardSet(found[0].rank, 3), *found[1:])]
    return []


class HumanAgent:
    """A person, wearing the `Agent` protocol so the engine cannot tell."""

    def __init__(
        self,
        console: Console,
        name: str = "you",
        opponent: str = "your opponent",
    ) -> None:
        self.console = console
        self.name = name
        self.opponent = opponent
        self._narrated = 0
        self._opened = False

    # -- the board ---------------------------------------------------------

    def _show(self, view: View, legal: Optional[Hand] = None) -> None:
        if len(view.log) < self._narrated:
            self._narrated, self._opened = 0, False     # a fresh deal
        lines, self._narrated = render_events(
            view.log, self._narrated, view.me, self.name, self.opponent
        )

        self.console.write("")
        standing = render_standing(view, self.opponent, full=not self._opened)
        self._opened = True
        if standing:
            self.console.write(standing)
        for line in lines:
            self.console.write(line)
        trick = render_trick(view, self.opponent)
        if trick:
            self.console.write(trick)
        self.console.write(render_hand(view.hand, legal))

    # -- the three decisions ----------------------------------------------

    def exchange(self, view: View) -> Hand:
        limit = view.exchange_limit
        self._show(view)
        self.console.write(f"  {render_combinations(view.hand)}")
        self.console.write(
            f"  name 1 to {limit} cards to throw, and draw as many back"
            f" — like {_for_example(view.hand)}"
        )
        while True:
            tokens = self.console.read("  discard: ").replace(",", " ").split()
            if not 1 <= len(tokens) <= limit:
                self.console.write(
                    f"  between 1 and {limit} cards, and at least one is compulsory"
                )
                continue
            try:
                cards = [Card.parse(token) for token in tokens]
            except ValueError:
                self.console.write(
                    f"  name each card by rank and suit, like {_for_example(view.hand)}"
                )
                continue
            if len(set(cards)) != len(cards):
                self.console.write("  each card once")
                continue
            if any(card not in view.hand for card in cards):
                self.console.write("  you do not hold all of those")
                continue
            return Hand.of(*cards)

    def declare(self, view: View, category: Category) -> Declaration:
        full = Declaration.full(view.hand, category)
        self._show(view)
        if view.awaiting_answer is not None:
            self.console.write(f"  {self.opponent} calls {view.awaiting_answer}")
        if not full:
            self.console.write(f"  you have no {category.name.lower()} to call")
            return full

        options = [full, Declaration.sink()] + _understatements(view.hand, category)
        self.console.write(f"  {category.name.lower()}:")
        for number, option in enumerate(options, start=1):
            if option == Declaration.sink():
                label = "say nothing, and give up the category"
            elif option is full:
                label = f"call {option} — {option.score} points if it is good"
            else:
                label = f"call only {option} — sinking the rest"
            self.console.write(f"    {number}) {label}")
        while True:
            raw = self.console.read("  which: ").strip() or "1"
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            self.console.write(f"  a number from 1 to {len(options)}")

    def play(self, view: View) -> Card:
        legal = view.legal_plays
        self._show(view, legal)
        if legal != view.hand:
            self.console.write("  the bracketed cards are the ones you may play")
        while True:
            raw = self.console.read("  your card: ").strip()
            try:
                card = Card.parse(raw)
            except ValueError:
                self.console.write(
                    f"  name a card by rank and suit, like {_for_example(view.hand)}"
                )
                continue
            if card not in view.hand:
                self.console.write("  you do not hold that one")
                continue
            if card not in legal:
                led = view.current_trick.led.suit.name.lower()
                self.console.write(f"  you must follow {led}s while you can")
                continue
            return card


# --------------------------------------------------------------------------
# The opponents
# --------------------------------------------------------------------------

#: A rung of the ladder for each step the game took towards being understood.
OPPONENTS: dict[int, tuple[str, str]] = {
    1: ("Rabelais", "listed the game in 1535 and explained none of it"),
    2: ("Cotton", "wrote the first English rules, 1674"),
    3: ("Hoyle", "computed the odds on the discard, 1744"),
    4: ("Cavendish", "codified the laws for the Portland Club, 1892"),
    5: ("Kempelen", "the machine that plays the endgame out exactly"),
}


def name_for(level: int) -> str:
    return OPPONENTS[level][0]


def make_opponent(
    level: int, erraticism: float = 0.0, rng: Optional[random.Random] = None
) -> Agent:
    """A named opponent at the given rung, with a style drawn once and kept.

    Once per opponent and held for the whole partie, which is what makes a
    habit readable -- Cavendish's worked example of spotting a sink opens
    "your adversary, for instance, is a player who rarely discards from his
    point", and that inference only works against someone who *has* one.
    """
    rng = rng or random.Random()
    style = Style.random(rng)
    name = name_for(level)
    if level >= 5:
        return SolverAgent(style=style, erraticism=erraticism, rng=rng, name=name)
    return HeuristicAgent(level, style, erraticism, rng, name)


# --------------------------------------------------------------------------
# The table
# --------------------------------------------------------------------------


class Table:
    """Two players, six deals, and a running commentary."""

    def __init__(
        self,
        side_a: Agent,
        side_b: Agent,
        console: Optional[Console] = None,
        rng: Optional[random.Random] = None,
        opening_dealer: Side = Side.A,
    ) -> None:
        self.sides = (side_a, side_b)
        self.console = console or Console()
        self.rng = rng or random.Random()
        self.opening_dealer = opening_dealer

    def _after_deal(self, deal: Deal, partie: Partie) -> None:
        outcome = partie.outcomes[-1]
        elder, younger = outcome.elder, outcome.elder.other
        self.console.write(
            f"\n  deal {outcome.number}: "
            f"{self.sides[elder.index].name} (elder) {outcome.score_of(elder)}"
            f"  ·  {self.sides[younger.index].name} {outcome.score_of(younger)}"
        )
        bonus = [e for e in deal.log if e.category.name == "BONUS"]
        for event in bonus:
            self.console.write(f"  {event}")
        self.console.write(
            f"  running: {self.sides[0].name} {partie.totals[0]}"
            f"  ·  {self.sides[1].name} {partie.totals[1]}"
        )

    def play(self) -> Partie:
        from piquet.match import play_partie

        self.console.write(
            f"\n  {self.sides[0].name} against {self.sides[1].name}"
            f" — six deals, and the rubicon at {RUBICON}.\n"
        )
        partie, _ = play_partie(
            self.sides[0],
            self.sides[1],
            rng=self.rng,
            opening_dealer=self.opening_dealer,
            keep_records=False,
            on_deal=self._after_deal,
        )
        settlement = partie.settlement
        if settlement.winner is None:
            self.console.write("\n  the partie is drawn.")
        else:
            self.console.write(
                f"\n  {self.sides[settlement.winner.index].name} {settlement}"
            )
        return partie


def choose_opponent(console: Console) -> tuple[int, float]:
    """Ask who to play and how steady they are. The two skill dials, and no
    more: strength is a named capability and erraticism is how reliably it is
    brought to bear, which between them are a whole person."""
    console.write("\n  Piquet — a partie of six deals.\n")
    for level, (name, gloss) in sorted(OPPONENTS.items()):
        console.write(f"    {level}) {name:<12} {gloss}")

    def ask(prompt: str, default: str, read) -> float:
        while True:
            raw = console.read(f"\n  {prompt} [{default}]: ").strip() or default
            try:
                return read(raw)
            except ValueError:
                console.write("  a number, please")

    level = int(ask("which opponent", "3", lambda r: max(1, min(5, int(r)))))
    erraticism = ask("how erratic, 0 to 1", "0.2",
                     lambda r: max(0.0, min(1.0, float(r))))
    return level, erraticism


def main(
    argv: Optional[TypingSequence[str]] = None,
    console: Optional[Console] = None,
    rng: Optional[random.Random] = None,
) -> int:
    """Sit a person down opposite one of the named opponents."""
    console = console or Console()
    rng = rng or random.Random()
    level, erraticism = choose_opponent(console)
    you = HumanAgent(console, name="you", opponent=name_for(level))
    them = make_opponent(level, erraticism, rng)
    # You deal the first, and so sit elder in the critical sixth deal -- which
    # pagat says is why the winner of the cut should choose to deal.
    Table(you, them, console=console, rng=rng, opening_dealer=Side.A).play()
    return 0
