"""The card-art pipeline: what it cuts from the pinned originals, and what it
writes. Run with the project's pytest:

    .venv/bin/pytest -q web3d/tools
"""

import io
import xml.etree.ElementTree as ET

import pytest

import art

SVG = "{http://www.w3.org/2000/svg}"


def test_the_piquet_pack_is_thirty_two_cards_in_protocol_codes():
    codes = art.piquet_codes()
    assert len(codes) == 32 == len(set(codes))
    assert {c[0] for c in codes} == set("AKQJT987")
    assert {c[1] for c in codes} == set("SHDC")


@pytest.mark.parametrize("code, index", [
    ("AS", 0), ("KS", 12), ("7S", 6), ("TS", 9),     # spades: A 2 ... 10 J Q K
    ("AH", 13), ("QH", 24),                          # then hearts
    ("AC", 26), ("JC", 36),                          # then clubs
    ("AD", 39), ("7D", 45),                          # then diamonds
])
def test_a_code_finds_its_cell_in_the_deck(code, index):
    # The deck's order is A 2 .. 10 J Q K of spades, hearts, clubs, diamonds
    # (web3d/art/source/SOURCES.md), which is not the protocol's suit order.
    assert art.deck_index(code) == index


def test_each_card_svg_is_framed_on_its_own_cell():
    faces = art.face_svgs()
    assert sorted(faces) == sorted(art.piquet_codes())
    root = ET.fromstring(faces["JC"])
    col, row = 36 % 9, 36 // 9
    assert root.get("viewBox") == f"{750 * col} {1050 * row} 750 1050"
    # The deck's root style (even-odd fills) is inherited by every path; a card
    # cut out without it fills some shapes wrongly.
    assert "fill-rule:evenodd" in root.get("style")
    groups = root.findall(f"{SVG}g")
    assert len(groups) == 1
    assert groups[0].get("transform") == "matrix(0.24,0,0,0.24,375,4725)"


def test_the_back_is_reframed_to_five_by_seven_without_the_old_border():
    root = ET.fromstring(art.back_svg())
    x, y, w, h = map(float, root.get("viewBox").split())
    assert (x, y) == (0, 0)
    assert abs(w / h - 5 / 7) < 1e-6
    text = art.back_svg()
    # Our adaptation: flat white instead of the grey gradient, and no black
    # stroke -- the 3D ink line draws the card's edge.
    assert "url(#b)" not in text
    assert 'stroke="#000"' not in text


def test_the_images_are_opaque_on_a_white_matte():
    from PIL import Image
    image = Image.open(io.BytesIO(art.webp(art.rasterise(art.face_svgs()["AS"], 64))))
    assert image.mode == "RGB"
    # Outside the rounded corner: white, give or take the lossy encoding.
    assert min(image.getpixel((0, 0))) >= 250
