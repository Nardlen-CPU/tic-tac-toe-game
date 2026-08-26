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
