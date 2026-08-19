from flask import Flask, render_template, request, jsonify
from tic_tac_toe import check_win, check_draw, get_machine_move, EMPTY

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/play', methods=['POST'])
def play():
    data = request.json
    board = data['board']
    difficulty = data.get('difficulty', 'Intermediate')

    # 1. Check if the human player already won
    if check_win(board, 'X'):
        return jsonify({'status': 'win', 'winner': 'X', 'board': board})
    if check_draw(board):
        return jsonify({'status': 'draw', 'board': board})

    # 2. Machine calculates its move
    machine_move = get_machine_move(board, 'O', 'X', difficulty)

    if machine_move:
        row, col = machine_move
        board[row][col] = 'O'

    # 3. Check if the machine won after making its move
    if check_win(board, 'O'):
        return jsonify({'status': 'win', 'winner': 'O', 'board': board})
    if check_draw(board):
        return jsonify({'status': 'draw', 'board': board})

    return jsonify({'status': 'continue', 'board': board})

if __name__ == '__main__':
    app.run(debug=True)