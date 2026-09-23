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

import os
import random
import sys
from typing import Callable, Optional, Sequence as TypingSequence

from piquet.agents import Agent
from piquet.cards import Card, Hand, Suit
from piquet.chances import chance_of, in_words
from piquet.combos import CardSet, Point, Sequence, best_point, sequences, sets
from piquet.heuristics import HeuristicAgent
from piquet.observation import View
from piquet.partie import RUBICON, Partie, Side
from piquet.rules import TRICKS_PER_DEAL, Declaration, Deal, Phase
from piquet.scoring import Category, Player, ScoreLog
from piquet.solver import SolverAgent
from piquet.style import Style

__all__ = [
    "render_hand", "render_combinations", "render_standing", "render_stages",
    "render_briefing",
    "render_trick", "render_events", "HumanAgent", "Console", "Table",
    "Palette", "PLAIN", "detect_palette", "name_for", "OPPONENTS", "main",
]

#: Suits in the order a player expects to see them laid out.
_DISPLAY_ORDER = (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)

#: How wide a card's name is drawn, so the columns line up under the tens.
_CELL = 5

#: Drawn in red. The other two are never painted black: half the world runs a
#: dark terminal and the spades would vanish into it.
_RED_SUITS = (Suit.HEARTS, Suit.DIAMONDS)

#: The spine of a deal, which nobody arrives knowing.
_STAGES = ("exchange", "point", "sequences", "sets", "play")
_STAGE_OF = {
    Phase.ELDER_EXCHANGE: 0,
    Phase.YOUNGER_EXCHANGE: 0,
    Phase.DECLARE_POINT: 1,
    Phase.DECLARE_SEQUENCES: 2,
    Phase.DECLARE_SETS: 3,
    Phase.PLAY: 4,
    Phase.COMPLETE: 4,
}


class Palette:
    """ANSI colour, or nothing at all."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def _wrap(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def red(self, text: str) -> str:
        return self._wrap(text, "31")

    def bold(self, text: str) -> str:
        return self._wrap(text, "1")

    def dim(self, text: str) -> str:
        return self._wrap(text, "2")


#: For anything that is not a terminal, and for the test suite.
PLAIN = Palette(False)


def detect_palette(stream=None) -> Palette:
    """Colour when there is somebody there to see it.

    Off when the output is not a terminal, and off when `NO_COLOR` is set --
    a convention worth honouring rather than a special case to argue about.
    """
    stream = stream if stream is not None else sys.stdout
    if os.environ.get("NO_COLOR"):
        return PLAIN
    isatty = getattr(stream, "isatty", None)
    return Palette(bool(isatty and isatty()))


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


def render_hand(
    hand: Hand, legal: Optional[Hand] = None, palette: Palette = PLAIN
) -> str:
    """A hand laid out by suit, highest first, legal plays in brackets.

    Every card is drawn as the code you would type to name it. An earlier
    version drew the ranks alone under a suit symbol -- "\u2660  K J 7" -- which is
    prettier and, the first person to sit down at it discovered, unusable: the
    table spoke in symbols and the prompt wanted letters, and nothing anywhere
    said how to get from one to the other. The display and the input are now
    the same language, so there is nothing to translate.

    All four suits are always drawn, a void as a dash. Leaving voids out was
    my idea and it was wrong on both counts. Four fixed rows keep the layout
    still, so the eye learns where hearts live instead of re-finding them
    every trick; and a void is a fact you *act* on rather than an absence,
    because it is exactly what lets you throw whatever you like.
    """
    rows = []
    if legal is not None and legal == hand:
        legal = None        # nothing is narrowed, so nothing is worth marking
    for suit in _DISPLAY_ORDER:
        ranks = hand.ranks_in(suit)
        if ranks:
            cells = []
            for rank in ranks:
                card = Card(rank, suit)
                marked = legal is not None and card in legal
                drawn = f"[{_name(card)}]" if marked else f" {_name(card)} "
                cells.append(drawn.ljust(_CELL))
            body = "".join(cells).rstrip()
        else:
            body = " \u2014"
        row = f"  {suit.symbol} {body}"
        rows.append(palette.red(row) if suit in _RED_SUITS else row)
    return "\n".join(rows)


def render_stages(view: View, palette: Palette = PLAIN) -> str:
    """Where in a deal we are, with the whole shape of one around it.

    A deal has a fixed spine and nobody arrives knowing it. Showing all five
    stages with your place among them is a table of contents for a game the
    player is learning while they play it -- and it answers, without being
    asked, why the table wants a discard now and a card later.
    """
    here = _STAGE_OF[view.phase]
    parts = []
    for index, label in enumerate(_STAGES):
        if label == "play":
            trick = min(len(view.tricks) + 1, TRICKS_PER_DEAL)
            label = f"play {trick}/{TRICKS_PER_DEAL}"
        if index == here:
            parts.append(palette.bold(f"[{label}]"))
        elif index < here:
            parts.append(palette.dim(label))
        else:
            parts.append(label)
    return "  " + " \u00b7 ".join(parts)


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


def render_standing(
    view: View, opponent: str, full: bool = True, palette: Palette = PLAIN
) -> str:
    """The scoreboard, and what it means.

    Three things a player cannot work out for themselves. **Which chair they
    are in**, which changes every deal and is why the discard is five cards
    one deal and three the next. **What this deal has added so far**, shown
    beside the total carried in, so a pique can be watched building. And
    **which piquet this is**: a hundred is a finish line to race for in
    *piquet au cent* and a line to clear in the rubicon game, and a player who
    confuses the two will play the last deal wrong.

    Once a player is over the line the interesting question inverts: keeping
    the *opponent* short pays the sum of both scores rather than the
    difference, and that incentive has no counterpart inside a single deal.

    `full=False` keeps only the live line. The rest cannot change inside a
    deal, so the table says it once, when the deal opens.
    """
    standing = view.partie
    if standing is None:
        return ""
    elder = view.me is Player.ELDER
    mine, theirs = ("elder", "younger") if elder else ("younger", "elder")

    def running(banked: int, gained: int) -> str:
        return f"{banked}+{gained}" if gained else str(banked)

    of = standing.number + standing.deals_left - 1
    live = (
        f"  deal {standing.number} of {of}"
        f"   ·   you ({mine}) {running(standing.mine, view.log.total(view.me))}"
        f"   ·   {opponent} ({theirs})"
        f" {running(standing.theirs, view.log.total(view.opponent))}"
    )
    if not full:
        return live
    return "\n".join([live] + render_briefing(view, opponent))


def render_briefing(view: View, opponent: str) -> list[str]:
    """What cannot change inside a deal, so is said once when it opens.

    Which chair you are in, which piquet this is, and how far off the line
    you are. Three things a player cannot work out for themselves and which
    the table would otherwise repeat at every prompt.
    """
    standing = view.partie
    if standing is None:
        return []
    elder = view.me is Player.ELDER
    of = standing.number + standing.deals_left - 1
    lines = [
        "  you exchange first, up to five, and lead to the first trick"
        if elder else
        f"  {opponent} exchanges first and leads; you take what they leave",
        f"  rubicon piquet — all {of} deals are played;"
        f" {RUBICON} is a line to clear, not a finish",
    ]
    needed = RUBICON - standing.mine
    if needed > 0:
        odds = chance_of(needed, standing.deals_left, elder)
        lines.append(f"  you need {needed} more to cross it — {in_words(odds)}")
    else:
        short = RUBICON - standing.theirs
        if short > 0:
            odds = chance_of(short, standing.deals_left, not elder)
            lines.append(
                f"  you are over. {opponent} needs {short} — {in_words(odds)};"
                " short, and they pay the sum"
            )
        else:
            lines.append("  you are both over — the difference is what pays now")
    return lines


def render_trick(view: View, opponent: str, palette: Palette = PLAIN) -> str:
    """The card on the table, and whether you are held to its suit.

    `Suit.name` is already plural, so nothing here adds an "s" to it. An
    earlier version did, and told a player to follow "clubss".
    """
    trick = view.current_trick
    if trick is None:
        return ""
    card = str(trick.led)
    if trick.led.suit in _RED_SUITS:
        card = palette.red(card)
    if trick.leader is view.me:
        return f"  you lead {card}"
    line = f"  {opponent} leads {card}"
    if view.hand.in_suit(trick.led.suit):
        line += f" — you must follow {trick.led.suit.name.lower()}"
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
        palette: Palette = PLAIN,
    ) -> None:
        self.console = console
        self.name = name
        self.opponent = opponent
        self.palette = palette
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
        live = render_standing(view, self.opponent, full=False, palette=self.palette)
        if live:
            self.console.write(live)
        self.console.write(render_stages(view, self.palette))
        if not self._opened:
            for line in render_briefing(view, self.opponent):
                self.console.write(line)
        self._opened = True
        for line in lines:
            self.console.write(line)
        trick = render_trick(view, self.opponent, self.palette)
        if trick:
            self.console.write(trick)
        self.console.write(render_hand(view.hand, legal, self.palette))

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
                self.console.write(f"  you must follow {led} while you can")
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
        palette: Palette = PLAIN,
    ) -> None:
        self.sides = (side_a, side_b)
        self.palette = palette
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
    palette = detect_palette()
    level, erraticism = choose_opponent(console)
    you = HumanAgent(
        console, name="you", opponent=name_for(level), palette=palette
    )
    them = make_opponent(level, erraticism, rng)
    # You deal the first, and so sit elder in the critical sixth deal -- which
    # pagat says is why the winner of the cut should choose to deal.
    Table(
        you, them, console=console, rng=rng,
        opening_dealer=Side.A, palette=palette,
    ).play()
    return 0
