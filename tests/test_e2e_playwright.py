from playwright.sync_api import sync_playwright


def test_ui_loads_and_start():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('http://127.0.0.1:5000/', timeout=10000)
        assert 'TIC TAC TOE' in page.content()
        # Start the game
        page.click('#startBtn')
        page.wait_for_selector('.cell', timeout=5000)
        cells = page.query_selector_all('.cell')
        # For default 3x3 board there should be 9 cells
        assert len(cells) >= 9
        browser.close()
