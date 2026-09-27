#!/usr/bin/env python3
"""The card art: cut the pinned originals into the 33 images the table uses.

    .venv/bin/python web3d/tools/art.py [--sheet contact.png]

Reads the two pinned originals in web3d/art/source/ (see SOURCES.md there)
and writes:

  web3d/art/cards/{AS,KS,...,7D}.webp   the 32 piquet faces, 512 x 717
  web3d/art/cards/back.webp             the back, re-framed to 5:7

Both ways of shipping the art (docs/TABLE3D.md section 3.2) start from the
same cut: one standalone SVG per card, framed on its own cell of the deck.
Way A rasterises those here with `rsvg-convert` (apt: librsvg2-bin) and
encodes WebP with Pillow; Way B embeds the SVGs themselves, with their path
data trimmed, and lets the browser rasterise them (web3d/build.py --art svg).

The back is our adaptation of a CC BY-SA 3.0 work: its lace field, re-framed
from Spanish proportions (about 1:1.53) to the faces' 5:7, on flat white with
no drawn border -- the table's ink line draws every card's edge. So the image
this writes is itself CC BY-SA 3.0 (CREDITS.md).

Run it again only when the pipeline changes; the images it writes are
committed, because the machine a player builds on may have no librsvg.
"""

import argparse
import copy
import io
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "art"
DECK = ART / "source" / "public-domain-complete-playing-card-deck.svg"
BACK = ART / "source" / "reverso-baraja-espanola.svg"
CARDS = ART / "cards"

NS = "http://www.w3.org/2000/svg"
SVG = f"{{{NS}}}"
for prefix, uri in [("", NS), ("xlink", "http://www.w3.org/1999/xlink"),
                    ("serif", "http://www.serif.com/")]:
    ET.register_namespace(prefix, uri)

RANKS = "AKQJT987"                 # the protocol's ranks, high first
SUITS = "SHDC"                     # the protocol's suits
DECK_SUITS = "SHCD"                # the deck file's order: spades, hearts, clubs, diamonds
DECK_RANKS = "A23456789TJQK"       # and within a suit
CELL = (750, 1050)                 # each card's cell in the deck, 5:7
COLUMNS = 9                        # the deck is a 9 x 6 grid

WIDTH = 512                        # raster width; 717 tall at 5:7
QUALITY = 88                       # WebP quality for the faces

# The back, re-framed. Its width is kept (208) and its height cut to 5:7; the
# frame is rebuilt in the original's proportions and the lace field, clipped
# to the new height, is cropped evenly at both ends.
BACK_W = 208.0
BACK_H = BACK_W * 7 / 5            # 291.2
BACK_OLD_H = 319.0
NAVY = "#28284e"


def piquet_codes() -> list[str]:
    return [r + s for s in SUITS for r in RANKS]


def deck_index(code: str) -> int:
    return DECK_SUITS.index(code[1]) * 13 + DECK_RANKS.index(code[0])


def face_svgs() -> dict[str, str]:
    """Every piquet card as a standalone SVG, framed on its own cell."""
    root = ET.parse(DECK).getroot()
    cards = [e for e in root if e.tag == f"{SVG}g"]
    out = {}
    for code in piquet_codes():
        n = deck_index(code)
        x, y = CELL[0] * (n % COLUMNS), CELL[1] * (n // COLUMNS)
        svg = ET.Element(f"{SVG}svg", {
            "viewBox": f"{x} {y} {CELL[0]} {CELL[1]}",
            "width": str(CELL[0]), "height": str(CELL[1]),
            "style": root.get("style"),
        })
        svg.append(copy.deepcopy(cards[n]))
        out[code] = ET.tostring(svg, encoding="unicode")
    return out


def back_svg() -> str:
    """The back, re-framed to 5:7: our adaptation (CC BY-SA 3.0)."""
    root = ET.parse(BACK).getroot()
    defs = [copy.deepcopy(e) for e in root if e.tag == f"{SVG}defs"]
    outer = root.find(f"{SVG}g")
    navy, lace = list(list(outer)[1])  # the frame, and the clipped lace
    cut = BACK_OLD_H - BACK_H          # how much shorter the card becomes

    svg = ET.Element(f"{SVG}svg", {"viewBox": f"0 0 {BACK_W:g} {BACK_H:g}",
                                   "width": f"{BACK_W:g}", "height": f"{BACK_H:g}"})
    for d in defs:
        for grad in d.findall(f"{SVG}linearGradient"):
            d.remove(grad)             # the grey shading: not ours
        for clip in d.findall(f"{SVG}clipPath"):
            rect = clip.find(f"{SVG}rect")
            rect.set("height", f"{float(rect.get('height')) - cut:g}")
        svg.append(d)
    ET.SubElement(svg, f"{SVG}rect", {"width": f"{BACK_W:g}", "height": f"{BACK_H:g}",
                                      "rx": f"{BACK_W * 0.05:g}", "fill": "#fff"})
    frame = ET.SubElement(svg, f"{SVG}g", {"fill": NAVY})
    for rect in navy:
        r = copy.deepcopy(rect)
        r.set("height", f"{float(r.get('height')) - cut:g}")
        # The original's corners were stretched with the card; ours are round.
        r.set("ry", r.get("rx"))
        frame.append(r)
    clip = lace.get("clip-path")
    del lace.attrib["clip-path"]
    wrapper = ET.SubElement(svg, f"{SVG}g", {"clip-path": clip})
    shifted = ET.SubElement(wrapper, f"{SVG}g", {"transform": f"translate(0 {-cut / 2:g})"})
    shifted.append(lace)
    return ET.tostring(svg, encoding="unicode")


NUMBER = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def trim_numbers(data: str, decimals: int) -> str:
    """Round every number in SVG path data to `decimals` places."""
    out, last = [], 0
    for m in NUMBER.finditer(data):
        out.append(data[last:m.start()])
        text = m.group(0)
        if "e" not in text.lower():
            rounded = f"{round(float(text), decimals):.{decimals}f}".rstrip("0").rstrip(".")
            if rounded in ("-0", ""):
                rounded = "0"
            # Keep the leading-dot shorthand the original used.
            if text.lstrip("-").startswith(".") and rounded.lstrip("-").startswith("0."):
                rounded = rounded.replace("0.", ".", 1)
            if "." not in rounded and data[m.end():m.end() + 1] == ".":
                rounded += " "         # "2" then ".5" would read as "2.5"
            text = rounded
        out.append(text)
        last = m.end()
    out.append(data[last:])
    return "".join(out)


def trim_precision(svg: str, decimals: int) -> str:
    """Trim path data only. Transforms carry scale factors and stay exact."""
    return re.sub(r'(\sd=")([^"]*)(")',
                  lambda m: m.group(1) + trim_numbers(m.group(2), decimals) + m.group(3), svg)


def rasterise(svg: str, width: int) -> bytes:
    return subprocess.run(["rsvg-convert", "-w", str(width), "-f", "png"],
                          input=svg.encode(), capture_output=True, check=True).stdout


def webp(png: bytes, lossless: bool = False) -> bytes:
    """Encode on a white matte, with no alpha: the table's card geometry
    carries the rounded corners itself, and texels outside them that were
    transparent black would bleed dark into the corners through the mipmaps."""
    from PIL import Image
    rgba = Image.open(io.BytesIO(png)).convert("RGBA")
    image = Image.new("RGB", rgba.size, (255, 255, 255))
    image.paste(rgba, mask=rgba.getchannel("A"))
    buffer = io.BytesIO()
    if lossless:
        image.save(buffer, "WEBP", lossless=True, method=6)
    else:
        image.save(buffer, "WEBP", quality=QUALITY, method=6)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sheet", type=Path, help="also write a contact sheet PNG, to check by eye")
    args = parser.parse_args()

    CARDS.mkdir(parents=True, exist_ok=True)
    written = {}
    for code, svg in face_svgs().items():
        written[code] = webp(rasterise(svg, WIDTH))
    back_png = rasterise(back_svg(), WIDTH)
    lossy, lossless = webp(back_png), webp(back_png, lossless=True)
    written["back"] = min(lossy, lossless, key=len)

    for name, data in written.items():
        (CARDS / f"{name}.webp").write_bytes(data)
    total = sum(len(d) for d in written.values())
    faces = sum(len(d) for n, d in written.items() if n != "back")
    print(f"{len(written)} images in {CARDS.relative_to(HERE.parent.parent)}: {total:,} bytes "
          f"(faces {faces:,}, back {len(written['back']):,}, "
          f"{'lossless' if written['back'] is lossless else 'lossy'})")
    if args.sheet:
        contact_sheet(written, args.sheet)
    return 0


def contact_sheet(images: dict[str, bytes], path: Path) -> None:
    from PIL import Image
    thumbs = {n: Image.open(io.BytesIO(d)).convert("RGBA").resize((128, 179)) for n, d in images.items()}
    order = piquet_codes() + ["back"]
    sheet = Image.new("RGBA", (8 * 136 + 8, 5 * 187 + 8), (205, 210, 220, 255))
    for i, name in enumerate(order):
        sheet.alpha_composite(thumbs[name], (8 + 136 * (i % 8), 8 + 187 * (i // 8)))
    sheet.save(path)
    print(f"contact sheet: {path}")


if __name__ == "__main__":
    sys.exit(main())
