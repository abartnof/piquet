#!/usr/bin/env python3
"""Play the built page in a real browser, by clicking, the way a person would.

    python3 web/build.py
    .venv/bin/python web/test/browser.py [screenshot-dir]

Needs Playwright's Python package (in the project `.venv` on the dev VM) and a
Chromium; the system one is used (`/usr/bin/chromium`, from apt), so
Playwright's own browser download is not needed. The page is opened with
`?test`, which drops the pauses that make play feel like play.

Checks the things only a browser can show: that the engine loads from a
file:// URL; that whole parties can be played by clicking at several levels;
that an illegal card is refused *on screen* with the engine's reason; that a
reload resumes the game in progress exactly; that the aids work from the
settings panel, the keyboard and the hint's Follow button; that undo puts the
table back; that a phone never scrolls sideways; and that nothing is ever
written to the console in error.
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


def state(page):
    return page.evaluate("engine.state()")


def kind(page):
    return page.evaluate("engine.state().prompt.kind")


def settle(page):
    page.wait_for_function("!busy")


def cut_at(page, n):
    """Cut by clicking the visible edge of the nth cuttable card, as a person
    does. A fan shows only each card's edge; Playwright's own pre-click check
    misjudges what covers it once the hover lift has run, so click the mouse
    at the edge directly."""
    target = page.locator("#trick .cutfan .card.cuttable").nth(n)
    target.scroll_into_view_if_needed()
    box = target.bounding_box()
    page.mouse.click(box["x"] + 4, box["y"] + 30)
    settle(page)


def ready(page):
    page.wait_for_selector("#prompt .ask")
    settle(page)


def open_fresh(page, level, seed):
    page.goto(f"{PAGE}?test&level={level}&seed={seed}")
    page.evaluate("localStorage.clear()")
    page.goto(f"{PAGE}?test&level={level}&seed={seed}")
    ready(page)


def take_turn(page):
    """One human decision, made by clicking. False once the partie is over."""
    now = kind(page)
    if now == "cut":
        cut_at(page, 14)
    elif now == "choose_dealer":
        page.get_by_role("button", name="Deal first").click()
    elif now == "exchange":
        page.locator("#hand .card").first.click()
        page.locator("#prompt button.primary").click()
    elif now == "declare":
        page.locator("#prompt .options button").first.click()
    elif now == "play":
        page.locator("#hand .card:not(.illegal)").first.click()
    elif now == "next_deal":
        page.get_by_role("button", name="Deal the next hand").click()
    elif now == "over":
        return False
    else:
        raise AssertionError(f"unknown prompt {now}")
    settle(page)
    return True


def whole_parties(page):
    for level, seed in [(1, 5), (3, 42), (5, 7)]:
        open_fresh(page, level, seed)
        assert state(page)["seed"] == seed

        turns, shots_taken, illegal_checked, reload_checked = 0, set(), False, False
        while take_turn(page):
            turns += 1
            assert turns < 1500, "the partie never ended"
            now = kind(page)
            if level == 3 and now not in shots_taken:
                shot(page, f"level3-{now}")
                shots_taken.add(now)

            # A card that does not follow suit, clicked: refused, on screen.
            if now == "play" and not illegal_checked and page.locator("#hand .card.illegal").count():
                before = page.evaluate("JSON.stringify(engine.state().hand)")
                page.locator("#hand .card.illegal").first.click()
                settle(page)
                message = page.locator("#prompt .error").inner_text()
                assert "follow" in message, message
                assert page.evaluate("JSON.stringify(engine.state().hand)") == before
                if level == 3:
                    shot(page, "level3-illegal")
                illegal_checked = True

            # A reload in the middle of the second deal resumes it exactly.
            if not reload_checked and state(page)["deal"] == 2 and now == "play":
                before = page.evaluate("JSON.stringify(engine.state())")
                page.reload()
                ready(page)
                after = page.evaluate("JSON.stringify(engine.state())")
                assert before == after, "a reload did not resume the game in progress"
                reload_checked = True

        final = state(page)
        assert final["settlement"] is not None
        folds = page.locator("#log details.fold").count()
        assert folds >= 5, f"earlier deals fold away in the narration: {folds}"
        assert illegal_checked, f"level {level}: never had an illegal card to try"
        assert reload_checked, f"level {level}: never reloaded mid-game"
        print(f"level {level} seed {seed}: {turns} clicks, "
              f"you {final['partie']['you']} - opponent {final['partie']['them']}")
        body = page.locator("body").inner_text()
        for name in ("Bess", "Cotton", "Cavendish", "Hoyle", "Foster"):
            assert name not in body, f"the page names the opponent {name}"
        if level == 3:
            shot(page, "level3-over")


def through_the_cut(page):
    while kind(page) in ("cut", "choose_dealer"):
        take_turn(page)


def the_aids(page):
    open_fresh(page, 4, 99)
    assert page.locator("#settings").is_hidden(), "the settings panel starts shut"
    through_the_cut(page)
    s = state(page)
    assert s["aids"] == {"hints": True, "play_forced": True, "play_winners": True,
                         "declare_for_me": False}, s["aids"]

    # What the hand is worth reads as words, not as a serialised object.
    worth = page.locator("#worth").inner_text()
    assert worth.startswith("Worth:") and "[object" not in worth, worth

    # A hint, pointed at in the hand, and followed with one click.
    assert page.locator("#prompt .hint").count() == 1
    assert page.locator("#hand .card.hinted").count() >= 1
    page.get_by_role("button", name="Follow").click()
    settle(page)
    assert kind(page) in ("declare", "play"), "following the exchange hint exchanged"
    shot(page, "aids-after-follow")

    # Undo puts it back, from the button and from the keyboard.
    before = page.evaluate("JSON.stringify([engine.state().hand, engine.state().prompt])")
    take_turn(page)
    page.locator("#undo").click()
    settle(page)
    after = page.evaluate("JSON.stringify([engine.state().hand, engine.state().prompt])")
    assert before == after, "undo did not put the table back"
    take_turn(page)
    page.keyboard.press("u")
    settle(page)
    assert page.evaluate("JSON.stringify([engine.state().hand, engine.state().prompt])") == before

    # Declare-for-me from the settings panel: no more declaration prompts.
    page.locator("#settings-toggle").click()
    page.locator("[data-aid=declare_for_me]").check()
    settle(page)
    shot(page, "aids-settings")
    assert state(page)["aids"]["declare_for_me"] is True
    for _ in range(60):
        assert kind(page) != "declare", "asked to declare with declare-for-me on"
        if not take_turn(page):
            break

    # H toggles hints; the hint line goes with them.
    page.keyboard.press("h")
    settle(page)
    assert state(page)["aids"]["hints"] is False
    assert page.locator("#prompt .hint").count() == 0

    # The running tab can be put away.
    assert page.locator("#tab .deal-cell").count() >= 7
    page.locator("[data-pref=tab]").uncheck()
    assert page.locator("#tab").is_hidden()


def the_keyboard(page):
    open_fresh(page, 2, 123)
    through_the_cut(page)
    page.locator("#hand .card").nth(2).click()
    page.keyboard.press("Enter")
    settle(page)
    assert kind(page) != "exchange", "Enter did not exchange"
    # Digits choose declaration options.
    for _ in range(10):
        if kind(page) == "declare":
            page.keyboard.press("1")
            settle(page)
            break
        take_turn(page)


def the_table(page):
    """The cut, the piles, the tricks face up, the sort bar and the chips."""
    open_fresh(page, 3, 2024)
    assert kind(page) == "cut", "a partie begins with the cut"
    assert page.locator("#trick .cutfan .card").count() == 32
    assert page.locator("#hand .card").count() == 0, "nothing dealt before the cut"
    shot(page, "table-cut")

    # Cut until someone has the choice; if it is us, the two cards are shown.
    for _ in range(10):
        cut_at(page, 9)
        if kind(page) != "cut":
            break
    if kind(page) == "choose_dealer":
        assert page.locator("#trick .card").count() == 2, "both cut cards on the table"
        shot(page, "table-choose")
        page.get_by_role("button", name="Deal first").click()
        settle(page)
    s = state(page)
    assert any(e["kind"] == "first_dealer" for e in s["events"])
    assert page.locator("#hand .card").count() == 12

    # The sort bar: rank groups ranks, combinations leads with the best holding.
    page.locator("#sortbar button[data-sort=suit]").click()
    by_suit = page.evaluate("[...document.querySelectorAll('#hand .card')].map(c => c.dataset.code)")
    page.locator("#sortbar button[data-sort=rank]").click()
    by_rank = page.evaluate("[...document.querySelectorAll('#hand .card')].map(c => c.dataset.code)")
    assert sorted(by_suit) == sorted(by_rank) and by_suit != by_rank
    ranks = [c[0] for c in by_rank]
    assert all(ranks.index(r) + ranks.count(r) - 1 == len(ranks) - 1 - ranks[::-1].index(r) for r in ranks), "ranks together"
    page.locator("#sortbar button[data-sort=combos]").click()
    shot(page, "table-combos")
    worth = state(page)["worth"]
    if worth and worth[0]["category"] != "carte_blanche":
        combos = page.evaluate("[...document.querySelectorAll('#hand .card')].map(c => c.dataset.code)")
        first = set(worth[0]["cards"])
        assert set(combos[: len(first)]) == first, "the best holding comes first"
        assert page.locator("#hand .card.group-start").count() >= 1, "groups are set apart"
        # Pointing at a holding lifts exactly its cards.
        page.locator("#worth .chip").first.hover()
        lifted = page.evaluate("[...document.querySelectorAll('#hand .card.lifted')].map(c => c.dataset.code)")
        assert set(lifted) == first, (lifted, first)
    page.locator("#sortbar button[data-sort=auto]").click()

    # Play on to the middle of the deal: the piles and the tricks.
    while kind(page) != "play":
        take_turn(page)
    for _ in range(5):
        if kind(page) != "play":
            break
        take_turn(page)
    s = state(page)
    count = page.locator("#their-discards .count").inner_text()
    assert count.startswith(str(s["their_discards"])), (count, s["their_discards"])
    assert page.locator("#your-tricks .pair").count() == s["tricks"]["you"]
    assert page.locator("#their-tricks .pair").count() == s["tricks"]["them"]
    shot(page, "table-midplay")

    # The hints switch, in the header, both ways.
    assert state(page)["aids"]["hints"] is True
    page.locator("#hints-switch").click()
    settle(page)
    assert state(page)["aids"]["hints"] is False
    assert page.locator("#prompt .hint").count() == 0
    page.locator("#hints-switch").click()
    settle(page)
    assert state(page)["aids"]["hints"] is True


def main() -> int:
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 1100})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))

        whole_parties(page)
        the_aids(page)
        the_keyboard(page)
        the_table(page)
        print("aids, undo, hints, settings, keyboard, cut, piles, tricks and sorting all work")

        phone = browser.new_page(viewport={"width": 390, "height": 844})
        phone.on("pageerror", lambda e: errors.append(str(e)))
        phone.goto(f"{PAGE}?test&level=2&seed=11")
        ready(phone)
        through_the_cut(phone)
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

