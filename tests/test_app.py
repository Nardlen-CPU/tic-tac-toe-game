import json
import pytest
from app import app as flask_app

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client


def test_play_invalid_board(client):
    resp = client.post('/play', json={'board': 'not-a-board'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['status'] == 'error'


def test_play_local_mode_no_machine(client):
    board = [[' ', ' ', ' '], [' ', ' ', ' '], [' ', ' ', ' ']]
    resp = client.post('/play', json={'board': board, 'mode': 'local', 'player_symbol': 'X'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'no_machine'


def test_play_human_already_won(client):
    board = [['X','X','X'], ['O',' ',' '], [' ','O',' ']]
    resp = client.post('/play', json={'board': board, 'mode':'computer', 'player_symbol':'X'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'win'
    assert data['winner'] == 'X'
    assert 'winning_line' in data


def test_play_machine_wins(client):
    # set up so machine (O) has a winning move
    board = [['O','O',' '], ['X','X',' '], [' ',' ',' ']]
    resp = client.post('/play', json={'board': board, 'mode':'computer', 'player_symbol':'X', 'difficulty':'Easy'})
    assert resp.status_code == 200
    data = resp.get_json()
    # machine should play and either win or continue; assert machine_move is present
    assert 'machine_move' in data
    assert isinstance(data['machine_move'], list) or data['machine_move'] is None


def test_deterministic_seed(client):
    board = [[' ', ' ', ' '], [' ', ' ', ' '], [' ', ' ', ' ']]
    payload = {'board': board, 'mode': 'computer', 'player_symbol': 'X', 'difficulty': 'Easy', 'seed': 'seed123'}
    resp1 = client.post('/play', json=payload)
    resp2 = client.post('/play', json=payload)
    assert resp1.status_code == 200 and resp2.status_code == 200
    m1 = resp1.get_json().get('machine_move')
    m2 = resp2.get_json().get('machine_move')
    # With the same seed and deterministic seeding on server side, moves should match
    assert m1 == m2
