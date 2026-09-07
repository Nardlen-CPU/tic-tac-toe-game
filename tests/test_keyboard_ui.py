from pathlib import Path

from playwright.sync_api import sync_playwright


def test_keyboard_navigation_dialogs_and_reduced_motion():
    html = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("http://game.test/**", lambda route: route.fulfill(
            content_type="text/html" if route.request.resource_type == "document" else "application/json",
            body=html if route.request.resource_type == "document" else "{}",
        ))
        page.goto("http://game.test/")
        page.keyboard.press("Escape")
        page.select_option("#mode", "local")
        page.click("#startBtn")
        # An occupied cell must not trap arrow navigation.
        page.evaluate("boardState[1][1] = 'X'; updateBoardUI();")
        page.locator('.cell[data-row="1"][data-col="0"]').focus()
        page.keyboard.press("ArrowRight")
        assert page.locator('.cell[data-row="1"][data-col="2"]').evaluate("el => el === document.activeElement")

        page.click("#aboutBtn")
        assert page.locator("#closeAboutBtn").evaluate("el => el === document.activeElement")
        page.keyboard.press("Tab")
        assert page.locator("#closeAboutBtn").evaluate("el => el === document.activeElement")
        page.keyboard.press("Shift+Tab")
        assert page.locator("#closeAboutBtn").evaluate("el => el === document.activeElement")
        page.keyboard.press("r")
        assert page.evaluate("boardState[1][1]") == "X"
        page.keyboard.press("Escape")
        assert page.locator("#aboutBtn").evaluate("el => el === document.activeElement")
        assert not page.locator(".app-shell").evaluate("el => el.inert")

        page.locator("#playerXNameInput").fill("Player")
        page.keyboard.press("r")
        assert page.evaluate("boardState[1][1]") == "X"
        page.evaluate("explodeConfetti()")
        assert not page.locator("#confettiCanvas").is_visible()
        assert not errors
        browser.close()
