#!/usr/bin/env python3
"""The 3D table in a real browser, offline.

    python3 web3d/build.py
    .venv/bin/python web3d/test/browser.py [screenshot-dir]

Needs Playwright's Python package (the project `.venv` on the dev VM) and the
system Chromium (`/usr/bin/chromium`, from apt). WebGL runs on SwiftShader, so
no GPU is needed. The page is opened from a file:// URL with `?test`, which
makes every motion instant.

Checks what only a browser can show: that the page makes **no network request
of any kind** -- it is one file and must work offline; that the engine loads
and answers through the test hooks; that the canvas is actually drawn on, a
lit surface rather than one flat colour; and that nothing is written to the
console in error.
"""

import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "web3d" / "piquet3d.html"
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
LOCAL = ("file:", "data:", "blob:")


def shot(page, name):
    if SHOTS:
        page.screenshot(path=str(SHOTS / f"{name}.png"))


def open_page(browser, query="test", viewport=None):
    """A fresh context, offline, recording every request the page makes."""
    context = browser.new_context(viewport=viewport or {"width": 1280, "height": 800})
    context.set_offline(True)
    page = context.new_page()
    page.requests = []
    page.errors = []
    page.on("request", lambda r: page.requests.append(r.url))
    page.on("console", lambda m: m.type == "error" and page.errors.append(m.text))
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.goto(f"{PAGE.as_uri()}?{query}")
    page.wait_for_function("window.piquet3d && window.piquet3d.ready()", timeout=60_000)
    return page


def canvas_image(page):
    return Image.open(io.BytesIO(page.locator("canvas#stage").screenshot())).convert("RGB")


def check_offline(page, failures):
    remote = [u for u in page.requests if not u.startswith(LOCAL)]
    if remote:
        failures.append(f"the page asked the network for {len(remote)} things: {remote[:5]}")
    pages = [u for u in page.requests if u.startswith("file:")]
    if len(pages) != 1:
        failures.append(f"expected the page to load exactly one file, it loaded {pages}")


def check_engine(page, failures):
    s = page.evaluate("window.piquet3d.state()")
    if s.get("protocol") != 2:
        failures.append(f"the engine answered protocol {s.get('protocol')!r}, expected 2")
    if s["prompt"]["kind"] != "cut":
        failures.append(f"a new partie should open on the cut, not {s['prompt']['kind']!r}")


def check_drawn(page, failures):
    """A lit surface: the canvas is not one colour, and is not mostly black
    (the colour of WebGL that failed)."""
    image = canvas_image(page)
    small = image.resize((160, 100))
    colours = small.getcolors(maxcolors=160 * 100)
    dark = sum(n for n, (r, g, b) in colours if r + g + b < 60)
    if len(colours) < 4:
        failures.append(f"the canvas is nearly flat: {len(colours)} colours")
    if dark > 0.5 * 160 * 100:
        failures.append("the canvas is mostly black -- WebGL may have failed")


def main() -> int:
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])

        page = open_page(browser)
        check_offline(page, failures)
        check_engine(page, failures)
        check_drawn(page, failures)
        shot(page, "01-opened")
        if page.errors:
            failures.append(f"console errors: {page.errors}")
        page.context.close()

        # A phone, held upright: the page must still load and draw.
        phone = open_page(browser, viewport={"width": 390, "height": 844})
        check_drawn(phone, failures)
        shot(phone, "02-phone")
        if phone.errors:
            failures.append(f"console errors on a phone: {phone.errors}")
        phone.context.close()

        browser.close()

    for f in failures:
        print("FAIL:", f)
    if not failures:
        print("web3d browser test: all checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
