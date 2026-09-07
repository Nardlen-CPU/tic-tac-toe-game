from flask import Flask, render_template, request, jsonify
import random
import os
import json
import secrets
import socket
import time
from threading import Lock
from pathlib import Path
from tic_tac_toe import check_win, check_draw, get_machine_move, get_winning_line, EMPTY

app = Flask(__name__)

LEAGUE_ORDER = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Grandmaster', 'Super Undefeated']
ROOM_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
ROOM_TTL_SECONDS = 6 * 60 * 60
rooms = {}
rooms_lock = Lock()

# simple trophies storage file (JSON) kept only for migration
TROPHIES_FILE = Path(__file__).with_name('trophies.json')
DB_PATH = Path(__file__).with_name('data.db')
import sqlite3


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trophies (league TEXT PRIMARY KEY, x_count INTEGER DEFAULT 0, o_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS unlocks (league TEXT PRIMARY KEY, unlocked INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS challenge (league TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
    # migrate existing trophies.json to DB if present
    if TROPHIES_FILE.exists():
        try:
            with TROPHIES_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            conn = get_conn(); c = conn.cursor()
            for league, counts in (data or {}).items():
                x = int(counts.get('X', 0) or 0)
                o = int(counts.get('O', 0) or 0)
                c.execute('INSERT OR REPLACE INTO trophies (league, x_count, o_count) VALUES (?,?,?)', (league, x, o))
            conn.commit(); conn.close()
            try:
                TROPHIES_FILE.unlink()
            except Exception:
                pass
        except Exception:
            pass

init_db()

# DB helpers

def normalize_room_code(code):
    return ''.join(ch for ch in str(code or '').upper().strip() if ch.isalnum())[:12]


def normalize_board_size(value):
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = 3
    return max(3, min(5, size))


def clean_player_name(value, fallback):
    name = str(value or '').strip()
    return name[:32] if name else fallback


def empty_board(size):
    return [[EMPTY for _ in range(size)] for _ in range(size)]


def generate_room_code():
    while True:
        code = ''.join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(5))
        if code not in rooms:
            return code


def cleanup_rooms():
    cutoff = time.time() - ROOM_TTL_SECONDS
    expired = [code for code, room in rooms.items() if room.get('updated_at', 0) < cutoff]
    for code in expired:
        rooms.pop(code, None)


def get_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return '127.0.0.1'


def build_room_url(code):
    public_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    if public_domain:
        return f'https://{public_domain}/?room={code}'
    host = request.host
    host_name, _, port = host.partition(':')
    if host_name in {'127.0.0.1', 'localhost', '0.0.0.0'}:
        host = get_lan_ip()
        if port:
            host = f'{host}:{port}'
    return f'{request.scheme}://{host}/?room={code}'


def public_room(room):
    players = {}
    for symbol in ('X', 'O'):
        player = room['players'].get(symbol)
        players[symbol] = {
            'connected': bool(player),
            'name': player['name'] if player else room['names'].get(symbol, f'Player {symbol}'),
        }
    return {
        'code': room['code'],
        'board_size': room['board_size'],
        'board': room['board'],
        'current_player': room['current_player'],
        'status': room['status'],
        'winner': room.get('winner'),
        'winning_line': room.get('winning_line'),
        'players': players,
        'moves': room['moves'],
        'last_move': room.get('last_move'),
        'version': room['version'],
        'round': room.get('round', 1),
        'rematch_votes': room.get('rematch_votes', []),
    }


def find_room_player(room, player_id):
    for symbol, player in room['players'].items():
        if player and player.get('id') == player_id:
            return symbol
    return None


def set_room_terminal_state(room, winner=None):
    if winner:
        room['status'] = 'win'
        room['winner'] = winner
        room['winning_line'] = get_winning_line(room['board'], winner)
        if not room.get('trophy_awarded'):
            increment_trophy(room.get('league') or 'General', winner)
            room['trophy_awarded'] = True
        return
    if check_draw(room['board']):
        room['status'] = 'draw'
        room['winner'] = None
        room['winning_line'] = None


def get_all_trophies():
    conn = get_conn(); c = conn.cursor(); c.execute('SELECT league, x_count, o_count FROM trophies'); rows = c.fetchall(); conn.close()
    result = {}
    for r in rows:
        result[r['league']] = {'X': int(r['x_count']), 'O': int(r['o_count'])}
    return result


def increment_trophy(league, winner):
    if winner not in ('X', 'O'):
        return
    conn = get_conn(); c = conn.cursor()
    if winner == 'X':
        # SQLite UPSERT
        c.execute('INSERT INTO trophies (league, x_count, o_count) VALUES (?,?,?) ON CONFLICT(league) DO UPDATE SET x_count = x_count + 1', (league, 1, 0))
    else:
        c.execute('INSERT INTO trophies (league, x_count, o_count) VALUES (?,?,?) ON CONFLICT(league) DO UPDATE SET o_count = o_count + 1', (league, 0, 1))
    conn.commit(); conn.close()


def get_all_unlocks():
    # default unlocks
    defaults = {league: league == 'Bronze' for league in LEAGUE_ORDER}
    conn = get_conn(); c = conn.cursor(); c.execute('SELECT league, unlocked FROM unlocks'); rows = c.fetchall(); conn.close()
    out = defaults.copy()
    for r in rows:
        out[r['league']] = bool(r['unlocked'])
    return out


def set_unlock(league, unlocked=True):
    conn = get_conn(); c = conn.cursor()
    val = 1 if unlocked else 0
    c.execute('INSERT INTO unlocks (league, unlocked) VALUES (?,?) ON CONFLICT(league) DO UPDATE SET unlocked=excluded.unlocked', (league, val))
    conn.commit(); conn.close()


def get_challenge_count(league):
    conn = get_conn(); c = conn.cursor(); c.execute('SELECT count FROM challenge WHERE league=?', (league,)); row = c.fetchone(); conn.close()
    return int(row['count']) if row else 0


def inc_challenge_count(league):
    conn = get_conn(); c = conn.cursor()
    c.execute('INSERT INTO challenge (league, count) VALUES (?,1) ON CONFLICT(league) DO UPDATE SET count = count + 1', (league,))
    conn.commit()
    c.execute('SELECT count FROM challenge WHERE league=?', (league,))
    row = c.fetchone(); conn.close()
    return int(row['count']) if row else 0


def reset_challenge_count(league):
    conn = get_conn(); c = conn.cursor()
    c.execute('INSERT INTO challenge (league, count) VALUES (?,0) ON CONFLICT(league) DO UPDATE SET count=0', (league,))
    conn.commit(); conn.close()

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@app.route('/api/rooms', methods=['POST'])
def api_create_room():
    data = request.json or {}
    board_size = normalize_board_size(data.get('board_size', 3))
    player_id = secrets.token_urlsafe(16)
    now = time.time()
    with rooms_lock:
        cleanup_rooms()
        code = generate_room_code()
        room = {
            'code': code,
            'board_size': board_size,
            'board': empty_board(board_size),
            'current_player': 'X',
            'status': 'waiting',
            'winner': None,
            'winning_line': None,
            'players': {
                'X': {'id': player_id, 'name': clean_player_name(data.get('player_x_name'), 'Player X')},
                'O': None,
            },
            'names': {
                'X': clean_player_name(data.get('player_x_name'), 'Player X'),
                'O': clean_player_name(data.get('player_o_name'), 'Player O'),
            },
            'moves': [],
            'last_move': None,
            'league': clean_player_name(data.get('league'), 'General'),
            'version': 0,
            'trophy_awarded': False,
            'created_at': now,
            'updated_at': now,
        }
        rooms[code] = room
        payload = public_room(room)
    return jsonify({
        'status': 'ok',
        'room': payload,
        'player': {'id': player_id, 'symbol': 'X'},
        'share_url': build_room_url(code),
    })


@app.route('/api/rooms/<room_code>/join', methods=['POST'])
def api_join_room(room_code):
    code = normalize_room_code(room_code)
    data = request.json or {}
    player_id = data.get('player_id') or secrets.token_urlsafe(16)
    with rooms_lock:
        room = rooms.get(code)
        if not room:
            return jsonify({'status': 'error', 'message': 'Room not found'}), 404

        existing_symbol = find_room_player(room, player_id)
        if existing_symbol:
            room['updated_at'] = time.time()
            return jsonify({
                'status': 'ok',
                'room': public_room(room),
                'player': {'id': player_id, 'symbol': existing_symbol},
                'share_url': build_room_url(code),
            })

        if room['players'].get('O') is not None:
            return jsonify({'status': 'error', 'message': 'Room is full', 'room': public_room(room)}), 409

        room['players']['O'] = {
            'id': player_id,
            'name': clean_player_name(data.get('player_name'), room['names'].get('O', 'Player O')),
        }
        room['names']['O'] = room['players']['O']['name']
        if room['status'] == 'waiting':
            room['status'] = 'active'
        room['version'] += 1
        room['updated_at'] = time.time()
        payload = public_room(room)

    return jsonify({
        'status': 'ok',
        'room': payload,
        'player': {'id': player_id, 'symbol': 'O'},
        'share_url': build_room_url(code),
    })


@app.route('/api/rooms/<room_code>', methods=['GET'])
def api_get_room(room_code):
    code = normalize_room_code(room_code)
    with rooms_lock:
        room = rooms.get(code)
        if not room:
            return jsonify({'status': 'error', 'message': 'Room not found'}), 404
        room['updated_at'] = time.time()
        payload = public_room(room)
    return jsonify({'status': 'ok', 'room': payload, 'share_url': build_room_url(code)})


@app.route('/api/rooms/<room_code>/move', methods=['POST'])
def api_room_move(room_code):
    code = normalize_room_code(room_code)
    data = request.json or {}
    with rooms_lock:
        room = rooms.get(code)
        if not room:
            return jsonify({'status': 'error', 'message': 'Room not found'}), 404

        symbol = find_room_player(room, data.get('player_id'))
        if not symbol:
            return jsonify({'status': 'error', 'message': 'Player is not in this room'}), 403

        if room['status'] != 'active':
            return jsonify({'status': 'error', 'message': 'Room is not ready', 'room': public_room(room)}), 409

        client_version = data.get('version')
        try:
            version_changed = client_version is not None and int(client_version) != int(room['version'])
        except (TypeError, ValueError):
            version_changed = True
        if version_changed:
            return jsonify({'status': 'error', 'message': 'Board changed', 'room': public_room(room)}), 409

        if symbol != room['current_player']:
            return jsonify({'status': 'error', 'message': 'Not your turn', 'room': public_room(room)}), 409

        try:
            row = int(data.get('row'))
            col = int(data.get('col'))
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'Invalid move'}), 400

        size = room['board_size']
        if row not in range(size) or col not in range(size):
            return jsonify({'status': 'error', 'message': 'Move outside board'}), 400
        if room['board'][row][col] != EMPTY:
            return jsonify({'status': 'error', 'message': 'Cell already taken', 'room': public_room(room)}), 409

        room['board'][row][col] = symbol
        room['moves'].append({'symbol': symbol, 'row': row, 'col': col})
        room['last_move'] = {'symbol': symbol, 'row': row, 'col': col}
        if check_win(room['board'], symbol):
            set_room_terminal_state(room, symbol)
        elif check_draw(room['board']):
            set_room_terminal_state(room)
        else:
            room['current_player'] = 'O' if symbol == 'X' else 'X'
        room['version'] += 1
        room['updated_at'] = time.time()
        payload = public_room(room)

    return jsonify({'status': 'ok', 'room': payload})


@app.route('/api/rooms/<room_code>/reset', methods=['POST'])
def api_room_reset(room_code):
    code = normalize_room_code(room_code)
    data = request.json or {}
    with rooms_lock:
        room = rooms.get(code)
        if not room:
            return jsonify({'status': 'error', 'message': 'Room not found'}), 404
        symbol = find_room_player(room, data.get('player_id'))
        if not symbol:
            return jsonify({'status': 'error', 'message': 'Player is not in this room'}), 403

        if room['players'].get('O'):
            if room['status'] not in ('win', 'draw'):
                return jsonify({'status': 'error', 'message': 'Finish this round before requesting a rematch', 'room': public_room(room)}), 409
            if data.get('round') != room.get('round', 1):
                return jsonify({'status': 'error', 'message': 'Round changed', 'room': public_room(room)}), 409
            votes = room.setdefault('rematch_votes', [])
            if symbol not in votes:
                votes.append(symbol)
            room['updated_at'] = time.time()
            if len(votes) < 2:
                return jsonify({'status': 'pending', 'room': public_room(room)})

        board_size = normalize_board_size(data.get('board_size', room['board_size']))
        if room['players'].get('O'):
            board_size = room['board_size']
        room['rematch_votes'] = []
        room['round'] = room.get('round', 1) + 1
        room['board_size'] = board_size
        room['board'] = empty_board(board_size)
        room['current_player'] = 'X'
        room['status'] = 'active' if room['players'].get('O') else 'waiting'
        room['winner'] = None
        room['winning_line'] = None
        room['moves'] = []
        room['last_move'] = None
        room['league'] = clean_player_name(data.get('league'), room.get('league') or 'General')
        room['trophy_awarded'] = False
        room['version'] += 1
        room['updated_at'] = time.time()
        payload = public_room(room)

    return jsonify({'status': 'ok', 'room': payload})


@app.route('/play', methods=['POST'])
def play():
    data = request.json or {}
    board = data.get('board')
    difficulty = data.get('difficulty', 'Intermediate')
    # Allow client to tell which symbol the human uses and whether mode is computer
    human_symbol = data.get('player_symbol', 'X')
    mode = data.get('mode', 'computer')

    # Basic validation
    if not isinstance(board, list) or not board or not all(isinstance(row, list) for row in board):
        return jsonify({'status': 'error', 'message': 'Invalid board'}), 400

    size = len(board)
    # normalize any non-square boards defensively
    if any(len(row) != size for row in board):
        return jsonify({'status': 'error', 'message': 'Board must be square'}), 400

    # If not playing vs computer, nothing for server to do
    if mode != 'computer':
        return jsonify({'status': 'no_machine', 'board': board})

    # Determine machine symbol
    machine_symbol = 'O' if human_symbol == 'X' else 'X'

    # 1. Check if the human player already won (server-side validation)
    if check_win(board, human_symbol):
        winning_line = get_winning_line(board, human_symbol)
        return jsonify({'status': 'win', 'winner': human_symbol, 'board': board, 'winning_line': winning_line})

    if check_draw(board):
        return jsonify({'status': 'draw', 'board': board})

    # 2. Optionally create RNG for deterministic behavior
    seed = data.get('seed', None)
    if seed is not None:
        try:
            rng = random.Random(seed)
        except Exception:
            rng = random
    else:
        rng = random

    # 3. Machine calculates its move
    machine_move = get_machine_move(board, machine_symbol, human_symbol, difficulty, rng=rng)
    machine_move_coords = None
    if machine_move:
        row, col = machine_move
        machine_move_coords = [row, col]
        board[row][col] = machine_symbol

    # 3. Check if the machine won after making its move
    if check_win(board, machine_symbol):
        winning_line = get_winning_line(board, machine_symbol)
        return jsonify({
            'status': 'win',
            'winner': machine_symbol,
            'board': board,
            'machine_move': machine_move_coords,
            'winning_line': winning_line,
        })

    if check_draw(board):
        return jsonify({'status': 'draw', 'board': board, 'machine_move': machine_move_coords})

    return jsonify({'status': 'continue', 'board': board, 'machine_move': machine_move_coords})

# API endpoints using SQLite-backed persistence
@app.route('/api/trophies', methods=['GET'])
def api_get_trophies():
    return jsonify({'trophies': get_all_trophies()})

@app.route('/api/trophies', methods=['POST'])
def api_post_trophies():
    payload = request.json or {}
    league = payload.get('league', 'General')
    winner = payload.get('winner')
    if winner not in ('X', 'O'):
        return jsonify({'status': 'error', 'message': 'Invalid winner'}), 400
    increment_trophy(league, winner)
    return jsonify({'status': 'ok', 'trophies': get_all_trophies()})


# Backwards-compatible routes used by some clients/tests
@app.route('/trophies', methods=['GET'])
def trophies_get_compat():
    return api_get_trophies()

@app.route('/trophies', methods=['POST'])
def trophies_post_compat():
    return api_post_trophies()

@app.route('/api/unlocks', methods=['GET'])
def api_get_unlocks():
    return jsonify({'unlocks': get_all_unlocks()})

@app.route('/api/unlocks', methods=['POST'])
def api_post_unlocks():
    payload = request.json or {}
    league = payload.get('league')
    unlocked = bool(payload.get('unlocked', True))
    if not league:
        return jsonify({'status': 'error', 'message': 'league required'}), 400
    set_unlock(league, unlocked)
    return jsonify({'status': 'ok', 'unlocks': get_all_unlocks()})

@app.route('/api/challenge', methods=['POST'])
def api_post_challenge():
    payload = request.json or {}
    league = payload.get('league', 'General')
    winner = payload.get('winner')
    if winner not in ('X', 'O'):
        return jsonify({'status': 'error', 'message': 'Invalid winner'}), 400
    # increment challenge count (assume winner is the player who completed a challenge)
    count = inc_challenge_count(league)
    unlocked = None
    threshold = 1
    order = LEAGUE_ORDER
    if count >= threshold:
        if league in order:
            idx = order.index(league)
            if idx < len(order) - 1:
                next_league = order[idx + 1]
                set_unlock(next_league, True)
                unlocked = next_league
        reset_challenge_count(league)
    return jsonify({'status': 'ok', 'count': count, 'unlocked': unlocked, 'unlocks': get_all_unlocks()})

@app.route('/admin')
def admin_view():
    trophies = get_all_trophies()
    unlocks = get_all_unlocks()
    challenge_rows = {}
    conn = get_conn(); c = conn.cursor(); c.execute('SELECT league, count FROM challenge'); rows = c.fetchall(); conn.close()
    for r in rows:
        challenge_rows[r['league']] = int(r['count'])
    html = ['<html><head><title>Admin - TIC TAC TOE</title></head><body><h1>Admin</h1>']
    html.append('<h2>Trophies</h2><ul>')
    for league, counts in trophies.items():
        html.append(f"<li>{league}: X={counts.get('X',0)} O={counts.get('O',0)}</li>")
    html.append('</ul>')
    html.append('<h2>Unlocks</h2><ul>')
    for league, val in unlocks.items():
        html.append(f"<li>{league}: {'Unlocked' if val else 'Locked'}</li>")
    html.append('</ul>')
    html.append('<h2>Challenge Progress</h2><ul>')
    for league, cnt in challenge_rows.items():
        html.append(f"<li>{league}: {cnt}</li>")
    html.append('</ul>')
    html.append('</body></html>')
    return '\n'.join(html)

if __name__ == '__main__':
    app.run(host=os.environ.get('FLASK_RUN_HOST', '0.0.0.0'), port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG') == '1')
