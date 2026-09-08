import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture
def page():
    html = (Path(__file__).resolve().parents[1] / 'templates' / 'index.html').read_text(encoding='utf-8')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('http://game.test/**', lambda route: route.fulfill(
            content_type='text/html' if route.request.resource_type == 'document' else 'application/json',
            body=html if route.request.resource_type == 'document' else '{}',
        ))
        page.goto('http://game.test/')
        page.keyboard.press('Escape')
        page.select_option('#mode', 'local')
        yield page
        assert not errors
        browser.close()


def play(page, moves):
    for row, col in moves:
        page.locator(f'.cell[data-row="{row}"][data-col="{col}"]').click()


@pytest.mark.parametrize('level', ['Easy', 'Intermediate', 'Hard', 'Grandmaster', 'Super Undefeated'])
def test_selected_difficulty_reaches_ai_and_survives_reload(page, level):
    requests = []

    def respond(route):
        payload = route.request.post_data_json
        requests.append(payload)
        board = payload['board']
        board[1][1] = 'O'
        route.fulfill(content_type='application/json', body=json.dumps({
            'status': 'continue', 'board': board, 'machine_move': [1, 1],
        }))

    page.route('http://game.test/play', respond)
    page.select_option('#mode', 'computer')
    page.select_option('#playerSymbol', 'X')
    page.select_option('#difficulty', level)
    page.click('#startBtn')
    assert page.locator('#difficulty').input_value() == level
    play(page, [(0, 0)])
    page.wait_for_function('!busy && boardState[1][1] === "O"')
    assert requests[0]['difficulty'] == level
    page.reload()
    assert page.locator('#difficulty').input_value() == level


def test_ladder_controls_difficulty_only_while_enabled(page):
    page.select_option('#difficulty', 'Grandmaster')
    page.click('#challengeBtn')
    assert page.locator('#difficulty').is_disabled()
    assert page.locator('#difficulty').input_value() == 'Easy'
    page.click('#challengeBtn')
    assert page.locator('#difficulty').is_enabled()
    assert page.locator('#difficulty').input_value() == 'Grandmaster'
    page.click('#startBtn')
    assert page.locator('#difficulty').input_value() == 'Grandmaster'


def test_series_alternates_starters_and_finishes(page):
    page.select_option('#seriesLength', '3')
    page.click('#seriesBtn')
    play(page, [(0, 0), (1, 0), (0, 1), (1, 1)])
    page.click('#hintBtn')
    assert 'Complete a line to win now' in page.locator('#hintStatus').inner_text()
    play(page, [(0, 2)])
    assert page.evaluate('series.X') == 1
    page.click('#startBtn')
    assert page.evaluate('currentPlayer') == 'O'
    play(page, [(1, 0), (0, 0), (1, 1), (0, 1), (2, 2), (0, 2)])
    assert 'X wins the series' in page.locator('#seriesStatus').inner_text()
    page.click('#startBtn')
    assert page.evaluate('series') is None


def test_replay_preserves_live_board(page):
    page.click('#startBtn')
    play(page, [(0, 0), (1, 1)])
    original = page.evaluate('boardState')
    page.click('#replayBtn')
    assert page.evaluate('gamePaused')
    assert 'Move 0 of 2' in page.locator('#featureMessage').inner_text()
    page.click('#featureNext')
    assert page.locator('#featureBoard button').nth(0).inner_text() == 'X'
    page.click('#featureNext')
    assert page.locator('#featureBoard button').nth(4).inner_text() == 'O'
    page.click('#featurePrev')
    assert page.locator('#featureBoard button').nth(4).inner_text() == '·'
    page.keyboard.press('Escape')
    assert page.evaluate('boardState') == original


def test_daily_puzzle_is_solvable_and_persists_completion(page):
    page.click('#dailyBtn')
    date = page.evaluate('new Date().toISOString().slice(0, 10)')
    board = page.evaluate('(date) => dailyPuzzle(date)', date)
    assert page.evaluate('(date) => dailyPuzzle(date)', date) == board
    for _ in range(2):
        board = [page.locator('#featureBoard button').nth(i).inner_text() for i in range(9)]
        board = [[' ' if v == '·' else v for v in board[i:i + 3]] for i in range(0, 9, 3)]
        move = page.evaluate('(board) => bestPracticeMove(board, "X")', board)
        page.locator('#featureBoard button').nth(move[0] * 3 + move[1]).click()
    assert 'Solved!' in page.locator('#featureMessage').inner_text()
    assert page.evaluate('(date) => storage.getItem(`puzzle:${date}`)', date) == 'solved'
    page.click('#featureNext')
    assert 'Already solved today' in page.locator('#featureMessage').inner_text()


def test_hint_prioritizes_win_without_changing_board(page):
    page.click('#startBtn')
    play(page, [(2, 2), (0, 0), (1, 2), (0, 1)])
    # X also has a win here: hints should prioritize winning over blocking.
    original = page.evaluate('boardState')
    page.click('#hintBtn')
    assert 'Complete a line' in page.locator('#hintStatus').inner_text()
    assert page.evaluate('boardState') == original


def test_series_draw_does_not_award_a_win(page):
    page.select_option('#seriesLength', '5')
    page.click('#seriesBtn')
    play(page, [(0, 0), (0, 1), (0, 2), (1, 1), (1, 0), (1, 2), (2, 1), (2, 0), (2, 2)])
    assert page.evaluate('[series.X, series.O, series.draws, series.complete]') == [0, 0, 1, False]
    page.click('#startBtn')
    assert page.evaluate('currentPlayer') == 'O'


def test_hint_explains_required_block(page):
    page.click('#startBtn')
    play(page, [(1, 1), (0, 0), (2, 1), (0, 1)])
    page.click('#hintBtn')
    assert 'Row 1, column 3: Block' in page.locator('#hintStatus').inner_text()


def test_ai_can_open_alternating_series_round(page):
    from app import app

    def respond(route):
        response = app.test_client().post('/play', json=route.request.post_data_json)
        route.fulfill(status=response.status_code, content_type='application/json', body=response.get_data(as_text=True))

    page.route('http://game.test/play', respond)
    page.select_option('#mode', 'computer')
    page.select_option('#playerSymbol', 'X')
    page.select_option('#seriesLength', '3')
    page.click('#seriesBtn')
    page.evaluate('finishGame("win", "X")')
    page.click('#startBtn')
    page.wait_for_function('!busy && boardState.flat().filter(cell => cell === "O").length === 1')
    assert page.evaluate('currentPlayer') == 'X'
    assert page.evaluate('series.round') == 2


def test_wifi_rematch_button_sends_round_and_keeps_score_once(page):
    from urllib.parse import urlsplit
    from app import app

    with app.test_client() as client:
        created = client.post('/api/rooms', json={}).get_json()
        code = created['room']['code']
        x = created['player']['id']
        o = client.post(f'/api/rooms/{code}/join', json={}).get_json()['player']['id']
        for player, row, col in [(x, 0, 0), (o, 1, 0), (x, 0, 1), (o, 1, 1), (x, 0, 2)]:
            room = client.post(f'/api/rooms/{code}/move', json={'player_id': player, 'row': row, 'col': col}).get_json()['room']

        def respond(route):
            response = app.test_client().open(urlsplit(route.request.url).path, method=route.request.method, json=route.request.post_data_json)
            route.fulfill(status=response.status_code, content_type='application/json', body=response.get_data(as_text=True))

        page.route('http://game.test/api/rooms/**', respond)
        page.select_option('#mode', 'wifi')
        page.evaluate('''(data) => {
            roomSession.code = data.room.code;
            roomSession.playerId = data.id;
            roomSession.symbol = 'X';
            applyRoomState(data.room);
        }''', {'room': room, 'id': x})
        score = page.evaluate('scoreX')
        page.click('#startBtn')
        page.wait_for_function('roomSession.room.rematch_votes.length === 1')
        assert page.evaluate('boardState[0]') == ['X', 'X', 'X']
        assert page.evaluate('scoreX') == score
        restarted = client.post(f'/api/rooms/{code}/reset', json={'player_id': o, 'round': 1}).get_json()['room']
        page.evaluate('(room) => applyRoomState(room)', restarted)
        assert page.evaluate('boardState') == [[' '] * 3 for _ in range(3)]
        assert page.locator('#startBtn').is_disabled()
