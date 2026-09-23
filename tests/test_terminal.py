"""Tests for the terminal table.

A user interface is mostly untestable and mostly does not need testing. What
does need it is the part that turns state into words, and the part that turns
a person's typing into a legal move -- so those are pure functions and a small
agent with its input and output injected, and the shell around them is thin.

The rule this file enforces more than any other: **the table never shows a
player anything the rules do not.** Everything rendered comes out of a `View`.
"""

import random

import pytest

from piquet.cards import Card, Hand, parse_hand
from piquet.observation import view_for
from piquet.partie import Standing
from piquet.rules import Declaration, deal_shuffled
from piquet.scoring import Category, Player
from piquet.terminal import (
    HumanAgent,
    choose_opponent,
    make_opponent,
    Table,
    name_for,
    render_combinations,
    render_events,
    render_hand,
    render_standing,
    render_trick,
)

from tests.helpers import declaring, skip_declarations

E, Y = Player.ELDER, Player.YOUNGER


class Script:
    """A console that reads from a list and remembers what was written."""

    def __init__(self, *lines):
        self.lines = list(lines)
        self.out = []

    def write(self, text=""):
        self.out.append(str(text))

    def read(self, prompt=""):
        if not self.lines:
            raise AssertionError(f"nothing left to answer {prompt!r} with")
        return self.lines.pop(0)

    @property
    def shown(self):
        return "\n".join(self.out)


# --------------------------------------------------------------------------
# Turning state into words
# --------------------------------------------------------------------------


def test_a_hand_is_shown_in_the_language_the_prompt_wants_back():
    """The first person to sit at this table could not tell what to type. The
    hand was drawn as "♠  K J 7" and the prompt wanted "KS", with nothing
    anywhere to get you from one to the other. Now they are the same words."""
    hand = parse_hand("7S AS KS 9H QH AD TD KC QC 9C 8C 7C")
    shown = " ".join(render_hand(hand).split())
    assert "AS KS 7S" in shown, "spades, high to low, named as you would type them"
    assert "10D" in shown, "and the ten spelled out rather than left as T"
    assert shown.index("♠") < shown.index("♣"), "a stable suit order"


def test_a_card_can_be_named_with_the_symbol_it_was_drawn_with():
    """If the table draws you a spade as ♠ it should take ♠ back."""
    assert Card.parse("K♠") == Card.parse("KS")
    assert Card.parse("10♥") == Card.parse("TH")


def test_a_suit_the_hand_is_void_in_is_not_drawn_as_an_empty_row():
    assert "♥" not in render_hand(parse_hand("AS KS QS JS"))


def test_the_cards_you_may_legally_play_are_marked():
    hand = parse_hand("AS KS 9H QH AD TD KC QC")
    legal = parse_hand("AS KS")
    shown = render_hand(hand, legal)
    assert "[AS]" in shown and "[KS]" in shown
    assert "[QC]" not in shown, "clubs are not legal here"


def test_your_own_combinations_are_named_for_you():
    """Not a hint -- it is your hand, and a person at a real table can see it.
    Doing the arithmetic for them is the difference between a game and a
    spreadsheet."""
    shown = render_combinations(parse_hand("AS KS QS JS TS 9H 8H AD KD QC JC TC"))
    assert "point of 5" in shown
    assert "quint" in shown
    assert "quatorze" not in shown


def test_a_hand_with_no_sequence_and_no_set_is_told_so():
    """There is always a point -- every hand has a longest suit -- so the
    absences worth naming are the other two."""
    shown = render_combinations(parse_hand("AS 9S 7S TH 8H AD 9D 7D KC TC 8C 7C"))
    assert "point of 4" in shown
    assert "no sequence" in shown and "no set" in shown


def test_the_trick_names_who_led_and_what_you_must_follow():
    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    deal = deal.play(E, Card.parse("AS"))
    shown = render_trick(view_for(deal, Y), "Cavendish")
    assert "Cavendish" in shown
    assert "A♠" in shown
    assert "spade" in shown.lower(), "and that she is held to the suit"


def test_nothing_is_drawn_for_a_trick_that_has_not_been_led_to():
    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    assert render_trick(view_for(deal, E), "Cavendish") == ""


def test_the_log_is_read_back_in_the_second_person():
    """"elder scores 6 for point of 6" is how the engine records it and not
    how anyone would say it to your face."""
    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    deal = deal.play(E, Card.parse("AS"))
    yours, _ = render_events(deal.log, 0, me=E, theirs="Cavendish")
    assert "you score 1 for leads A\u2660" in yours[0]
    hers, _ = render_events(deal.log, 0, me=Y, theirs="Cavendish")
    assert "Cavendish scores 1 for leads A\u2660" in hers[0]


def test_the_rubicon_line_is_said_once_a_deal_and_not_once_a_move():
    """It cannot change inside a deal -- the partie total is fixed until the
    deal is entered -- so repeating it every prompt is noise."""
    deal = deal_shuffled(random.Random(1674))
    view = view_for(deal, E, Standing(mine=82, theirs=71, deals_left=1))
    assert "rubicon" in render_standing(view, "Cavendish")
    assert "rubicon" not in render_standing(view, "Cavendish", full=False)
    assert "82" in render_standing(view, "Cavendish", full=False)


def test_brackets_are_only_drawn_when_the_choice_is_actually_narrowed():
    """Everything bracketed is everything shouted, which is nothing said."""
    hand = parse_hand("AS KS 9H QH")
    assert "[" not in render_hand(hand, hand)
    assert "[" in render_hand(hand, parse_hand("AS KS"))


def test_events_are_narrated_only_once():
    """The log is public and grows all deal; the table reports what is new."""
    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    deal = deal.play(E, Card.parse("AS"))
    first, seen = render_events(deal.log, 0)
    assert len(first) == 1 and "leads" in first[0]
    again, _ = render_events(deal.log, seen)
    assert again == []


# --------------------------------------------------------------------------
# The scoreboard, which is the drama
# --------------------------------------------------------------------------


def test_the_scoreboard_tells_a_player_which_game_they_are_in():
    """Late in a partie the score alone is not the useful fact. Failing to
    reach a hundred costs you the sum of both scores rather than the
    difference, so what a player needs is the distance and the odds."""
    deal = deal_shuffled(random.Random(1674))
    view = view_for(deal, E, Standing(mine=82, theirs=71, deals_left=1))
    shown = render_standing(view, "Cavendish")
    assert "82" in shown and "71" in shown
    assert "Cavendish" in shown
    assert "18" in shown, "the distance to the rubicon"
    assert "2 in 3" in shown, "and the odds on covering it, from elder's chair"


def test_the_table_says_which_chair_you_are_in():
    """It changes every deal, and it is why the discard is five cards one deal
    and three the next. A player who has not been told reads that as a bug."""
    deal = deal_shuffled(random.Random(1674))
    standing = Standing(mine=10, theirs=10, deals_left=4)
    assert "you (elder)" in render_standing(view_for(deal, E, standing), "Cavendish")
    assert "Cavendish (elder)" in render_standing(view_for(deal, Y, standing), "Cavendish")
    assert "you (younger)" in render_standing(view_for(deal, Y, standing), "Cavendish")


def test_a_player_already_over_the_rubicon_is_not_nagged_about_it():
    deal = deal_shuffled(random.Random(1674))
    view = view_for(deal, E, Standing(mine=140, theirs=71, deals_left=1))
    shown = render_standing(view, "Cavendish")
    assert "rubicon" not in shown.lower()


def test_a_deal_played_outside_a_partie_has_no_scoreboard():
    view = view_for(deal_shuffled(random.Random(1674)), E)
    assert render_standing(view, "Cavendish") == ""


# --------------------------------------------------------------------------
# Turning typing into a legal move
# --------------------------------------------------------------------------


def test_the_person_plays_a_card_by_naming_it():
    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    console = Script("as")
    agent = HumanAgent(console, name="you")
    assert agent.play(view_for(deal, E)) == Card.parse("AS")


def test_an_illegal_card_is_refused_and_the_person_asked_again():
    """The tutor proper comes later, but refusing the impossible is the
    cheapest teaching in the game and it costs nothing to do now."""
    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    deal = deal.play(E, Card.parse("AS"))
    console = Script("ad", "js")          # a diamond, while spades were led
    card = HumanAgent(console, name="you").play(view_for(deal, Y))
    assert card == Card.parse("JS")
    assert "follow" in console.shown.lower()


def test_nonsense_is_refused_without_crashing():
    deal = skip_declarations(declaring(
        elder="AS KS QS AH KH QH 7D 8D 9D 7C 8C 9C",
        younger="JS TS 9S JH TH 9H AD KD QD AC KC QC",
    ))
    console = Script("", "zz", "6H", "AS")
    assert HumanAgent(console, name="you").play(view_for(deal, E)) == Card.parse("AS")


def test_the_person_discards_by_naming_cards():
    deal = deal_shuffled(random.Random(1674))
    console = Script(" ".join(c.code for c in list(deal.hand_of(E))[:5]))
    discard = HumanAgent(console, name="you").exchange(view_for(deal, E))
    assert len(discard) == 5


def test_a_discard_of_the_wrong_size_is_refused():
    deal = deal_shuffled(random.Random(1674))
    hand = list(deal.hand_of(E))
    console = Script(
        " ".join(c.code for c in hand[:6]),      # too many
        "",                                      # too few
        " ".join(c.code for c in hand[:3]),
    )
    discard = HumanAgent(console, name="you").exchange(view_for(deal, E))
    assert len(discard) == 3
    assert "five" in console.shown.lower() or "5" in console.shown


def test_declaring_offers_the_whole_holding_and_the_sink():
    deal = declaring(
        elder="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
        younger="AD KD QD JD TD 9D 8D AC KC QC JC TC",
    )
    console = Script("1")
    declaration = HumanAgent(console, name="you").declare(view_for(deal, E), Category.POINT)
    assert declaration.score == 8
    assert "say nothing" in console.shown.lower()


def test_a_player_may_choose_to_sink():
    deal = declaring(
        elder="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
        younger="AD KD QD JD TD 9D 8D AC KC QC JC TC",
    )
    console = Script("2")
    declaration = HumanAgent(console, name="you").declare(view_for(deal, E), Category.POINT)
    assert declaration == Declaration.sink()


def test_understating_is_offered_because_it_is_the_heart_of_the_game():
    """Cavendish's examples are all partial: "he calls five cards, and declares
    five spades, when he might have six". A teaching game that only offers all
    or nothing has hidden the interesting move."""
    deal = declaring(
        elder="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
        younger="AD KD QD JD TD 9D 8D AC KC QC JC TC",
    )
    console = Script("3")
    declaration = HumanAgent(console, name="you").declare(view_for(deal, E), Category.POINT)
    assert 0 < declaration.score < 8
    assert declaration.claims[0].is_supported_by(deal.hand_of(E))


# --------------------------------------------------------------------------
# The opponents
# --------------------------------------------------------------------------


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_every_rung_has_a_name_worth_meeting(level):
    assert name_for(level) and name_for(level) != str(level)


def test_the_table_runs_a_whole_partie_without_a_person():
    """Two bots at the table, so the loop itself can be exercised."""
    from piquet.heuristics import HeuristicAgent

    console = Script()
    rng = random.Random(1674)
    table = Table(
        HeuristicAgent(2, rng=rng, name="Cotton"),
        HeuristicAgent(3, rng=rng, name="Hoyle"),
        console=console,
        rng=rng,
    )
    partie = table.play()
    assert partie.complete
    assert partie.settlement is not None
    assert "Cotton" in console.shown and "Hoyle" in console.shown
    assert "rubicon" in console.shown.lower() or "wins" in console.shown.lower()


def test_the_two_dials_are_the_only_setup_questions():
    """Strength is a named capability and erraticism is how reliably it is
    brought to bear. Between them that is a whole person, and a third dial
    would be one the player could not form a theory about."""
    console = Script("4", "0.3")
    assert choose_opponent(console) == (4, 0.3)
    assert "Cavendish" in console.shown


def test_the_setup_survives_being_typed_at():
    """Empty takes the default; nonsense asks again; out of range is clamped."""
    console = Script("", "banana", "2")
    assert choose_opponent(console) == (3, 1.0)
    assert "number" in console.shown.lower()


@pytest.mark.slow
def test_an_opponent_carries_one_style_for_the_whole_partie():
    """Cavendish teaches reading the habit, and a habit that changes every
    deal is not one: his worked example of spotting a sink opens "your
    adversary, for instance, is a player who rarely discards from his point".
    So the style is drawn once, at the table, and held through all six deals.
    """
    from piquet.heuristics import HeuristicAgent
    from piquet.match import play_partie

    rng = random.Random(1674)
    agent = make_opponent(4, 0.2, rng)
    before = agent.style
    partie, _ = play_partie(agent, HeuristicAgent(3, rng=rng), rng=rng)
    assert partie.complete
    assert agent.style == before, "and it is the same habit at the end of it"
    assert agent.name == "Cavendish"
