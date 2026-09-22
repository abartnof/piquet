"""Tests for what a declaration actually gives away.

Declaring is an exchange of points for information, so exactly *how much*
information is the hinge the whole game turns on. Three separate things happen:

- You **announce** a shape -- "point of five" -- and never a suit.
- If your combination scores, or ties, the opponent may **ask to see it**, and
  the cards become public.
- If it is beaten it scores nothing and is never shown, so you have given away
  the shape of your hand without giving away the suit.
"""

from piquet.cards import Suit
from piquet.combos import Point
from piquet.observation import view_for
from piquet.rules import Declaration
from piquet.scoring import Category, Player

from tests.helpers import declaring

E, Y = Player.ELDER, Player.YOUNGER

# Elder holds eight spades; younger seven diamonds. Elder wins point.
LOPSIDED = dict(
    elder="AS KS QS JS TS 9S 8S 7S AH KH QH JH",
    younger="AD KD QD JD TD 9D 8D AC KC QC JC TC",
)

# Both hold a four-card point worth 41. An exact tie.
TIED_POINT = dict(
    elder="AS KS QS JS 7H 8H 9H 7C 8C 9C 7D 8D",
    younger="AD KD QD JD TH JH QH TC JC QC TS 9S",
)


def declare_point(deal, player):
    return deal.declare(
        player, Declaration.full(deal.hand_of(player), Category.POINT)
    )


# --------------------------------------------------------------------------
# What is said aloud
# --------------------------------------------------------------------------


def test_younger_hears_elders_declaration_before_she_must_answer_it():
    deal = declare_point(declaring(**LOPSIDED), E)
    heard = view_for(deal, Y).awaiting_answer
    assert heard is not None
    assert heard.category is Category.POINT
    assert heard.primary == 8


def test_an_announcement_names_a_shape_and_never_a_suit():
    """"Point of five", not "five spades". The suit is what stays private."""
    deal = declare_point(declaring(**LOPSIDED), E)
    heard = view_for(deal, Y).awaiting_answer
    assert str(heard) == "point of 8"
    assert not hasattr(heard, "suit")


def test_sequences_are_announced_by_their_french_name():
    from piquet.rules import Announcement

    assert str(Announcement(Category.SEQUENCES, 3, 14)) == "tierce"
    assert str(Announcement(Category.SEQUENCES, 5, 14)) == "quint"
    assert str(Announcement(Category.SEQUENCES, 8, 14)) == "huitième"


def test_sets_are_announced_by_size():
    from piquet.rules import Announcement

    assert str(Announcement(Category.SETS, 4, 14)) == "quatorze"
    assert str(Announcement(Category.SETS, 3, 14)) == "trio"


def test_elder_hears_nothing_while_it_is_his_turn_to_speak():
    assert view_for(declaring(**LOPSIDED), Y).awaiting_answer is None
    assert view_for(declaring(**LOPSIDED), E).awaiting_answer is None


def test_a_sink_announces_nothing_at_all():
    deal = declaring(**LOPSIDED).declare(E, Declaration.sink())
    assert view_for(deal, Y).awaiting_answer is None


def test_both_players_hear_what_the_other_announced():
    deal = declare_point(declare_point(declaring(**LOPSIDED), E), Y)
    assert [a.primary for a in view_for(deal, Y).heard] == [8]
    assert [a.primary for a in view_for(deal, E).heard] == [7]


# --------------------------------------------------------------------------
# What must be shown
# --------------------------------------------------------------------------


def test_a_combination_that_scores_must_be_shown():
    """Either player "may ask to see any combination that has been scored for"."""
    deal = declare_point(declare_point(declaring(**LOPSIDED), E), Y)
    seen = view_for(deal, Y).seen
    assert len(seen) == 1
    assert isinstance(seen[0], Point)
    assert seen[0].suit is Suit.SPADES, "the winning point's suit is now public"


def test_a_beaten_declaration_is_never_shown():
    """Younger loses the point, so she gave away the shape of her hand -- seven
    cards in some suit -- without giving away which suit."""
    deal = declare_point(declare_point(declaring(**LOPSIDED), E), Y)
    assert view_for(deal, E).seen == ()
    assert [a.primary for a in view_for(deal, E).heard] == [7]


def test_an_equal_declaration_is_shown_to_both():
    """"...or which caused no score because of equality"."""
    deal = declare_point(declare_point(declaring(**TIED_POINT), E), Y)
    assert deal.results[-1].winner is None
    assert len(view_for(deal, E).seen) == 1
    assert len(view_for(deal, Y).seen) == 1


def test_sinking_gives_away_nothing_whatever():
    """The whole purchase: no points, but no information either."""
    deal = declaring(**LOPSIDED).declare(E, Declaration.sink())
    deal = declare_point(deal, Y)
    assert view_for(deal, Y).heard == ()
    assert view_for(deal, Y).seen == ()


def test_the_outcome_of_a_category_is_public_even_when_nothing_is_shown():
    """The scores are called aloud, so you always know who won -- you simply do
    not always get to see what they won with."""
    deal = declare_point(declare_point(declaring(**LOPSIDED), E), Y)
    assert view_for(deal, Y).outcomes == ((Category.POINT, E),)
    assert view_for(deal, E).outcomes == ((Category.POINT, E),)


def test_understating_a_point_reveals_only_the_smaller_shape():
    """Cavendish's manoeuvre: declaring five spades while holding eight. The
    opponent hears five, and if it wins, sees only the five cards claimed."""
    deal = declaring(**LOPSIDED)
    understated = Declaration.of(Point(Suit.SPADES, 5, 11 + 10 + 10 + 10 + 10))
    deal = deal.declare(E, understated)
    assert view_for(deal, Y).awaiting_answer.primary == 5

    deal = declare_point(deal, Y)
    assert deal.results[-1].winner is Y, "the understatement loses the category"
    assert view_for(deal, Y).seen == (), "and so is never shown"
