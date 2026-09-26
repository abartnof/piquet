#!/usr/bin/env python3
"""Play the built page in a real browser, by clicking, the way a person would.

    python3 web/build.py
    .venv/bin/python web/test/browser.py [screenshot-dir]

Needs Playwright's Python package (in the project `.venv` on the dev VM) and a
Chromium; the system one is used (`/usr/bin/chromium`, from apt), so
Playwright's own browser download is not needed. Plays whole parties at several levels through the page's buttons and
cards, and checks the things only a browser can show: that the page loads the
engine at all from a file:// URL, that an illegal card is refused *on screen*
with the engine's reason, that a reload resumes the game in progress, and that
nothing is ever written to the console in error.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PAGE = (ROOT / "web" / "piquet.html").as_uri()
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def shot(page, name):
    if SHOTS:
        page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)


def prompt_kind(page):
    return page.evaluate("engine.state().prompt.kind")


def take_turn(page):
    """One human decision, made by clicking. False once the partie is over."""
    kind = prompt_kind(page)
    if kind == "exchange":
        page.locator("#hand .card").first.click()
        page.locator("#prompt button.primary").click()
    elif kind == "declare":
        page.locator("#prompt .options button").first.click()
    elif kind == "play":
        page.locator("#hand .card:not(.illegal)").first.click()
    elif kind == "next_deal":
        page.get_by_role("button", name="Deal the next hand").click()
    elif kind == "over":
        return False
    else:
        raise AssertionError(f"unknown prompt {kind}")
    page.wait_for_function("!busy")
    return True


def main() -> int:
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))

        for level, seed in [(1, 5), (3, 42), (5, 7)]:
            page.goto(f"{PAGE}?level={level}&seed={seed}")
            page.evaluate("localStorage.clear()")
            page.goto(f"{PAGE}?level={level}&seed={seed}")
            page.wait_for_selector("#hand .card")
            assert page.evaluate("engine.state().seed") == seed

            turns, shots_taken, illegal_checked, reload_checked = 0, set(), False, False
            while take_turn(page):
                turns += 1
                assert turns < 1500, "the partie never ended"
                kind = prompt_kind(page)
                if level == 3 and kind not in shots_taken:
                    shot(page, f"level3-{kind}")
                    shots_taken.add(kind)

                # A card that does not follow suit, clicked: refused, on screen.
                if kind == "play" and not illegal_checked and page.locator("#hand .card.illegal").count():
                    before = page.evaluate("JSON.stringify(engine.state().hand)")
                    page.locator("#hand .card.illegal").first.click()
                    page.wait_for_function("!busy")
                    message = page.locator("#prompt .error").inner_text()
                    assert "follow" in message, message
                    assert page.evaluate("JSON.stringify(engine.state().hand)") == before
                    if level == 3:
                        shot(page, "level3-illegal")
                    illegal_checked = True

                # A reload in the middle of the second deal resumes it exactly.
                if not reload_checked and page.evaluate("engine.state().deal") == 2 and kind == "play":
                    before = page.evaluate("JSON.stringify(engine.state())")
                    page.reload()
                    page.wait_for_selector("#hand .card")
                    after = page.evaluate("JSON.stringify(engine.state())")
                    assert before == after, "a reload did not resume the game in progress"
                    reload_checked = True

            final = page.evaluate("engine.state()")
            assert final["settlement"] is not None
            assert illegal_checked, f"level {level}: never had an illegal card to try"
            assert reload_checked, f"level {level}: never reloaded mid-game"
            print(f"level {level} seed {seed}: {turns} clicks, "
                  f"you {final['partie']['you']} - {final['opponent']['name']} {final['partie']['them']}")
            if level == 3:
                shot(page, "level3-over")

        # And at phone width.
        phone = browser.new_page(viewport={"width": 390, "height": 844})
        phone.goto(f"{PAGE}?level=2&seed=11")
        phone.wait_for_selector("#hand .card")
        width = phone.evaluate("document.documentElement.scrollWidth")
        assert width <= 390, f"the page scrolls sideways on a phone: {width}px"
        shot(phone, "phone")
        browser.close()

    if errors:
        print("console errors:", *errors, sep="\n  ")
        return 1
    print("no console errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
