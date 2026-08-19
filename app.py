from flask import Flask, render_template, request, jsonify
import random
from tic_tac_toe import check_win, check_draw, get_machine_move, get_winning_line, EMPTY

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

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

if __name__ == '__main__':
    app.run(debug=True)