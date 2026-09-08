import pytest

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client


def test_wifi_room_create_join_and_play_to_win(client):
    created = client.post('/api/rooms', json={
        'board_size': 3,
        'player_x_name': 'Host',
        'player_o_name': 'Guest',
        'league': 'Bronze',
    })
    assert created.status_code == 200
    created_data = created.get_json()
    code = created_data['room']['code']
    x_player = created_data['player']
    assert x_player['symbol'] == 'X'
    assert created_data['room']['status'] == 'waiting'

    blocked = client.post(f'/api/rooms/{code}/move', json={
        'player_id': x_player['id'],
        'row': 0,
        'col': 0,
        'version': created_data['room']['version'],
    })
    assert blocked.status_code == 409

    joined = client.post(f'/api/rooms/{code}/join', json={'player_name': 'Guest'})
    assert joined.status_code == 200
    joined_data = joined.get_json()
    o_player = joined_data['player']
    assert o_player['symbol'] == 'O'
    assert joined_data['room']['status'] == 'active'

    wrong_turn = client.post(f'/api/rooms/{code}/move', json={
        'player_id': o_player['id'],
        'row': 1,
        'col': 1,
        'version': joined_data['room']['version'],
    })
    assert wrong_turn.status_code == 409

    room = joined_data['room']
    for player, row, col in [
        (x_player, 0, 0),
        (o_player, 1, 0),
        (x_player, 0, 1),
        (o_player, 1, 1),
        (x_player, 0, 2),
    ]:
        moved = client.post(f'/api/rooms/{code}/move', json={
            'player_id': player['id'],
            'row': row,
            'col': col,
            'version': room['version'],
        })
        assert moved.status_code == 200
        room = moved.get_json()['room']

    assert room['status'] == 'win'
    assert room['winner'] == 'X'
    assert room['winning_line'] == [[0, 0], [0, 1], [0, 2]]


def test_wifi_room_reset_syncs_board(client):
    created = client.post('/api/rooms', json={'board_size': 4})
    data = created.get_json()
    code = data['room']['code']
    player = data['player']

    reset = client.post(f'/api/rooms/{code}/reset', json={
        'player_id': player['id'],
        'board_size': 5,
    })
    assert reset.status_code == 200
    room = reset.get_json()['room']
    assert room['board_size'] == 5
    assert len(room['board']) == 5
    assert room['status'] == 'waiting'


def test_rematch_requires_two_votes_and_rejects_stale_round(client):
    created = client.post('/api/rooms', json={}).get_json()
    code = created['room']['code']
    x = created['player']['id']
    o = client.post(f'/api/rooms/{code}/join', json={}).get_json()['player']['id']
    url = f'/api/rooms/{code}/reset'
    assert client.post(url, json={'player_id': x, 'round': 1}).status_code == 409

    assert client.post(url, json={'player_id': 'stranger', 'round': 1}).status_code == 403
    for player, row, col in [(x, 0, 0), (o, 1, 0), (x, 0, 1), (o, 1, 1), (x, 0, 2)]:
        result = client.post(f'/api/rooms/{code}/move', json={'player_id': player, 'row': row, 'col': col})
        assert result.status_code == 200
    finished = result.get_json()['room']
    for _ in range(2):
        vote = client.post(url, json={'player_id': x, 'round': 1}).get_json()
        assert vote['status'] == 'pending'
        assert vote['room']['rematch_votes'] == ['X']
        assert vote['room']['board'] == finished['board']
        assert vote['room']['version'] == finished['version']
    restarted = client.post(url, json={'player_id': o, 'round': 1, 'board_size': 5}).get_json()['room']
    assert restarted['status'] == 'active'
    assert restarted['round'] == 2
    assert restarted['board'] == [[' '] * 3 for _ in range(3)]
    assert restarted['rematch_votes'] == []
    assert client.post(url, json={'player_id': x, 'round': 1}).status_code == 409


def test_guest_selects_league_and_next_round_requires_fresh_votes(client, monkeypatch):
    awards = []
    monkeypatch.setattr('app.increment_trophy', lambda league, winner: awards.append((league, winner)))
    created = client.post('/api/rooms', json={'league': 'Bronze'}).get_json()
    code = created['room']['code']
    x = created['player']['id']
    joined = client.post(f'/api/rooms/{code}/join', json={}).get_json()
    o = joined['player']['id']
    url = f'/api/rooms/{code}/league'
    version = joined['room']['version']
    assert client.post(url, json={'player_id': 'outsider', 'league': 'Gold', 'version': version}).status_code == 403
    assert client.post(url, json={'player_id': o, 'league': 'Unknown', 'version': version}).status_code == 400
    assert client.post(url, json={'player_id': o, 'league': 'Gold', 'version': version - 1}).status_code == 409
    chosen = client.post(url, json={'player_id': o, 'league': 'Gold', 'version': version})
    assert chosen.status_code == 200
    assert chosen.get_json()['room']['league'] == 'Gold'
    for player, row, col in [(x, 0, 0), (o, 1, 0), (x, 0, 1), (o, 1, 1), (x, 0, 2)]:
        room = client.post(f'/api/rooms/{code}/move', json={'player_id': player, 'row': row, 'col': col}).get_json()['room']
        if len(room['moves']) == 1:
            assert client.post(url, json={'player_id': o, 'league': 'Silver', 'version': room['version']}).status_code == 409
    assert awards == [('Gold', 'X')]
    reset = f'/api/rooms/{code}/reset'
    old_version = room['version']
    client.post(reset, json={'player_id': x, 'round': 1, 'version': old_version})
    queued = client.post(url, json={'player_id': o, 'league': 'Silver', 'version': old_version}).get_json()['room']
    assert queued['league'] == 'Gold'
    assert queued['next_league'] == 'Silver'
    assert queued['rematch_votes'] == []
    assert client.post(reset, json={'player_id': x, 'round': 1, 'version': old_version}).status_code == 409
    first = client.post(reset, json={'player_id': o, 'round': 1, 'version': queued['version']}).get_json()
    assert first['status'] == 'pending'
    final = client.post(reset, json={'player_id': x, 'round': 1, 'version': queued['version'], 'league': 'Hard'}).get_json()['room']
    assert final['league'] == 'Silver'
    assert final['next_league'] is None
    assert final['status'] == 'active'
    assert awards == [('Gold', 'X')]
